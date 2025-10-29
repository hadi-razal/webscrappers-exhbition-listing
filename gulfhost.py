from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time, logging

logging.basicConfig(
    filename="gulfhost_scrape_log.txt",
    filemode="w",
    format="%(asctime)s - %(message)s",
    level=logging.INFO
)
def log(msg):
    print(msg)
    logging.info(msg)

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 25)

url = "https://www.gulfhost.ae/exhibitors-2024"
driver.get(url)
time.sleep(5)

exhibitors = []
page = 1

while True:
    log(f"\n📄 Scraping Page {page} ...")

    # Wait for exhibitor list (NOT footer)
    retry = 0
    while retry < 3:
        try:
            wait.until(EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "div.m-exhibitors-list__list__items a.js-librarylink-entry")))
            break
        except:
            retry += 1
            log(f"⏳ Waiting for exhibitors to load (retry {retry}/3)...")
            time.sleep(3)
    else:
        log("❌ Exhibitors not loaded after retries — skipping page.")
        break

    # Find only exhibitors (ignore sponsors / media)
    links = driver.find_elements(By.CSS_SELECTOR,
        "div.m-exhibitors-list__list__items a.js-librarylink-entry")
    total = len(links)
    log(f"🔍 Found {total} exhibitors on this page")

    for i in range(total):
        try:
            link = driver.find_elements(By.CSS_SELECTOR,
                "div.m-exhibitors-list__list__items a.js-librarylink-entry")[i]
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", link)
            time.sleep(0.8)

            driver.execute_script("arguments[0].click();", link)
            wait.until(EC.visibility_of_element_located(
                (By.CSS_SELECTOR, ".m-exhibitor-entry__item__header__title")))
            time.sleep(0.8)

            def safe_text(sel):
                try:
                    return driver.find_element(By.CSS_SELECTOR, sel).text.strip()
                except:
                    return ""

            def safe_attr(sel, attr):
                try:
                    return driver.find_element(By.CSS_SELECTOR, sel).get_attribute(attr).strip()
                except:
                    return ""

            name = safe_text(".m-exhibitor-entry__item__header__title")
            hall_stand = safe_text(".m-exhibitor-entry__item__header__stand")
            hall, stand = "", ""
            if "Hall:" in hall_stand:
                parts = hall_stand.split("Stand:")
                hall = parts[0].replace("Hall:", "").strip() if len(parts) > 0 else ""
                stand = parts[1].strip() if len(parts) > 1 else ""

            addr, country = "", ""
            try:
                addr_text = driver.find_element(By.CSS_SELECTOR,
                    ".m-exhibitor-entry__item__body__content__overview__contacts__address").text.strip()
                lines = [x.strip() for x in addr_text.split("\n") if x.strip()]
                if len(lines) > 1:
                    addr = " ".join(lines[:-1])
                    country = lines[-1]
                else:
                    addr = addr_text
            except:
                pass

            website = safe_attr("a.w-button__button", "href")

            socials = {"LinkedIn": "", "Facebook": "", "Instagram": "", "Twitter": "", "YouTube": ""}
            for s in driver.find_elements(By.CSS_SELECTOR,
                "ul.m-exhibitor-entry__item__body__content__overview__contacts__additional__social li a"):
                href = s.get_attribute("href")
                if not href:
                    continue
                if "linkedin" in href:
                    socials["LinkedIn"] = href
                elif "facebook" in href:
                    socials["Facebook"] = href
                elif "instagram" in href:
                    socials["Instagram"] = href
                elif "twitter" in href or "x.com" in href:
                    socials["Twitter"] = href
                elif "youtube" in href:
                    socials["YouTube"] = href

            log(f"\n➡️ {i+1}/{total} | {name}")
            log(f"   🏛 Hall: {hall}")
            log(f"   🎯 Stand: {stand}")
            log(f"   📍 Address: {addr}")
            log(f"   🌍 Country: {country}")
            log(f"   🌐 Website: {website}")
            for k, v in socials.items():
                if v:
                    log(f"   🔗 {k}: {v}")

            exhibitors.append({
                "Name": name,
                "Hall": hall,
                "Stand": stand,
                "Address": addr,
                "Country": country,
                "Website": website,
                "LinkedIn": socials["LinkedIn"],
                "Facebook": socials["Facebook"],
                "Instagram": socials["Instagram"],
                "Twitter": socials["Twitter"],
                "YouTube": socials["YouTube"]
            })

            log(f"✅ Saved: {name}")

            try:
                driver.find_element(By.CSS_SELECTOR, "button.mfp-close").click()
            except:
                driver.execute_script("document.querySelector('button.mfp-close').click();")
            time.sleep(1.2)

            driver.execute_script("""
                const el = arguments[0];
                const bottom = el.getBoundingClientRect().bottom + window.scrollY;
                window.scrollTo({ top: bottom + 100, behavior: 'smooth' });
            """, link)
            time.sleep(0.7)

        except Exception as e:
            log(f"⚠️ Error on exhibitor {i+1}: {e}")
            try:
                driver.execute_script("document.querySelector('button.mfp-close').click();")
            except:
                pass
            time.sleep(1)
            continue

    # Next page
    try:
        next_btn = driver.find_element(By.CSS_SELECTOR, ".w-module-pagination__list__item--next a[element='next']")
        next_link = next_btn.get_attribute("href")
        if not next_link:
            log("✅ No next page found — scraping complete.")
            break

        log(f"\n➡️ Moving to next page: {next_link}")
        driver.get("https://www.gulfhost.ae/" + next_link)
        page += 1
        time.sleep(5)
    except:
        log("✅ No more pages — finished.")
        break

df = pd.DataFrame(exhibitors)
df.to_excel("gulfhost_exhibitors_clean.xlsx", index=False)
log(f"\n🎉 Done! {len(df)} exhibitors saved to 'gulfhost_exhibitors_clean.xlsx'.")
driver.quit()
