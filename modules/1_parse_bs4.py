"""
Module 1: Parsing product details from brain.com.ua using Requests and BeautifulSoup.
Collects iPhone 16 Pro Max data, specifications, media, and saves it into PostgreSQL via Django ORM.
"""

from pprint import pprint
import requests
from bs4 import BeautifulSoup

from load_django import *
from parser_app.models import Product

TARGET_URL = "https://brain.com.ua/ukr/Mobilniy_telefon_Apple_iPhone_16_Pro_Max_256GB_Black_Titanium-p1145443.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://brain.com.ua/",
    "Connection": "keep-alive",
}


def get_specification_value(specs_dict: dict, search_terms: list):
    """Safely finds a specific parameter in specifications dictionary by keywords."""
    for key, value in specs_dict.items():
        for term in search_terms:
            if term.lower() in key.lower():
                return value
    return None


def main():
    print(f"Fetching product URL: {TARGET_URL}")
    response = requests.get(TARGET_URL, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    product_data = {}

    # 1. Title
    try:
        title_tag = soup.find("h1")
        product_data["title"] = title_tag.text.strip() if title_tag else None
    except AttributeError:
        product_data["title"] = None

    # 2. Product Code (SKU)
    try:
        code_tag = soup.find("span", class_="br-pr-code-val")
        product_data["product_code"] = code_tag.text.strip() if code_tag else None
    except AttributeError:
        product_data["product_code"] = None

    # 3. Vendor
    try:
        vendor_tag = soup.find("meta", attrs={"itemprop": "brand"})
        if vendor_tag and vendor_tag.get("content"):
            product_data["vendor"] = vendor_tag["content"].strip()
        else:
            product_data["vendor"] = "Apple" if product_data["title"] and "Apple" in product_data["title"] else None
    except AttributeError:
        product_data["vendor"] = None

    # 4. Pricing (Regular and Promo)
    try:
        old_price_tag = soup.find("span", class_="br-pr-old")
        current_price_tag = soup.find("span", attrs={"itemprop": "price"}) or soup.find("div", class_="br-pr-price")

        if old_price_tag and current_price_tag:
            product_data["regular_price"] = "".join(filter(str.isdigit, old_price_tag.text))
            product_data["promo_price"] = "".join(filter(str.isdigit, current_price_tag.text))
        elif current_price_tag:
            product_data["regular_price"] = "".join(filter(str.isdigit, current_price_tag.text))
            product_data["promo_price"] = None
        else:
            product_data["regular_price"] = None
            product_data["promo_price"] = None
    except AttributeError:
        product_data["regular_price"] = None
        product_data["promo_price"] = None

    # 5. Reviews Count
    try:
        reviews_link = soup.find("a", href=lambda h: h and "#reviews" in h)
        if reviews_link:
            digits = "".join(filter(str.isdigit, reviews_link.text))
            product_data["reviews_count"] = digits if digits else "0"
        else:
            product_data["reviews_count"] = "0"
    except AttributeError:
        product_data["reviews_count"] = None

    # 6. Photos (Extract all high-resolution images from product slider)
    try:
        photo_urls = []
        slider_container = soup.find("div", class_="br-pr-slider")
        if slider_container:
            for img in slider_container.find_all("img"):
                src = img.get("src") or img.get("data-src")
                if src and "prod_img" in src:
                    full_url = f"https://brain.com.ua{src}" if src.startswith("/") else src
                    if full_url not in photo_urls:
                        photo_urls.append(full_url)
        product_data["photos"] = photo_urls
    except (AttributeError, TypeError):
        product_data["photos"] = []

    # 7. Complete Specifications Dictionary
    specs_dict = {}
    try:
        specs_container = soup.find(id="br-characteristics")
        if specs_container:
            for row in specs_container.find_all("div"):
                spans = row.find_all("span")
                if len(spans) >= 2:
                    key_title = spans[0].text.strip()
                    value_title = spans[1].text.strip()
                    if key_title and value_title and key_title not in specs_dict:
                        specs_dict[key_title] = value_title

        product_data["specifications"] = specs_dict
    except (AttributeError, TypeError):
        product_data["specifications"] = {}

    # 8. Specific attributes extracted from specifications dictionary
    product_data["color"] = get_specification_value(specs_dict, ["Колір", "Цвет"])
    product_data["memory_capacity"] = get_specification_value(specs_dict, ["Вбудована пам'ять", "Об'єм пам'яті"])
    product_data["screen_diagonal"] = get_specification_value(specs_dict, ["Діагональ екрану", "Діагональ"])
    product_data["display_resolution"] = get_specification_value(specs_dict, ["Роздільна здатність"])

    # 9. Technical & Service Fields
    product_data["link"] = TARGET_URL
    product_data["parser_type"] = "bs4"
    product_data["status"] = "Done"

    # Terminal output formatted with pprint
    print("\n" + "=" * 50)
    print("PARSED DATA SUMMARY:")
    print("=" * 50)
    pprint(product_data)

    # 10. Database persistence via get_or_create directly
    item, created = Product.objects.get_or_create(**product_data)

    print("\n" + "=" * 50)
    print(f"Database sync: {'Created new record' if created else 'Already exists in DB'} (ID: {item.id})")
    print("=" * 50)


if __name__ == "__main__":
    main()