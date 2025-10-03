import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://www.gulfoodmanufacturing.com/2025exhibitorlist?page={}"

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
    exhibitors = soup.select("li.m-exhibitors-list__items__item")
    
    for ex in exhibitors:
        # Name
        name = ex.select_one(".m-exhibitors-list__items__item__name").get_text(strip=True) if ex.select_one(".m-exhibitors-list__items__item__name") else ""

        # Country
        country = ex.select_one(".m-exhibitors-list__items__item__location")
        country = country.get_text(strip=True) if country else ""

        # Hall
        hall = ex.select_one(".m-exhibitors-list__items__item__hall")
        hall = hall.get_text(strip=True) if hall else ""

        # Stand
        stand = ex.select_one(".m-exhibitors-list__items__item__stand")
        stand = stand.get_text(strip=True) if stand else ""

        data.append({
            "Name": name,
            "Country": country,
            "Hall": hall,
            "Stand": stand
        })

    return data


all_data = []

for page in range(1, 42):  # 41 pages
    print(f"Scraping page {page} ...")
    try:
        page_data = scrape_page(page)
        all_data.extend(page_data)
        time.sleep(1)  # be polite, avoid blocking
    except Exception as e:
        print(f"Error on page {page}: {e}")

# Save to Excel
df = pd.DataFrame(all_data)
df.to_excel("gulfood_exhibitors_2025.xlsx", index=False)

print("✅ Done! Data saved to gulfood_exhibitors_2025.xlsx")
