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
        self.tmdb_key = os.getenv("TMDB_API_KEY")
        self.mode = "LIVE" if self.tmdb_key else "OFFLINE"
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
        # Always use the Rating Quiz logic
        return self._get_rating_quiz(watched_movies)

    def _get_rating_quiz(self, watched_movies):
        target_movie = None
        
        if watched_movies and len(watched_movies) > 0:
            target_movie = random.choice(watched_movies)
            user_rating = target_movie['rating']
        else:
            # If no watched data, pick random from DB and pretend
            target_movie = random.choice(self.movies_db)
            user_rating = random.choice([3.0, 3.5, 4.0, 4.5, 5.0]) # Mock rating
            target_movie['rating'] = user_rating

        # Try to get real poster if TMDB key exists
        poster_url = self._get_tmdb_poster(target_movie['title'])
        
        # If TMDB failed or no key, check local DB for fallback
        if "via.placeholder.com" in poster_url:
             db_match = next((m for m in self.movies_db if m['title'].lower() == target_movie['title'].lower()), None)
             if db_match:
                 poster_url = db_match['poster_url']

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

    def _get_tmdb_poster(self, title):
        if not self.tmdb_key:
            return "https://via.placeholder.com/300x450?text=No+Poster"
            
        from tmdbv3api import TMDb, Movie
        tmdb = TMDb()
        tmdb.api_key = self.tmdb_key
        movie_api = Movie()
        
        try:
            search = movie_api.search(title)
            if search:
                # Get first result
                path = search[0].poster_path
                if path:
                    return f"https://image.tmdb.org/t/p/w500{path}"
        except Exception as e:
            print(f"TMDB Error for {title}: {e}")
            pass
        
        return "https://via.placeholder.com/300x450?text=No+Poster"

    def get_recommendations(self, top_genres, watched_titles):
        # Use local DB intersection for selection, but TMDB for posters
        recs = []
        watched_set = set(t.lower() for t in watched_titles)
        
        # Filter logic
        candidates = []
        for movie in self.movies_db:
             if movie['title'].lower() in watched_set:
                continue
             
             movie_genres = set(movie.get('genre', []))
             if not top_genres:
                 candidates.append(movie)
                 continue
                 
             if movie_genres.intersection(set(top_genres)):
                 candidates.append(movie)
        
        # Shuffle and pick top 10
        random.shuffle(candidates)
        selected = candidates[:10]
        
        # Hydrate with TMDB posters
        final_recs = []
        for m in selected:
            # We preferentially use the TMDB poster if available, otherwise keep local
            tmdb_poster = self._get_tmdb_poster(m['title'])
            final_recs.append({
                "title": m['title'],
                "year": m['year'],
                "poster_url": tmdb_poster if "via.placeholder.com" not in tmdb_poster else m['poster_url']
            })
            
        return final_recs

    def analyze_profile(self, watched_movies):
        """
        Analyzes the watched movies to return statistics.
        Also hydrates the movies with TMDB data (Genres/Posters) if possible.
        """
        if not watched_movies:
            return {
                "total_films": 0,
                "average_rating": 0,
                "top_genres": [],
                "heatmap_data": {}
            }
            
        # Hydrate data with TMDB if key is available
        if self.tmdb_key:
            self._hydrate_with_tmdb(watched_movies)
            
        total_films = len(watched_movies)
        total_rating = sum(m['rating'] for m in watched_movies)
        average_rating = round(total_rating / total_films, 2) if total_films > 0 else 0
        
        # Genre Analysis
        genre_counts = {}
        for m in watched_movies:
            for g in m.get('genre', []):
                # Filter out 'Uncategorized' if we have real data
                if g == 'Uncategorized' and len(m.get('genre', [])) > 1:
                    continue
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

    def _hydrate_with_tmdb(self, movies):
        """
        Updates the passed list of movies in-place with Genres and Poster URLs from TMDB.
        Fetching is done only if necessary to save API calls, but for a sync we might do a batch.
        """
        from tmdbv3api import TMDb, Movie, Genre
        tmdb = TMDb()
        tmdb.api_key = self.tmdb_key
        movie_api = Movie()
        genre_api = Genre()
        
        # Get Genre Map once
        try:
            genres_list = genre_api.movie_list()
            # Handle different return types from library versions
            if isinstance(genres_list, list):
                genre_map = {g['id']: g['name'] for g in genres_list}
            elif hasattr(genres_list, 'genres'):
                 genre_map = {g['id']: g['name'] for g in genres_list.genres}
            else:
                 genre_map = {}
        except:
            genre_map = {}

        print("Hydrating movies with TMDB data...")
        
        # Limit to last 20 for speed in demo, or full sync if robust
        # Let's do a safe iteration.
        for movie in movies:
            # Skip if already hydrated (simple check: genre is not Uncategorized)
            if movie.get('genre') != ['Uncategorized'] and movie.get('poster_url'):
                continue
                
            try:
                # Search by title and year if possible
                results = movie_api.search(movie['title'])
                
                # Filter by year if we have it to be precise
                target_year = movie['year']
                match = None
                
                if results:
                    if target_year:
                        # Try to match year
                        for r in results:
                            if hasattr(r, 'release_date') and str(target_year) in r.release_date:
                                match = r
                                break
                    
                    # Fallback to first result
                    if not match:
                        match = results[0]
                        
                    # Update Metadata
                    if match:
                         # Poster
                         if hasattr(match, 'poster_path') and match.poster_path:
                             movie['poster_url'] = f"https://image.tmdb.org/t/p/w500{match.poster_path}"
                         
                         # Genres
                         if hasattr(match, 'genre_ids') and genre_map:
                             real_genres = [genre_map.get(gid) for gid in match.genre_ids if gid in genre_map]
                             if real_genres:
                                 movie['genre'] = real_genres
            except Exception as e:
                print(f"Failed to hydrate {movie['title']}: {e}")
                continue
