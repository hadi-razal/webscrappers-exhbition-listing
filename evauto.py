from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

BASE_URL = "https://evautoshowonline.com/exhibitorlist.aspx"

def init_driver():
    options = Options()
    options.add_argument("--start-maximized")
    # options.add_argument("--headless")  # uncomment if you don’t want to see Chrome
    service = Service()  # if chromedriver is in PATH
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def scrape_exhibitors():
    driver = init_driver()
    driver.get(BASE_URL)

    wait = WebDriverWait(driver, 10)

    exhibitors_data = []

    # find all exhibitor cards
    cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.col-lg-3.col-md-4.col-sm-6.col-xs-12 div.card")))

    for idx, card in enumerate(cards, start=1):
        try:
            name = card.find_element(By.CSS_SELECTOR, "h5.card-title").text.strip()
            stand = card.find_element(By.CSS_SELECTOR, "p.card-text strong").text.strip()
            more_link = card.find_element(By.CSS_SELECTOR, "a.moreDetailBtn").get_attribute("href")

            print(f"[{idx}] {name} - {stand}")

            # open details page
            driver.execute_script("window.open(arguments[0]);", more_link)
            driver.switch_to.window(driver.window_handles[1])

            # wait for company name
            wait.until(EC.presence_of_element_located((By.ID, "cphContents_lblCompanyNamehead")))

            company_name = driver.find_element(By.ID, "cphContents_lblCompanyNamehead").text.strip()

            # Stand number (inside)
            try:
                stand_number = driver.find_element(By.ID, "cphContents_lblStandNo").text.replace("Stand Number:", "").strip()
            except:
                try:
                    stand_number = driver.find_element(By.ID, "cphContents_lblStand").text.replace("Stand Number:", "").strip()
                except:
                    stand_number = ""

            # Website
            try:
                website = driver.find_element(By.CSS_SELECTOR, "#cphContents_Label23 a").get_attribute("href")
            except:
                website = ""

            # Country
            try:
                country = driver.find_element(By.ID, "cphContents_Label10").text.replace("Country:", "").strip()
            except:
                country = ""

            # LinkedIn
            linkedin = ""
            try:
                social_links = driver.find_elements(By.CSS_SELECTOR, ".ForSocialColor_ a")
                for sl in social_links:
                    href = sl.get_attribute("href")
                    if "linkedin" in href:
                        linkedin = href
                        break
            except:
                pass

            # Description
            try:
                desc_blocks = driver.find_elements(By.CSS_SELECTOR, "div.ContentBox p span[style]")
                description = " ".join([d.text.strip() for d in desc_blocks if d.text.strip()])
            except:
                description = ""

            exhibitors_data.append({
                "list_name": name,
                "list_stand": stand,
                "detail_url": more_link,
                "company_name": company_name,
                "stand_number": stand_number,
                "website": website,
                "country": country,
                "linkedin": linkedin,
                "description": description
            })

            # close detail tab and return to main list
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

            time.sleep(1)  # polite delay

        except Exception as e:
            print(f"Error scraping card {idx}: {e}")
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

    driver.quit()
    return exhibitors_data

def main():
    data = scrape_exhibitors()
    df = pd.DataFrame(data)
    df.to_excel("evautoshow_exhibitors_selenium.xlsx", index=False)
    print("Saved evautoshow_exhibitors_selenium.xlsx")

if __name__ == "__main__":
    main()
