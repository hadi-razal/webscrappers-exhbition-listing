from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

# --- Website URL ---
URL = "https://saudipp.com/exhibitor-list/"

# --- Setup Chrome ---
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

driver.get(URL)
time.sleep(5)  # allow JS to load the full table

results = []

# --- Locate all rows ---
rows = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table tbody tr")))

print(f"📄 Found {len(rows)} exhibitors")

for i in range(len(rows)):
    try:
        # Re-locate each time to avoid stale elements
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

        # Skip expanded rows (data-expanded='true')
        row = rows[i]
        if row.get_attribute("data-expanded") == "true":
            continue

        company_name = ""
        stand_no = ""
        country = ""
        website = ""

        # Basic visible columns
        try:
            company_name = row.find_element(By.CSS_SELECTOR, ".ninja_column_1").text.strip()
        except:
            pass

        try:
            stand_no = row.find_element(By.CSS_SELECTOR, ".ninja_column_2").text.strip()
        except:
            pass

        try:
            country = row.find_element(By.CSS_SELECTOR, ".ninja_column_3").text.strip()
        except:
            pass

        # Click the plus button to expand
        try:
            plus_btn = row.find_element(By.CSS_SELECTOR, ".footable-toggle")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", plus_btn)
            driver.execute_script("arguments[0].click();", plus_btn)
            time.sleep(1.2)
        except Exception as e:
            print("⚠️ Could not expand row:", e)

        # After expansion, re-locate the same row (it updates to minus icon)
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        expanded_row = rows[i]

        # Extract website from hidden cell
        try:
            website_el = expanded_row.find_element(By.CSS_SELECTOR, ".ninja_column_8 a")
            website = website_el.get_attribute("href")
        except:
            website = ""

        # Append result
        results.append({
            "Company Name": company_name,
            "Country": country,
            "Stand Number": stand_no,
            "Website": website
        })

        print(f"✅ {company_name} | {country} | {stand_no} | {website}")

    except Exception as e:
        print("❌ Error scraping row:", e)

# --- Save results ---
df = pd.DataFrame(results)
df.to_excel("saudipp_exhibitors.xlsx", index=False)
print("💾 Saved all data to saudipp_exhibitors.xlsx")

driver.quit()
