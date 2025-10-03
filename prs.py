import time
import logging
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class PRSEventScraper:
    def __init__(self):
        self.base_url = "https://prseventmea.com/prsmea2025/en/page/exhibitor-list"
        self.driver = None
        self.exhibitors_data = []

    def init_selenium(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def scrape_list_page(self):
        """Scrape exhibitor list and go inside each profile"""
        self.driver.get(self.base_url)
        time.sleep(5)

        WebDriverWait(self.driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tr.exhibitor.list"))
        )

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        rows = soup.select("tr.exhibitor.list")

        logging.info(f"Found {len(rows)} exhibitors in list page.")

        for idx, row in enumerate(rows, start=1):
            try:
                name_tag = row.select_one(".td-name a")
                company_name = name_tag.get_text(strip=True) if name_tag else "N/A"
                profile_link = name_tag["href"] if name_tag else None
                if profile_link and profile_link.startswith(".."):
                    profile_link = "https://prseventmea.com/prsmea2025/en/" + profile_link.lstrip("./")

                categories = [c.get_text(strip=True) for c in row.select(".td-categories span.exhibitor-category")]
                stand = row.select_one(".td-stand")
                stand = stand.get_text(strip=True) if stand else "N/A"

                logging.info(f"\n[{idx}] {company_name} ({profile_link})")

                # Visit profile page
                profile_data = self.scrape_profile_page(profile_link) if profile_link else {}

                exhibitor = {
                    "Company Name": company_name,
                    "Categories": "; ".join(categories),
                    "Stand (List Page)": stand,
                    "Profile URL": profile_link
                }
                exhibitor.update(profile_data)

                # Print the data (console log)
                for k, v in exhibitor.items():
                    print(f"   {k}: {v}")

                self.exhibitors_data.append(exhibitor)

                # Small delay to avoid blocking
                time.sleep(2)
            except Exception as e:
                logging.error(f"Error scraping row {idx}: {e}")

    def scrape_profile_page(self, url):
        """Scrape individual exhibitor profile page"""
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".ev-exhibitor-profile"))
            )
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # Core fields
            company_name = soup.select_one(".exhibitor-company_name")
            company_name = company_name.get_text(strip=True) if company_name else "N/A"

            stand_number = soup.select_one(".exhibitor-stand_number span")
            stand_number = stand_number.get_text(strip=True) if stand_number else "N/A"

            stand_location = soup.select_one(".exhibitor-stand_location")
            stand_location = stand_location.get_text(strip=True).replace("Stand Location:", "").strip() if stand_location else "N/A"

            website = soup.select_one(".exhibitor-company_url a")
            website = website.get("href", "N/A") if website else "N/A"

            # Social links (LinkedIn, etc.)
            social_links = {a.get("href"): a.get("href") for a in soup.select(".exhibitor-social a")}
            linkedin = next((link for link in social_links if "linkedin" in link.lower()), "N/A")

            email = soup.select_one(".exhibitor-contact_email a")
            email = email.get_text(strip=True) if email else "N/A"

            phone = soup.select_one(".exhibitor-telephone span:nth-of-type(2)")
            phone = phone.get_text(strip=True) if phone else "N/A"

            country = soup.select_one(".exhibitor-address_country span:nth-of-type(2)")
            country = country.get_text(strip=True) if country else "N/A"

            address = soup.select_one(".exhibitor-address_main div:nth-of-type(2)")
            address = address.get_text(" ", strip=True) if address else "N/A"

            contact_person = soup.select_one(".exhibitor-name-parts span.field-value")
            contact_person = contact_person.get_text(strip=True) if contact_person else "N/A"

            brochures = [a["href"] for a in soup.select(".exhibitor-brochure a, .exhibitor-brochure2 a, .exhibitor-brochure3 a")]

            return {
                "Company Name (Profile)": company_name,
                "Stand Number": stand_number,
                "Stand Location": stand_location,
                "Website": website,
                "LinkedIn": linkedin,
                "Email": email,
                "Phone": phone,
                "Country": country,
                "Address": address,
                "Contact Person": contact_person,
                "Brochures": "; ".join(brochures)
            }
        except Exception as e:
            logging.error(f"Error scraping profile page {url}: {e}")
            return {}

    def save_to_excel(self, filename="prs_exhibitors.xlsx"):
        df = pd.DataFrame(self.exhibitors_data)
        df.to_excel(filename, index=False)
        logging.info(f"✅ Data saved to {filename}")

    def run(self):
        self.init_selenium()
        self.scrape_list_page()
        self.save_to_excel()
        self.driver.quit()


if __name__ == "__main__":
    scraper = PRSEventScraper()
    scraper.run()
