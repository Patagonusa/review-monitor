"""
Google Reviews Scraper
"""

import asyncio
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright


class GoogleReviewsScraper:
    async def scrape_google_reviews(self, business_name, google_url):
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
            ctx = await browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122",
                locale="en-US"
            )
            page = await ctx.new_page()
            try:
                print("[SCRAPER] Loading: " + business_name)
                await page.goto(google_url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(5)
                content = await page.content()
                
                # Rating
                m = re.search(r'"(\d\.\d)\s*stars"', content)
                if m:
                    business_info["overall_rating"] = float(m.group(1))
                
                # Review count
                m = re.search(r"(\d[\d,]*)\s*reviews", content, re.I)
                if m:
                    business_info["total_reviews"] = int(m.group(1).replace(",", ""))
                
                rating = business_info["overall_rating"]
                rev_count = business_info["total_reviews"]
                print("[SCRAPER] Rating: " + str(rating) + ", Reviews: " + str(rev_count))
                
                # Click reviews tab
                for sel in ["button[aria-label*=Reviews]", "[role=tab]:has-text(Reviews)"]:
                    try:
                        btn = await page.query_selector(sel)
                        if btn:
                            await btn.click()
                            await asyncio.sleep(2)
                            break
                    except:
                        pass
                
                # Scroll
                for sel in ["div.m6QErb.DxyBCb", "div.m6QErb"]:
                    try:
                        c = await page.query_selector(sel)
                        if c:
                            for _ in range(6):
                                await c.evaluate("e=>e.scrollTop=e.scrollHeight")
                                await asyncio.sleep(1)
                            break
                    except:
                        pass
                
                # Extract reviews
                elems = await page.query_selector_all("div[data-review-id]")
                if not elems:
                    elems = await page.query_selector_all("div.jftiEf")
                print("[SCRAPER] Found " + str(len(elems)) + " review elements")
                
                for el in elems[:50]:
                    try:
                        r = {"reviewer_name": None, "rating": None, "text": "", "date": None, "owner_response": None}
                        n = await el.query_selector("div.d4r55")
                        if n:
                            txt = await n.inner_text()
                            r["reviewer_name"] = txt.split("\n")[0]
                        s = await el.query_selector("span.kvMYJc")
                        if s:
                            a = await s.get_attribute("aria-label")
                            if a:
                                m = re.search(r"(\d)", a)
                                if m:
                                    r["rating"] = int(m.group(1))
                        t = await el.query_selector("span.wiI7pd")
                        if t:
                            r["text"] = await t.inner_text()
                        d = await el.query_selector("span.rsqaWe")
                        if d:
                            r["date"] = await d.inner_text()
                        if r["reviewer_name"] or r["text"]:
                            business_info["reviews"].append(r)
                    except:
                        pass
                num_extracted = len(business_info["reviews"])
                print("[SCRAPER] Extracted " + str(num_extracted) + " reviews")
            except Exception as e:
                business_info["error"] = str(e)
                print("[SCRAPER] Error: " + str(e))
            finally:
                await browser.close()
        return business_info

    async def scrape_all_businesses(self, businesses):
        results = {"scraped_at": datetime.now().isoformat(), "businesses": []}
        for biz in businesses:
            url = biz.get("google_maps_url")
            if url:
                biz_name = biz["name"]
                print("\n[SCRAPER] === " + biz_name + " ===")
                try:
                    data = await self.scrape_google_reviews(biz["name"], url)
                    data["id"] = biz.get("id")
                    results["businesses"].append(data)
                except Exception as e:
                    results["businesses"].append({
                        "id": biz.get("id"),
                        "name": biz["name"],
                        "error": str(e),
                        "reviews": []
                    })
                await asyncio.sleep(3)
        return results


if __name__ == "__main__":
    asyncio.run(GoogleReviewsScraper().scrape_google_reviews("Test", "https://google.com/maps"))
