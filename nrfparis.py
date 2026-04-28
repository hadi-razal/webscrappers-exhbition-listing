"""
NRF 2026 Retail's Big Show Europe — Perfect Exhibitor Scraper
=============================================================
All fields verified against live page data.

Fields per exhibitor:
  Company Name · Street · City · Postcode · Country · Phone
  Website · LinkedIn · Instagram · Facebook · Twitter/X
  Hall · Booth(s) · Contact Person · Contact Title · Contact Email
  Description · Product Categories · Exhibitor URL

Output: nrf2026_exhibitors.xlsx
"""

import re
import json
import time
import html as html_module
import requests
import pandas as pd
from bs4 import BeautifulSoup

# ──────────────────────────── CONFIG ────────────────────────────────────────
BASE        = "https://aecopa26.mapyourshow.com/8_0"
GALLERY_API = (
    BASE + "/ajax/remote-proxy.cfm"
    "?action=search&searchtype=exhibitorgallery&searchsize=200&startindex=0"
)
DETAIL_URL  = BASE + "/exhibitor/exhibitor-details.cfm?exhid={exhid}"
OUTPUT      = "nrf2026_exhibitors.xlsx"
DELAY       = 1.0   # seconds between requests — be polite

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    # Required for the gallery JSON API — without this you get 403
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE + "/explore/exhibitor-gallery.cfm",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

session = requests.Session()
session.headers.update(HEADERS)


# ─────────────────── STEP 1: Get all 151 exhibitor IDs ──────────────────────

def get_exhibitor_list() -> list[dict]:
    """
    Calls the internal Vue.js JSON API.
    Returns list of {exhid, name, booths_raw} dicts.
    """
    print("[1/3] Fetching exhibitor list from API …")
    r = session.get(GALLERY_API, timeout=30)
    r.raise_for_status()
    hits = r.json()["DATA"]["results"]["exhibitor"]["hit"]

    exhibitors = []
    for h in hits:
        f = h["fields"]
        # API appends "randomstring" to every booth code — strip it
        booths = [b.replace("randomstring", "").strip()
                  for b in f.get("boothsdisplay_la", [])]
        exhibitors.append({
            "exhid":  f["exhid_l"],
            "name":   f["exhname_t"],
            "booths": booths,
        })

    print(f"   → {len(exhibitors)} exhibitors found")
    return exhibitors


# ─────────────────── STEP 2: Parse one detail page ──────────────────────────

def _js_str(html: str, field: str) -> str:
    """
    Extract the value of a JavaScript string variable from the inline script:
        fieldName: "value with \\/escaped\\/ chars"
    Handles backslash-escaped forward-slashes and quotes.
    """
    m = re.search(
        rf'{re.escape(field)}\s*:\s*"((?:[^"\\\\]|\\\\.)*?)"',
        html
    )
    if not m:
        return ""
    return (m.group(1)
              .replace("\\/", "/")
              .replace('\\"', '"')
              .strip())


