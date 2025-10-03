import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE_URL = "https://www.ism-me.com/exhibitor-list?page={}&filters.exhibitor-year=__isBlank&searchgroup=CAE58EE8-exhibitors"

headers = {
    "User-Agent": "Mozilla/5.0"
}

def scrape_page(page):
    url = BASE_URL.format(page)
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    items = soup.select("li.m-exhibitors-list__items__item")
    data = []

    for item in items:
        # Name
        name = item.select_one(".m-exhibitors-list__items__item__name a")
        name = name.text.strip() if name else None

        # Hall
        hall = item.select_one(".m-exhibitors-list__items__item__hall")
        hall = hall.text.strip() if hall else None

        # Booth
        booth = item.select_one(".m-exhibitors-list__items__item__stand")
        booth = booth.text.strip() if booth else None

        # Floor Plan Link
        floor_link = item.select_one(".m-exhibitors-list__items__item__find-the-stand a")
        floor_link = floor_link["href"] if floor_link else None

        # Country
        country = item.select_one(".m-exhibitors-list__items__item__location")
        country = country.text.strip() if country else None

        data.append({
            "Name": name,
            "Hall": hall,
            "Booth": booth,
            "Floor Plan Link": floor_link,
            "Country": country
        })

    return data


def scrape_all_pages(max_pages=73):  # default to 73 pages
    all_data = []
    for page in range(1, max_pages + 1):
        print(f"Scraping page {page}/{max_pages} ...")
        page_data = scrape_page(page)
        all_data.extend(page_data)
        time.sleep(1)  # polite delay so we don’t overload the server
    return all_data


if __name__ == "__main__":
    exhibitors = scrape_all_pages(73)
    df = pd.DataFrame(exhibitors)
    df.to_excel("ism_exhibitors_all.xlsx", index=False)
    print("✅ Scraping complete. Saved to ism_exhibitors_all.xlsx")
