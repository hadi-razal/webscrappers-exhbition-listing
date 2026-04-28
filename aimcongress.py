"""
AIM Congress Exhibitor List Scraper

This scraper extracts exhibitor data from the AIM Congress website:
- Exhibitor name, logo, country (from list page)
- Website, LinkedIn, address, description (from detail page)

The scraper:
- Scrapes all exhibitor cards from the list page
- Clicks "VIEW DETAILS" for each exhibitor
- Extracts detailed information from each detail page
- Handles pagination automatically
- Console logs all extracted data
- Saves to Excel

Usage:
    python aimcongress.py

Output:
    - aimcongress_exhibitors_progress.xlsx (intermediate saves)
    - aimcongress_exhibitors_complete.xlsx (final output)
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

class AIMCongressScraper:
    def __init__(self, base_url="https://www.aimcongress.com/exhibitors-2025", headless=False):
        """
        Initialize the AIM Congress scraper
        
        Args:
            base_url: The URL to scrape
            headless: Whether to run browser in headless mode
        """
        self.base_url = base_url
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
        
    def get_exhibitor_cards_from_page(self):
        """
        Extract all exhibitor cards from the current list page
        
        Returns:
            list: List of dictionaries with card info (name, country, detail_url)
        """
        cards_data = []
        try:
            # Wait for the grid container to load
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.grid.grid-cols-2, div.grid"))
            )
            time.sleep(2)  # Give page time to render
            
            # Find all card containers
            card_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.grid > div")
            
            print(f"    🔍 Found {len(card_containers)} card containers")
            logging.info(f"Found {len(card_containers)} card containers")
            
            for idx, card in enumerate(card_containers, 1):
                try:
                    # Extract name
                    name = ""
                    try:
                        name_elem = card.find_element(By.CSS_SELECTOR, "h4.text-white")
                        name = name_elem.text.strip()
                        print(f"    📝 Card {idx} - Name: {name}")
                        logging.info(f"Card {idx} - Name: {name}")
                    except NoSuchElementException:
                        print(f"    ⚠️ Card {idx} - Name: NOT FOUND")
                        logging.warning(f"Card {idx} - Name not found")
                    
                    # Extract country
                    country = ""
                    try:
                        country_elem = card.find_element(By.CSS_SELECTOR, "p.text-md.text-white")
                        country = country_elem.text.strip()
                        print(f"    🌍 Card {idx} - Country: {country}")
                        logging.info(f"Card {idx} - Country: {country}")
                    except NoSuchElementException:
                        print(f"    ⚠️ Card {idx} - Country: NOT FOUND")
                        logging.warning(f"Card {idx} - Country not found")
                    
                    # Extract logo URL
                    logo_url = ""
                    try:
                        img_elem = card.find_element(By.CSS_SELECTOR, "img")
                        logo_url = img_elem.get_attribute('src') or ''
                        if logo_url:
                            # Convert relative URL to absolute
                            if logo_url.startswith('/'):
                                logo_url = urljoin(self.base_url, logo_url)
                            print(f"    🖼️ Card {idx} - Logo: {logo_url}")
                            logging.info(f"Card {idx} - Logo: {logo_url}")
                    except NoSuchElementException:
                        print(f"    ⚠️ Card {idx} - Logo: NOT FOUND")
                        logging.warning(f"Card {idx} - Logo not found")
                    
                    # Extract detail page URL
                    detail_url = ""
                    try:
                        detail_link = card.find_element(By.CSS_SELECTOR, "a[href*='/exhibitors-2025/']")
                        detail_url = detail_link.get_attribute('href') or ''
                        if detail_url:
                            if detail_url.startswith('/'):
                                detail_url = urljoin(self.base_url, detail_url)
                            print(f"    🔗 Card {idx} - Detail URL: {detail_url}")
                            logging.info(f"Card {idx} - Detail URL: {detail_url}")
                    except NoSuchElementException:
                        print(f"    ⚠️ Card {idx} - Detail URL: NOT FOUND")
                        logging.warning(f"Card {idx} - Detail URL not found")
                        continue  # Skip this card if no detail URL
                    
                    if name and detail_url:
                        cards_data.append({
                            'name': name,
                            'country': country,
                            'logo_url': logo_url,
                            'detail_url': detail_url
                        })
                        print(f"    ✅ Card {idx} added to list")
                    else:
                        print(f"    ⚠️ Card {idx} skipped (missing name or detail URL)")
                        
                except Exception as e:
                    print(f"    ❌ Error processing card {idx}: {e}")
                    logging.error(f"Error processing card {idx}: {e}")
                    continue
            
            print(f"\n    ✅ Total valid cards found: {len(cards_data)}")
            logging.info(f"Total valid cards found: {len(cards_data)}")
            
        except TimeoutException:
            logging.warning("Timeout waiting for cards to load")
            print("    ⚠️ Timeout waiting for cards to load")
        except Exception as e:
            logging.error(f"Error getting exhibitor cards: {e}")
            print(f"    ❌ Error getting exhibitor cards: {e}")
        
        return cards_data
    
    def extract_detail_page_data(self, detail_url):
        """
        Extract detailed data from an exhibitor's detail page
        
        Args:
            detail_url: URL of the detail page
            
        Returns:
            dict: Dictionary with detailed exhibitor data
        """
        data = {
            'Exhibitor Name': '',
            'Country': '',
            'Address': '',
            'Website': '',
            'LinkedIn': '',
            'Description': '',
            'Logo URL': ''
        }
        
        try:
            print(f"\n    🔍 Opening detail page: {detail_url}")
            logging.info(f"Opening detail page: {detail_url}")
            
            # Navigate to detail page
            self.driver.get(detail_url)
            time.sleep(3)  # Wait for page to load
            
            # Wait for main content to load
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.text-2xl, h1.text-3xl"))
                )
            except TimeoutException:
                logging.warning("Timeout waiting for detail page to load")
                print("    ⚠️ Timeout waiting for detail page content")
            
            # Extract name
            try:
                name_elem = self.driver.find_element(By.CSS_SELECTOR, "h1.text-2xl, h1.text-3xl")
                data['Exhibitor Name'] = name_elem.text.strip()
                print(f"    📝 Name: {data['Exhibitor Name']}")
                logging.info(f"Extracted Name: {data['Exhibitor Name']}")
            except NoSuchElementException:
                print("    ⚠️ Name: NOT FOUND")
                logging.warning("Could not extract Name")
            
            # Extract country
            try:
                # Look for "Country:" label - try multiple approaches
                country_found = False
                
                # Method 1: Look for p tag containing "Country:"
                try:
                    country_section = self.driver.find_element(By.XPATH, "//p[contains(text(), 'Country:')]")
                    country_text = country_section.text.strip()
                    # Extract country after "Country:"
                    if 'Country:' in country_text:
                        data['Country'] = country_text.split('Country:')[1].strip()
                        country_found = True
                        print(f"    🌍 Country: {data['Country']}")
                        logging.info(f"Extracted Country: {data['Country']}")
                except NoSuchElementException:
                    pass
                
                # Method 2: Look for strong tag with "Country:" followed by text
                if not country_found:
                    try:
                        country_section = self.driver.find_element(By.XPATH, "//p[strong[contains(text(), 'Country:')]]")
                        country_text = country_section.text.strip()
                        if 'Country:' in country_text:
                            data['Country'] = country_text.split('Country:')[1].strip()
                            country_found = True
                            print(f"    🌍 Country: {data['Country']}")
                            logging.info(f"Extracted Country: {data['Country']}")
                    except NoSuchElementException:
                        pass
                
                # Method 3: Look in text-gray-700 div
                if not country_found:
                    try:
                        country_elems = self.driver.find_elements(By.CSS_SELECTOR, "div.text-gray-700 p")
                        for elem in country_elems:
                            text = elem.text.strip()
                            if 'Country:' in text:
                                data['Country'] = text.split('Country:')[1].strip()
                                country_found = True
                                print(f"    🌍 Country: {data['Country']}")
                                logging.info(f"Extracted Country: {data['Country']}")
                                break
                    except:
                        pass
                
                if not country_found:
                    print("    ⚠️ Country: NOT FOUND")
                    logging.warning("Could not extract Country")
                    
            except Exception as e:
                print(f"    ⚠️ Country: ERROR - {e}")
                logging.error(f"Error extracting Country: {e}")
            
            # Extract address
            try:
                address_found = False
                
                # Method 1: Look for p tag with whitespace-pre-line class
                try:
                    address_elem = self.driver.find_element(By.CSS_SELECTOR, "p.whitespace-pre-line")
                    address_text = address_elem.text.strip()
                    if address_text and 'Country:' not in address_text:
                        data['Address'] = address_text
                        address_found = True
                        print(f"    📍 Address: {data['Address']}")
                        logging.info(f"Extracted Address: {data['Address']}")
                except NoSuchElementException:
                    pass
                
                # Method 2: Look in text-gray-700 paragraphs (skip country line)
                if not address_found:
                    try:
                        paragraphs = self.driver.find_elements(By.CSS_SELECTOR, "div.text-gray-700 p")
                        for p in paragraphs:
                            text = p.text.strip()
                            # Skip if it's the country line
                            if 'Country:' not in text and text and len(text) > 5:
                                data['Address'] = text
                                address_found = True
                                print(f"    📍 Address: {data['Address']}")
                                logging.info(f"Extracted Address: {data['Address']}")
                                break
                    except:
                        pass
                
                if not address_found:
                    print("    ⚠️ Address: NOT FOUND")
                    logging.warning("Could not extract Address")
                    
            except Exception as e:
                print(f"    ⚠️ Address: ERROR - {e}")
                logging.error(f"Error extracting Address: {e}")
            
            # Extract website
            try:
                website_found = False
                
                # Method 1: Look for link with "Visit Website" text
                try:
                    website_link = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Visit Website')]")
                    data['Website'] = website_link.get_attribute('href') or ''
                    if data['Website']:
                        website_found = True
                        print(f"    🌐 Website: {data['Website']}")
                        logging.info(f"Extracted Website: {data['Website']}")
                except NoSuchElementException:
                    pass
                
                # Method 2: Look for button/link with bg-primary class (usually the website button)
                if not website_found:
                    try:
                        website_btn = self.driver.find_element(By.CSS_SELECTOR, "a.bg-primary, button.bg-primary")
                        href = website_btn.get_attribute('href') or ''
                        if href and 'http' in href:
                            data['Website'] = href
                            website_found = True
                            print(f"    🌐 Website: {data['Website']}")
                            logging.info(f"Extracted Website: {data['Website']}")
                    except NoSuchElementException:
                        pass
                
                # Method 3: Look for any link with http in href that's not social media
                if not website_found:
                    try:
                        all_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='http']")
                        for link in all_links:
                            href = link.get_attribute('href') or ''
                            if href and 'linkedin.com' not in href.lower() and 'facebook.com' not in href.lower() and 'twitter.com' not in href.lower() and 'instagram.com' not in href.lower():
                                data['Website'] = href
                                website_found = True
                                print(f"    🌐 Website: {data['Website']}")
                                logging.info(f"Extracted Website: {data['Website']}")
                                break
                    except:
                        pass
                
                if not website_found:
                    print("    ⚠️ Website: NOT FOUND")
                    logging.warning("Could not extract Website")
                    
            except Exception as e:
                print(f"    ⚠️ Website: ERROR - {e}")
                logging.error(f"Error extracting Website: {e}")
            
            # Extract LinkedIn
            try:
                linkedin_found = False
                
                # Method 1: Look for link with "Follow on LinkedIn" text
                try:
                    linkedin_link = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Follow on LinkedIn')]")
                    data['LinkedIn'] = linkedin_link.get_attribute('href') or ''
                    if data['LinkedIn']:
                        linkedin_found = True
                        print(f"    💼 LinkedIn: {data['LinkedIn']}")
                        logging.info(f"Extracted LinkedIn: {data['LinkedIn']}")
                except NoSuchElementException:
                    pass
                
                # Method 2: Look for any link with linkedin.com in href
                if not linkedin_found:
                    try:
                        linkedin_link = self.driver.find_element(By.XPATH, "//a[contains(@href, 'linkedin.com')]")
                        data['LinkedIn'] = linkedin_link.get_attribute('href') or ''
                        if data['LinkedIn']:
                            linkedin_found = True
                            print(f"    💼 LinkedIn: {data['LinkedIn']}")
                            logging.info(f"Extracted LinkedIn: {data['LinkedIn']}")
                    except NoSuchElementException:
                        pass
                
                if not linkedin_found:
                    print("    ⚠️ LinkedIn: NOT FOUND")
                    logging.warning("Could not extract LinkedIn")
                    
            except Exception as e:
                print(f"    ⚠️ LinkedIn: ERROR - {e}")
                logging.error(f"Error extracting LinkedIn: {e}")
            
            # Extract description
            try:
                desc_elem = self.driver.find_element(By.CSS_SELECTOR, "div.prose.max-w-none")
                data['Description'] = desc_elem.text.strip()
                print(f"    📄 Description: {data['Description'][:100]}..." if len(data['Description']) > 100 else f"    📄 Description: {data['Description']}")
                logging.info(f"Extracted Description: {len(data['Description'])} characters")
            except NoSuchElementException:
                print("    ⚠️ Description: NOT FOUND")
                logging.warning("Could not extract Description")
            
            # Extract logo from detail page
            try:
                logo_elem = self.driver.find_element(By.CSS_SELECTOR, "div.bg-white.rounded-full img")
                logo_url = logo_elem.get_attribute('src') or ''
                if logo_url:
                    if logo_url.startswith('/'):
                        logo_url = urljoin(self.base_url, logo_url)
                    data['Logo URL'] = logo_url
                    print(f"    🖼️ Logo: {data['Logo URL']}")
                    logging.info(f"Extracted Logo: {data['Logo URL']}")
            except NoSuchElementException:
                print("    ⚠️ Logo: NOT FOUND")
                logging.warning("Could not extract Logo from detail page")
            
            print(f"\n    ✅ EXTRACTION COMPLETE for: {data['Exhibitor Name'] or 'Unknown'}")
            print(f"    {'─' * 60}")
            
        except Exception as e:
            logging.error(f"Error extracting detail page data: {e}")
            print(f"    ❌ ERROR extracting detail page data: {e}")
        
        return data
    
    def has_next_page(self):
        """
        Check if there's a next page available
        
        Returns:
            tuple: (has_next, next_url) or (False, None)
        """
        try:
            # Look for pagination buttons or "Load More" button
            # Check for common pagination patterns
            next_button = None
            
            # Try to find next page button
            try:
                next_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Next')]")
            except NoSuchElementException:
                try:
                    next_button = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Next')]")
                except NoSuchElementException:
                    # Check for page numbers
                    try:
                        current_page = self.driver.find_element(By.CSS_SELECTOR, "button[aria-current='true'], a[aria-current='true']")
                        # Try to find next page number
                        pass
                    except:
                        pass
            
            if next_button:
                next_url = next_button.get_attribute('href')
                if next_url:
                    return (True, next_url)
                # If it's a button, try clicking it
                try:
                    next_button.click()
                    time.sleep(3)
                    return (True, self.driver.current_url)
                except:
                    pass
                    
        except Exception as e:
            logging.warning(f"Error checking for next page: {e}")
        
        return (False, None)
    
    def scroll_to_load_more(self):
        """
        Scroll down to trigger lazy loading if the page uses infinite scroll
        
        Returns:
            bool: True if new content was loaded, False otherwise
        """
        try:
            # Get current number of cards
            current_count = len(self.driver.find_elements(By.CSS_SELECTOR, "div.grid > div"))
            
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            
            # Check if new cards appeared
            new_count = len(self.driver.find_elements(By.CSS_SELECTOR, "div.grid > div"))
            
            if new_count > current_count:
                print(f"    📜 Loaded more cards: {current_count} -> {new_count}")
                logging.info(f"Loaded more cards: {current_count} -> {new_count}")
                return True
            
            return False
        except Exception as e:
            logging.warning(f"Error scrolling: {e}")
            return False
    
    def scrape_all_exhibitors(self):
        """
        Scrape all exhibitors from the list page and their detail pages
        """
        try:
            # Navigate to the base URL
            logging.info(f"🌐 Navigating to {self.base_url}")
            print(f"\n{'='*60}")
            print(f"🌐 Navigating to {self.base_url}")
            print(f"{'='*60}\n")
            self.driver.get(self.base_url)
            time.sleep(5)  # Give page time to fully load
            
            # Try to load all cards by scrolling (in case of infinite scroll)
            print("📜 Checking for infinite scroll/lazy loading...")
            scroll_attempts = 0
            max_scrolls = 5
            while scroll_attempts < max_scrolls:
                if not self.scroll_to_load_more():
                    break
                scroll_attempts += 1
                time.sleep(2)
            
            # Get all exhibitor cards from the page
            print(f"\n🔍 Extracting exhibitor cards from list page...")
            cards_data = self.get_exhibitor_cards_from_page()
            
            if not cards_data:
                print("⚠️ No exhibitor cards found on the page")
                logging.warning("No exhibitor cards found")
                return
            
            total_exhibitors = len(cards_data)
            print(f"\n{'='*60}")
            print(f"📊 Found {total_exhibitors} exhibitors to scrape")
            print(f"{'='*60}\n")
            
            # Process each exhibitor
            for idx, card_info in enumerate(cards_data, 1):
                print(f"\n{'='*60}")
                print(f"📄 PROCESSING EXHIBITOR {idx}/{total_exhibitors}")
                print(f"{'='*60}")
                print(f"Name: {card_info['name']}")
                print(f"Country: {card_info.get('country', 'N/A')}")
                print(f"Detail URL: {card_info['detail_url']}")
                print(f"{'='*60}\n")
                
                logging.info(f"Processing exhibitor {idx}/{total_exhibitors}: {card_info['name']}")
                
                # Extract data from detail page
                detail_data = self.extract_detail_page_data(card_info['detail_url'])
                
                # Merge list page data with detail page data
                final_data = {
                    'Exhibitor Name': detail_data.get('Exhibitor Name') or card_info.get('name', ''),
                    'Country': detail_data.get('Country') or card_info.get('country', ''),
                    'Address': detail_data.get('Address', ''),
                    'Website': detail_data.get('Website', ''),
                    'LinkedIn': detail_data.get('LinkedIn', ''),
                    'Description': detail_data.get('Description', ''),
                    'Logo URL': detail_data.get('Logo URL') or card_info.get('logo_url', ''),
                    'Detail Page URL': card_info['detail_url']
                }
                
                # Add to all_data
                self.all_data.append(final_data)
                
                print(f"\n✅ COMPLETED: {final_data['Exhibitor Name']}")
                print(f"   Country: {final_data.get('Country', 'N/A')}")
                print(f"   Website: {final_data.get('Website', 'N/A')}")
                print(f"   LinkedIn: {final_data.get('LinkedIn', 'N/A')}")
                print(f"{'='*60}\n")
                
                # Save progress every 10 exhibitors
                if idx % 10 == 0:
                    self.save_progress()
                    print(f"💾 Progress saved: {idx}/{total_exhibitors} exhibitors processed")
                
                # Small delay between requests
                time.sleep(2)
            
            print(f"\n{'='*60}")
            print(f"🎉 SCRAPING COMPLETE!")
            print(f"{'='*60}")
            print(f"📊 Total exhibitors scraped: {len(self.all_data)}")
            print(f"{'='*60}\n")
            
            # Final save
            self.save_to_excel()
            
        except Exception as e:
            logging.error(f"Error during scraping: {e}")
            print(f"❌ Error during scraping: {e}")
            raise
    
    def save_progress(self):
        """Save current progress to Excel file"""
        if self.all_data:
            try:
                df = pd.DataFrame(self.all_data)
                df.to_excel('aimcongress_exhibitors_progress.xlsx', index=False)
                logging.info(f"Progress saved: {len(self.all_data)} exhibitors")
                print(f"💾 Progress saved: {len(self.all_data)} exhibitors")
            except Exception as e:
                logging.error(f"Error saving progress: {e}")
                print(f"❌ Error saving progress: {e}")
    
    def save_to_excel(self, filename='aimcongress_exhibitors_complete.xlsx'):
        """
        Save all scraped data to Excel file
        
        Args:
            filename: Name of the output Excel file
        """
        if not self.all_data:
            logging.warning("No data to save")
            print("⚠️ No data to save")
            return
        
        try:
            df = pd.DataFrame(self.all_data)
            df.to_excel(filename, index=False)
            logging.info(f"✅ Data saved to {filename}")
            print(f"✅ Data saved to {filename}")
            print(f"📊 Total records: {len(df)}")
        except Exception as e:
            logging.error(f"Error saving to Excel: {e}")
            print(f"❌ Error saving to Excel: {e}")
            raise
    
    def close(self):
        """Close the browser"""
        if hasattr(self, 'driver'):
            self.driver.quit()
            logging.info("Browser closed")
            print("🔒 Browser closed")

def main():
    """Main function to run the scraper"""
    scraper = None
    try:
        scraper = AIMCongressScraper(headless=False)  # Set to True for headless mode
        scraper.scrape_all_exhibitors()
    except KeyboardInterrupt:
        print("\n⚠️ Scraping interrupted by user")
        logging.info("Scraping interrupted by user")
        if scraper:
            scraper.save_progress()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        print(f"❌ Fatal error: {e}")
        if scraper:
            scraper.save_progress()
        raise
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()
