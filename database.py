"""
Database operations for Telegram Protection Bot
"""

import aiosqlite
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from config import Config

logger = logging.getLogger(__name__)

class Database:
    """Database manager for bot data"""
    
    def __init__(self):
        self.config = Config()
        self.db_path = self.config.DATABASE_PATH
        self.connection = None
    
    async def initialize(self):
        """Initialize database connection and create tables"""
        try:
            self.connection = await aiosqlite.connect(self.db_path)
            await self._create_tables()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    async def _create_tables(self):
        """Create necessary database tables"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                settings TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                is_admin BOOLEAN DEFAULT FALSE,
                is_whitelisted BOOLEAN DEFAULT FALSE,
                warnings INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS moderation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                original_message TEXT,
                edited_message TEXT,
                message_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS flood_tracker (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                message_count INTEGER DEFAULT 1,
                last_message_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reset_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS banned_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                keyword TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_id, category, keyword)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS group_settings (
                group_id INTEGER PRIMARY KEY,
                text_filter_enabled BOOLEAN DEFAULT TRUE,
                edit_monitor_enabled BOOLEAN DEFAULT TRUE,
                media_filter_enabled BOOLEAN DEFAULT TRUE,
                anti_flood_enabled BOOLEAN DEFAULT TRUE,
                max_messages_per_minute INTEGER DEFAULT 10,
                flood_threshold INTEGER DEFAULT 5,
                auto_delete_enabled BOOLEAN DEFAULT TRUE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        for table_sql in tables:
            await self.connection.execute(table_sql)
        
        await self.connection.commit()
    
    async def add_group(self, group_id: int, title: str) -> bool:
        """Add or update group in database"""
        try:
            await self.connection.execute(
                "INSERT OR REPLACE INTO groups (id, title, updated_at) VALUES (?, ?, ?)",
                (group_id, title, datetime.utcnow())
            )
            
            # Initialize group settings
            await self.connection.execute(
                "INSERT OR IGNORE INTO group_settings (group_id) VALUES (?)",
                (group_id,)
            )
            
            await self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to add group {group_id}: {e}")
            return False
    
    async def add_user(self, user_id: int, first_name: str, last_name: str = None, 
                      username: str = None, is_admin: bool = False) -> bool:
        """Add or update user in database"""
        try:
            await self.connection.execute(
                """INSERT OR REPLACE INTO users 
                   (id, first_name, last_name, username, is_admin, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, first_name, last_name, username, is_admin, datetime.utcnow())
            )
            await self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to add user {user_id}: {e}")
            return False
    
    async def log_moderation_action(self, group_id: int, user_id: int, action: str,
                                   reason: str = None, original_message: str = None,
                                   edited_message: str = None, message_id: int = None) -> bool:
        """Log moderation action"""
        try:
            await self.connection.execute(
                """INSERT INTO moderation_logs 
                   (group_id, user_id, action, reason, original_message, edited_message, message_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (group_id, user_id, action, reason, original_message, edited_message, message_id)
            )
            await self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to log moderation action: {e}")
            return False
    
    async def get_group_settings(self, group_id: int) -> Dict[str, Any]:
        """Get group settings"""
        try:
            cursor = await self.connection.execute(
                "SELECT * FROM group_settings WHERE group_id = ?", (group_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                return {
                    'text_filter_enabled': bool(row[1]),
                    'edit_monitor_enabled': bool(row[2]),
                    'media_filter_enabled': bool(row[3]),
                    'anti_flood_enabled': bool(row[4]),
                    'max_messages_per_minute': row[5],
                    'flood_threshold': row[6],
                    'auto_delete_enabled': bool(row[7])
                }
            else:
                # Return default settings
                return {
                    'text_filter_enabled': True,
                    'edit_monitor_enabled': True,
                    'media_filter_enabled': True,
                    'anti_flood_enabled': True,
                    'max_messages_per_minute': 10,
                    'flood_threshold': 5,
                    'auto_delete_enabled': True
                }
        except Exception as e:
            logger.error(f"Failed to get group settings for {group_id}: {e}")
            return {}
    
    async def update_group_settings(self, group_id: int, settings: Dict[str, Any]) -> bool:
        """Update group settings"""
        try:
            await self.connection.execute(
                """UPDATE group_settings SET 
                   text_filter_enabled = ?, edit_monitor_enabled = ?, media_filter_enabled = ?,
                   anti_flood_enabled = ?, max_messages_per_minute = ?, flood_threshold = ?,
                   auto_delete_enabled = ?, updated_at = ?
                   WHERE group_id = ?""",
                (
                    settings.get('text_filter_enabled', True),
                    settings.get('edit_monitor_enabled', True),
                    settings.get('media_filter_enabled', True),
                    settings.get('anti_flood_enabled', True),
                    settings.get('max_messages_per_minute', 10),
                    settings.get('flood_threshold', 5),
                    settings.get('auto_delete_enabled', True),
                    datetime.utcnow(),
                    group_id
                )
            )
            await self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update group settings for {group_id}: {e}")
            return False
    
    async def check_flood(self, group_id: int, user_id: int) -> bool:
        """Check if user is flooding and update counter"""
        try:
            now = datetime.utcnow()
            reset_time = now - timedelta(seconds=60)  # 1 minute window
            
            # Clean old flood records
            await self.connection.execute(
                "DELETE FROM flood_tracker WHERE reset_time < ?", (reset_time,)
            )
            
            # Get current flood record
            cursor = await self.connection.execute(
                "SELECT message_count, last_message_time FROM flood_tracker WHERE group_id = ? AND user_id = ?",
                (group_id, user_id)
            )
            row = await cursor.fetchone()
            
            if row:
                message_count, last_message_time = row
                last_time = datetime.fromisoformat(last_message_time)
                
                # If within flood timeframe, increment counter
                if (now - last_time).total_seconds() < 60:
                    message_count += 1
                    await self.connection.execute(
                        "UPDATE flood_tracker SET message_count = ?, last_message_time = ? WHERE group_id = ? AND user_id = ?",
                        (message_count, now, group_id, user_id)
                    )
                else:
                    # Reset counter
                    message_count = 1
                    await self.connection.execute(
                        "UPDATE flood_tracker SET message_count = 1, last_message_time = ?, reset_time = ? WHERE group_id = ? AND user_id = ?",
                        (now, now, group_id, user_id)
                    )
            else:
                # First message from user
                message_count = 1
                await self.connection.execute(
                    "INSERT INTO flood_tracker (group_id, user_id, message_count, last_message_time, reset_time) VALUES (?, ?, 1, ?, ?)",
                    (group_id, user_id, now, now)
                )
            
            await self.connection.commit()
            
            # Check flood threshold
            settings = await self.get_group_settings(group_id)
            flood_threshold = settings.get('flood_threshold', 5)
            
            return message_count >= flood_threshold
            
        except Exception as e:
            logger.error(f"Failed to check flood for user {user_id}: {e}")
            return False
    
    async def get_moderation_logs(self, group_id: int, limit: int = 100) -> List[Dict]:
        """Get recent moderation logs"""
        try:
            cursor = await self.connection.execute(
                """SELECT ml.*, u.first_name, u.username 
                   FROM moderation_logs ml 
                   LEFT JOIN users u ON ml.user_id = u.id 
                   WHERE ml.group_id = ? 
                   ORDER BY ml.timestamp DESC 
                   LIMIT ?""",
                (group_id, limit)
            )
            rows = await cursor.fetchall()
            
            logs = []
            for row in rows:
                logs.append({
                    'id': row[0],
                    'group_id': row[1],
                    'user_id': row[2],
                    'action': row[3],
                    'reason': row[4],
                    'original_message': row[5],
                    'edited_message': row[6],
                    'message_id': row[7],
                    'timestamp': row[8],
                    'user_name': row[9],
                    'username': row[10]
                })
            
            return logs
            
        except Exception as e:
            logger.error(f"Failed to get moderation logs: {e}")
            return []
    
    async def cleanup_old_logs(self, days: int = 30):
        """Clean up old moderation logs"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            await self.connection.execute(
                "DELETE FROM moderation_logs WHERE timestamp < ?", (cutoff_date,)
            )
            await self.connection.commit()
            logger.info(f"Cleaned up logs older than {days} days")
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
    
    async def close(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
