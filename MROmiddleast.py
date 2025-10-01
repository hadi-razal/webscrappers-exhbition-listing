from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# --- Setup driver ---
driver = webdriver.Chrome()
driver.get("https://mromiddleeast.aviationweek.com/en/exhibition/exhibitor-list.html")
wait = WebDriverWait(driver, 20)

# --- Locate scrollable element ---
scrollable = wait.until(EC.presence_of_element_located(
    (By.CSS_SELECTOR, "div.MuiPaper-root.MuiPaper-outlined.MuiPaper-rounded.css-8rt01o[data-testid='marketplaceBlock']")
))

# --- Scroll helper ---
def scroll_element(el, driver, direction="down"):
    if direction == "down":
        driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", el)
    elif direction == "up":
        driver.execute_script("arguments[0].scrollTo(0, 0);", el)
    time.sleep(2)  # wait for content to load

# --- Scroll sequence ---
scroll_element(scrollable, driver, "down")
scroll_element(scrollable, driver, "up")
scroll_element(scrollable, driver, "down")

print("Finished scrolling container!")
