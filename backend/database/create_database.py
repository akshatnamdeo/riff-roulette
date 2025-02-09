from pymongo import MongoClient
from pymongo.errors import CollectionInvalid
import logging
from typing import List, Dict
import os
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RiffRouletteDBSetup:
    def __init__(self, connection_string: str):
        """Initialize database connection"""
        try:
            self.client = MongoClient(connection_string)
            self.db = self.client.riff_roulette  # database name
            logger.info("Successfully connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    def create_collections(self):
        """Create all required collections with validators"""
        try:
            # Users Collection
            self.create_users_collection()
            
            # GameSessions Collection
            self.create_game_sessions_collection()
            
            # UserProgress Collection
            self.create_user_progress_collection()
            
            # Achievements Collection
            self.create_achievements_collection()
            
            # Leaderboards Collection
            self.create_leaderboards_collection()
            
            # UserSessions Collection
            self.create_user_sessions_collection()
            
            # UserSkillAnalytics Collection
            self.create_user_skill_analytics_collection()
            
            # Create indexes
            self.create_indexes()
            
            logger.info("Successfully created all collections and indexes")
            
        except Exception as e:
            logger.error(f"Error creating collections: {str(e)}")
            raise

    def create_users_collection(self):
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["username", "email", "password", "created_at"],
                "properties": {
                    "username": {
                        "bsonType": "string",
                        "minLength": 3,
                        "maxLength": 50
                    },
                    "email": {
                        "bsonType": "string",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
                    },
                    "profile": {
                        "bsonType": "object",
                        "properties": {
                            "skill_level": {
                                "enum": ["beginner", "intermediate", "advanced", "expert"]
                            }
                        }
                    }
                }
            }
        }
        self._create_collection_with_validator("users", validator)

    def create_game_sessions_collection(self):
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["user_id", "started_at", "difficulty"],
                "properties": {
                    "difficulty": {
                        "enum": ["easy", "medium", "hard", "expert"]
                    },
                    "mode": {
                        "enum": ["normal", "problem"]
                    }
                }
            }
        }
        self._create_collection_with_validator("game_sessions", validator)

    def create_user_progress_collection(self):
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["user_id", "song_id"],
                "properties": {
                    "highest_score": {
                        "bsonType": "number",
                        "minimum": 0
                    },
                    "times_played": {
                        "bsonType": "number",
                        "minimum": 0
                    }
                }
            }
        }
        self._create_collection_with_validator("user_progress", validator)

    def create_achievements_collection(self):
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name", "description", "requirements"],
                "properties": {
                    "rarity": {
                        "enum": ["common", "rare", "epic", "legendary"]
                    }
                }
            }
        }
        self._create_collection_with_validator("achievements", validator)

    def create_leaderboards_collection(self):
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["song_id", "difficulty", "type", "timeframe"],
                "properties": {
                    "timeframe": {
                        "enum": ["daily", "weekly", "monthly", "all-time"]
                    }
                }
            }
        }
        self._create_collection_with_validator("leaderboards", validator)

    def create_user_sessions_collection(self):
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["user_id", "session_start"],
                "properties": {
                    "games_played": {
                        "bsonType": "number",
                        "minimum": 0
                    }
                }
            }
        }
        self._create_collection_with_validator("user_sessions", validator)

    def create_user_skill_analytics_collection(self):
        validator = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["user_id", "updated_at"],
                "properties": {
                    "mastery_levels": {
                        "bsonType": "object",
                        "properties": {
                            "overall": {
                                "bsonType": "number",
                                "minimum": 0,
                                "maximum": 100
                            }
                        }
                    }
                }
            }
        }
        self._create_collection_with_validator("user_skill_analytics", validator)

    def _create_collection_with_validator(self, name: str, validator: Dict):
        """Helper method to create a collection with validation"""
        try:
            self.db.create_collection(name, validator=validator)
            logger.info(f"Created collection: {name}")
        except CollectionInvalid:
            logger.info(f"Collection {name} already exists")

    def create_indexes(self):
        """Create all required indexes"""
        # Users indexes
        self.db.users.create_index("username", unique=True)
        self.db.users.create_index("email", unique=True)
        
        # GameSessions indexes
        self.db.game_sessions.create_index([("user_id", 1), ("started_at", -1)])
        
        # UserProgress indexes
        self.db.user_progress.create_index([("user_id", 1), ("song_id", 1)])
        
        # Leaderboards indexes
        self.db.leaderboards.create_index([
            ("song_id", 1),
            ("difficulty", 1),
            ("type", 1),
            ("timeframe", 1)
        ])
        
        # UserSessions indexes
        self.db.user_sessions.create_index([("user_id", 1), ("session_start", -1)])
        
        # UserSkillAnalytics indexes
        self.db.user_skill_analytics.create_index([("user_id", 1), ("updated_at", -1)])
        
        logger.info("Created all indexes")

    def create_sample_data(self):
        """Create sample data for testing"""
        # Create a sample user
        user = {
            "username": "test_user",
            "email": "test@example.com",
            "password": "hashed_password",
            "created_at": datetime.utcnow(),
            "profile": {
                "skill_level": "intermediate",
                "guitar_experience_years": 2
            }
        }
        
        try:
            user_id = self.db.users.insert_one(user).inserted_id
            logger.info(f"Created sample user with ID: {user_id}")
            
            # Create a sample game session
            game_session = {
                "user_id": user_id,
                "song_id": "sample_song",
                "started_at": datetime.utcnow(),
                "difficulty": "medium",
                "mode": "normal"
            }
            self.db.game_sessions.insert_one(game_session)
            
            logger.info("Created sample data successfully")
            
        except Exception as e:
            logger.error(f"Error creating sample data: {str(e)}")
            raise

def main():
    # Get MongoDB connection string from environment variable
    connection_string = ""
    if not connection_string:
        raise ValueError("MONGODB_URI environment variable not set")
    
    # Initialize and run setup
    db_setup = RiffRouletteDBSetup(connection_string)
    db_setup.create_collections()
    
    # Optionally create sample data
    # if os.getenv("CREATE_SAMPLE_DATA", "false").lower() == "true":
    #     db_setup.create_sample_data()

if __name__ == "__main__":
    main()