"""
Review Monitor - Flask Backend
Serves dashboard and manages review scraping
"""

import asyncio
import json
import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from scraper import GoogleReviewsScraper

app = Flask(__name__)

# Data storage (in production, use a database)
DATA_FILE = "reviews_data.json"
BUSINESSES_FILE = "businesses.json"

def load_businesses():
    """Load business configuration"""
    if os.path.exists(BUSINESSES_FILE):
        with open(BUSINESSES_FILE, 'r') as f:
            return json.load(f)
    return {"businesses": [], "settings": {"check_interval_hours": 2}}

def save_businesses(data):
    """Save business configuration"""
    with open(BUSINESSES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_reviews_data():
    """Load cached reviews data"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {"scraped_at": None, "businesses": []}

def save_reviews_data(data):
    """Save reviews data"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def run_scrape():
    """Run the scraper for all businesses"""
    print(f"[{datetime.now()}] Starting scheduled scrape...")
    businesses = load_businesses()

    async def do_scrape():
        scraper = GoogleReviewsScraper()
        results = await scraper.scrape_all_businesses(businesses.get("businesses", []))
        save_reviews_data(results)
        print(f"[{datetime.now()}] Scrape complete. {len(results['businesses'])} businesses processed.")

    asyncio.run(do_scrape())

# Initialize scheduler
scheduler = BackgroundScheduler()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/reviews')
def get_reviews():
    """Get all cached reviews data"""
    data = load_reviews_data()
    return jsonify(data)

@app.route('/api/businesses', methods=['GET'])
def get_businesses():
    """Get business configuration"""
    data = load_businesses()
    return jsonify(data)

@app.route('/api/businesses', methods=['POST'])
def update_businesses():
    """Update business configuration"""
    data = request.json
    save_businesses(data)
    return jsonify({"status": "success"})

@app.route('/api/business', methods=['POST'])
def add_business():
    """Add a new business"""
    new_business = request.json
    data = load_businesses()

    # Generate new ID
    max_id = max([b.get("id", 0) for b in data["businesses"]], default=0)
    new_business["id"] = max_id + 1

    data["businesses"].append(new_business)
    save_businesses(data)
    return jsonify({"status": "success", "business": new_business})

@app.route('/api/business/<int:business_id>', methods=['DELETE'])
def delete_business(business_id):
    """Delete a business"""
    data = load_businesses()
    data["businesses"] = [b for b in data["businesses"] if b.get("id") != business_id]
    save_businesses(data)
    return jsonify({"status": "success"})

@app.route('/api/scrape', methods=['POST'])
def trigger_scrape():
    """Manually trigger a scrape"""
    try:
        run_scrape()
        return jsonify({"status": "success", "message": "Scrape completed"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get aggregated statistics"""
    reviews_data = load_reviews_data()
    businesses_config = load_businesses()

    # Get scraped data
    scraped_businesses = {b.get("id"): b for b in reviews_data.get("businesses", [])}
    config_businesses = businesses_config.get("businesses", [])

    stats = {
        "total_businesses": len(config_businesses),
        "total_reviews": 0,
        "average_rating": 0,
        "rating_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        "businesses_summary": [],
        "recent_reviews": [],
        "needs_response": [],
        "scraped_at": reviews_data.get("scraped_at")
    }

    all_ratings = []

    # Merge config businesses with scraped data
    for config_biz in config_businesses:
        biz_id = config_biz.get("id")
        scraped_biz = scraped_businesses.get(biz_id, {})

        biz_reviews = scraped_biz.get("reviews", [])
        biz_rating = scraped_biz.get("overall_rating")

        stats["total_reviews"] += len(biz_reviews)

        if biz_rating:
            all_ratings.append(biz_rating)

        # Count rating distribution
        for review in biz_reviews:
            rating = review.get("rating")
            if rating and 1 <= rating <= 5:
                stats["rating_distribution"][str(rating)] += 1

        # Business summary - always include from config
        stats["businesses_summary"].append({
            "id": biz_id,
            "name": config_biz.get("name"),
            "rating": biz_rating,
            "review_count": len(biz_reviews),
            "url": config_biz.get("google_maps_url")
        })

        # Collect reviews needing response
        for review in biz_reviews:
            if not review.get("owner_response") and review.get("rating", 5) <= 3:
                stats["needs_response"].append({
                    "business_name": config_biz.get("name"),
                    "reviewer": review.get("reviewer_name"),
                    "rating": review.get("rating"),
                    "text": review.get("text", "")[:200],
                    "date": review.get("date")
                })

        # Recent reviews (last 5 per business)
        for review in biz_reviews[:5]:
            stats["recent_reviews"].append({
                "business_name": config_biz.get("name"),
                **review
            })

    if all_ratings:
        stats["average_rating"] = round(sum(all_ratings) / len(all_ratings), 2)

    # Sort recent reviews and needs_response
    stats["recent_reviews"] = stats["recent_reviews"][:20]
    stats["needs_response"] = stats["needs_response"][:20]

    return jsonify(stats)

def start_scheduler():
    """Start the background scheduler"""
    config = load_businesses()
    interval = config.get("settings", {}).get("check_interval_hours", 2)

    scheduler.add_job(run_scrape, 'interval', hours=interval, id='scrape_job', replace_existing=True)
    scheduler.start()
    print(f"Scheduler started - scraping every {interval} hours")

if __name__ == '__main__':
    # Start scheduler in background
    start_scheduler()

    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
