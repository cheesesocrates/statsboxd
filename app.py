from flask import Flask, render_template, jsonify, request
from data_engine import DataEngine
from scraper import Scraper
import logging
import sys
import time

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
app.secret_key = 'super_secret_statsboxd_key'

data_engine = DataEngine()
scraper = Scraper()

# Runtime storage (In-memory)
RUNTIME_DB = {}

@app.route('/')
def home():
    user_data = RUNTIME_DB
    username = user_data.get('username', 'Guest')
    return render_template('index.html', user=username)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    watched_movies = RUNTIME_DB.get('watched', [])
    year = request.args.get('year')
    if year: year = str(year)
    
    include_undated = request.args.get('include_undated', 'false').lower() == 'true'
    
    stats = data_engine.analyze_profile(watched_movies, year=year, include_undated=include_undated)
    return jsonify(stats)

@app.route('/api/evolution', methods=['GET'])
def get_evolution():
    watched = RUNTIME_DB.get('watched', [])
    year = request.args.get('year') # Can be None
    
    evolution = data_engine.get_genre_evolution(watched, year_filter=year)
    return jsonify(evolution)

@app.route('/api/sync/batch', methods=['POST'])
def sync_batch():
    data = request.json
    username = data.get('username')
    page = data.get('page', 1)
    source = data.get('source', 'diary') # 'diary' or 'films'
    
    if not username:
        return jsonify({"status": "error", "message": "Username required"}), 400
    
    # 1. Scrape Page
    t0 = time.time()
    try:
        logging.info(f"--- START BATCH: {username} [{source}] PG {page} ---")
        if source == 'films':
            result = scraper.scrape_films_page(username, page)
        else:
            result = scraper.scrape_page(username, page)
            
        new_entries = result.get('entries', [])
        has_next = result.get('has_next', False)
        t_scrape = time.time() - t0
        logging.info(f"Scrape Page Took: {t_scrape:.2f}s. Entries: {len(new_entries)}")
    except Exception as e:
        logging.error(f"Scrape failed: {e}")
        return jsonify({"status": "error", "message": f"Scraper Error: {str(e)}"}), 500

    # 2. Update Runtime DB
    # Only clear on Diary Page 1 (Start of full sync)
    if source == 'diary' and page == 1:
        RUNTIME_DB.clear()
        RUNTIME_DB['username'] = username
        RUNTIME_DB['watched'] = []
    
    # Safety Check
    if RUNTIME_DB.get('username') != username:
         RUNTIME_DB.clear()
         RUNTIME_DB['username'] = username
         RUNTIME_DB['watched'] = []
    
    current_watched = RUNTIME_DB.get('watched', [])
    
    # Deduplication Logic
    # If source is 'films', we only add if NOT in 'diary' (current_watched)
    # We prioritize Diary entries because they have dates.
    seen_titles = set(m['title'].lower() for m in current_watched)
    
    unique_entries = []
    for entry in new_entries:
        if entry['title'].lower() not in seen_titles:
            unique_entries.append(entry)
            seen_titles.add(entry['title'].lower()) # Mark as seen
    
    current_watched.extend(unique_entries)
    RUNTIME_DB['watched'] = current_watched
    
    # 3. Analyze / Hydrate
    # Hydrate unique_entries only
    t1 = time.time()
    try:
        data_engine._hydrate_with_tmdb(unique_entries)
        t_hydrate = time.time() - t1
        logging.info(f"Hydration Took: {t_hydrate:.2f}s")
    except Exception as e:
        logging.error(f"Hydration failed: {e}")
        # Don't fail the request, just log
    
    # Extract years (excluding None/Undated for the list)
    years = sorted(list(set(m['date'][:4] for m in current_watched if m['date'])), reverse=True)
    latest_year = years[0] if years else None
    
    RUNTIME_DB['available_years'] = years
    RUNTIME_DB['last_updated'] = "Just now"
    
    logging.info(f"--- END BATCH: Total {time.time()-t0:.2f}s ---")
    
    return jsonify({
        "status": "success",
        "entries": unique_entries,
        "has_next": has_next,
        "years": years,
        "latest_year": latest_year
    })

@app.route('/api/quiz')
def get_quiz():
    watched_movies = RUNTIME_DB.get('watched', [])
    quiz = data_engine.get_quiz_question(watched_movies)
    return jsonify(quiz)

@app.route('/api/recommendations')
def recommendations():
    watched = RUNTIME_DB.get('watched', [])
    recs = data_engine.get_recommendations(watched)
    return jsonify(recs)

@app.route('/api/debug/connection')
def debug_connection():
    # Diagnostic endpoint to check if Vercel IP is blocked
    try:
        url = "https://letterboxd.com/"
        resp = scraper.scraper.get(url)
        return jsonify({
            "status": "success" if resp.status_code == 200 else "error",
            "http_code": resp.status_code,
            "url": url,
            "headers": dict(resp.headers)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
