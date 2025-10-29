
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time, os, sys, traceback
from datetime import datetime

# ---------------- CONFIG ----------------
URL = "https://beautyworld-saudi-arabia.ae.messefrankfurt.com/ksa/en/exhibitor-search.html"
SAVE_FILE = "beautyworldksa.xlsx"
CHECKPOINT_INTERVAL = 10  

# ---------------- SETUP ----------------
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 25)

results = []

# ------------- AUTO-SAVE CHECKPOINT -------------
def checkpoint_autosave():
    """Save intermediate progress every few items."""
    if len(results) % CHECKPOINT_INTERVAL == 0 and len(results) > 0:
        df = pd.DataFrame(results)
        df.to_excel(SAVE_FILE, index=False)
        print(f"💾 Auto-saved {len(results)} records → {SAVE_FILE}")

# ------------- SCRAPER FUNCTION -------------
def scrape_detail_page():
    """Scrape one exhibitor detail page."""
    data = {
        "Company Name": "",
        "City": "",
        "Country": "",
        "Booth No": "",
        "Company Website": "",
        "Company LinkedIn": "",
        "Company Contact": ""
    }

    try:
        data["Company Name"] = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1.ex-exhibitor-detail__title-headline"))
        ).text.strip()
    except:
        pass

    try:
        addr_block = driver.find_element(By.CSS_SELECTOR, ".ex-contact-box__address-field-full-address").text
        lines = [l.strip() for l in addr_block.split("\n") if l.strip()]
        if len(lines) >= 2:
            data["City"] = lines[-2]
            data["Country"] = lines[-1]
    except:
        pass

    try:
        data["Company Contact"] = driver.find_element(By.CSS_SELECTOR, ".ex-contact-box__address-field-tel-number").text.strip()
    except:
        pass

    try:
        hall = driver.find_element(By.CSS_SELECTOR, ".ex-contact-box__container-location-hall").text.strip()
        booth = driver.find_element(By.CSS_SELECTOR, ".ex-contact-box__container-location-stand").text.strip()
        data["Booth No"] = f"{hall} - {booth}"
    except:
        pass

    try:
        website_el = driver.find_element(By.CSS_SELECTOR, "a.ex-contact-box__website-link")
        data["Company Website"] = website_el.get_attribute("href").strip()
    except:
        pass

    try:
        social_links = driver.find_elements(By.CSS_SELECTOR, ".ex-contact-box__container-social a")
        for link in social_links:
            href = link.get_attribute("href")
            if href and "linkedin.com" in href:
                data["Company LinkedIn"] = href
                break
    except:
        pass

    return data

# ------------- MAIN LOOP -------------
try:
    driver.get(URL)
    time.sleep(5)
    page = 1

    while True:
        cards = wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div.col-xxs-6.col-md-4.col-sm-6.grid-item a"))
        )
        print(f"\n📄 Page {page}: {len(cards)} exhibitors found")

        for i in range(len(cards)):
            try:
                cards = driver.find_elements(By.CSS_SELECTOR, "div.col-xxs-6.col-md-4.col-sm-6.grid-item a")
                href = cards[i].get_attribute("href")
                driver.execute_script("window.open(arguments[0], '_blank');", href)
                driver.switch_to.window(driver.window_handles[1])

                data = scrape_detail_page()
                results.append(data)
                print(f"✅ {len(results)} | {data['Company Name']}")
                checkpoint_autosave()

                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                time.sleep(0.5)

            except Exception as e:
                print(f"⚠️ Error on item {i+1}: {e}")
                traceback.print_exc()
                try:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                except:
                    pass
                continue

        # Pagination
        try:
            paging = driver.find_element(By.CSS_SELECTOR, "div.m-paging")
            buttons = paging.find_elements(By.TAG_NAME, "button")

            if not buttons:
                print("✅ No pagination buttons found. Exiting.")
                break

            next_btn = buttons[-1]
            if "disabled" in next_btn.get_attribute("class"):
                print("✅ Reached final page.")
                break

            driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", next_btn)
            print(f"➡️ Moving to next page ({page+1})...")
            page += 1
            time.sleep(3)

        except Exception as e:
            print("⚠️ Pagination ended or error:", e)
            break

except KeyboardInterrupt:
    print("\n🛑 Interrupted by user — saving progress.")
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    traceback.print_exc()
finally:
    # --- Always save whatever is scraped ---
    if results:
        df = pd.DataFrame(results)
        df.to_excel(SAVE_FILE, index=False)
        print(f"\n💾 Final save completed: {len(results)} exhibitors saved to {SAVE_FILE}")
    else:
        print("⚠️ No data to save.")

    driver.quit()
    print("✅ Browser closed. Script finished safely.")
