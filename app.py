"""
Review Monitor - Flask Backend
Serves dashboard and manages review scraping
"""

import asyncio
import json
import os
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from scraper import GoogleReviewsScraper

app = Flask(__name__)

# Data storage (in production, use a database)
DATA_FILE = "reviews_data.json"
BUSINESSES_FILE = "businesses.json"
SCRAPE_STATUS_FILE = "scrape_status.json"

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

def get_scrape_status():
    """Get current scrape status"""
    if os.path.exists(SCRAPE_STATUS_FILE):
        with open(SCRAPE_STATUS_FILE, 'r') as f:
            return json.load(f)
    return {"status": "idle", "progress": 0, "total": 0, "current": None, "started_at": None}

def set_scrape_status(status, progress=0, total=0, current=None):
    """Set scrape status"""
    data = {
        "status": status,
        "progress": progress,
        "total": total,
        "current": current,
        "updated_at": datetime.now().isoformat()
    }
    if status == "running" and progress == 0:
        data["started_at"] = datetime.now().isoformat()
    with open(SCRAPE_STATUS_FILE, 'w') as f:
        json.dump(data, f)

def run_scrape_background():
    """Run the scraper in background"""
    print(f"[{datetime.now()}] Starting background scrape...")
    businesses_config = load_businesses()
    businesses = businesses_config.get("businesses", [])
    total = len(businesses)

    set_scrape_status("running", 0, total, None)

    async def do_scrape():
        scraper = GoogleReviewsScraper()
        results = {
            "scraped_at": datetime.now().isoformat(),
            "businesses": []
        }

        for i, biz in enumerate(businesses):
            url = biz.get("google_maps_url")
            if url:
                set_scrape_status("running", i + 1, total, biz.get("name"))
                print(f"[{datetime.now()}] Scraping {i+1}/{total}: {biz['name']}")
                try:
                    data = await scraper.scrape_google_reviews(biz["name"], url)
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

                # Save progress after each business
                save_reviews_data(results)
                await asyncio.sleep(2)

        set_scrape_status("completed", total, total, None)
        print(f"[{datetime.now()}] Scrape complete. {len(results['businesses'])} businesses processed.")

    try:
        asyncio.run(do_scrape())
    except Exception as e:
        print(f"Scrape error: {e}")
        set_scrape_status("error", 0, 0, str(e))

# Initialize scheduler
scheduler = BackgroundScheduler()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/gs-thompson')
def gs_thompson_page():
    """GS Thompson dedicated page"""
    return render_template('gs_thompson.html')

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
    """Manually trigger a scrape (runs in background)"""
    status = get_scrape_status()
    if status.get("status") == "running":
        return jsonify({
            "status": "already_running",
            "message": f"Scrape already in progress: {status.get('progress')}/{status.get('total')}"
        })

    # Start scrape in background thread
    thread = threading.Thread(target=run_scrape_background)
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started", "message": "Scrape started in background"})

@app.route('/api/scrape/status')
def scrape_status():
    """Get current scrape status"""
    return jsonify(get_scrape_status())

