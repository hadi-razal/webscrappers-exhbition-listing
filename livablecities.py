from selenium import webdriver
from selenium.webdriver.common.by import By
import pandas as pd
import time

# =============================
# ⚙️ SETUP
# =============================
URL = "https://exhibitors.liveablecitiesx.com/liveable-citiesx-2025/Exhibitor"

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--disable-gpu")
# options.add_argument("--headless=new")

driver = webdriver.Chrome(options=options)
driver.get(URL)
time.sleep(3)


# =============================
# 🍪 CLOSE COOKIE POPUP
# =============================
def close_cookie_banner():
    try:
        time.sleep(1)
        driver.execute_script("""
            var el = document.querySelector('.onetrust-pc-dark-filter');
            if (el) el.style.display = 'none';
            var ot = document.querySelector('#onetrust-banner-sdk');
            if (ot) ot.style.display = 'none';
        """)
        print("🍪 Cookie banner hidden.")
    except Exception as e:
        print("⚠️ Cookie banner not found:", e)


close_cookie_banner()
time.sleep(1)


# =============================
# 🧭 SCRAPE FUNCTION
# =============================
def scrape_exhibitor(link):
    """Open exhibitor link in new tab, scrape, close tab"""
    driver.execute_script("window.open(arguments[0], '_blank');", link)
    driver.switch_to.window(driver.window_handles[-1])
    time.sleep(1.3)

    data = {}
    try:
        data["Company Name"] = driver.find_element(By.CSS_SELECTOR, "h1.company-title").text.strip()
    except:
        data["Company Name"] = ""

    try:
        h6_tags = driver.find_elements(By.CSS_SELECTOR, "h6")
        data["Stand Number"] = h6_tags[0].text.strip() if len(h6_tags) > 0 else ""
        data["Country"] = h6_tags[1].text.strip() if len(h6_tags) > 1 else ""
    except:
        data["Stand Number"] = ""
        data["Country"] = ""

    try:
        data["Website"] = driver.find_element(By.CSS_SELECTOR, ".fa-globe + a").get_attribute("href")
    except:
        data["Website"] = ""

    try:
        links = driver.find_elements(By.CSS_SELECTOR, ".social-links a")
        linkedin = [a.get_attribute("href") for a in links if "linkedin.com" in a.get_attribute("href")]
        data["LinkedIn"] = linkedin[0] if linkedin else ""
    except:
        data["LinkedIn"] = ""

    try:
        data["Logo URL"] = driver.find_element(By.CSS_SELECTOR, ".logo-holder img").get_attribute("src")
    except:
        data["Logo URL"] = ""

    data["Page URL"] = link

    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    return data



results = []
offset = 0
page = 1
seen_links = set()

while True:
    print(f"\n📄 Scraping page {page} (offset={offset})")
    time.sleep(2)

    cards = driver.find_elements(By.CSS_SELECTOR, ".card.h-100 a")
    links = [a.get_attribute("href") for a in cards if a.get_attribute("href")]
    links = list(dict.fromkeys(links))  # remove duplicates

    if not links:
        print("⚠️ No exhibitor links found — stopping.")
        break

    for idx, link in enumerate(links, start=1):
        if link in seen_links:
            continue
        seen_links.add(link)
        print(f"  🔹 [{idx}/{len(links)}] {link}")
        try:
            data = scrape_exhibitor(link)
            results.append(data)
            print(f"     ✅ {data['Company Name']}")
        except Exception as e:
            print(f"     ❌ Error on {link}: {e}")
            driver.switch_to.window(driver.window_handles[0])


    offset += 24  # each page shows 24 cards
    prev_count = len(results)

    driver.execute_script("searchFilter(arguments[0]);", offset)
    time.sleep(3)

  
    new_cards = driver.find_elements(By.CSS_SELECTOR, ".card.h-100 a")
    new_links = [a.get_attribute("href") for a in new_cards if a.get_attribute("href")]
    if not new_links or all(link in seen_links for link in new_links):
        print("✅ No new exhibitors found — finished.")
        break

    page += 1


df = pd.DataFrame(results)
df.to_excel("liveable_citiesx_exhibitors_unique.xlsx", index=False)
print(f"\n💾 Done! {len(results)} unique exhibitors saved to liveable_citiesx_exhibitors_unique.xlsx")

driver.quit()
