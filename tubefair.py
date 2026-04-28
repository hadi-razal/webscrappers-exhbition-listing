"""
Tube Fair / wire 2026 Exhibitor Scraper

Two-phase approach:
  Phase 1 - Navigate through alphabetical directory pages (A-Z, 0-9) to collect all exhibitor cards.
  Phase 2 - Click "Details" button on each card to open profile, then click "Company data" to open modal and extract contact details.

Fields collected
  From listing card : Company Name, Hall, Stand, Event, Exhibitor ID
  From modal        : Website, Phone, Email, Country, Address, Description, Categories, Contact Person

Output files
  tubefair_exhibitors.xlsx          <- final result
  tubefair_exhibitors_progress.xlsx <- auto-saved every 25 profiles

Usage
  python tubefair.py

Notes
  - Chrome opens visibly so you can watch progress.
  - Press Ctrl+C at any time to save what has been collected and exit.
  - On a second run the progress file is loaded and already-scraped IDs are skipped
    so the scraper resumes where it left off.
"""

import re
import sys
import time
import logging
import signal

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LISTING_URL   = "https://www.tube-tradefair.com/vis/v1/en/directory/a"
SAVE_FILE     = "tubefair_exhibitors.xlsx"
PROGRESS_FILE = "tubefair_exhibitors_progress.xlsx"
SAVE_EVERY    = 25   # save progress after every N profile pages scraped


