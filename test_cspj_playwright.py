import asyncio
import sys
import io
from main import JurisCassationClient

if sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


async def main():
    client = JurisCassationClient()
    result = await client._search_with_playwright("طلاق", chamber_id=2)
    print(f"status: {result.status}")
    print(f"count: {result.count}")
    print(f"error: {result.error}")
    print(f"meta: {result.meta}")
    for i, r in enumerate(result.results[:3]):
        print(f"\nresult {i+1}:")
        print(f"  file_number: {r.get('file_number')}")
        print(f"  decision_number: {r.get('decision_number')}")
        print(f"  date: {r.get('date')}")
        print(f"  chamber: {r.get('chamber')}")
        print(f"  subject: {r.get('subject', '')[:120]}")
        print(f"  pdf_url: {r.get('pdf_url')}")


asyncio.run(main())
