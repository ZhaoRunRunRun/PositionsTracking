#!/usr/bin/env python3
import json
import re
import time
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_FILE = DATA_DIR / "positions.json"
YEARS_BACK = 10
TOP_HOLDINGS = 12
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"

INVESTORS = [
    {"name": "Warren Buffett", "entity": "Berkshire Hathaway", "query": "warren buffett", "color": "#f59e0b"},
    {"name": "Michael Burry", "entity": "Scion Asset Management", "query": "michael burry", "color": "#22c55e"},
    {"name": "Bill Ackman", "entity": "Pershing Square Capital Management", "query": "bill ackman", "color": "#38bdf8"},
    {"name": "David Tepper", "entity": "Appaloosa", "query": "david tepper", "color": "#fb7185"},
    {"name": "Ray Dalio", "entity": "Bridgewater Associates", "query": "ray dalio", "color": "#a78bfa"},
    {"name": "Carl Icahn", "entity": "Icahn Capital", "query": "carl icahn", "color": "#f97316"},
    {"name": "Dan Loeb", "entity": "Third Point", "query": "dan loeb", "color": "#2dd4bf"},
    {"name": "Seth Klarman", "entity": "Baupost Group", "query": "seth klarman", "color": "#f43f5e"},
    {"name": "Stanley Druckenmiller", "entity": "Duquesne Family Office", "query": "stanley druckenmiller", "color": "#84cc16"},
    {"name": "Bill Gates", "entity": "Gates Foundation Trust", "query": "bill gates", "color": "#06b6d4"},
]


def fetch(url: str, accept: str = "text/html,application/json;q=0.9,*/*;q=0.8") -> str:
    req = Request(url, headers={"User-Agent": UA, "Accept": accept, "X-Requested-With": "XMLHttpRequest"})
    with urlopen(req, timeout=40) as resp:
        time.sleep(0.15)
        return resp.read().decode("utf-8", "ignore")


def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def parse_money_thousands(text: str) -> int:
    cleaned = re.sub(r"[^\d.-]", "", text)
    return int(float(cleaned or 0) * 1000)


def parse_int(text: str) -> int:
    cleaned = re.sub(r"[^\d.-]", "", text)
    return int(float(cleaned or 0))


def quarter_key(label: str) -> tuple:
    m = re.search(r"Q([1-4])\s+(\d{4})", label)
    if not m:
        return (0, 0)
    return (int(m.group(2)), int(m.group(1)))


def quarter_to_date(label: str) -> str:
    year, quarter = quarter_key(label)
    end = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}.get(quarter, "12-31")
    return f"{year}-{end}"


def find_manager_url(query: str) -> str:
    body = fetch(f"https://13f.info/data/autocomplete?q={quote(query)}", accept="application/json,text/plain,*/*")
    data = json.loads(body)
    managers = data.get("managers", [])
    if not managers:
        raise RuntimeError(f"No manager match for {query}")
    return urljoin("https://13f.info", managers[0]["url"])


def parse_manager_page(html: str):
    table_match = re.search(r'<table[^>]*id="managerFilings"[^>]*>.*?<tbody[^>]*>(.*?)</tbody>', html, re.S)
    if not table_match:
        raise RuntimeError("managerFilings table not found")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_match.group(1), re.S)
    timeline = []
    filings = []
    cutoff_year = datetime.utcnow().year - YEARS_BACK
    for row in rows:
        cols = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cols) < 7:
            continue
        quarter = strip_tags(cols[0])
        link_match = re.search(r'href="([^"]+)"', cols[0])
        if not link_match:
            continue
        year, _q = quarter_key(quarter)
        if year < cutoff_year:
            continue
        holdings = parse_int(cols[1])
        portfolio_value = parse_money_thousands(cols[2])
        top_holding = strip_tags(cols[3]).split(",")[0].strip()
        filing_date = strip_tags(cols[5])
        filings.append(urljoin("https://13f.info", link_match.group(1)))
        timeline.append(
            {
                "date": quarter_to_date(quarter),
                "quarter": quarter.replace(" ", "-"),
                "portfolioValue": portfolio_value,
                "holdingsCount": holdings,
                "topHolding": top_holding,
                "filedAt": filing_date,
            }
        )
    timeline.sort(key=lambda item: item["date"])
    filings.reverse()
    return timeline, filings


