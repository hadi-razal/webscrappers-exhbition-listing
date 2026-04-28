"""
scrape_cannes_exhibitors.py
============================
Scrapes all 646 exhibitor listings from the Cannes Yachting Festival website.

  https://www.cannesyachtingfestival.com/en-gb/exhibitors/exhibitors-list.html

The page uses React + infinite scroll, so a two-strategy approach is used:

  Strategy 1 – API Discovery (fast, ~5 s)
    The script fetches the listing page, extracts any bundled JS/config that
    reveals the underlying JSON API endpoint, and calls it directly with
    pagination parameters.  No browser needed.

  Strategy 2 – Selenium + headless Chrome (reliable fallback, ~3-5 min)
    A headless Chrome browser is launched, the page is opened, and the script
    auto-scrolls until all cards are visible (count stops increasing),
    then the full HTML is parsed.

Extracted fields
----------------
  Exhibitor_ID, Company, Stand, Description, Brands, Categories,
  Website, Email, Phone, Profile_URL, Logo_URL

Requirements
------------
    pip install selenium webdriver-manager requests beautifulsoup4 pandas openpyxl lxml

Usage
-----
    python scrape_cannes_exhibitors.py                         # auto-detects strategy
    python scrape_cannes_exhibitors.py --strategy api          # force API mode
    python scrape_cannes_exhibitors.py --strategy selenium     # force Selenium mode
    python scrape_cannes_exhibitors.py --output my_file.xlsx   # custom output path
    python scrape_cannes_exhibitors.py --visible               # show browser window
"""

import argparse
import json
import os
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlencode

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_URL      = "https://www.cannesyachtingfestival.com"
LIST_URL      = f"{BASE_URL}/en-gb/exhibitors/exhibitors-list.html"
TOTAL_EXPECT  = 646   # Known exhibitor count – used as scroll-stop signal
SCROLL_PAUSE  = 2.5   # Seconds to wait after each scroll before checking count
MAX_SCROLLS   = 120   # Hard-cap to prevent infinite loops (~646 / 10 per scroll)
REQUEST_TIMEOUT = 30

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": LIST_URL,
}

# Common API endpoint patterns used by the rxweb/EventsAir platform
# The script tries these in order before falling back to Selenium
CANDIDATE_API_PATTERNS = [
    "/api/exhibitors/search",
    "/api/exhibitor/search",
    "/_api/exhibitors",
    "/api/v1/exhibitors",
    "/api/directory/exhibitors",
    "/en-gb/api/exhibitors",
]


# ── Card parser ───────────────────────────────────────────────────────────────

