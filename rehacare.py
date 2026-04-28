#!/usr/bin/env python3
"""
REHACARE 2025 Exhibitor Scraper
================================
Scrapes all 769 exhibitors from rehacare.com, including company details
(address, email, phone, website, hall/stand), and exports to Excel.

Requirements:
    pip install playwright openpyxl pandas tqdm
    playwright install chromium
"""

import asyncio
import re
import time
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional
import pandas as pd
from playwright.async_api import async_playwright, Page, BrowserContext
from tqdm.asyncio import tqdm as atqdm

# ─── Configuration ────────────────────────────────────────────────────────────
BASE_URL       = "https://www.rehacare.com"
SEARCH_URL     = f"{BASE_URL}/vis/v1/en/search?view_type=rows&f_type=profile"
DIRECTORY_BASE = f"{BASE_URL}/vis/v1/en/directory"
OUTPUT_FILE    = "rehacare_2025_exhibitors.xlsx"

# All directory letters including 0-9
LETTERS = list("abcdefghijklmnopqrstuvwxyz") + ["0-9"]

# Concurrent tabs for detail scraping
MAX_CONCURRENT_TABS = 6

# Polite delay range (seconds)
MIN_DELAY = 0.5
MAX_DELAY = 1.2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


# ─── Data Model ───────────────────────────────────────────────────────────────
@dataclass
class Exhibitor:
    name:         str            = ""
    hall_stand:   str            = ""
    city:         str            = ""
    country:      str            = ""
    street:       str            = ""
    zip_code:     str            = ""
    email:        str            = ""
    phone:        str            = ""
    website:      str            = ""
    description:  str            = ""
    categories:   str            = ""   # pipe-separated
    profile_url:  str            = ""
    letter:       str            = ""


# ─── Step 1 – Collect all exhibitor profile URLs from the A-Z directory ───────
async def collect_exhibitors_from_directory(context: BrowserContext) -> list[dict]:
    """
    Visit /vis/v1/en/directory/{letter} for every letter and collect:
      - name, city/country, hall/stand, profile_url
    Returns a list of dicts (one per exhibitor, de-duped by profile_url).
    """
    seen_urls: set[str] = set()
    all_exhibitors: list[dict] = []

    for letter in LETTERS:
        url = f"{DIRECTORY_BASE}/{letter}"
        page = await context.new_page()
        try:
            log.info(f"  Collecting letter '{letter}' …")
            await page.goto(url, wait_until="networkidle", timeout=30_000)
            await page.wait_for_selector(".directory-result-row", timeout=20_000)

            rows = await page.query_selector_all(".directory-result-row")
            log.info(f"    → {len(rows)} exhibitors found")

            for row in rows:
                # Name
                name_el = await row.query_selector(".teaser-row__title")
                name    = (await name_el.inner_text()).strip() if name_el else ""

                # City / Country
                loc_el  = await row.query_selector(".teaser-row__text")
                loc     = (await loc_el.inner_text()).strip() if loc_el else ""

                # Hall / Stand
                hall_el = await row.query_selector(".teaser-row__location")
                hall    = (await hall_el.inner_text()).strip() if hall_el else ""

                # Profile URL – click Details → grab "Go to Exhibitor Profile" href
                details_btn = await row.query_selector("button.cta-button")
                profile_url = ""
                if details_btn:
                    await details_btn.click()
                    try:
                        await page.wait_for_selector(
                            ".modal-window-manager .profile-head__name",
                            timeout=8_000
                        )
                        link_el = await page.query_selector(
                            ".modal-window-manager a[href*='exhprofiles']"
                        )
                        if link_el:
                            profile_url = await link_el.get_attribute("href") or ""
                            if profile_url and not profile_url.startswith("http"):
                                profile_url = BASE_URL + profile_url

                        # Close modal
                        close_btn = await page.query_selector(
                            ".modal-window-manager .icon-button[title*='lose'], "
                            ".modal-window-manager button.icon-button"
                        )
                        if close_btn:
                            await close_btn.click()
                        else:
                            await page.keyboard.press("Escape")
                        await page.wait_for_timeout(300)
                    except Exception as e:
                        log.debug(f"Modal error for '{name}': {e}")
                        await page.keyboard.press("Escape")

                if profile_url and profile_url not in seen_urls:
                    seen_urls.add(profile_url)
                    # Parse city / country
                    parts   = loc.split(",", 1)
                    city    = parts[0].strip() if parts else loc
                    country = parts[1].strip() if len(parts) > 1 else ""

                    all_exhibitors.append({
                        "name":        name,
                        "hall_stand":  hall,
                        "city":        city,
                        "country":     country,
                        "profile_url": profile_url,
                        "letter":      letter,
                    })

            await asyncio.sleep(MIN_DELAY)

        except Exception as e:
            log.error(f"  Error on letter '{letter}': {e}")
        finally:
            await page.close()

    log.info(f"Total unique exhibitors collected: {len(all_exhibitors)}")
    return all_exhibitors


