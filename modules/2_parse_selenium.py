"""
Module 2: Automation and web scraping using Undetected Selenium WebDriver.
Navigates to brain.com.ua, performs search for iPhone 15, clicks the 1st search result,
extracts specifications, media, pricing, and saves data to PostgreSQL via Django ORM.
"""

from pprint import pprint
import re
import subprocess
import time

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

import load_django
from parser_app.models import Product

SEARCH_QUERY = "Apple iPhone 15 128GB Black"
BASE_URL = "https://brain.com.ua/"


def get_installed_chrome_version() -> int:
    """Detects installed Chrome major version on Windows to avoid driver mismatch."""
    for hive in ["HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE"]:
        try:
            cmd = f'reg query "{hive}\\Software\\Google\\Chrome\\BLBeacon" /v version'
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode()
            match = re.search(r"version\s+REG_SZ\s+(\d+)", output)
            if match:
                return int(match.group(1))
        except Exception:
            continue
    return 154  # Fallback to local Chrome 154


def get_specification_value(specs_dict: dict, search_terms: list):
    """Safely extracts a characteristic from specifications dictionary."""
    for key, value in specs_dict.items():
        for term in search_terms:
            if term.lower() in key.lower():
                return value
    return None


def extract_digits(raw_value: str):
    """Extracts purely numerical digits from text or returns None."""
    if not raw_value:
        return None
    digits = "".join(filter(str.isdigit, raw_value))
    return digits if digits else None


def init_stealth_driver():
    """Initializes Undetected Chrome Driver locked to matching Chrome browser version."""
    chrome_version = get_installed_chrome_version()
    print(f"Detected Chrome major version: {chrome_version}")

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")

    driver = uc.Chrome(options=options, version_main=chrome_version)
    return driver


