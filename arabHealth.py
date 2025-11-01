from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)
import time
import pandas as pd

URL = "https://intersec.ae.messefrankfurt.com/dubai/en/exhibitor-search/exhibitor-search.html"

# Selectors
CARD_SEL = "div.ex-exhibitor-search-result-item"
COMPANY_SEL = "h4.ex-exhibitor-search-result-item__headline span"
BOOTH_SEL = "span.ex-exhibitor-search-result-item__location-text"
PAGING_SEL = "div.m-paging"

# Inside details page
DETAIL_CONTAINER = "div.ex-exhibitor-profile"  # profile page container
COUNTRY_SEL = "span.ex-exhibitor-profile__country"
WEBSITE_SEL = "a.ex-exhibitor-profile__website"
LINKEDIN_SEL = "a[href*='linkedin']"
CONTACT_SEL = "a[href^='mailto']"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--log-level=3")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

driver.get(URL)
time.sleep(2)

data = []
page = 1

try:
    while True:
        # Wait until exhibitor cards load
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, CARD_SEL)))
        cards = driver.find_elements(By.CSS_SELECTOR, CARD_SEL)

        for i in range(len(cards)):
            cards = driver.find_elements(By.CSS_SELECTOR, CARD_SEL)
            card = cards[i]

            # Extract company + booth from card
            try:
                company = card.find_element(By.CSS_SELECTOR, COMPANY_SEL).text.strip()
            except:
                company = ""
            try:
                booth = card.find_element(By.CSS_SELECTOR, BOOTH_SEL).text.strip()
            except:
                booth = ""

            # Open detail page
            link = card.find_element(By.TAG_NAME, "a")
            driver.execute_script("arguments[0].click();", link)

            # Wait for detail page
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, DETAIL_CONTAINER)))
            except TimeoutException:
                print("⚠️ Detail page not loading, skipping.")
                driver.back()
                continue

            # Extract details
            try:
                country = driver.find_element(By.CSS_SELECTOR, COUNTRY_SEL).text.strip()
            except:
                country = ""
            try:
                website = driver.find_element(By.CSS_SELECTOR, WEBSITE_SEL).get_attribute("href")
            except:
                website = ""
            try:
                linkedin = driver.find_element(By.CSS_SELECTOR, LINKEDIN_SEL).get_attribute("href")
            except:
                linkedin = ""
            try:
                contact = driver.find_element(By.CSS_SELECTOR, CONTACT_SEL).get_attribute("href").replace("mailto:", "")
            except:
                contact = ""

            data.append({
                "Company Name": company,
                "Country": country,
                "Booth No": booth,
                "Company Website": website,
                "Company LinkedIn": linkedin,
                "Company Contact": contact,
            })

            print(f"✅ Scraped: {company}")

            # Go back
            driver.back()
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, CARD_SEL)))
            time.sleep(0.5)

        # ---- Pagination ----
        try:
            paging_divs = driver.find_elements(By.CSS_SELECTOR, PAGING_SEL)
            if not paging_divs:
                break
            paging = paging_divs[-1]
            next_button = paging.find_element(By.XPATH, ".//button[.//span[contains(@class,'icon-right')]]")
        except NoSuchElementException:
            break

        if next_button.get_attribute("disabled") is not None:
            break

        # Click next page
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_button)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", next_button)

        # Wait for new page data
        try:
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, CARD_SEL)))
            time.sleep(1)
        except TimeoutException:
            break

        page += 1

finally:
    df = pd.DataFrame(data, columns=[
        "Company Name", "Country", "Booth No", "Company Website", "Company LinkedIn", "Company Contact"
    ])
    if not df.empty:
        df.drop_duplicates(inplace=True)
        df.to_excel("exhibitors_full.xlsx", index=False)
        print(f"✅ Saved {len(df)} unique exhibitors to exhibitors_full.xlsx")
    else:
        print("No data scraped.")
    driver.quit()