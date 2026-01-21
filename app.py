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
    year = request.args.get('year') # Can be None
    
    evolution = data_engine.get_genre_evolution(watched, year_filter=year)
    return jsonify(evolution)

@app.route('/api/sync/batch', methods=['POST'])
# ... (Sync Batch remains same) ...

# ... (Skip Sync Batch lines to find Recs) ...

@app.route('/api/recommendations')
def recommendations():
    watched = RUNTIME_DB.get('watched', [])
    # Logic moved to DataEngine
    recs = data_engine.get_recommendations(watched)
    return jsonify(recs)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
