from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd

# ---------------- CONFIG ----------------
URL = "https://middleeast.breakbulk.com/exhibitors"
SAVE_FILE = "breakbulk_2026.xlsx"

# ---------------- SETUP ----------------
options = webdriver.ChromeOptions()
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--start-maximized")
# options.add_argument("--headless=new")  # optional
driver = webdriver.Chrome(options=options)

wait = WebDriverWait(driver, 20)
data = []

# ---------------- HELPERS ----------------
def get_country(contact_element):
    """Extract country text from contact block"""
    try:
        html = contact_element.get_attribute("innerHTML").split("<br>")
        for i, item in enumerate(html):
            if "Location" in item:
                if i + 1 < len(html):
                    country = html[i + 1].strip()
                    return country.replace("\n", "").replace("\r", "")
    except:
        pass
    return ""

def scrape_detail():
    """Extract exhibitor details from current tab"""
    info = {
        "Company name": "",
        "Country": "",
        "Booth No": "",
        "Company Website": "",
        "Company LinkedIn": "",
        "Company Contact": "",
        "URL": driver.current_url
    }

    try:
        company = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".exhibitor-title-banner h1"))).text.strip()
        info["Company name"] = company
    except:
        pass

    try:
        info["Booth No"] = driver.find_element(By.CSS_SELECTOR, ".exhibitor-profile-stand").text.strip()
    except:
        pass

    try:
        contact_block = driver.find_element(By.CSS_SELECTOR, ".exhibitor-contacts")
        info["Country"] = get_country(contact_block)
        info["Company Contact"] = contact_block.text.strip()

        links = contact_block.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href:
                if "linkedin.com" in href.lower():
                    info["Company LinkedIn"] = href
                elif href.startswith("http"):
                    info["Company Website"] = href
    except:
        pass

    return info

def open_and_scrape_all_on_page(links):
    """Open all exhibitors in new tabs, scrape, then close"""
    print(f"🟢 Opening {len(links)} exhibitor tabs...")

    # --- Open all tabs ---
    for href in links:
        driver.execute_script("window.open(arguments[0], '_blank');", href)
        time.sleep(0.1)

    # --- Scrape each tab ---
    for i in range(1, len(driver.window_handles)):
        driver.switch_to.window(driver.window_handles[i])
        try:
            exhibitor = scrape_detail()
            data.append(exhibitor)
            print(f"✅ {len(data)} | {exhibitor['Company name'] or '(No Name)'} — {exhibitor['Booth No']}")
        except Exception as e:
            print(f"⚠️ Error scraping tab {i}: {e}")
            continue

    # --- Close all tabs except main ---
    while len(driver.window_handles) > 1:
        driver.switch_to.window(driver.window_handles[-1])
        driver.close()
    driver.switch_to.window(driver.window_handles[0])
    print(f"💾 Completed {len(links)} exhibitors on this page.\n")

# ---------------- MAIN SCRAPING LOOP ----------------
driver.get(URL)
time.sleep(5)
page_number = 1

while True:
    cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.exhibitor-details")))
    print(f"\n📄 Page {page_number}: Found {len(cards)} exhibitors")

    # Collect all exhibitor links
    links = []
    for card in cards:
        try:
            parent = card.find_element(By.XPATH, "./ancestor::a[1]")
            href = parent.get_attribute("href")
            if href and href not in links:
                links.append(href)
        except:
            continue

    # Open all exhibitors and scrape their data
    open_and_scrape_all_on_page(links)

    # --- Try to click Next page ---
    try:
        next_btn = driver.find_element(By.CSS_SELECTOR, ".m-paging button.btn.btn-default.btn-icon-single:last-child")
        if "disabled" in next_btn.get_attribute("outerHTML"):
            print("✅ No more pages.")
            break
        driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
        time.sleep(1)
        next_btn.click()
        page_number += 1
        time.sleep(4)
    except Exception as e:
        print(f"⚠️ Pagination finished or error: {e}")
        break

# ---------------- SAVE TO EXCEL ----------------
df = pd.DataFrame(data)
df.to_excel(SAVE_FILE, index=False)
print(f"\n💾 Saved {len(df)} exhibitors to {SAVE_FILE}")
driver.quit()
print("✅ Browser closed safely.")
