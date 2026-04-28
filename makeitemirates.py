"""
MIITE (Make it in the Emirates) Exhibitor List Scraper

This scraper extracts exhibitor data from the MIITE website:
- Exhibitor name, logo, classification, country
- Website and social media links (Twitter, LinkedIn, Instagram, Facebook, YouTube)
- Stand numbers and map links
- Products, Brochures, and News counts

The scraper handles:
- Dynamic Vue.js content using Selenium
- Pagination (automatically detects and navigates through all pages)
- Progress saving (auto-saves every 20 exhibitors)
- Final export to Excel

Usage:
    python makeitemirates.py

Output:
    - miite_exhibitors_progress.xlsx (intermediate saves)
    - miite_exhibitors_complete.xlsx (final output)
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
import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MIITEScraper:
    def __init__(self, base_url="https://www.miite.ae/exhibit/exhibitor-list-2025/", headless=True):
        """
        Initialize the MIITE scraper
        
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
        
    def extract_exhibitor_card_data(self, card):
        """
        Extract data from a single exhibitor card
        
        Args:
            card: WebElement representing an exhibitor card
            
        Returns:
            dict: Dictionary with exhibitor data
        """
        print(f"\n    🔍 Starting data extraction from card...")
        logging.info("Starting to extract data from exhibitor card")
        
        data = {
            'Exhibitor Name': '',
            'Logo URL': '',
            'Classification': '',
            'Country': '',
            'Website': '',
            'Stand Numbers': '',
            'Stand Map Links': '',
            'Twitter': '',
            'LinkedIn': '',
            'Instagram': '',
            'Facebook': '',
            'YouTube': '',
            'Products Count': '',
            'Brochures Count': '',
            'News Count': ''
        }
        
        try:
            # Extract exhibitor name
            try:
                # Try primary selector
                name_elem = card.find_element(By.CSS_SELECTOR, ".v-card-title")
                data['Exhibitor Name'] = name_elem.text.strip()
            except NoSuchElementException:
                # Try alternative selectors
                try:
                    name_elem = card.find_element(By.CSS_SELECTOR, ".v-card-title.cursor-pointer")
                    data['Exhibitor Name'] = name_elem.text.strip()
                except NoSuchElementException:
                    try:
                        # Try finding by XPath
                        name_elem = card.find_element(By.XPATH, ".//div[contains(@class, 'v-card-title')]")
                        data['Exhibitor Name'] = name_elem.text.strip()
                    except NoSuchElementException:
                        print("    ⚠️ Exhibitor Name: NOT FOUND - tried multiple selectors")
                        logging.warning("Could not extract Exhibitor Name with any selector")
            
            if data['Exhibitor Name']:
                print(f"    📝 Exhibitor Name: {data['Exhibitor Name']}")
                logging.info(f"Extracted Exhibitor Name: {data['Exhibitor Name']}")
            else:
                print("    ⚠️ Exhibitor Name: NOT FOUND")
                logging.warning("Could not extract Exhibitor Name")
            
            # Extract logo URL
            try:
                img_elem = card.find_element(By.CSS_SELECTOR, ".v-img__img")
                data['Logo URL'] = img_elem.get_attribute('src') or ''
                if data['Logo URL']:
                    print(f"    🖼️ Logo URL: {data['Logo URL']}")
                    logging.info(f"Extracted Logo URL: {data['Logo URL']}")
                else:
                    print("    ⚠️ Logo URL: NOT FOUND")
            except NoSuchElementException:
                print("    ⚠️ Logo URL: NOT FOUND")
                logging.warning("Could not extract Logo URL")
            
            # Extract classification (Individual, etc.)
            try:
                classification_chip = card.find_element(By.CSS_SELECTOR, ".v-card-subtitle .v-chip.text-green")
                data['Classification'] = classification_chip.text.strip()
                if data['Classification']:
                    print(f"    🏷️ Classification: {data['Classification']}")
                    logging.info(f"Extracted Classification: {data['Classification']}")
                else:
                    print("    ⚠️ Classification: NOT FOUND")
            except NoSuchElementException:
                print("    ⚠️ Classification: NOT FOUND")
                logging.warning("Could not extract Classification")
            
            # Extract country - look in v-card-subtitle (but not the classification one)
            try:
                # Get all v-card-subtitle elements
                subtitle_elems = card.find_elements(By.CSS_SELECTOR, ".v-card-subtitle")
                for subtitle in subtitle_elems:
                    # Check if this subtitle contains a span (country) and not a chip (classification)
                    try:
                        # Look for span that's not inside a chip
                        country_span = subtitle.find_element(By.CSS_SELECTOR, "span:not(.v-chip span)")
                        country_text = country_span.text.strip()
                        # Skip if it's empty or contains classification keywords
                        if country_text and country_text not in ['Individual', 'Pavilion'] and 'Individual' not in country_text and 'Pavilion' not in country_text:
                            data['Country'] = country_text
                            break
                    except NoSuchElementException:
                        # Try direct text from subtitle if no span found
                        subtitle_text = subtitle.text.strip()
                        if subtitle_text and subtitle_text not in ['Individual', 'Pavilion'] and 'Individual' not in subtitle_text:
                            # Check if it's not the classification chip
                            try:
                                subtitle.find_element(By.CSS_SELECTOR, ".v-chip.text-green")
                                # This is the classification, skip it
                                continue
                            except:
                                data['Country'] = subtitle_text
                                break
            except NoSuchElementException:
                pass
            
            # Try alternative: look for country in the info section at bottom
            if not data['Country']:
                try:
                    # Look for the country info section with flag icon
                    country_sections = card.find_elements(By.XPATH, ".//div[contains(@class, 'v-card-text')]//i[contains(@class, 'mdi-flag-outline')]/parent::div")
                    for section in country_sections:
                        country_text = section.text.strip()
                        # The text should contain the country name after the icon
                        # Clean up any extra whitespace
                        country_text = ' '.join(country_text.split())
                        # Remove common prefixes
                        country_text = country_text.replace('United Arab Emirates', '').strip()
                        if country_text and len(country_text) > 2:
                            data['Country'] = country_text
                        else:
                            # If cleaned text is empty, the original might be the country
                            original_text = section.text.strip()
                            if original_text and len(original_text) > 2:
                                data['Country'] = original_text
                        if data['Country']:
                            break
                except Exception as e:
                    logging.debug(f"Error in alternative country extraction: {e}")
            
            if data['Country']:
                print(f"    🌍 Country: {data['Country']}")
                logging.info(f"Extracted Country: {data['Country']}")
            else:
                print("    ⚠️ Country: NOT FOUND")
                logging.warning("Could not extract Country")
            
            # Extract stand numbers and map links
            stand_numbers = []
            stand_links = []
            try:
                # Find all links that contain map.miite.ae in href
                stand_links_elements = card.find_elements(By.CSS_SELECTOR, "a[href*='map.miite.ae']")
                
                for stand_link_elem in stand_links_elements:
                    stand_link = stand_link_elem.get_attribute('href')
                    if stand_link:
                        stand_links.append(stand_link)
                    
                    # Try to get stand number from the link's text content
                    try:
                        # The stand number is in .v-chip__content inside the link
                        stand_content = stand_link_elem.find_element(By.CSS_SELECTOR, ".v-chip__content")
                        stand_text = stand_content.text.strip()
                        if stand_text:
                            stand_numbers.append(stand_text)
                    except NoSuchElementException:
                        # Fallback: get text directly from the link
                        stand_text = stand_link_elem.text.strip()
                        if stand_text and stand_text not in stand_numbers:
                            stand_numbers.append(stand_text)
                
                data['Stand Numbers'] = ', '.join(stand_numbers) if stand_numbers else ''
                data['Stand Map Links'] = ', '.join(stand_links) if stand_links else ''
                
                if data['Stand Numbers']:
                    print(f"    📍 Stand Numbers: {data['Stand Numbers']}")
                    logging.info(f"Extracted Stand Numbers: {data['Stand Numbers']}")
                else:
                    print("    ⚠️ Stand Numbers: NOT FOUND")
                    logging.warning("Could not extract Stand Numbers")
                    
                if data['Stand Map Links']:
                    print(f"    🗺️ Stand Map Links: {data['Stand Map Links']}")
                    logging.info(f"Extracted Stand Map Links: {data['Stand Map Links']}")
                else:
                    print("    ⚠️ Stand Map Links: NOT FOUND")
                    logging.warning("Could not extract Stand Map Links")
                    
            except NoSuchElementException:
                print("    ⚠️ Stand Numbers: NOT FOUND")
                logging.warning("Could not extract Stand Numbers")
            except Exception as e:
                print(f"    ⚠️ Stand Numbers: ERROR - {e}")
                logging.error(f"Error extracting stand numbers: {e}")
            
            # Extract website URL
            try:
                # First try: find link with web icon in button group
                website_link = card.find_element(By.CSS_SELECTOR, ".v-btn-group a i.mdi-web-box")
                website_elem = website_link.find_element(By.XPATH, "./ancestor::a")
                data['Website'] = website_elem.get_attribute('href') or ''
            except NoSuchElementException:
                # Try alternative: look in the info section at bottom
                try:
                    website_section = card.find_element(By.XPATH, ".//div[contains(@class, 'v-card-text')]//i[contains(@class, 'mdi-web-box')]/parent::div")
                    website_link = website_section.find_element(By.TAG_NAME, "a")
                    data['Website'] = website_link.get_attribute('href') or website_link.text.strip()
                except:
                    # Last resort: find any link with web icon
                    try:
                        web_icon = card.find_element(By.CSS_SELECTOR, "i.mdi-web-box")
                        website_elem = web_icon.find_element(By.XPATH, "./ancestor::a")
                        data['Website'] = website_elem.get_attribute('href') or ''
                    except:
                        pass
            
            if data['Website']:
                print(f"    🌐 Website: {data['Website']}")
                logging.info(f"Extracted Website: {data['Website']}")
            else:
                print("    ⚠️ Website: NOT FOUND")
                logging.warning("Could not extract Website")
            
            # Extract social media links
            try:
                social_links = card.find_elements(By.CSS_SELECTOR, ".v-btn-group a[href*='http']")
                for link in social_links:
                    href = link.get_attribute('href') or ''
                    if not href:
                        continue
                    
                    # Check icon class to determine platform
                    try:
                        icon = link.find_element(By.CSS_SELECTOR, "i")
                        icon_class = icon.get_attribute('class') or ''
                        
                        if 'mdi-twitter' in icon_class or 'x.com' in href or 'twitter.com' in href:
                            data['Twitter'] = href
                            print(f"    🐦 Twitter: {href}")
                            logging.info(f"Extracted Twitter: {href}")
                        elif 'mdi-linkedin' in icon_class or 'linkedin.com' in href:
                            data['LinkedIn'] = href
                            print(f"    💼 LinkedIn: {href}")
                            logging.info(f"Extracted LinkedIn: {href}")
                        elif 'mdi-instagram' in icon_class or 'instagram.com' in href:
                            data['Instagram'] = href
                            print(f"    📷 Instagram: {href}")
                            logging.info(f"Extracted Instagram: {href}")
                        elif 'mdi-facebook' in icon_class or 'facebook.com' in href:
                            data['Facebook'] = href
                            print(f"    👍 Facebook: {href}")
                            logging.info(f"Extracted Facebook: {href}")
                        elif 'mdi-youtube' in icon_class or 'youtube.com' in href:
                            data['YouTube'] = href
                            print(f"    ▶️ YouTube: {href}")
                            logging.info(f"Extracted YouTube: {href}")
                    except NoSuchElementException:
                        # Try to determine by URL
                        if 'linkedin.com' in href:
                            data['LinkedIn'] = href
                            print(f"    💼 LinkedIn: {href}")
                            logging.info(f"Extracted LinkedIn: {href}")
                        elif 'instagram.com' in href:
                            data['Instagram'] = href
                            print(f"    📷 Instagram: {href}")
                            logging.info(f"Extracted Instagram: {href}")
                        elif 'facebook.com' in href:
                            data['Facebook'] = href
                            print(f"    👍 Facebook: {href}")
                            logging.info(f"Extracted Facebook: {href}")
                        elif 'youtube.com' in href or 'youtu.be' in href:
                            data['YouTube'] = href
                            print(f"    ▶️ YouTube: {href}")
                            logging.info(f"Extracted YouTube: {href}")
                        elif 'x.com' in href or 'twitter.com' in href:
                            data['Twitter'] = href
                            print(f"    🐦 Twitter: {href}")
                            logging.info(f"Extracted Twitter: {href}")
            except NoSuchElementException:
                pass
            
            # Log missing social media
            if not data['Twitter'] and not data['LinkedIn'] and not data['Instagram'] and not data['Facebook'] and not data['YouTube']:
                print("    ⚠️ Social Media: NONE FOUND")
                logging.info("No social media links found")
            
            # Extract Products/Brochures/News counts
            try:
                category_chips = card.find_elements(By.CSS_SELECTOR, ".px-4 .v-chip")
                for chip in category_chips:
                    chip_text = chip.text.strip()
                    chip_class = chip.get_attribute('class') or ''
                    
                    # Check for icon to determine category
                    try:
                        icon = chip.find_element(By.CSS_SELECTOR, "i")
                        icon_class = icon.get_attribute('class') or ''
                        
                        if 'mdi-cube-outline' in icon_class:
                            # Extract count from text (e.g., "1 Products" -> 1)
                            match = re.search(r'(\d+)', chip_text)
                            if match:
                                data['Products Count'] = match.group(1)
                                print(f"    📦 Products Count: {data['Products Count']}")
                                logging.info(f"Extracted Products Count: {data['Products Count']}")
                            elif 'Products' in chip_text:
                                data['Products Count'] = '0'
                                print(f"    📦 Products Count: 0")
                        elif 'mdi-file-document-multiple-outline' in icon_class:
                            match = re.search(r'(\d+)', chip_text)
                            if match:
                                data['Brochures Count'] = match.group(1)
                                print(f"    📄 Brochures Count: {data['Brochures Count']}")
                                logging.info(f"Extracted Brochures Count: {data['Brochures Count']}")
                            elif 'Brochures' in chip_text:
                                data['Brochures Count'] = '0'
                                print(f"    📄 Brochures Count: 0")
                        elif 'mdi-newspaper-variant-multiple-outline' in icon_class:
                            match = re.search(r'(\d+)', chip_text)
                            if match:
                                data['News Count'] = match.group(1)
                                print(f"    📰 News Count: {data['News Count']}")
                                logging.info(f"Extracted News Count: {data['News Count']}")
                            elif 'News' in chip_text:
                                data['News Count'] = '0'
                                print(f"    📰 News Count: 0")
                    except NoSuchElementException:
                        pass
            except NoSuchElementException:
                pass
            
            # Log counts if not found
            if not data['Products Count']:
                print("    ⚠️ Products Count: NOT FOUND")
            if not data['Brochures Count']:
                print("    ⚠️ Brochures Count: NOT FOUND")
            if not data['News Count']:
                print("    ⚠️ News Count: NOT FOUND")
                
        except Exception as e:
            logging.error(f"Error extracting data from card: {e}")
            print(f"    ❌ ERROR extracting data: {e}")
        
        # Print summary of extracted data
        print(f"\n    ✅ EXTRACTION COMPLETE for: {data['Exhibitor Name'] or 'Unknown'}")
        print(f"    {'─' * 60}")
        
        return data
    
    def get_exhibitor_cards_from_page(self, retry_count=0, max_retries=3):
        """
        Extract all exhibitor cards from the current page with retry logic
        
        Returns:
            list: List of WebElements representing exhibitor cards
        """
        try:
            # Wait for the exhibitor list app to load
            self.wait.until(
                EC.presence_of_element_located((By.ID, "app"))
            )
            
            # Wait for Vue.js to finish loading - check for loading indicators to disappear
            try:
                # Wait for any loading indicators to disappear
                loading_indicators = self.driver.find_elements(By.CSS_SELECTOR, ".v-progress-linear__indeterminate")
                if loading_indicators:
                    print(f"    ⏳ Waiting for loading indicators to disappear...")
                    time.sleep(2)
            except:
                pass
            
            # Wait for exhibitor cards to appear - try multiple selectors with longer timeout
            cards_found = False
            try:
                # Wait for at least one card title (more reliable indicator)
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".v-card-title"))
                )
                print(f"    ✅ Found card titles, waiting for full render...")
                time.sleep(2)  # Give Vue.js time to render all cards
                cards_found = True
            except TimeoutException:
                # Try alternative - wait for any card
                try:
                    self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".v-col-sm-4 .v-card, .v-col-md-3 .v-card, .v-col-lg-3 .v-card"))
                    )
                    print(f"    ✅ Found cards, waiting for full render...")
                    time.sleep(2)
                    cards_found = True
                except TimeoutException:
                    if retry_count < max_retries:
                        print(f"    ⚠️ Timeout waiting for cards (retry {retry_count + 1}/{max_retries})...")
                        time.sleep(3)
                        return self.get_exhibitor_cards_from_page(retry_count + 1, max_retries)
                    else:
                        logging.warning("Timeout waiting for cards to appear after retries")
            
            if not cards_found:
                time.sleep(3)  # Extra wait if cards weren't found initially
            
            # Find all exhibitor cards - try multiple selectors
            cards = []
            
            # Try selector for column-based cards (most specific)
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, ".v-col-sm-4 .v-card, .v-col-md-3 .v-card, .v-col-lg-3 .v-card, .v-col-12 .v-card")
                if cards:
                    print(f"    ✅ Found {len(cards)} cards using column selector")
                    logging.info(f"Found {len(cards)} cards using column selector")
            except Exception as e:
                logging.debug(f"Column selector failed: {e}")
            
            # If no cards found, try alternative
            if not cards:
                try:
                    cards = self.driver.find_elements(By.CSS_SELECTOR, ".v-row .v-col .v-card")
                    if cards:
                        print(f"    ✅ Found {len(cards)} cards using row/col selector")
                        logging.info(f"Found {len(cards)} cards using row/col selector")
                except Exception as e:
                    logging.debug(f"Row/col selector failed: {e}")
            
            # If still no cards, try finding by card-title
            if not cards:
                try:
                    # Find all cards that have a v-card-title
                    all_cards = self.driver.find_elements(By.CSS_SELECTOR, ".v-card")
                    for card in all_cards:
                        try:
                            card.find_element(By.CSS_SELECTOR, ".v-card-title")
                            cards.append(card)
                        except:
                            continue
                    if cards:
                        print(f"    ✅ Found {len(cards)} cards using card-title filter")
                        logging.info(f"Found {len(cards)} cards using card-title filter")
                except Exception as e:
                    logging.debug(f"Card-title filter failed: {e}")
            
            # Filter out cards that don't have exhibitor names (to avoid non-exhibitor cards)
            valid_cards = []
            for idx, card in enumerate(cards):
                try:
                    name_elem = card.find_element(By.CSS_SELECTOR, ".v-card-title")
                    name_text = name_elem.text.strip()
                    # Make sure it's a real exhibitor card (has a name and is not empty)
                    if name_text and len(name_text) > 1:
                        valid_cards.append(card)
                    else:
                        logging.debug(f"Card {idx + 1} filtered out: empty or invalid name")
                except NoSuchElementException:
                    logging.debug(f"Card {idx + 1} filtered out: no title found")
                    continue
            
            print(f"    ✅ Found {len(valid_cards)} valid exhibitor cards after filtering")
            logging.info(f"Found {len(valid_cards)} valid exhibitor cards after filtering")
            
            if not valid_cards and retry_count < max_retries:
                print(f"    ⚠️ No valid cards found, retrying... (attempt {retry_count + 1}/{max_retries})")
                time.sleep(3)
                return self.get_exhibitor_cards_from_page(retry_count + 1, max_retries)
            
            return valid_cards
            
        except TimeoutException:
            logging.warning("Timeout waiting for exhibitor cards to load")
            return []
        except Exception as e:
            logging.error(f"Error getting exhibitor cards: {e}")
            return []
    
    def get_total_pages(self):
        """
        Get the total number of pages from pagination
        
        Returns:
            int: Total number of pages, or 62 if detection fails (known total)
        """
        try:
            # Wait for pagination to load
            time.sleep(3)
            pagination = self.driver.find_element(By.CSS_SELECTOR, "nav.v-pagination")
            
            # Get all page number buttons
            page_buttons = pagination.find_elements(By.CSS_SELECTOR, "li.v-pagination__item button")
            
            page_numbers = []
            for btn in page_buttons:
                text = btn.text.strip()
                # Skip ellipsis and non-numeric buttons
                if text.isdigit():
                    page_numbers.append(int(text))
            
            if page_numbers:
                max_page = max(page_numbers)
                logging.info(f"Found {max_page} total pages from pagination")
                return max_page
            
            # Alternative: look for aria-label with page numbers
            try:
                all_buttons = pagination.find_elements(By.CSS_SELECTOR, "button[aria-label*='page']")
                for btn in all_buttons:
                    aria_label = btn.get_attribute('aria-label') or ''
                    # Extract number from aria-label like "Go to page 62"
                    match = re.search(r'page\s+(\d+)', aria_label, re.IGNORECASE)
                    if match:
                        page_numbers.append(int(match.group(1)))
                
                if page_numbers:
                    max_page = max(page_numbers)
                    logging.info(f"Found {max_page} total pages from aria-labels")
                    return max_page
            except:
                pass
            
            # Try to find the last visible page number (often the highest)
            try:
                # Scroll to bottom of pagination to see last page
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'end'});", pagination)
                time.sleep(1)
                
                # Get all buttons again after scroll
                page_buttons = pagination.find_elements(By.CSS_SELECTOR, "li.v-pagination__item button")
                for btn in page_buttons:
                    text = btn.text.strip()
                    if text.isdigit():
                        page_numbers.append(int(text))
                
                if page_numbers:
                    max_page = max(page_numbers)
                    logging.info(f"Found {max_page} total pages after scroll")
                    return max_page
            except:
                pass
                
        except Exception as e:
            logging.warning(f"Could not determine total pages: {e}")
        
        # Fallback: Use known total (62 pages as confirmed by user)
        logging.warning("Could not determine total pages automatically, using known total: 62")
        return 62
    
    def wait_for_page_content_to_load(self, expected_page=None, max_wait=15):
        """
        Wait for page content to fully load after navigation
        
        Args:
            expected_page: Expected page number (optional, for verification)
            max_wait: Maximum seconds to wait
        """
        try:
            # Wait for the app container
            self.wait.until(EC.presence_of_element_located((By.ID, "app")))
            
            # Wait for loading indicators to disappear (if any)
            start_time = time.time()
            while time.time() - start_time < 5:  # Wait up to 5 seconds for loading to finish
                try:
                    loading_indicators = self.driver.find_elements(By.CSS_SELECTOR, ".v-progress-linear__indeterminate")
                    visible_loaders = [ind for ind in loading_indicators if ind.is_displayed()]
                    if not visible_loaders:
                        break
                    time.sleep(0.5)
                except:
                    break
            
            # Wait for at least one card title to appear (indicates content loaded)
            # Use a longer timeout for this critical check
            try:
                WebDriverWait(self.driver, max_wait).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".v-card-title"))
                )
            except TimeoutException:
                # Try alternative - wait for any card
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".v-card, .v-col-sm-4 .v-card"))
                    )
                except:
                    logging.warning("No cards found after waiting")
                    return False
            
            # Additional wait for Vue.js to finish rendering all cards
            time.sleep(2)
            
            # Verify we have actual content (not just empty cards)
            try:
                card_titles = self.driver.find_elements(By.CSS_SELECTOR, ".v-card-title")
                if card_titles:
                    # Check if at least one has text
                    has_content = any(title.text.strip() for title in card_titles[:3])  # Check first 3
                    if not has_content:
                        logging.warning("Cards found but no content in titles")
                        time.sleep(2)  # Wait a bit more
            except:
                pass
            
            # Verify we're on the correct page if expected_page is provided
            if expected_page:
                try:
                    pagination = self.driver.find_element(By.CSS_SELECTOR, "nav.v-pagination")
                    current_page_elem = pagination.find_element(By.CSS_SELECTOR, "button[aria-current='true']")
                    current_page = int(current_page_elem.text.strip())
                    if current_page == expected_page:
                        logging.info(f"✅ Verified we're on page {current_page}")
                        return True
                    else:
                        logging.warning(f"⚠️ Expected page {expected_page} but found page {current_page}")
                        # Still return True if we have content, page number might be off
                        return True
                except:
                    pass
            
            return True
        except TimeoutException:
            logging.warning(f"Timeout waiting for page content to load")
            return False
        except Exception as e:
            logging.warning(f"Error waiting for page content: {e}")
            return False
    
    def navigate_to_page(self, page_number):
        """
        Navigate to a specific page number with proper waiting
        
        Args:
            page_number: The page number to navigate to
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"    🔄 Navigating to page {page_number} (attempt {attempt + 1}/{max_retries})...")
                
                # Wait for pagination to be available
                time.sleep(2)
                pagination = self.driver.find_element(By.CSS_SELECTOR, "nav.v-pagination")
                
                # Get current page first
                try:
                    current_page_elem = pagination.find_element(By.CSS_SELECTOR, "button[aria-current='true']")
                    current_page = int(current_page_elem.text.strip())
                    print(f"    📍 Current page: {current_page}, Target: {page_number}")
                    
                    if current_page == page_number:
                        print(f"    ✅ Already on page {page_number}")
                        return True
                except:
                    pass
                
                # First, try to find the button for the specific page by aria-label
                clicked = False
                try:
                    page_button = pagination.find_element(By.XPATH, f".//button[@aria-label='Go to page {page_number}']")
                    # Scroll to button
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", page_button)
                    time.sleep(0.5)
                    page_button.click()
                    clicked = True
                    print(f"    ✅ Clicked page {page_number} button (aria-label)")
                except NoSuchElementException:
                    # Try clicking by text content
                    try:
                        page_button = pagination.find_element(By.XPATH, f".//button[text()='{page_number}']")
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", page_button)
                        time.sleep(0.5)
                        page_button.click()
                        clicked = True
                        print(f"    ✅ Clicked page {page_number} button (text)")
                    except NoSuchElementException:
                        # Use next/prev buttons if page number not visible
                        try:
                            current_page_elem = pagination.find_element(By.CSS_SELECTOR, "button[aria-current='true']")
                            current_page = int(current_page_elem.text.strip())
                            
                            if page_number > current_page:
                                # Click next button
                                next_button = pagination.find_element(By.CSS_SELECTOR, "li.v-pagination__next button:not([disabled])")
                                next_button.click()
                                clicked = True
                                print(f"    ✅ Clicked next button (from {current_page} to {page_number})")
                            elif page_number < current_page:
                                # Click prev button
                                prev_button = pagination.find_element(By.CSS_SELECTOR, "li.v-pagination__prev button:not([disabled])")
                                prev_button.click()
                                clicked = True
                                print(f"    ✅ Clicked prev button (from {current_page} to {page_number})")
                        except Exception as e:
                            logging.warning(f"Could not use next/prev buttons: {e}")
                
                if clicked:
                    # Wait for page content to load
                    print(f"    ⏳ Waiting for page {page_number} content to load...")
                    if self.wait_for_page_content_to_load(expected_page=page_number, max_wait=10):
                        # Double check we're on the right page
                        try:
                            pagination = self.driver.find_element(By.CSS_SELECTOR, "nav.v-pagination")
                            current_page_elem = pagination.find_element(By.CSS_SELECTOR, "button[aria-current='true']")
                            current_page = int(current_page_elem.text.strip())
                            if current_page == page_number:
                                print(f"    ✅ Successfully navigated to page {page_number}")
                                return True
                            else:
                                print(f"    ⚠️ Navigation clicked but ended up on page {current_page} instead of {page_number}")
                        except:
                            # If we can't verify, assume success and continue
                            print(f"    ⚠️ Could not verify page number, but content loaded")
                            return True
                    else:
                        print(f"    ⚠️ Page content did not load properly (attempt {attempt + 1})")
                        if attempt < max_retries - 1:
                            time.sleep(2)  # Wait before retry
                            continue
                else:
                    print(f"    ⚠️ Could not find navigation button for page {page_number} (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                
            except Exception as e:
                logging.error(f"Error navigating to page {page_number} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
        
        logging.warning(f"❌ Failed to navigate to page {page_number} after {max_retries} attempts")
        return False
    
    def scrape_all_pages(self):
        """
        Scrape all pages of exhibitors
        """
        try:
            # Navigate to the base URL
            logging.info(f"🌐 Navigating to {self.base_url}")
            self.driver.get(self.base_url)
            time.sleep(5)  # Give page time to fully load
            
            # Get total number of pages
            total_pages = self.get_total_pages()
            logging.info(f"📄 Found {total_pages} pages to scrape")
            print(f"\n{'='*60}")
            print(f"📄 Total pages found: {total_pages}")
            print(f"{'='*60}\n")
            
            total_exhibitors = 0
            successful_pages = []
            failed_pages = []
            
            for page_num in range(1, total_pages + 1):
                print(f"\n{'='*60}")
                print(f"📄 PAGE {page_num}/{total_pages}")
                print(f"{'='*60}")
                logging.info(f"📄 Starting to scrape page {page_num}/{total_pages}")
                
                # Navigate to page if not on first page
                if page_num > 1:
                    print(f"🔄 Navigating to page {page_num}...")
                    if not self.navigate_to_page(page_num):
                        print(f"⚠️ Could not navigate to page {page_num}, retrying...")
                        # Retry navigation once
                        time.sleep(3)
                        if not self.navigate_to_page(page_num):
                            logging.warning(f"Could not navigate to page {page_num} after retry, skipping...")
                            print(f"❌ Skipping page {page_num} after failed navigation")
                            continue
                
                # Wait a bit before looking for cards
                time.sleep(2)
                
                # Get all exhibitor cards from current page with retry
                print(f"🔍 Looking for exhibitor cards on page {page_num}...")
                cards = self.get_exhibitor_cards_from_page()
                
                # If no cards found, try refreshing the page content
                if not cards:
                    print(f"⚠️ No cards found, waiting longer and retrying...")
                    time.sleep(5)
                    cards = self.get_exhibitor_cards_from_page()
                
                if not cards:
                    print(f"⚠️ No exhibitor cards found on page {page_num}")
                    logging.warning(f"No exhibitors found on page {page_num}")
                    failed_pages.append(page_num)
                    # Try to debug - check what elements are present
                    try:
                        all_cards = self.driver.find_elements(By.CSS_SELECTOR, ".v-card")
                        print(f"   Debug: Found {len(all_cards)} total .v-card elements on page")
                        all_titles = self.driver.find_elements(By.CSS_SELECTOR, ".v-card-title")
                        print(f"   Debug: Found {len(all_titles)} total .v-card-title elements on page")
                        if all_titles:
                            print(f"   Debug: First title text: '{all_titles[0].text.strip()}'")
                    except Exception as e:
                        print(f"   Debug error: {e}")
                    continue
                
                logging.info(f"✅ Found {len(cards)} exhibitors on page {page_num}")
                print(f"✅ Found {len(cards)} exhibitors on page {page_num}")
                
                # Extract data from each card
                page_exhibitors_count = 0
                for idx, card in enumerate(cards, 1):
                    print(f"\n  [{idx}/{len(cards)}] Processing exhibitor card {idx}...")
                    logging.info(f"Processing exhibitor card {idx}/{len(cards)} on page {page_num}")
                    exhibitor_data = self.extract_exhibitor_card_data(card)
                    
                    # Always add the data, even if name is missing (for debugging)
                    exhibitor_data['Page Number'] = page_num
                    
                    if exhibitor_data.get('Exhibitor Name'):
                        self.all_data.append(exhibitor_data)
                        total_exhibitors += 1
                        page_exhibitors_count += 1
                        print(f"\n  ✅ SUCCESS: {exhibitor_data['Exhibitor Name']} - {exhibitor_data.get('Country', 'N/A')}")
                        logging.info(f"✅ Scraped: {exhibitor_data['Exhibitor Name']}")
                    else:
                        print(f"\n  ⚠️ WARNING: Could not extract exhibitor name from card {idx}")
                        print(f"     Extracted data: {exhibitor_data}")
                        logging.warning(f"⚠️ Could not extract exhibitor name from card {idx}")
                        # Still add it for debugging purposes
                        self.all_data.append(exhibitor_data)
                    
                    # Save progress every 20 exhibitors
                    if total_exhibitors % 20 == 0 and total_exhibitors > 0:
                        self.save_progress()
                        print(f"  💾 Progress saved: {total_exhibitors} exhibitors so far")
                
                # Mark page as successful or failed
                if page_exhibitors_count > 0:
                    successful_pages.append(page_num)
                    print(f"\n  ✅ Page {page_num} completed: {page_exhibitors_count} exhibitors extracted")
                else:
                    if page_num not in failed_pages:
                        failed_pages.append(page_num)
                    print(f"\n  ⚠️ Page {page_num} completed but no valid exhibitors extracted")
                
                # Small delay between pages
                time.sleep(2)
            
            print(f"\n{'='*60}")
            print(f"🎉 SCRAPING COMPLETE!")
            print(f"{'='*60}")
            print(f"📊 Total pages: {total_pages}")
            print(f"✅ Successful pages: {len(successful_pages)}")
            if successful_pages:
                print(f"   Pages: {', '.join(map(str, successful_pages[:10]))}{'...' if len(successful_pages) > 10 else ''}")
            print(f"❌ Failed pages: {len(failed_pages)}")
            if failed_pages:
                print(f"   Pages: {', '.join(map(str, failed_pages))}")
            print(f"📊 Total exhibitors scraped: {total_exhibitors}")
            print(f"{'='*60}\n")
            
            # Log summary
            logging.info(f"Scraping complete: {total_exhibitors} exhibitors from {len(successful_pages)} successful pages")
            if failed_pages:
                logging.warning(f"Failed pages: {failed_pages}")
            
            # Final save
            self.save_to_excel()
            
        except Exception as e:
            logging.error(f"Error during scraping: {e}")
            raise
    
    def save_progress(self):
        """Save current progress to Excel file"""
        if self.all_data:
            try:
                df = pd.DataFrame(self.all_data)
                df.to_excel('miite_exhibitors_progress.xlsx', index=False)
                logging.info(f"Progress saved: {len(self.all_data)} exhibitors")
            except Exception as e:
                logging.error(f"Error saving progress: {e}")
    
    def save_to_excel(self, filename='miite_exhibitors_complete.xlsx'):
        """
        Save all scraped data to Excel file
        
        Args:
            filename: Name of the output Excel file
        """
        if not self.all_data:
            logging.warning("No data to save")
            return
        
        try:
            df = pd.DataFrame(self.all_data)
            df.to_excel(filename, index=False)
            logging.info(f"✅ Data saved to {filename}")
            print(f"✅ Data saved to {filename}")
            print(f"📊 Total records: {len(df)}")
        except Exception as e:
            logging.error(f"Error saving to Excel: {e}")
            raise
    
    def close(self):
        """Close the browser"""
        if hasattr(self, 'driver'):
            self.driver.quit()
            logging.info("Browser closed")

def main():
    """Main function to run the scraper"""
    scraper = None
    try:
        scraper = MIITEScraper(headless=False)  # Set to True for headless mode
        scraper.scrape_all_pages()
    except KeyboardInterrupt:
        print("\n⚠️ Scraping interrupted by user")
        logging.info("Scraping interrupted by user")
        if scraper:
            scraper.save_progress()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        if scraper:
            scraper.save_progress()
        raise
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()
