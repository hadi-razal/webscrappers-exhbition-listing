from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time

# ---------------- SETUP ----------------
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 25)

url = "https://arabianorganics.com/pages/exhibitors"
driver.get(url)
time.sleep(5)

exhibitors = []

# ---------------- MAIN SCRAPING ----------------
cards = driver.find_elements(By.CSS_SELECTOR, "div.mb-3.pb-3.col-md-4")
print(f"🔍 Found {len(cards)} exhibitors to scrape.")

for index in range(len(cards)):
    try:
        cards = driver.find_elements(By.CSS_SELECTOR, "div.mb-3.pb-3.col-md-4")
        card = cards[index]
        driver.execute_script("arguments[0].scrollIntoView(true);", card)
        time.sleep(1)

        name = card.find_element(By.CSS_SELECTOR, "h2").text.strip()
        print(f"\n➡️ Opening {index+1}/{len(cards)}: {name}")

        link = card.find_element(By.CSS_SELECTOR, "a")
        driver.execute_script("arguments[0].click();", link)

        # Wait for inside page
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".company_name")))
        time.sleep(2)

        # ---------------- Extract core info ----------------
        try:
            company_name = driver.find_element(By.CSS_SELECTOR, ".company_name").text.strip()
        except:
            company_name = name

        try:
            loc_text = driver.find_element(By.CSS_SELECTOR, "#location").text.strip()
            country = loc_text.split(",")[-1].strip()
        except:
            country = ""

        try:
            intro = driver.find_element(By.CSS_SELECTOR, "#company_intro").text.strip()
        except:
            intro = ""

        # ---------------- Extract labeled fields ----------------
        fields = {"Address": "", "City": "", "Website": "", "Phone": "", "Email": ""}
        rows = driver.find_elements(By.CSS_SELECTOR, ".col-md-7 .row")

        for row in rows:
            try:
                label = row.find_element(By.CSS_SELECTOR, ".col-md-4").text.strip().replace(":", "")
                value = row.find_element(By.CSS_SELECTOR, ".col-md-8").text.strip()
                if label in fields:
                    fields[label] = value
            except:
                continue

        exhibitors.append({
            "Name": company_name,
            "Country": country,
            "Introduction": intro,
            "Address": fields["Address"],
            "City": fields["City"],
            "Website": fields["Website"],
            "Phone": fields["Phone"],
            "Email": fields["Email"]
        })

        print(f"✅ Scraped: {company_name} ({country})")

        # Go back (AJAX)
        driver.execute_script("window.history.go(-1)")
        time.sleep(3)
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.mb-3.pb-3.col-md-4")))

    except Exception as e:
        print(f"⚠️ Error on item {index+1}: {e}")
        driver.execute_script("window.history.go(-1)")
        time.sleep(3)
        continue

# ---------------- SAVE ----------------
df = pd.DataFrame(exhibitors)
df.to_excel("arabian_organics_exhibitors_final.xlsx", index=False)
print(f"\n🎉 Done! {len(df)} exhibitors saved to 'arabian_organics_exhibitors_final.xlsx'.")

driver.quit()