def parse_card(card: BeautifulSoup) -> Dict[str, Optional[str]]:
    """Extract all fields from a single exhibitor card div.

    Handles the exact HTML structure served by the Cannes Yachting Festival
    site as confirmed from the live card markup.
    """
    # ── Exhibitor ID (from data attribute) ────────────────────────────────
    try:
        attrs = json.loads(card.get("data-dtm-attributes", "{}"))
        exhibitor_id = attrs.get("exhibitorId")
    except (json.JSONDecodeError, TypeError):
        exhibitor_id = None

    # ── Company name ──────────────────────────────────────────────────────
    name_tag = card.find("h3", class_="exhibitor-name")
    company  = name_tag.get_text(strip=True) if name_tag else None

    # ── Profile URL ───────────────────────────────────────────────────────
    profile_anchor = card.find("a", href=lambda h: h and "/profil." in h)
    profile_url = (
        urljoin(BASE_URL, profile_anchor["href"]) if profile_anchor else None
    )

    # ── Logo URL ──────────────────────────────────────────────────────────
    logo_img = card.find("div", class_="profile-logo")
    logo_url = None
    if logo_img:
        img = logo_img.find("img", src=True)
        if img:
            logo_url = img["src"]

    # ── Description ───────────────────────────────────────────────────────
    desc_p = card.find("p", {"data-testid": "exh-content"})
    description = desc_p.get_text(strip=True) if desc_p else None

    # ── Brands ────────────────────────────────────────────────────────────
    brands_div = card.find("div", {"data-testid": "exh-brands"})
    brands = None
    if brands_div:
        bp = brands_div.find("p")
        if bp:
            brands = bp.get_text(strip=True)

    # ── Categories ────────────────────────────────────────────────────────
    categories_span = card.find("span", class_="pps-tags")
    categories = categories_span.get_text(strip=True) if categories_span else None

    # ── Stand ─────────────────────────────────────────────────────────────
    # Structure: [SVG icon span][" Stand" span][stand_value spans…]
    stand = None
    stand_div = card.find("div", class_="directory-stand")
    if stand_div:
        all_spans = stand_div.find_all("span")
        # spans[0] = SVG icon (empty text), spans[1] = " Stand" label
        # spans[2:] = the actual stand numbers/codes
        value_spans = all_spans[2:] if len(all_spans) > 2 else []
        raw_stand = " ".join(s.get_text(strip=True) for s in value_spans)
        # Clean up trailing commas and normalise whitespace
        raw_stand = re.sub(r",\s*$", "", raw_stand.strip())
        raw_stand = re.sub(r"\s*,\s*", ", ", raw_stand)
        stand = raw_stand if raw_stand else None

    # ── Contact links ─────────────────────────────────────────────────────
    def contact_href(label: str) -> Optional[str]:
        tag = card.find("a", {"aria-label": re.compile(label, re.I)})
        return tag["href"].strip() if tag else None

    website_href = contact_href("Website")
    # Some cards put the URL in the href directly; ensure it's an http URL
    website = website_href if website_href and website_href.startswith("http") else None

    raw_email = contact_href("Email")
    email = raw_email.replace("mailto:", "").strip() if raw_email else None

    raw_phone = contact_href("Phone")
    phone = raw_phone.replace("tel:", "").strip() if raw_phone else None

    return {
        "Exhibitor_ID": exhibitor_id,
        "Company":      company,
        "Stand":        stand,
        "Description":  description,
        "Brands":       brands,
        "Categories":   categories,
        "Website":      website,
        "Email":        email,
        "Phone":        phone,
        "Profile_URL":  profile_url,
        "Logo_URL":     logo_url,
    }


def parse_all_cards(html: str) -> List[Dict]:
    """Parse every exhibitor card in a full HTML blob."""
    soup  = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", {"data-testid": "row-desktop"})
    print(f"  Parsing {len(cards)} exhibitor cards …")
    return [parse_card(c) for c in cards]


# ── Strategy 1: API Discovery ─────────────────────────────────────────────────

