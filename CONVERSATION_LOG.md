# Review Monitor - Development Log

## Session: December 19, 2025

### Project Overview
Multi-business Google Reviews monitoring dashboard with scraping capabilities.

### Businesses Monitored (19 total)
- **Expert Home Builders** (1 location)
- **Joey Builders** (1 location)
- **Regency Construction** (1 location)
- **JBC Building Contractors** (1 location)
- **MG Construction** (1 location)
- **GS Thompson Restoration** (14 locations across California)

### Features Implemented

#### 1. Dashboard (`/`)
- Blue gradient color scheme
- Stats overview (total businesses, average rating, total reviews, needs response)
- Business cards with star distribution breakdown
- Rating distribution chart
- Reviews needing response section
- Recent reviews list
- GS Thompson businesses filtered out (they have dedicated page)

#### 2. GS Thompson Page (`/gs-thompson`)
- Dedicated dashboard for 14 GS Thompson locations
- Location comparison table
- Per-location rating distribution
- All reviews table
- Reviews needing response

#### 3. Backend Features
- Background scraping (avoids HTTP timeout)
- Scrape status endpoint (`/api/scrape/status`)
- Progress tracking during scrape
- Auto-refresh every 2 hours via scheduler

### Technical Stack
- **Backend**: Flask + APScheduler
- **Scraping**: Playwright (headless Chromium)
- **Deployment**: Render (Docker-based)
- **Repository**: GitHub (Patagonusa/review-monitor)

### Key Files
- `app.py` - Flask backend with all API endpoints
- `scraper.py` - Google Maps review scraper using Playwright
- `templates/dashboard.html` - Main dashboard UI
- `templates/gs_thompson.html` - GS Thompson dedicated page
- `businesses.json` - Business configuration
- `Dockerfile` - Docker config using Playwright image

### Issues Resolved
1. **502 timeout on scrape** - Implemented background threading
2. **Empty dashboard** - Fixed API to merge config with scraped data
3. **GS Thompson duplication** - Filtered from main page, separate dashboard
4. **Scraper not capturing reviews** - Updated CSS selectors for Google Maps
5. **Python syntax errors** - Fixed f-string issues for Python 3.10 compatibility

### URLs
- Main Dashboard: https://review-monitor.onrender.com/
- GS Thompson: https://review-monitor.onrender.com/gs-thompson
- GitHub: https://github.com/Patagonusa/review-monitor

### Pending/Future Work
- Add Yelp scraper
- Add BBB scraper
- Add Thumbtack scraper
- Add Angie's List scraper
- Improve review extraction reliability
