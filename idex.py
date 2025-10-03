import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Setup Selenium
options = webdriver.ChromeOptions()
# options.add_argument("--headless")  # Uncomment later for production
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--window-size=1920,1080")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

BASE_URL = "https://www.idexuae.ae/exhibit/exhibitor-list/"
driver.get(BASE_URL)
time.sleep(5)

all_data = []
wait = WebDriverWait(driver, 10)

for page in range(1, 66):  # 65 pages
    print(f"\n================= Page {page} =================")
    time.sleep(3)

    # Wait for cards to load and use more specific selector
    cards = wait.until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.v-col-sm-4 div.v-card.v-theme--light.bg-white"))
    )
    print(f"Found {len(cards)} exhibitors on page {page}")

    for idx, card in enumerate(cards, start=1):
        try:
            name = card.find_element(By.CSS_SELECTOR, "div.v-card-title").text.strip()
        except:
            name = ""

        try:
            # Get country - look for the span that contains country name after the flag icon
            country_elements = card.find_elements(By.CSS_SELECTOR, "div.v-card-subtitle span")
            country = ""
            for elem in country_elements:
                text = elem.text.strip()
                # Skip empty text and chip labels (like "Individual", "Brand", etc.)
                if text and not any(keyword in text.lower() for keyword in ['individual', 'brand', 'pavilion', 'uae pavilion']):
                    country = text
                    break
        except:
            country = ""

        try:
            # Stand number - more specific selector
            stand_element = card.find_element(By.CSS_SELECTOR, "a.v-chip--link div.v-chip__content")
            stand_number = stand_element.text.strip()
        except:
            stand_number = ""

        try:
            stand_link = card.find_element(By.CSS_SELECTOR, "a[href*='map.idexuae.ae']").get_attribute("href")
        except:
            stand_link = ""

        try:
            # Website - more specific selector
            website_element = card.find_element(By.CSS_SELECTOR, "div.v-card-text a[target='_blank']")
            website = website_element.get_attribute("href")
        except:
            website = ""

        # Additional data points you might want
        try:
            # Company type (Individual, Brand, Pavilion, etc.)
            type_element = card.find_element(By.CSS_SELECTOR, "span.v-chip--label div.v-chip__content")
            company_type = type_element.text.strip()
        except:
            company_type = ""

        row = {
            "Name": name,
            "Type": company_type,
            "Country": country,
            "Stand Number": stand_number,
            "Stand Link": stand_link,
            "Website": website
        }
        all_data.append(row)

        # Log in console
        print(f"[Page {page} - {idx}] {name} | {country} | {stand_number}")

    # Go to next page - improved selector and waiting
    try:
        # Wait for next button to be clickable
        next_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Next page']"))
        )
        driver.execute_script("arguments[0].scrollIntoView();", next_btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", next_btn)
        
        # Wait for new page to load
        wait.until(EC.staleness_of(cards[0] if cards else next_btn))
        time.sleep(2)
        
    except Exception as e:
        print(f"⚠️ Could not go to next page from page {page}: {e}")
        # Try alternative approach - click page number
        try:
            next_page_num = page + 1
            page_btn = driver.find_element(By.CSS_SELECTOR, f"button.v-btn[aria-label='Go to page {next_page_num}']")
            driver.execute_script("arguments[0].click();", page_btn)
            time.sleep(3)
        except:
            print(f"❌ No more pages available after page {page}")
            break

# Save to Excel
df = pd.DataFrame(all_data)
df.to_excel("idex_exhibitors.xlsx", index=False)

driver.quit()
print(f"\n✅ Scraping finished. Collected {len(all_data)} exhibitors. Data saved to idex_exhibitors.xlsx")