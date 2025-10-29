from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time, traceback

# ---------------- CONFIG ----------------
BASE_URL = "https://intersec-ksa.ae.messefrankfurt.com/ksa/en/exhibitor-search.html?page={}&pagesize=90"
SAVE_FILE = "Intersec_KSA_2025.xlsx"
TOTAL_PAGES = 7   # only 2 pages now
CHECKPOINT_INTERVAL = 50  # save after every 50 records

# ---------------- SETUP ----------------
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless=new")  # uncomment to run headless

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 25)

results = []
counter = 1  # for numbering

# ---------------- HELPERS ----------------
def checkpoint_autosave():
    if len(results) % CHECKPOINT_INTERVAL == 0 and len(results) > 0:
        df = pd.DataFrame(results)
        df.to_excel(SAVE_FILE, index=False)
        print(f"💾 Auto-saved {len(results)} records → {SAVE_FILE}")

def wait_for_redirect_to_finish():
    """Wait until redirected from blank loader to exhibitor detail."""
    try:
        wait.until(lambda d: "redirect" not in d.current_url.lower())
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.ex-exhibitor-detail__title-headline")))
        return True
    except:
        return False

def scrape_detail_page():
    """Extract data from one exhibitor detail page."""
    data = {
        "Order": "",
        "Company Name": "",
        "City": "",
        "Country": "",
        "Booth No": "",
        "Company Website": "",
        "Company LinkedIn": "",
        "Company Contact": "",
        "URL": driver.current_url,
    }

    if not wait_for_redirect_to_finish():
        time.sleep(2)
        wait_for_redirect_to_finish()

    try:
        data["Company Name"] = driver.find_element(
            By.CSS_SELECTOR, "h1.ex-exhibitor-detail__title-headline"
        ).text.strip()
    except:
        pass

    try:
        addr_block = driver.find_element(
            By.CSS_SELECTOR, ".ex-contact-box__address-field-full-address"
        ).text
        lines = [l.strip() for l in addr_block.split("\n") if l.strip()]
        if len(lines) >= 2:
            data["City"] = lines[-2]
            data["Country"] = lines[-1]
    except:
        pass

    try:
        data["Company Contact"] = driver.find_element(
            By.CSS_SELECTOR, ".ex-contact-box__address-field-tel-number"
        ).text.strip()
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

def scrape_page(page_number):
    """Scrape all exhibitors from one page (up to 90 per page)."""
    global counter

    driver.get(BASE_URL.format(page_number))
    time.sleep(5)

    cards = wait.until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div.col-xxs-6.col-md-4.col-sm-6.grid-item a")
        )
    )

    links = [c.get_attribute("href") for c in cards if c.get_attribute("href")]
    print(f"\n📄 Page {page_number}: {len(links)} exhibitors found")
    print(f"🟢 Opening all {len(links)} exhibitor tabs...")

    # Open all tabs
    for href in links:
        driver.execute_script("window.open(arguments[0], '_blank');", href)
        time.sleep(0.1)

    # Scrape each opened tab
    for tab_index in range(1, len(driver.window_handles)):
        driver.switch_to.window(driver.window_handles[tab_index])
        try:
            data = scrape_detail_page()
            data["Order"] = counter
            results.append(data)
            print(f"✅ {counter} | {data['Company Name'] or '(No Name)'}")
            counter += 1
        except Exception as e:
            print(f"⚠️ Error scraping tab {tab_index}: {e}")
            traceback.print_exc()
            continue

    checkpoint_autosave()

    # Close all tabs except main
    for _ in range(len(driver.window_handles) - 1):
        driver.switch_to.window(driver.window_handles[-1])
        driver.close()
    driver.switch_to.window(driver.window_handles[0])

# ---------------- MAIN ----------------
try:
    for page_number in range(1, TOTAL_PAGES + 1):
        scrape_page(page_number)
        print(f"➡️ Completed page {page_number}")
        time.sleep(3)

except KeyboardInterrupt:
    print("\n🛑 Interrupted by user — saving progress.")
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    traceback.print_exc()
finally:
    if results:
        df = pd.DataFrame(results)
        df.to_excel(SAVE_FILE, index=False)
        print(f"\n💾 Final save completed: {len(results)} exhibitors saved to {SAVE_FILE}")
    else:
        print("⚠️ No data to save.")

    driver.quit()
    print("✅ Browser closed. Script finished safely.")