def parse_filing_data_url(html: str) -> str:
    m = re.search(r'<table[^>]*id="filingAggregated"[^>]*data-url="([^"]+)"', html)
    if not m:
        raise RuntimeError("filing data url not found")
    return urljoin("https://13f.info", m.group(1))


def fetch_holdings(filing_url: str):
    html = fetch(filing_url)
    data_url = parse_filing_data_url(html)
    payload = json.loads(fetch(data_url, accept="application/json,text/plain,*/*"))
    rows = payload.get("data", [])
    holdings = []
    for row in rows[:TOP_HOLDINGS]:
        holdings.append(
            {
                "symbol": row[0],
                "name": row[1],
                "title": row[2],
                "cusip": row[3],
                "value": int(row[4]) * 1000,
                "weight": float(row[5] or 0),
                "shares": int(row[6] or 0),
                "putCall": row[8],
            }
        )
    return holdings


def compare_holdings(current, previous):
    prev_map = {item["cusip"] or item["name"]: item for item in previous}
    current_keys = set()
    changes = []
    for item in current:
        key = item["cusip"] or item["name"]
        current_keys.add(key)
        prev = prev_map.get(key)
        prev_value = prev["value"] if prev else 0
        diff = item["value"] - prev_value
        status = "new" if not prev else "flat" if diff == 0 else "increased" if diff > 0 else "reduced"
        changes.append({"name": item["name"], "cusip": item["cusip"], "value": item["value"], "previousValue": prev_value, "diffValue": diff, "status": status})
    for item in previous:
        key = item["cusip"] or item["name"]
        if key in current_keys:
            continue
        changes.append({"name": item["name"], "cusip": item["cusip"], "value": 0, "previousValue": item["value"], "diffValue": -item["value"], "status": "exited"})
    return sorted(changes, key=lambda x: abs(x["diffValue"]), reverse=True)[:TOP_HOLDINGS]


def fetch_investor_data(investor):
    manager_url = find_manager_url(investor["query"])
    timeline, filing_urls = parse_manager_page(fetch(manager_url))
    if len(timeline) < 1 or len(filing_urls) < 1:
        raise RuntimeError(f"No filing timeline for {investor['name']}")
    latest_holdings = fetch_holdings(filing_urls[0])
    previous_holdings = fetch_holdings(filing_urls[1]) if len(filing_urls) > 1 else []
    latest_value = timeline[-1]["portfolioValue"]
    prev_value = timeline[-2]["portfolioValue"] if len(timeline) > 1 else 0
    return {
        "name": investor["name"],
        "entity": investor["entity"],
        "sourceUrl": manager_url,
        "accent": investor["color"],
        "latestQuarter": timeline[-1]["quarter"],
        "latestDate": timeline[-1]["date"],
        "latestPortfolioValue": latest_value,
        "portfolioValueChange": latest_value - prev_value,
        "timeline": timeline,
        "latestHoldings": latest_holdings,
        "changes": compare_holdings(latest_holdings, previous_holdings),
    }


def build_dashboard(investors):
    rankings = []
    spotlight = []
    for inv in investors:
        rankings.append({
            "name": inv["name"],
            "entity": inv["entity"],
            "quarter": inv["latestQuarter"],
            "portfolioValue": inv["latestPortfolioValue"],
            "valueChange": inv["portfolioValueChange"],
            "topHolding": inv["latestHoldings"][0]["name"] if inv["latestHoldings"] else "-",
        })
        for change in inv["changes"][:3]:
            spotlight.append({"investor": inv["name"], "entity": inv["entity"], **change})
    rankings.sort(key=lambda item: item["portfolioValue"], reverse=True)
    spotlight.sort(key=lambda item: abs(item["diffValue"]), reverse=True)
    return {
        "generatedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "yearsBack": YEARS_BACK,
        "investorCount": len(investors),
        "rankings": rankings,
        "spotlightChanges": spotlight[:12],
        "investors": investors,
        "errors": [],
    }


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    investors = []
    errors = []
    for investor in INVESTORS:
        try:
            investors.append(fetch_investor_data(investor))
        except Exception as err:
            errors.append({"investor": investor["name"], "error": str(err)})
    if not investors:
        raise RuntimeError(f"All investor fetches failed: {errors}")
    payload = build_dashboard(investors)
    payload["errors"] = errors
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE} with {len(investors)} investors; errors={len(errors)}")


if __name__ == "__main__":
    main()
