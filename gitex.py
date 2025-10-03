import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import re

class GitexExhibitorScraper:
    def __init__(self):
        self.setup_driver()
        self.all_data = []
        
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 15)
        
    def scroll_to_load_all_exhibitors(self):
        """Scroll to bottom to trigger infinite scroll loading until all items are loaded"""
        print("🔄 Starting infinite scroll to load all exhibitors...")
        last_count = 0
        no_new_items_count = 0
        
        while True:
            # Scroll down to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Get current count of exhibitors
            current_exhibitors = self.driver.find_elements(By.CSS_SELECTOR, "div.item.col-12.list-group-item")
            current_count = len(current_exhibitors)
            
            print(f"📊 Loaded {current_count} exhibitors...")
            
            # Check if we're still loading new items
            if current_count == last_count:
                no_new_items_count += 1
                if no_new_items_count >= 3:  # If no new items after 3 scrolls, stop
                    print("✅ All exhibitors loaded!")
                    break
            else:
                no_new_items_count = 0
                last_count = current_count
            
            # Safety limit to prevent infinite loop
            if current_count > 1000:
                print("⚠️ Reached safety limit of 1000 exhibitors")
                break
    
    def scroll_to_element(self, element):
        """Scroll to a specific element to ensure it's in view"""
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            time.sleep(0.5)  # Wait for scroll to complete
            return True
        except Exception as e:
            print(f"❌ Error scrolling to element: {e}")
            return False
    
    def extract_exhibitor_basic_info(self, exhibitor_element):
        """Extract basic info from exhibitor list without clicking into profile"""
        try:
            data = {}
            
            # Extract company name from list view
            try:
                name_element = exhibitor_element.find_element(By.CSS_SELECTOR, "h4.heading")
                data['Company Name'] = name_element.text.strip()
            except:
                data['Company Name'] = "Not found"
            
            # Extract stand info from list view
            try:
                stand_element = exhibitor_element.find_element(By.CSS_SELECTOR, "p[style*='margin-bottom:0']")
                stand_text = stand_element.text.strip()
                data['Stand Info'] = stand_text
                
                # Extract stand number and hall
                stand_match = re.search(r'Stand No-\s*([^,]+)', stand_text)
                hall_match = re.search(r'Hall\s*(\d+)', stand_text)
                
                data['Stand Number'] = stand_match.group(1) if stand_match else "Not found"
                data['Hall'] = f"Hall {hall_match.group(1)}" if hall_match else "Not found"
            except:
                data['Stand Info'] = "Not found"
                data['Stand Number'] = "Not found"
                data['Hall'] = "Not found"
            
            # Extract country from list view
            try:
                country_element = exhibitor_element.find_element(By.CSS_SELECTOR, "span[style*='font-weight: 600']")
                data['Country'] = country_element.text.strip()
            except:
                data['Country'] = "Not found"
            
            # Extract description from list view
            try:
                desc_element = exhibitor_element.find_element(By.CSS_SELECTOR, "span[style='']")
                data['Short Description'] = desc_element.text.strip()[:300]
            except:
                data['Short Description'] = "Not found"
            
            # Extract sectors from list view
            try:
                sector_elements = exhibitor_element.find_elements(By.CSS_SELECTOR, "ul.sector_block li")
                data['Sectors'] = [sector.text.strip() for sector in sector_elements]
            except:
                data['Sectors'] = []
            
            return data
            
        except Exception as e:
            print(f"❌ Error extracting basic info: {e}")
            return None
    
    def extract_detailed_profile_data(self):
        """Extract detailed data from the exhibitor profile page"""
        try:
            data = {}
            
            # Extract company name
            try:
                name_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h4.group.card-title.inner.list-group-item-heading"))
                )
                data['Company Name'] = name_element.text.strip()
            except TimeoutException:
                data['Company Name'] = "Not found"
            
            # Extract country
            try:
                country_element = self.driver.find_element(By.CSS_SELECTOR, "div.head_discription p span[style*='float:left']")
                data['Country'] = country_element.text.strip()
            except NoSuchElementException:
                data['Country'] = "Not found"
            
            # Extract booth number and hall
            try:
                booth_element = self.driver.find_element(By.CSS_SELECTOR, "div.head_discription p[style*='margin-bottom:0']")
                booth_text = booth_element.text.strip()
                data['Booth Info'] = booth_text
                
                # Extract stand number and hall separately
                stand_match = re.search(r'Stand No\s*-\s*([^,]+)', booth_text)
                hall_match = re.search(r'Hall No\s*-\s*(.+)', booth_text)
                
                data['Stand Number'] = stand_match.group(1) if stand_match else "Not found"
                data['Hall'] = hall_match.group(1) if hall_match else "Not found"
            except NoSuchElementException:
                data['Booth Info'] = "Not found"
                data['Stand Number'] = "Not found"
                data['Hall'] = "Not found"
            
            # Extract website
            try:
                website_element = self.driver.find_element(By.CSS_SELECTOR, "li.social_website a[href*='http']")
                data['Website'] = website_element.get_attribute('href')
            except NoSuchElementException:
                data['Website'] = "Not found"
            
            # Extract LinkedIn
            try:
                linkedin_element = self.driver.find_element(By.CSS_SELECTOR, "a.linkdin_link[href*='linkedin']")
                data['LinkedIn'] = linkedin_element.get_attribute('href')
            except NoSuchElementException:
                data['LinkedIn'] = "Not found"
            
            # Extract YouTube
            try:
                youtube_element = self.driver.find_element(By.CSS_SELECTOR, "a.youtube_link[href*='youtube']")
                data['YouTube'] = youtube_element.get_attribute('href')
            except NoSuchElementException:
                data['YouTube'] = "Not found"
            
            # Extract company description
            try:
                description_element = self.driver.find_element(By.CSS_SELECTOR, "p.group.inner")
                data['Full Description'] = description_element.text.strip()
            except NoSuchElementException:
                data['Full Description'] = "Not found"
            
            # Extract sectors/categories
            try:
                sector_elements = self.driver.find_elements(By.CSS_SELECTOR, "ul.sector_block li")
                data['All Sectors'] = [sector.text.strip() for sector in sector_elements]
            except NoSuchElementException:
                data['All Sectors'] = []
            
            print(f"✅ Detailed data extracted for: {data['Company Name']}")
            return data
            
        except Exception as e:
            print(f"❌ Error extracting detailed profile data: {e}")
            return None
    
    def ensure_element_loaded(self, index):
        """Ensure the element at given index is loaded and visible"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Refresh the elements list
                exhibitors = self.driver.find_elements(By.CSS_SELECTOR, "div.item.col-12.list-group-item")
                
                if index < len(exhibitors):
                    element = exhibitors[index]
                    
                    # Scroll to the element to ensure it's loaded
                    if self.scroll_to_element(element):
                        # Wait a bit for any lazy loading
                        time.sleep(1)
                        return element
                
                # If element not found, scroll a bit more
                self.driver.execute_script("window.scrollBy(0, 300);")
                time.sleep(1)
                
            except Exception as e:
                print(f"⚠️ Attempt {attempt + 1} failed to load element {index}: {e}")
                time.sleep(1)
        
        print(f"❌ Failed to load element {index} after {max_attempts} attempts")
        return None
    
    def scrape_exhibitor_profile(self, index):
        """Click into an exhibitor profile and extract detailed data"""
        try:
            # Ensure the element is loaded and visible
            exhibitor_element = self.ensure_element_loaded(index)
            if not exhibitor_element:
                return False
            
            # Store basic info first
            basic_info = self.extract_exhibitor_basic_info(exhibitor_element)
            if not basic_info:
                return False
            
            print(f"🔄 Clicking profile {index + 1}: {basic_info.get('Company Name', 'Unknown')}")
            
            # Find and click the "VIEW PROFILE" button
            view_profile_btn = exhibitor_element.find_element(By.CSS_SELECTOR, "a.btn[data-type='a']")
            
            # Scroll to the button to ensure it's clickable
            self.scroll_to_element(view_profile_btn)
            time.sleep(0.5)
            
            # Click using JavaScript to avoid interception issues
            self.driver.execute_script("arguments[0].click();", view_profile_btn)
            
            # Wait for profile page to load
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.company_description"))
            )
            
            time.sleep(2)  # Wait for complete loading
            
            # Extract detailed data from profile page
            detailed_data = self.extract_detailed_profile_data()
            
            if detailed_data:
                # Merge basic and detailed data
                merged_data = {**basic_info, **detailed_data}
                self.all_data.append(merged_data)
            
            # Go back to main list
            print("🔙 Navigating back to main list...")
            back_btn = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn.pull-right.back"))
            )
            self.driver.execute_script("arguments[0].click();", back_btn)
            
            # Wait for main list to reload completely
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.item.col-12.list-group-item"))
            )
            
            # After coming back, we need to restore our scroll position
            # Scroll back to where we were (approximately)
            if index > 0:
                scroll_script = f"window.scrollTo(0, {index * 200});"
                self.driver.execute_script(scroll_script)
            
            time.sleep(2)  # Wait for the list to stabilize
            
            print(f"✅ Completed profile {index + 1}: {basic_info.get('Company Name', 'Unknown')}")
            return True
            
        except Exception as e:
            print(f"❌ Error processing exhibitor {index + 1}: {e}")
            # Try to recover by going back to main page
            try:
                print("🔄 Attempting recovery...")
                self.driver.get("https://exhibitors.gitex.com/gitex-global-2025/Exhibitor")
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.item.col-12.list-group-item"))
                )
                # After recovery, scroll to approximately where we were
                if index > 0:
                    scroll_script = f"window.scrollTo(0, {index * 200});"
                    self.driver.execute_script(scroll_script)
                time.sleep(3)
            except Exception as recovery_error:
                print(f"❌ Recovery failed: {recovery_error}")
            return False
    
    def scrape_all_exhibitors(self):
        """Main function to scrape all exhibitors"""
        try:
            # Navigate to the main exhibitor page
            print("🌐 Navigating to GITEX exhibitor page...")
            self.driver.get("https://exhibitors.gitex.com/gitex-global-2025/Exhibitor")
            
            # Wait for initial page load
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.item.col-12.list-group-item"))
            )
            time.sleep(3)
            
            # Scroll to load all exhibitors first
            self.scroll_to_load_all_exhibitors()
            
            # Get final count of exhibitors
            exhibitor_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.item.col-12.list-group-item")
            total_exhibitors = len(exhibitor_elements)
            
            print(f"🎯 Starting to scrape {total_exhibitors} exhibitors...")
            
            # Process each exhibitor by index
            successful_scrapes = 0
            for index in range(total_exhibitors):
                try:
                    if self.scrape_exhibitor_profile(index):
                        successful_scrapes += 1
                    
                    # Save progress every 3 exhibitors (more frequent due to navigation)
                    if (index + 1) % 3 == 0:
                        self.save_progress()
                        print(f"📈 Progress: {index + 1}/{total_exhibitors} completed ({successful_scrapes} successful)")
                        
                    # Small delay between profiles
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"❌ Failed to process exhibitor {index + 1}: {e}")
                    continue
            
            print(f"✅ Successfully scraped {successful_scrapes} out of {total_exhibitors} exhibitors")
            
        except Exception as e:
            print(f"❌ Error in main scraping process: {e}")
        
        finally:
            self.save_final_data()
            self.cleanup()
    
    def save_progress(self):
        """Save progress to Excel file"""
        if self.all_data:
            df = self.prepare_final_dataframe()
            df.to_excel("gitex_exhibitors_progress.xlsx", index=False)
            print(f"💾 Progress saved: {len(self.all_data)} exhibitors")
    
    def prepare_final_dataframe(self):
        """Prepare final DataFrame with all data"""
        detailed_data = []
        for item in self.all_data:
            detailed_item = {
                'Company Name': item.get('Company Name', ''),
                'Country': item.get('Country', ''),
                'Stand Number': item.get('Stand Number', ''),
                'Hall': item.get('Hall', ''),
                'Booth Info': item.get('Booth Info', ''),
                'Website': item.get('Website', ''),
                'LinkedIn': item.get('LinkedIn', ''),
                'YouTube': item.get('YouTube', ''),
                'Short Description': item.get('Short Description', ''),
                'Full Description': item.get('Full Description', ''),
                'Sectors': ', '.join(item.get('Sectors', [])),
                'All Sectors': ', '.join(item.get('All Sectors', [])),
                'Total Sectors': len(item.get('All Sectors', [])),
                'Profile Scraped': 'Yes' if item.get('Website') else 'No'
            }
            detailed_data.append(detailed_item)
        
        return pd.DataFrame(detailed_data)
    
    def save_final_data(self):
        """Save final data to Excel file"""
        if self.all_data:
            df = self.prepare_final_dataframe()
            df.to_excel("gitex_exhibitors_complete.xlsx", index=False)
            
            print(f"🎉 Final data saved: {len(self.all_data)} exhibitors")
            print("📊 Summary Report:")
            print(f"   - Total companies: {len(self.all_data)}")
            print(f"   - With websites: {df[df['Website'] != 'Not found'].shape[0]}")
            print(f"   - With LinkedIn: {df[df['LinkedIn'] != 'Not found'].shape[0]}")
            print(f"   - With YouTube: {df[df['YouTube'] != 'Not found'].shape[0]}")
            print(f"   - Average sectors per company: {df['Total Sectors'].mean():.1f}")
        else:
            print("⚠️ No data to save")
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.driver.quit()
            print("🧹 Browser closed")
        except:
            pass

def main():
    """Main execution function"""
    print("🚀 Starting GITEX Global 2025 Exhibitor Scraper...")
    print("=" * 50)
    
    scraper = GitexExhibitorScraper()
    
    try:
        scraper.scrape_all_exhibitors()
    except KeyboardInterrupt:
        print("\n⏹️ Scraping interrupted by user")
        scraper.save_final_data()
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        scraper.save_final_data()
    finally:
        print("=" * 50)
        print("🎯 Scraping completed!")

if __name__ == "__main__":
    main()