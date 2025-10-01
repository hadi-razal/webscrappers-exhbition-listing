import requests
from bs4 import BeautifulSoup
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import re
import json

class WHXExhibitorScraper:
    def __init__(self, headless=False):
        self.base_url = "https://www.worldhealthexpo.com/events/labs/dubai/en/attend/exhibitor-list.html"
        self.driver = None
        self.setup_driver(headless)
        
    def setup_driver(self, headless=False):
        """Setup Chrome driver"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        chrome_options.add_argument("--window-size=1920,1080")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def wait_for_exhibitor_widget(self):
        """Wait for the exhibitor widget to load"""
        print("⏳ Waiting for exhibitor widget to load...")
        
        # Wait for the iframe to be present
        try:
            wait = WebDriverWait(self.driver, 30)
            iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
            print("✅ Iframe found")
            
            # Switch to the iframe
            self.driver.switch_to.frame(iframe)
            print("✅ Switched to iframe")
            
            # Wait for exhibitor content inside iframe
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='exhibitor'], [class*='card'], .sc-")))
            print("✅ Exhibitor content loaded inside iframe")
            return True
            
        except TimeoutException:
            print("❌ Timeout waiting for exhibitor widget")
            return False
    
    def infinite_scroll_until_end(self):
        """Scroll until all exhibitors are loaded"""
        print("📜 Starting infinite scroll...")
        
        last_count = 0
        same_count_iterations = 0
        max_iterations = 20
        
        for i in range(max_iterations):
            # Get current number of exhibitor elements
            exhibitor_elements = self.driver.find_elements(By.CSS_SELECTOR, "[class*='exhibitor'], [class*='card'], .sc-")
            current_count = len(exhibitor_elements)
            
            print(f"🔄 Iteration {i+1}: Found {current_count} exhibitors")
            
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # Check if new content loaded
            new_exhibitor_elements = self.driver.find_elements(By.CSS_SELECTOR, "[class*='exhibitor'], [class*='card'], .sc-")
            new_count = len(new_exhibitor_elements)
            
            if new_count == current_count:
                same_count_iterations += 1
                print(f"📊 No new exhibitors loaded ({same_count_iterations}/3)")
            else:
                same_count_iterations = 0
                print(f"🎯 New exhibitors loaded: {new_count - current_count}")
            
            # Stop if no new content after 3 iterations
            if same_count_iterations >= 3:
                print("✅ All exhibitors loaded - no new content")
                break
            
            # Stop if we've reached maximum iterations
            if i == max_iterations - 1:
                print("⚠️  Reached maximum scroll iterations")
        
        final_count = len(self.driver.find_elements(By.CSS_SELECTOR, "[class*='exhibitor'], [class*='card'], .sc-"))
        print(f"🎉 Finished scrolling. Total exhibitors found: {final_count}")
        return final_count
    
    def extract_exhibitor_data_from_list(self):
        """Extract exhibitor data directly from the list without clicking"""
        print("🔍 Extracting exhibitor data from list...")
        
        exhibitors_data = []
        
        # Find all exhibitor cards
        exhibitor_cards = self.driver.find_elements(By.CSS_SELECTOR, "[class*='exhibitor'], [class*='card'], .sc-")
        print(f"📋 Found {len(exhibitor_cards)} exhibitor cards")
        
        for i, card in enumerate(exhibitor_cards):
            try:
                print(f"\n📊 Processing exhibitor {i+1}/{len(exhibitor_cards)}")
                
                # Get the card HTML
                card_html = card.get_attribute('outerHTML')
                soup = BeautifulSoup(card_html, 'html.parser')
                
                # Extract company name
                company_name = "N/A"
                name_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div'])
                for elem in name_elements:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 2 and len(text) < 100:  # Reasonable name length
                        # Skip booth numbers and other metadata
                        if not re.match(r'[A-Z]\d+\.?[A-Z]?\d*', text) and not re.match(r'^\d+$', text):
                            company_name = text
                            break
                
                # Extract booth number
                booth_number = "N/A"
                booth_elements = soup.find_all(string=re.compile(r'[A-Z]\d+\.?[A-Z]?\d*'))
                for elem in booth_elements:
                    booth_match = re.search(r'[A-Z]\d+\.?[A-Z]?\d*', elem)
                    if booth_match:
                        booth_number = booth_match.group()
                        break
                
                # Try to find LinkedIn in the card
                linkedin = "N/A"
                linkedin_links = soup.find_all('a', href=re.compile(r'linkedin\.com', re.I))
                for link in linkedin_links:
                    href = link.get('href', '')
                    if 'linkedin' in href.lower():
                        linkedin = href
                        break
                
                # Console log the data
                print(f"📋 EXHIBITOR DATA:")
                print(f"   🏢 Company: {company_name}")
                print(f"   📍 Booth: {booth_number}")
                print(f"   💼 LinkedIn: {linkedin}")
                print("   " + "="*40)
                
                exhibitors_data.append({
                    'company_name': company_name,
                    'booth_number': booth_number,
                    'linkedin': linkedin,
                    'email': 'N/A',  # Not available in list view
                    'phone': 'N/A'   # Not available in list view
                })
                
            except Exception as e:
                print(f"❌ Error processing exhibitor {i+1}: {str(e)}")
                continue
        
        return exhibitors_data
    
    def click_and_extract_detailed_info(self, card_element):
        """Click on exhibitor card and extract detailed information"""
        try:
            # Click on the card
            self.driver.execute_script("arguments[0].click();", card_element)
            time.sleep(3)
            
            # Now we should be on the detail page
            detail_html = self.driver.page_source
            detail_soup = BeautifulSoup(detail_html, 'html.parser')
            
            # Extract detailed information
            company_name = "N/A"
            booth_number = "N/A"
            linkedin = "N/A"
            email = "N/A"
            phone = "N/A"
            
            # Extract company name from detail page
            name_elements = detail_soup.find_all(['h1', 'h2'])
            for elem in name_elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 2:
                    company_name = text
                    break
            
            # Extract booth number
            booth_elements = detail_soup.find_all(string=re.compile(r'[A-Z]\d+\.?[A-Z]?\d*'))
            for elem in booth_elements:
                booth_match = re.search(r'[A-Z]\d+\.?[A-Z]?\d*', elem)
                if booth_match:
                    booth_number = booth_match.group()
                    break
            
            # Extract LinkedIn
            linkedin_links = detail_soup.find_all('a', href=re.compile(r'linkedin\.com', re.I))
            for link in linkedin_links:
                href = link.get('href', '')
                if 'linkedin' in href.lower():
                    linkedin = href
                    break
            
            # Extract email
            email_links = detail_soup.find_all('a', href=re.compile(r'mailto:', re.I))
            if email_links:
                email = email_links[0]['href'].replace('mailto:', '')
            
            # Extract phone
            phone_pattern = r'[\+\(]?[1-9][0-9\-\(\)\s]{8,}'
            phone_matches = re.findall(phone_pattern, detail_soup.get_text())
            for match in phone_matches:
                clean_match = match.strip()
                if len(clean_match.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')) >= 8:
                    phone = clean_match
                    break
            
            # Go back to list
            self.driver.execute_script("window.history.back();")
            time.sleep(2)
            
            return {
                'company_name': company_name,
                'booth_number': booth_number,
                'linkedin': linkedin,
                'email': email,
                'phone': phone
            }
            
        except Exception as e:
            print(f"❌ Error extracting detailed info: {str(e)}")
            # Try to go back if we're stuck
            try:
                self.driver.execute_script("window.history.back();")
                time.sleep(2)
            except:
                pass
            return None
    
    def scrape_all_exhibitors(self):
        """Main method to scrape all exhibitors"""
        print("🚀 Starting WHX Labs Dubai exhibitor scraping...")
        
        try:
            # Navigate to the page
            self.driver.get(self.base_url)
            time.sleep(5)
            
            # Wait for and switch to exhibitor widget
            if not self.wait_for_exhibitor_widget():
                print("❌ Failed to load exhibitor widget")
                return []
            
            # Perform infinite scroll to load all exhibitors
            total_exhibitors = self.infinite_scroll_until_end()
            
            if total_exhibitors == 0:
                print("❌ No exhibitors found after scrolling")
                return []
            
            # Extract data from the list view (faster, less detailed)
            print("\n🎯 Extracting exhibitor data from list view...")
            exhibitors_data = self.extract_exhibitor_data_from_list()
            
            # If we want more detailed info, we can click each card (slower)
            # Uncomment below if you need email and phone numbers
            """
            print("\n🎯 Extracting detailed information by clicking each card...")
            detailed_exhibitors_data = []
            exhibitor_cards = self.driver.find_elements(By.CSS_SELECTOR, "[class*='exhibitor'], [class*='card'], .sc-")
            
            for i, card in enumerate(exhibitor_cards):
                print(f"\n🔍 Clicking exhibitor {i+1}/{len(exhibitor_cards)} for details...")
                detailed_data = self.click_and_extract_detailed_info(card)
                if detailed_data:
                    detailed_exhibitors_data.append(detailed_data)
                time.sleep(1)
            
            exhibitors_data = detailed_exhibitors_data
            """
            
            return exhibitors_data
            
        except Exception as e:
            print(f"❌ Error during scraping: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            # Switch back to main content
            try:
                self.driver.switch_to.default_content()
            except:
                pass
    
    def save_to_excel(self, exhibitors_data, filename="whx_labs_dubai_exhibitors.xlsx"):
        """Save scraped data to Excel file"""
        if not exhibitors_data:
            print("❌ No data to save")
            return
            
        df = pd.DataFrame(exhibitors_data)
        
        # Reorder columns
        column_order = ['company_name', 'booth_number', 'linkedin', 'email', 'phone']
        df = df[column_order]
        
        df.to_excel(filename, index=False, engine='openpyxl')
        print(f"\n💾 Data saved to {filename}")
        
        # Print summary
        self.print_summary(df)
        
        # Also save as CSV
        csv_filename = filename.replace('.xlsx', '.csv')
        df.to_csv(csv_filename, index=False)
        print(f"💾 Data also saved to {csv_filename}")
    
    def print_summary(self, df):
        """Print summary of scraped data"""
        print(f"\n📊 SCRAPING SUMMARY:")
        print(f"   ✅ Total exhibitors: {len(df)}")
        print(f"   💼 With LinkedIn: {len(df[df['linkedin'] != 'N/A'])}")
        print(f"   📧 With Email: {len(df[df['email'] != 'N/A'])}")
        print(f"   📞 With Phone: {len(df[df['phone'] != 'N/A'])}")
        
        # Show first few results
        print(f"\n📋 FIRST 5 EXHIBITORS:")
        for i, row in df.head().iterrows():
            print(f"   {i+1}. {row['company_name']} - Booth: {row['booth_number']}")
    
    def close(self):
        """Close the browser driver"""
        if self.driver:
            self.driver.quit()

def main():
    scraper = None
    try:
        # Initialize scraper with visible browser
        scraper = WHXExhibitorScraper(headless=False)
        
        # Scrape all exhibitors
        exhibitors_data = scraper.scrape_all_exhibitors()
        
        if exhibitors_data:
            # Save to Excel
            scraper.save_to_excel(exhibitors_data)
            print(f"\n🎉 Successfully scraped {len(exhibitors_data)} exhibitors!")
        else:
            print("❌ No exhibitor data was scraped")
            
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        if scraper:
            scraper.close()
            print("🔚 Browser closed")

if __name__ == "__main__":
    main()