# ─── Step 2 – Scrape detail page (Company data modal) ─────────────────────────
async def scrape_company_details(
    context:      BrowserContext,
    exhibitor:    dict,
    semaphore:    asyncio.Semaphore,
    pbar,
) -> Exhibitor:
    """
    Opens the exhibitor profile page, clicks 'Company data' button,
    extracts address / email / phone / website, also grabs categories
    and description from the main profile page.
    """
    async with semaphore:
        page = await context.new_page()
        result = Exhibitor(
            name        = exhibitor.get("name", ""),
            hall_stand  = exhibitor.get("hall_stand", ""),
            city        = exhibitor.get("city", ""),
            country     = exhibitor.get("country", ""),
            profile_url = exhibitor.get("profile_url", ""),
            letter      = exhibitor.get("letter", ""),
        )

        try:
            await page.goto(
                exhibitor["profile_url"],
                wait_until="networkidle",
                timeout=30_000
            )
            await page.wait_for_selector(".exhibitor-profile", timeout=15_000)

            # ── Description ─────────────────────────────────────────────────
            desc_el = await page.query_selector(".profile__text")
            if desc_el:
                result.description = (await desc_el.inner_text()).strip()

            # ── Hall / Stand (confirm / update) ─────────────────────────────
            hall_el = await page.query_selector(".profile__location")
            if hall_el:
                hall_txt = (await hall_el.inner_text()).strip()
                # Format: "Hall 5 / C06-2Denmark, Hornslet" – take only hall part
                hall_match = re.match(r"(Hall[^,\n]+)", hall_txt)
                if hall_match:
                    result.hall_stand = hall_match.group(1).strip()

            # ── Product categories ──────────────────────────────────────────
            cat_els = await page.query_selector_all(
                ".product-filter__tags-list button, "
                ".product-filter__tag, "
                "[class*='filter-tag']"
            )
            cats = []
            for c in cat_els:
                txt = (await c.inner_text()).strip()
                if txt:
                    cats.append(txt)
            result.categories = " | ".join(cats)

            # ── Click "Company data" button ──────────────────────────────────
            comp_btn = await page.query_selector("a[href*='details'], button.cta-button")
            # Find the right one
            buttons = await page.query_selector_all("a, button")
            comp_data_btn = None
            for btn in buttons:
                txt = (await btn.inner_text()).strip()
                if "Company data" in txt or "company data" in txt.lower():
                    comp_data_btn = btn
                    break

            if comp_data_btn:
                await comp_data_btn.click()
                await page.wait_for_selector(
                    ".modal-window-manager .profile-head__name, "
                    ".exh-address, .profile-details__business-data",
                    timeout=10_000
                )
                await page.wait_for_timeout(500)

                modal = await page.query_selector(".modal-window-manager")
                if modal:
                    # ── Address ──────────────────────────────────────────────
                    street_el = await modal.query_selector(".address-street")
                    if street_el:
                        result.street = (await street_el.inner_text()).strip()

                    zip_el = await modal.query_selector(".address-zip")
                    if zip_el:
                        result.zip_code = (await zip_el.inner_text()).strip()

                    city_el = await modal.query_selector(".address-city")
                    if city_el:
                        result.city = (await city_el.inner_text()).strip()

                    country_el = await modal.query_selector(".address-country")
                    if country_el:
                        result.country = (await country_el.inner_text()).strip()

                    # ── Contact ───────────────────────────────────────────────
                    email_el = await modal.query_selector(".exh-contact__email")
                    if email_el:
                        raw = (await email_el.inner_text()).strip()
                        result.email = raw.replace("E-mail:", "").strip()

                    phone_el = await modal.query_selector(".exh-contact__phone")
                    if phone_el:
                        raw = (await phone_el.inner_text()).strip()
                        result.phone = raw.replace("Phone:", "").strip()

                    web_el = await modal.query_selector(".exh-contact__links a")
                    if web_el:
                        result.website = await web_el.get_attribute("href") or ""

                # Close modal
                close_btn = await page.query_selector(
                    ".modal-window-manager .icon-button"
                )
                if close_btn:
                    await close_btn.click()

            await asyncio.sleep(MIN_DELAY)

        except Exception as e:
            log.debug(f"Detail error for '{exhibitor.get('name', '?')}': {e}")
        finally:
            pbar.update(1)
            await page.close()

    return result


