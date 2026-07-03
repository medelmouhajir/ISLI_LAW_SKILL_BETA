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


class SourceResult(BaseModel):
    status: str
    count: int
    results: List[Dict]
    error: Optional[str] = None


class SearchResponse(BaseModel):
    status: str
    query: str
    count: int
    total: int
    results: List[Dict]
    sources: Dict[str, SourceResult]


class JurisCassationClient:
    BASE_URL = "https://juriscassation.cspj.ma"
    CHAMBERS = {
        1: "الغرفة المدنية",
        2: "غرفة الأحوال الشخصية والميراث",
        3: "الغرفة التجارية",
        4: "الغرفة الإدارية",
        5: "الغرفة الاجتماعية",
        6: "الغرفة الجنائية",
        7: "الغرفة العقارية",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "ar,fr;q=0.9,en;q=0.8",
        })
        self.token = None

    def _get_csrf_token(self) -> Optional[str]:
        try:
            r = self.session.get(
                f"{self.BASE_URL}/Decisions/RechercheDecisions",
                timeout=15,
                headers={"Referer": f"{self.BASE_URL}/Decisions/RechercheDecisions"},
            )
            r.raise_for_status()
            m = re.search(
                r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"',
                r.text,
            )
            token = m.group(1) if m else None
            if not token:
                # Try alternative patterns used by ASP.NET Core anti-forgery tokens
                m = re.search(
                    r'value="(CfDJ[^"]+)"[^>]*name="__RequestVerificationToken"',
                    r.text,
                )
                token = m.group(1) if m else None
            self.token = token
            return token
        except Exception as e:
            return None

    def _refresh_token(self) -> Optional[str]:
        self.session.cookies.clear()
        return self._get_csrf_token()

    def search(
        self,
        subject: str,
        chamber_id=None,
        decision_number=None,
        file_number=None,
        date=None,
    ) -> SourceResult:
        if not self.token:
            self._get_csrf_token()

        if not self.token:
            return SourceResult(
                status="error",
                count=0,
                results=[],
                error="Could not obtain CSRF token from CSPJ.",
            )

        data = {
            "NumeroDos": file_number or "",
            "NumeroDec": decision_number or "",
            "DateDec": date or "",
            "ChambreIds": str(chamber_id) if chamber_id else "",
            "DecisionPriseParId": "",
            "Sujet": subject,
            "__RequestVerificationToken": self.token,
        }

        referer = f"{self.BASE_URL}/Decisions/RechercheDecisions"

        try:
            r = self.session.post(
                f"{self.BASE_URL}/Decisions/RechercheDecisionsRes",
                data=data,
                timeout=20,
                headers={
                    "Referer": referer,
                    "Origin": self.BASE_URL,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            r.raise_for_status()

            # Sometimes CSPJ returns the search page again with a new token if
            # the previous one expired. Detect that and retry once.
            if "__RequestVerificationToken" in r.text and not self._parse_results(
                r.text, chamber_id=chamber_id
            ):
                new_token = self._refresh_token()
                if new_token:
                    data["__RequestVerificationToken"] = new_token
                    r = self.session.post(
                        f"{self.BASE_URL}/Decisions/RechercheDecisionsRes",
                        data=data,
                        timeout=20,
                        headers={
                            "Referer": referer,
                            "Origin": self.BASE_URL,
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                    )
                    r.raise_for_status()

            results = self._parse_results(r.text, chamber_id=chamber_id)
            return SourceResult(
                status="ok",
                count=len(results),
                results=results,
            )
        except requests.exceptions.Timeout:
            return SourceResult(
                status="error",
                count=0,
                results=[],
                error="CSPJ search request timed out.",
            )
        except requests.exceptions.HTTPError as e:
            return SourceResult(
                status="error",
                count=0,
                results=[],
                error=f"CSPJ returned HTTP error: {e.response.status_code}.",
            )
        except Exception as e:
            return SourceResult(
                status="error",
                count=0,
                results=[],
                error=f"CSPJ search failed: {str(e)}",
            )

    def _parse_results(self, html: str, chamber_id: Optional[int] = None) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # CSPJ renders results in a table whose observed id is "myid" and whose
        # headers are: رقم الملف | رقم القرار | تاريخ القرار | المفاتيح أو القاعدة أو المحتوى | تحميل القرار
        table = (
            soup.find("table", {"id": "myid"})
            or soup.find("table", {"id": "table-data"})
            or soup.find("table", {"class": re.compile(r"table[-_]data", re.I)})
            or soup.find("table", {"class": re.compile(r"table", re.I)})
        )

        if table:
            tbody = table.find("tbody") or table
            for tr in tbody.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 4:
                    continue

                row = {
                    "file_number": tds[0].get_text(strip=True),
                    "decision_number": tds[1].get_text(strip=True),
                    "date": tds[2].get_text(strip=True),
                    "subject": tds[3].get_text(strip=True),
                }

                if chamber_id and chamber_id in self.CHAMBERS:
                    row["chamber"] = self.CHAMBERS[chamber_id]

                # The last cell contains the "معاينة القرار" PDF link
                pdf_link = tr.find("a", href=re.compile(r"GetArret"))
                if pdf_link:
                    href = pdf_link.get("href")
                    if href:
                        row["pdf_url"] = (
                            href if href.startswith("http") else f"{self.BASE_URL}{href}"
                        )
                        row["pdf_text"] = pdf_link.get_text(strip=True)

                # Keep rows that have at least a file number or a PDF link
                if row["file_number"] or "pdf_url" in row:
                    results.append(row)

        # Fallback / enrichment: grab any GetArret link even outside a table
        if not results:
            for a in soup.find_all("a", href=re.compile(r"GetArret")):
                href = a.get("href")
                if not href:
                    continue
                title = a.get_text(strip=True) or a.get("title", "")
                row = {
                    "decision_number": title,
                    "pdf_url": (
                        href if href.startswith("http") else f"{self.BASE_URL}{href}"
                    ),
                }
                if chamber_id and chamber_id in self.CHAMBERS:
                    row["chamber"] = self.CHAMBERS[chamber_id]
                results.append(row)

        return results


class JurisprudenceClient:
    BASE_URL = "https://www.jurisprudence.ma/"

    def search(self, query: str) -> SourceResult:
        results = []
        try:
            r = requests.get(
                self.BASE_URL,
                params={"s": query},
                headers={"User-Agent": "Mozilla/5.0"},
                verify=False,
                timeout=15,
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            articles = soup.find_all("article")
            if not articles:
                # Fallback: search result titles are often h2/h3 inside divs with class "post"
                articles = soup.find_all("div", class_=re.compile(r"post|entry|result", re.I))

            for article in articles:
                title_tag = article.find(["h2", "h3"])
                if not title_tag:
                    continue

                link_tag = title_tag.find("a")
                if not link_tag:
                    continue

                title = link_tag.get_text(strip=True)
                href = link_tag.get("href")
                if not title or not href:
                    continue

                results.append({
                    "title": title,
                    "link": href,
                    "source": "jurisprudence.ma",
                })

            return SourceResult(status="ok", count=len(results), results=results)
        except Exception as e:
            return SourceResult(
                status="error",
                count=0,
                results=[],
                error=f"jurisprudence.ma failed: {str(e)}",
            )


class AdalaClient:
    BASE_URL = "https://adala.justice.gov.ma"
    SEARCH_PATH = "/search"

    async def search(self, query: str) -> SourceResult:
        results = []
        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                url = (
                    f"{self.BASE_URL}{self.SEARCH_PATH}"
                    f"?term={quote(query)}&type=rapid_search"
                )
                await page.goto(url, wait_until="networkidle", timeout=20000)

                # Try to wait for dynamic content; do not fail if timeout.
                try:
                    await page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

                content = await page.content()
                soup = BeautifulSoup(content, "html.parser")

                # Next.js sometimes ships initial props in __NEXT_DATA__
                next_data = soup.find("script", id="__NEXT_DATA__")
                if next_data and next_data.string:
                    try:
                        import json

                        data = json.loads(next_data.string)
                        search_res = (
                            data.get("props", {})
                            .get("pageProps", {})
                            .get("searchResult", {})
                        )
                        if isinstance(search_res, dict):
                            items = search_res.get("data", [])
                            if isinstance(items, list):
                                for item in items:
                                    if isinstance(item, dict):
                                        title = item.get("title") or item.get("name") or "Adala Document"
                                        slug = item.get("slug") or item.get("id")
                                        link = (
                                            f"{self.BASE_URL}/resource/{slug}"
                                            if slug
                                            else None
                                        )
                                        results.append({
                                            "title": title,
                                            "link": link,
                                            "source": "adala.justice.gov.ma",
                                            "raw": item,
                                        })
                    except Exception:
                        pass

                # DOM-level fallback
                if not results:
                    selectors = [
                        "a[href*='/resource/']",
                        "a[href*='/law/']",
                        "a[href*='/decision/']",
                        "a[href*='/text/']",
                        ".search-result-item a",
                        ".result-card a",
                        "article a",
                    ]
                    seen_hrefs = set()
                    for selector in selectors:
                        for a in soup.select(selector):
                            href = a.get("href")
                            if not href:
                                continue
                            # Normalize relative URLs
                            full_href = (
                                href
                                if href.startswith("http")
                                else f"{self.BASE_URL}{href}"
                            )
                            if full_href in seen_hrefs:
                                continue
                            seen_hrefs.add(full_href)
                            text = a.get_text(strip=True) or "Adala Document"
                            results.append({
                                "title": text,
                                "link": full_href,
                                "source": "adala.justice.gov.ma",
                            })

                if browser:
                    await browser.close()
                    browser = None

            return SourceResult(status="ok", count=len(results), results=results)
        except Exception as e:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            return SourceResult(
                status="error",
                count=0,
                results=[],
                error=f"adala.justice.gov.ma failed: {str(e)}",
            )


@app.post("/search", response_model=SearchResponse)
async def search_decisions(req: SearchRequest):
    client_cspj = JurisCassationClient()
    client_juris = JurisprudenceClient()
    client_adala = AdalaClient()

    sources = {}

    # Primary Source: CSPJ
    try:
        sources["cspj"] = client_cspj.search(
            subject=req.query,
            chamber_id=req.chamber_id,
            decision_number=req.decision_number,
            file_number=req.file_number,
            date=req.date,
        )
    except Exception as e:
        sources["cspj"] = SourceResult(
            status="error",
            count=0,
            results=[],
            error=f"Unhandled CSPJ error: {str(e)}",
        )

    # Secondary Source: jurisprudence.ma
    try:
        sources["jurisprudence"] = client_juris.search(query=req.query)
    except Exception as e:
        sources["jurisprudence"] = SourceResult(
            status="error",
            count=0,
            results=[],
            error=f"Unhandled jurisprudence error: {str(e)}",
        )

    # Tertiary Source: adala.justice.gov.ma
    try:
        sources["adala"] = await client_adala.search(query=req.query)
    except Exception as e:
        sources["adala"] = SourceResult(
            status="error",
            count=0,
            results=[],
            error=f"Unhandled adala error: {str(e)}",
        )

    total = sum(s.count for s in sources.values())
    overall_status = "success" if total > 0 else "no_results"
    if any(s.status == "error" for s in sources.values()) and total == 0:
        overall_status = "error"
    elif any(s.status == "error" for s in sources.values()):
        overall_status = "partial_success"

    # Build a flat, backward-compatible `results` list while preserving source info.
    flat_results = []
    for source_name, source in sources.items():
        for item in source.results:
            item = dict(item)
            item["source"] = source_name
            flat_results.append(item)

    return SearchResponse(
        status=overall_status,
        query=req.query,
        count=total,
        total=total,
        results=flat_results,
        sources={name: s.model_dump() for name, s in sources.items()},
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}
