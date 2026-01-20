import os
import json
import random
from dotenv import load_dotenv

# Load env variables from .env if present
load_dotenv()

class DataEngine:
    def __init__(self, movies_path='movies.json'):
        self.movies_path = movies_path
        self.movies_db = self._load_movies_db()
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.tmdb_key = os.getenv("TMDB_API_KEY")
        self.mode = "AI" if (self.openai_key and self.tmdb_key) else "FALLBACK"
        print(f"DataEngine initialized in {self.mode} mode.")

    def _load_movies_db(self):
        if os.path.exists(self.movies_path):
            with open(self.movies_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def get_quiz_question(self, watched_movies=None):
        """
        Returns a dictionary:
        {
            "question": str,
            "options": [str, str, str, str],
            "correct_index": int,
            "movie_title": str,
            "poster_url": str
        }
        """
        if self.mode == "AI" and self.openai_key:
            return self._get_ai_quiz(watched_movies)
        else:
            return self._get_fallback_quiz(watched_movies)

    def _get_fallback_quiz(self, watched_movies):
        # Default quiz: "You watched [Title]. What star rating did you give it?"
        # If we have scraped data (watched_movies), use it. otherwise use random from DB.
        
        target_movie = None
        user_rating = None
        
        if watched_movies and len(watched_movies) > 0:
            target_movie = random.choice(watched_movies)
            # Find poster in DB if possible
            db_match = next((m for m in self.movies_db if m['title'].lower() == target_movie['title'].lower()), None)
            poster_url = db_match['poster_url'] if db_match else "https://via.placeholder.com/300x450?text=No+Poster"
            user_rating = target_movie['rating']
        else:
            # If no watched data, pick random from DB and pretend
            target_movie = random.choice(self.movies_db)
            poster_url = target_movie['poster_url']
            user_rating = random.choice([3.0, 3.5, 4.0, 4.5, 5.0]) # Mock rating
            target_movie['rating'] = user_rating

        question = f"You watched '{target_movie['title']}'. What star rating did you give it?"
        
        # Generate options
        correct_rating = float(target_movie['rating'])
        options = [correct_rating]
        while len(options) < 4:
            # Generate random rating between 0.5 and 5.0 in 0.5 steps
            r = random.randint(1, 10) / 2.0
            if r not in options:
                options.append(r)
        
        random.shuffle(options)
        
        return {
            "question": question,
            "options": [f"{opt} stars" for opt in options],
            "correct_index": options.index(correct_rating),
            "movie_title": target_movie['title'],
            "poster_url": poster_url
        }

    def _get_ai_quiz(self, watched_movies):
        # Placeholder for AI implementation
        # In a real scenario, call OpenAI API here
        return self._get_fallback_quiz(watched_movies) # Fallback for now until fully implemented

    def get_recommendations(self, top_genres, watched_titles):
        if self.mode == "AI" and self.openai_key:
            return self._get_ai_recommendations(top_genres, watched_titles)
        else:
            return self._get_fallback_recommendations(top_genres, watched_titles)

    def _get_fallback_recommendations(self, top_genres, watched_titles):
        # Filter DB for movies that match top genres and are NOT in watched_titles
        recs = []
        watched_set = set(t.lower() for t in watched_titles)
        
        for movie in self.movies_db:
            if movie['title'].lower() in watched_set:
                continue
            
            # Check overlap in genres
            movie_genres = set(movie.get('genre', []))
            if not top_genres:
                # If no top genres known, just add it (random fill later)
                recs.append(movie)
                continue

            # If movie shares at least one genre with top_genres
            common = movie_genres.intersection(set(top_genres))
            if common:
               recs.append(movie)
        
        # Return top 10 random matches
        random.shuffle(recs)
        return recs[:10]

    def _get_ai_recommendations(self, top_genres, watched_titles):
        # Placeholder for AI implementation
        return self._get_fallback_recommendations(top_genres, watched_titles)

    def analyze_profile(self, watched_movies):
        """
        Analyzes the watched movies to return:
        - total_films
        - average_rating
        - top_genres: [("Drama", 15), ("Comedy", 10), ...]
        - heatmap_data: { "2024-01-01": 2, ... }
        """
        if not watched_movies:
            return {
                "total_films": 0,
                "average_rating": 0,
                "top_genres": [],
                "heatmap_data": {}
            }
            
        total_films = len(watched_movies)
        total_rating = sum(m['rating'] for m in watched_movies)
        average_rating = round(total_rating / total_films, 2) if total_films > 0 else 0
        
        # Genre Analysis
        genre_counts = {}
        for m in watched_movies:
            for g in m.get('genre', []):
                genre_counts[g] = genre_counts.get(g, 0) + 1
                
        # Sort genres by count
        sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Heatmap Data (Date -> Count)
        heatmap_data = {}
        for m in watched_movies:
            d = m['date']
            heatmap_data[d] = heatmap_data.get(d, 0) + 1
            
        return {
            "total_films": total_films,
            "average_rating": average_rating,
            "top_genres": sorted_genres,
            "heatmap_data": heatmap_data
        }

