import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

base_url = "https://www.prime-expo.com/exhibitors-2025?page={}"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

all_data = []

for page in range(1, 7):  # pages 1–6
    print(f"Scraping page {page}...")
    url = base_url.format(page)
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    items = soup.select("li.m-exhibitors-list__items__item")

    for item in items:
        name = item.select_one("h2.m-exhibitors-list__items__item__name a")
        hall = item.select_one("div.m-exhibitors-list__items__item__hall")
        stand = item.select_one("div.m-exhibitors-list__items__item__stand")
        country = item.select_one("div.m-exhibitors-list__items__item__location")
        logo = item.select_one("div.m-exhibitors-list__items__item__logo img")
        stand_link = item.select_one("div.m-exhibitors-list__items__item__stand__location a")

        all_data.append({
            "Exhibitor Name": name.get_text(strip=True) if name else "",
            "Hall": hall.get_text(strip=True) if hall else "",
            "Stand": stand.get_text(strip=True) if stand else "",
            "Country": country.get_text(strip=True) if country else "",
            "Logo URL": logo["src"] if logo else "",
            "Find the Stand Link": stand_link["href"] if stand_link else ""
        })

    time.sleep(1)  # polite delay between pages

# Save to Excel
df = pd.DataFrame(all_data)
df.to_excel("prime_expo_exhibitors_2025.xlsx", index=False)

print("✅ Done! Data saved to prime_expo_exhibitors_2025.xlsx")
