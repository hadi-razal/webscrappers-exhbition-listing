from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd

options = webdriver.ChromeOptions()
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(options=options)

url = "https://middleeast.breakbulk.com/exhibitors"
driver.get(url)

wait = WebDriverWait(driver, 12)
data = []

def get_location(contact_element):
    location_text = ""
    try:
        children = contact_element.get_attribute("innerHTML").split("<br>")
        for i, child in enumerate(children):
            if "Location" in child:
                if i + 1 < len(children):
                    location_text = children[i + 1].strip()
                break
        location_text = location_text.replace("\n", "").replace("\r", "").strip()
    except:
        location_text = ""
    return location_text

def scrape_detail(link):
    driver.execute_script("window.open(arguments[0], '_blank');", link)
    driver.switch_to.window(driver.window_handles[-1])
    try:
        company = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".exhibitor-title-banner h1"))).text.strip()
        try:
            booth = driver.find_element(By.CSS_SELECTOR, ".exhibitor-profile-stand").text.strip()
        except:
            booth = ""
        try:
            contact_block = driver.find_element(By.CSS_SELECTOR, ".exhibitor-contacts")
            location = get_location(contact_block)
        except:
            location = ""
        try:
            website_elem = driver.find_element(By.CSS_SELECTOR, ".exhibitor-contacts a")
            website = website_elem.get_attribute("href")
        except:
            website = ""
        data.append({
            "Company": company,
            "Booth": booth,
            "Location": location,
            "Website": website
        })
        print(f"✅ Scraped: {company} | Booth: {booth} | Location: {location} | Website: {website}")
    except Exception as e:
        print(f"⚠️ Failed to scrape {link}: {e}")
    finally:
        driver.close()
        driver.switch_to.window(driver.window_handles[0])

while True:
    cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.exhibitor-details")))
    print(f"📦 Found {len(cards)} exhibitors on this page")
    links = []
    for card in cards:
        try:
            parent = card.find_element(By.XPATH, "./ancestor::a[1]")
            links.append(parent.get_attribute("href"))
        except:
            continue
    for link in links:
        scrape_detail(link)
    try:
        next_btn = driver.find_element(By.CSS_SELECTOR, ".m-paging button.btn.btn-default.btn-icon-single:last-child")
        if "disabled" in next_btn.get_attribute("outerHTML"):
            print("⚠️ No more pages.")
            break
        next_btn.click()
        time.sleep(2)
    except:
        print("⚠️ Pagination finished.")
        break

df = pd.DataFrame(data)
df.to_excel("breakbulk_exhibitors.xlsx", index=False)
print(f"✅ Saved {len(df)} exhibitors to breakbulk_exhibitors.xlsx")

driver.quit()
