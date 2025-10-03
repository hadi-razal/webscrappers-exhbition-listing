from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import time


def scrape_with_selenium():

    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    
    companies = []
    booth_numbers = []
    countries = []
    linkedin_urls = []
    
    try:
        # Navigate to the page
        print("Loading page...")
        driver.get("https://www.middleeast-energy.com/en/exhibit/exhibitor-directory.html")
        
        # Wait for iframe to load
        wait = WebDriverWait(driver, 20)
        
        # Switch to iframe if present
        try:
            iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
            driver.switch_to.frame(iframe)
            print("Switched to iframe")
        except:
            print("No iframe found, continuing with main page")
        
        # Wait for exhibitor data to load
        time.sleep(5)
        
        # Scroll to load all exhibitors (if infinite scroll)
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        # Find all exhibitor cards
        exhibitor_cards = driver.find_elements(By.CSS_SELECTOR, "[class*='sc-'][class*='exhibitor'], [class*='sc-'][class*='company']")
        
        print(f"Found {len(exhibitor_cards)} potential exhibitor cards")
        
        for card in exhibitor_cards:
            try:
                # Company name
                company_name = None
                for selector in ["span.hbcoOt", "span.bhjVsd", "[class*='sc-'][class*='title']", "h2", "h3"]:
                    try:
                        elem = card.find_element(By.CSS_SELECTOR, selector)
                        company_name = elem.text.strip()
                        if company_name:
                            break
                    except:
                        continue
                
                if not company_name:
                    continue
                
                companies.append(company_name)
                
                # Booth number
                booth = "N/A"
                for selector in ["span.gZlljB", "span.eBoPmB", "[class*='booth']", "[class*='stand']"]:
                    try:
                        elem = card.find_element(By.CSS_SELECTOR, selector)
                        booth = elem.text.strip()
                        if booth:
                            break
                    except:
                        continue
                booth_numbers.append(booth)
                
                # Country
                country = "N/A"
                try:
                    country_label = card.find_element(By.XPATH, ".//*[contains(text(), 'Country')]")
                    country_elem = country_label.find_element(By.XPATH, "./following-sibling::*[1]")
                    country = country_elem.text.strip()
                except:
                    pass
                countries.append(country)
                
                # LinkedIn
                linkedin = "N/A"
                try:
                    linkedin_elem = card.find_element(By.CSS_SELECTOR, "a[href*='linkedin.com']")
                    linkedin = linkedin_elem.get_attribute('href')
                except:
                    pass
                linkedin_urls.append(linkedin)
                
            except Exception as e:
                continue
        
    finally:
        driver.quit()
    
    # Create DataFrame
    if companies:
        df = pd.DataFrame({
            'Company Name': companies,
            'Booth Number': booth_numbers,
            'Country': countries,
            'LinkedIn URL': linkedin_urls
        })
        return df
    return None

# Run the Selenium scraper
if __name__ == "__main__":
    print("Note: This script requires ChromeDriver to be installed.")
    print("Download from: https://chromedriver.chromium.org/")
    
    df = scrape_with_selenium()
    if df is not None:
        df.to_excel('middle_east_energy_exhibitors_selenium.xlsx', index=False)
        print(f"Extracted {len(df)} exhibitors")