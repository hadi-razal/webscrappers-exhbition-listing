#!/usr/bin/env python3
"""
TFWA World Exhibition & Conference 2025 - Exhibitor Scraper
Scrapes all 482 exhibitors across 10 pages and exports to Excel.
Uses concurrent threads to open multiple pages simultaneously (fast mode).
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random
import re
from urllib.parse import urljoin

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BASE_URL = "https://www.tfwa.com"
LIST_URL = "https://www.tfwa.com/exhibitors/tfwa-world-exhibition-and-conference/2025"
TOTAL_PAGES = 10          # pages 0–9
MAX_WORKERS = 10          # concurrent threads (like 10 tabs open at once)
DELAY_MIN = 0.5           # min delay between requests (be polite)
DELAY_MAX = 1.5           # max delay between requests
OUTPUT_FILE = "tfwa_exhibitors_2025.xlsx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)


# ─────────────────────────────────────────────
# STEP 1: Collect all exhibitor URLs from listing pages
# ─────────────────────────────────────────────
def get_exhibitor_links_from_page(page_num: int) -> list[dict]:
    """Scrape one listing page and return list of {name, url} dicts."""
    url = f"{LIST_URL}?page={page_num}"
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [ERROR] Failed to load listing page {page_num}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    exhibitors = []

    # Each exhibitor name is an <h2> containing an <a> link
    for heading in soup.select("main h2"):
        link_tag = heading.find("a", href=True)
        if link_tag:
            name = link_tag.get_text(strip=True)
            href = link_tag["href"]
            full_url = urljoin(BASE_URL, href)
            exhibitors.append({"name": name, "url": full_url})

    print(f"  Page {page_num}: found {len(exhibitors)} exhibitors")
    return exhibitors


def collect_all_links() -> list[dict]:
    """Collect all exhibitor links across all listing pages."""
    print(f"\n[1/3] Collecting exhibitor links from {TOTAL_PAGES} pages...")
    all_links = []
    for page_num in range(0, TOTAL_PAGES):
        links = get_exhibitor_links_from_page(page_num)
        all_links.extend(links)
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    print(f"  Total exhibitors found: {len(all_links)}")
    return all_links


# ─────────────────────────────────────────────
# STEP 2: Scrape each exhibitor's detail page
# ─────────────────────────────────────────────
def scrape_exhibitor_page(exhibitor: dict) -> dict:
    """
    Open one exhibitor detail page and extract all available fields.
    Returns a dict with all data (missing fields = empty string).
    """
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    data = {
        "Name":             exhibitor["name"],
        "URL":              exhibitor["url"],
        "Member Status":    "",
        "Company Name":     "",   # legal company name (may differ from brand)
        "Product Category": "",
        "Event":            "",
        "Stand Number":     "",
        "Village/Location": "",
        "Address Line 1":   "",
        "Address Line 2":   "",
        "City":             "",
        "Postcode":         "",
        "Country":          "",
        "Website":          "",
        "Logo URL":         "",
    }

    try:
        resp = session.get(exhibitor["url"], timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [ERROR] {exhibitor['name']}: {e}")
        return data

    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find("main") or soup

    # ── Member Status ──────────────────────────────────
    member_tag = main.find(string=re.compile(r"MEMBER", re.I))
    if member_tag:
        data["Member Status"] = member_tag.strip()

    # ── Product Category ──────────────────────────────
    # It appears as a <p> or <div> right after the heading
    # Pattern: contains "/" and known categories
    category_patterns = [
        "Wine", "Spirits", "Perfumes", "Cosmetics", "Fashion",
        "Accessories", "Confectionery", "Jewellery", "Electronics",
        "Tobacco", "Gifts", "Toys"
    ]
    for tag in main.find_all(["p", "div", "span", "generic"]):
        text = tag.get_text(strip=True)
        if any(cat in text for cat in category_patterns) and "/" in text and len(text) < 200:
            data["Product Category"] = text
            break

    # ── Stand Number and Village ───────────────────────
    # Pattern: letter + number(s) + village name
    stand_pattern = re.compile(
        r'\b([A-Z]{1,3}\s*\d+(?:-\d+)?)\b'   # e.g. "L 62", "H 15", "51-55"
    )
    village_keywords = ["Village", "Terrace", "Foyer", "Beach", "Riviera",
                        "Ambassadeurs", "Level", "Marine", "Harbour"]

    page_text = main.get_text(separator=" ")

    stand_match = stand_pattern.search(page_text)
    if stand_match:
        data["Stand Number"] = stand_match.group(0).strip()

    for keyword in village_keywords:
        kw_pattern = re.compile(rf'({keyword}[^,\n]{{0,30}})', re.I)
        kw_match = kw_pattern.search(page_text)
        if kw_match:
            data["Village/Location"] = kw_match.group(0).strip()
            break

    # ── Event ──────────────────────────────────────────
    event_match = re.search(r'TFWA World Exhibition[^>]{0,60}', page_text)
    if event_match:
        data["Event"] = event_match.group(0).strip()

    # ── Address ────────────────────────────────────────
    # Address block is usually after an "Address" heading
    addr_heading = main.find(string=re.compile(r'^Address$', re.I))
    if addr_heading:
        # Walk siblings/parent children after the heading
        parent = addr_heading.find_parent()
        if parent:
            siblings = list(parent.next_siblings)
            addr_lines = []
            for sib in siblings[:6]:  # collect up to 6 lines
                line = sib.get_text(strip=True) if hasattr(sib, 'get_text') else str(sib).strip()
                if line and "Website" not in line and "Contact" not in line and len(line) < 100:
                    addr_lines.append(line)
                elif "Website" in line or "Contact" in line:
                    break

            # Parse address lines
            if len(addr_lines) >= 1:
                data["Address Line 1"] = addr_lines[0]
            if len(addr_lines) >= 2:
                data["Address Line 2"] = addr_lines[1]
            if len(addr_lines) >= 3:
                # Try to detect postcode + city
                postcode_city = addr_lines[2]
                pc_match = re.match(r'(\d{4,6})\s+(.*)', postcode_city)
                if pc_match:
                    data["Postcode"] = pc_match.group(1)
                    data["City"] = pc_match.group(2)
                else:
                    data["City"] = postcode_city
            if len(addr_lines) >= 4:
                data["Country"] = addr_lines[-1]

    # ── Website ────────────────────────────────────────
    website_tag = main.find("a", href=re.compile(r'^https?://(?!www\.tfwa\.com)'))
    if website_tag:
        data["Website"] = website_tag["href"]

    # ── Legal Company Name (from logo alt text) ────────
    logo = main.find("img")
    if logo and logo.get("alt"):
        data["Company Name"] = logo["alt"].strip()

    # ── Logo URL ───────────────────────────────────────
    if logo and logo.get("src"):
        data["Logo URL"] = urljoin(BASE_URL, logo["src"])

    print(f"  ✓ {exhibitor['name']}")
    return data


# ─────────────────────────────────────────────
# STEP 3: Run concurrent scraping (parallel tabs)
# ─────────────────────────────────────────────
def scrape_all_exhibitors(exhibitor_list: list[dict]) -> list[dict]:
    """
    Open MAX_WORKERS pages concurrently (like having many browser tabs open).
    Returns list of scraped data dicts.
    """
    print(f"\n[2/3] Scraping {len(exhibitor_list)} exhibitor pages "
          f"with {MAX_WORKERS} concurrent workers...\n")
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_exhibitor = {
            executor.submit(scrape_exhibitor_page, ex): ex
            for ex in exhibitor_list
        }
        for i, future in enumerate(as_completed(future_to_exhibitor), 1):
            try:
                result = future.result()
                results.append(result)
                if i % 50 == 0:
                    print(f"\n  ── Progress: {i}/{len(exhibitor_list)} done ──\n")
            except Exception as e:
                ex = future_to_exhibitor[future]
                print(f"  [ERROR] {ex['name']}: {e}")
    return results


# ─────────────────────────────────────────────
# STEP 4: Export to Excel
# ─────────────────────────────────────────────
def export_to_excel(data: list[dict], filename: str):
    """Save scraped data to a formatted Excel file."""
    print(f"\n[3/3] Exporting {len(data)} records to Excel: {filename}")
    df = pd.DataFrame(data)

    # Sort alphabetically by exhibitor name
    df.sort_values("Name", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Replace empty strings with NaN for cleaner Excel output
    df.replace("", pd.NA, inplace=True)

    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Exhibitors 2025")

        # Auto-fit column widths
        ws = writer.sheets["Exhibitors 2025"]
        for col in ws.columns:
            max_len = max(
                (len(str(cell.value)) if cell.value else 0 for cell in col), default=10
            )
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

        # Freeze top row (header)
        ws.freeze_panes = "A2"

    print(f"  ✅ Done! File saved: {filename}")
    print(f"  📊 Total rows: {len(df)}")
    print(f"\n  Missing data summary:")
    for col in df.columns:
        missing = df[col].isna().sum()
        if missing > 0:
            print(f"    {col}: {missing} missing ({missing/len(df)*100:.1f}%)")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  TFWA 2025 Exhibitor Scraper")
    print("  Target: 482 exhibitors across 10 pages")
    print("=" * 60)

    # Step 1: Get all exhibitor links
    exhibitor_links = collect_all_links()

    # Step 2: Scrape each exhibitor page concurrently
    all_data = scrape_all_exhibitors(exhibitor_links)

    # Step 3: Export to Excel
    export_to_excel(all_data, OUTPUT_FILE)

    print("\n✅ Scraping complete!")