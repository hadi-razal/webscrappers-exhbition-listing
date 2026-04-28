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

class NStandsScraper:
    def __init__(self, base_url, headless=True):
        """
        Initialize the scraper
        
        Args:
            base_url: The URL to scrape (e.g., 'https://www.nstands.com/austria/')
            headless: Whether to run browser in headless mode
        """
        self.base_url = base_url.rstrip('/')
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
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 15)
        
    def extract_company_data_from_detail_page(self):
        """
        Extract company name and country from the detail page
        
        Returns:
            dict: Dictionary with 'Company Name' and 'Country' keys
        """
        data = {
            'Company Name': '',
            'Country': ''
        }
        
        try:
            # Wait for the page to load
            time.sleep(2)
            
            # Extract company name
            try:
                name_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1.nTitle.section-sm.text-white.display-1"))
                )
                data['Company Name'] = name_element.text.strip()
            except TimeoutException:
                # Try alternative selector
                try:
                    name_element = self.driver.find_element(By.CSS_SELECTOR, "h1.nTitle")
                    data['Company Name'] = name_element.text.strip()
                except NoSuchElementException:
                    logging.warning("Could not find company name")
            
            # Extract country (format: "City, Country")
            try:
                country_element = self.driver.find_element(By.CSS_SELECTOR, "p.font-lg.text-white")
                location_text = country_element.text.strip()
                data['Country'] = location_text
                # If format is "City, Country", extract just the country
                if ',' in location_text:
                    data['Country'] = location_text.split(',')[-1].strip()
            except NoSuchElementException:
                # Try alternative selector
                try:
                    country_element = self.driver.find_element(By.CSS_SELECTOR, "p.text-white")
                    location_text = country_element.text.strip()
                    data['Country'] = location_text
                    if ',' in location_text:
                        data['Country'] = location_text.split(',')[-1].strip()
                except NoSuchElementException:
                    logging.warning("Could not find country")
            
        except Exception as e:
            logging.error(f"Error extracting data from detail page: {e}")
        
        return data
    
    def scrape_company_detail(self, company_url):
        """
        Navigate to company detail page and extract data
        
        Args:
            company_url: URL of the company detail page
            
        Returns:
            dict: Dictionary with company data
        """
        try:
            # Navigate to the detail page
            self.driver.get(company_url)
            time.sleep(2)
            
            # Extract data from detail page
            data = self.extract_company_data_from_detail_page()
            data['Company URL'] = company_url
            
            return data
            
        except Exception as e:
            logging.error(f"Error scraping company detail page {company_url}: {e}")
            return {
                'Company Name': '',
                'Country': '',
                'Company URL': company_url
            }
    
    def get_company_links_from_page(self):
        """
        Extract all company links from the current listing page
        
        Returns:
            list: List of company detail page URLs
        """
        company_links = []
        
        try:
            # Wait for company cards to load
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.x-item-content"))
            )
            time.sleep(2)
            
            # Find all company cards
            company_cards = self.driver.find_elements(By.CSS_SELECTOR, "div.x-item-content")
            
            for card in company_cards:
                try:
                    # Find the link inside the card
                    link_element = card.find_element(By.CSS_SELECTOR, "p.x-item-title.mb-1 a")
                    href = link_element.get_attribute('href')
                    
                    if href:
                        # Make sure it's a full URL
                        if not href.startswith('http'):
                            href = urljoin(self.base_url, href)
                        company_links.append(href)
                        
                except NoSuchElementException:
                    continue
                    
        except TimeoutException:
            logging.warning("Timeout waiting for company cards to load")
        except Exception as e:
            logging.error(f"Error extracting company links: {e}")
        
        return company_links
    
    def has_next_page(self):
        """
        Check if there's a next page available
        
        Returns:
            tuple: (has_next, next_url) or (False, None)
        """
        try:
            # Look for the "Next" pagination link - try multiple selectors
            next_link = None
            
            # Try selector with rel attribute containing 'next'
            try:
                next_link = self.driver.find_element(By.CSS_SELECTOR, "a.page-link[rel*='next']")
            except NoSuchElementException:
                # Try alternative: look for link with text "Next"
                try:
                    next_link = self.driver.find_element(By.XPATH, "//a[@class='page-link' and contains(text(), 'Next')]")
                except NoSuchElementException:
                    # Try looking for any pagination link with "Next" in rel
                    try:
                        pagination_links = self.driver.find_elements(By.CSS_SELECTOR, "a.page-link")
                        for link in pagination_links:
                            rel_attr = link.get_attribute('rel') or ''
                            if 'next' in rel_attr.lower():
                                next_link = link
                                break
                    except:
                        pass
            
            if next_link:
                next_url = next_link.get_attribute('href')
                if next_url:
                    logging.info(f"Found next page link: {next_url}")
                    return (True, next_url)
                    
        except Exception as e:
            logging.warning(f"Error checking for next page: {e}")
        
        logging.info("No next page found - reached the end")
        return (False, None)
    
    def scrape_all_pages(self, source_url=None):
        """
        Scrape all pages of companies from the given URL
        Continues until no more pages are found
        
        Args:
            source_url: The original URL that was provided (for tracking)
        """
        try:
            # Use source_url if provided, otherwise use base_url
            url_to_scrape = source_url if source_url else self.base_url
            
            # Navigate to the base URL
            logging.info(f"🌐 Navigating to {url_to_scrape}")
            self.driver.get(url_to_scrape)
            time.sleep(3)
            
            page_number = 1
            total_companies_scraped = 0
            
            while True:
                print(f"\n{'='*60}")
                print(f"📄 PAGE {page_number}")
                print(f"{'='*60}")
                logging.info(f"📄 Starting to scrape page {page_number}")
                
                # Get all company links from current page
                company_links = self.get_company_links_from_page()
                
                if not company_links:
                    logging.warning(f"No companies found on page {page_number}. This might be the last page.")
                    # Still check for next page in case there are more pages
                else:
                    logging.info(f"✅ Found {len(company_links)} companies on page {page_number}")
                    
                    # Scrape each company
                    for idx, company_url in enumerate(company_links, 1):
                        print(f"  [{idx}/{len(company_links)}] Processing: {company_url}")
                        logging.info(f"Scraping company {idx}/{len(company_links)} on page {page_number}: {company_url}")
                        
                        company_data = self.scrape_company_detail(company_url)
                        
                        if company_data.get('Company Name'):
                            # Add source URL to track where this company came from
                            company_data['Source URL'] = url_to_scrape
                            self.all_data.append(company_data)
                            total_companies_scraped += 1
                            print(f"  ✅ Scraped: {company_data['Company Name']} - {company_data.get('Country', 'N/A')}")
                            logging.info(f"✅ Scraped: {company_data['Company Name']} - {company_data.get('Country', 'N/A')}")
                        else:
                            logging.warning(f"⚠️ Could not extract data from {company_url}")
                        
                        # Save progress every 10 companies
                        if total_companies_scraped % 10 == 0 and total_companies_scraped > 0:
                            self.save_progress()
                            print(f"  💾 Progress saved: {total_companies_scraped} companies so far")
                        
                        # Small delay between requests
                        time.sleep(1)
                
                # Check for next page BEFORE moving on
                print(f"\n🔍 Checking for next page...")
                has_next, next_url = self.has_next_page()
                
                if not has_next:
                    print(f"\n✅ Reached the end! No more pages found.")
                    logging.info(f"✅ Reached the end! No more pages found. Total pages scraped: {page_number}")
                    break
                
                # Navigate to next page
                print(f"➡️ Moving to page {page_number + 1}: {next_url}")
                logging.info(f"➡️ Moving to next page ({page_number + 1}): {next_url}")
                self.driver.get(next_url)
                time.sleep(3)  # Wait for page to load
                page_number += 1
                
                # Safety limit to prevent infinite loops
                if page_number > 100:
                    logging.warning("⚠️ Reached maximum page limit (100). Stopping to prevent infinite loop.")
                    print(f"⚠️ Reached maximum page limit (100). Stopping.")
                    break
            
            print(f"\n{'='*60}")
            print(f"🎉 SCRAPING COMPLETE!")
            print(f"{'='*60}")
            print(f"📊 Total pages scraped: {page_number}")
            print(f"📊 Total companies scraped: {total_companies_scraped}")
            print(f"{'='*60}\n")
            logging.info(f"✅ Scraping completed. Total pages: {page_number}, Total companies: {total_companies_scraped}")
            
        except Exception as e:
            logging.error(f"❌ Error in scraping process: {e}")
            print(f"\n❌ Error occurred: {e}")
        finally:
            self.save_final_data()
    
    def save_progress(self):
        """Save progress to Excel file"""
        if self.all_data:
            df = pd.DataFrame(self.all_data)
            df.to_excel("nstands_progress.xlsx", index=False)
            logging.info(f"💾 Progress saved: {len(self.all_data)} companies")
    
    def save_final_data(self):
        """Save final data to Excel file"""
        if self.all_data:
            df = pd.DataFrame(self.all_data)
            
            # Reorder columns to put Source URL at the end for better readability
            if 'Source URL' in df.columns:
                cols = [col for col in df.columns if col != 'Source URL'] + ['Source URL']
                df = df[cols]
            
            df.to_excel("nstands_complete.xlsx", index=False)
            
            logging.info(f"🎉 Final data saved: {len(self.all_data)} companies")
            logging.info("📊 Summary Report:")
            logging.info(f"   - Total companies: {len(self.all_data)}")
            
            # Count by source URL
            if 'Source URL' in df.columns:
                source_counts = df['Source URL'].value_counts()
                logging.info(f"   - Companies by source URL:")
                for source, count in source_counts.items():
                    logging.info(f"     {source}: {count} companies")
            
            # Count by country
            if 'Country' in df.columns:
                countries = df['Country'].value_counts()
                logging.info(f"   - Top countries:")
                for country, count in countries.head(5).items():
                    logging.info(f"     {country}: {count}")
        else:
            logging.warning("⚠️ No data to save")
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.driver.quit()
            logging.info("🧹 Browser closed")
        except:
            pass

