"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   IAAPA Expo Europe 2026 – MULTI-TAB PARALLEL Scraper  v3.0                ║
║                                                                              ║
║   FIX: Correctly loads ALL 804 exhibitors by clicking "Load More Results"  ║
║        4 times (200 → 400 → 600 → 800 → 804) before scraping begins        ║
║                                                                              ║
║   ⚡  Opens up to 50 tabs simultaneously in ONE Chrome window               ║
║   ⚡  Parses all tabs concurrently in background threads                    ║
║   ⚡  ~12× faster than scraping one page at a time                          ║
║                                                                              ║
║   Output: iaapa_output/  →  .csv  +  .json  +  .xlsx                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

INSTALL:
    pip install selenium webdriver-manager beautifulsoup4 pandas openpyxl

RUN:
    python iaapa_scraper_v3.py
"""

# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS
# ══════════════════════════════════════════════════════════════════════════════
import re
import csv
import json
import time
import logging
import random
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchWindowException,
    StaleElementReferenceException,
)
from webdriver_manager.chrome import ChromeDriverManager


# ══════════════════════════════════════════════════════════════════════════════
#  ⚙  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
BASE_URL        = "https://iaapaexpoeurope26.mapyourshow.com"
LIST_URL        = f"{BASE_URL}/8_0/explore/exhibitor-alphalist.cfm"
DETAIL_BASE     = f"{BASE_URL}/8_0/exhibitor/exhibitor-details.cfm?exhid="

MAX_TABS        = 50      # parallel tabs per batch  (10–50 recommended)
HEADLESS        = False   # True = no visible Chrome window
PAGE_TIMEOUT    = 25      # seconds to wait for page load
TAB_OPEN_DELAY  = 0.25   # seconds gap between opening each new tab
RETRY_LIMIT     = 3       # retries per failed tab
CHECKPOINT_EVERY= 50      # save checkpoint every N records

# How many exhibitors "Load More" adds per click (confirmed = 200)
LOAD_MORE_STEP  = 200
# Total exhibitors on the site (confirmed = 804)
EXPECTED_TOTAL  = 804
# Wait after each "Load More" click for React to render
LOAD_MORE_WAIT  = 3.0     # seconds

OUTPUT_DIR = Path("iaapa_output")
OUTPUT_DIR.mkdir(exist_ok=True)

TS         = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_FILE   = OUTPUT_DIR / f"iaapa_{TS}.csv"
JSON_FILE  = OUTPUT_DIR / f"iaapa_{TS}.json"
EXCEL_FILE = OUTPUT_DIR / f"iaapa_{TS}.xlsx"
CHECKPOINT = OUTPUT_DIR / "checkpoint.json"
LOG_FILE   = OUTPUT_DIR / "scraper.log"

CSV_FIELDS = [
    "exhid", "name",
    "address_line1", "address_line2", "city_state_zip",
    "country", "full_address",
    "website", "phone",
    "booth", "booth_code",
    "about", "product_categories",
    "facebook", "linkedin", "instagram", "twitter", "youtube",
    "profile_url", "scraped_at",
]


# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)
_lock = threading.Lock()   # thread-safe console output


def tlog(msg, level="info"):
    with _lock:
        getattr(log, level)(msg)


# ══════════════════════════════════════════════════════════════════════════════
#  CHROME SETUP
# ══════════════════════════════════════════════════════════════════════════════
def create_driver(headless: bool = HEADLESS) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")

    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1600,960")
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-infobars")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--log-level=3")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-popup-blocking")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    svc    = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=svc, options=opts)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
    )
    driver.set_page_load_timeout(40)
    return driver


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — LOAD ALL 804 EXHIBITORS FROM THE LIST PAGE
# ══════════════════════════════════════════════════════════════════════════════
def get_all_exhibitor_ids(driver: webdriver.Chrome) -> list[dict]:
    """
    Opens the exhibitor alpha-list page, clicks 'Load More Results' until
    ALL 804 exhibitors are visible, then extracts every exhid + name.

    Confirmed behaviour (live-tested):
      - Page starts with 200 visible
      - Each click of <a class="btn-secondary">Load More Results</a> adds 200
      - 4 clicks needed:  200 → 400 → 600 → 800 → 804
      - Button disappears when all 804 are loaded
    """
    log.info("━" * 65)
    log.info("  STEP 1 — Loading FULL exhibitor list (all 804)")
    log.info("━" * 65)

    driver.get(LIST_URL)

    # Wait for at least the first batch of exhibitor links
    try:
        WebDriverWait(driver, PAGE_TIMEOUT).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "a[href*='exhibitor-details.cfm']")
            )
        )
    except TimeoutException:
        log.error("❌  Timed out waiting for exhibitor list to appear.")
        return []

    time.sleep(2)  # let React settle

    # ── Click "Load More Results" until the button disappears ─────────────────
    click_count = 0
    while True:
        # Count current exhibitors
        current = driver.execute_script(
            "return document.querySelectorAll(\"a[href*='exhibitor-details.cfm']\").length;"
        )
        log.info(f"  Currently loaded: {current} / {EXPECTED_TOTAL}")

        if current >= EXPECTED_TOTAL:
            log.info("  ✅  All exhibitors loaded — no more clicking needed.")
            break

        # Check if "Load More Results" button still exists
        # Button is: <a class="btn-secondary">Load More Results</a>
        btn_exists = driver.execute_script(
            "return Array.from(document.querySelectorAll('a.btn-secondary'))"
            ".filter(a => a.textContent.trim() === 'Load More Results').length > 0;"
        )

        if not btn_exists:
            log.info("  ✅  'Load More Results' button gone — all results loaded.")
            break

        # Click via JavaScript (most reliable for this React-rendered button)
        try:
            driver.execute_script(
                "var btn = Array.from(document.querySelectorAll('a.btn-secondary'))"
                ".find(a => a.textContent.trim() === 'Load More Results');"
                "if(btn) { btn.scrollIntoView({block:'center'}); btn.click(); }"
            )
            click_count += 1
            log.info(f"  🖱   'Load More' click #{click_count} — waiting {LOAD_MORE_WAIT}s …")
            time.sleep(LOAD_MORE_WAIT)

        except Exception as e:
            log.warning(f"  ⚠   Click error: {e} — retrying in 2s …")
            time.sleep(2)

        # Safety: if we've clicked more than expected times, break
        if click_count > (EXPECTED_TOTAL // LOAD_MORE_STEP) + 2:
            log.warning("  ⚠   Safety limit reached — stopping Load More clicks.")
            break

    # ── Final count verification ───────────────────────────────────────────────
    final_count = driver.execute_script(
        "return document.querySelectorAll(\"a[href*='exhibitor-details.cfm']\").length;"
    )
    log.info(f"  Final page count: {final_count} exhibitor links visible")

    # ── Extract all exhid + name from the fully-loaded page ───────────────────
    log.info("  Extracting exhibitor IDs …")
    soup    = BeautifulSoup(driver.page_source, "html.parser")
    pattern = re.compile(r"exhibitor-details\.cfm\?exhid=(.+?)(?:&|$)", re.I)

    seen       = {}   # exhid → name  (dedup)
    exhibitors = []

    for a_tag in soup.find_all("a", href=True):
        m = pattern.search(a_tag["href"])
        if m:
            exhid = m.group(1).strip()
            name  = a_tag.get_text(strip=True)
            if exhid and exhid not in seen:
                seen[exhid] = name
                exhibitors.append({"exhid": exhid, "name": name})

    log.info(f"  ✅  Extracted {len(exhibitors)} unique exhibitor IDs")

    if len(exhibitors) < EXPECTED_TOTAL:
        log.warning(
            f"  ⚠   Expected {EXPECTED_TOTAL}, got {len(exhibitors)}. "
            f"Some may have loaded late — proceeding with what we have."
        )

    return exhibitors


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — MULTI-TAB PARALLEL SCRAPER
# ══════════════════════════════════════════════════════════════════════════════
class MultiTabScraper:
    """
    Divides all exhibitors into batches of MAX_TABS.

    For each batch:
      1. Open MAX_TABS browser tabs simultaneously (each loading one profile)
      2. Wait for every tab to finish loading
      3. Grab page source from each tab
      4. Close all extra tabs (back to 1)
      5. Parse all HTML blobs concurrently in a ThreadPoolExecutor
      6. Collect results and checkpoint

    Visual flow:
    ┌─────────────────────────────────────────────────────┐
    │  Batch 1: tabs 1-50 open simultaneously             │
    │  All 50 pages load in parallel                      │
    │  Grab HTML → close tabs → parse in threads          │
    ├─────────────────────────────────────────────────────┤
    │  Batch 2: next 50 tabs open simultaneously          │
    │  ...repeat until all 804 done                       │
    └─────────────────────────────────────────────────────┘
    """

    def __init__(self, driver: webdriver.Chrome, max_tabs: int = MAX_TABS):
        self.driver    = driver
        self.max_tabs  = max_tabs
        self.results   = []
        self._done_cnt = 0

    # ──────────────────────────────────────────────────────────────────────────
    def run(self, exhibitors: list[dict]) -> list[dict]:
        total   = len(exhibitors)
        batches = _chunk(exhibitors, self.max_tabs)
        n_batch = len(batches)

        log.info("━" * 65)
        log.info(f"  STEP 2 — Multi-tab scraping")
        log.info(f"  Total exhibitors : {total}")
        log.info(f"  Tabs per batch   : {self.max_tabs}")
        log.info(f"  Number of batches: {n_batch}")
        log.info(f"  Est. time        : ~{n_batch * 30 // 60} min")
        log.info("━" * 65)

        with ThreadPoolExecutor(max_workers=self.max_tabs) as pool:
            for idx, batch in enumerate(batches, 1):
                tlog(f"\n  ┌─ Batch {idx}/{n_batch}  ({len(batch)} tabs) ─────────────────")

                # 1. Open all tabs in this batch simultaneously
                tab_data = self._open_all_tabs(batch)

                # 2. Wait for every tab to finish loading + grab HTML
                self._collect_all_html(tab_data)

                # 3. Close all extra tabs (return to 1 open tab)
                self._close_extra_tabs()

                # 4. Parse all HTML blobs in parallel threads
                futures = {
                    pool.submit(
                        parse_exhibitor_html,
                        td.get("html", ""),
                        td["exhid"],
                        td["name"],
                        f"{DETAIL_BASE}{td['exhid']}",
                    ): td["exhid"]
                    for td in tab_data
                }

                # 5. Collect parsed results
                for future in as_completed(futures):
                    exhid = futures[future]
                    try:
                        record = future.result()
                        self.results.append(record)
                        self._done_cnt += 1
                        tlog(
                            f"  ✅ [{self._done_cnt:>3}/{total}]  "
                            f"{record['name'][:42]:<42}  "
                            f"{record['country'][:18]:<18}  "
                            f"booth: {record['booth_code']}"
                        )
                    except Exception as e:
                        tlog(f"  ✗  Parse error exhid={exhid}: {e}", "error")

                tlog(f"  └─ Batch {idx}/{n_batch} complete ({self._done_cnt} total)")

                # 6. Checkpoint
                if self._done_cnt % CHECKPOINT_EVERY < len(batch):
                    save_checkpoint(self.results)
                    tlog(f"  💾  Checkpoint saved ({len(self.results)} records)")

                # Polite delay between batches
                if idx < n_batch:
                    time.sleep(random.uniform(1.5, 2.5))

        return self.results

    # ──────────────────────────────────────────────────────────────────────────
    def _open_all_tabs(self, batch: list[dict]) -> list[dict]:
        """
        Opens one tab per exhibitor in the batch.
        Tab 0  → reuses the existing active tab (navigate in place)
        Tab 1+ → opened via window.open() JavaScript call
        Returns list of {exhid, name, handle, html:""}
        """
        tab_data = []

        for i, exh in enumerate(batch):
            url = f"{DETAIL_BASE}{exh['exhid']}"

            if i == 0:
                # Reuse existing tab
                self.driver.get(url)
                handle = self.driver.current_window_handle
            else:
                # Open new tab (don't wait — open all fast)
                self.driver.execute_script(f"window.open('{url}','_blank');")
                time.sleep(TAB_OPEN_DELAY)
                handle = self.driver.window_handles[-1]

            tab_data.append({
                "exhid":  exh["exhid"],
                "name":   exh["name"],
                "handle": handle,
                "html":   "",
            })

        tlog(f"  🌐  Opened {len(tab_data)} tabs — waiting for pages to load …")
        return tab_data

    # ──────────────────────────────────────────────────────────────────────────
    def _collect_all_html(self, tab_data: list[dict]) -> None:
        """
        Cycles through every tab, waits for <main> to appear,
        then grabs page_source. Retries up to RETRY_LIMIT on timeout.
        """
        for td in tab_data:
            handle = td["handle"]

            # Skip if handle is no longer valid
            if handle not in self.driver.window_handles:
                tlog(f"  ⚠  Handle gone for exhid={td['exhid']}", "warning")
                continue

            for attempt in range(1, RETRY_LIMIT + 1):
                try:
                    self.driver.switch_to.window(handle)
                    WebDriverWait(self.driver, PAGE_TIMEOUT).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "main"))
                    )
                    td["html"] = self.driver.page_source
                    break

                except TimeoutException:
                    if attempt < RETRY_LIMIT:
                        tlog(
                            f"  ⚠  Timeout exhid={td['exhid']} "
                            f"(attempt {attempt}/{RETRY_LIMIT}) — refreshing …",
                            "warning",
                        )
                        try:
                            self.driver.refresh()
                            time.sleep(2)
                        except Exception:
                            pass
                    else:
                        tlog(
                            f"  ✗  Failed after {RETRY_LIMIT} tries: exhid={td['exhid']}",
                            "error",
                        )
                        td["html"] = ""

                except NoSuchWindowException:
                    tlog(f"  ✗  Window closed: exhid={td['exhid']}", "error")
                    td["html"] = ""
                    break

                except WebDriverException as e:
                    tlog(f"  ✗  WebDriver error exhid={td['exhid']}: {e}", "error")
                    td["html"] = ""
                    break

    # ──────────────────────────────────────────────────────────────────────────
    def _close_extra_tabs(self) -> None:
        """Closes all tabs except the very first one."""
        handles = self.driver.window_handles
        if len(handles) <= 1:
            return
        keep = handles[0]
        for h in handles[1:]:
            try:
                self.driver.switch_to.window(h)
                self.driver.close()
            except Exception:
                pass
        self.driver.switch_to.window(keep)


# ══════════════════════════════════════════════════════════════════════════════
#  HTML PARSERS  (pure Python / BeautifulSoup — no Selenium, fully thread-safe)
# ══════════════════════════════════════════════════════════════════════════════
def parse_exhibitor_html(
    html: str, exhid: str, fallback_name: str, url: str
) -> dict:
    """Top-level parser. Calls all sub-parsers and returns a flat record."""
    rec = {f: "" for f in CSV_FIELDS}
    rec["exhid"]       = exhid
    rec["profile_url"] = url

    if not html:
        rec["name"] = fallback_name
        return rec

    soup = BeautifulSoup(html, "html.parser")
    _parse_name(soup, rec, fallback_name)
    _parse_company_info(soup, rec)
    _parse_social_links(soup, rec)
    _parse_booths(soup, rec)
    _parse_about(soup, rec)
    _parse_categories(soup, rec)
    rec["scraped_at"] = datetime.now().isoformat(timespec="seconds")
    return rec


# ─────────────────────────────────────────────────────────────────────────────
def _parse_name(soup, rec, fallback=""):
    """<main><h1>Company Name</h1>"""
    h1 = soup.select_one("main h1")
    rec["name"] = h1.get_text(strip=True) if h1 else fallback


def _parse_company_info(soup, rec):
    """
    Finds the 'Company Information' article and extracts:
      - Address lines (as role=generic / plain div leaf nodes)
      - Website  (<a aria-label="Visit ... on the web">)
      - Phone    (<a href="tel:...">)
    """
    article = None
    for h2 in soup.find_all("h2"):
        if "company information" in h2.get_text(strip=True).lower():
            article = h2.find_parent("article")
            break
    if not article:
        return

    # ── Address ───────────────────────────────────────────────────────────────
    # Address lines are leaf-level elements (no child tags), short (<100 chars)
    addr = []
    for el in article.find_all(True):
        if el.name in ("h1","h2","h3","h4","h5","a","button","ul","li","nav"):
            continue
        if any(getattr(c, "name", None) for c in el.children):
            continue   # not a leaf
        text = el.get_text(strip=True)
        if not text or len(text) > 100:
            continue
        if "company information" in text.lower():
            continue
        if text not in addr:
            addr.append(text)
        if len(addr) >= 5:
            break

    if addr:
        rec["address_line1"]  = addr[0] if len(addr) > 0 else ""
        rec["address_line2"]  = addr[1] if len(addr) > 1 else ""
        rec["city_state_zip"] = addr[2] if len(addr) > 2 else ""
        rec["country"]        = addr[-1]
        rec["full_address"]   = ", ".join(addr)

    # ── Website ───────────────────────────────────────────────────────────────
    web = article.find("a", attrs={"aria-label": re.compile(r"visit.+web", re.I)})
    if not web:
        for a in article.find_all("a", href=True):
            h = a["href"]
            if h.startswith("http") and "mapyourshow" not in h.lower():
                web = a
                break
    if web:
        rec["website"] = web.get("href", "").strip()

    # ── Phone ─────────────────────────────────────────────────────────────────
    tel = article.find("a", href=re.compile(r"^tel:", re.I))
    if tel:
        rec["phone"] = tel.get_text(strip=True)


def _parse_social_links(soup, rec):
    """
    Detects social links by aria-label AND href domain.
    Confirmed structure:
      <a aria-label="Like ... on Facebook"    href="https://www.facebook.com/...">
      <a aria-label="Connect ... on LinkedIn" href="https://www.linkedin.com/...">
      <a aria-label="Follow ... on Instagram" href="https://www.instagram.com/...">
    """
    for a in soup.find_all("a", href=True):
        href  = a.get("href", "").strip()
        label = (a.get("aria-label") or a.get("title") or "").lower()
        hl    = href.lower()
        if not href or href.startswith(("#", "javascript", "/8_0")):
            continue
        if ("facebook.com"  in hl or "facebook"  in label) and not rec["facebook"]:
            rec["facebook"]  = href
        elif ("linkedin.com" in hl or "linkedin"  in label) and not rec["linkedin"]:
            rec["linkedin"]  = href
        elif ("instagram.com"in hl or "instagram" in label) and not rec["instagram"]:
            rec["instagram"] = href
        elif ("twitter.com"  in hl or "x.com" in hl or "twitter" in label) and not rec["twitter"]:
            rec["twitter"]   = href
        elif ("youtube.com"  in hl or "youtu.be" in hl or "youtube" in label) and not rec["youtube"]:
            rec["youtube"]   = href


def _parse_booths(soup, rec):
    """
    <aside role="complementary">
      <h2>Booths</h2>
      <ul><li><ul><li>
        <a href="/8_0/floorplan_link.cfm?...">
          North Exhibit Halls N19-N23 — N4919
        </a>
    """
    aside = soup.find("aside") or soup.find(attrs={"role": "complementary"})
    if not aside:
        for h2 in soup.find_all("h2"):
            if "booth" in h2.get_text(strip=True).lower():
                aside = h2.find_parent()
                break
    if not aside:
        return

    booths, codes = [], []
    for a in aside.find_all("a", href=True):
        text = a.get_text(strip=True)
        if not text:
            continue
        booths.append(text)
        m = re.search(r"[—–-]\s*([A-Z]\d+)\s*$", text)
        codes.append(m.group(1) if m else text)

    rec["booth"]      = " | ".join(booths)
    rec["booth_code"] = " | ".join(codes)


def _parse_about(soup, rec):
    """
    <article>
      <h2>About {Name}</h2>
      <div role="generic">Description text…</div>
    </article>
    """
    about_h2 = None
    for h2 in soup.find_all("h2"):
        if re.match(r"about\b", h2.get_text(strip=True), re.I):
            about_h2 = h2
            break
    if not about_h2:
        return

    article = about_h2.find_parent("article") or about_h2.find_parent("section")
    if not article:
        return

    parts = []
    for el in article.find_all(True):
        if el.name in ("h1","h2","h3"):
            continue
        if any(getattr(c, "name", None) for c in el.children):
            continue
        text = el.get_text(strip=True)
        if text and text not in parts:
            parts.append(text)

    about = " ".join(parts).strip()
    about = re.sub(r"^About\s+\S.+?\s{2,}", "", about).strip()
    rec["about"] = about[:3000]


def _parse_categories(soup, rec):
    """
    <article>
      <h2>Product Categories</h2>
      <ul><li><a>Category > Subcategory</a></li>…</ul>
    </article>
    """
    cat_h2 = None
    for h2 in soup.find_all("h2"):
        if "product categor" in h2.get_text(strip=True).lower():
            cat_h2 = h2
            break
    if not cat_h2:
        return

    article = cat_h2.find_parent("article") or cat_h2.find_parent("section")
    if not article:
        return

    cats = [a.get_text(strip=True) for a in article.find_all("a") if a.get_text(strip=True)]
    rec["product_categories"] = " | ".join(cats)


# ══════════════════════════════════════════════════════════════════════════════
#  CHECKPOINT & OUTPUT
# ══════════════════════════════════════════════════════════════════════════════
def save_checkpoint(records):
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def load_checkpoint():
    if CHECKPOINT.exists():
        with open(CHECKPOINT, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_final(records):
    data = sorted(records, key=lambda r: r.get("name", "").lower())

    # CSV
    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(data)
    log.info(f"  💾  CSV   → {CSV_FILE}")

    # JSON
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info(f"  💾  JSON  → {JSON_FILE}")

    # Excel with auto column width
    df = pd.DataFrame(data, columns=CSV_FIELDS)
    with pd.ExcelWriter(EXCEL_FILE, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Exhibitors")
        ws = writer.sheets["Exhibitors"]
        for col in ws.columns:
            max_w = max((len(str(c.value or "")) for c in col), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max_w + 4, 60)
    log.info(f"  💾  Excel → {EXCEL_FILE}")


def _chunk(lst, size):
    return [lst[i: i + size] for i in range(0, len(lst), size)]


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    t_start = time.time()

    log.info("╔" + "═" * 63 + "╗")
    log.info("║  IAAPA Expo Europe 2026 — Multi-Tab Parallel Scraper v3.0  ║")
    log.info(f"║  Tabs/batch : {MAX_TABS:<4}   Headless: {str(HEADLESS):<5}                      ║")
    log.info("╚" + "═" * 63 + "╝\n")

    driver = create_driver(headless=HEADLESS)

    try:
        # ── Resume support ────────────────────────────────────────────────────
        saved      = load_checkpoint()
        done_ids   = {r["exhid"] for r in saved}
        all_records = list(saved)
        if done_ids:
            log.info(f"  ♻   Resuming — {len(done_ids)} already scraped\n")

        # ── STEP 1: Load ALL 804 exhibitor IDs ────────────────────────────────
        all_exhibitors = get_all_exhibitor_ids(driver)

        if not all_exhibitors:
            log.error("❌  No exhibitors found. Aborting.")
            return

        # Filter already-done ones
        todo = [e for e in all_exhibitors if e["exhid"] not in done_ids]

        log.info(f"\n  Total found  : {len(all_exhibitors)}")
        log.info(f"  Already done : {len(done_ids)}")
        log.info(f"  To scrape    : {len(todo)}")
        log.info(f"  Batches      : {len(_chunk(todo, MAX_TABS))} × {MAX_TABS} tabs\n")

        if not todo:
            log.info("  ✅  Everything already scraped.")
            save_final(all_records)
            return

        # ── STEP 2: Multi-tab parallel scraping ───────────────────────────────
        scraper     = MultiTabScraper(driver, max_tabs=MAX_TABS)
        new_records = scraper.run(todo)
        all_records.extend(new_records)

        # ── Save final outputs ────────────────────────────────────────────────
        log.info("\n" + "━" * 65)
        log.info("  Saving output files …")
        save_final(all_records)

        if CHECKPOINT.exists():
            CHECKPOINT.unlink()

        # ── Summary ───────────────────────────────────────────────────────────
        elapsed = time.time() - t_start
        log.info("╔" + "═" * 63 + "╗")
        log.info(f"║  🎉  DONE!                                                ║")
        log.info(f"║  Scraped   : {len(all_records):<4} exhibitors                             ║")
        log.info(f"║  Time      : {elapsed/60:.1f} min                                      ║")
        log.info(f"║  Speed     : {len(all_records)/(elapsed/60):.0f} exhibitors/min                         ║")
        log.info("╚" + "═" * 63 + "╝")

        # Quick stats
        log.info("\n  📊  Data coverage:")
        for field in ["website","linkedin","facebook","instagram","twitter","youtube","phone"]:
            n = sum(1 for r in all_records if r.get(field))
            log.info(f"     {field:<12}: {n:>3} / {len(all_records)}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass
        log.info("\n  🔒  Chrome closed.")


if __name__ == "__main__":
    main()