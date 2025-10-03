import requests
from bs4 import BeautifulSoup
import time
import json
import csv
from urllib.parse import urljoin
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Big5ExhibitorScraper:
    def __init__(self, headless=True):
        self.base_url = "https://exhibitors.big5constructsaudi.com/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.exhibitors_data = []
        
        # Setup Chrome driver
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
    def scrape_all_pages_selenium(self):
        """Scrape all pages using Selenium to handle JavaScript pagination"""
        try:
            logging.info("Starting Selenium scraping...")
            
            # Navigate to the main exhibitor page
            self.driver.get(f"{self.base_url}hvac-r-expo-saudi-2025/Exhibitor")
            time.sleep(5)
            
            total_exhibitors = 0
            page_count = 0
            
            while True:
                page_count += 1
                logging.info(f"Scraping page {page_count}")
                
                # Wait for cards to load
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "card"))
                )
                
                # Get page source and parse with BeautifulSoup
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Extract exhibitors from current page
                cards = soup.find_all('div', class_='card')
                logging.info(f"Found {len(cards)} exhibitor cards on page {page_count}")
                
                for card in cards:
                    exhibitor_data = self.extract_exhibitor_data(card)
                    if exhibitor_data:
                        self.exhibitors_data.append(exhibitor_data)
                        logging.info(f"Scraped: {exhibitor_data['name']}")
                
                total_exhibitors += len(cards)
                
                # Check if there's a next page
                next_buttons = self.driver.find_elements(By.XPATH, "//a[contains(@onclick, 'searchFilter')]")
                next_button = None
                
                # Find the "»" button
                for button in next_buttons:
                    if "»" in button.text:
                        next_button = button
                        break
                
                if not next_button:
                    logging.info("No more pages found")
                    break
                
                # Check if we're on the last page by looking at pagination text
                pagination_divs = self.driver.find_elements(By.CLASS_NAME, "list-pagination")
                if pagination_divs:
                    pagination_text = pagination_divs[0].text
                    if "Showing" in pagination_text:
                        # Extract current range and total
                        match = re.search(r'Showing (\d+) to (\d+) of (\d+)', pagination_text)
                        if match:
                            current_end = int(match.group(2))
                            total = int(match.group(3))
                            if current_end >= total:
                                logging.info("Reached the last page")
                                break
                
                # Click next page using JavaScript
                try:
                    self.driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(4)  # Wait for page to load
                    
                    # Wait for new content to load
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "card"))
                    )
                    
                except Exception as e:
                    logging.error(f"Error clicking next button: {e}")
                    break
                
                # Safety break to avoid infinite loops
                if page_count >= 50:
                    logging.warning("Reached maximum page limit")
                    break
            
            logging.info(f"Scraping completed. Total pages: {page_count}, Total exhibitors: {len(self.exhibitors_data)}")
            
        except Exception as e:
            logging.error(f"Error in Selenium scraping: {e}")
        finally:
            self.driver.quit()
    
    def extract_exhibitor_data(self, card):
        """Extract data from a single exhibitor card"""
        try:
            # Extract name
            name_element = card.find('h5', class_='card-title')
            if name_element:
                name_link = name_element.find('a')
                name = name_link.text.strip() if name_link else name_element.text.strip()
            else:
                name = "N/A"
            
            # Extract detail URL
            detail_url = None
            if name_element:
                name_link = name_element.find('a')
                if name_link:
                    detail_url = name_link.get('href')
                    if detail_url and not detail_url.startswith('http'):
                        detail_url = urljoin(self.base_url, detail_url)
            
            # Extract stand number
            stand_element = card.find('h6', class_='card-subtitle')
            stand_info = stand_element.text.strip() if stand_element else "N/A"
            
            # Extract country
            country_element = card.find('p', class_='card-text')
            country = country_element.text.strip() if country_element else "N/A"
            
            # Check if featured
            featured_badge = card.find('span', class_='featured-badge')
            is_featured = featured_badge is not None
            
            # Extract image URL
            img_element = card.find('img', class_='card-img-top')
            image_url = img_element.get('src') if img_element else "N/A"
            
            # Extract available resources
            resources = []
            footer = card.find('div', class_='card-footer')
            if footer:
                resource_links = footer.find_all('a')
                for link in resource_links:
                    title = link.get('title', '')
                    if title:
                        resources.append(title)
            
            # Check for eco trail icon
            eco_trail = card.find('div', class_='ecotrailicon-img')
            has_eco_trail = eco_trail is not None
            
            # Get detailed information if we have a detail URL
            detailed_info = {}
            if detail_url:
                try:
                    detailed_info = self.get_detailed_info(detail_url)
                except Exception as e:
                    logging.warning(f"Could not get detailed info for {name}: {e}")
            
            exhibitor_data = {
                'name': name,
                'stand_info': stand_info,
                'country': country,
                'is_featured': is_featured,
                'has_eco_trail': has_eco_trail,
                'image_url': image_url,
                'resources': resources,
                'detail_url': detail_url,
                **detailed_info
            }
            
            return exhibitor_data
            
        except Exception as e:
            logging.error(f"Error extracting exhibitor data: {e}")
            return None
    
    def get_detailed_info(self, detail_url):
        """Get detailed information from exhibitor's detail page"""
        try:
            response = self.session.get(detail_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            detailed_info = {}
            
            # Extract website
            website_element = soup.find('i', class_='fa-solid fa-globe')
            if website_element:
                website_parent = website_element.parent
                if website_parent:
                    website_link = website_parent.find('a')
                    if website_link:
                        website_url = website_link.get('href', '').strip()
                        if website_url and website_url != 'N/A':
                            detailed_info['website'] = website_url
            
            # Extract email (if available)
            email_element = soup.find('i', class_='fa-regular fa-envelope')
            if email_element:
                email_parent = email_element.parent
                if email_parent:
                    email_link = email_parent.find('a')
                    if email_link and 'mailto:' in email_link.get('href', ''):
                        email = email_link.get('href', '').replace('mailto:', '').strip()
                        if email:
                            detailed_info['email'] = email
            
            # Extract categories
            categories = []
            badge_elements = soup.find_all('span', class_='badge bg-secondary')
            for badge in badge_elements:
                category_text = badge.text.strip()
                if category_text:
                    categories.append(category_text)
            detailed_info['categories'] = categories
            
            # Extract company description
            about_tab = soup.find('div', id='pills-About')
            description = ""
            if about_tab:
                paragraphs = about_tab.find_all('p')
                description_texts = []
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 10:  # Only include substantial text
                        description_texts.append(text)
                description = ' '.join(description_texts)
            detailed_info['description'] = description
            
            return detailed_info
            
        except Exception as e:
            logging.error(f"Error getting detailed info from {detail_url}: {e}")
            return {}
    
    def save_to_json(self, filename="exhibitors_data.json"):
        """Save data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.exhibitors_data, f, indent=2, ensure_ascii=False)
        logging.info(f"Data saved to {filename}")
    
    def save_to_csv(self, filename="exhibitors_data.csv"):
        """Save data to CSV file"""
        if not self.exhibitors_data:
            logging.warning("No data to save")
            return
        
        fieldnames = [
            'name', 'stand_info', 'country', 'is_featured', 'has_eco_trail',
            'website', 'email', 'categories', 'description', 
            'image_url', 'detail_url', 'resources'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for exhibitor in self.exhibitors_data:
                row = {
                    'name': exhibitor.get('name', ''),
                    'stand_info': exhibitor.get('stand_info', ''),
                    'country': exhibitor.get('country', ''),
                    'is_featured': exhibitor.get('is_featured', False),
                    'has_eco_trail': exhibitor.get('has_eco_trail', False),
                    'website': exhibitor.get('website', ''),
                    'email': exhibitor.get('email', ''),
                    'categories': ', '.join(exhibitor.get('categories', [])),
                    'description': exhibitor.get('description', ''),
                    'image_url': exhibitor.get('image_url', ''),
                    'detail_url': exhibitor.get('detail_url', ''),
                    'resources': ', '.join(exhibitor.get('resources', []))
                }
                writer.writerow(row)
        
        logging.info(f"Data saved to {filename}")
    
    def display_summary(self):
        """Display summary of scraped data"""
        if not self.exhibitors_data:
            print("No data collected")
            return
        
        print(f"\n=== SCRAPING SUMMARY ===")
        print(f"Total exhibitors: {len(self.exhibitors_data)}")
        print(f"Featured exhibitors: {sum(1 for e in self.exhibitors_data if e.get('is_featured'))}")
        print(f"Eco trail exhibitors: {sum(1 for e in self.exhibitors_data if e.get('has_eco_trail'))}")
        
        # Count by country
        countries = {}
        for exhibitor in self.exhibitors_data:
            country = exhibitor.get('country', 'Unknown')
            countries[country] = countries.get(country, 0) + 1
        
        print(f"\nExhibitors by country (top 10):")
        for country, count in sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {country}: {count}")
        
        # Count with websites
        with_websites = sum(1 for e in self.exhibitors_data if e.get('website') and e.get('website') not in ['', 'N/A'])
        print(f"\nExhibitors with websites: {with_websites}")
        
        # Count with emails
        with_emails = sum(1 for e in self.exhibitors_data if e.get('email'))
        print(f"Exhibitors with emails: {with_emails}")
        
        # Display sample data
        print(f"\n=== SAMPLE DATA ===")
        for i, exhibitor in enumerate(self.exhibitors_data[:3]):
            print(f"\n{i+1}. {exhibitor.get('name')}")
            print(f"   Stand: {exhibitor.get('stand_info')}")
            print(f"   Country: {exhibitor.get('country')}")
            print(f"   Website: {exhibitor.get('website', 'N/A')}")
            print(f"   Email: {exhibitor.get('email', 'N/A')}")
            print(f"   Categories: {exhibitor.get('categories', [])}")
            print(f"   Featured: {exhibitor.get('is_featured', False)}")
            print(f"   Eco Trail: {exhibitor.get('has_eco_trail', False)}")

def main():
    """Main function to run the scraper"""
    print("Big 5 Construct Saudi 2025 Exhibitor Scraper")
    print("=" * 50)
    
    # Ask user if they want headless mode
    headless_input = input("Run in headless mode? (y/n, default y): ").strip().lower()
    headless = headless_input != 'n'
    
    scraper = Big5ExhibitorScraper(headless=headless)
    
    try:
        print("\nStarting scraping process...")
        print("This may take several minutes for all 43 pages...")
        
        scraper.scrape_all_pages_selenium()
        
        # Save data
        scraper.save_to_json()
        scraper.save_to_csv()
        
        # Display summary
        scraper.display_summary()
        
        print(f"\nScraping completed successfully!")
        print(f"Check 'exhibitors_data.json' and 'exhibitors_data.csv' for the complete data.")
        
    except Exception as e:
        logging.error(f"Error in main execution: {e}")
        print(f"An error occurred: {e}")
    finally:
        # Ensure driver is closed
        try:
            scraper.driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()