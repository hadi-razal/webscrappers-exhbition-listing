import requests
from bs4 import BeautifulSoup
import time
import json
import csv
from urllib.parse import urljoin
import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ChromeAssistedScraper:
    def __init__(self):
        self.base_url = "https://automechanika-dubai.ae.messefrankfurt.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        })
        self.exhibitors_data = []
    
    def manual_chrome_instructions(self):
        """Print instructions for manual Chrome extraction"""
        print("""
🔧 MANUAL CHROME ASSISTED SCRAPING INSTRUCTIONS:

STEP 1: Open Chrome and go to:
https://automechanika-dubai.ae.messefrankfurt.com/dubai/en/exhibitor-search/exhibitor-list.html

STEP 2: Wait for the page to load completely

STEP 3: Open Developer Tools (F12 or Right-click → Inspect)

STEP 4: Go to Console tab and run these commands one by one:

// Get all exhibitor items
const items = document.querySelectorAll('.m-search-result-item');
console.log(`Found ${items.length} exhibitor items`);

// Extract basic info from first few items
items.forEach((item, index) => {
    if (index < 5) {
        const nameElem = item.querySelector('.ex-exhibitor-search-result-itemheadline');
        const descElem = item.querySelector('.ex-exhibitor-search-result-itemcopy');
        const locationElem = item.querySelector('.ex-exhibitor-search-result-itemlocation');
        
        console.log(`Item ${index + 1}:`);
        console.log(`  Name: ${nameElem?.textContent?.trim()}`);
        console.log(`  Desc: ${descElem?.textContent?.trim()}`);
        console.log(`  Location: ${locationElem?.textContent?.trim()}`);
    }
});

// Check pagination
const nextBtn = document.querySelector('a.next, .pagination .next a');
console.log('Next button:', nextBtn);

STEP 5: Copy the output and share it with me.

This will help us understand the exact structure!
        """)
    
    def extract_from_html_file(self, html_file_path):
        """Extract data from saved HTML file"""
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all exhibitor items
            exhibitor_items = soup.find_all('div', class_='m-search-result-item')
            print(f"Found {len(exhibitor_items)} exhibitor items in HTML file")
            
            for i, item in enumerate(exhibitor_items):
                exhibitor_data = self.extract_exhibitor_data(item)
                if exhibitor_data and exhibitor_data.get('name') != 'N/A':
                    self.exhibitors_data.append(exhibitor_data)
                    print(f"✅ Extracted: {exhibitor_data['name']}")
                
                # Only process first few for testing
                if i >= 5:
                    break
            
            return True
            
        except Exception as e:
            print(f"Error extracting from HTML file: {e}")
            return False
    
    def extract_exhibitor_data(self, item):
        """Extract data from exhibitor item"""
        try:
            # Name
            name_elem = item.find('h4', class_='ex-exhibitor-search-result-itemheadline')
            name = name_elem.get_text(strip=True) if name_elem else "N/A"
            
            # Description
            desc_elem = item.find('p', class_='ex-exhibitor-search-result-itemcopy')
            description = desc_elem.get_text(strip=True) if desc_elem else "N/A"
            
            # Location/Stand
            location_elem = item.find('div', class_='ex-exhibitor-search-result-itemlocation')
            location = location_elem.get_text(strip=True) if location_elem else "N/A"
            
            # Detail URL
            detail_url = None
            if name_elem:
                link = name_elem.find('a')
                if link and link.get('href'):
                    detail_url = link.get('href')
                    if not detail_url.startswith('http'):
                        detail_url = urljoin(self.base_url, detail_url)
            
            # Images
            logo_img = item.find('img', class_='ex-exhibitor-search-result-itemexhibitor-image')
            logo_url = logo_img.get('src') if logo_img else "N/A"
            
            product_img = item.find('img', class_='ex-exhibitor-search-result-itemimage-img')
            product_url = product_img.get('src') if product_img else "N/A"
            
            return {
                'name': name,
                'description': description,
                'location': location,
                'detail_url': detail_url,
                'logo_url': logo_url,
                'product_image_url': product_url
            }
            
        except Exception as e:
            print(f"Error extracting exhibitor data: {e}")
            return None
    
    def get_detailed_info_manual(self, detail_url):
        """Get detailed info from detail page - manual approach"""
        try:
            print(f"📄 Fetching detail page: {detail_url}")
            response = self.session.get(detail_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            detailed_info = {}
            
            # Extract contact information
            contact_box = soup.find('div', class_='ex-contact-box__container-address')
            if contact_box:
                # Address
                address_elem = contact_box.find('p', class_='ex-contact-box__address-field-full-address')
                if address_elem:
                    detailed_info['address'] = address_elem.get_text(separator='\n').strip()
                
                # Telephone
                tel_elem = contact_box.find('a', class_='ex-contact-box__address-field-tel-number')
                if tel_elem:
                    detailed_info['telephone'] = tel_elem.get_text(strip=True)
            
            # Email
            email_btn = soup.find('a', class_='ex-contact-box__contact-btn')
            if email_btn and 'mailto:' in email_btn.get('href', ''):
                detailed_info['email'] = email_btn['href'].replace('mailto:', '').split('?')[0]
            
            # Website
            website_link = soup.find('a', class_='ex-contact-box__website-link')
            if website_link:
                detailed_info['website'] = website_link.get('href', 'N/A')
            
            # Social media
            social_links = {}
            social_container = soup.find('div', class_='ex-contact-box__social-links-container')
            if social_container:
                linkedin_links = social_container.find_all('a', class_='icon-linkedin')
                social_links['linkedin'] = [link.get('href') for link in linkedin_links if link.get('href')]
                
                twitter_links = social_container.find_all('a', class_='icon-twitter')
                social_links['twitter'] = [link.get('href') for link in twitter_links if link.get('href')]
            
            detailed_info['social_links'] = social_links
            
            # Booth information
            booth_container = soup.find('div', class_='ex-contact-box__container-location')
            if booth_container:
                hall_elem = booth_container.find('span', class_='ex-contact-box__container-location-hall')
                detailed_info['hall'] = hall_elem.get_text(strip=True) if hall_elem else "N/A"
                
                booth_elem = booth_container.find('span', class_='ex-contact-box__container-location-stand')
                detailed_info['booth_number'] = booth_elem.get_text(strip=True) if booth_elem else "N/A"
            
            return detailed_info
            
        except Exception as e:
            print(f"Error getting detailed info: {e}")
            return {}
    
    def save_data(self):
        """Save extracted data"""
        if not self.exhibitors_data:
            print("No data to save")
            return
        
        # Save to JSON
        with open('manual_extraction_data.json', 'w', encoding='utf-8') as f:
            json.dump(self.exhibitors_data, f, indent=2, ensure_ascii=False)
        print("✅ Data saved to manual_extraction_data.json")
        
        # Save to CSV
        if self.exhibitors_data:
            fieldnames = ['name', 'description', 'location', 'detail_url', 'logo_url', 'product_image_url']
            with open('manual_extraction_data.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for item in self.exhibitors_data:
                    row = {field: item.get(field, '') for field in fieldnames}
                    writer.writerow(row)
            print("✅ Data saved to manual_extraction_data.csv")

def main():
    """Main function with multiple options"""
    print("🛠️ CHROME-ASSISTED AUTOMECHANIKA SCRAPER")
    print("=" * 50)
    
    scraper = ChromeAssistedScraper()
    
    print("Choose an option:")
    print("1. Show manual Chrome extraction instructions")
    print("2. Extract from saved HTML file (debug_automechanika.html)")
    print("3. Try automated extraction (basic)")
    
    choice = input("Enter choice (1/2/3): ").strip()
    
    if choice == "1":
        scraper.manual_chrome_instructions()
        
    elif choice == "2":
        # Try to extract from the HTML file we saved earlier
        if scraper.extract_from_html_file("debug_automechanika.html"):
            print(f"\n✅ Successfully extracted {len(scraper.exhibitors_data)} exhibitors")
            
            # Try to get detailed info for first exhibitor
            if scraper.exhibitors_data and scraper.exhibitors_data[0].get('detail_url'):
                print("\n🔍 Getting detailed info for first exhibitor...")
                detail_url = scraper.exhibitors_data[0]['detail_url']
                detailed_info = scraper.get_detailed_info_manual(detail_url)
                
                if detailed_info:
                    print("📋 Detailed info found:")
                    for key, value in detailed_info.items():
                        print(f"   {key}: {value}")
                    
                    # Merge detailed info
                    scraper.exhibitors_data[0].update(detailed_info)
            
            scraper.save_data()
            
            # Show sample
            print("\n🎯 SAMPLE EXTRACTED DATA:")
            for i, exhibitor in enumerate(scraper.exhibitors_data[:3]):
                print(f"\n{i+1}. {exhibitor.get('name')}")
                print(f"   Description: {exhibitor.get('description', 'N/A')[:100]}...")
                print(f"   Location: {exhibitor.get('location', 'N/A')}")
                print(f"   Detail URL: {exhibitor.get('detail_url', 'N/A')}")
        
    elif choice == "3":
        print("🚧 Automated extraction coming soon...")
        # We can implement basic requests-based scraping here
        
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()