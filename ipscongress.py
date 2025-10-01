from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

URL = "https://www.ipscongress.com/exhibitors-2025"

options = webdriver.ChromeOptions()
options.add_argument("--log-level=3")
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)
driver.get(URL)

wait = WebDriverWait(driver, 10)
cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".exhibitor-item")))
print(f"Found {len(cards)} exhibitors")

data = []

for i, card in enumerate(cards):
    try:
        link = card.find_element(By.TAG_NAME, "a").get_attribute("href")

        # Open detail page in a new tab
        driver.execute_script("window.open(arguments[0]);", link)
        driver.switch_to.window(driver.window_handles[1])
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".col-lg-7 h1")))

        # Scrape details
        company_name = driver.find_element(By.CSS_SELECTOR, ".col-lg-7 h1").text.strip()

        info_paragraphs = driver.find_elements(By.CSS_SELECTOR, ".col-lg-7 p")
        booth_no = ""
        country = ""
        address = ""
        for p in info_paragraphs:
            text = p.text.strip()
            if "Stand No" in text:
                booth_no = text.replace("Stand No:", "").strip()
            elif len(text.split(',')) == 1:
                country = text
            else:
                address = text

        try:
            website = driver.find_element(By.CSS_SELECTOR, ".col-lg-7 a.btn[href*='http']").get_attribute("href")
        except:
            website = ""

        try:
            linkedin = driver.find_element(By.CSS_SELECTOR, ".col-lg-7 a[href*='linkedin.com']").get_attribute("href")
        except:
            linkedin = ""

        contact = ""

        data.append({
            "Company name": company_name,
            "Country": country,
            "Booth No": booth_no,
            "Company Website": website,
            "Company LinkedIn": linkedin,
            "Company Contact": contact
        })

        print(f"Scraped: {company_name}")

        # Close tab and switch back
        driver.close()
        driver.switch_to.window(driver.window_handles[0])

    except Exception as e:
        print(f"Error on card {i+1}: {e}")
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        continue

# Save to CSV
df = pd.DataFrame(data)
df.to_csv("exhibitors_fast.csv", index=False)
print("Data saved to exhibitors_fast.csv")

driver.quit()