def main():
    """Main execution function - supports multiple URLs in one session"""
    print("🚀 Starting NStands Company Scraper...")
    print("=" * 60)
    print("📝 You can enter multiple URLs. All data will be combined.")
    print("=" * 60)
    
    # Ask about headless mode (once at the start)
    headless_input = input("\nRun in headless mode? (y/n, default y): ").strip().lower()
    headless = headless_input != 'n'
    
    # Initialize scraper with first URL (will be updated)
    scraper = None
    all_urls_scraped = []
    total_companies_all_urls = 0
    
    try:
        while True:
            # Get URL from user
            print("\n" + "=" * 60)
            url = input("\nEnter URL to scrape (or press Enter to finish): ").strip()
            
            if not url:
                print("\n✅ No more URLs. Finishing up...")
                break
            
            all_urls_scraped.append(url)
            
            # Initialize or reuse scraper
            if scraper is None:
                # First URL - initialize scraper
                scraper = NStandsScraper(url, headless=headless)
                print(f"\n🌐 Starting to scrape: {url}")
            else:
                # Update base URL for subsequent URLs (but keep driver open)
                scraper.base_url = url.rstrip('/')
                print(f"\n🌐 Starting to scrape: {url}")
            
            # Scrape this URL
            try:
                companies_before = len(scraper.all_data)
                scraper.scrape_all_pages(source_url=url)
                companies_after = len(scraper.all_data)
                companies_from_this_url = companies_after - companies_before
                total_companies_all_urls += companies_from_this_url
                
                print(f"\n✅ Completed scraping: {url}")
                print(f"   Companies from this URL: {companies_from_this_url}")
                print(f"   Total companies so far: {companies_after}")
                
                # Save progress after each URL
                scraper.save_progress()
                
            except Exception as e:
                print(f"\n❌ Error scraping {url}: {e}")
                logging.error(f"Error scraping {url}: {e}")
                continue
            
            # Ask if user wants to add another URL
            print("\n" + "-" * 60)
            continue_input = input("Add another URL? (y/n, default y): ").strip().lower()
            if continue_input == 'n':
                print("\n✅ Finishing up...")
                break
        
        # Final save with all combined data
        if scraper and scraper.all_data:
            print("\n" + "=" * 60)
            print("💾 Saving all combined data...")
            print("=" * 60)
            
            scraper.save_final_data()
            
            print(f"\n📊 FINAL SUMMARY:")
            print(f"   - Total URLs scraped: {len(all_urls_scraped)}")
            print(f"   - Total companies collected: {len(scraper.all_data)}")
            print(f"   - Data saved to: nstands_complete.xlsx")
            print(f"\n📋 URLs scraped:")
            for idx, url in enumerate(all_urls_scraped, 1):
                print(f"   {idx}. {url}")
        else:
            print("\n⚠️ No data collected. Nothing to save.")
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Scraping interrupted by user")
        if scraper:
            scraper.save_final_data()
            print("💾 Progress saved before exit")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        if scraper:
            scraper.save_final_data()
    finally:
        if scraper:
            scraper.cleanup()
        print("\n" + "=" * 60)
        print("🎯 Scraping session completed!")
        print("=" * 60)

if __name__ == "__main__":
    main()