def _probe_api_endpoint(session: requests.Session) -> Optional[str]:
    """Try to find the JSON API endpoint from the page source or JS bundles."""
    try:
        resp = session.get(LIST_URL, headers=BASE_HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        return None

    page_html = resp.text

    # Look for API base URL in inline JS/config (common pattern on rxweb sites)
    api_match = re.search(
        r'["\'](?:apiBaseUrl|exhibitorApiUrl|api_url)["\']:\s*["\']([^"\']+)["\']',
        page_html, re.I
    )
    if api_match:
        candidate = api_match.group(1)
        if "/exhibitor" in candidate.lower():
            return urljoin(BASE_URL, candidate)

    # Try well-known endpoint patterns
    for path in CANDIDATE_API_PATTERNS:
        url = BASE_URL + path
        try:
            r = session.get(
                url,
                params={"page": 1, "pageSize": 1},
                headers={**BASE_HEADERS, "Accept": "application/json"},
                timeout=10,
            )
            if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("application/json"):
                data = r.json()
                # Expect a list or a dict with a list inside
                if isinstance(data, (list, dict)):
                    print(f"  API discovered: {url}")
                    return url
        except Exception:
            continue

    return None


def _fetch_via_api(api_url: str, session: requests.Session) -> List[Dict]:
    """Page through the JSON API and return raw exhibitor dicts."""
    records: List[Dict] = []
    page = 1
    page_size = 50

    while True:
        params = {"page": page, "pageSize": page_size, "locale": "en-gb"}
        try:
            r = session.get(
                api_url,
                params=params,
                headers={**BASE_HEADERS, "Accept": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            print(f"  API error on page {page}: {exc}")
            break

        # Normalise to a list
        items = data if isinstance(data, list) else data.get("items") or data.get("exhibitors") or data.get("data") or []
        if not items:
            break

        records.extend(items)
        print(f"  Page {page}: {len(items)} items  (total so far: {len(records)})")

        if len(items) < page_size:
            break   # last page
        page += 1
        time.sleep(0.3)

    return records


def try_api_strategy() -> Optional[List[Dict]]:
    """Return parsed records via API, or None if not possible."""
    print("\n[Strategy 1] Attempting API discovery …")
    session = requests.Session()
    api_url = _probe_api_endpoint(session)

    if not api_url:
        print("  No API endpoint found.")
        return None

    raw = _fetch_via_api(api_url, session)
    if not raw:
        return None

    # API responses vary; try to normalise to our schema
    # If the API returns HTML-embedded data, fall back to parsing
    records = []
    for item in raw:
        if isinstance(item, dict) and "Company" in item:
            records.append(item)   # already normalised
        elif isinstance(item, dict):
            # Best-effort mapping from common API field names
            records.append({
                "Exhibitor_ID": item.get("id") or item.get("exhibitorId"),
                "Company":      item.get("name") or item.get("companyName"),
                "Stand":        item.get("stand") or item.get("boothNumber"),
                "Description":  item.get("description") or item.get("summary"),
                "Brands":       item.get("brands"),
                "Categories":   item.get("categories") or item.get("tags"),
                "Website":      item.get("website") or item.get("websiteUrl"),
                "Email":        item.get("email") or item.get("contactEmail"),
                "Phone":        item.get("phone") or item.get("telephone"),
                "Profile_URL":  item.get("profileUrl") or item.get("url"),
                "Logo_URL":     item.get("logoUrl") or item.get("logo"),
            })

    print(f"  API strategy: {len(records)} exhibitors extracted.")
    return records


# ── Strategy 2: Selenium + infinite scroll ────────────────────────────────────

def try_selenium_strategy(headless: bool = True) -> List[Dict]:
    """Launch headless Chrome, scroll until all cards load, parse them."""
    print("\n[Strategy 2] Launching Selenium + headless Chrome …")

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError:
        raise SystemExit(
            "selenium is not installed. Run: pip install selenium webdriver-manager"
        )

    # ── Set up ChromeDriver automatically ────────────────────────────────
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
    except Exception:
        # Fall back to system chromedriver if webdriver-manager fails
        service = Service()

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(f"user-agent={BASE_HEADERS['User-Agent']}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = webdriver.Chrome(service=service, options=opts)
    wait   = WebDriverWait(driver, 30)

    try:
        print(f"  Opening {LIST_URL} …")
        driver.get(LIST_URL)

        # Wait for the first batch of cards to appear
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='row-desktop']")))
        time.sleep(2)   # Allow JS to settle

        # ── Dismiss cookie banner if present ─────────────────────────────
        for cookie_sel in (
            "#onetrust-accept-btn-handler",
            ".cookie-accept",
            "[aria-label*='Accept']",
            "button[id*='accept']",
        ):
            try:
                btn = driver.find_element(By.CSS_SELECTOR, cookie_sel)
                btn.click()
                time.sleep(0.8)
                break
            except Exception:
                continue

        # ── Detect scrollable list container ─────────────────────────────
        # The page uses Intersection Observer (not window onscroll), so
        # window.scrollTo() stops triggering new loads after ~43 cards.
        # We must scroll the CONTAINER element or use scrollIntoView() on
        # the last card — which is exactly what the observer watches.
        scroll_container = None
        for sel in (
            ".exhibitors-list-container",
            ".directory-list",
            ".exhibitor-list",
            "[class*='list-container']",
            "[class*='exhibitor-list']",
            "[class*='directory-list']",
        ):
            try:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                scroll_container = el
                print(f"  Scroll container found: {sel}")
                break
            except Exception:
                continue

        # ── Infinite scroll loop ──────────────────────────────────────────
        prev_count  = 0
        stale_ticks = 0
        STALE_LIMIT = 8   # raised: observer may need extra ticks to fire

        for scroll_num in range(1, MAX_SCROLLS + 1):
            cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='row-desktop']")

            # PRIMARY FIX: scrollIntoView() on the very last card fires the
            # Intersection Observer directly — this is what was missing before.
            if cards:
                driver.execute_script(
                    "arguments[0].scrollIntoView({behavior:'smooth', block:'end'});",
                    cards[-1],
                )

            # SECONDARY: also scroll any detected container + window
            if scroll_container:
                driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight;",
                    scroll_container,
                )
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # Adaptive wait: poll every 0.5 s, break early if new cards arrive
            deadline = time.time() + SCROLL_PAUSE
            while time.time() < deadline:
                time.sleep(0.5)
                new_count = len(driver.find_elements(By.CSS_SELECTOR, "[data-testid='row-desktop']"))
                if new_count > len(cards):
                    break   # new content arrived — don't wait out the full pause

            cards = driver.find_elements(By.CSS_SELECTOR, "[data-testid='row-desktop']")
            count = len(cards)

            print(f"  Scroll {scroll_num:>3}: {count:>4} cards loaded", end="")

            if count >= TOTAL_EXPECT:
                print(f"  ✓ All {TOTAL_EXPECT} exhibitors loaded.")
                break

            if count == prev_count:
                stale_ticks += 1
                print(f"  (no change, stale {stale_ticks}/{STALE_LIMIT})")
                if stale_ticks >= STALE_LIMIT:
                    print(f"  Stopping – no new cards after {STALE_LIMIT} scrolls.")
                    break
            else:
                stale_ticks = 0
                print()

            prev_count = count

        # ── Grab full page source and parse ──────────────────────────────
        page_source = driver.page_source

    finally:
        driver.quit()

    return parse_all_cards(page_source)


# ── Output ────────────────────────────────────────────────────────────────────

def save_results(records: List[Dict], output_path: str) -> None:
    if not records:
        print("No records to save.")
        return

    df = pd.DataFrame(records)

    # Column ordering
    preferred_cols = [
        "Company", "Stand", "Description", "Brands", "Categories",
        "Website", "Email", "Phone", "Profile_URL", "Logo_URL", "Exhibitor_ID",
    ]
    cols = [c for c in preferred_cols if c in df.columns] + \
           [c for c in df.columns if c not in preferred_cols]
    df = df[cols]

    # Excel
    df.to_excel(output_path, index=False, engine="openpyxl")

    # CSV (utf-8-sig so Excel on Windows opens it correctly)
    base, _ = os.path.splitext(output_path)
    csv_path = base + ".csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(f"\n✓  {len(df)} exhibitors saved")
    print(f"   Excel → {output_path}")
    print(f"   CSV   → {csv_path}")
    _print_sample(df)


def _print_sample(df: pd.DataFrame) -> None:
    """Print a quick preview table to the console."""
    print("\nSample (first 3 rows):")
    preview_cols = ["Company", "Stand", "Website", "Email", "Phone"]
    preview = df[[c for c in preview_cols if c in df.columns]].head(3)
    print(preview.to_string(index=False))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    global TOTAL_EXPECT
    parser = argparse.ArgumentParser(
        description="Scrape all exhibitors from Cannes Yachting Festival"
    )
    parser.add_argument(
        "--strategy",
        choices=["auto", "api", "selenium"],
        default="auto",
        help="Scraping strategy (default: auto – tries API first, falls back to Selenium)",
    )
    parser.add_argument(
        "--output",
        default="cannes_exhibitors.xlsx",
        help="Output Excel file path (a matching .csv is also created)",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show browser window (Selenium strategy only)",
    )
    parser.add_argument(
        "--expected",
        type=int,
        default=TOTAL_EXPECT,
        help=f"Expected total exhibitors (default: {TOTAL_EXPECT})",
    )
    args = parser.parse_args()

    TOTAL_EXPECT = args.expected
    records: Optional[List[Dict]] = None

    if args.strategy in ("auto", "api"):
        records = try_api_strategy()

    if not records and args.strategy in ("auto", "selenium"):
        records = try_selenium_strategy(headless=not args.visible)

    if not records:
        raise SystemExit("No data extracted. Check network access and try --visible to debug.")

    save_results(records, args.output)


if __name__ == "__main__":
    main()