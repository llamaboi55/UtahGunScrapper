#!/usr/bin/env python3
"""
Utah Gun Exchange Category Scraper

This script will:
1. Fetch every category and sub-category from https://utahgunexchange.com/categories/
2. For each category, paginate up to MAX_PAGES_PER_CATEGORY and scrape every listing:
   - Title
   - URL
   - Price
   - Total views
3. Compile all listings into a single Excel workbook, sorted by Category (A→Z) and within each Category by Views (high→low).

Dependencies:
    pip install cloudscraper beautifulsoup4 pandas openpyxl
"""

import re
from urllib.parse import urljoin

import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup

BASE_URL = "https://utahgunexchange.com"
CATEGORIES_URL = f"{BASE_URL}/categories/"
MAX_PAGES_PER_CATEGORY = 50

scraper = cloudscraper.create_scraper()

def get_category_links():
    """Fetch the /categories/ page and return a dict[name→url] of every category."""
    resp = scraper.get(CATEGORIES_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    adv = soup.find("div", id="adv_categories")
    if not adv:
        raise RuntimeError("Could not find the category listing on /categories/")
    cats = {}
    for a in adv.find_all("a", href=True):
        href = a["href"]
        # only ad-category links
        if "/ad-category/" not in href:
            continue
        name = a.get_text(strip=True)
        full_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        cats[name] = full_url
    return cats

def fetch_listings_from_page(cat_name, page_url):
    """Scrape one page of listings for a given category name."""
    resp = scraper.get(page_url)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    blocks = soup.select("div.post-block")
    listings = []
    for blk in blocks:
        # URL & Title
        left = blk.select_one("div.post-left a.preview")
        if not left:
            continue
        link = left["href"]
        title = left.get("title") or left.get_text(strip=True)

        # Price
        price_el = blk.select_one("p.post-price")
        price = None
        if price_el:
            txt = price_el.get_text(strip=True)
            m = re.search(r"[\d,\.]+", txt)
            if m:
                try:
                    price = float(m.group(0).replace(",", ""))
                except ValueError:
                    pass

        # Views
        stats_el = blk.select_one("p.stats")
        views = None
        if stats_el:
            txt = stats_el.get_text(strip=True)
            m = re.match(r"([\d,]+)\s+total views", txt)
            if m:
                try:
                    views = int(m.group(1).replace(",", ""))
                except ValueError:
                    pass

        listings.append({
            "Category": cat_name,
            "Title": title,
            "URL": link,
            "Price": price,
            "Views": views,
        })
    return listings

def fetch_category_listings(cat_name, cat_url):
    """Paginate through a category (up to MAX_PAGES_PER_CATEGORY) and scrape all its listings."""
    all_recs = []
    for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
        if page == 1:
            page_url = cat_url
        else:
            page_url = cat_url.rstrip("/") + f"/page/{page}/"
        recs = fetch_listings_from_page(cat_name, page_url)
        if not recs:
            break
        all_recs.extend(recs)
    return all_recs

def main():
    print("Fetching category list…")
    cats = get_category_links()
    print(f"Found {len(cats)} categories.")

    all_data = []
    for name, url in cats.items():
        print(f"  → Scraping category: {name}")
        recs = fetch_category_listings(name, url)
        print(f"     • {len(recs)} listings")
        all_data.extend(recs)

    df = pd.DataFrame(all_data)
    if df.empty:
        print("No data scraped. Exiting.")
        return

    # Sort by Category A→Z, then within each by Views high→low
    df_sorted = df.sort_values(
        ["Category", "Views"],
        ascending=[True, False]
    )

    # Output to Excel
    out_file = "all_categories_listings.xlsx"
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        df_sorted.to_excel(writer, sheet_name="Listings", index=False)

    print(f"\nDone! Scraped {len(df_sorted)} listings across {len(cats)} categories.")
    print(f"Output → {out_file}")

if __name__ == "__main__":
    main()
