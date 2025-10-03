import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://www.sleepexpome.com/exhibitor-list-2025/?page={}"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}

def scrape_page(page):
    url = BASE_URL.format(page)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    data = []
    exhibitors = soup.select("div.list--list-item")

    for ex in exhibitors:
        # Name
        name = ex.select_one("strong.name")
        name = name.get_text(strip=True) if name else ""

        # Stand
        stand = ex.select_one("div.stand")
        stand = stand.get_text(strip=True).replace("Stand:", "").strip() if stand else ""

        # Print to console
        print(f"Name: {name} | Stand: {stand}")

        data.append({
            "Name": name,
            "Stand": stand
        })

    return data


all_data = []

for page in range(1, 7):  # 1 to 6 pages
    print(f"\n🔎 Scraping page {page} ...")
    try:
        page_data = scrape_page(page)
        all_data.extend(page_data)
        time.sleep(1)  # avoid hammering server
    except Exception as e:
        print(f"❌ Error on page {page}: {e}")

# Save to Excel
df = pd.DataFrame(all_data)
df.to_excel("sleepexpo_exhibitors_2025.xlsx", index=False)

print("\n✅ Done! Data saved to sleepexpo_exhibitors_2025.xlsx")
