from flask import Flask, render_template, jsonify, request, session
from data_engine import DataEngine
from scraper import Scraper
import os
import json
import logging
import sys

# Configure logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = Flask(__name__) 
app.secret_key = 'super_secret_statsboxd_key'  # Needed for session

data_engine = DataEngine()
scraper = Scraper()

# Runtime storage (In-memory)
# Data will be lost on server restart/cold boot
RUNTIME_DB = {}

@app.route('/')
def home():
    # Initial page load
    # Maybe load default year (latest) here? 
    # Or just let frontend do it. 
    # For now, just render basic template and user info
    user_data = RUNTIME_DB
    username = user_data.get('username', 'Guest')
    return render_template('index.html', user=username)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    watched_movies = RUNTIME_DB.get('watched', [])
    year = request.args.get('year')
    if year: year = str(year)
    
    stats = data_engine.analyze_profile(watched_movies, year=year)
    return jsonify(stats)

@app.route('/api/evolution', methods=['GET'])
def get_evolution():
    watched = RUNTIME_DB.get('watched', [])
    evolution = data_engine.get_genre_evolution(watched)
    return jsonify(evolution)

@app.route('/api/sync/batch', methods=['POST'])
def sync_batch():
    data = request.json
    username = data.get('username')
    page = data.get('page', 1)
    
    if not username:
        return jsonify({"status": "error", "message": "Username required"}), 400
    
    # 1. Scrape Page
    import time
    t0 = time.time()
    try:
        logging.info(f"--- START BATCH: {username} PG {page} ---")
        result = scraper.scrape_page(username, page)
        new_entries = result.get('entries', [])
        has_next = result.get('has_next', False)
        t_scrape = time.time() - t0
        logging.info(f"Scrape Page Took: {t_scrape:.2f}s. Entries: {len(new_entries)}")
    except Exception as e:
        logging.error(f"Scrape failed: {e}")
        return jsonify({"status": "error", "message": f"Scraper Error: {str(e)}"}), 500

    # 2. Update Runtime DB
    # ... (DB Logic) ...
    if page == 1:
        RUNTIME_DB.clear()
        RUNTIME_DB['username'] = username
        RUNTIME_DB['watched'] = []
    
    if RUNTIME_DB.get('username') != username:
        RUNTIME_DB.clear()
        RUNTIME_DB['username'] = username
        RUNTIME_DB['watched'] = []

    current_watched = RUNTIME_DB.get('watched', [])
    current_watched.extend(new_entries)
    RUNTIME_DB['watched'] = current_watched
    
    # 3. Analyze / Hydrate
    t1 = time.time()
    try:
        data_engine._hydrate_with_tmdb(new_entries)
        t_hydrate = time.time() - t1
        logging.info(f"Hydration Took: {t_hydrate:.2f}s")
    except Exception as e:
        logging.error(f"Hydration failed: {e}")
        # Don't fail the request, just log
    
    years = sorted(list(set(m['date'][:4] for m in current_watched)), reverse=True)
    latest_year = years[0] if years else None
    
    RUNTIME_DB['available_years'] = years
    RUNTIME_DB['last_updated'] = "Just now"
    
    logging.info(f"--- END BATCH: Total {time.time()-t0:.2f}s ---")
    
    return jsonify({
        "status": "success",
        "entries": new_entries,
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
    watched_titles = [m['title'] for m in watched]

    # Recs potentially based on "All Time" prefs or "Current Year" prefs?
    # Usually recs should be based on recent taste or all time. 
    # Let's use All Time for wider pool.
    profile = data_engine.analyze_profile(watched, year=None)
    recs = data_engine.get_recommendations(profile['top_genres'], watched_titles)

    return jsonify(recs)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
