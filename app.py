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
    user_data = RUNTIME_DB
    watched_movies = user_data.get('watched', [])
    stats = data_engine.analyze_profile(watched_movies)
    
    return render_template('index.html', stats=stats, user=user_data.get('username', 'Guest'))

@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    username = request.json.get('username')
    if not username:
        return jsonify({"status": "error", "message": "Username required"}), 400
    
    logging.info(f"Scraping for {username}...")
    watched_movies = scraper.scrape_user(username)
    
    if not watched_movies:
        return jsonify({"status": "error", "message": "No entries found or private profile"}), 404
        
    # Analyze and save
    stats = data_engine.analyze_profile(watched_movies)
    
    # Update Runtime DB
    RUNTIME_DB.clear() # Clear old data
    RUNTIME_DB.update({
        "username": username,
        "watched": watched_movies,
        "last_updated": "Just now",
        "stats": stats
    })
    
    return jsonify({"status": "success", "message": f"Scraped {len(watched_movies)} films"})

@app.route('/api/quiz')
def get_quiz():
    watched_movies = RUNTIME_DB.get('watched', [])
    quiz = data_engine.get_quiz_question(watched_movies)
    return jsonify(quiz)

@app.route('/api/recommendations')
def recommendations():
    watched = RUNTIME_DB.get('watched', [])
    watched_titles = [m['title'] for m in watched]

    profile = data_engine.analyze_profile(watched)
    recs = data_engine.get_recommendations(profile['top_genres'], watched_titles)

    return jsonify(recs)

# --- Filmle Game Routes ---
@app.route('/api/game/start', methods=['POST'])
def start_game():
    return jsonify(data_engine.start_filmle())

@app.route('/api/game/guess', methods=['POST'])
def guess_game():
    data = request.json
    guess = data.get('guess', '')
    return jsonify(data_engine.guess_filmle(guess))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
