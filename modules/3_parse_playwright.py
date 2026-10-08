"""
Module 3: Web automation and data extraction using Playwright Sync API.
Bypasses anti-bot protection, navigates brain.com.ua, executes search query,
extracts specifications without arbitrary indexes, and persists data to PostgreSQL via Django ORM.
"""

import os
from pprint import pprint
import time

# Allow Django ORM execution in threads with active event loops
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Error as PlaywrightError

from load_django import *
from parser_app.models import Product

SEARCH_QUERY = "Apple iPhone 18 Pro"
BASE_URL = "https://brain.com.ua/"


def get_specification_value(specs_dict: dict, search_terms: list):
    """Safely extracts a characteristic from specifications dictionary."""
    for key, value in specs_dict.items():
        for term in search_terms:
            if term.lower() in key.lower():
                return value
    return None


def main():
    product_data = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        # Stealth script to evade bot detection
        page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """
        )

        try:
            # Step 1: Navigate to homepage
            print(f"Opening main page: {BASE_URL}")
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            # Step 2: Locate desktop search input and type query
            print(f"Typing search query: '{SEARCH_QUERY}'")
            search_input_xpath = "//input[contains(@class, 'quick-search-input') and following-sibling::input[contains(@class, 'search-button-first-form')]]"
            search_input = page.locator(search_input_xpath)
            search_input.wait_for(state="visible", timeout=15000)
            search_input.fill(SEARCH_QUERY)
            time.sleep(1)

            # Step 3: Submit search query
            print("Submitting search via ENTER...")
            page.keyboard.press("Enter")

            # Step 4: Click 1st product card link
            print("Waiting for search results...")
            first_product_xpath = "//a[contains(@href, '.html') and contains(@href, '-p') and not(contains(@class, 'reviews')) and not(contains(@class, 'compare'))]"
            first_card = page.locator(first_product_xpath).first
            first_card.wait_for(state="visible", timeout=15000)

            target_url = first_card.get_attribute("href")
            print(f"Opening 1st product card: {target_url}")
            first_card.click()

            # Ensure product card DOM is attached
            page.locator("//h1").first.wait_for(state="attached", timeout=20000)
            time.sleep(2)

            # Step 5: Data extraction
            # 1. Product Title
            product_data["title"] = None
            try:
                for h1 in page.locator("//h1").all():
                    txt = h1.inner_text().strip()
                    if txt:
                        product_data["title"] = txt
                        break
            except (PlaywrightTimeoutError, PlaywrightError):
                product_data["title"] = None

            # 2. Product Code (SKU)
            product_data["product_code"] = None
            try:
                code_locators = page.locator(
                    "//span[contains(@class, 'br-pr-code-val')]"
                ).all()
                for code in code_locators:
                    txt = code.inner_text().strip()
                    if txt:
                        product_data["product_code"] = txt
                        break
            except (PlaywrightTimeoutError, PlaywrightError):
                product_data["product_code"] = None

            # 3. Vendor
            product_data["vendor"] = None
            try:
                vendor_meta = page.locator("//meta[@itemprop='brand']")
                if vendor_meta.count() > 0:
                    product_data["vendor"] = vendor_meta.first.get_attribute(
                        "content"
                    ).strip()
                elif (
                    product_data.get("title")
                    and "Apple" in product_data["title"]
                ):
                    product_data["vendor"] = "Apple"
            except (PlaywrightTimeoutError, PlaywrightError):
                product_data["vendor"] = None

            # 4. Pricing (Regular and Promo)
            product_data["regular_price"] = None
            product_data["promo_price"] = None
            try:
                old_price_locator = page.locator(
                    "//*[contains(@class, 'br-pp-op') or contains(@class, 'br-pr-old')]"
                )
                price_locator = page.locator(
                    "//*[contains(@class, 'br-pp-price') or contains(@class, 'br-pr-price')]"
                )

                if old_price_locator.count() > 0 and price_locator.count() > 0:
                    old_text = old_price_locator.first.inner_text()
                    promo_spans = price_locator.first.locator(
                        ".//span[not(contains(@class, 'hidden'))]"
                    )
                    promo_text = (
                        promo_spans.first.inner_text()
                        if promo_spans.count() > 0
                        else ""
                    )

                    old_digits = "".join(filter(str.isdigit, old_text))
                    promo_digits = "".join(filter(str.isdigit, promo_text))
                    product_data["regular_price"] = (
                        old_digits if old_digits else None
                    )
                    product_data["promo_price"] = (
                        promo_digits if promo_digits else None
                    )
                elif price_locator.count() > 0:
                    spans = price_locator.first.locator(
                        ".//span[not(contains(@class, 'hidden'))]"
                    )
                    digits = (
                        "".join(
                            filter(str.isdigit, spans.first.inner_text())
                        )
                        if spans.count() > 0
                        else ""
                    )
                    product_data["regular_price"] = digits if digits else None
                    product_data["promo_price"] = None
            except (PlaywrightTimeoutError, PlaywrightError):
                product_data["regular_price"] = None
                product_data["promo_price"] = None

            # 5. Reviews Count
            product_data["reviews_count"] = "0"
            try:
                reviews_locator = page.locator(
                    "//a[contains(@href, '#reviews')]"
                )
                if reviews_locator.count() > 0:
                    digits = "".join(
                        filter(str.isdigit, reviews_locator.first.inner_text())
                    )
                    product_data["reviews_count"] = digits if digits else "0"
            except (PlaywrightTimeoutError, PlaywrightError):
                product_data["reviews_count"] = "0"

            # 6. Photos (Extract gallery URLs)
            product_data["photos"] = []
            try:
                photo_urls = []
                img_elements = page.locator(
                    "//div[contains(@class, 'br-pr-slider')]//img"
                ).all()
                for img in img_elements:
                    src = img.get_attribute("src") or img.get_attribute(
                        "data-src"
                    )
                    if src and "prod_img" in src and src not in photo_urls:
                        photo_urls.append(src)
                product_data["photos"] = photo_urls
            except (PlaywrightTimeoutError, PlaywrightError):
                product_data["photos"] = []

            # 7. Complete Specifications Dictionary
            specs_dict = {}
            try:
                spec_rows = page.locator(
                    "//*[@id='br-characteristics']//div"
                ).all()
                for row in spec_rows:
                    spans = row.locator("span").all()
                    if len(spans) >= 2:
                        key_title = spans[0].inner_text().strip()
                        val_title = spans[1].inner_text().strip()
                        if (
                            key_title
                            and val_title
                            and key_title not in specs_dict
                        ):
                            specs_dict[key_title] = val_title
                product_data["specifications"] = specs_dict
            except (PlaywrightTimeoutError, PlaywrightError):
                product_data["specifications"] = {}

            # 8. Specific attributes extracted from specifications dictionary
            product_data["color"] = get_specification_value(
                specs_dict, ["Колір", "Цвет"]
            )
            product_data["memory_capacity"] = get_specification_value(
                specs_dict, ["Вбудована пам'ять", "Об'єм пам'яті"]
            )
            product_data["screen_diagonal"] = get_specification_value(
                specs_dict, ["Діагональ екрану", "Діагональ"]
            )
            product_data["display_resolution"] = get_specification_value(
                specs_dict, ["Роздільна здатність"]
            )

            # 9. Technical & Service Fields
            product_data["link"] = page.url
            product_data["parser_type"] = "playwright"
            product_data["status"] = "Done"

        finally:
            browser.close()

    # Step 6: Database persistence outside of Playwright event loop
    print("\n" + "=" * 50)
    print("PARSED DATA SUMMARY (PLAYWRIGHT):")
    print("=" * 50)
    pprint(product_data)

    item, created = Product.objects.get_or_create(**product_data)

    print("\n" + "=" * 50)
    print(
        f"Database sync: {'Created new record' if created else 'Already exists in DB'} (ID: {item.id})"
    )
    print("=" * 50)


if __name__ == "__main__":
    main()