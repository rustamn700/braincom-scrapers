"""
Module 2: Automation and web scraping using Selenium WebDriver.
Navigates to brain.com.ua with stealth flags, executes search query for iPhone 15,
clicks the 1st search result, extracts specifications, and saves data to PostgreSQL.
"""

from pprint import pprint
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

from load_django import *
from parser_app.models import Product

SEARCH_QUERY = "Apple iPhone 15 128GB Black"
BASE_URL = "https://brain.com.ua/"


def get_specification_value(specs_dict: dict, search_terms: list):
    """Safely extracts a characteristic from specifications dictionary."""
    for key, value in specs_dict.items():
        for term in search_terms:
            if term.lower() in key.lower():
                return value
    return None


def init_stealth_driver():
    """Initializes Chrome WebDriver with stealth options to bypass bot detection."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Patch navigator.webdriver via CDP to remain undetected
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """
        }
    )
    return driver


def main():
    driver = init_stealth_driver()
    wait = WebDriverWait(driver, 15)
    product_data = {}

    try:
        # Step 1: Navigate to homepage
        print(f"Opening main page: {BASE_URL}")
        driver.get(BASE_URL)
        time.sleep(2)

        # Step 2: Locate desktop search input and type query
        print(f"Typing search query: '{SEARCH_QUERY}'")
        search_input_xpath = "//input[contains(@class, 'quick-search-input') and following-sibling::input[contains(@class, 'search-button-first-form')]]"
        search_input = wait.until(EC.element_to_be_clickable((By.XPATH, search_input_xpath)))
        search_input.clear()
        search_input.send_keys(SEARCH_QUERY)
        time.sleep(1)

        # Step 3: Submit search query
        print("Submitting search via ENTER...")
        search_input.send_keys(Keys.ENTER)

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
        # 1. Product Title (scan all H1s to capture populated textContent)
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

        # 3. Vendor
        try:
            vendor_meta = driver.find_element(By.XPATH, "//meta[@itemprop='brand']")
            product_data["vendor"] = vendor_meta.get_attribute("content").strip()
        except NoSuchElementException:
            product_data["vendor"] = "Apple" if product_data["title"] and "Apple" in product_data["title"] else None

        # 4. Pricing (Regular and Promo)
        try:
            old_price_blocks = driver.find_elements(By.XPATH, "//*[contains(@class, 'br-pp-op') or contains(@class, 'br-pr-old')]")
            price_blocks = driver.find_elements(By.XPATH, "//*[contains(@class, 'br-pp-price') or contains(@class, 'br-pr-price')]")

            if old_price_blocks and price_blocks:
                old_digits = "".join(filter(str.isdigit, old_price_blocks[0].get_attribute("textContent")))
                # Take the first non-hidden span with active price
                promo_spans = price_blocks[0].find_elements(By.XPATH, ".//span[not(contains(@class, 'hidden'))]")
                promo_digits = "".join(filter(str.isdigit, promo_spans[0].get_attribute("textContent"))) if promo_spans else ""

                product_data["regular_price"] = old_digits if old_digits else None
                product_data["promo_price"] = promo_digits if promo_digits else None
            elif price_blocks:
                spans = price_blocks[0].find_elements(By.XPATH, ".//span[not(contains(@class, 'hidden'))]")
                digits = "".join(filter(str.isdigit, spans[0].get_attribute("textContent"))) if spans else ""
                product_data["regular_price"] = digits if digits else None
                product_data["promo_price"] = None
            else:
                product_data["regular_price"] = None
                product_data["promo_price"] = None
        except (NoSuchElementException, IndexError):
            product_data["regular_price"] = None
            product_data["promo_price"] = None

        # 5. Reviews Count
        try:
            reviews_links = driver.find_elements(By.XPATH, "//a[contains(@href, '#reviews')]")
            if reviews_links:
                digits = "".join(filter(str.isdigit, reviews_links[0].get_attribute("textContent")))
                product_data["reviews_count"] = digits if digits else "0"
            else:
                product_data["reviews_count"] = "0"
        except (NoSuchElementException, IndexError):
            product_data["reviews_count"] = "0"

        # 6. Photos (Extract unique image URLs from product slider)
        try:
            photo_urls = []
            img_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'br-pr-slider')]//img")
            for img in img_elements:
                src = img.get_attribute("src") or img.get_attribute("data-src")
                if src and "prod_img" in src and src not in photo_urls:
                    photo_urls.append(src)
            product_data["photos"] = photo_urls
        except NoSuchElementException:
            product_data["photos"] = []

        # 7. Complete Specifications Dictionary
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

        # 8. Specific attributes extracted from specifications dictionary
        product_data["color"] = get_specification_value(specs_dict, ["Колір", "Цвет"])
        product_data["memory_capacity"] = get_specification_value(specs_dict, ["Вбудована пам'ять", "Об'єм пам'яті"])
        product_data["screen_diagonal"] = get_specification_value(specs_dict, ["Діагональ екрану", "Діагональ"])
        product_data["display_resolution"] = get_specification_value(specs_dict, ["Роздільна здатність"])

        # 9. Technical & Service Fields
        product_data["link"] = driver.current_url
        product_data["parser_type"] = "selenium"
        product_data["status"] = "Done"

        # Terminal output via pprint
        print("\n" + "=" * 50)
        print("PARSED DATA SUMMARY (SELENIUM):")
        print("=" * 50)
        pprint(product_data)

        # 10. Database persistence via get_or_create directly
        item, created = Product.objects.get_or_create(**product_data)

        print("\n" + "=" * 50)
        print(f"Database sync: {'Created new record' if created else 'Already exists in DB'} (ID: {item.id})")
        print("=" * 50)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()