from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

URL = "https://automechanika-dubai.ae.messefrankfurt.com/dubai/en/exhibitor-search/exhibitor-list.html"

# --- Setup Chrome ---
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

driver.get(URL)

results = []

def scrape_detail_page():
    """Scrape exhibitor detail page"""
    # --- Company name ---
    try:
        name = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "h1.ex-exhibitor-detail__title-headline"))
        ).text.strip()
    except:
        name = ""

    # --- City & Country ---
    city, country = "", ""
    try:
        address_block = driver.find_element(By.CSS_SELECTOR, ".ex-contact-box__address-field-full-address").text
        lines = [l.strip() for l in address_block.split("\n") if l.strip()]
        if len(lines) >= 2:
            city = lines[-2]
            country = lines[-1]
    except:
        pass

    # --- Phone ---
    try:
        telephone = driver.find_element(By.CSS_SELECTOR, ".ex-contact-box__address-field-tel-number").text.strip()
    except:
        telephone = ""

    # --- Booth No ---
    booth_no = ""
    try:
        hall = driver.find_element(By.CSS_SELECTOR, ".ex-contact-box__container-location-hall").text.strip()
        booth = driver.find_element(By.CSS_SELECTOR, ".ex-contact-box__container-location-stand").text.strip()
        booth_no = f"{hall} - {booth}"
    except:
        pass

    # --- Website ---
    website = ""
    try:
        website_el = driver.find_element(By.CSS_SELECTOR, "a.ex-contact-box__website-link")
        website = website_el.get_attribute("href").strip()
    except:
        website = ""

    # --- LinkedIn ---
    linkedin = ""
    try:
        social_links = driver.find_elements(By.CSS_SELECTOR, ".ex-contact-box__container-social a")
        for link in social_links:
            href = link.get_attribute("href")
            if href and "linkedin.com" in href:
                linkedin = href
                break
    except:
        linkedin = ""

    return {
        "Company Name": name,
        "City": city,
        "Country": country,
        "Booth No": booth_no,
        "Company Website": website,
        "Company LinkedIn": linkedin,
        "Company Contact": telephone
    }

# --- Pagination loop ---
page = 1
while True:
    # Wait for cards to load
    cards = wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, "div.col-xxs-6.col-md-4.col-sm-6.grid-item a"))
    )
    print(f"📄 Page {page}: Found {len(cards)} exhibitors")

    for i in range(len(cards)):
        # Re-locate to avoid stale element
        cards = driver.find_elements(By.CSS_SELECTOR, "div.col-xxs-6.col-md-4.col-sm-6.grid-item a")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cards[i])
        time.sleep(0.3)

        # Open each in new tab
        href = cards[i].get_attribute("href")
        driver.execute_script("window.open(arguments[0],'_blank');", href)
        driver.switch_to.window(driver.window_handles[1])

        try:
            data = scrape_detail_page()
            results.append(data)
            print(f"✅ Scraped: {data['Company Name']}")
        except Exception as e:
            print("❌ Error:", e)

        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        time.sleep(0.3)

    # --- Pagination ---
    try:
        paging = driver.find_element(By.CSS_SELECTOR, "div.m-paging")
        buttons = paging.find_elements(By.TAG_NAME, "button")
        if not buttons:
            print("✅ No pagination found.")
            break

        next_btn = buttons[-1]
        if "disabled" in next_btn.get_attribute("class"):
            print("✅ Reached last page.")
            break

        driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", next_btn)
        print("➡ Going to next page...")
        page += 1
        time.sleep(3)
        wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div.col-xxs-6.col-md-4.col-sm-6.grid-item a"))
        )
    except Exception as e:
        print("⚠️ Pagination finished or error:", e)
        break

# --- Save to Excel ---
df = pd.DataFrame(results)
df.to_excel("automechanika_exhibitors.xlsx", index=False)
print("💾 Saved all data to automechanika_exhibitors.xlsx")

driver.quit()
