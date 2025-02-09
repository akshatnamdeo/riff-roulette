from pymongo import MongoClient
import logging
from datetime import datetime, timedelta
import random
import hashlib
import os
from typing import List, Dict, Any
from bson import ObjectId

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RiffRoulettePopulator:
    def __init__(self, connection_string: str):
        """Initialize database connection"""
        try:
            self.client = MongoClient(connection_string)
            self.db = self.client.riff_roulette
            logger.info("Successfully connected to MongoDB")
            
            # Sample song IDs (simulating Pinata CIDs)
            self.song_ids = [
                "QmX9LqsJ7wXHq3Kg5Z1nE5Vj6X2K8Y9NpQjR4M2mWvY1a",  # Easy
                "QmYbN8JvZ9K4L5X6P7rHqK2M3W4Y5NpQjR4M2mWvY2b",    # Medium
                "QmZcD8JvZ9K4L5X6P7rHqK2M3W4Y5NpQjR4M2mWvY3c",    # Hard
                "QmdE8JvZ9K4L5X6P7rHqK2M3W4Y5NpQjR4M2mWvY4d"      # Expert
            ]
            
            # Predefined user profiles for consistent data
            self.user_profiles = [
                {
                    "username": "GuitarMaster",
                    "email": "master@example.com",
                    "skill_level": "expert",
                    "preferred_difficulty": "expert",
                    "experience": 10
                },
                {
                    "username": "IntermediateJammer",
                    "email": "jammer@example.com",
                    "skill_level": "intermediate",
                    "preferred_difficulty": "medium",
                    "experience": 3
                },
                {
                    "username": "BeginnerRocker",
                    "email": "beginner@example.com",
                    "skill_level": "beginner",
                    "preferred_difficulty": "easy",
                    "experience": 1
                },
                {
                    "username": "CasualPlayer",
                    "email": "casual@example.com",
                    "skill_level": "intermediate",
                    "preferred_difficulty": "medium",
                    "experience": 2
                }
            ]
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    def populate_database(self):
        """Main method to populate all collections"""
        try:
            logger.info("Starting database population...")
            
            # Clear existing data
            self._clear_existing_data()
            
            # Create achievements first
            achievement_ids = self._create_achievements()
            
            # Create users
            user_ids = self._create_users()
            
            # Create game history for each user
            for user_id in user_ids:
                self._create_user_game_history(user_id, achievement_ids)
            
            # Create leaderboards
            self._create_leaderboards(user_ids)
            
            logger.info("Database population completed successfully!")
            
        except Exception as e:
            logger.error(f"Error during database population: {str(e)}")
            raise

    def _clear_existing_data(self):
        """Clear all existing data from collections"""
        collections = [
            'users', 'game_sessions', 'user_progress', 'achievements',
            'leaderboards', 'user_sessions', 'user_skill_analytics'
        ]
        for collection in collections:
            self.db[collection].delete_many({})
        logger.info("Cleared existing data from all collections")

    def _create_achievements(self) -> List[ObjectId]:
        """Create achievement templates"""
        achievements = [
            {
                "name": "Perfect Streak",
                "description": "Hit 100 perfect notes in a row",
                "requirements": {"type": "perfect_notes", "threshold": 100},
                "rarity": "legendary",
                "points": 1000
            },
            {
                "name": "Score Master",
                "description": "Achieve a score of 1,000,000 points",
                "requirements": {"type": "score", "threshold": 1000000},
                "rarity": "epic",
                "points": 750
            },
            {
                "name": "Combo King",
                "description": "Achieve a 500x combo",
                "requirements": {"type": "combo", "threshold": 500},
                "rarity": "rare",
                "points": 500
            }
        ]
        
        achievement_ids = []
        for achievement in achievements:
            result = self.db.achievements.insert_one(achievement)
            achievement_ids.append(result.inserted_id)
            
        logger.info(f"Created {len(achievement_ids)} achievements")
        return achievement_ids

    def _create_users(self) -> List[ObjectId]:
        """Create users with varying profiles"""
        user_ids = []
        
        for profile in self.user_profiles:
            user = {
                "username": profile["username"],
                "email": profile["email"],
                "password": self._hash_password("defaultpassword"),
                "created_at": datetime.utcnow() - timedelta(days=random.randint(30, 365)),
                "last_login": datetime.utcnow() - timedelta(hours=random.randint(1, 72)),
                "profile": {
                    "avatar_url": f"https://example.com/avatars/{profile['username'].lower()}.jpg",
                    "skill_level": profile["skill_level"],
                    "preferred_difficulty": profile["preferred_difficulty"],
                    "guitar_experience_years": profile["experience"],
                    "favorite_genres": self._generate_favorite_genres()
                },
                "stats": self._generate_user_stats(profile["skill_level"]),
                "settings": self._generate_user_settings()
            }
            
            result = self.db.users.insert_one(user)
            user_ids.append(result.inserted_id)
            
        logger.info(f"Created {len(user_ids)} users")
        return user_ids

    def _create_user_game_history(self, user_id: ObjectId, achievement_ids: List[ObjectId]):
        """Create comprehensive game history for a user"""
        user = self.db.users.find_one({"_id": user_id})
        skill_level = user["profile"]["skill_level"]
        
        # Calculate number of sessions based on account age
        days_since_creation = (datetime.utcnow() - user["created_at"]).days
        sessions_per_day = {"expert": 5, "intermediate": 3, "beginner": 1}.get(skill_level, 2)
        total_sessions = min(days_since_creation * sessions_per_day, 1000)
        
        # Generate session dates
        session_dates = self._generate_session_dates(
            user["created_at"],
            total_sessions
        )
        
        for session_date in session_dates:
            # Create user session
            session = self._create_single_session(user_id, session_date)
            
            # Create game sessions
            game_sessions = self._create_game_sessions(user, session_date)
            
            # Update user progress
            self._update_user_progress(user_id, game_sessions)
            
            # Update skill analytics
            self._update_skill_analytics(user_id, game_sessions, session_date)
            
            # Check achievements
            self._check_achievements(user_id, achievement_ids, game_sessions)

    def _generate_session_dates(self, start_date: datetime, num_sessions: int) -> List[datetime]:
        """Generate realistic session dates"""
        current_date = datetime.utcnow()
        date_range = (current_date - start_date).days
        
        dates = []
        for _ in range(num_sessions):
            random_days = random.randint(0, date_range)
            session_date = start_date + timedelta(days=random_days)
            dates.append(session_date)
        
        return sorted(dates)

    def _create_single_session(self, user_id: ObjectId, session_date: datetime) -> Dict[str, Any]:
        """Create a single user session"""
        session_duration = random.randint(30, 180)  # 30 mins to 3 hours
        end_date = session_date + timedelta(minutes=session_duration)
        
        session = {
            "user_id": user_id,
            "session_start": session_date,
            "session_end": end_date,
            "games_played": random.randint(5, 20),
            "practice_time": session_duration * 60,
            "songs_attempted": random.sample(self.song_ids, random.randint(1, 4)),
            "performance_summary": {
                "average_score": random.randint(70000, 95000),
                "average_accuracy": random.uniform(0.75, 0.95),
                "total_notes_hit": random.randint(1000, 5000),
                "total_combos": random.randint(10, 50)
            }
        }
        
        self.db.user_sessions.insert_one(session)
        return session

    def _create_game_sessions(self, user: Dict[str, Any], session_date: datetime) -> List[Dict[str, Any]]:
        """Create multiple game sessions for a user session"""
        skill_level = user["profile"]["skill_level"]
        num_games = random.randint(3, 10)
        games = []
        
        for i in range(num_games):
            game_start = session_date + timedelta(minutes=i*15)
            duration = random.randint(180, 300)  # 3-5 minutes
            
            accuracy = self._get_skill_based_accuracy(skill_level)
            score = int(accuracy * 10000)
            
            game = {
                "user_id": user["_id"],
                "song_id": random.choice(self.song_ids),
                "started_at": game_start,
                "ended_at": game_start + timedelta(seconds=duration),
                "duration": duration,
                "difficulty": user["profile"]["preferred_difficulty"],
                "mode": random.choice(["normal", "problem"]),
                "final_score": score,
                "max_combo": int(accuracy * 100),
                "notes_data": self._generate_notes_data(accuracy),
                "performance_metrics": self._generate_performance_metrics(accuracy)
            }
            
            games.append(game)
        
        self.db.game_sessions.insert_many(games)
        return games

    def _generate_notes_data(self, accuracy: float) -> Dict[str, Any]:
        """Generate note hit/miss data based on accuracy"""
        total_notes = random.randint(100, 500)
        perfect_hits = int(total_notes * accuracy * 0.8)
        good_hits = int(total_notes * accuracy * 0.2)
        misses = total_notes - perfect_hits - good_hits
        
        return {
            "total_notes": total_notes,
            "hits": perfect_hits + good_hits,
            "misses": misses,
            "perfect_hits": perfect_hits,
            "good_hits": good_hits,
            "early_hits": int(good_hits * 0.6),
            "late_hits": int(good_hits * 0.4)
        }

    def _generate_performance_metrics(self, accuracy: float) -> Dict[str, Any]:
        """Generate performance metrics"""
        return {
            "accuracy": accuracy,
            "reaction_score": random.uniform(accuracy * 0.9, accuracy * 1.1),
            "rhythm_score": random.uniform(accuracy * 0.9, accuracy * 1.1),
            "creativity_score": random.uniform(0.6, 0.9),
            "avg_timing_error": random.uniform(0.01, 0.05)
        }

    def _update_user_progress(self, user_id: ObjectId, game_sessions: List[Dict[str, Any]]):
        """Update user progress based on game sessions"""
        for song_id in self.song_ids:
            song_sessions = [s for s in game_sessions if s["song_id"] == song_id]
            if song_sessions:
                progress = {
                    "user_id": user_id,
                    "song_id": song_id,
                    "highest_score": max(s["final_score"] for s in song_sessions),
                    "highest_combo": max(s["max_combo"] for s in song_sessions),
                    "times_played": len(song_sessions),
                    "best_performance_date": max(s["ended_at"] for s in song_sessions),
                    "difficulties_cleared": list(set(s["difficulty"] for s in song_sessions))
                }
                
                self.db.user_progress.update_one(
                    {"user_id": user_id, "song_id": song_id},
                    {"$set": progress},
                    upsert=True
                )

    def _update_skill_analytics(self, user_id: ObjectId, game_sessions: List[Dict[str, Any]], 
                              session_date: datetime):
        """Update user skill analytics"""
        analytics = {
            "user_id": user_id,
            "updated_at": session_date,
            "skill_metrics": {
                "reaction_time": self._generate_skill_metric_history(session_date),
                "rhythm_accuracy": self._generate_skill_metric_history(session_date),
                "creativity_score": self._generate_skill_metric_history(session_date)
            },
            "string_proficiency": {
                "low_e": random.uniform(60, 100),
                "a": random.uniform(60, 100),
                "d": random.uniform(60, 100),
                "g": random.uniform(60, 100),
                "b": random.uniform(60, 100),
                "high_e": random.uniform(60, 100)
            },
            "mastery_levels": {
                "timing": random.uniform(60, 100),
                "sight_reading": random.uniform(60, 100),
                "improvisation": random.uniform(60, 100),
                "overall": random.uniform(60, 100)
            }
        }
        
        self.db.user_skill_analytics.update_one(
            {"user_id": user_id},
            {"$set": analytics},
            upsert=True
        )

    def _check_achievements(self, user_id: ObjectId, achievement_ids: List[ObjectId],
                          game_sessions: List[Dict[str, Any]]):
        """Check and award achievements based on game sessions"""
        user = self.db.users.find_one({"_id": user_id})
        current_achievements = user.get("achievements", [])
        
        # Calculate metrics for achievement checks
        total_score = sum(session['final_score'] for session in game_sessions)
        max_combo = max(session['max_combo'] for session in game_sessions)
        perfect_hits = sum(session['notes_data']['perfect_hits'] for session in game_sessions)
        
        # Check for new achievements
        new_achievements = []
        for achievement_id in achievement_ids:
            if achievement_id not in [a['achievement_id'] for a in current_achievements]:
                achievement = self.db.achievements.find_one({"_id": achievement_id})
                if self._check_achievement_requirements(achievement, total_score, max_combo, perfect_hits):
                    new_achievements.append({
                        "achievement_id": achievement_id,
                        "unlocked_at": datetime.utcnow(),
                        "progress": 100
                    })
        
        # If new achievements were earned, update the user
        if new_achievements:
            all_achievements = current_achievements + new_achievements
            self.db.users.update_one(
                {"_id": user_id},
                {"$set": {"achievements": all_achievements}}
            )
            
            # Log awarded achievements
            for achievement in new_achievements:
                achievement_details = self.db.achievements.find_one({"_id": achievement['achievement_id']})
                logger.info(f"User {user_id} earned achievement: {achievement_details['name']}")

    def _check_achievement_requirements(self, achievement: Dict[str, Any], 
                                     total_score: int, max_combo: int, 
                                     perfect_hits: int) -> bool:
        """Check if the user meets achievement requirements"""
        req_type = achievement['requirements']['type']
        threshold = achievement['requirements']['threshold']
        
        if req_type == 'score':
            return total_score >= threshold
        elif req_type == 'combo':
            return max_combo >= threshold
        elif req_type == 'perfect_notes':
            return perfect_hits >= threshold
        
        return False

    def _get_skill_based_accuracy(self, skill_level: str) -> float:
        """Get accuracy range based on skill level"""
        ranges = {
            "expert": (0.90, 0.99),
            "intermediate": (0.75, 0.89),
            "beginner": (0.60, 0.74)
        }
        min_acc, max_acc = ranges.get(skill_level, (0.70, 0.85))
        return random.uniform(min_acc, max_acc)

    def _generate_favorite_genres(self) -> List[str]:
        """Generate a list of favorite genres"""
        all_genres = ["rock", "metal", "jazz", "blues", "pop", "classical", "funk"]
        return random.sample(all_genres, random.randint(1, 4))

    def _generate_user_stats(self, skill_level: str) -> Dict[str, Any]:
        """Generate user statistics based on skill level"""
        accuracy = self._get_skill_based_accuracy(skill_level)
        multipliers = {
            "expert": (1000, 2000, 0.95),
            "intermediate": (200, 500, 0.85),
            "beginner": (20, 50, 0.70)
        }
        songs_mult, playtime_mult, acc_mult = multipliers.get(skill_level, (100, 300, 0.80))
        
        return {
            "total_songs_played": random.randint(songs_mult, songs_mult * 2),
            "total_play_time": random.randint(playtime_mult * 3600, playtime_mult * 7200),
            "highest_score": int(1000000 * accuracy),
            "highest_combo": int(1000 * accuracy),
            "average_accuracy": accuracy * acc_mult,
            "total_notes_hit": random.randint(10000, 50000),
            "total_notes_missed": random.randint(1000, 5000)
        }

    def _generate_user_settings(self) -> Dict[str, Any]:
        """Generate user settings"""
        return {
            "note_speed": random.uniform(0.8, 1.2),
            "visual_effects": random.choice([True, False]),
            "key_bindings": {
                "low_e": "q",
                "a": "w",
                "d": "e",
                "g": "r",
                "b": "t",
                "high_e": "y"
            },
            "audio_settings": {
                "master_volume": random.uniform(0.7, 1.0),
                "effects_volume": random.uniform(0.6, 1.0),
                "music_volume": random.uniform(0.8, 1.0)
            }
        }

    def _generate_skill_metric_history(self, date: datetime) -> Dict[str, Any]:
        """Generate skill metric history"""
        return {
            "average": random.uniform(70, 95),
            "trend": random.uniform(-0.1, 0.1),
            "history": [
                {
                    "date": date - timedelta(days=i),
                    "value": random.uniform(65, 100)
                }
                for i in range(0, 30, 5)  # 6 data points over 30 days
            ]
        }

    def _create_leaderboards(self, user_ids: List[ObjectId]):
        """Create leaderboards for all songs"""
        timeframes = ["daily", "weekly", "monthly", "all-time"]
        difficulties = ["easy", "medium", "hard", "expert"]
        types = ["score", "combo", "accuracy"]
        
        for song_id in self.song_ids:
            for difficulty in difficulties:
                for type_ in types:
                    for timeframe in timeframes:
                        entries = []
                        for user_id in user_ids:
                            user = self.db.users.find_one({"_id": user_id})
                            skill_level = user['profile']['skill_level']
                            
                            # Generate realistic score based on skill level
                            base_score = self._get_skill_based_score(skill_level, difficulty)
                            variance = random.uniform(-0.1, 0.1)  # ±10% variance
                            score = int(base_score * (1 + variance))
                            
                            entries.append({
                                "user_id": user_id,
                                "username": user['username'],
                                "score": score,
                                "achieved_at": datetime.utcnow() - timedelta(
                                    days=random.randint(0, self._get_timeframe_days(timeframe))
                                )
                            })
                        
                        # Sort entries by score
                        entries.sort(key=lambda x: x['score'], reverse=True)
                        
                        leaderboard = {
                            "song_id": song_id,
                            "difficulty": difficulty,
                            "type": type_,
                            "timeframe": timeframe,
                            "updated_at": datetime.utcnow(),
                            "entries": entries
                        }
                        
                        self.db.leaderboards.insert_one(leaderboard)
                        
    def _get_timeframe_days(self, timeframe: str) -> int:
        """Convert timeframe to number of days"""
        return {
            "daily": 1,
            "weekly": 7,
            "monthly": 30,
            "all-time": 365
        }.get(timeframe, 0)

    def _get_skill_based_score(self, skill_level: str, difficulty: str) -> int:
        """Generate realistic base score based on skill level and difficulty"""
        base_scores = {
            "expert": {
                "easy": 95000,
                "medium": 90000,
                "hard": 85000,
                "expert": 80000
            },
            "intermediate": {
                "easy": 85000,
                "medium": 75000,
                "hard": 65000,
                "expert": 55000
            },
            "beginner": {
                "easy": 70000,
                "medium": 60000,
                "hard": 45000,
                "expert": 35000
            }
        }
        return base_scores.get(skill_level, {}).get(difficulty, 50000)

    def _hash_password(self, password: str) -> str:
        """Hash a password for storing"""
        return hashlib.sha256(password.encode()).hexdigest()


def main():
    try:
        # Use a default connection string for testing
        connection_string = ""
        # Initialize and run populator
        logger.info("Starting database population process...")
        populator = RiffRoulettePopulator(connection_string)
        
        # Populate database
        populator.populate_database()
        
        logger.info("Database population completed successfully!")
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        raise


if __name__ == "__main__":
    main()