@app.route('/api/stats')
def get_stats():
    """Get aggregated statistics"""
    reviews_data = load_reviews_data()
    businesses_config = load_businesses()

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

    # Filter out GS Thompson (they have dedicated page)
    non_gs_businesses = [b for b in config_businesses if "GS Thompson" not in b.get("name", "")]
    stats["total_businesses"] = len(non_gs_businesses)
    
    for config_biz in non_gs_businesses:
        biz_id = config_biz.get("id")
        scraped_biz = scraped_businesses.get(biz_id, {})

        biz_reviews = scraped_biz.get("reviews", [])
        biz_rating = scraped_biz.get("overall_rating")

        stats["total_reviews"] += len(biz_reviews)

        if biz_rating:
            all_ratings.append(biz_rating)

        # Per-business rating distribution
        biz_rating_dist = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for review in biz_reviews:
            rating = review.get("rating")
            if rating and 1 <= rating <= 5:
                stats["rating_distribution"][str(rating)] += 1
                biz_rating_dist[str(rating)] += 1

        # Business summary with rating distribution
        stats["businesses_summary"].append({
            "id": biz_id,
            "name": config_biz.get("name"),
            "address": config_biz.get("address"),
            "rating": biz_rating,
            "review_count": len(biz_reviews),
            "url": config_biz.get("google_maps_url"),
            "rating_distribution": biz_rating_dist
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

        # Recent reviews
        for review in biz_reviews[:5]:
            stats["recent_reviews"].append({
                "business_name": config_biz.get("name"),
                **review
            })

    if all_ratings:
        stats["average_rating"] = round(sum(all_ratings) / len(all_ratings), 2)

    stats["recent_reviews"] = stats["recent_reviews"][:20]
    stats["needs_response"] = stats["needs_response"][:20]

    return jsonify(stats)

@app.route('/api/gs-thompson')
def get_gs_thompson_stats():
    """Get GS Thompson specific stats"""
    reviews_data = load_reviews_data()
    businesses_config = load_businesses()

    scraped_businesses = {b.get("id"): b for b in reviews_data.get("businesses", [])}
    config_businesses = businesses_config.get("businesses", [])

    # Filter for GS Thompson businesses
    gs_businesses = [b for b in config_businesses if "GS Thompson" in b.get("name", "")]

    stats = {
        "total_locations": len(gs_businesses),
        "total_reviews": 0,
        "average_rating": 0,
        "rating_distribution": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        "locations": [],
        "all_reviews": [],
        "needs_response": [],
        "scraped_at": reviews_data.get("scraped_at")
    }

    all_ratings = []

    for config_biz in gs_businesses:
        biz_id = config_biz.get("id")
        scraped_biz = scraped_businesses.get(biz_id, {})

        biz_reviews = scraped_biz.get("reviews", [])
        biz_rating = scraped_biz.get("overall_rating")

        stats["total_reviews"] += len(biz_reviews)

        if biz_rating:
            all_ratings.append(biz_rating)

        biz_rating_dist = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for review in biz_reviews:
            rating = review.get("rating")
            if rating and 1 <= rating <= 5:
                stats["rating_distribution"][str(rating)] += 1
                biz_rating_dist[str(rating)] += 1

        # Location name (remove "GS Thompson - " prefix)
        location_name = config_biz.get("name", "").replace("GS Thompson - ", "")

        stats["locations"].append({
            "id": biz_id,
            "name": config_biz.get("name"),
            "location": location_name,
            "address": config_biz.get("address"),
            "rating": biz_rating,
            "review_count": len(biz_reviews),
            "url": config_biz.get("google_maps_url"),
            "rating_distribution": biz_rating_dist,
            "reviews": biz_reviews[:10]  # Last 10 reviews per location
        })

        # Collect reviews needing response
        for review in biz_reviews:
            if not review.get("owner_response") and review.get("rating", 5) <= 3:
                stats["needs_response"].append({
                    "location": location_name,
                    "reviewer": review.get("reviewer_name"),
                    "rating": review.get("rating"),
                    "text": review.get("text", "")[:200],
                    "date": review.get("date")
                })

            # All reviews for table view
            stats["all_reviews"].append({
                "location": location_name,
                "reviewer": review.get("reviewer_name"),
                "rating": review.get("rating"),
                "text": review.get("text", ""),
                "date": review.get("date"),
                "owner_response": review.get("owner_response")
            })

    if all_ratings:
        stats["average_rating"] = round(sum(all_ratings) / len(all_ratings), 2)

    return jsonify(stats)

def start_scheduler():
    """Start the background scheduler"""
    config = load_businesses()
    interval = config.get("settings", {}).get("check_interval_hours", 2)
    scheduler.add_job(run_scrape_background, 'interval', hours=interval, id='scrape_job', replace_existing=True)
    scheduler.start()
    print(f"Scheduler started - scraping every {interval} hours")

if __name__ == '__main__':
    start_scheduler()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
