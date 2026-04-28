"""
Hardware Fair Saudi Arabia 2025 Exhibitor List Scraper

This scraper extracts exhibitor data from:
https://exhibitors.hardwarefair-saudi.com/international-hardware-fair-saudi-arabia-2025/Exhibitor

The scraper handles:
- JavaScript pagination using searchFilter() function
- Opens all card detail pages in new tabs simultaneously for efficient data extraction
- Extracts: Company Name, Stand Number, Country, Website, Categories, About, Products, Brochures
- Closes tabs after extraction and moves to next page
- Saves to Excel file on exit (complete or interrupted)

Usage:
    python hardwarefare.py

Output:
    - hardwarefare_exhibitors.xlsx (final results)
    - hardwarefare_exhibitors_progress.xlsx (progress backup)
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

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
BASE_URL = "https://exhibitors.hardwarefair-saudi.com/international-hardware-fair-saudi-arabia-2025/Exhibitor"
ITEMS_PER_PAGE = 24
SAVE_FILE = "hardwarefare_exhibitors.xlsx"
PROGRESS_FILE = "hardwarefare_exhibitors_progress.xlsx"

class HardwareFairScraper:
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
            'Country': '',
            'Detail URL': '',
            'Image URL': ''
        }
        
        try:
            # Extract company name and detail URL
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
                
        except Exception as e:
            logging.warning(f"Error extracting card data: {e}")
        
        return data
    
    def extract_detail_page_data_from_tab(self, tab_handle):
        """
        Extract additional data from exhibitor detail page in a specific tab
        
        Args:
            tab_handle: Window handle of the tab to extract data from
            
        Returns:
            dict: Dictionary with additional data from detail page
        """
        detail_data = {
            'Website': '',
            'Categories': '',
            'About': '',
            'Products Count': '',
            'Brochures Count': '',
            'Logo URL': ''
        }
        
        try:
            # Switch to the tab
            self.driver.switch_to.window(tab_handle)
            time.sleep(0.5)  # Minimal wait for page load
            
            # Wait for company details section
            try:
                wait = WebDriverWait(self.driver, 8)
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "section.company-details"))
                )
            except TimeoutException:
                logging.warning(f"Timeout waiting for detail page in tab")
                return detail_data
            
            # Extract logo URL
            try:
                logo_elem = self.driver.find_element(By.CSS_SELECTOR, "div.logo-holder img")
                detail_data['Logo URL'] = logo_elem.get_attribute('src') or ''
            except:
                pass
            
            # Extract website URL
            try:
                website_container = self.driver.find_element(
                    By.XPATH,
                    "//div[contains(@class, 'd-flex') and .//i[contains(@class, 'fa-globe')]]"
                )
                website_elem = website_container.find_element(By.TAG_NAME, "a")
                detail_data['Website'] = website_elem.get_attribute('href') or website_elem.text.strip()
            except:
                pass
            
            # Extract categories
            try:
                badges = self.driver.find_elements(By.CSS_SELECTOR, "span.badge.bg-secondary")
                categories = [badge.text.strip() for badge in badges if badge.text.strip()]
                detail_data['Categories'] = ', '.join(categories)
            except:
                pass
            
            # Extract About section
            try:
                about_elem = self.driver.find_element(By.CSS_SELECTOR, "div#pills-About p")
                detail_data['About'] = about_elem.text.strip()
            except:
                pass
            
            # Count products
            try:
                products = self.driver.find_elements(By.CSS_SELECTOR, "div#pills-Products .col")
                detail_data['Products Count'] = str(len(products))
            except:
                pass
            
            # Count brochures
            try:
                brochures = self.driver.find_elements(By.CSS_SELECTOR, "div#pills-Brochures tbody tr")
                detail_data['Brochures Count'] = str(len(brochures))
            except:
                pass
                    
        except Exception as e:
            logging.warning(f"Error extracting detail page data from tab: {e}")
        
        return detail_data
    
    def scrape_page(self, offset, page_num):
        """
        Scrape a single page by opening all card detail pages in new tabs simultaneously
        
        Args:
            offset: The offset value to pass to searchFilter (0, 24, 48, etc.)
            page_num: Current page number (for fallback pagination)
            
        Returns:
            list: List of exhibitor data dictionaries
        """
        page_data = []
        main_window = None
        
        try:
            # Store main window handle
            main_window = self.driver.current_window_handle
            
            # Call searchFilter JavaScript function
            try:
                logging.info(f"Calling searchFilter({offset})...")
                self.driver.execute_script(f"searchFilter({offset});")
                time.sleep(2)  # Reduced wait time
            except Exception as e:
                logging.warning(f"Could not call searchFilter directly: {e}")
                self.click_pagination_button(page_num)
                time.sleep(2)
            
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
            
            # Collect all card data and URLs from the listing page
            card_urls = []
            for idx, card in enumerate(cards, 1):
                try:
                    card_data = self.extract_card_data(card)
                    if card_data['Company Name'] and card_data['Detail URL']:
                        card_urls.append({
                            'data': card_data,
                            'url': card_data['Detail URL']
                        })
                except Exception as e:
                    logging.warning(f"  ⚠️ Error extracting card {idx} data: {e}")
                    continue
            
            logging.info(f"Collected {len(card_urls)} card URLs to process")
            
            if not card_urls:
                logging.warning("No card URLs found to process")
                return page_data
            
            # Step 1: Open ALL detail pages in new tabs simultaneously (FAST)
            logging.info(f"📂 Opening {len(card_urls)} detail pages in new tabs simultaneously...")
            
            # Open all tabs as fast as possible
            for idx, card_info in enumerate(card_urls, 1):
                if self.interrupted:
                    break
                try:
                    detail_url = card_info['url']
                    self.driver.execute_script(f"window.open('{detail_url}', '_blank');")
                    # No sleep between tab opens - maximum speed
                except Exception as e:
                    logging.warning(f"  ⚠️ Error opening tab {idx}: {e}")
                    continue
            
            # Get all window handles (main + new tabs)
            time.sleep(1)  # Small wait for all tabs to open
            all_handles = self.driver.window_handles
            tab_handles = [handle for handle in all_handles if handle != main_window]
            
            logging.info(f"✅ Opened {len(tab_handles)} tabs. Now extracting data from all tabs...")
            
            # Step 2: Extract data from each tab (parallel processing)
            for idx, card_info in enumerate(card_urls, 1):
                if self.interrupted:
                    break
                
                try:
                    card_data = card_info['data'].copy()
                    
                    # Get corresponding tab handle
                    if idx <= len(tab_handles):
                        tab_handle = tab_handles[idx - 1]
                        logging.info(f"  📋 Tab {idx}/{len(card_urls)}: {card_data['Company Name']}")
                        
                        # Extract detail page data from this tab
                        detail_data = self.extract_detail_page_data_from_tab(tab_handle)
                        
                        # Merge detail data into card data
                        card_data.update(detail_data)
                    else:
                        logging.warning(f"  ⚠️ No tab available for card {idx}, using card data only")
                    
                    # Add to page data
                    page_data.append(card_data)
                    logging.info(f"    ✓ {card_data['Company Name']} - {card_data['Stand Number']} - {card_data['Country']}")
                    if card_data.get('Website'):
                        logging.info(f"      🌐 Website: {card_data['Website']}")
                    
                except Exception as e:
                    logging.error(f"  ❌ Error processing card {idx}: {e}")
                    # Still add the card data even if detail page failed
                    try:
                        if card_data.get('Company Name'):
                            page_data.append(card_data)
                    except:
                        pass
                    continue
            
            # Step 3: Close ALL tabs quickly and return to main window
            logging.info(f"🗑️ Closing {len(tab_handles)} tabs...")
            self.driver.switch_to.window(main_window)
            
            # Close all tabs quickly
            for tab_handle in tab_handles:
                try:
                    self.driver.switch_to.window(tab_handle)
                    self.driver.close()
                except:
                    pass
            
            # Switch back to main window
            self.driver.switch_to.window(main_window)
            
            # Ensure we're back on the listing page
            try:
                self.driver.execute_script(f"searchFilter({offset});")
                time.sleep(1)
            except:
                pass
            
            logging.info(f"✅ Page {page_num} complete: {len(page_data)} exhibitors scraped")
            
        except Exception as e:
            logging.error(f"Error scraping page with offset {offset}: {e}")
            import traceback
            traceback.print_exc()
            
            # Make sure we're back on main window even if error occurred
            try:
                if main_window:
                    self.driver.switch_to.window(main_window)
            except:
                pass
        
        return page_data
    
    def click_pagination_button(self, page_num):
        """
        Fallback method: Click pagination button for a specific page
        
        Args:
            page_num: Page number to navigate to
        """
        try:
            pagination_buttons = self.driver.find_elements(By.CSS_SELECTOR, "div.pagination a.page-link")
            for button in pagination_buttons:
                if button.text.strip() == str(page_num):
                    self.driver.execute_script("arguments[0].click();", button)
                    logging.info(f"Clicked pagination button for page {page_num}")
                    return
            
            if page_num > 1:
                next_buttons = self.driver.find_elements(By.XPATH, "//a[contains(@onclick, 'searchFilter') and contains(text(), '»')]")
                if next_buttons:
                    self.driver.execute_script("arguments[0].click();", next_buttons[0])
                    logging.info(f"Clicked 'Next' button")
        except Exception as e:
            logging.warning(f"Could not click pagination button: {e}")
    
    def get_total_pages(self):
        """Determine total number of pages from pagination"""
        try:
            # Look for pagination text like "Showing 1 to 24 of 184"
            pagination_text = self.driver.find_element(By.CSS_SELECTOR, "div.pagination").text
            import re
            match = re.search(r'of\s+(\d+)', pagination_text)
            if match:
                total_items = int(match.group(1))
                total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
                logging.info(f"Found {total_items} total items, {total_pages} pages")
                return total_pages
        except:
            pass
        
        # Fallback: try to find last page number
        try:
            last_button = self.driver.find_element(By.XPATH, "//a[contains(@onclick, 'searchFilter') and contains(text(), 'Last')]")
            onclick = last_button.get_attribute('onclick')
            import re
            match = re.search(r'searchFilter\((\d+)\)', onclick)
            if match:
                last_offset = int(match.group(1))
                total_pages = (last_offset // ITEMS_PER_PAGE) + 1
                return total_pages
        except:
            pass
        
        # Default fallback
        return 8
    
    def scrape_all_pages(self):
        """Scrape all pages"""
        try:
            logging.info(f"Navigating to {BASE_URL}")
            self.driver.get(BASE_URL)
            time.sleep(4)  # Wait for initial page load
            
            # Get total pages
            total_pages = self.get_total_pages()
            logging.info(f"Total pages to scrape: {total_pages}")
            
            # Scrape all pages
            for page_num in range(1, total_pages + 1):
                # Check if interrupted
                if self.interrupted:
                    logging.warning("Scraping interrupted. Saving progress...")
                    break
                
                offset = (page_num - 1) * ITEMS_PER_PAGE
                logging.info(f"\n{'='*60}")
                logging.info(f"Scraping page {page_num}/{total_pages} (offset: {offset})")
                logging.info(f"{'='*60}")
                
                page_data = self.scrape_page(offset, page_num)
                self.all_data.extend(page_data)
                
                logging.info(f"Page {page_num} complete: {len(page_data)} exhibitors scraped")
                logging.info(f"Total so far: {len(self.all_data)} exhibitors")
                
                # Save progress after each page
                self.save_progress()
                
                # Small delay between pages
                time.sleep(1)
            
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
    print("Hardware Fair Saudi Arabia 2025 - Exhibitor Scraper")
    print("="*60)
    print(f"URL: {BASE_URL}")
    print("Note: This scraper opens all card detail pages simultaneously")
    print("      for maximum speed and efficiency")
    print("Press Ctrl+C to interrupt and save data to Excel")
    print("="*60)
    print("\nStarting scraper...\n")
    
    scraper = HardwareFairScraper(headless=False)
    scraper.scrape_all_pages()
    
    print("\n✅ Scraping completed successfully!")

if __name__ == "__main__":
    main()
