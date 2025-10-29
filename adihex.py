from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time

# ---------- SETUP ----------
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")  # open browser fullscreen
options.add_argument("--disable-blink-features=AutomationControlled")  # avoid detection

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

url = "https://www.adihex.com/ar/exhibitor-information/exhibitor-list"
driver.get(url)

wait = WebDriverWait(driver, 30)
actions = ActionChains(driver)

exhibitors = []
page = 1

# ---------- MAIN LOOP ----------
while True:
    print(f"🟢 Scraping Page {page}...")
    try:
        # Wait for cards to load
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".v-card.v-theme--light")))
        time.sleep(2)

        # Scroll gradually to load all exhibitors
        for _ in range(5):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight / 3);")
            time.sleep(1.5)

        cards = driver.find_elements(By.CSS_SELECTOR, ".v-card.v-theme--light")
        print(f"Found {len(cards)} exhibitors on this page")

        for card in cards:
            try:
                name = card.find_element(By.CSS_SELECTOR, ".v-card-title").text.strip()
            except:
                name = ""

            try:
                country = card.find_element(By.CSS_SELECTOR, ".v-card-subtitle span").text.strip()
            except:
                country = ""

            try:
                stand_elem = card.find_element(By.CSS_SELECTOR, ".v-chip.v-chip--link")
                stand_number = stand_elem.text.strip()
                stand_map = stand_elem.get_attribute("href")
            except:
                stand_number, stand_map = "", ""

            # collect all social/media links
            links = {}
            try:
                link_buttons = card.find_elements(By.CSS_SELECTOR, "a.v-btn")
                for l in link_buttons:
                    href = l.get_attribute("href")
                    if not href:
                        continue
                    if "instagram" in href:
                        links["Instagram"] = href
                    elif "facebook" in href:
                        links["Facebook"] = href
                    elif "linkedin" in href:
                        links["LinkedIn"] = href
                    elif "twitter" in href or "x.com" in href:
                        links["Twitter"] = href
                    elif "youtube" in href:
                        links["YouTube"] = href
                    elif "http" in href:
                        links["Website"] = href
            except:
                pass

            exhibitors.append({
                "Name": name,
                "Country": country,
                "Stand Number": stand_number,
                "Stand Map": stand_map,
                "Website": links.get("Website", ""),
                "Instagram": links.get("Instagram", ""),
                "Facebook": links.get("Facebook", ""),
                "LinkedIn": links.get("LinkedIn", ""),
                "Twitter": links.get("Twitter", ""),
                "YouTube": links.get("YouTube", "")
            })

        # ---------- NEXT PAGE ----------
        try:
            next_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "li.v-pagination__next button:not([disabled])")
            ))
            driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
            time.sleep(1)
            actions.move_to_element(next_btn).click().perform()
            page += 1
            time.sleep(4)
        except:
            print("✅ No more pages found — scraping complete.")
            break

    except Exception as e:
        print(f"⚠️ Error on page {page}: {e}")
        break

# ---------- SAVE ----------
df = pd.DataFrame(exhibitors)
df.to_excel("adihex_exhibitors.xlsx", index=False)
print(f"✅ Scraping finished: {len(df)} exhibitors saved to 'adihex_exhibitors.xlsx'.")

driver.quit()
