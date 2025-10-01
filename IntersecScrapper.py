from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

# --- URL ---
URL = "https://intersec.ae.messefrankfurt.com/dubai/en/exhibitor-search/exhibitor-search.html"

# --- Setup Selenium ---
driver = webdriver.Chrome()
driver.get(URL)
wait = WebDriverWait(driver, 15)

results = []

def scrape_detail_page():
    """Scrape exhibitor detail page"""
    try:
        name = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "h1.ex-exhibitor-detail__title-headline")
        )).text.strip()
    except:
        name = ""

    city, country, telephone = "", "", ""
    try:
        address_block = driver.find_element(By.CSS_SELECTOR, ".ex-contact-box__address-field-full-address").text
        lines = [l.strip() for l in address_block.split("\n") if l.strip()]
        if len(lines) >= 2:
            city = lines[-2]
            country = lines[-1]
    except:
        pass

    try:
        telephone = driver.find_element(By.CSS_SELECTOR, ".ex-contact-box__address-field-tel-number").text.strip()
    except:
        telephone = ""

    booth_no = ""
    try:
        hall = driver.find_element(By.CSS_SELECTOR,
            ".ex-contact-box__container-location-item-top-hall span.ex-contact-box__container-location-hall").text.strip()
        booth = driver.find_element(By.CSS_SELECTOR,
            ".ex-contact-box__container-location-item-top-stand span.ex-contact-box__container-location-stand").text.strip()
        booth_no = f"{hall} - {booth}"
    except:
        pass

    website, linkedin = "", ""
    try:
        website = driver.find_element(By.CSS_SELECTOR, "a.ex-exhibitor-detail__weblink").get_attribute("href")
    except:
        pass
    try:
        for link in driver.find_elements(By.CSS_SELECTOR, ".ex-exhibitor-detail__social a"):
            href = link.get_attribute("href")
            if "linkedin.com" in href:
                linkedin = href
                break
    except:
        pass

    return {
        "Company Name": name,
        "City": city,
        "Country": country,
        "Booth No": booth_no,
        "Company Website": website,
        "Company LinkedIn": linkedin,
        "Company Contact": telephone
    }

while True:
    # --- Wait for all cards on current page ---
    cards = wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, "div.col-xxs-6.col-md-4.col-sm-6.grid-item a")
    ))
    print(f"Found {len(cards)} cards on this page")

    for i in range(len(cards)):
        # Re-fetch elements to avoid stale reference
        cards = driver.find_elements(By.CSS_SELECTOR, "div.col-xxs-6.col-md-4.col-sm-6.grid-item a")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cards[i])
        time.sleep(0.2)

        # Open in new tab to scrape faster
        driver.execute_script("window.open(arguments[0].href,'_blank');", cards[i])
        driver.switch_to.window(driver.window_handles[1])
        try:
            data = scrape_detail_page()
            results.append(data)
            print(data)  # log data
        except Exception as e:
            print("Error scraping card:", e)
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        time.sleep(0.2)

    # --- Pagination: click last button in m-paging (next page) ---
    try:
        paging = driver.find_element(By.CSS_SELECTOR, "div.m-paging")
        buttons = paging.find_elements(By.TAG_NAME, "button")
        if len(buttons) == 0:
            print("✅ No pagination found, scraping finished")
            break

        last_btn = buttons[-1]  # last button (next page)
        if "disabled" in last_btn.get_attribute("class"):
            print("✅ Reached last page")
            break

        driver.execute_script("arguments[0].scrollIntoView(true);", last_btn)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", last_btn)
        print("➡ Going to next page")
        time.sleep(1)
        wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div.col-xxs-6.col-md-4.col-sm-6.grid-item a")
        ))
    except Exception as e:
        print("✅ Pagination finished or error:", e)
        break

# --- Save all results ---
df = pd.DataFrame(results)
df.to_excel("exhibitors.xlsx", index=False)
print("✅ Saved all data to exhibitors.xlsx")

driver.quit()
