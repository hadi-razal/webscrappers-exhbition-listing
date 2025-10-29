from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time, traceback

# ---------------- CONFIG ----------------
URL = "https://www.worldhealthexpo.com/events/labs/dubai/en/attend/exhibitor-list.html"
SAVE_FILE = "medlab_full_exhibitors.xlsx"

# ---------------- SETUP ----------------
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless=new")  # optional if running on server

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 25)

# ---------------- LOAD PAGE ----------------
driver.get(URL)
time.sleep(8)

# ---------------- INFINITE SCROLL ----------------
def scroll_until_end(pause=2, max_waits=10):
    """Scroll until all exhibitors loaded."""
    same_height_count = 0
    last_height = driver.execute_script("return document.body.scrollHeight")
    while same_height_count < max_waits:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            same_height_count += 1
        else:
            same_height_count = 0
        last_height = new_height
        print(f"⬇️ Scrolling... current height: {new_height}")
    print("✅ Finished scrolling. All exhibitors should be loaded.")

scroll_until_end()

# ---------------- SCRAPE ALL EXHIBITOR LINKS ----------------
cards = driver.find_elements(By.CSS_SELECTOR, "a[href*='/widget/event/medlab-middle-east-2025/exhibitor/']")
print(f"📦 Total exhibitor cards found: {len(cards)}")

exhibitor_links = [c.get_attribute("href") for c in cards if c.get_attribute("href")]

results = []
counter = 1

# ---------------- FUNCTION TO SCRAPE DETAIL PAGE ----------------
def scrape_detail_page():
    data = {
        "Order": "",
        "Company Name": "",
        "Booth No": "",
        "Country": "",
        "Hall": "",
        "Team Members": "",
        "URL": driver.current_url,
    }

    # Name
    try:
        name_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.sc-5973f5f6-7")))
        data["Company Name"] = name_el.text.strip()
    except:
        pass

    # Booth
    try:
        booth_el = driver.find_element(By.CSS_SELECTOR, "span.sc-e737835f-0.dGsaxK")
        data["Booth No"] = booth_el.text.strip()
    except:
        pass

    # Hall
    try:
        hall_el = driver.find_element(By.XPATH, "//div[text()='Halls']/following-sibling::div")
        data["Hall"] = hall_el.text.strip()
    except:
        pass

    # Country
    try:
        country_el = driver.find_element(By.XPATH, "//div[text()='Country']/following-sibling::div//span")
        data["Country"] = country_el.text.strip()
    except:
        pass

    # Team Members
    try:
        team_blocks = driver.find_elements(By.CSS_SELECTOR, "div.sc-93d274cd-0.gzRgeD")
        team_list = []
        for block in team_blocks:
            try:
                name = block.find_element(By.CSS_SELECTOR, "span.sc-26585cd5-9").text.strip()
                role = block.find_element(By.CSS_SELECTOR, "span.sc-26585cd5-11").text.strip()
                company = block.find_element(By.CSS_SELECTOR, "span.sc-26585cd5-12").text.strip()
                team_list.append(f"{name} - {role} ({company})")
            except:
                continue
        data["Team Members"] = "; ".join(team_list)
    except:
        pass

    return data

# ---------------- SCRAPE EACH EXHIBITOR ----------------
for link in exhibitor_links:
    try:
        driver.execute_script("window.open(arguments[0], '_blank');", link)
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(4)
        data = scrape_detail_page()
        data["Order"] = counter
        results.append(data)
        print(f"✅ {counter}. {data['Company Name'] or '(No Name)'} — {data['Booth No']}")
        counter += 1
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
    except Exception as e:
        print(f"⚠️ Error on exhibitor {counter}: {e}")
        traceback.print_exc()
        try:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass
        continue

# ---------------- SAVE TO EXCEL ----------------
if results:
    df = pd.DataFrame(results)
    df.to_excel(SAVE_FILE, index=False)
    print(f"\n💾 Saved {len(results)} exhibitors to {SAVE_FILE}")
else:
    print("⚠️ No exhibitors scraped.")

driver.quit()
print("✅ Browser closed. Script finished safely.")
