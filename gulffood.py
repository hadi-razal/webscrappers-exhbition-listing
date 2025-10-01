from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import csv

# --- Setup ---
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

base_url = "https://www.gulfood.com/exhibitor-list?page={}&sortby=title asc,title asc&azLetterField="

# --- Output CSV ---
csv_file = open("gulfood_exhibitors.csv", "w", newline="", encoding="utf-8")
writer = csv.writer(csv_file)
writer.writerow([
    "Name",
    "Country", 
    "Full Address",
    "Hall & Stand",
    "Floorplan Link",
    "Website",
    "LinkedIn",
    "Facebook",
    "Instagram",
    "YouTube"
])

# --- Loop through pages ---
for page in range(1, 152):  # 1 → 151
    print(f"\n📄 Scraping page {page}...")
    driver.get(base_url.format(page))
    time.sleep(3)  # let page load

    # Find all exhibitor items
    exhibitors = driver.find_elements(By.CSS_SELECTOR, "li.m-exhibitors-list__items__item")
    print(f"Found {len(exhibitors)} exhibitors on page {page}")

    for index, exhibitor in enumerate(exhibitors):
        try:
            # --- Extract basic info from list ---
            name_elem = exhibitor.find_element(By.CSS_SELECTOR, ".m-exhibitors-list__items__item__name")
            name = name_elem.text.strip()
            
            try:
                hall = exhibitor.find_element(By.CSS_SELECTOR, ".m-exhibitors-list__items__item__hall").text.strip()
            except NoSuchElementException:
                hall = ""
                
            try:
                stand = exhibitor.find_element(By.CSS_SELECTOR, ".m-exhibitors-list__items__item__stand").text.strip()
            except NoSuchElementException:
                stand = ""
                
            try:
                location_country = exhibitor.find_element(By.CSS_SELECTOR, ".m-exhibitors-list__items__item__location").text.strip()
            except NoSuchElementException:
                location_country = ""

            hall_stand = f"{hall} | {stand}" if hall and stand else f"{hall}{stand}"

            print(f"Processing {index + 1}/{len(exhibitors)}: {name}")

            # --- Click to open modal ---
            name_link = exhibitor.find_element(By.CSS_SELECTOR, ".m-exhibitors-list__items__item__name__link")
            driver.execute_script("arguments[0].click();", name_link)

            # Wait for modal to load
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.m-exhibitor-entry__item__body"))
            )

            # --- Extract data from modal ---
            modal_name = ""
            modal_hall_stand = ""
            full_address = ""
            floorplan_link = ""
            website = ""
            linkedin = ""
            facebook = ""
            instagram = ""
            youtube = ""

            # Get name from modal
            try:
                modal_name = driver.find_element(By.CSS_SELECTOR, "h1.m-exhibitor-entry__item__header__infos__title").text.strip()
            except NoSuchElementException:
                modal_name = name  # fallback to list name

            # Get hall and stand from modal
            try:
                modal_hall_stand_elem = driver.find_element(By.CSS_SELECTOR, ".m-exhibitor-entry__item__header__infos__stand")
                modal_hall_stand = modal_hall_stand_elem.text.strip()
            except NoSuchElementException:
                modal_hall_stand = hall_stand  # fallback to list hall_stand

            # Get address
            try:
                address_elem = driver.find_element(By.CSS_SELECTOR, ".m-exhibitor-entry__item__body__contacts__address")
                # Get all text, skip the "Address" header
                address_lines = address_elem.find_elements(By.TAG_NAME, "br")
                if address_lines:
                    full_address = address_elem.text.replace("Address", "").strip()
            except NoSuchElementException:
                pass

            # Get floorplan link
            try:
                floorplan_elem = driver.find_element(By.CSS_SELECTOR, ".m-exhibitor-entry__item__body__contacts__additional__button__additional-field a")
                floorplan_link = floorplan_elem.get_attribute("href")
            except NoSuchElementException:
                pass

            # Get website
            try:
                website_elem = driver.find_element(By.CSS_SELECTOR, ".m-exhibitor-entry__item__body__contacts__additional__button__website a")
                website = website_elem.get_attribute("href")
            except NoSuchElementException:
                pass

            # Get social media links
            try:
                social_items = driver.find_elements(By.CSS_SELECTOR, ".m-exhibitor-entry__item__body__contacts__additional__social__item a")
                for social_item in social_items:
                    href = social_item.get_attribute("href")
                    if "linkedin.com" in href:
                        linkedin = href
                    elif "facebook.com" in href:
                        facebook = href
                    elif "instagram.com" in href:
                        instagram = href
                    elif "youtube.com" in href or "youtu.be" in href:
                        youtube = href
            except NoSuchElementException:
                pass

            # --- Save row ---
            writer.writerow([
                modal_name,
                location_country,
                full_address,
                modal_hall_stand,
                floorplan_link,
                website,
                linkedin,
                facebook,
                instagram,
                youtube
            ])

            # --- Console log ---
            print(f"✅ {modal_name}")
            print(f"   Country: {location_country}")
            print(f"   Hall & Stand: {modal_hall_stand}")
            print(f"   Address: {full_address}")
            print(f"   Floorplan: {floorplan_link}")
            print(f"   Website: {website}")
            print(f"   LinkedIn: {linkedin}")
            print(f"   Facebook: {facebook}")
            print(f"   Instagram: {instagram}")
            print(f"   YouTube: {youtube}")

            # --- Close modal ---
            try:
                close_btn = driver.find_element(By.CSS_SELECTOR, ".mfp-close")
                driver.execute_script("arguments[0].click();", close_btn)
                time.sleep(1)  # wait for modal to close
            except NoSuchElementException:
                # If close button not found, try ESC key or click outside
                driver.execute_script("document.activeElement.blur();")
                time.sleep(1)

        except Exception as e:
            print(f"❌ Error on exhibitor {index + 1}: {str(e)}")
            # Try to close modal if it's open
            try:
                close_btn = driver.find_element(By.CSS_SELECTOR, ".mfp-close")
                driver.execute_script("arguments[0].click();", close_btn)
                time.sleep(1)
            except:
                pass
            continue

    print(f"✅ Completed page {page}")

csv_file.close()
driver.quit()
print("\n🎉 Scraping completed! Data saved to gulfood_exhibitors.csv")