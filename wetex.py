import requests
import pandas as pd
import time
import json

BASE_URL = "https://www.wetex.ae/umbraco/surface/wetexdatasurface/GetExhibitorList"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.wetex.ae/en/exhibit"
}

def scrape_exhibitors():
    all_data = []
    page_size = 20  # Default page size from the website
    current_page = 0
    
    while True:
        params = {
            "PageNumber": current_page,
            "Records": page_size,
            "OrderBy": 0,  # 0 = Sort by, 1 = Exhibitor Name, etc.
            "SearchBy": 0,  # 0 = All
            "type": 1,      # 1 = Private Sector, 2 = Government Organization
            "Search": ""    # Empty search term
        }
        
        print(f"🔎 Scraping page {current_page + 1}...")
        
        try:
            response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                print(f"⚠️ Failed to fetch page {current_page + 1}, status {response.status_code}")
                break
            
            # Parse the HTML response
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.select("tr.m19-table__content-table-row")
            
            if not rows:
                print("⏹️ No more data found. Stopping.")
                break
            
            page_data = []
            for row in rows:
                cells = row.select("td.m19-table__content-table-cell")
                if len(cells) >= 7:
                    record = {
                        "Name": cells[0].get_text(strip=True),
                        "Stand Number": cells[2].get_text(strip=True),
                        "Country": cells[3].get_text(strip=True),
                        "Sector": cells[4].get_text(strip=True),
                        "Business Activity": cells[5].get_text(strip=True),
                        "Hall": cells[6].get_text(strip=True)
                    }
                    print(record)
                    page_data.append(record)
            
            if not page_data:
                print("⏹️ No valid data on this page. Stopping.")
                break
                
            all_data.extend(page_data)
            current_page += 1
            time.sleep(1)  # Be respectful to the server
            
        except Exception as e:
            print(f"❌ Error scraping page {current_page + 1}: {e}")
            break
    
    return all_data

def scrape_government_exhibitors():
    """Scrape government organization exhibitors (type=2)"""
    all_data = []
    page_size = 20
    current_page = 0
    
    while True:
        params = {
            "PageNumber": current_page,
            "Records": page_size,
            "OrderBy": 0,
            "SearchBy": 0,
            "type": 2,      # Government Organization
            "Search": ""
        }
        
        print(f"🔎 Scraping government exhibitors page {current_page + 1}...")
        
        try:
            response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                print(f"⚠️ Failed to fetch government page {current_page + 1}, status {response.status_code}")
                break
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            rows = soup.select("tr.m19-table__content-table-row")
            
            if not rows:
                print("⏹️ No more government data found. Stopping.")
                break
            
            page_data = []
            for row in rows:
                cells = row.select("td.m19-table__content-table-cell")
                if len(cells) >= 7:
                    record = {
                        "Name": cells[0].get_text(strip=True),
                        "Stand Number": cells[2].get_text(strip=True),
                        "Country": cells[3].get_text(strip=True),
                        "Sector": cells[4].get_text(strip=True),
                        "Business Activity": cells[5].get_text(strip=True),
                        "Hall": cells[6].get_text(strip=True),
                        "Type": "Government Organization"
                    }
                    print(record)
                    page_data.append(record)
            
            if not page_data:
                break
                
            all_data.extend(page_data)
            current_page += 1
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Error scraping government page {current_page + 1}: {e}")
            break
    
    return all_data

def scrape_all_exhibitors():
    """Scrape both private sector and government exhibitors"""
    print("🚀 Starting to scrape Private Sector exhibitors...")
    private_exhibitors = scrape_exhibitors()  # type=1
    
    print("\n🚀 Starting to scrape Government Organization exhibitors...")
    government_exhibitors = scrape_government_exhibitors()  # type=2
    
    # Add type to private exhibitors
    for exhibitor in private_exhibitors:
        exhibitor["Type"] = "Private Sector"
    
    all_exhibitors = private_exhibitors + government_exhibitors
    return all_exhibitors

if __name__ == "__main__":
    exhibitors = scrape_all_exhibitors()
    
    if exhibitors:
        df = pd.DataFrame(exhibitors)
        
        # Save to Excel with different sheets for different types
        with pd.ExcelWriter("wetex_exhibitors.xlsx") as writer:
            # All exhibitors
            df.to_excel(writer, sheet_name="All Exhibitors", index=False)
            
            # Private sector only
            private_df = df[df["Type"] == "Private Sector"]
            private_df.to_excel(writer, sheet_name="Private Sector", index=False)
            
            # Government only
            gov_df = df[df["Type"] == "Government Organization"]
            gov_df.to_excel(writer, sheet_name="Government", index=False)
        
        print(f"\n✅ Scraping complete! Saved {len(exhibitors)} exhibitors to wetex_exhibitors.xlsx")
        print(f"   - Private Sector: {len(private_df)} exhibitors")
        print(f"   - Government: {len(gov_df)} exhibitors")
    else:
        print("⚠️ No exhibitors scraped.")