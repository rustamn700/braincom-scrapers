# Brain.com.ua Scrapers & Django ORM Integration

A web scraping and data persistence suite built with Python, Django ORM, and PostgreSQL. The project implements three independent data extraction modules targeting `brain.com.ua`:
1. **Requests + BeautifulSoup4** — Direct HTML parsing.
2. **Selenium WebDriver** — Browser automation with stealth configuration and automated search flow.
3. **Playwright (Sync API)** — Modern browser automation handling dynamic content and Cloudflare bot detection.

---

## 🛠 Tech Stack

* **Language:** Python 3.12+
* **Framework / ORM:** Django 5.x
* **Database:** PostgreSQL
* **Scraping Engines:** BeautifulSoup4, Requests, Selenium, Playwright

---

## 📌 Features & Compliance

* **Robust Selectors:** All XPath and CSS selectors are crafted manually using stable attributes and classes (no brittle absolute paths like `/html/body/...`).
* **Safe Key-Value Extraction:** Specifications and hardware characteristics are parsed into dictionary pairs by semantic name rather than arbitrary line indices.
* **Resilient Data Normalization:** Missing or non-existent attributes explicitly default to `None` to prevent database clutter.
* **Clean ORM Integration:** Records are inserted via `Product.objects.get_or_create(**product_data)` without using ambiguous defaults.
* **Stealth Automation:** Configured Chrome DevTools Protocol (CDP) scripts and custom user-agents to bypass automated browser detection.

---

## 🚀 Setup & Installation

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone [https://github.com/rustamn700/braincom-scrapers.git](https://github.com/rustamn700/braincom-scrapers.git)
cd braincom-scrapers

python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
