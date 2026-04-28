"""
World Utilities Congress Exhibitor Scraper

This scraper extracts exhibitor data from the World Utilities Congress website:
- Starts at the first exhibitor detail page
- Extracts: Company Name, Logo, Stand Number, Country, Categories, Website, Social Media Links, Description
- Follows "Next" button to scrape all exhibitors sequentially
- Console logs all extracted data
- Saves to Excel

Usage:
    python wlrducongress.py

Output:
    - wlrducongress_exhibitors_progress.xlsx (intermediate saves)
    - wlrducongress_exhibitors_complete.xlsx (final output)
"""

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
from urllib.parse import urljoin
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WorldUtilitiesCongressScraper:
    def __init__(self, list_page_url="https://exhibitors.worldutilitiescongress.com/world-utilities-congress-2025/Exhibitor/", headless=False):
        """
        Initialize the World Utilities Congress scraper
        
        Args:
            list_page_url: URL of the exhibitor list page
            headless: Whether to run browser in headless mode
        """
        self.list_page_url = list_page_url
        self.headless = headless
        self.all_data = []
        self.setup_driver()
        
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--window-size=1920,1080")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 20)
        
    def extract_exhibitor_data(self):
        """
        Extract all data from the current exhibitor detail page
        
        Returns:
            dict: Dictionary with exhibitor data
        """
        data = {
            'Company Name': '',
            'Logo URL': '',
            'Stand Number': '',
            'Country': '',
            'Categories': '',
            'Website': '',
            'Facebook': '',
            'Twitter': '',
            'LinkedIn': '',
            'Instagram': '',
            'YouTube': '',
            'Email': '',
            'Description': '',
            'Page URL': self.driver.current_url
        }
        
        try:
            print(f"\n    [EXTRACTING] Extracting data from: {self.driver.current_url}")
            logging.info(f"Extracting data from: {self.driver.current_url}")
            
            # Wait for main content to load
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.font-bold.company-title"))
                )
            except TimeoutException:
                logging.warning("Timeout waiting for page content to load")
                print("    [WARNING] Timeout waiting for page content")
            
            time.sleep(2)  # Give page time to fully render
            
            # Extract Company Name
            try:
                name_elem = self.driver.find_element(By.CSS_SELECTOR, "h1.font-bold.company-title")
                data['Company Name'] = name_elem.text.strip()
                print(f"    [NAME] Company Name: {data['Company Name']}")
                logging.info(f"Extracted Company Name: {data['Company Name']}")
            except NoSuchElementException:
                print("    [WARNING] Company Name: NOT FOUND")
                logging.warning("Could not extract Company Name")
            
            # Extract Logo URL
            try:
                logo_elem = self.driver.find_element(By.CSS_SELECTOR, "div.logo-holder img")
                logo_url = logo_elem.get_attribute('src') or ''
                if logo_url:
                    data['Logo URL'] = logo_url
                    print(f"    [LOGO] Logo URL: {data['Logo URL']}")
                    logging.info(f"Extracted Logo URL: {data['Logo URL']}")
            except NoSuchElementException:
                print("    [WARNING] Logo URL: NOT FOUND")
                logging.warning("Could not extract Logo URL")
            
            # Extract Stand Number and Country from h6 tags
            try:
                h6_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.col-md-8 h6")
                stand_found = False
                country_found = False
                
                for h6 in h6_elements:
                    text = h6.text.strip()
                    if not text:
                        continue
                    
                    # Check if it's a stand number
                    if ('Stand No' in text or 'Stand' in text) and not stand_found:
                        # Extract stand number (remove "Stand No -" or "Stand No-")
                        stand_text = text.replace('Stand No -', '').replace('Stand No-', '').replace('Stand No', '').strip()
                        if stand_text:
                            data['Stand Number'] = stand_text
                            stand_found = True
                            print(f"    [STAND] Stand Number: {data['Stand Number']}")
                            logging.info(f"Extracted Stand Number: {data['Stand Number']}")
                    # Otherwise, it's likely the country
                    elif not country_found and 'Stand' not in text:
                        data['Country'] = text
                        country_found = True
                        print(f"    [COUNTRY] Country: {data['Country']}")
                        logging.info(f"Extracted Country: {data['Country']}")
                
                if not stand_found:
                    print("    [WARNING] Stand Number: NOT FOUND")
                    logging.warning("Could not extract Stand Number")
                if not country_found:
                    print("    [WARNING] Country: NOT FOUND")
                    logging.warning("Could not extract Country")
                    
            except Exception as e:
                print(f"    [WARNING] Stand/Country: ERROR - {e}")
                logging.warning(f"Could not extract Stand/Country: {e}")
            
            # Extract Categories/Badges
            try:
                badge_elements = self.driver.find_elements(By.CSS_SELECTOR, "span.badge.bg-secondary")
                categories = []
                for badge in badge_elements:
                    categories.append(badge.text.strip())
                if categories:
                    data['Categories'] = ', '.join(categories)
                    print(f"    [CATEGORIES] Categories: {data['Categories']}")
                    logging.info(f"Extracted Categories: {data['Categories']}")
            except Exception as e:
                print(f"    [WARNING] Categories: NOT FOUND - {e}")
                logging.warning(f"Could not extract Categories: {e}")
            
            # Extract Website
            try:
                website_found = False
                
                # Method 1: Look for link with fa-globe icon
                try:
                    website_elem = self.driver.find_element(By.XPATH, "//i[contains(@class, 'fa-globe')]/parent::div/a")
                    website_url = website_elem.get_attribute('href') or ''
                    if website_url:
                        data['Website'] = website_url
                        website_found = True
                        print(f"    [WEBSITE] Website: {data['Website']}")
                        logging.info(f"Extracted Website: {data['Website']}")
                except NoSuchElementException:
                    pass
                
                # Method 2: Look for any link in company-info div that's not social media
                if not website_found:
                    try:
                        company_info = self.driver.find_element(By.CSS_SELECTOR, "div.company-info")
                        links = company_info.find_elements(By.CSS_SELECTOR, "a[href*='http']")
                        for link in links:
                            href = link.get_attribute('href') or ''
                            if href:
                                href_lower = href.lower()
                                # Skip social media links
                                if 'linkedin.com' not in href_lower and 'facebook.com' not in href_lower and 'twitter.com' not in href_lower and 'instagram.com' not in href_lower and 'youtube.com' not in href_lower:
                                    data['Website'] = href
                                    website_found = True
                                    print(f"    [WEBSITE] Website: {data['Website']}")
                                    logging.info(f"Extracted Website: {data['Website']}")
                                    break
                    except:
                        pass
                
                if not website_found:
                    print("    [WARNING] Website: NOT FOUND")
                    logging.warning("Could not extract Website")
                    
            except Exception as e:
                print(f"    [WARNING] Website: ERROR - {e}")
                logging.error(f"Error extracting Website: {e}")
            
            # Extract Social Media Links
            try:
                # Look for social media buttons in btn-group
                try:
                    social_group = self.driver.find_element(By.CSS_SELECTOR, "div.btn-group")
                    social_links = social_group.find_elements(By.CSS_SELECTOR, "a")
                    
                    for link in social_links:
                        href = link.get_attribute('href') or ''
                        if not href:
                            continue
                        
                        href_lower = href.lower()
                        if 'facebook.com' in href_lower:
                            data['Facebook'] = href
                            print(f"    [FACEBOOK] Facebook: {data['Facebook']}")
                            logging.info(f"Extracted Facebook: {data['Facebook']}")
                        elif 'twitter.com' in href_lower or 'x.com' in href_lower:
                            data['Twitter'] = href
                            print(f"    [TWITTER] Twitter: {data['Twitter']}")
                            logging.info(f"Extracted Twitter: {data['Twitter']}")
                        elif 'linkedin.com' in href_lower:
                            data['LinkedIn'] = href
                            print(f"    [LINKEDIN] LinkedIn: {data['LinkedIn']}")
                            logging.info(f"Extracted LinkedIn: {data['LinkedIn']}")
                        elif 'instagram.com' in href_lower:
                            data['Instagram'] = href
                            print(f"    [INSTAGRAM] Instagram: {data['Instagram']}")
                            logging.info(f"Extracted Instagram: {data['Instagram']}")
                        elif 'youtube.com' in href_lower:
                            data['YouTube'] = href
                            print(f"    [YOUTUBE] YouTube: {data['YouTube']}")
                            logging.info(f"Extracted YouTube: {data['YouTube']}")
                except NoSuchElementException:
                    # Social media links are optional, so no warning needed
                    pass
            except Exception as e:
                # Social media links are optional
                pass
            
            # Extract Email (if present)
            try:
                # Look for mailto link
                email_elem = self.driver.find_element(By.XPATH, "//a[starts-with(@href, 'mailto:')]")
                email = email_elem.get_attribute('href') or ''
                if email:
                    data['Email'] = email.replace('mailto:', '').strip()
                    print(f"    [EMAIL] Email: {data['Email']}")
                    logging.info(f"Extracted Email: {data['Email']}")
            except NoSuchElementException:
                # Email is optional, so no warning needed
                pass
            
            # Extract Description
            try:
                desc_found = False
                
                # Method 1: Check if "About the company" tab exists and is active
                try:
                    about_tab = self.driver.find_element(By.CSS_SELECTOR, "button#pills-About-tab")
                    # Check if tab is active
                    if 'active' not in about_tab.get_attribute('class'):
                        # Click the tab to activate it
                        about_tab.click()
                        time.sleep(1.5)  # Wait for tab content to load
                    
                    # Extract description from the tab content
                    desc_elem = self.driver.find_element(By.CSS_SELECTOR, "div#pills-About p")
                    desc_text = desc_elem.text.strip()
                    if desc_text:
                        data['Description'] = desc_text
                        desc_found = True
                        print(f"    [DESCRIPTION] Description: {data['Description'][:100]}..." if len(data['Description']) > 100 else f"    [DESCRIPTION] Description: {data['Description']}")
                        logging.info(f"Extracted Description: {len(data['Description'])} characters")
                except NoSuchElementException:
                    pass
                
                # Method 2: Try to find any p tag in tab content
                if not desc_found:
                    try:
                        tab_content = self.driver.find_element(By.CSS_SELECTOR, "div#pills-About")
                        paragraphs = tab_content.find_elements(By.CSS_SELECTOR, "p")
                        if paragraphs:
                            desc_text = paragraphs[0].text.strip()
                            if desc_text:
                                data['Description'] = desc_text
                                desc_found = True
                                print(f"    [DESCRIPTION] Description: {data['Description'][:100]}..." if len(data['Description']) > 100 else f"    [DESCRIPTION] Description: {data['Description']}")
                                logging.info(f"Extracted Description: {len(data['Description'])} characters")
                    except:
                        pass
                
                if not desc_found:
                    print("    [WARNING] Description: NOT FOUND")
                    logging.warning("Could not extract Description")
                    
            except Exception as e:
                print(f"    [WARNING] Description: ERROR - {e}")
                logging.error(f"Error extracting Description: {e}")
            
            print(f"\n    [SUCCESS] EXTRACTION COMPLETE for: {data['Company Name'] or 'Unknown'}")
            print(f"    {'-' * 60}")
            
        except Exception as e:
            logging.error(f"Error extracting exhibitor data: {e}")
            print(f"    [ERROR] ERROR extracting exhibitor data: {e}")
        
        return data
    
    def get_exhibitor_cards_from_list_page(self):
        """
        Extract all exhibitor card links from the current list page
        
        Returns:
            list: List of dictionaries with card info (name, stand, country, detail_url)
        """
        cards_data = []
        try:
            # Wait for cards to load
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.col-md-3.mb-3 div.card"))
            )
            time.sleep(2)  # Give page time to render
            
            # Find all exhibitor cards
            card_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.col-md-3.mb-3")
            
            print(f"    [FOUND] Found {len(card_containers)} card containers")
            logging.info(f"Found {len(card_containers)} card containers")
            
            for idx, card_container in enumerate(card_containers, 1):
                try:
                    card = card_container.find_element(By.CSS_SELECTOR, "div.card")
                    
                    # Extract detail page URL
                    detail_url = ""
                    try:
                        # Try to get URL from card-title link
                        title_link = card.find_element(By.CSS_SELECTOR, "h5.card-title a")
                        detail_url = title_link.get_attribute('href') or ''
                        if not detail_url:
                            # Try card-img link
                            img_link = card.find_element(By.CSS_SELECTOR, "div.card-img a")
                            detail_url = img_link.get_attribute('href') or ''
                    except NoSuchElementException:
                        print(f"    [WARNING] Card {idx} - Detail URL: NOT FOUND")
                        continue
                    
                    # Extract company name
                    name = ""
                    try:
                        name_elem = card.find_element(By.CSS_SELECTOR, "h5.card-title a")
                        name = name_elem.text.strip()
                        print(f"    [NAME] Card {idx} - Name: {name}")
                    except NoSuchElementException:
                        print(f"    [WARNING] Card {idx} - Name: NOT FOUND")
                    
                    # Extract stand number
                    stand = ""
                    try:
                        stand_elem = card.find_element(By.CSS_SELECTOR, "h6.card-subtitle")
                        stand_text = stand_elem.text.strip()
                        stand = stand_text.replace('Stand No-', '').replace('Stand No -', '').strip()
                        print(f"    [STAND] Card {idx} - Stand: {stand}")
                    except NoSuchElementException:
                        print(f"    [WARNING] Card {idx} - Stand: NOT FOUND")
                    
                    # Extract country
                    country = ""
                    try:
                        country_elem = card.find_element(By.CSS_SELECTOR, "p.card-text")
                        country = country_elem.text.strip()
                        print(f"    [COUNTRY] Card {idx} - Country: {country}")
                    except NoSuchElementException:
                        print(f"    [WARNING] Card {idx} - Country: NOT FOUND")
                    
                    # Extract logo URL
                    logo_url = ""
                    try:
                        img_elem = card.find_element(By.CSS_SELECTOR, "div.card-img img")
                        logo_url = img_elem.get_attribute('src') or ''
                        print(f"    [LOGO] Card {idx} - Logo: {logo_url}")
                    except NoSuchElementException:
                        print(f"    [WARNING] Card {idx} - Logo: NOT FOUND")
                    
                    if detail_url:
                        cards_data.append({
                            'name': name,
                            'stand': stand,
                            'country': country,
                            'logo_url': logo_url,
                            'detail_url': detail_url
                        })
                        print(f"    [SUCCESS] Card {idx} added to list")
                    else:
                        print(f"    [WARNING] Card {idx} skipped (no detail URL)")
                        
                except Exception as e:
                    print(f"    [ERROR] Error processing card {idx}: {e}")
                    logging.error(f"Error processing card {idx}: {e}")
                    continue
            
            print(f"\n    [SUCCESS] Total valid cards found: {len(cards_data)}")
            logging.info(f"Total valid cards found: {len(cards_data)}")
            
        except TimeoutException:
            logging.warning("Timeout waiting for cards to load")
            print("    [WARNING] Timeout waiting for cards to load")
        except Exception as e:
            logging.error(f"Error getting exhibitor cards: {e}")
            print(f"    [ERROR] Error getting exhibitor cards: {e}")
        
        return cards_data
    
    def has_next_list_page(self):
        """
        Check if there's a next page on the list page
        
        Returns:
            tuple: (has_next, next_url) or (False, None)
        """
        try:
            # Look for pagination buttons
            # Common pagination patterns: "Next", ">", page numbers, etc.
            next_button = None
            
            # Try various selectors for next button
            selectors = [
                "//a[contains(text(), 'Next')]",
                "//a[contains(text(), '>')]",
                "//li[@class='page-item']/a[contains(text(), 'Next')]",
                "//a[@aria-label='Next']"
            ]
            
            for selector in selectors:
                try:
                    next_button = self.driver.find_element(By.XPATH, selector)
                    break
                except NoSuchElementException:
                    continue
            
            if next_button:
                # Check if button is disabled
                if 'disabled' in next_button.get_attribute('class') or 'disabled' in next_button.get_attribute('aria-disabled'):
                    return (False, None)
                
                next_url = next_button.get_attribute('href') or ''
                if next_url:
                    if next_url.startswith('/'):
                        base_url = '/'.join(self.driver.current_url.split('/')[:3])
                        next_url = base_url + next_url
                    return (True, next_url)
            
            return (False, None)
            
        except Exception as e:
            logging.warning(f"Error checking for next list page: {e}")
            return (False, None)
    
    def scrape_all_exhibitors(self):
        """
        Scrape all exhibitors from the list page
        """
        try:
            # Start at the list page
            current_list_url = self.list_page_url
            list_page_number = 1
            total_exhibitors_processed = 0
            
            print(f"\n{'='*60}")
            print(f"[STARTING] Starting scraper")
            print(f"[LIST PAGE] List page: {current_list_url}")
            print(f"{'='*60}\n")
            
            logging.info(f"Starting scraper at list page: {current_list_url}")
            
            while current_list_url:
                print(f"\n{'='*60}")
                print(f"[LIST PAGE] PROCESSING LIST PAGE #{list_page_number}")
                print(f"{'='*60}")
                print(f"URL: {current_list_url}")
                print(f"{'='*60}\n")
                
                # Navigate to list page
                self.driver.get(current_list_url)
                time.sleep(3)  # Wait for page to load
                
                # Get all exhibitor cards from this list page
                cards_data = self.get_exhibitor_cards_from_list_page()
                
                if not cards_data:
                    print(f"[WARNING] No cards found on page {list_page_number}")
                    break
                
                # Process each exhibitor card
                for idx, card_info in enumerate(cards_data, 1):
                    total_exhibitors_processed += 1
                    
                    print(f"\n{'='*60}")
                    print(f"[PROCESSING] PROCESSING EXHIBITOR #{total_exhibitors_processed}")
                    print(f"{'='*60}")
                    print(f"Name: {card_info['name']}")
                    print(f"Stand: {card_info.get('stand', 'N/A')}")
                    print(f"Country: {card_info.get('country', 'N/A')}")
                    print(f"Detail URL: {card_info['detail_url']}")
                    print(f"{'='*60}\n")
                    
                    logging.info(f"Processing exhibitor {total_exhibitors_processed}: {card_info['name']}")
                    
                    # Navigate to detail page
                    self.driver.get(card_info['detail_url'])
                    time.sleep(3)  # Wait for page to load
                    
                    # Extract detailed data from detail page
                    exhibitor_data = self.extract_exhibitor_data()
                    
                    # Merge list page data with detail page data
                    final_data = {
                        'Company Name': exhibitor_data.get('Company Name') or card_info.get('name', ''),
                        'Stand Number': exhibitor_data.get('Stand Number') or card_info.get('stand', ''),
                        'Country': exhibitor_data.get('Country') or card_info.get('country', ''),
                        'Logo URL': exhibitor_data.get('Logo URL') or card_info.get('logo_url', ''),
                        'Categories': exhibitor_data.get('Categories', ''),
                        'Website': exhibitor_data.get('Website', ''),
                        'Facebook': exhibitor_data.get('Facebook', ''),
                        'Twitter': exhibitor_data.get('Twitter', ''),
                        'LinkedIn': exhibitor_data.get('LinkedIn', ''),
                        'Instagram': exhibitor_data.get('Instagram', ''),
                        'YouTube': exhibitor_data.get('YouTube', ''),
                        'Email': exhibitor_data.get('Email', ''),
                        'Description': exhibitor_data.get('Description', ''),
                        'Detail Page URL': card_info['detail_url']
                    }
                    
                    # Add to all_data
                    self.all_data.append(final_data)
                    
                    print(f"\n[SUCCESS] COMPLETED EXHIBITOR #{total_exhibitors_processed}: {final_data['Company Name']}")
                    print(f"   Stand: {final_data.get('Stand Number', 'N/A')}")
                    print(f"   Country: {final_data.get('Country', 'N/A')}")
                    print(f"   Website: {final_data.get('Website', 'N/A')}")
                    print(f"{'='*60}\n")
                    
                    # Save progress every 10 exhibitors
                    if total_exhibitors_processed % 10 == 0:
                        self.save_progress()
                        print(f"[SAVED] Progress saved: {total_exhibitors_processed} exhibitors processed")
                    
                    # Small delay between exhibitors
                    time.sleep(1)
                
                # Check for next list page
                has_next, next_list_url = self.has_next_list_page()
                
                if not has_next or not next_list_url:
                    print(f"\n{'='*60}")
                    print(f"[COMPLETE] REACHED THE END OF LIST PAGES!")
                    print(f"{'='*60}")
                    break
                
                # Check if we're going in circles (safety check)
                if next_list_url == current_list_url:
                    print(f"\n[WARNING] Next list URL is same as current URL. Stopping to prevent infinite loop.")
                    logging.warning("Next list URL is same as current URL. Stopping.")
                    break
                
                current_list_url = next_list_url
                list_page_number += 1
                
                # Small delay before next list page
                time.sleep(2)
            
            print(f"\n{'='*60}")
            print(f"[COMPLETE] SCRAPING COMPLETE!")
            print(f"{'='*60}")
            print(f"[TOTAL] Total list pages scraped: {list_page_number}")
            print(f"[TOTAL] Total exhibitors scraped: {len(self.all_data)}")
            print(f"{'='*60}\n")
            
            logging.info(f"Scraping completed. Total list pages: {list_page_number}, Total exhibitors: {len(self.all_data)}")
            
            # Final save
            self.save_to_excel()
            
        except KeyboardInterrupt:
            print("\n[WARNING] Scraping interrupted by user")
            logging.info("Scraping interrupted by user")
            self.save_progress()
        except Exception as e:
            logging.error(f"Error during scraping: {e}")
            print(f"[ERROR] Error during scraping: {e}")
            self.save_progress()
            raise
    
    def save_progress(self):
        """Save current progress to Excel file"""
        if self.all_data:
            try:
                df = pd.DataFrame(self.all_data)
                df.to_excel('wlrducongress_exhibitors_progress.xlsx', index=False)
                logging.info(f"Progress saved: {len(self.all_data)} exhibitors")
                print(f"[SAVED] Progress saved: {len(self.all_data)} exhibitors")
            except Exception as e:
                logging.error(f"Error saving progress: {e}")
                print(f"[ERROR] Error saving progress: {e}")
    
    def save_to_excel(self, filename='wlrducongress_exhibitors_complete.xlsx'):
        """
        Save all scraped data to Excel file
        
        Args:
            filename: Name of the output Excel file
        """
        if not self.all_data:
            logging.warning("No data to save")
            print("[WARNING] No data to save")
            return
        
        try:
            df = pd.DataFrame(self.all_data)
            df.to_excel(filename, index=False)
            logging.info(f"Data saved to {filename}")
            print(f"[SUCCESS] Data saved to {filename}")
            print(f"[TOTAL] Total records: {len(df)}")
        except Exception as e:
            logging.error(f"Error saving to Excel: {e}")
            print(f"[ERROR] Error saving to Excel: {e}")
            raise
    
    def close(self):
        """Close the browser"""
        if hasattr(self, 'driver'):
            self.driver.quit()
            logging.info("Browser closed")
            print("[CLOSED] Browser closed")

def main():
    """Main function to run the scraper"""
    scraper = None
    try:
        scraper = WorldUtilitiesCongressScraper(headless=False)  # Set to True for headless mode
        scraper.scrape_all_exhibitors()
    except KeyboardInterrupt:
        print("\n[WARNING] Scraping interrupted by user")
        logging.info("Scraping interrupted by user")
        if scraper:
            scraper.save_progress()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        print(f"[ERROR] Fatal error: {e}")
        if scraper:
            scraper.save_progress()
        raise
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()