def main():
    driver = init_stealth_driver()
    wait = WebDriverWait(driver, 45)
    product_data = {}

    try:
        # Step 1: Navigate to homepage
        print(f"Opening main page: {BASE_URL}")
        driver.get(BASE_URL)
        time.sleep(2)

        # Step 2: Locate search input and type query
        print(f"Typing search query: '{SEARCH_QUERY}'")
        search_input_xpath = "//input[contains(@class, 'quick-search-input') and following-sibling::input[contains(@class, 'search-button-first-form')]]"
        search_input = wait.until(EC.element_to_be_clickable((By.XPATH, search_input_xpath)))
        search_input.clear()

        for char in SEARCH_QUERY:
            search_input.send_keys(char)
            time.sleep(0.03)
        time.sleep(1)

        # Step 3: Click search button explicitly per specification via JS
        print("Clicking search button...")
        search_button_xpath = "//input[contains(@class, 'search-button-first-form')]"
        search_button = wait.until(EC.presence_of_element_located((By.XPATH, search_button_xpath)))
        driver.execute_script("arguments[0].click();", search_button)

        # Step 4: Click the 1st search result item
        print("Waiting for search results...")
        first_product_xpath = "//a[contains(@href, '.html') and contains(@href, '-p') and not(contains(@class, 'reviews')) and not(contains(@class, 'compare'))]"
        first_product_link = wait.until(EC.element_to_be_clickable((By.XPATH, first_product_xpath)))

        target_url = first_product_link.get_attribute("href")
        print(f"Opening 1st product card: {target_url}")
        driver.execute_script("arguments[0].click();", first_product_link)

        # Ensure product page is fully loaded
        wait.until(EC.presence_of_element_located((By.XPATH, "//h1")))
        time.sleep(2)

        # Step 5: Data extraction
        # 1. Product Title
        product_data["title"] = None
        for h1 in driver.find_elements(By.TAG_NAME, "h1"):
            txt = h1.get_attribute("textContent").strip()
            if txt:
                product_data["title"] = txt
                break

        # 2. Product Code (SKU)
        product_data["product_code"] = None
        for code_elem in driver.find_elements(By.XPATH, "//span[contains(@class, 'br-pr-code-val')]"):
            txt = code_elem.get_attribute("textContent").strip()
            if txt:
                product_data["product_code"] = txt
                break

        # 3. Complete Specifications Dictionary
        specs_dict = {}
        try:
            spec_rows = driver.find_elements(By.XPATH, "//*[@id='br-characteristics']//div")
            for row in spec_rows:
                spans = row.find_elements(By.TAG_NAME, "span")
                if len(spans) >= 2:
                    key_title = spans[0].get_attribute("textContent").strip()
                    val_title = spans[1].get_attribute("textContent").strip()
                    if key_title and val_title and key_title not in specs_dict:
                        specs_dict[key_title] = val_title
            product_data["specifications"] = specs_dict
        except NoSuchElementException:
            product_data["specifications"] = {}

        # 4. Vendor (Dynamic extraction without hardcoded defaults)
        try:
            vendor_meta = driver.find_elements(By.XPATH, "//meta[@itemprop='brand']")
            if vendor_meta and vendor_meta[0].get_attribute("content"):
                product_data["vendor"] = vendor_meta[0].get_attribute("content").strip()
            else:
                spec_vendor = get_specification_value(specs_dict, ["Виробник", "Бренд", "Производитель"])
                if spec_vendor:
                    product_data["vendor"] = spec_vendor
                elif product_data.get("title"):
                    product_data["vendor"] = product_data["title"].split()[0]
                else:
                    product_data["vendor"] = None
        except (NoSuchElementException, IndexError):
            product_data["vendor"] = None

        # 5. Pricing (Regular and Promo)
        try:
            old_price_blocks = driver.find_elements(By.XPATH, "//*[contains(@class, 'br-pp-op') or contains(@class, 'br-pr-old')]")
            price_blocks = driver.find_elements(By.XPATH, "//*[contains(@class, 'br-pp-price') or contains(@class, 'br-pr-price')]")

            if old_price_blocks and price_blocks:
                old_val = old_price_blocks[0].get_attribute("textContent")
                promo_spans = price_blocks[0].find_elements(By.XPATH, ".//span[not(contains(@class, 'hidden'))]")
                promo_val = promo_spans[0].get_attribute("textContent") if promo_spans else price_blocks[0].get_attribute("textContent")

                product_data["regular_price"] = extract_digits(old_val)
                product_data["promo_price"] = extract_digits(promo_val)
            elif price_blocks:
                spans = price_blocks[0].find_elements(By.XPATH, ".//span[not(contains(@class, 'hidden'))]")
                raw_price = spans[0].get_attribute("textContent") if spans else price_blocks[0].get_attribute("textContent")
                product_data["regular_price"] = extract_digits(raw_price)
                product_data["promo_price"] = None
            else:
                product_data["regular_price"] = None
                product_data["promo_price"] = None
        except (NoSuchElementException, IndexError):
            product_data["regular_price"] = None
            product_data["promo_price"] = None

        # 6. Reviews Count
        try:
            reviews_links = driver.find_elements(By.XPATH, "//a[contains(@href, '#reviews')]")
            if reviews_links:
                digits = extract_digits(reviews_links[0].get_attribute("textContent"))
                product_data["reviews_count"] = digits if digits is not None else "0"
            else:
                product_data["reviews_count"] = "0"
        except (NoSuchElementException, IndexError):
            product_data["reviews_count"] = "0"

        # 7. Photos List (extracted via slider container)
        try:
            photo_urls = []
            slider_containers = driver.find_elements(By.XPATH, "//div[contains(@class, 'br-pr-slider')]")
            if slider_containers:
                for img in slider_containers[0].find_elements(By.TAG_NAME, "img"):
                    src = img.get_attribute("src") or img.get_attribute("data-src")
                    if src and "prod_img" in src and src not in photo_urls:
                        photo_urls.append(src)
            product_data["photos"] = photo_urls
        except (NoSuchElementException, IndexError):
            product_data["photos"] = []

        # 8. Specific Characteristics Extracted from Specs Dictionary
        product_data["color"] = get_specification_value(specs_dict, ["Колір", "Цвет"])
        product_data["memory_capacity"] = get_specification_value(specs_dict, ["Вбудована пам'ять", "Об'єм пам'яті"])
        product_data["screen_diagonal"] = get_specification_value(specs_dict, ["Діагональ екрану", "Діагональ"])
        product_data["display_resolution"] = get_specification_value(specs_dict, ["Роздільна здатність"])

        # 9. Meta & Diagnostic Attributes
        product_data["link"] = driver.current_url
        product_data["parser_type"] = "selenium"
        product_data["status"] = "Done"

        # Terminal output formatted with pprint
        print("\n" + "=" * 50)
        print("PARSED DATA SUMMARY (SELENIUM):")
        print("=" * 50)
        pprint(product_data)

        # 10. Database Persistence via get_or_create Directly
        item, created = Product.objects.get_or_create(**product_data)

        print("\n" + "=" * 50)
        print(f"Database sync: {'Created new record' if created else 'Already exists in DB'} (ID: {item.id})")
        print("=" * 50)

    finally:
        try:
            # Silence Windows destructor bug on exit
            driver.__del__ = lambda: None
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()