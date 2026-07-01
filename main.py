from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import requests
import re
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import quote
from playwright.async_api import async_playwright

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(title="Moroccan Cassation Court Search Skill")

class SearchRequest(BaseModel):
    query: str
    chamber_id: Optional[int] = None
    decision_number: Optional[str] = None
    file_number: Optional[str] = None
    date: Optional[str] = None

class JurisCassationClient:
    BASE_URL = "https://juriscassation.cspj.ma"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.token = self._get_csrf_token()
    
    def _get_csrf_token(self):
        try:
            r = self.session.get(f"{self.BASE_URL}/Decisions/RechercheDecisions", timeout=10)
            r.raise_for_status()
            m = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', r.text)
            return m.group(1) if m else None
        except Exception as e:
            print(f"Error fetching CSRF token: {e}")
            return None
            
    def search(self, subject: str, chamber_id=None, decision_number=None, file_number=None, date=None) -> List[Dict]:
        if not self.token:
            self.token = self._get_csrf_token()
            
        if not self.token:
            raise Exception("Could not obtain CSRF token from CSPJ.")

        data = {
            "NumeroDos": file_number or "",
            "NumeroDec": decision_number or "",
            "DateDec": date or "",
            "ChambreIds": str(chamber_id) if chamber_id else "",
            "DecisionPriseParId": "",
            "Sujet": subject,
            "__RequestVerificationToken": self.token
        }
        
        try:
            r = self.session.post(
                f"{self.BASE_URL}/Decisions/RechercheDecisionsRes",
                data=data,
                timeout=15
            )
            r.raise_for_status()
            return self._parse_results(r.text)
        except Exception as e:
            print(f"Error during search POST: {e}")
            return []
            
    def _parse_results(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        # Usually results are in a table or specific divs, we will attempt to extract rows
        table = soup.find("table", {"id": "table-data"})
        if not table:
            # Fallback parse logic if table id is different, assuming standard table classes
            table = soup.find("table")
            
        if not table:
            return results
            
        tbody = table.find("tbody")
        if not tbody: return results
        
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 5: continue
            
            # This extraction logic may need adjustment based on actual HTML structure
            case_info = {
                "file_number": tds[0].text.strip(),
                "decision_number": tds[1].text.strip(),
                "date": tds[2].text.strip(),
                "chamber": tds[3].text.strip(),
                "subject": tds[4].text.strip()
            }
            
            # Find PDF link
            pdf_link = tr.find("a", href=re.compile(r"GetArret"))
            if pdf_link:
                href = pdf_link.get("href")
                # e.g. /Decisions/GetArret?encryptedId=XYZ
                case_info["pdf_url"] = f"{self.BASE_URL}{href}"
                
            results.append(case_info)
            
        return results

class JurisprudenceClient:
    BASE_URL = "https://www.jurisprudence.ma/"
    
    def search(self, query: str) -> List[Dict]:
        results = []
        try:
            r = requests.get(self.BASE_URL, params={"s": query}, headers={"User-Agent": "Mozilla/5.0"}, verify=False, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Simple WordPress search parsing
            articles = soup.find_all("article")
            for article in articles:
                title_tag = article.find("h2") or article.find("h3")
                if not title_tag: continue
                
                link_tag = title_tag.find("a")
                if not link_tag: continue
                
                results.append({
                    "title": link_tag.text.strip(),
                    "link": link_tag.get("href"),
                    "source": "jurisprudence.ma"
                })
        except Exception as e:
            print(f"Error scraping jurisprudence.ma: {e}")
            
        return results

class AdalaClient:
    BASE_URL = "https://adala.justice.gov.ma/search"
    
    async def search(self, query: str) -> List[Dict]:
        results = []
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(f"{self.BASE_URL}?term={quote(query)}&type=rapid_search")
                # Wait for results to load (e.g. some element that indicates results)
                # Next.js CSR will populate the DOM
                try:
                    await page.wait_for_selector("div.search-result-item, article, .result-card", timeout=5000)
                except Exception:
                    # Timeout waiting for results
                    pass
                
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Adala results are usually inside cards or list items.
                # Since we don't know the exact class, we grab links that look like result links or have titles
                links = soup.find_all("a", href=True)
                seen_hrefs = set()
                for a in links:
                    href = a.get("href")
                    # Try to filter only relevant links to documents/decisions
                    if href and ('/resource/' in href or '/law/' in href or '/decision/' in href):
                        if href not in seen_hrefs:
                            seen_hrefs.add(href)
                            results.append({
                                "title": a.text.strip() or "Adala Document",
                                "link": f"https://adala.justice.gov.ma{href}" if href.startswith('/') else href,
                                "source": "adala.justice.gov.ma"
                            })
                
                await browser.close()
        except Exception as e:
            print(f"Error scraping adala.justice.gov.ma: {e}")
            
        return results

@app.post("/search")
async def search_decisions(req: SearchRequest):
    client_cspj = JurisCassationClient()
    client_juris = JurisprudenceClient()
    client_adala = AdalaClient()
    
    results = []
    
    # Primary Source
    try:
        cspj_results = client_cspj.search(
            subject=req.query,
            chamber_id=req.chamber_id,
            decision_number=req.decision_number,
            file_number=req.file_number,
            date=req.date
        )
        for r in cspj_results:
            r["source"] = "juriscassation.cspj.ma"
        results.extend(cspj_results)
    except Exception as e:
        print(f"CSPJ Search error: {e}")

    # Fallback/Secondary Source
    try:
        juris_results = client_juris.search(query=req.query)
        results.extend(juris_results)
    except Exception as e:
        print(f"Jurisprudence Search error: {e}")

    # Adala Source
    try:
        adala_results = await client_adala.search(query=req.query)
        results.extend(adala_results)
    except Exception as e:
        print(f"Adala Search error: {e}")

    return {"status": "success", "results": results, "count": len(results)}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
