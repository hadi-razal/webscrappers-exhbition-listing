import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import pandas as pd


BASE_URL = "https://www.techshowlondon.co.uk/"

# Single listing page (you can change page=1 to any page you want)
LISTING_URL = (
    "https://www.techshowlondon.co.uk/2026-exhibitor-list?page=1"
    "&sortby=group,title asc ,title asc"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def get_soup(url: str) -> BeautifulSoup:
    """Fetch a URL and return BeautifulSoup parser."""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def extract_exhibitor_paths_from_listing(listing_soup: BeautifulSoup):
    """
    From the listing page, extract exhibitor paths like 'exhibitors/vertiv'.
    These are embedded in javascript:openRemoteModal('exhibitors/vertiv', ...)
    on each card.
    """
    paths = []

    cards = listing_soup.select(
        "ul.m-exhibitors-list__items > "
        "li.m-exhibitors-list__items__item"
    )

    for li in cards:
        data_href = li.get("data-href") or ""

        # Fallback: sometimes the href is on the inner <a>
        if not data_href:
            a = li.select_one(
                "a.js-librarylink-entry[href*='openRemoteModal']"
            )
            if a:
                data_href = a.get("href", "")

        if not data_href:
            continue

        m = re.search(r"openRemoteModal\('([^']+)'", data_href)
        if not m:
            continue

        path = m.group(1)  # e.g. "exhibitors/vertiv"

        if path.startswith("http"):
            full_url = path
        else:
            full_url = urljoin(BASE_URL, path)

        paths.append(full_url)

    return paths


def parse_exhibitor_modal(url: str) -> dict:
    """
    Given a full exhibitor URL, fetch it and parse the modal content.
    Uses the structure from the <main class="content__main"> snippet.
    """
    soup = get_soup(url)

    entry = soup.select_one("div.m-exhibitor-entry__item")
    if not entry:
        return {"url": url, "error": "No exhibitor entry found"}

    # Name
    name_el = entry.select_one(
        "div.m-exhibitor-entry__item__header__infos h1"
    )
    name = name_el.get_text(strip=True) if name_el else ""

    # Stand
    stand_el = entry.select_one(
        "div.m-exhibitor-entry__item__header__infos__stand"
    )
    stand = ""
    if stand_el:
        stand = stand_el.get_text(strip=True)
        stand = stand.replace("Stand:", "").strip()

    # Categories (header categories)
    categories = [
        li.get_text(strip=True)
        for li in entry.select(
            "ul.m-exhibitor-entry__item__header__infos__categories li"
        )
    ]

    # Description
    desc_el = entry.select_one(
        "div.m-exhibitor-entry__item__body__description"
    )
    description = desc_el.get_text(" ", strip=True) if desc_el else ""

    # Address (joined into one line)
    addr_el = entry.select_one(
        "div.m-exhibitor-entry__item__body__contacts__address"
    )
    address = ""
    if addr_el:
        address = " ".join(
            part.strip()
            for part in addr_el.stripped_strings
            if part.lower() != "address"
        )

    # Website button
    website_el = entry.select_one(
        "div.m-exhibitor-entry__item__body__contacts__additional__"
        "button__website a"
    )
    website = website_el.get("href") if website_el else ""

    # Social links
    socials = [
        a.get("href")
        for a in entry.select(
            "ul.m-exhibitor-entry__item__body__contacts__additional__"
            "social a"
        )
        if a.get("href")
    ]

    return {
        "url": url,
        "name": name,
        "stand": stand,
        "categories": categories,
        "description": description,
        "address": address,
        "website": website,
        "socials": socials,
    }


def main():
    # 1) Fetch listing page (single page)
    print(f"Fetching listing page: {LISTING_URL}")
    listing_soup = get_soup(LISTING_URL)

    # 2) Extract exhibitor detail URLs from the cards
    exhibitor_urls = extract_exhibitor_paths_from_listing(listing_soup)
    print(f"Found {len(exhibitor_urls)} exhibitor URLs on this page")

    rows = []

    # 3) Visit each exhibitor modal, print and store data
    for i, url in enumerate(exhibitor_urls, start=1):
        print(f"\n=== Exhibitor {i}: {url} ===")
        data = parse_exhibitor_modal(url)
        rows.append(data)
        for key, value in data.items():
            # Make sure we can print even if there are characters
            # not supported by the current Windows console encoding.
            line = f"{key}: {value}"
            safe_line = line.encode("cp1252", errors="replace").decode("cp1252")
            print(safe_line)

    # 4) Transform data for Excel (flatten lists)
    if rows:
        # Clean categories: list -> comma-separated string, strip leading '|' markers
        for row in rows:
            cats = row.get("categories") or []
            cleaned_cats = [c.lstrip("|").strip() for c in cats]
            row["categories"] = ", ".join(cleaned_cats)

        # Map socials into dedicated columns
        for row in rows:
            socials = row.get("socials") or []
            facebook = ""
            twitter_x = ""
            linkedin = ""
            instagram = ""
            others = []

            for url in socials:
                lower = url.lower()
                if "facebook.com" in lower and not facebook:
                    facebook = url
                elif ("twitter.com" in lower or "x.com" in lower) and not twitter_x:
                    twitter_x = url
                elif "linkedin.com" in lower and not linkedin:
                    linkedin = url
                elif "instagram.com" in lower and not instagram:
                    instagram = url
                else:
                    others.append(url)

            row["facebook"] = facebook
            row["twitter_x"] = twitter_x
            row["linkedin"] = linkedin
            row["instagram"] = instagram
            row["other_socials"] = ", ".join(others)
            # Drop original list column to avoid arrays in Excel
            row.pop("socials", None)

        df = pd.DataFrame(rows)
        output_file = "techshowlondon_exhibitors_page1.xlsx"
        df.to_excel(output_file, index=False)
        print(f"\nSaved {len(rows)} exhibitors to '{output_file}'")
    else:
        print("No exhibitors found to save.")


if __name__ == "__main__":
    main()

