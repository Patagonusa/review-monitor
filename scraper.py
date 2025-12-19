"""
Google Reviews Scraper using Playwright
Scrapes reviews from Google Maps and Google Search business panels
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

    async def scrape_google_reviews(self, business_name: str, google_url: str) -> dict:
        """
        Scrape all reviews from a Google Maps business page or Google Search result
        """
        reviews = []
        business_info = {
            "name": business_name,
            "url": google_url,
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
                # Determine if it's a Maps URL or Search URL
                is_maps_url = "google.com/maps" in google_url

                await page.goto(google_url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(3)

                if is_maps_url:
                    # Google Maps scraping logic
                    business_info = await self._scrape_maps_page(page, business_info)
                else:
                    # Google Search knowledge panel scraping
                    business_info = await self._scrape_search_page(page, business_info)

            except Exception as e:
                business_info["error"] = str(e)
                print(f"Error scraping {business_name}: {e}")
            finally:
                await browser.close()

        return business_info

    async def _scrape_maps_page(self, page, business_info: dict) -> dict:
        """Scrape from Google Maps place page"""
        reviews = []

        print(f"[SCRAPER] Processing maps page for {business_info['name']}")

        # Try to get overall rating - multiple selectors
        try:
            rating_selectors = ['div.fontDisplayLarge', 'span.fontDisplayLarge', 'div.F7nice span', '[class*="fontDisplayLarge"]']
            for selector in rating_selectors:
                rating_elem = await page.query_selector(selector)
                if rating_elem:
                    rating_text = await rating_elem.inner_text()
                    rating_text = rating_text.strip().replace(",", ".")
                    if re.match(r'^\d\.?\d?$', rating_text):
                        business_info["overall_rating"] = float(rating_text)
                        print(f"[SCRAPER] Found rating: {rating_text}")
                        break
        except Exception as e:
            print(f"[SCRAPER] Rating extraction error: {e}")

        # Try to get total review count from page content
        try:
            content = await page.content()
            matches = re.findall(r'([\d,]+)\s*reviews?', content, re.IGNORECASE)
            for match in matches:
                count = int(match.replace(",", ""))
                if count > 0 and count < 100000:
                    business_info["total_reviews"] = count
                    print(f"[SCRAPER] Found review count: {count}")
                    break
        except Exception as e:
            print(f"[SCRAPER] Review count extraction error: {e}")

        # Click on Reviews tab to load all reviews
        try:
            reviews_tab = await page.query_selector('button[aria-label*="Reviews"]')
            if reviews_tab:
                await reviews_tab.click()
                await asyncio.sleep(2)
        except:
            pass

        # Try clicking "More reviews" or similar
        try:
            more_reviews = await page.query_selector('button:has-text("reviews")')
            if more_reviews:
                await more_reviews.click()
                await asyncio.sleep(2)
        except:
            pass

        # Scroll to load more reviews
        try:
            reviews_container = await page.query_selector('[class*="m6QErb"][class*="DxyBCb"]')
            if reviews_container:
                for _ in range(10):
                    await reviews_container.evaluate('(el) => el.scrollTop = el.scrollHeight')
                    await asyncio.sleep(1)
        except:
            pass

        # Extract individual reviews
        review_selectors = ['[data-review-id]', 'div.jftiEf', 'div.jJc9Ad']
        review_elements = []
        for sel in review_selectors:
            review_elements = await page.query_selector_all(sel)
            if review_elements:
                print(f"[SCRAPER] Found {len(review_elements)} reviews with selector: {sel}")
                break

        for elem in review_elements[:100]:
            try:
                review = await self._extract_review_from_element(elem)
                if review.get("reviewer_name"):
                    reviews.append(review)
            except Exception as e:
                continue

        business_info["reviews"] = reviews
        business_info["reviews_scraped"] = len(reviews)
        return business_info

    async def _scrape_search_page(self, page, business_info: dict) -> dict:
        """Scrape from Google Search knowledge panel"""
        reviews = []

        # Try to get overall rating from knowledge panel
        try:
            # Look for rating in knowledge panel
            rating_selectors = [
                '[data-attrid*="rating"] span',
                '.Aq14fc',
                '[class*="rating"]',
                'span:has-text("stars")',
                '[aria-label*="stars"]',
                '[aria-label*="rating"]'
            ]
            for selector in rating_selectors:
                try:
                    rating_elem = await page.query_selector(selector)
                    if rating_elem:
                        rating_text = await rating_elem.inner_text()
                        match = re.search(r'(\d+\.?\d*)', rating_text)
                        if match:
                            rating = float(match.group(1))
                            if 0 < rating <= 5:
                                business_info["overall_rating"] = rating
                                break
                except:
                    continue
        except Exception as e:
            print(f"Rating extraction error: {e}")

        # Try to get total review count
        try:
            review_count_selectors = [
                '[data-attrid*="review"]',
                'a:has-text("reviews")',
                'span:has-text("reviews")',
                '[href*="reviews"]'
            ]
            for selector in review_count_selectors:
                try:
                    count_elem = await page.query_selector(selector)
                    if count_elem:
                        count_text = await count_elem.inner_text()
                        match = re.search(r'([\d,]+)\s*review', count_text, re.IGNORECASE)
                        if match:
                            business_info["total_reviews"] = int(match.group(1).replace(",", ""))
                            break
                except:
                    continue
        except Exception as e:
            print(f"Review count extraction error: {e}")

        # Try to click on reviews link to get more details
        try:
            reviews_link = await page.query_selector('a:has-text("Google reviews")')
            if reviews_link:
                await reviews_link.click()
                await asyncio.sleep(3)

                # Now try to extract reviews from the reviews popup/page
                review_elements = await page.query_selector_all('[data-review-id], [class*="review"]')
                for elem in review_elements[:50]:
                    try:
                        review = await self._extract_review_from_element(elem)
                        if review.get("reviewer_name"):
                            reviews.append(review)
                    except:
                        continue
        except:
            pass

        # Alternative: Look for reviews in the knowledge panel directly
        if not reviews:
            try:
                review_containers = await page.query_selector_all('[data-attrid*="review"], [class*="review"]')
                for container in review_containers[:20]:
                    try:
                        text = await container.inner_text()
                        if len(text) > 20:  # Likely a review text
                            reviews.append({
                                "reviewer_name": "Google User",
                                "text": text[:500],
                                "rating": None,
                                "date": None
                            })
                    except:
                        continue
            except:
                pass

        business_info["reviews"] = reviews
        business_info["reviews_scraped"] = len(reviews)
        return business_info

    async def _extract_review_from_element(self, elem) -> dict:
        """Extract review data from a review element"""
        review = {}

        # Reviewer name
        name_selectors = ['[class*="d4r55"]', '[class*="reviewer"]', '[class*="author"]', 'a[href*="/contrib"]']
        for selector in name_selectors:
            try:
                name_elem = await elem.query_selector(selector)
                if name_elem:
                    review["reviewer_name"] = await name_elem.inner_text()
                    break
            except:
                continue

        # Star rating
        stars_selectors = ['[class*="kvMYJc"]', '[aria-label*="star"]', '[class*="rating"]']
        for selector in stars_selectors:
            try:
                stars_elem = await elem.query_selector(selector)
                if stars_elem:
                    stars_label = await stars_elem.get_attribute('aria-label')
                    if stars_label:
                        match = re.search(r'(\d)', stars_label)
                        if match:
                            review["rating"] = int(match.group(1))
                            break
            except:
                continue

        # Review text
        text_selectors = ['[class*="wiI7pd"]', '[class*="review-text"]', '[class*="content"]']
        for selector in text_selectors:
            try:
                text_elem = await elem.query_selector(selector)
                if text_elem:
                    review["text"] = await text_elem.inner_text()
                    break
            except:
                continue

        if "text" not in review:
            review["text"] = ""

        # Date
        date_selectors = ['[class*="rsqaWe"]', '[class*="date"]', 'span:has-text("ago")']
        for selector in date_selectors:
            try:
                date_elem = await elem.query_selector(selector)
                if date_elem:
                    review["date"] = await date_elem.inner_text()
                    break
            except:
                continue

        # Owner response
        response_selectors = ['[class*="CDe7pd"]', '[class*="owner-response"]', '[class*="response"]']
        for selector in response_selectors:
            try:
                response_elem = await elem.query_selector(selector)
                if response_elem:
                    review["owner_response"] = await response_elem.inner_text()
                    break
            except:
                continue

        if "owner_response" not in review:
            review["owner_response"] = None

        return review

    async def scrape_all_businesses(self, businesses: list) -> dict:
        """
        Scrape reviews for all businesses in the list
        """
        results = {
            "scraped_at": datetime.now().isoformat(),
            "businesses": []
        }

        for biz in businesses:
            url = biz.get("google_maps_url")
            if url:
                print(f"Scraping: {biz['name']}")
                try:
                    data = await self.scrape_google_reviews(biz["name"], url)
                    data["id"] = biz.get("id")
                    results["businesses"].append(data)
                except Exception as e:
                    print(f"Error scraping {biz['name']}: {e}")
                    results["businesses"].append({
                        "id": biz.get("id"),
                        "name": biz["name"],
                        "error": str(e),
                        "reviews": []
                    })

                # Small delay between requests to avoid rate limiting
                await asyncio.sleep(2)

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