# ---------------------------------------------------------------------------
# Scraper class
# ---------------------------------------------------------------------------
class TubeFairScraper:

    def __init__(self):
        self.all_data: list[dict] = []
        self.done_ids: set[str]  = set()
        self.interrupted = False

        self._setup_driver()
        self._setup_signals()

    # ------------------------------------------------------------------
    # Browser setup
    # ------------------------------------------------------------------
    def _setup_driver(self):
        opts = Options()
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument("--start-maximized")

        self.driver = webdriver.Chrome(options=opts)
        self.driver.execute_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
        )
        self.wait = WebDriverWait(self.driver, 20)
        self.actions = ActionChains(self.driver)
        log.info("Chrome opened")

    def _setup_signals(self):
        def _handler(_sig, _frame):
            log.warning("Interrupt received – saving and exiting...")
            self.interrupted = True
            self._save_excel()
            self._teardown()
            sys.exit(0)
        try:
            signal.signal(signal.SIGINT, _handler)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, _handler)
        except (ValueError, AttributeError):
            pass

    def _teardown(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Resume: load already-scraped IDs from progress file
    # ------------------------------------------------------------------
    def _load_progress(self):
        import os
        if not os.path.exists(PROGRESS_FILE):
            log.info("No progress file found – starting fresh")
            return
        try:
            df = pd.read_excel(PROGRESS_FILE)
            self.all_data = df.to_dict("records")
            self.done_ids = {
                str(r.get("Exhibitor ID", ""))
                for r in self.all_data
                if r.get("Exhibitor ID")
            }
            log.info(
                f"Resumed from progress file – {len(self.all_data)} records already done"
            )
        except Exception as e:
            log.warning(f"Could not load progress file: {e}")

    # ------------------------------------------------------------------
    # Phase 1 – collect cards from all alphabetical directory pages
    # ------------------------------------------------------------------
    def _get_all_alphabet_pages(self) -> list[str]:
        """Collect all alphabetical page URLs from the directory navigation."""
        log.info("Collecting all alphabetical directory pages...")
        self.driver.get(LISTING_URL)
        self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".directory-nav__list, .directory-nav"))
        )
        time.sleep(2)  # Let content load
        
        # Try multiple selectors for alphabet navigation
        alphabet_links = []
        selectors = [
            ".directory-nav__list a[href*='/directory/']",
            ".directory-nav a[href*='/directory/']",
            "a[href*='/directory/']",
        ]
        
        for selector in selectors:
            try:
                links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if links:
                    alphabet_links = links
                    break
            except:
                continue
        
        urls = []
        for link in alphabet_links:
            href = link.get_attribute("href")
            if href and "/directory/" in href:
                urls.append(href)
        
        # Remove duplicates and sort
        urls = sorted(list(set(urls)))
        log.info(f"Found {len(urls)} alphabetical pages.")
        return urls

    def _scrape_alphabet_page(self, page_url: str) -> list[dict]:
        """Scrape all exhibitor cards from a single alphabetical directory page, clicking Details to extract from modal."""
        log.info(f"Navigating to alphabetical page: {page_url}")
        self.driver.get(page_url)
        self.wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "li.directory__result-list-item, .directory__result-list-item")
            )
        )
        time.sleep(2)  # Let content load

        # Try multiple selectors for cards
        cards = []
        selectors = [
            "li.directory__result-list-item article.teaser-row",
            "li.directory__result-list-item",
            ".directory__result-list-item article.teaser-row",
            ".teaser-row",
        ]
        
        for selector in selectors:
            try:
                found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if found:
                    cards = found
                    break
            except:
                continue
        
        log.info(f"Found {len(cards)} exhibitor cards on this page.")
        items = []
        
        for card_idx, card in enumerate(cards, 1):
            try:
                # Hover over the card to reveal hover buttons (like Details button)
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                    time.sleep(0.3)
                    self.actions.move_to_element(card).perform()
                    time.sleep(0.5)  # Wait for hover effects to appear
                except Exception as e:
                    log.warning(f"  Could not hover over card: {e}")
                
                # Extract basic info from the card
                name = ""
                try:
                    name_elem = card.find_element(By.CSS_SELECTOR, ".teaser-row__title, .teaser-tile__title")
                    name = name_elem.text.strip()
                except NoSuchElementException:
                    continue  # Skip if no name found

                # Extract Exhibitor ID from the 'Details' button href
                # The Details button may only appear on hover, so we try multiple approaches
                eid = ""
                details_url = ""
                try:
                    # Try to find Details button - it might be visible after hover
                    details_button = None
                    detail_selectors = [
                        "button.teaser-row__details",
                        "a.teaser-row__details",
                        ".teaser-row__details",
                        "a[href*='actionItem']",
                        "a[href*='/profile/']",
                        "button[class*='details']",
                    ]
                    
                    for selector in detail_selectors:
                        try:
                            details_button = card.find_element(By.CSS_SELECTOR, selector)
                            if details_button.is_displayed():
                                break
                        except:
                            continue
                    
                    if not details_button:
                        # Try finding by text content
                        try:
                            all_buttons = card.find_elements(By.CSS_SELECTOR, "button, a")
                            for btn in all_buttons:
                                btn_text = btn.text.strip().lower()
                                if "detail" in btn_text or "view" in btn_text:
                                    details_button = btn
                                    break
                        except:
                            pass
                    
                    if details_button:
                        # Try to get href from parent link or button
                        try:
                            parent_link = details_button.find_element(By.XPATH, "./ancestor::a")
                            details_url = parent_link.get_attribute("href") or ""
                        except:
                            try:
                                details_url = details_button.get_attribute("href") or ""
                            except:
                                # Try onclick or data attributes
                                try:
                                    onclick = details_button.get_attribute("onclick") or ""
                                    if onclick:
                                        url_match = re.search(r"['\"]([^'\"]*actionItem[^'\"]*)['\"]", onclick)
                                        if url_match:
                                            details_url = url_match.group(1)
                                except:
                                    pass
                        
                        # Extract ID from URL
                        if details_url:
                            eid_match = re.search(r"actionItem=(\d+)", details_url)
                            if not eid_match:
                                eid_match = re.search(r"/profile/(\d+)", details_url)
                            if not eid_match:
                                eid_match = re.search(r"id=(\d+)", details_url)
                            eid = eid_match.group(1) if eid_match else ""
                    
                    # If still no URL found, try to extract from card's data attributes or links
                    if not details_url:
                        try:
                            # Look for any link in the card that might be the profile link
                            all_links = card.find_elements(By.CSS_SELECTOR, "a[href*='actionItem'], a[href*='/profile/']")
                            for link in all_links:
                                href = link.get_attribute("href") or ""
                                if "actionItem" in href or "/profile/" in href:
                                    details_url = href
                                    eid_match = re.search(r"actionItem=(\d+)", href)
                                    if not eid_match:
                                        eid_match = re.search(r"/profile/(\d+)", href)
                                    if eid_match:
                                        eid = eid_match.group(1)
                                    break
                        except:
                            pass
                    
                    if not eid and not details_url:
                        log.warning(f"  Could not find Details button or URL for {name}")
                        continue
                        
                except NoSuchElementException:
                    log.warning(f"  Could not find Details button for {name}")
                    continue

                hall_stand = ""
                try:
                    hall_stand_elem = card.find_element(By.CSS_SELECTOR, "a.hall-map-link, .hall-map-link")
                    hall_stand = hall_stand_elem.text.strip()
                except NoSuchElementException:
                    pass

                hall, stand = "", ""
                if "/" in hall_stand:
                    parts = hall_stand.split("/", 1)
                    hall = parts[0].strip()
                    stand = parts[1].strip() if len(parts) > 1 else ""
                else:
                    hall = hall_stand

                event = ""
                try:
                    event_img = card.find_element(By.CSS_SELECTOR, ".event-icon-list img, .event-icon img")
                    event = event_img.get_attribute("alt") or ""
                except NoSuchElementException:
                    pass

                city_country = ""
                try:
                    city_country_elem = card.find_element(By.CSS_SELECTOR, ".teaser-row__text, .teaser-tile__text")
                    city_country = city_country_elem.text.strip()
                except NoSuchElementException:
                    pass

                # Create basic record
                basic_record = {
                    "Exhibitor ID": eid,
                    "Company Name": name,
                    "Hall": hall,
                    "Stand": stand,
                    "Event": event,
                    "City/Country (from card)": city_country,
                }
                
                # Skip if already processed
                if eid and eid in self.done_ids:
                    log.info(f"  [{card_idx}/{len(cards)}] Skipping {name} (already done)")
                    continue
                
                log.info(f"\n  [{card_idx}/{len(cards)}] Processing {name} ({hall} / {stand}) [{eid}]")
                
                # Click Details button and extract all data from modal
                full_record = self._click_details_and_extract_from_modal(card, basic_record)
                
                items.append(full_record)
                if eid:
                    self.done_ids.add(eid)
                
                # Save progress periodically
                if len(items) % SAVE_EVERY == 0:
                    self.all_data.extend(items)
                    self._save_progress()
                    log.info(f"  Progress saved ({len(items)} cards processed on this page)")
                
            except StaleElementReferenceException:
                log.warning("StaleElementReferenceException caught while scraping card, retrying...")
                continue
            except Exception as e:
                log.error(f"Error scraping card: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        return items

    # ------------------------------------------------------------------
    # Phase 2 – extract data from profile page and modal
    # ------------------------------------------------------------------
    def _wait_for_profile(self) -> bool:
        """Wait for the profile page to load."""
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".profile, .exhibitor-profile, h1, [data-testid*='profile']")
                )
            )
            time.sleep(1)  # Let page fully render
            return True
        except TimeoutException:
            return False

    def _extract_website(self) -> str:
        """Extract website URL from modal."""
        try:
            # Try multiple selectors - look within modal context
            selectors = [
                ".content-modal-width-wrapper a[href^='http']",
                ".exh-contact__links a[href^='http']",
                ".profile-details__links a[href^='http']",
                "[class*='modal'] a[href^='http']",
                "a[href^='http']:not([href*='tube-tradefair']):not([href*='wire.de'])",
            ]
            for sel in selectors:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for link in links:
                        href = link.get_attribute("href") or ""
                        if href and not any(x in href.lower() for x in ["tube-tradefair.com", "wire.de", "facebook", "linkedin", "twitter", "instagram", "youtube", "x.com"]):
                            # Check if it's a website link (not social media)
                            text = link.text.strip().lower()
                            if not any(x in text for x in ["facebook", "linkedin", "twitter", "instagram", "youtube"]):
                                return href
                except:
                    continue
        except:
            pass
        return ""

    def _extract_phone(self) -> str:
        """Extract phone number from modal."""
        try:
            # Try multiple selectors - look within modal context
            selectors = [
                ".content-modal-width-wrapper [class*='phone']",
                ".exh-contact__phone",
                ".profile-details__phone",
                "[class*='modal'] [class*='phone']",
                "a[href^='tel:']",
            ]
            for sel in selectors:
                try:
                    if "tel:" in sel:
                        # Extract from tel: link
                        link = self.driver.find_element(By.CSS_SELECTOR, sel)
                        href = link.get_attribute("href") or ""
                        if href.startswith("tel:"):
                            return href.replace("tel:", "").strip()
                    else:
                        elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                        text = elem.text.strip()
                        # Remove "Phone: " prefix if present
                        text = re.sub(r'^Phone:\s*', '', text, flags=re.IGNORECASE)
                        # Extract phone pattern
                        phone_match = re.search(r'[\d\s\+\-\(\)]+', text)
                        if phone_match:
                            return phone_match.group(0).strip()
                except:
                    continue
        except:
            pass
        return ""

    def _extract_email(self) -> str:
        """Extract email from modal."""
        try:
            # Try multiple selectors - look within modal context
            selectors = [
                ".content-modal-width-wrapper a[href^='mailto:']",
                ".exh-contact__email",
                ".profile-details__email",
                "[class*='modal'] a[href^='mailto:']",
                "a[href^='mailto:']",
                "[class*='email']",
            ]
            for sel in selectors:
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                    # Try href first (mailto:)
                    href = elem.get_attribute("href") or ""
                    if href.startswith("mailto:"):
                        return href.replace("mailto:", "").strip()
                    # Otherwise try text
                    text = elem.text.strip()
                    # Remove "E-mail: " prefix if present
                    text = re.sub(r'^E-mail:\s*', '', text, flags=re.IGNORECASE)
                    # Extract email pattern
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
                    if email_match:
                        return email_match.group(0).strip()
                except:
                    continue
        except:
            pass
        return ""

    def _extract_country_address(self) -> tuple[str, str]:
        """Extract country and address from modal."""
        country, address = "", ""
        try:
            # Try multiple selectors for address block - look within modal context
            selectors = [
                ".content-modal-width-wrapper .exh-address",
                ".content-modal-width-wrapper [class*='address']",
                ".exh-address",
                ".profile-details__address",
                "[class*='modal'] [class*='address']",
                "[class*='address']",
            ]
            address_block = None
            for sel in selectors:
                try:
                    address_block = self.driver.find_element(By.CSS_SELECTOR, sel)
                    break
                except:
                    continue
            
            if address_block:
                # Extract country
                try:
                    country_selectors = [
                        ".address-country",
                        "[class*='country']",
                        "[data-testid*='country']",
                    ]
                    for cs in country_selectors:
                        try:
                            country_elem = address_block.find_element(By.CSS_SELECTOR, cs)
                            country = country_elem.text.strip()
                            if country:
                                break
                        except:
                            continue
                except:
                    pass
                
                # Extract address parts
                address_parts = []
                
                # Street
                try:
                    street_selectors = [".address-street", "[class*='street']", "[data-testid*='street']"]
                    for ss in street_selectors:
                        try:
                            street_elem = address_block.find_element(By.CSS_SELECTOR, ss)
                            street = street_elem.text.strip()
                            if street:
                                address_parts.append(street)
                                break
                        except:
                            continue
                except:
                    pass
                
                # Zip and City
                try:
                    zip_elem = None
                    city_elem = None
                    zip_selectors = [".address-zip", "[class*='zip']", "[data-testid*='zip']"]
                    city_selectors = [".address-city", "[class*='city']", "[data-testid*='city']"]
                    
                    for zs in zip_selectors:
                        try:
                            zip_elem = address_block.find_element(By.CSS_SELECTOR, zs)
                            break
                        except:
                            continue
                    
                    for cs in city_selectors:
                        try:
                            city_elem = address_block.find_element(By.CSS_SELECTOR, cs)
                            break
                        except:
                            continue
                    
                    zip_code = zip_elem.text.strip() if zip_elem else ""
                    city = city_elem.text.strip() if city_elem else ""
                    if zip_code or city:
                        zip_city = f"{zip_code} {city}".strip()
                        address_parts.append(zip_city)
                except:
                    pass
                
                address = ", ".join(address_parts)
        except:
            pass
        
        return country, address

    def _extract_description(self) -> str:
        """Extract description from modal."""
        try:
            # Try multiple selectors - look within modal context
            selectors = [
                ".content-modal-width-wrapper .profile-details__text",
                ".content-modal-width-wrapper [class*='description']",
                ".profile-details__text",
                ".exhibitor-profile__description",
                "[class*='modal'] [class*='description']",
                "[class*='description']",
            ]
            for sel in selectors:
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                    text = elem.text.strip()
                    if text:
                        return text
                except:
                    continue
        except:
            pass
        return ""

    def _extract_categories(self) -> str:
        """Extract categories from profile page."""
        try:
            selectors = [
                ".profile-details__categories",
                "[class*='categor']",
            ]
            for sel in selectors:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    categories = [e.text.strip() for e in elems if e.text.strip()]
                    if categories:
                        return ", ".join(categories)
                except:
                    continue
        except:
            pass
        return ""

    def _extract_contact_person(self) -> str:
        """Extract contact person from profile page."""
        try:
            selectors = [
                ".profile-details__contact",
                "[class*='contact-person']",
            ]
            for sel in selectors:
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                    return elem.text.strip()
                except:
                    continue
        except:
            pass
        return ""

    def _text(self, selectors: list[str]) -> str:
        """Helper to extract text using multiple selectors."""
        for sel in selectors:
            try:
                elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                return elem.text.strip()
            except:
                continue
        return ""

    def _click_details_and_extract_from_modal(self, card, basic: dict) -> dict:
        """Click Details button on card, extract all data from the modal, then close it."""
        record = dict(basic)
        record.update({
            "Website":         "",
            "Phone":           "",
            "Email":           "",
            "Country":         "",
            "Address":         "",
            "Description":     "",
            "Categories":      "",
            "Contact Person":  "",
        })

        try:
            # Find and click the Details button
            details_button = None
            detail_selectors = [
                "button.teaser-row__details",
                "a.teaser-row__details",
                ".teaser-row__details",
                "button[class*='details']",
            ]
            
            for selector in detail_selectors:
                try:
                    details_button = card.find_element(By.CSS_SELECTOR, selector)
                    if details_button.is_displayed():
                        break
                except:
                    continue
            
            if not details_button:
                # Try finding by text content
                try:
                    all_buttons = card.find_elements(By.CSS_SELECTOR, "button, a")
                    for btn in all_buttons:
                        btn_text = btn.text.strip().lower()
                        if "detail" in btn_text:
                            details_button = btn
                            break
                except:
                    pass
            
            if not details_button:
                log.warning(f"     Could not find Details button for {basic.get('Company Name', 'unknown')}")
                return record

            # Click the Details button to open modal
            log.info(f"  -> Clicking Details button for {basic.get('Company Name', 'unknown')}")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", details_button)
            time.sleep(0.3)
            self.driver.execute_script("arguments[0].click();", details_button)
            time.sleep(2)  # Wait for modal to open

            # Wait for modal to appear
            try:
                self.wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, ".content-modal-width-wrapper, [class*='modal'], [class*='content-modal']")
                    )
                )
                time.sleep(1)  # Let modal fully render
            except TimeoutException:
                log.warning("     Modal did not open after clicking Details button")
                return record

            # Extract all data from the modal
            record["Website"]        = self._extract_website()
            record["Phone"]          = self._extract_phone()
            record["Email"]          = self._extract_email()
            record["Description"]    = self._extract_description()
            record["Categories"]     = self._extract_categories()
            record["Contact Person"] = self._extract_contact_person()

            country, address = self._extract_country_address()
            record["Country"] = country
            record["Address"] = address

            # Close the modal
            try:
                close_selectors = [
                    "button[data-testid='modal.close']",
                    "button[aria-label='Close']",
                    ".modal-close",
                    "button[class*='close']",
                    "[class*='modal-close']",
                ]
                close_button = None
                for sel in close_selectors:
                    try:
                        close_button = self.driver.find_element(By.CSS_SELECTOR, sel)
                        if close_button.is_displayed():
                            break
                    except:
                        continue
                
                if close_button:
                    self.driver.execute_script("arguments[0].click();", close_button)
                    time.sleep(1)
                else:
                    # Fallback: press Escape key
                    from selenium.webdriver.common.keys import Keys
                    self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    time.sleep(1)
            except Exception as e:
                log.warning(f"     Could not close modal: {e}")
                # Try Escape key as fallback
                try:
                    from selenium.webdriver.common.keys import Keys
                    self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    time.sleep(1)
                except:
                    pass

            # --- Log what was found ---
            log.info(f"     Website:  {record['Website'] or '(not found)'}")
            log.info(f"     Phone:    {record['Phone'] or '(not found)'}")
            log.info(f"     Email:    {record['Email'] or '(not found)'}")
            log.info(f"     Country:  {record['Country'] or '(not found)'}")
            log.info(f"     Address:  {record['Address'] or '(not found)'}")
            if record["Categories"]:
                log.info(f"     Categories: {record['Categories'][:80]}")
            if record["Description"]:
                log.info(f"     Desc ({len(record['Description'])} chars captured)")

        except Exception as e:
            log.error(f"     Error extracting data from modal: {e}")
            import traceback
            traceback.print_exc()
            # Try to close modal if it's still open
            try:
                from selenium.webdriver.common.keys import Keys
                self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(1)
            except:
                pass

        return record

    # ------------------------------------------------------------------
    # Save helpers
    # ------------------------------------------------------------------
    def _save_progress(self):
        if not self.all_data:
            return
        try:
            pd.DataFrame(self.all_data).to_excel(PROGRESS_FILE, index=False)
            log.info(
                f"Progress saved: {len(self.all_data)} records -> {PROGRESS_FILE}"
            )
        except Exception as e:
            log.error(f"Progress save failed: {e}")

    def _save_excel(self):
        if not self.all_data:
            log.warning("No data to save")
            return
        try:
            pd.DataFrame(self.all_data).to_excel(SAVE_FILE, index=False)
            log.info(f"Final file saved: {len(self.all_data)} records -> {SAVE_FILE}")
        except Exception as e:
            log.error(f"Excel save failed: {e}")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def run(self):
        try:
            self._load_progress()

            log.info("=" * 60)
            log.info("Scraping all alphabetical directory pages")
            log.info("Clicking Details button on each card to extract data from modal")
            log.info("=" * 60)
            alphabet_pages = self._get_all_alphabet_pages()
            
            all_items = []
            for page_idx, page_url in enumerate(alphabet_pages, 1):
                if self.interrupted:
                    break
                
                log.info(f"\n{'='*60}")
                log.info(f"Processing alphabetical page {page_idx}/{len(alphabet_pages)}: {page_url}")
                log.info(f"{'='*60}")
                
                page_items = self._scrape_alphabet_page(page_url)
                all_items.extend(page_items)
                
                # Add to main data list
                self.all_data.extend(page_items)
                
                log.info(f"Completed page {page_idx}/{len(alphabet_pages)} - {len(page_items)} items collected")
                
                # Save progress after each page
                self._save_progress()

            log.info("\n" + "=" * 60)
            if self.interrupted:
                log.info(f"INTERRUPTED – {len(self.all_data)} records collected")
            else:
                log.info(f"COMPLETE – {len(self.all_data)} records collected")
            log.info("=" * 60)

        except KeyboardInterrupt:
            log.warning("KeyboardInterrupt caught")
        except Exception as e:
            log.error(f"Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._save_excel()
            self._teardown()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Tube Fair / wire 2026 – Exhibitor Scraper")
    print("=" * 60)
    print(f"  Listing URL : {LISTING_URL}")
    print(f"  Output file : {SAVE_FILE}")
    print(f"  Progress    : {PROGRESS_FILE}  (auto-saved every {SAVE_EVERY} profiles)")
    print()
    print("  The scraper runs in two phases:")
    print("    1. Navigate through all alphabetical directory pages (A-Z, 0-9) to collect all exhibitor cards")
    print("    2. Visit each profile page, click 'Company data' to open modal, and extract contact details")
    print()
    print("  Press Ctrl+C at any time to save collected data and exit.")
    print("  Re-run to resume – already-scraped profiles are skipped.")
    print("=" * 60)
    print()

    scraper = TubeFairScraper()
    scraper.run()
    print("\nDone.")


if __name__ == "__main__":
    main()
