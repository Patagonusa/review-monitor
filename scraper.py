"""
Google Reviews Scraper using Playwright
Scrapes reviews from Google Maps business pages
"""

import asyncio
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright
import os

class GoogleReviewsScraper:
    def __init__(self):
        self.reviews_data = {}

    async def scrape_google_reviews(self, business_name: str, google_maps_url: str) -> dict:
        """
        Scrape all reviews from a Google Maps business page
        """
        reviews = []
        business_info = {
            "name": business_name,
            "url": google_maps_url,
            "scraped_at": datetime.now().isoformat(),
            "overall_rating": None,
            "total_reviews": 0,
            "reviews": []
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                await page.goto(google_maps_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

                # Try to get overall rating
                try:
                    rating_elem = await page.query_selector('[class*="fontDisplayLarge"]')
                    if rating_elem:
                        rating_text = await rating_elem.inner_text()
                        business_info["overall_rating"] = float(rating_text.replace(",", "."))
                except:
                    pass

                # Try to get total review count
                try:
                    review_count_elem = await page.query_selector('[class*="fontBodyMedium"] >> text=/\\d+\\s*review/')
                    if review_count_elem:
                        count_text = await review_count_elem.inner_text()
                        match = re.search(r'([\d,]+)\s*review', count_text)
                        if match:
                            business_info["total_reviews"] = int(match.group(1).replace(",", ""))
                except:
                    pass

                # Click on Reviews tab to load all reviews
                try:
                    reviews_tab = await page.query_selector('button[aria-label*="Reviews"]')
                    if reviews_tab:
                        await reviews_tab.click()
                        await asyncio.sleep(2)
                except:
                    pass

                # Scroll to load more reviews (up to 50 for performance)
                reviews_container = await page.query_selector('[class*="m6QErb"][class*="DxyBCb"]')
                if reviews_container:
                    for _ in range(10):  # Scroll 10 times
                        await reviews_container.evaluate('(el) => el.scrollTop = el.scrollHeight')
                        await asyncio.sleep(1)

                # Extract individual reviews
                review_elements = await page.query_selector_all('[data-review-id]')

                for elem in review_elements[:100]:  # Limit to 100 reviews
                    try:
                        review = {}

                        # Reviewer name
                        name_elem = await elem.query_selector('[class*="d4r55"]')
                        if name_elem:
                            review["reviewer_name"] = await name_elem.inner_text()

                        # Star rating
                        stars_elem = await elem.query_selector('[class*="kvMYJc"]')
                        if stars_elem:
                            stars_label = await stars_elem.get_attribute('aria-label')
                            if stars_label:
                                match = re.search(r'(\d)', stars_label)
                                if match:
                                    review["rating"] = int(match.group(1))

                        # Review text
                        text_elem = await elem.query_selector('[class*="wiI7pd"]')
                        if text_elem:
                            review["text"] = await text_elem.inner_text()
                        else:
                            review["text"] = ""

                        # Date
                        date_elem = await elem.query_selector('[class*="rsqaWe"]')
                        if date_elem:
                            review["date"] = await date_elem.inner_text()

                        # Owner response
                        response_elem = await elem.query_selector('[class*="CDe7pd"]')
                        if response_elem:
                            review["owner_response"] = await response_elem.inner_text()
                        else:
                            review["owner_response"] = None

                        if review.get("reviewer_name"):
                            reviews.append(review)
                    except Exception as e:
                        continue

                business_info["reviews"] = reviews
                business_info["reviews_scraped"] = len(reviews)

            except Exception as e:
                business_info["error"] = str(e)
            finally:
                await browser.close()

        return business_info

    async def scrape_all_businesses(self, businesses: list) -> dict:
        """
        Scrape reviews for all businesses in the list
        """
        results = {
            "scraped_at": datetime.now().isoformat(),
            "businesses": []
        }

        for biz in businesses:
            if biz.get("google_maps_url"):
                print(f"Scraping: {biz['name']}")
                data = await self.scrape_google_reviews(biz["name"], biz["google_maps_url"])
                data["id"] = biz.get("id")
                results["businesses"].append(data)

        return results


async def main():
    """Test the scraper"""
    scraper = GoogleReviewsScraper()

    # Example test
    test_url = "https://www.google.com/maps/place/Example+Business"
    result = await scraper.scrape_google_reviews("Test Business", test_url)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
