from flask import Flask, render_template, jsonify, request, session
from data_engine import DataEngine
from scraper import Scraper
import os
import json

app = Flask(__name__)
app.secret_key = 'super_secret_statsboxd_key'  # Needed for session

data_engine = DataEngine()
scraper = Scraper()

# Path to store per-user data temporarily (or just use session/memory)
# For this demo, let's use a simple global dict or a local json file "user_data.json"
# Global is bad for production but fine for a single-user local demo. 
# Let's use a file so it persists restart.
USER_DATA_FILE = "user_data.json"

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f)

@app.route('/')
def home():
    # Load data if exists
    user_data = load_user_data()
    watched_movies = user_data.get('watched', [])
    stats = data_engine.analyze_profile(watched_movies)
    
    return render_template('index.html', stats=stats, user=user_data.get('username', 'Guest'))

@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    username = request.json.get('username')
    if not username:
        return jsonify({"status": "error", "message": "Username required"}), 400
    
    print(f"Scraping for {username}...")
    watched_movies = scraper.scrape_user(username)
    
    if not watched_movies:
        return jsonify({"status": "error", "message": "No entries found or private profile"}), 404
        
    # Analyze and save
    stats = data_engine.analyze_profile(watched_movies)
    
    user_data = {
        "username": username,
        "watched": watched_movies,
        "last_updated": "Just now",
        "stats": stats
    }
    save_user_data(user_data)
    
    return jsonify({"status": "success", "message": f"Scraped {len(watched_movies)} films"})

@app.route('/api/quiz')
def get_quiz():
    user_data = load_user_data()
    watched_movies = user_data.get('watched', [])
    quiz = data_engine.get_quiz_question(watched_movies)
    return jsonify(quiz)

@app.route('/api/recommendations')
def get_recommendations():
    user_data = load_user_data()
    watched_movies = user_data.get('watched', [])
    stats = user_data.get('stats', {})
    top_genres = [g[0] for g in stats.get('top_genres', [])]
    
    # Pass just titles for filtering
    watched_titles = [m['title'] for m in watched_movies]
    
    recs = data_engine.get_recommendations(top_genres, watched_titles)
    return jsonify(recs)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
