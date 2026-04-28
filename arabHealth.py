from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)
import time
import pandas as pd
import re

URL = "https://www.worldhealthexpo.com/events/healthcare/dubai/en/attend/exhibitor-list.html"

# Selectors - will need to be adjusted based on actual page structure
# Common patterns for exhibitor cards
CARD_SELECTORS = [
    "div[data-hook*='exhibitor']",
    "div[class*='exhibitor']",
    "div[class*='card']",
    "a[href*='exhibitor']",
    "div[class*='sc-']",  # styled-components pattern from HTML
]

# Load More button selectors
LOAD_MORE_SELECTORS = [
    "button[data-hook*='load']",
    "button:contains('Load More')",
    "button:contains('Load more')",
    "button:contains('Show more')",
    "a[data-hook*='load']",
]

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--log-level=3")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

driver.get(URL)
time.sleep(5)  # Wait for initial page load

# Scroll down a bit to trigger lazy loading
driver.execute_script("window.scrollTo(0, 500);")
time.sleep(2)

data = []
seen_names = set()  # Track unique exhibitors
processed_card_texts = set()  # Track processed cards by their text to avoid duplicates

try:
    # Debug: Print page title to confirm we're on the right page
    print(f"📄 Page title: {driver.title}")
    print(f"📄 Current URL: {driver.current_url}")
    
    # Try to find all clickable links that might be exhibitor cards
    # Look for links in the main content area
    print("🔍 Searching for exhibitor cards...")
    
    # Main scraping loop with Load More handling
    load_more_attempts = 0
    max_load_more_attempts = 200  # Safety limit
    no_new_data_count = 0
    previous_card_count = 0
    
    while True:
        # Get current page source and find all cards
        time.sleep(2)
        
        # Scroll to bottom to trigger lazy loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Try multiple strategies to find cards
        all_cards = []
        card_count_retries = 0
        
        # Strategy 1: Look for links that might be exhibitor cards
        try:
            # Find all links in the main content area (excluding nav/footer)
            main_content = driver.find_element(By.TAG_NAME, "main")
            if main_content:
                links = main_content.find_elements(By.TAG_NAME, "a")
                # Filter links that look like exhibitor links
                for link in links:
                    href = link.get_attribute("href") or ""
                    text = link.text.strip()
                    # If link has text and looks like an exhibitor link
                    if text and len(text) > 2 and ("exhibitor" in href.lower() or len(text) < 100):
                        all_cards.append(link)
        except:
            pass
        
        # Strategy 2: Look for divs with text that might be cards
        if not all_cards:
            try:
                # Find divs that contain text and might be cards
                divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'sc-') or @data-hook]")
                for div in divs:
                    text = div.text.strip()
                    # If div has substantial text, it might be a card
                    if text and 5 < len(text) < 200:
                        all_cards.append(div)
            except:
                pass
        
        # Strategy 3: Try CSS selectors
        if not all_cards:
            for selector in CARD_SELECTORS:
                try:
                    found = driver.find_elements(By.CSS_SELECTOR, selector)
                    if found:
                        all_cards = found
                        print(f"✅ Found cards using selector: {selector}")
                        break
                except:
                    continue
        
        # If we didn't find cards, wait a bit and try again (might be loading)
        if not all_cards and load_more_attempts > 0:
            print("⏳ No cards found, waiting for content to load...")
            time.sleep(3)
            # Try one more time
            try:
                divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'sc-') or @data-hook]")
                for div in divs:
                    text = div.text.strip()
                    if text and 5 < len(text) < 200:
                        all_cards.append(div)
            except:
                pass
        
        print(f"📊 Found {len(all_cards)} potential cards on page")
        
        # Track if we got new cards
        if len(all_cards) > previous_card_count:
            print(f"✨ New cards detected! Previous: {previous_card_count}, Current: {len(all_cards)}")
        previous_card_count = len(all_cards)
        
        # Extract data from visible cards
        current_count = len(data)
        for card in all_cards:
            try:
                # Try to find company name in various ways
                company = ""
                booth = ""
                country = ""
                website = ""
                linkedin = ""
                contact = ""
                
                # Get all text from the card
                card_text = card.text.strip()
                
                # Skip if we've already processed this card (check first 50 chars as fingerprint)
                if card_text:
                    card_fingerprint = card_text[:50].strip()
                    if card_fingerprint in processed_card_texts:
                        continue  # Skip this card, already processed
                    processed_card_texts.add(card_fingerprint)
                
                # Try to find heading tags first (most reliable)
                for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    try:
                        name_elems = card.find_elements(By.TAG_NAME, tag)
                        for elem in name_elems:
                            text = elem.text.strip()
                            if text and 2 < len(text) < 100:  # Reasonable name length
                                company = text
                                break
                        if company:
                            break
                    except:
                        continue
                
                # If no heading found, try to get the first meaningful line
                if not company and card_text:
                    lines = [line.strip() for line in card_text.split('\n') if line.strip()]
                    for line in lines:
                        # Skip common non-name text
                        if (len(line) > 2 and len(line) < 100 and 
                            line.lower() not in ['view profile', 'learn more', 'read more', 'details'] and
                            not line.startswith('http') and
                            'email' not in line.lower() and
                            'phone' not in line.lower()):
                            company = line
                            break
                
                # Clean up company name
                if company:
                    # Remove extra whitespace
                    company = ' '.join(company.split())
                    # Remove common prefixes/suffixes
                    company = re.sub(r'^(View|See|Read|More|Details|Profile)\s*:?\s*', '', company, flags=re.IGNORECASE)
                    company = company.strip()
                
                # Extract booth number - look for patterns like "Booth", "Stand", "Hall", etc.
                if card_text:
                    # Pattern 1: "Booth" or "Stand" followed by number/letters
                    booth_patterns = [
                        r'(?:Booth|Stand|Hall|Pavilion)[\s:]*([A-Z0-9\-]+)',
                        r'(?:Booth|Stand|Hall|Pavilion)[\s:]*([A-Z]?\d+[A-Z]?)',
                        r'([A-Z]?\d+[A-Z]?)[\s]*(?:Booth|Stand|Hall)',
                    ]
                    for pattern in booth_patterns:
                        match = re.search(pattern, card_text, re.IGNORECASE)
                        if match:
                            booth = match.group(1).strip()
                            break
                    
                    # Pattern 2: Look for spans/divs with booth-related classes
                    try:
                        booth_elems = card.find_elements(By.XPATH, ".//*[contains(@class, 'booth') or contains(@class, 'stand') or contains(@data-hook, 'booth') or contains(@data-hook, 'stand')]")
                        for elem in booth_elems:
                            text = elem.text.strip()
                            if text and len(text) < 20:  # Booth numbers are usually short
                                booth = text
                                break
                    except:
                        pass
                
                # Extract website - look for links
                try:
                    links = card.find_elements(By.TAG_NAME, "a")
                    for link in links:
                        href = link.get_attribute("href") or ""
                        if href and ("http" in href or "www" in href):
                            if "linkedin.com" in href.lower():
                                linkedin = href
                            elif "facebook.com" in href.lower() or "twitter.com" in href.lower() or "instagram.com" in href.lower():
                                pass  # Skip social media for website field
                            elif not website:  # Use first non-social link as website
                                website = href
                except:
                    pass
                
                # Extract contact email
                try:
                    email_links = card.find_elements(By.XPATH, ".//a[starts-with(@href, 'mailto:')]")
                    if email_links:
                        contact = email_links[0].get_attribute("href").replace("mailto:", "")
                except:
                    pass
                
                # Extract country - look for country names or flags
                if card_text:
                    # Common country patterns
                    country_patterns = [
                        r'\b(United Arab Emirates|UAE|Dubai|Abu Dhabi|Saudi Arabia|USA|United States|UK|United Kingdom|Germany|France|Italy|Spain|China|India|Japan|Korea|Singapore|Malaysia|Thailand|Philippines|Indonesia|Australia|Canada|Brazil|Mexico|Egypt|Turkey|Lebanon|Jordan|Qatar|Kuwait|Bahrain|Oman)\b'
                    ]
                    for pattern in country_patterns:
                        match = re.search(pattern, card_text, re.IGNORECASE)
                        if match:
                            country = match.group(1).strip()
                            break
                
                # Only add if we have a valid name and haven't seen it before
                if company and company not in seen_names and 2 < len(company) < 150:
                    seen_names.add(company)
                    
                    # Create data entry
                    entry = {
                        "Company Name": company,
                        "Booth No": booth,
                        "Country": country,
                        "Company Website": website,
                        "Company LinkedIn": linkedin,
                        "Company Contact": contact,
                    }
                    data.append(entry)
                    
                    # Console log all data
                    print("\n" + "="*60)
                    print(f"📋 EXHIBITOR DATA #{len(data)}")
                    print("="*60)
                    print(f"🏢 Company Name: {company}")
                    print(f"📍 Booth Number: {booth if booth else 'Not found'}")
                    print(f"🌍 Country: {country if country else 'Not found'}")
                    print(f"🌐 Website: {website if website else 'Not found'}")
                    print(f"💼 LinkedIn: {linkedin if linkedin else 'Not found'}")
                    print(f"📧 Contact: {contact if contact else 'Not found'}")
                    print(f"📄 Full Card Text: {card_text[:200]}..." if len(card_text) > 200 else f"📄 Full Card Text: {card_text}")
                    print("="*60)
                    
            except Exception as e:
                print(f"⚠️ Error processing card: {str(e)}")
                continue
        
        print(f"\n📊 Total exhibitors scraped so far: {len(data)}")
        if len(data) > current_count:
            print(f"✨ New exhibitors added in this batch: {len(data) - current_count}")
        
        # Check if we got new data
        if len(data) == current_count:
            no_new_data_count += 1
            if no_new_data_count >= 3:
                print("✅ No new data found after multiple attempts. Finished scraping.")
                break
        else:
            no_new_data_count = 0
        
        # Try to find and click "Load More" button
        load_more_found = False
        
        # Store current card count before clicking
        cards_before_click = len(all_cards)
        
        # Strategy 1: Find by text content (case-insensitive) - re-find each time
        load_more_texts = ["load more", "show more", "load additional", "view more", "see more"]
        for text in load_more_texts:
            try:
                # Re-find the button each time (it might become stale)
                load_more_btn = None
                try:
                    load_more_btn = driver.find_element(By.XPATH, f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]")
                except:
                    try:
                        load_more_btn = driver.find_element(By.XPATH, f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]")
                    except:
                        try:
                            load_more_btn = driver.find_element(By.XPATH, f"//div[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]")
                        except:
                            pass
                
                if load_more_btn:
                    # Check if button is visible and clickable
                    try:
                        if load_more_btn.is_displayed():
                            # Scroll to button
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", load_more_btn)
                            time.sleep(1)
                            
                            # Click button using JavaScript (more reliable)
                            driver.execute_script("arguments[0].click();", load_more_btn)
                            load_more_found = True
                            load_more_attempts += 1
                            print(f"🔄 Clicked 'Load More' button (attempt {load_more_attempts})")
                            
                            # Wait for new content to load - wait for card count to increase
                            print("⏳ Waiting for new content to load...")
                            wait_time = 0
                            max_wait = 10  # Maximum wait time in seconds
                            while wait_time < max_wait:
                                time.sleep(1)
                                wait_time += 1
                                try:
                                    # Check if new cards appeared
                                    new_cards = driver.find_elements(By.XPATH, "//div[contains(@class, 'sc-') or @data-hook]")
                                    if len(new_cards) > cards_before_click:
                                        print(f"✅ New content loaded! Found {len(new_cards)} cards (was {cards_before_click})")
                                        break
                                except:
                                    pass
                            
                            # Additional wait for any animations
                            time.sleep(2)
                            break
                    except StaleElementReferenceException:
                        print("⚠️ Button became stale, trying to re-find...")
                        continue
                    except Exception as e:
                        print(f"⚠️ Error clicking button: {str(e)}")
                        continue
            except Exception as e:
                continue
        
        # Strategy 2: Try CSS selectors - re-find each time
        if not load_more_found:
            for selector in LOAD_MORE_SELECTORS:
                if ":" in selector:  # Skip pseudo-selectors
                    continue
                try:
                    # Re-find button
                    load_more_btn = driver.find_element(By.CSS_SELECTOR, selector)
                    if load_more_btn.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_btn)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", load_more_btn)
                        load_more_found = True
                        load_more_attempts += 1
                        print(f"🔄 Clicked 'Load More' (attempt {load_more_attempts})")
                        
                        # Wait for new content
                        print("⏳ Waiting for new content to load...")
                        time.sleep(5)
                        break
                except StaleElementReferenceException:
                    continue
                except:
                    continue
        
        # Strategy 3: Try to find any clickable element with load more text in the page
        if not load_more_found:
            try:
                # Find all buttons and links on the page
                all_buttons = driver.find_elements(By.TAG_NAME, "button")
                all_links = driver.find_elements(By.TAG_NAME, "a")
                all_clickables = all_buttons + all_links
                
                for element in all_clickables:
                    try:
                        text = element.text.strip().lower()
                        if any(phrase in text for phrase in ["load more", "show more", "view more", "see more"]):
                            if element.is_displayed():
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                time.sleep(1)
                                driver.execute_script("arguments[0].click();", element)
                                load_more_found = True
                                load_more_attempts += 1
                                print(f"🔄 Clicked 'Load More' element (attempt {load_more_attempts})")
                                time.sleep(5)
                                break
                    except:
                        continue
            except:
                pass
        
        # If no Load More button found, we might be done
        if not load_more_found:
            print("ℹ️ No 'Load More' button found. All items may be loaded.")
            # Scroll to trigger any lazy loading
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            # Check one more time if new cards appeared
            if len(data) == current_count:
                break
        
        # Safety check
        if load_more_attempts >= max_load_more_attempts:
            print(f"⚠️ Reached maximum load more attempts ({max_load_more_attempts})")
            break

finally:
    # Save to Excel
    if data:
        df = pd.DataFrame(data)
        df.drop_duplicates(subset=["Company Name"], inplace=True)
        output_file = "worldhealthexpo_exhibitors.xlsx"
        df.to_excel(output_file, index=False)
        
        print("\n" + "="*60)
        print("📊 FINAL SUMMARY")
        print("="*60)
        print(f"✅ Total exhibitors scraped: {len(data)}")
        print(f"✅ Unique exhibitors: {len(df)}")
        print(f"✅ Saved to: {output_file}")
        print("\n📋 All Company Names:")
        print("-"*60)
        for idx, name in enumerate(df["Company Name"], 1):
            booth = df.iloc[idx-1]["Booth No"] if idx <= len(df) else ""
            print(f"{idx}. {name} {'(Booth: ' + booth + ')' if booth else ''}")
        print("-"*60)
        print(f"\n✅ Scraping completed successfully!")
    else:
        print("\n⚠️ No data scraped. Please check the selectors.")
        print("💡 Tip: The page structure might be different. Check the console output above.")
    driver.quit()   