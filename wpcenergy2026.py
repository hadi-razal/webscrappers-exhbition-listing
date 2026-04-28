"""
WPC Energy 2026 Exhibitor List Scraper

This scraper extracts exhibitor data from:
https://wpcenergy2026.org/exhibitors/

The scraper handles:
- Extracts exhibitor cards from listing page
- Visits each detail page to get additional information
- Extracts: Company Name, Stand Number, Hall, Logo URL, Description, Address, Website, Social Media Links
- Saves to Excel file on exit (complete or interrupted)

Usage:
    python wpcenergy2026.py

Output:
    - wpcenergy2026_exhibitors.xlsx (final results)
    - wpcenergy2026_exhibitors_progress.xlsx (progress backup)
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import time
import logging
import signal
import sys
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
BASE_URL = "https://wpcenergy2026.org/exhibitors/"
SAVE_FILE = "wpcenergy2026_exhibitors.xlsx"
PROGRESS_FILE = "wpcenergy2026_exhibitors_progress.xlsx"

class WPCEnergyScraper:
    def __init__(self, headless=False):
        """
        Initialize the scraper
        
        Args:
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        self.all_data = []
        self.interrupted = False
        self.setup_driver()
        self.setup_signal_handlers()
        
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
        chrome_options.add_argument("--start-maximized")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 20)
    
    def setup_signal_handlers(self):
        """Setup signal handlers to catch interrupts and save progress"""
        def signal_handler(sig, frame):
            logging.warning("\n⚠️ Interrupt received! Saving data to Excel...")
            self.interrupted = True
            self.save_to_excel()
            self.cleanup()
            sys.exit(0)
        
        try:
            signal.signal(signal.SIGINT, signal_handler)
            if hasattr(signal, 'SIGTERM'):
                signal.signal(signal.SIGTERM, signal_handler)
        except (ValueError, AttributeError):
            pass
    
    def extract_card_data(self, card_element):
        """
        Extract data from a single exhibitor card on listing page
        
        Args:
            card_element: WebElement representing an exhibitor card
            
        Returns:
            dict: Dictionary with exhibitor data from card
        """
        data = {
            'Company Name': '',
            'Stand Number': '',
            'Hall': '',
            'Detail URL': '',
            'Logo URL': ''
        }
        
        try:
            # Extract company name - try multiple strategies
            name_found = False
            
            # Strategy 1: Try specific selector (based on observed structure)
            try:
                name_elem = card_element.find_element(By.CSS_SELECTOR, "div.fusion-text-2 p")
                name_text = name_elem.text.strip()
                if name_text:
                    data['Company Name'] = name_text
                    name_found = True
            except Exception:
                pass
            
            # Strategy 2: Try all paragraph elements in fusion-text divs
            if not name_found:
                try:
                    text_divs = card_element.find_elements(By.CSS_SELECTOR, "div.fusion-text p, div.fusion-text-2 p, div.fusion-text-3 p")
                    for elem in text_divs:
                        text = elem.text.strip()
                        if not text:
                            continue
                        # Skip lines that are clearly not company names
                        lower = text.lower()
                        if "stand " in lower or "hall " in lower:
                            continue
                        if "visit website" in lower or "more info" in lower or "learn more" in lower:
                            continue
                        # If we find a reasonable text, use it
                        if len(text) > 2 and len(text) < 150:
                            data['Company Name'] = text
                            name_found = True
                            break
                except Exception:
                    pass
            
            # Strategy 3: Try common heading / text elements inside the card
            if not name_found:
                try:
                    name_candidates = card_element.find_elements(
                        By.CSS_SELECTOR,
                        "h1, h2, h3, h4, h5, h6, .fusion-title, .fusion-title-heading, p"
                    )
                    best_name = ""
                    for elem in name_candidates:
                        text = elem.text.strip()
                        if not text:
                            continue
                        # Skip lines that are clearly not company names
                        lower = text.lower()
                        if "stand " in lower or "hall " in lower:
                            continue
                        if "visit website" in lower or "more info" in lower or "learn more" in lower:
                            continue
                        # Skip if it's just a number or very short
                        if len(text) < 2 or len(text) > 150:
                            continue
                        # Keep the longest reasonable candidate
                        if len(text) > len(best_name):
                            best_name = text
                    if best_name:
                        data['Company Name'] = best_name
                        name_found = True
                except Exception:
                    pass
            
            # Strategy 4: Try to get from image alt attribute
            if not name_found:
                try:
                    img_elem = card_element.find_element(By.CSS_SELECTOR, "img")
                    alt_text = img_elem.get_attribute('alt') or ''
                    if alt_text and len(alt_text) > 2 and len(alt_text) < 150:
                        # Clean up alt text (remove common suffixes)
                        alt_text = alt_text.replace(' logo', '').replace(' Logo', '').strip()
                        data['Company Name'] = alt_text
                        name_found = True
                except Exception:
                    pass
            
            # Extract stand and hall info
            try:
                stand_elem = card_element.find_element(By.CSS_SELECTOR, "div.stand-label p")
                stand_text = stand_elem.text.strip()
                # Parse "Stand 1360 | Hall 1" format
                if "|" in stand_text:
                    parts = stand_text.split("|")
                    stand_part = parts[0].strip()
                    hall_part = parts[1].strip() if len(parts) > 1 else ''
                    
                    # Extract stand number
                    stand_match = re.search(r'Stand\s+(\S+)', stand_part)
                    if stand_match:
                        data['Stand Number'] = stand_match.group(1)
                    
                    # Extract hall number
                    hall_match = re.search(r'Hall\s+(\S+)', hall_part)
                    if hall_match:
                        data['Hall'] = hall_match.group(1)
                else:
                    # Try to extract stand number from text
                    stand_match = re.search(r'Stand\s+(\S+)', stand_text)
                    if stand_match:
                        data['Stand Number'] = stand_match.group(1)
                    
                    # Try to extract hall number from text
                    hall_match = re.search(r'Hall\s+(\S+)', stand_text)
                    if hall_match:
                        data['Hall'] = hall_match.group(1)
            except:
                pass
            
            # Extract detail URL - try multiple selectors
            try:
                # First try the "More info" link
                link_elem = card_element.find_element(By.CSS_SELECTOR, "a[href*='/exhibitor/']")
                detail_url = link_elem.get_attribute('href') or ''
                if detail_url and not detail_url.startswith('http'):
                    detail_url = f"https://wpcenergy2026.org{detail_url}"
                data['Detail URL'] = detail_url
            except:
                try:
                    # Fallback: try image link
                    link_elem = card_element.find_element(By.CSS_SELECTOR, "a.fusion-no-lightbox[href*='/exhibitor/']")
                    detail_url = link_elem.get_attribute('href') or ''
                    if detail_url and not detail_url.startswith('http'):
                        detail_url = f"https://wpcenergy2026.org{detail_url}"
                    data['Detail URL'] = detail_url
                except:
                    pass
            
            # Extract logo URL
            try:
                img_elem = card_element.find_element(By.CSS_SELECTOR, "img")
                data['Logo URL'] = img_elem.get_attribute('src') or img_elem.get_attribute('data-orig-src') or ''
            except:
                pass
                
        except Exception as e:
            logging.warning(f"Error extracting card data: {e}")
        
        return data
    
    def extract_detail_page_data(self, detail_url):
        """
        Extract additional data from exhibitor detail page
        
        Args:
            detail_url: URL of the detail page
            
        Returns:
            dict: Dictionary with additional data from detail page
        """
        detail_data = {
            'Company Name': '',  # Will be extracted from detail page if missing
            'Description': '',
            'Address': '',
            'Website': '',
            'Facebook': '',
            'LinkedIn': '',
            'Twitter': ''
        }
        
        try:
            # Navigate to detail page
            self.driver.get(detail_url)
            time.sleep(2)  # Wait for page to load
            
            # Wait for main content
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.fusion-title-heading"))
                )
            except TimeoutException:
                logging.warning(f"Timeout waiting for detail page: {detail_url}")
                return detail_data
            
            # Extract company name from detail page heading (if not found on card)
            try:
                name_elem = self.driver.find_element(By.CSS_SELECTOR, "h1.fusion-title-heading")
                company_name = name_elem.text.strip()
                if company_name:
                    detail_data['Company Name'] = company_name
            except:
                pass
            
            # Extract description
            try:
                desc_elem = self.driver.find_element(By.CSS_SELECTOR, "div.fusion-text-4")
                # Get all paragraph text
                paragraphs = desc_elem.find_elements(By.TAG_NAME, "p")
                description_text = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
                if description_text:
                    detail_data['Description'] = description_text
            except:
                pass
            
            # Extract address
            try:
                address_elem = self.driver.find_element(By.CSS_SELECTOR, "div.fusion-text-6 p")
                detail_data['Address'] = address_elem.text.strip()
            except:
                pass
            
            # Extract website - try multiple selectors
            try:
                # Try button with "Visit website" text
                website_elem = self.driver.find_element(By.XPATH, "//a[contains(@class, 'fusion-button') and contains(@href, 'http')]")
                detail_data['Website'] = website_elem.get_attribute('href') or ''
            except:
                try:
                    # Fallback: try any link with http in href
                    website_elem = self.driver.find_element(By.CSS_SELECTOR, "a[href^='http']:not([href*='facebook']):not([href*='linkedin']):not([href*='twitter']):not([href*='x.com'])")
                    href = website_elem.get_attribute('href') or ''
                    # Only use if it's not a social media link
                    if href and 'facebook' not in href.lower() and 'linkedin' not in href.lower() and 'twitter' not in href.lower() and 'x.com' not in href.lower():
                        detail_data['Website'] = href
                except:
                    pass
            
            # Extract social media links
            try:
                social_links = self.driver.find_elements(By.CSS_SELECTOR, "a.fusion-social-network-icon")
                for link in social_links:
                    href = link.get_attribute('href') or ''
                    class_name = link.get_attribute('class') or ''
                    
                    if 'facebook' in class_name.lower() or 'facebook' in href.lower():
                        detail_data['Facebook'] = href
                    elif 'linkedin' in class_name.lower() or 'linkedin' in href.lower():
                        detail_data['LinkedIn'] = href
                    elif 'twitter' in class_name.lower() or 'x.com' in href.lower() or 'twitter.com' in href.lower():
                        detail_data['Twitter'] = href
            except:
                pass
                    
        except Exception as e:
            logging.warning(f"Error extracting detail page data from {detail_url}: {e}")
        
        return detail_data
    
    def get_all_cards(self):
        """
        Get all exhibitor cards from the listing page
        
        Returns:
            list: List of card WebElements
        """
        cards = []
        try:
            # Wait for cards to load
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.fusion-column-wrapper.fusion-column-has-shadow"))
            )
            time.sleep(3)  # Give page time to render
            
            # Scroll to load all content (lazy loading might be used)
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            while True:
                # Scroll down to bottom
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                
                # Calculate new scroll height and compare with last scroll height
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Find all exhibitor cards
            # Cards are in divs with class "fusion-column-wrapper fusion-column-has-shadow"
            # that contain a "stand-label" div
            card_containers = self.driver.find_elements(By.CSS_SELECTOR, "div.fusion-column-wrapper.fusion-column-has-shadow")
            
            # Filter to only cards that have stand-label (exhibitor cards)
            for container in card_containers:
                try:
                    # Check if this container has a stand-label (indicating it's an exhibitor card)
                    container.find_element(By.CSS_SELECTOR, "div.stand-label")
                    cards.append(container)
                except:
                    # Not an exhibitor card, skip
                    continue
            
            logging.info(f"Found {len(cards)} exhibitor cards")
            
        except Exception as e:
            logging.error(f"Error getting cards: {e}")
        
        return cards
    
    def scrape_all_exhibitors(self):
        """Scrape all exhibitors from the listing page"""
        try:
            logging.info(f"Navigating to {BASE_URL}")
            self.driver.get(BASE_URL)
            time.sleep(4)  # Wait for initial page load
            
            # Get all cards (includes scrolling to load all content)
            cards = self.get_all_cards()
            
            if not cards:
                logging.warning("No exhibitor cards found!")
                return
            
            logging.info(f"\n{'='*60}")
            logging.info(f"Found {len(cards)} exhibitors to scrape")
            logging.info(f"{'='*60}\n")
            
            # Process each card
            for idx, card in enumerate(cards, 1):
                if self.interrupted:
                    logging.warning("Scraping interrupted. Saving progress...")
                    break
                
                try:
                    logging.info(f"\n📋 Processing exhibitor {idx}/{len(cards)}")
                    
                    # Extract card data
                    card_data = self.extract_card_data(card)
                    
                    # Log what we found on the card
                    if card_data.get('Company Name'):
                        logging.info(f"  Company (from card): {card_data['Company Name']}")
                    else:
                        logging.info(f"  Company (from card): Not found - will try detail page")
                    logging.info(f"  Stand: {card_data.get('Stand Number', 'N/A')} | Hall: {card_data.get('Hall', 'N/A')}")
                    
                    # Extract detail page data if URL is available
                    if card_data.get('Detail URL'):
                        logging.info(f"  🔍 Visiting detail page...")
                        detail_data = self.extract_detail_page_data(card_data['Detail URL'])
                        
                        # If company name wasn't found on card, use the one from detail page
                        if not card_data.get('Company Name') and detail_data.get('Company Name'):
                            card_data['Company Name'] = detail_data['Company Name']
                            logging.info(f"  ✓ Company (from detail page): {card_data['Company Name']}")
                        
                        # Merge detail data into card data (but don't overwrite company name if we already have it)
                        for key, value in detail_data.items():
                            if key != 'Company Name' or not card_data.get('Company Name'):
                                if value:  # Only update if there's a value
                                    card_data[key] = value
                        
                        if detail_data.get('Description'):
                            logging.info(f"    ✓ Description: {len(detail_data['Description'])} chars")
                        if detail_data.get('Website'):
                            logging.info(f"    🌐 Website: {detail_data['Website']}")
                        if detail_data.get('Address'):
                            logging.info(f"    📍 Address: {detail_data['Address']}")
                    else:
                        logging.warning(f"  ⚠️ No detail URL found")
                    
                    # Final check: if we still don't have a company name, log a warning but continue
                    if not card_data.get('Company Name'):
                        logging.warning(f"  ⚠️ Could not extract company name for card {idx}")
                    
                    # Add to all data
                    self.all_data.append(card_data)
                    logging.info(f"  ✅ Completed: {card_data['Company Name']}")
                    
                    # Save progress after each exhibitor
                    if idx % 10 == 0:
                        self.save_progress()
                    
                    # Small delay between requests
                    time.sleep(1)
                    
                except Exception as e:
                    logging.error(f"  ❌ Error processing card {idx}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            if not self.interrupted:
                logging.info(f"\n{'='*60}")
                logging.info(f"✅ SCRAPING COMPLETE!")
                logging.info(f"Total exhibitors scraped: {len(self.all_data)}")
                logging.info(f"{'='*60}\n")
            else:
                logging.info(f"\n{'='*60}")
                logging.info(f"⚠️ SCRAPING INTERRUPTED!")
                logging.info(f"Total exhibitors scraped: {len(self.all_data)}")
                logging.info(f"Progress saved to {PROGRESS_FILE}")
                logging.info(f"{'='*60}\n")
            
        except KeyboardInterrupt:
            logging.warning("\n⚠️ Keyboard interrupt received! Saving data to Excel...")
            self.interrupted = True
            self.save_to_excel()
        except Exception as e:
            logging.error(f"Error in scraping process: {e}")
            import traceback
            traceback.print_exc()
            self.save_to_excel()
        finally:
            logging.info("💾 Saving data to Excel on exit...")
            self.save_to_excel()
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
        except:
            pass
    
    def save_progress(self):
        """Save progress to Excel file (intermediate save)"""
        if not self.all_data:
            return
        
        try:
            df = pd.DataFrame(self.all_data)
            df.to_excel(PROGRESS_FILE, index=False)
            logging.info(f"💾 Progress saved: {len(self.all_data)} exhibitors to {PROGRESS_FILE}")
        except Exception as e:
            logging.error(f"Error saving progress: {e}")
    
    def save_to_excel(self):
        """Save all scraped data to final Excel file"""
        if not self.all_data:
            logging.warning("No data to save!")
            return
        
        try:
            df = pd.DataFrame(self.all_data)
            df.to_excel(SAVE_FILE, index=False)
            logging.info(f"💾 Saved {len(self.all_data)} exhibitors to {SAVE_FILE}")
        except Exception as e:
            logging.error(f"Error saving to Excel: {e}")

def main():
    """Main function to run the scraper"""
    print("="*60)
    print("WPC Energy 2026 - Exhibitor Scraper")
    print("="*60)
    print(f"URL: {BASE_URL}")
    print("Press Ctrl+C to interrupt and save data to Excel")
    print("="*60)
    print("\nStarting scraper...\n")
    
    scraper = WPCEnergyScraper(headless=False)
    scraper.scrape_all_exhibitors()
    
    # Use plain ASCII characters to avoid Windows console encoding issues
    print("\nScraping completed successfully!")

if __name__ == "__main__":
    main()
