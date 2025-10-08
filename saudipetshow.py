from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import re

# --- Website URL ---
URL = "https://www.petvet-expo.com/en/exhibitorslist"

# --- Setup Chrome ---
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

driver.get(URL)
results = []

def scrape_page():
    """Scrape all exhibitors from current page"""
    time.sleep(2)
    rows = wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, "tr.UhXTve.wixui-table__row")
    ))
    print(f"📄 Found {len(rows)} exhibitors on this page")

    for row in rows:
        try:
            cols = row.find_elements(By.CSS_SELECTOR, "td.VG9vCO.wixui-table__cell")
            company_name = cols[0].text.strip() if len(cols) > 0 else ""
            stand_number = cols[2].text.strip() if len(cols) > 2 else ""
            country = cols[3].text.strip() if len(cols) > 3 else ""
            website = ""
            try:
                link_el = cols[4].find_element(By.TAG_NAME, "a")
                website = link_el.get_attribute("href").strip()
            except:
                website = ""
            
            results.append({
                "Company Name": company_name,
                "Country": country,
                "Stand Number": stand_number,
                "Website": website
            })
        except Exception as e:
            print("❌ Error scraping row:", e)

def get_total_pages():
    """Read total pages text like 'Page 1 of 4'"""
    try:
        text = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "div[data-testid='pagination-text']")
        )).text.strip()
        match = re.search(r"of\s+(\d+)", text)
        if match:
            return int(match.group(1))
    except:
        pass
    return 1

# --- Main scraping loop ---
total_pages = get_total_pages()
print(f"📄 Total pages detected: {total_pages}")

for page in range(1, total_pages + 1):
    print(f"\n➡ Scraping Page {page}")
    scrape_page()

    if page < total_pages:
        try:
            next_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[data-testid='page-next']")
            ))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
            time.sleep(1)
            next_btn.click()
            print("➡ Clicked Next Page Button")
            time.sleep(3)

            # Wait until pagination text updates (page number changes)
            wait.until(EC.text_to_be_present_in_element(
                (By.CSS_SELECTOR, "div[data-testid='pagination-text']"),
                f"Page {page + 1}"
            ))

        except Exception as e:
            print("⚠️ Pagination stopped or error:", e)
            break

# --- Save results ---
df = pd.DataFrame(results)
df.to_excel("petvet_exhibitors_full.xlsx", index=False)
print("💾 Saved all data to petvet_exhibitors_full.xlsx")

driver.quit()
