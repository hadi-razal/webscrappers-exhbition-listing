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

COMPANY_SEL = "h4.ex-exhibitor-search-result-item__headline span"
BOOTH_SEL = "span.ex-exhibitor-search-result-item__location-text"
CARD_SEL = "div.ex-exhibitor-search-result-item"
PAGING_SEL = "div.m-paging"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

driver.get(URL)
time.sleep(1)

data = []
page = 1

try:
    while True:
       
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, CARD_SEL)))
        cards = driver.find_elements(By.CSS_SELECTOR, CARD_SEL)

 
        for card in cards:
            try:
                company = card.find_element(By.CSS_SELECTOR, COMPANY_SEL).text.strip()
            except Exception:
                company = ""
            try:
                booth = card.find_element(By.CSS_SELECTOR, BOOTH_SEL).text.strip()
            except Exception:
                booth = ""
            data.append({"Company Name": company, "Booth Number": booth})

        print(f"✅ Page {page}: scraped {len(cards)} companies.")
        page += 1

      
        try:
            paging_divs = driver.find_elements(By.CSS_SELECTOR, PAGING_SEL)
            if not paging_divs:
                print("No paging row found → stopping.")
                break
            paging = paging_divs[-1]

          
            next_button = paging.find_element(By.XPATH, ".//button[.//span[contains(@class,'icon-right')]]")
        except NoSuchElementException:
            print("Next button not found in paging → end.")
            break

        if next_button.get_attribute("disabled") is not None:
            print("Next button is disabled → reached last page.")
            break

  
        prev_first = None
        try:
            prev_first = cards[0].find_element(By.CSS_SELECTOR, COMPANY_SEL).text.strip()
        except Exception:
            prev_first = None

 
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_button)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", next_button)

      
        try:
           
            if prev_first:
                
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, COMPANY_SEL)))
                wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, COMPANY_SEL)[0].text.strip() != prev_first)
            else:
               
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, CARD_SEL)))

            
            time.sleep(0.8)

        except TimeoutException:
            print("⚠️ Timed out waiting for next page to load after clicking next. Stopping to avoid duplicates.")
            break
        except StaleElementReferenceException:
            
            time.sleep(0.5)
            continue

finally:
  
    df = pd.DataFrame(data)
    if not df.empty:
        df.drop_duplicates(subset=["Company Name", "Booth Number"], inplace=True)
        df.to_excel("exhibitors.xlsx", index=False)
        print(f"✅ Saved {len(df)} unique rows to exhibitors.xlsx")
    else:
        print("No data scraped.")
    driver.quit()
