"""
Configuration management for Telegram Protection Bot
"""

import os
import json
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Bot configuration class"""
    
    def __init__(self):
        # Telegram API credentials
        self.API_ID = int(os.getenv("API_ID", "0"))
        self.API_HASH = os.getenv("API_HASH", "")
        self.BOT_TOKEN = os.getenv("BOT_TOKEN", "")
        
        # Database configuration
        self.DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_data.db")
        
        # Moderation settings
        self.MAX_MESSAGES_PER_MINUTE = int(os.getenv("MAX_MESSAGES_PER_MINUTE", "10"))
        self.FLOOD_THRESHOLD = int(os.getenv("FLOOD_THRESHOLD", "5"))
        self.FLOOD_TIMEFRAME = int(os.getenv("FLOOD_TIMEFRAME", "60"))  # seconds
        
        # Feature toggles
        self.ENABLE_TEXT_FILTER = os.getenv("ENABLE_TEXT_FILTER", "true").lower() == "true"
        self.ENABLE_EDIT_MONITOR = os.getenv("ENABLE_EDIT_MONITOR", "true").lower() == "true"
        self.ENABLE_MEDIA_FILTER = os.getenv("ENABLE_MEDIA_FILTER", "true").lower() == "true"
        self.ENABLE_ANTI_FLOOD = os.getenv("ENABLE_ANTI_FLOOD", "true").lower() == "true"
        
        # Logging settings
        self.LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "30"))
        self.ENABLE_AUDIT_LOGS = os.getenv("ENABLE_AUDIT_LOGS", "true").lower() == "true"
        
        # Admin settings
        self.SUDO_USERS = self._parse_user_list(os.getenv("SUDO_USERS", ""))
        
        # Keywords file path
        self.KEYWORDS_FILE = os.getenv("KEYWORDS_FILE", "keywords.json")
        
        # Validation
        self._validate_config()
    
    def _parse_user_list(self, user_string: str) -> List[int]:
        """Parse comma-separated user IDs"""
        if not user_string:
            return []
        try:
            return [int(uid.strip()) for uid in user_string.split(",") if uid.strip()]
        except ValueError:
            return []
    
    def _validate_config(self):
        """Validate essential configuration"""
        if not self.API_ID or not self.API_HASH or not self.BOT_TOKEN:
            raise ValueError("Missing required Telegram API credentials")
        
        if self.API_ID == 0:
            raise ValueError("Invalid API_ID")
    
    def get_keywords(self) -> Dict[str, List[str]]:
        """Load banned keywords from file"""
        try:
            with open(self.KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return self._get_default_keywords()
        except json.JSONDecodeError:
            return self._get_default_keywords()
    
    def _get_default_keywords(self) -> Dict[str, List[str]]:
        """Default banned keywords"""
        return {
            "hate_speech": [
                "terrorist", "terrorism", "jihad", "isis", "bomb", "kill", "murder",
                "hate", "racist", "nazi", "fascist", "extremist", "radical"
            ],
            "violence": [
                "violence", "attack", "assault", "weapon", "gun", "knife", "blood",
                "gore", "death", "execute", "torture", "harm", "hurt", "beat"
            ],
            "drugs": [
                "drugs", "cocaine", "heroin", "weed", "marijuana", "cannabis",
                "pills", "needle", "inject", "smoke", "high", "dealer"
            ],
            "adult_content": [
                "porn", "sex", "nude", "naked", "explicit", "adult", "nsfw",
                "sexual", "erotic", "xxx", "18+", "mature"
            ],
            "hindi_offensive": [
                "मार", "मारूंगा", "हत्या", "आतंक", "बम", "गोली", "चाकू",
                "नफरत", "जाति", "धर्म", "हिंसा", "खून"
            ]
        }
    
    def save_keywords(self, keywords: Dict[str, List[str]]):
        """Save keywords to file"""
        try:
            with open(self.KEYWORDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(keywords, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise Exception(f"Failed to save keywords: {e}")
