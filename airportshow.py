# pip install selenium pandas openpyxl
import time, pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

URL = "https://www.theairportshow.com/en-gb/exhibitor-directory.html#/"

opts = webdriver.ChromeOptions()
opts.add_argument("--start-maximized")
# opts.add_argument("--headless=new")  # optional
driver = webdriver.Chrome(options=opts)
wait = WebDriverWait(driver, 30)

driver.get(URL)
wait.until(EC.presence_of_all_elements_located(
    (By.CSS_SELECTOR, "div.directory-item-feature-toggled.exhibitor-category")))

# -------------------------------
# STEP 1: AUTO SCROLL UNTIL END
# -------------------------------
print("🔄 Scrolling to load all exhibitors...")
prev_count = 0
stable_rounds = 0
max_wait_rounds = 15  # ~30 seconds max idle wait

while stable_rounds < max_wait_rounds:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    cards = driver.find_elements(By.CSS_SELECTOR,
                                 "div.directory-item-feature-toggled.exhibitor-category")
    curr_count = len(cards)
    print(f"Currently loaded: {curr_count}")

    if curr_count == prev_count:
        stable_rounds += 1
    else:
        stable_rounds = 0
        prev_count = curr_count

print(f"✅ All exhibitors loaded: {len(cards)} total")

# -------------------------------
# STEP 2: SCRAPE EACH CARD
# -------------------------------
exhibitors = []

for idx, card in enumerate(cards, start=1):
    try:
        name_el = card.find_element(By.CSS_SELECTOR, "h3.exhibitor-name")
        company = name_el.text.strip()
        print(f"{idx}/{len(cards)} → {company}")

        logo = ""
        try:
            logo = card.find_element(By.CSS_SELECTOR, "div.profile-logo img").get_attribute("src")
        except Exception:
            pass

        stand = ""
        try:
            stand = card.find_element(By.CSS_SELECTOR, ".directory-stand span:last-child").text.strip()
        except Exception:
            pass

        link = name_el.find_element(By.XPATH, "./ancestor::a").get_attribute("href")

        # open detail page in new tab
        driver.execute_script("window.open(arguments[0], '_blank');", link)
        driver.switch_to.window(driver.window_handles[1])
        time.sleep(2)

        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "main, body")))

        def safe(sel):
            try:
                return driver.find_element(By.CSS_SELECTOR, sel).text.strip()
            except Exception:
                return ""

        description = safe("div[data-testid='exh-content']")
        country = safe("div[data-testid='exh-country'], span.exhibitor-country")

        # ----- CONTACTS -----
        website, email, phone = "", "", ""
        try:
            links = driver.find_elements(By.CSS_SELECTOR, "div.exhibitor-details-contact-us-links a")
            for a in links:
                href = a.get_attribute("href") or ""
                if href.startswith("mailto:"):
                    email = href.replace("mailto:", "")
                elif href.startswith("tel:"):
                    phone = href.replace("tel:", "")
                elif href.startswith("http") and "linkedin" not in href:
                    website = href
        except Exception:
            pass

        # ----- SOCIAL MEDIA -----
        linkedin = facebook = instagram = youtube = twitter = ""
        try:
            social_links = driver.find_elements(By.CSS_SELECTOR, "div.social-media-logo-container a")
            for s in social_links:
                href = s.get_attribute("href") or ""
                lower = href.lower()
                if "linkedin" in lower:
                    linkedin = href
                elif "facebook" in lower:
                    facebook = href
                elif "instagram" in lower:
                    instagram = href
                elif "youtube" in lower:
                    youtube = href
                elif "twitter" in lower or "x.com" in lower:
                    twitter = href
        except Exception:
            pass

        exhibitors.append({
            "Company": company,
            "Country": country,
            "Stand": stand,
            "Description": description,
            "Logo": logo,
            "Website": website,
            "Email": email,
            "Phone": phone,
            "LinkedIn": linkedin,
            "Facebook": facebook,
            "Instagram": instagram,
            "YouTube": youtube,
            "Twitter": twitter
        })

        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        time.sleep(1)

    except Exception as e:
        print(f"⚠️ Error on {idx}: {e}")
        try:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass

# -------------------------------
# STEP 3: SAVE RESULTS
# -------------------------------
driver.quit()
df = pd.DataFrame(exhibitors)
df.to_excel("airport_show_exhibitors_full.xlsx", index=False)
print(f"✅ Done! {len(exhibitors)} exhibitors saved → airport_show_exhibitors_full.xlsx")
