"""
extract_exhibitors.py
======================
Scrapes exhibitor information from the International Security Expo website.
Retrieves all exhibitor page URLs from the site's sitemap and parses each
page for:

  * Company     – exhibitor name from the page heading
  * Stand       – booth number (e.g. "C70")
  * Description – descriptive paragraph(s)
  * Address     – mailing address as a single string
  * Website     – official link from the exhibitor page
  * LinkedIn    – LinkedIn profile link (if present)

Results are written to both an Excel (.xlsx) and a CSV file.

Usage
-----
    python extract_exhibitors.py --output exhibitors.xlsx

Note
----
Direct HTTP requests to the Expo site may be blocked in some environments.
Run from a network that permits access to www.internationalsecurityexpo.com.
"""

import argparse
import re
import time
from typing import Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

# ── Constants ────────────────────────────────────────────────────────────────

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
}

REQUEST_TIMEOUT = 30   # seconds
RETRY_ATTEMPTS  = 3
RETRY_BACKOFF   = 2.0  # seconds between retries
POLITE_DELAY    = 0.6  # seconds between page requests


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_with_retry(
    session: requests.Session,
    url: str,
    attempts: int = RETRY_ATTEMPTS,
) -> Optional[requests.Response]:
    """GET a URL with automatic retries on transient failures."""
    for attempt in range(1, attempts + 1):
        try:
            resp = session.get(url, headers=BASE_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            print(f"  [attempt {attempt}/{attempts}] Error fetching {url}: {exc}")
            if attempt < attempts:
                time.sleep(RETRY_BACKOFF * attempt)
    return None


def _text(tag: Optional[Tag], sep: str = " ") -> Optional[str]:
    """Return stripped text from a tag, or None if the tag is missing."""
    if tag is None:
        return None
    value = tag.get_text(separator=sep, strip=True)
    return value if value else None


# ── Sitemap ──────────────────────────────────────────────────────────────────

def fetch_sitemap_urls(sitemap_url: str) -> List[str]:
    """Return all exhibitor page URLs found in the XML sitemap.

    FIX: added timeout; uses 'lxml-xml' parser (correct name for lxml's
    XML mode) with a fallback to 'html.parser' so the function never crashes
    even if lxml isn't installed.
    """
    try:
        resp = requests.get(sitemap_url, headers=BASE_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise SystemExit(f"Could not fetch sitemap: {exc}") from exc

    # FIX: 'xml' is not a valid BeautifulSoup parser name; use 'lxml-xml'
    # for XML documents. Fall back to plain html.parser if lxml isn't present.
    for parser in ("lxml-xml", "xml", "html.parser"):
        try:
            soup = BeautifulSoup(resp.content, parser)
            break
        except Exception:
            continue
    else:
        raise SystemExit("No suitable XML parser found. Run: pip install lxml")

    urls = [loc.get_text(strip=True) for loc in soup.find_all("loc")]

    # Keep only individual exhibitor pages, drop the listing root
    return [u for u in urls if "/exhibitors/" in u and u.rstrip("/").count("/exhibitors/") >= 1]


# ── Social links ─────────────────────────────────────────────────────────────

def get_social_links(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract social-media links from an exhibitor page.

    FIX: the original selector was too specific and relied on an exact class
    substring that may not match. This version scans *all* anchor tags on the
    page for known social-media domains, so it works regardless of markup
    changes.
    """
    social_links: Dict[str, str] = {}

    domain_map = {
        "linkedin.com":  "LinkedIn",
        "twitter.com":   "Twitter",
        "x.com":         "Twitter",
        "facebook.com":  "Facebook",
        "instagram.com": "Instagram",
        "youtube.com":   "YouTube",
    }

    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        for domain, platform in domain_map.items():
            if domain in href and platform not in social_links:
                social_links[platform] = href

    return social_links


# ── Page parser ───────────────────────────────────────────────────────────────

def parse_exhibitor_page(
    url: str, session: requests.Session
) -> Optional[Dict[str, str]]:
    """Parse one exhibitor page and return a data dict.

    Fixes applied
    -------------
    * Added timeout and retry via _get_with_retry().
    * Class matching uses broader fallback strategies for every field so the
      scraper is resilient to minor markup changes.
    * FIX: address_tag.find_all(text=True) is deprecated since BS4 4.x;
      replaced with the .strings generator (NavigableString iteration).
    * FIX: Stand regex used re.search without DOTALL; the stand value is now
      taken from the stripped full text, handling multi-line markup.
    * Website extraction now tries multiple strategies: aria-label, link text,
      and any href that looks like an external site URL.
    * All fields degrade gracefully to None instead of raising.
    """
    resp = _get_with_retry(session, url)
    if resp is None:
        print(f"  Skipping {url} after repeated failures.")
        return None

    soup = BeautifulSoup(resp.content, "html.parser")

    # ── Company name ──────────────────────────────────────────────────────
    company = None
    for selector in (
        {"name": "h2", "class_": re.compile(r"header__title", re.I)},
        {"name": "h1", "class_": re.compile(r"header__title", re.I)},
        {"name": "h1"},   # last-resort: first h1 on the page
    ):
        tag = soup.find(**selector)
        if tag:
            company = tag.get_text(strip=True)
            break

    # ── Stand number ─────────────────────────────────────────────────────
    stand = None
    # Strategy 1: dedicated stand div
    stand_tag = soup.find(
        True,
        class_=re.compile(r"(stand|booth)", re.I),
    )
    if stand_tag:
        raw = stand_tag.get_text(separator=" ", strip=True)
        # FIX: use re.DOTALL so multi-line text is matched correctly
        match = re.search(r"Stand[:\s]+([\w\s\-/]+)", raw, re.I | re.DOTALL)
        if match:
            stand = match.group(1).strip()

    # Strategy 2: search all page text for "Stand: XYZ"
    if not stand:
        page_text = soup.get_text(separator=" ")
        match = re.search(r"\bStand[:\s]+([\w\-/]+)", page_text, re.I)
        if match:
            stand = match.group(1).strip()

    # ── Description ───────────────────────────────────────────────────────
    description = None
    for selector in (
        {"name": "section", "class_": re.compile(r"body__description", re.I)},
        {"name": "div",     "class_": re.compile(r"description",        re.I)},
        {"name": "div",     "class_": re.compile(r"exhibitor.?content",  re.I)},
        {"name": "article"},
        {"name": "main"},
    ):
        section = soup.find(**selector)
        if section:
            paras = [p.get_text(strip=True) for p in section.find_all("p")]
            text  = " ".join(p for p in paras if p)
            if text:
                description = text
                break

    # ── Address ───────────────────────────────────────────────────────────
    address = None
    address_tag = soup.find("address")
    if address_tag:
        # FIX: find_all(text=True) is deprecated in BS4 4.x.
        # Use the .strings generator to iterate NavigableStrings directly.
        lines = [s.strip() for s in address_tag.strings if s.strip()]
        if lines:
            address = ", ".join(lines)

    # Fallback: div/span tagged with "address" in class
    if not address:
        addr_div = soup.find(True, class_=re.compile(r"\baddress\b", re.I))
        if addr_div:
            lines = [s.strip() for s in addr_div.strings if s.strip()]
            address = ", ".join(lines) if lines else None

    # ── Website ───────────────────────────────────────────────────────────
    website = None

    # Strategy 1: aria-label contains "website"
    website_tag = soup.find(
        "a", attrs={"aria-label": re.compile(r"visit.?website|website", re.I)}
    )
    if website_tag:
        website = website_tag.get("href", "").strip() or None

    # Strategy 2: link text contains "website" or "visit"
    if not website:
        for a in soup.find_all("a", href=True):
            link_text = a.get_text(strip=True).lower()
            if "visit website" in link_text or link_text == "website":
                website = a["href"].strip()
                break

    # Strategy 3: look for an external URL in the contacts section
    if not website:
        contacts = soup.find(True, class_=re.compile(r"contact", re.I))
        if contacts:
            for a in contacts.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith("http") and "internationalsecurityexpo" not in href:
                    # Exclude social-media domains so we don't capture LinkedIn, etc.
                    if not any(
                        s in href
                        for s in ("linkedin", "twitter", "facebook", "instagram", "youtube")
                    ):
                        website = href
                        break

    # ── Social links ─────────────────────────────────────────────────────
    socials  = get_social_links(soup)
    linkedin = socials.get("LinkedIn")

    return {
        "URL":         url,
        "Company":     company,
        "Stand":       stand,
        "Description": description,
        "Address":     address,
        "Website":     website,
        "LinkedIn":    linkedin,
    }


# ── Main scraper ──────────────────────────────────────────────────────────────

def scrape_exhibitors(output: str) -> None:
    """Fetch every exhibitor page and write results to Excel + CSV."""
    sitemap_url = (
        "https://www.internationalsecurityexpo.com/__media/sitemap_exhibitors.xml"
    )

    print("Fetching exhibitor URLs from sitemap …")
    urls = fetch_sitemap_urls(sitemap_url)
    print(f"Found {len(urls)} exhibitor pages.\n")

    session = requests.Session()
    records: List[Dict] = []

    for i, url in enumerate(urls, start=1):
        print(f"[{i:>4}/{len(urls)}] {url}")
        data = parse_exhibitor_page(url, session)
        if data:
            records.append(data)
        time.sleep(POLITE_DELAY)

    if not records:
        print("No records extracted. Check network access and page selectors.")
        return

    df = pd.DataFrame(records)

    # ── Excel ──────────────────────────────────────────────────────────────
    df.to_excel(output, index=False, engine="openpyxl")

    # ── CSV ────────────────────────────────────────────────────────────────
    # FIX: use os.path.splitext so the CSV path is always correct even when
    # the caller passes a filename without a dot.
    import os
    base, _ = os.path.splitext(output)
    csv_path = base + ".csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")  # utf-8-sig for Excel-safe CSV

    print(f"\n✓ Saved {len(df)} records → {output}  |  {csv_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape exhibitor data from International Security Expo."
    )
    parser.add_argument(
        "--output",
        default="exhibitors.xlsx",
        help="Path to the output Excel file (default: exhibitors.xlsx)",
    )
    args = parser.parse_args()
    scrape_exhibitors(args.output)


if __name__ == "__main__":
    main()