# ─── Step 3 – Fallback: collect exhibitors via paginated search ────────────────
async def collect_exhibitors_from_search(context: BrowserContext) -> list[dict]:
    """
    Fallback method: navigate through the paginated search
    (/vis/v1/en/search?view_type=rows&f_type=profile&_start=N)
    and collect basic exhibitor info. Used if directory method fails.
    """
    all_exhibitors: list[dict] = []
    seen_urls: set[str]        = set()
    start = 0
    rows_per_page = 30

    page = await context.new_page()
    try:
        # First load to detect total count
        await page.goto(SEARCH_URL, wait_until="networkidle", timeout=30_000)
        await page.wait_for_selector(".search__results-info", timeout=15_000)

        info_el = await page.query_selector(".search__results-info")
        total   = 769  # default
        if info_el:
            txt = (await info_el.inner_text()).strip()
            m   = re.search(r"(\d+)", txt)
            if m:
                total = int(m.group(1))
        log.info(f"Search total: {total} exhibitors")
        await page.close()

    except Exception:
        await page.close()
        total = 769

    # Paginate through all results
    while start < total:
        pg = await context.new_page()
        url = (
            f"{BASE_URL}/vis/v1/en/search?"
            f"_start={start}&view_type=rows&f_type=profile"
        )
        try:
            await pg.goto(url, wait_until="networkidle", timeout=30_000)
            await pg.wait_for_selector(".teaser-row", timeout=15_000)

            rows = await pg.query_selector_all(".teaser-row")
            log.info(f"  Search page start={start}: {len(rows)} rows")

            for row in rows:
                name_el = await row.query_selector(".teaser-row__title")
                name    = (await name_el.inner_text()).strip() if name_el else ""

                hall_el = await row.query_selector(".teaser-row__location a")
                hall    = (await hall_el.inner_text()).strip() if hall_el else ""

                # Click Details to get profile URL
                det_btn = await row.query_selector("button.cta-button")
                profile_url = ""
                if det_btn:
                    await det_btn.click()
                    try:
                        await pg.wait_for_selector(
                            ".modal-window-manager .profile-head__name",
                            timeout=8_000
                        )
                        link_el = await pg.query_selector(
                            ".modal-window-manager a[href*='exhprofiles']"
                        )
                        if link_el:
                            profile_url = await link_el.get_attribute("href") or ""
                            if profile_url and not profile_url.startswith("http"):
                                profile_url = BASE_URL + profile_url
                        await pg.keyboard.press("Escape")
                        await pg.wait_for_timeout(400)
                    except Exception:
                        await pg.keyboard.press("Escape")

                if profile_url and profile_url not in seen_urls:
                    seen_urls.add(profile_url)
                    all_exhibitors.append({
                        "name":        name,
                        "hall_stand":  hall,
                        "city":        "",
                        "country":     "",
                        "profile_url": profile_url,
                        "letter":      "",
                    })

        except Exception as e:
            log.error(f"  Search error at start={start}: {e}")
        finally:
            await pg.close()

        start += rows_per_page
        await asyncio.sleep(MIN_DELAY)

    log.info(f"Search collected {len(all_exhibitors)} unique exhibitors")
    return all_exhibitors


# ─── Step 4 – Save to Excel ────────────────────────────────────────────────────
def save_to_excel(exhibitors: list[Exhibitor], path: str) -> None:
    rows = [asdict(e) for e in exhibitors]
    df   = pd.DataFrame(rows, columns=[
        "name", "hall_stand", "street", "zip_code", "city", "country",
        "email", "phone", "website", "categories", "description",
        "profile_url", "letter",
    ])

    # Rename columns for readability
    df.columns = [
        "Company Name", "Hall / Stand", "Street Address", "ZIP Code",
        "City", "Country", "Email", "Phone", "Website",
        "Product Categories", "Description", "Profile URL", "Index Letter",
    ]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Exhibitors")

        ws = writer.sheets["Exhibitors"]

        # Auto-width columns
        for col in ws.columns:
            max_len = max(
                (len(str(cell.value)) if cell.value else 0 for cell in col), default=0
            )
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

        # Freeze header row
        ws.freeze_panes = "A2"

    log.info(f"✅  Saved {len(exhibitors)} exhibitors to '{path}'")


# ─── Main ──────────────────────────────────────────────────────────────────────
async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,          # set True for background runs
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        # ── Phase 1: Collect all exhibitor stubs ──────────────────────────
        log.info("═" * 60)
        log.info("PHASE 1 – Collecting exhibitors from A-Z directory …")
        log.info("═" * 60)

        exhibitor_stubs = await collect_exhibitors_from_directory(context)

        # Fallback if directory gives too few results
        if len(exhibitor_stubs) < 50:
            log.warning("Directory method returned too few results. "
                        "Trying search pagination fallback …")
            exhibitor_stubs = await collect_exhibitors_from_search(context)

        log.info(f"Total stubs: {len(exhibitor_stubs)}")

        # ── Phase 2: Scrape company details concurrently ──────────────────
        log.info("═" * 60)
        log.info(f"PHASE 2 – Scraping company details "
                 f"({MAX_CONCURRENT_TABS} tabs in parallel) …")
        log.info("═" * 60)

        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABS)
        results:  list[Exhibitor] = []

        with atqdm(total=len(exhibitor_stubs), desc="Details") as pbar:
            tasks = [
                scrape_company_details(context, stub, semaphore, pbar)
                for stub in exhibitor_stubs
            ]
            results = await asyncio.gather(*tasks)

        # ── Phase 3: Export ───────────────────────────────────────────────
        log.info("═" * 60)
        log.info("PHASE 3 – Saving to Excel …")
        log.info("═" * 60)

        save_to_excel(list(results), OUTPUT_FILE)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())