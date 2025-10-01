import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# Setup Chrome driver
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

url = "https://www.worldhealthexpo.com/events/healthcare/dubai/en/attend/exhibitor-list.html"
driver.get(url)

wait = WebDriverWait(driver, 20)

# Scroll to load all exhibitors
last_height = driver.execute_script("return document.body.scrollHeight")
while True:
    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
    time.sleep(2)
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
        break
    last_height = new_height

time.sleep(3)

# Get all exhibitor cards
cards = driver.find_elements(By.CSS_SELECTOR, "div.sc-8084dcd8-3.fGEabZ")

data = []

for i in range(len(cards)):
    # Re-find all cards (important after going back)
    cards = driver.find_elements(By.CSS_SELECTOR, "div.sc-8084dcd8-3.fGEabZ")
    card = cards[i]

    # Scroll into view
    ActionChains(driver).move_to_element(card).perform()
    driver.execute_script("arguments[0].scrollIntoView(true);", card)
    time.sleep(1)

    # Click on the card
    driver.execute_script("arguments[0].click();", card)

    # Wait for company name to load
    try:
        name = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.sc-5973f5f6-7.iSomte"))).text
    except:
        name = ""

    try:
        booth = driver.find_element(By.CSS_SELECTOR, "span.sc-29cfb1f4-0.hLjPHn").text
    except:
        booth = ""

    try:
        country = driver.find_element(By.CSS_SELECTOR, "span.sc-533e02b7-0.giUkut").text
    except:
        country = ""

    linkedin = ""
    try:
        social_links = driver.find_elements(By.CSS_SELECTOR, "div.sc-3d1aa370-15.faAOrn a")
        for link in social_links:
            href = link.get_attribute("href")
            if "linkedin.com" in href:
                linkedin = href
                break
    except:
        pass

    data.append({
        "Company": name,
        "Booth": booth,
        "Country": country,
        "LinkedIn": linkedin
    })

    print(f"Scraped: {name}, {booth}, {country}, {linkedin}")

    # Go back to exhibitor list
    driver.back()
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.sc-8084dcd8-3.fGEabZ")))
    time.sleep(2)

# Save to Excel
df = pd.DataFrame(data)
df.to_excel("exhibitors_list.xlsx", index=False)

driver.quit()
print("Scraping complete! Data saved to exhibitors_list.xlsx")