def scrape_detail(exhid: str, fallback_name: str, api_booths: list) -> dict:
    url  = DETAIL_URL.format(exhid=exhid)
    r    = session.get(url, timeout=30)
    r.raise_for_status()
    raw  = r.text                           # raw HTML string for regex
    soup = BeautifulSoup(raw, "html.parser")  # for HTML-entity decoding

    row = {
        "Exhibitor ID":    exhid,
        "Exhibitor URL":   url,
        "Company Name":    "",
        "Street Address":  "",
        "City":            "",
        "Postcode":        "",
        "State":           "",
        "Country":         "",
        "Phone":           "",
        "Website":         "",
        "LinkedIn":        "",
        "Instagram":       "",
        "Facebook":        "",
        "Twitter / X":     "",
        "Hall":            "",
        "Booth":           " | ".join(api_booths),
        "Contact Person":  "",
        "Contact Title":   "",
        "Contact Email":   "",
        "Description":     "",
        "Product Categories": "",
    }

    # ── Company name  (H1, auto-decode HTML entities via BeautifulSoup) ────
    h1 = soup.find("h1")
    row["Company Name"] = h1.get_text(strip=True) if h1 else fallback_name

    # ── Address  (embedded as JS object: addressValues: {"ZIP":…, "CITY":…}) ─
    addr_m = re.search(r'addressValues\s*:\s*(\{"ZIP"[^}]+\})', raw)
    if addr_m:
        try:
            a = json.loads(addr_m.group(1))
            parts = [a.get("ADDRESS1",""), a.get("ADDRESS2",""), a.get("ADDRESS3","")]
            row["Street Address"] = ", ".join(p.strip() for p in parts if p.strip())
            row["City"]           = a.get("CITY",    "").strip()
            row["Postcode"]       = a.get("ZIP",     "").strip()
            row["State"]          = a.get("STATE",   "").strip()
            row["Country"]        = a.get("COUNTRY", "").strip()
        except json.JSONDecodeError:
            pass

    # ── Phone / Website / Social  (all stored as JS string vars in <script>) ─
    row["Phone"]      = _js_str(raw, "phoneValue")
    website           = _js_str(raw, "websiteValue")
    row["Website"]    = website if website.startswith("http") else (
                            "https://" + website if website else "")
    row["LinkedIn"]   = _js_str(raw, "linkedInValue")
    row["Instagram"]  = _js_str(raw, "instagramValue")
    row["Facebook"]   = _js_str(raw, "facebookValue")
    row["Twitter / X"]= _js_str(raw, "twitterValue")

    # ── Hall + Booth  (server-rendered HTML: "Hall 6 &mdash; G-022") ────────
    # Some exhibitors have multiple booths — collect all, join with " | "
    hall_matches = re.findall(
        r'Hall\s+(\d+)\s+&mdash;\s+([A-Z0-9-]+)', raw
    )
    if hall_matches:
        halls  = list(dict.fromkeys(f"Hall {h[0]}" for h in hall_matches))
        booths = list(dict.fromkeys(h[1] for h in hall_matches))
        row["Hall"]  = " | ".join(halls)
        row["Booth"] = " | ".join(booths)

    # ── Description  (JS variable: description: "…escaped text…") ──────────
    # Uses \r\n line endings inside the JS string literal
    desc_m = re.search(
        r'\bdescription\s*:\s*"((?:[^"\\]|\\.)*?)"\s*,',
        raw,
        re.DOTALL
    )
    if desc_m and len(desc_m.group(1)) > 5:
        desc = desc_m.group(1)
        desc = desc.replace("\\r\\n", "\n") \
                   .replace("\\n",    "\n") \
                   .replace("\\'",    "'")  \
                   .replace("\\/",    "/")  \
                   .replace('\\"',    '"')
        # Decode any remaining HTML entities (&amp; etc.)
        row["Description"] = html_module.unescape(desc).strip()

    # ── Product Categories  (server-rendered <a> links in the page) ─────────
    cats = re.findall(
        r'href="/8_0/#/searchtype/category/search[^"]*">([^<]+)</a>',
        raw
    )
    row["Product Categories"] = " | ".join(c.strip() for c in cats)

    # ── Contact Person  (assigned at runtime: this.onlinecontactsdata = […]) ─
    # This is a different pattern from the Vue init data — it's a JS assignment
    contact_m = re.search(
        r'this\.onlinecontactsdata\s*=\s*(\[[\s\S]*?\]);\s*\n',
        raw
    )
    if contact_m:
        try:
            contacts = json.loads(contact_m.group(1))
            if contacts:
                c = contacts[0]
                row["Contact Person"] = c.get("fullname", "").strip()
                row["Contact Title"]  = c.get("title",    "").strip()
                row["Contact Email"]  = c.get("email",    "").strip()
        except json.JSONDecodeError:
            # Fallback: pull values directly with regex
            fn = re.search(r'"fullname"\s*:\s*"([^"]+)"', contact_m.group(1))
            ti = re.search(r'"title"\s*:\s*"([^"]+)"',    contact_m.group(1))
            em = re.search(r'"email"\s*:\s*"([^"]+)"',    contact_m.group(1))
            if fn: row["Contact Person"] = fn.group(1).strip()
            if ti: row["Contact Title"]  = ti.group(1).strip()
            if em: row["Contact Email"]  = em.group(1).strip()

    return row


# ─────────────────── STEP 3: Run and save to Excel ──────────────────────────

def main():
    # 1 — Get all exhibitor IDs
    exhibitors = get_exhibitor_list()

    # 2 — Scrape every detail page
    print(f"\n[2/3] Scraping {len(exhibitors)} detail pages …")
    rows = []
    for i, exh in enumerate(exhibitors, 1):
        print(f"  [{i:>3}/{len(exhibitors)}] {exh['name']}  ({exh['exhid']})")
        try:
            row = scrape_detail(exh["exhid"], exh["name"], exh["booths"])
        except Exception as e:
            print(f"         ⚠  Error: {e}")
            row = {
                "Exhibitor ID":  exh["exhid"],
                "Company Name":  exh["name"],
                "Booth":         " | ".join(exh["booths"]),
                "Exhibitor URL": DETAIL_URL.format(exhid=exh["exhid"]),
                "Error":         str(e),
            }
        rows.append(row)
        time.sleep(DELAY)

    # 3 — Build DataFrame & export
    print(f"\n[3/3] Saving {len(rows)} rows → {OUTPUT} …")
    df = pd.DataFrame(rows)

    COLUMN_ORDER = [
        "Exhibitor ID", "Company Name",
        "Street Address", "City", "Postcode", "State", "Country",
        "Phone", "Website", "LinkedIn", "Instagram", "Facebook", "Twitter / X",
        "Hall", "Booth",
        "Contact Person", "Contact Title", "Contact Email",
        "Description", "Product Categories",
        "Exhibitor URL",
    ]
    extra_cols  = [c for c in df.columns if c not in COLUMN_ORDER]
    final_order = [c for c in COLUMN_ORDER if c in df.columns] + extra_cols
    df = df[final_order]

    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="NRF 2026 Exhibitors")
        ws = writer.sheets["NRF 2026 Exhibitors"]

        # Auto-fit column widths
        for col in ws.columns:
            max_w = max(
                (len(str(cell.value)) for cell in col if cell.value),
                default=10
            )
            ws.column_dimensions[col[0].column_letter].width = min(max_w + 3, 80)

        # Freeze the header row
        ws.freeze_panes = "A2"

    print(f"\n✅  DONE — {len(df)} exhibitors saved to: {OUTPUT}")
    print(f"\n{'='*70}")
    print("SAMPLE DATA (first 4 rows):")
    print('='*70)
    preview = ["Company Name", "Country", "Phone", "Website", "LinkedIn",
               "Instagram", "Hall", "Booth"]
    print(df[[c for c in preview if c in df.columns]].head(4).to_string(index=False))


if __name__ == "__main__":
    main()