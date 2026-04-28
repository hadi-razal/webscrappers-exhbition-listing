"""
FSB Sports Show Riyadh 2025 Exhibitor List Scraper

This scraper extracts exhibitor data from:
https://exhibitors.fsb-riyadh.com/fsb-sports-show-riyadh-2025/Exhibitor

The scraper handles:
- JavaScript pagination using searchFilter() function
- Extracts: Company Name, Stand Number, Country, Detail URL
- Saves to Excel file

Usage:
    python fsbsports.py

Output:
    - fsbsports_exhibitors.xlsx
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time
import logging
import signal
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
BASE_URL = "https://exhibitors.fsb-riyadh.com/fsb-sports-show-riyadh-2025/Exhibitor"
ITEMS_PER_PAGE = 7
TOTAL_EXHIBITORS = 166  # Total exhibitors from pagination
TOTAL_PAGES = 24  # 166 / 7 = 23.71, rounded up to 24
SAVE_FILE = "fsbsports_exhibitors.xlsx"
PROGRESS_FILE = "fsbsports_exhibitors_progress.xlsx"

class FSBSportsScraper:
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
            logging.warning("\n⚠️ Interrupt received! Saving progress...")
            self.interrupted = True
            self.save_progress()
            self.cleanup()
            sys.exit(0)
        
        # Setup signal handlers (SIGTERM not available on Windows)
        try:
            signal.signal(signal.SIGINT, signal_handler)
            if hasattr(signal, 'SIGTERM'):
                signal.signal(signal.SIGTERM, signal_handler)
        except (ValueError, AttributeError):
            # Windows compatibility
            pass
        
    def extract_card_data(self, card_element):
        """
        Extract data from a single exhibitor card
        
        Args:
            card_element: WebElement representing an exhibitor card
            
        Returns:
            dict: Dictionary with exhibitor data
        """
        data = {
            'Company Name': '',
            'Stand Number': '',
            'Country': '',
            'Detail URL': '',
            'Image URL': '',
            'Is Featured': False
        }
        
        try:
            # Extract company name
            try:
                title_elem = card_element.find_element(By.CSS_SELECTOR, "h5.card-title a")
                data['Company Name'] = title_elem.text.strip()
                data['Detail URL'] = title_elem.get_attribute('href') or ''
            except:
                try:
                    title_elem = card_element.find_element(By.CSS_SELECTOR, "h5.card-title")
                    data['Company Name'] = title_elem.text.strip()
                except:
                    pass
            
            # Extract stand number
            try:
                stand_elem = card_element.find_element(By.CSS_SELECTOR, "h6.card-subtitle")
                stand_text = stand_elem.text.strip()
                # Remove "Stand No- " prefix if present
                if "Stand No-" in stand_text:
                    data['Stand Number'] = stand_text.replace("Stand No-", "").strip()
                elif "Sponsor" in stand_text:
                    data['Stand Number'] = "Sponsor"
                else:
                    data['Stand Number'] = stand_text
            except:
                pass
            
            # Extract country
            try:
                country_elem = card_element.find_element(By.CSS_SELECTOR, "p.card-text")
                data['Country'] = country_elem.text.strip()
            except:
                pass
            
            # Extract image URL
            try:
                img_elem = card_element.find_element(By.CSS_SELECTOR, "img.card-img-top")
                data['Image URL'] = img_elem.get_attribute('src') or ''
            except:
                pass
            
            # Check if featured
            try:
                featured_badge = card_element.find_element(By.CSS_SELECTOR, "span.featured-badge")
                data['Is Featured'] = True
            except:
                data['Is Featured'] = False
                
        except Exception as e:
            logging.warning(f"Error extracting card data: {e}")
        
        return data
    
    def scrape_page(self, offset, page_num):
        """
        Scrape a single page by calling searchFilter with offset
        
        Args:
            offset: The offset value to pass to searchFilter (0, 7, 14, etc.)
            page_num: Current page number (for fallback pagination)
            
        Returns:
            list: List of exhibitor data dictionaries
        """
        page_data = []
        
        try:
            # Method 1: Try calling searchFilter JavaScript function directly
            try:
                logging.info(f"Calling searchFilter({offset})...")
                self.driver.execute_script(f"searchFilter({offset});")
                time.sleep(3)
            except Exception as e:
                logging.warning(f"Could not call searchFilter directly: {e}")
                # Fallback: Try clicking pagination button
                self.click_pagination_button(page_num)
                time.sleep(3)
            
            # Wait for cards to be present
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.col-md-3.mb-3"))
                )
            except:
                logging.warning(f"Timeout waiting for cards on offset {offset}")
            
            # Get all card elements
            cards = self.driver.find_elements(By.CSS_SELECTOR, "div.col-md-3.mb-3")
            logging.info(f"Found {len(cards)} cards on page with offset {offset}")
            
            # Extract data from each card
            for card in cards:
                card_data = self.extract_card_data(card)
                if card_data['Company Name']:  # Only add if we got a company name
                    page_data.append(card_data)
                    logging.info(f"  ✓ {card_data['Company Name']} - {card_data['Stand Number']} - {card_data['Country']}")
            
        except Exception as e:
            logging.error(f"Error scraping page with offset {offset}: {e}")
            import traceback
            traceback.print_exc()
        
        return page_data
    
    def click_pagination_button(self, page_num):
        """
        Fallback method: Click pagination button for a specific page
        
        Args:
            page_num: Page number to navigate to
        """
        try:
            # Try to find and click the page number button
            pagination_buttons = self.driver.find_elements(By.CSS_SELECTOR, "div.pagination a.page-link")
            for button in pagination_buttons:
                if button.text.strip() == str(page_num):
                    self.driver.execute_script("arguments[0].click();", button)
                    logging.info(f"Clicked pagination button for page {page_num}")
                    return
            
            # If page number not found, try clicking "Next" button
            if page_num > 1:
                next_buttons = self.driver.find_elements(By.XPATH, "//a[contains(@onclick, 'searchFilter') and contains(text(), '»')]")
                if next_buttons:
                    self.driver.execute_script("arguments[0].click();", next_buttons[0])
                    logging.info(f"Clicked 'Next' button")
        except Exception as e:
            logging.warning(f"Could not click pagination button: {e}")
    
    def scrape_all_pages(self):
        """Scrape all pages"""
        try:
            logging.info(f"Navigating to {BASE_URL}")
            self.driver.get(BASE_URL)
            time.sleep(5)  # Wait for initial page load
            
            # Scrape all pages
            for page_num in range(1, TOTAL_PAGES + 1):
                # Check if interrupted
                if self.interrupted:
                    logging.warning("Scraping interrupted. Saving progress...")
                    break
                
                offset = (page_num - 1) * ITEMS_PER_PAGE
                logging.info(f"\n{'='*60}")
                logging.info(f"Scraping page {page_num}/{TOTAL_PAGES} (offset: {offset})")
                logging.info(f"{'='*60}")
                
                page_data = self.scrape_page(offset, page_num)
                self.all_data.extend(page_data)
                
                logging.info(f"Page {page_num} complete: {len(page_data)} exhibitors scraped")
                logging.info(f"Total so far: {len(self.all_data)} exhibitors")
                
                # If we've reached or exceeded the total, stop
                if len(self.all_data) >= TOTAL_EXHIBITORS:
                    logging.info(f"Reached total of {TOTAL_EXHIBITORS} exhibitors. Stopping.")
                    break
                
                # If no data found on a page, we might have reached the end
                if len(page_data) == 0 and page_num > 1:
                    logging.info("No data found on this page. Possibly reached the end.")
                    break
                
                # Save progress after each page
                self.save_progress()
                
                # Small delay between pages
                time.sleep(2)
            
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
            logging.warning("\n⚠️ Keyboard interrupt received! Saving progress...")
            self.interrupted = True
            self.save_progress()
        except Exception as e:
            logging.error(f"Error in scraping process: {e}")
            import traceback
            traceback.print_exc()
            self.save_progress()
        finally:
            if not self.interrupted:
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
    print("FSB Sports Show Riyadh 2025 - Exhibitor Scraper")
    print("="*60)
    print(f"URL: {BASE_URL}")
    print(f"Total Pages: {TOTAL_PAGES}")
    print(f"Items per Page: {ITEMS_PER_PAGE}")
    print(f"Expected Total: ~{TOTAL_EXHIBITORS} exhibitors")
    print(f"Progress will be saved to: {PROGRESS_FILE}")
    print("Press Ctrl+C to interrupt and save progress")
    print("="*60)
    print("\nStarting scraper...\n")
    
    scraper = FSBSportsScraper(headless=False)
    scraper.scrape_all_pages()
    
    print("\n✅ Scraping completed successfully!")

if __name__ == "__main__":
    main()
