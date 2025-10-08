# pip install selenium pandas openpyxl
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    ElementClickInterceptedException, TimeoutException, StaleElementReferenceException
)

URL = "https://www.simec-expo.com/en/exhibitors2025"

def normalize_url(u: str) -> str:
    if not u:
        return ""
    # Wix images sometimes start with '////'
    if u.startswith("////"):
        return "https:" + u[3:]
    if u.startswith("//"):
        return "https:" + u
    return u

def get_rows(driver):
    # Grab visible table rows
    return driver.find_elements(By.CSS_SELECTOR, "tr.wixui-table__row")

def parse_page(driver):
    data = []
    rows = get_rows(driver)
    for r in rows:
        tds = r.find_elements(By.CSS_SELECTOR, "td.wixui-table__cell")
        if len(tds) < 5:
            continue

        # Company
        company = tds[0].text.strip()

        # Logo
        logo = ""
        try:
            img = tds[1].find_element(By.CSS_SELECTOR, "img")
            logo = normalize_url(img.get_attribute("src"))
        except Exception:
            pass

        # Stand, Country
        stand = tds[2].text.strip()
        country = tds[3].text.strip()

        # Website
        website = ""
        try:
            a = tds[4].find_element(By.TAG_NAME, "a")
            website = a.get_attribute("href") or a.text.strip()
        except Exception:
            pass

        data.append({
            "Company Name": company,
            "Logo URL": logo,
            "Stand": stand,
            "Country": country,
            "Website": website
        })
    return data

def click_next(driver, wait):
    next_btn = driver.find_element(By.CSS_SELECTOR, "button[data-testid='page-next']")
    # If disabled attribute is present, we're at the last page
    if next_btn.get_attribute("disabled") is not None:
        return False

    # Scroll into view & JS click (avoids clicking the inner SVG by mistake)
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_btn)
    time.sleep(0.2)
    try:
        driver.execute_script("arguments[0].click();", next_btn)
    except ElementClickInterceptedException:
        # Fallback to normal click if JS click was intercepted
        next_btn.click()

    return True

def wait_for_page_change(driver, wait, prev_first_company):
    # Wait until the first row company changes (table re-rendered)
    try:
        wait.until(lambda d: (lambda first:
                              first and first != prev_first_company)(
            d.find_elements(By.CSS_SELECTOR, "tr.wixui-table__row td.wixui-table__cell")[0].text.strip()
            if d.find_elements(By.CSS_SELECTOR, "tr.wixui-table__row td.wixui-table__cell") else ""
        ))
    except TimeoutException:
        # Sometimes content changes but first cell text stays same (rare). Small sleep as fallback.
        time.sleep(0.8)

def main():
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    # opts.add_argument("--headless=new")  # uncomment if you want headless

    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 15)

    try:
        driver.get(URL)
        # Wait for table to appear
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tr.wixui-table__row")))

        all_rows = []
        seen = set()  # (company, stand) to avoid dupes

        while True:
            # Parse current page
            page_data = parse_page(driver)

            for row in page_data:
                key = (row["Company Name"], row["Stand"])
                if key not in seen:
                    seen.add(key)
                    all_rows.append(row)

            # Check pagination status
            next_btn = driver.find_element(By.CSS_SELECTOR, "button[data-testid='page-next']")
            if next_btn.get_attribute("disabled") is not None:
                break  # last page

            # Capture first company on current page to detect change
            try:
                first_cell = driver.find_element(By.CSS_SELECTOR, "tr.wixui-table__row td.wixui-table__cell")
                prev_first_company = first_cell.text.strip()
            except Exception:
                prev_first_company = ""

            # Click next and wait for content to change
            if not click_next(driver, wait):
                break
            wait_for_page_change(driver, wait, prev_first_company)

            # Short polite delay
            time.sleep(0.5)

        # Save to Excel
        df = pd.DataFrame(all_rows)
        df.to_excel("simec_expo_exhibitors_2025.xlsx", index=False)
        print(f"✅ Saved {len(df)} rows to simec_expo_exhibitors_2025.xlsx")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
