from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time, traceback

# ---------------- CONFIG ----------------
BASE_URL = "https://automechanika.messefrankfurt.com/frankfurt/en/exhibitor-search.html?page={}&pagesize=90"
SAVE_FILE = "Automechanika_Frankfurt.xlsx"
TOTAL_PAGES = 50          # ← Update this after checking the last page number on the site
CHECKPOINT_INTERVAL = 50

# ---------------- SETUP ----------------
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless=new")  # Uncomment for headless mode

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 25)

results = []
counter = 1

# ---------------- HELPERS ----------------
def checkpoint_autosave():
    if len(results) % CHECKPOINT_INTERVAL == 0 and len(results) > 0:
        df = pd.DataFrame(results)
        df.to_excel(SAVE_FILE, index=False)
        print(f"💾 Auto-saved {len(results)} records → {SAVE_FILE}")

def wait_for_redirect_to_finish():
    try:
        wait.until(lambda d: "redirect" not in d.current_url.lower())
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.ex-exhibitor-detail__title-headline")))
        return True
    except:
        return False

def scrape_detail_page():
    """Extract data from one exhibitor detail page."""
    data = {
        "Event": "Automechanika Frankfurt",
        "Company": "",
        "Stand No": "",
        "City": "",
        "Country": "",
        "Company Website": "",
        "LinkedIn": "",
        "Company Contact": "",
        "Stand Link": driver.current_url,
        "Notes": "",
    }

    if not wait_for_redirect_to_finish():
        time.sleep(2)
        wait_for_redirect_to_finish()

    try:
        data["Company"] = driver.find_element(By.CSS_SELECTOR, "h1.ex-exhibitor-detail__title-headline").text.strip()
    except:
        pass

    try:
        addr_block = driver.find_element(By.CSS_SELECTOR, ".ex-contact-box__address-field-full-address").text
        lines = [l.strip() for l in addr_block.split("\n") if l.strip()]
        if len(lines) >= 2:
            data["City"] = lines[-2]
            data["Country"] = lines[-1]
        elif len(lines) == 1:
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
        data["Stand No"] = f"{hall} - {booth}"
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
                data["LinkedIn"] = href
                break
    except:
        pass

    return data

def get_total_pages():
    """
    Auto-detect total pages from the first listing page.
    Falls back to TOTAL_PAGES if detection fails.
    """
    try:
        driver.get(BASE_URL.format(1))
        time.sleep(5)

        # Messe Frankfurt typically renders pagination as <a> tags or a results count
        # Try to read the total result count and calculate pages
        total_text = driver.find_element(By.CSS_SELECTOR, ".ex-search-result__count").text
        # Usually something like "800 Exhibitors"
        total_count = int(''.join(filter(str.isdigit, total_text)))
        pages = (total_count // 90) + (1 if total_count % 90 != 0 else 0)
        print(f"🔍 Detected {total_count} exhibitors across {pages} pages.")
        return pages
    except Exception as e:
        print(f"⚠️ Could not auto-detect pages ({e}). Using TOTAL_PAGES={TOTAL_PAGES}")
        return TOTAL_PAGES

def scrape_page(page_number):
    """Scrape all exhibitors from one listing page."""
    global counter

    driver.get(BASE_URL.format(page_number))
    time.sleep(5)

    # Try the standard Messe Frankfurt card selector
    try:
        cards = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "div.col-xxs-6.col-md-4.col-sm-6.grid-item a")
            )
        )
    except Exception:
        # Fallback: broader anchor selector inside exhibitor cards
        print(f"⚠️ Primary selector failed on page {page_number}, trying fallback selector...")
        try:
            cards = driver.find_elements(By.CSS_SELECTOR, ".ex-exhibitor-search-result-item a")
        except Exception as e2:
            print(f"❌ Could not find exhibitor cards on page {page_number}: {e2}")
            return

    links = [c.get_attribute("href") for c in cards if c.get_attribute("href")]
    # Deduplicate while preserving order
    seen = set()
    links = [l for l in links if not (l in seen or seen.add(l))]

    print(f"\n📄 Page {page_number}: {len(links)} exhibitors found")

    if not links:
        print(f"⚠️ No links found on page {page_number} — possibly the last page or a layout change.")
        return

    # Open each exhibitor in a new tab
    for href in links:
        driver.execute_script("window.open(arguments[0], '_blank');", href)
        time.sleep(0.1)

    # Scrape each tab (skip index 0 = listing page)
    for tab_index in range(1, len(driver.window_handles)):
        driver.switch_to.window(driver.window_handles[tab_index])
        try:
            data = scrape_detail_page()
            results.append(data)
            print(f"✅ {counter:04d} | {data['Company'] or '(No Name)'} | {data['Stand No'] or 'No Stand'} | {data['Country']}")
            counter += 1
        except Exception as e:
            print(f"⚠️ Error scraping tab {tab_index}: {e}")
            traceback.print_exc()
        finally:
            checkpoint_autosave()

    # Close all tabs except main listing tab
    while len(driver.window_handles) > 1:
        driver.switch_to.window(driver.window_handles[-1])
        driver.close()
    driver.switch_to.window(driver.window_handles[0])

# ---------------- MAIN ----------------
try:
    total_pages = get_total_pages()

    for page_number in range(1, total_pages + 1):
        scrape_page(page_number)
        print(f"➡️  Completed page {page_number}/{total_pages}")
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
        print(f"\n💾 Final save: {len(results)} exhibitors → {SAVE_FILE}")
    else:
        print("⚠️ No data collected.")

    driver.quit()
    print("✅ Browser closed. Script finished.")