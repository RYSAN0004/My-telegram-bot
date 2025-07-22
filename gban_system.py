"""
Global Ban (GBAN) System for Telegram Protection Bot
Allows sharing bans across multiple groups for enhanced protection
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from pyrogram.client import Client
from pyrogram.types import Message, User
from database import Database
from utils import safe_ban_user, format_user_mention

logger = logging.getLogger(__name__)

@dataclass
class GBanEntry:
    """Global ban entry"""
    user_id: int
    username: str
    first_name: str
    reason: str
    banned_by: int
    banned_by_username: str
    timestamp: datetime
    evidence: Optional[str] = None
    is_permanent: bool = True
    expires_at: Optional[datetime] = None

class GBanSystem:
    """Global ban management system"""
    
    def __init__(self, client: Client, db: Database):
        self.client = client
        self.db = db
        self.gban_list: Dict[int, GBanEntry] = {}
        self.gban_admins: Set[int] = set()  # Users who can issue gbans
        self.subscribed_chats: Set[int] = set()  # Chats that enforce gbans
        
        # Load data on startup
        asyncio.create_task(self._load_gban_data())
    
    async def _load_gban_data(self):
        """Load GBAN data from database"""
        try:
            # Create GBAN tables if they don't exist
            await self._create_gban_tables()
            
            # Load GBAN entries
            await self._load_gban_entries()
            
            # Load GBAN admins
            await self._load_gban_admins()
            
            # Load subscribed chats
            await self._load_subscribed_chats()
            
            logger.info(f"Loaded {len(self.gban_list)} GBAN entries")
            
        except Exception as e:
            logger.error(f"Failed to load GBAN data: {e}")
    
    async def _create_gban_tables(self):
        """Create GBAN database tables"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS gban_entries (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                reason TEXT NOT NULL,
                banned_by INTEGER NOT NULL,
                banned_by_username TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                evidence TEXT,
                is_permanent BOOLEAN DEFAULT TRUE,
                expires_at TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS gban_admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS gban_subscriptions (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT,
                subscribed_by INTEGER,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                auto_enforce BOOLEAN DEFAULT TRUE
            )
            """
        ]
        
        for table_sql in tables:
            await self.db.connection.execute(table_sql)
        
        await self.db.connection.commit()
    
    async def _load_gban_entries(self):
        """Load GBAN entries from database"""
        cursor = await self.db.connection.execute(
            "SELECT * FROM gban_entries WHERE is_permanent = TRUE OR expires_at > ?"
            , (datetime.utcnow(),)
        )
        rows = await cursor.fetchall()
        
        for row in rows:
            entry = GBanEntry(
                user_id=row[0],
                username=row[1] or "",
                first_name=row[2] or "",
                reason=row[3],
                banned_by=row[4],
                banned_by_username=row[5] or "",
                timestamp=datetime.fromisoformat(row[6]),
                evidence=row[7],
                is_permanent=bool(row[8]),
                expires_at=datetime.fromisoformat(row[9]) if row[9] else None
            )
            self.gban_list[entry.user_id] = entry
    
    async def _load_gban_admins(self):
        """Load GBAN admins from database"""
        cursor = await self.db.connection.execute("SELECT user_id FROM gban_admins")
        rows = await cursor.fetchall()
        
        for row in rows:
            self.gban_admins.add(row[0])
    
    async def _load_subscribed_chats(self):
        """Load subscribed chats from database"""
        cursor = await self.db.connection.execute("SELECT chat_id FROM gban_subscriptions")
        rows = await cursor.fetchall()
        
        for row in rows:
            self.subscribed_chats.add(row[0])
    
    async def gban_user(self, user_id: int, reason: str, banned_by: int, 
                       evidence: str = None, duration_hours: int = None) -> bool:
        """Add user to global ban list"""
        try:
            # Check if user is already gbanned
            if user_id in self.gban_list:
                return False
            
            # Get user info
            try:
                user = await self.client.get_users(user_id)
                if isinstance(user, list):
                    user = user[0] if user else None
                
                username = user.username if user else ""
                first_name = user.first_name if user else "Unknown"
            except:
                username = ""
                first_name = "Unknown"
            
            # Get banned_by user info
            try:
                banned_by_user = await self.client.get_users(banned_by)
                if isinstance(banned_by_user, list):
                    banned_by_user = banned_by_user[0] if banned_by_user else None
                
                banned_by_username = banned_by_user.username if banned_by_user else ""
            except:
                banned_by_username = ""
            
            # Create GBAN entry
            is_permanent = duration_hours is None
            expires_at = None if is_permanent else datetime.utcnow() + timedelta(hours=duration_hours)
            
            gban_entry = GBanEntry(
                user_id=user_id,
                username=username,
                first_name=first_name,
                reason=reason,
                banned_by=banned_by,
                banned_by_username=banned_by_username,
                timestamp=datetime.utcnow(),
                evidence=evidence,
                is_permanent=is_permanent,
                expires_at=expires_at
            )
            
            # Save to database
            await self.db.connection.execute(
                """INSERT INTO gban_entries 
                   (user_id, username, first_name, reason, banned_by, banned_by_username, 
                    timestamp, evidence, is_permanent, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    gban_entry.user_id, gban_entry.username, gban_entry.first_name,
                    gban_entry.reason, gban_entry.banned_by, gban_entry.banned_by_username,
                    gban_entry.timestamp, gban_entry.evidence, gban_entry.is_permanent,
                    gban_entry.expires_at
                )
            )
            await self.db.connection.commit()
            
            # Add to memory
            self.gban_list[user_id] = gban_entry
            
            # Enforce ban in all subscribed chats
            await self._enforce_gban(user_id, reason)
            
            logger.info(f"User {user_id} globally banned by {banned_by}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to GBAN user {user_id}: {e}")
            return False
    
    async def ungban_user(self, user_id: int, unbanned_by: int) -> bool:
        """Remove user from global ban list"""
        try:
            if user_id not in self.gban_list:
                return False
            
            # Remove from database
            await self.db.connection.execute(
                "DELETE FROM gban_entries WHERE user_id = ?", (user_id,)
            )
            await self.db.connection.commit()
            
            # Remove from memory
            del self.gban_list[user_id]
            
            # Log the ungban
            await self.db.log_moderation_action(
                0, user_id, "Global unban", f"Unbanned by user {unbanned_by}"
            )
            
            logger.info(f"User {user_id} globally unbanned by {unbanned_by}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to UNGBAN user {user_id}: {e}")
            return False
    
    async def _enforce_gban(self, user_id: int, reason: str):
        """Enforce GBAN in all subscribed chats"""
        banned_chats = 0
        
        for chat_id in self.subscribed_chats.copy():
            try:
                # Check if user is in the chat
                try:
                    member = await self.client.get_chat_member(chat_id, user_id)
                    if member:
                        # Ban the user
                        success = await safe_ban_user(self.client, chat_id, user_id)
                        if success:
                            banned_chats += 1
                            
                            # Send notification to chat
                            try:
                                await self.client.send_message(
                                    chat_id,
                                    f"🚫 **Global Ban Enforced**\n"
                                    f"User {user_id} has been banned.\n"
                                    f"Reason: {reason}"
                                )
                            except:
                                pass
                
                except Exception:
                    # User not in chat, skip
                    continue
                    
            except Exception as e:
                logger.error(f"Failed to enforce GBAN in chat {chat_id}: {e}")
                # Remove chat from subscriptions if bot is not admin
                if "chat not found" in str(e).lower() or "not enough rights" in str(e).lower():
                    self.subscribed_chats.discard(chat_id)
        
        logger.info(f"GBAN enforced in {banned_chats} chats for user {user_id}")
    
    async def check_user_gban(self, user_id: int) -> Optional[GBanEntry]:
        """Check if user is globally banned"""
        if user_id not in self.gban_list:
            return None
        
        entry = self.gban_list[user_id]
        
        # Check if temporary ban has expired
        if not entry.is_permanent and entry.expires_at:
            if datetime.utcnow() > entry.expires_at:
                # Remove expired ban
                await self.ungban_user(user_id, 0)  # System removal
                return None
        
        return entry
    
    async def handle_new_member(self, chat_id: int, user_id: int) -> bool:
        """Handle new member join - check for GBAN"""
        if chat_id not in self.subscribed_chats:
            return False
        
        gban_entry = await self.check_user_gban(user_id)
        if gban_entry:
            try:
                # Ban the user immediately
                success = await safe_ban_user(self.client, chat_id, user_id)
                if success:
                    # Send notification
                    notification = await self.client.send_message(
                        chat_id,
                        f"🚫 **Global Ban Detected**\n"
                        f"User {user_id} is globally banned and has been removed.\n"
                        f"Reason: {gban_entry.reason}\n"
                        f"Banned by: {gban_entry.banned_by_username or gban_entry.banned_by}"
                    )
                    
                    # Auto-delete notification after 30 seconds
                    asyncio.create_task(self._delete_after(chat_id, notification.id, 30))
                    
                    # Log the enforcement
                    await self.db.log_moderation_action(
                        chat_id, user_id, "GBAN enforcement", 
                        f"Global ban reason: {gban_entry.reason}"
                    )
                    
                    return True
            
            except Exception as e:
                logger.error(f"Failed to enforce GBAN for user {user_id} in chat {chat_id}: {e}")
        
        return False
    
    async def add_gban_admin(self, user_id: int, added_by: int) -> bool:
        """Add user to GBAN admin list"""
        try:
            # Get user info
            try:
                user = await self.client.get_users(user_id)
                if isinstance(user, list):
                    user = user[0] if user else None
                username = user.username if user else ""
            except:
                username = ""
            
            # Add to database
            await self.db.connection.execute(
                "INSERT OR REPLACE INTO gban_admins (user_id, username, added_by) VALUES (?, ?, ?)",
                (user_id, username, added_by)
            )
            await self.db.connection.commit()
            
            # Add to memory
            self.gban_admins.add(user_id)
            
            logger.info(f"User {user_id} added as GBAN admin by {added_by}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add GBAN admin {user_id}: {e}")
            return False
    
    async def remove_gban_admin(self, user_id: int) -> bool:
        """Remove user from GBAN admin list"""
        try:
            # Remove from database
            await self.db.connection.execute(
                "DELETE FROM gban_admins WHERE user_id = ?", (user_id,)
            )
            await self.db.connection.commit()
            
            # Remove from memory
            self.gban_admins.discard(user_id)
            
            logger.info(f"User {user_id} removed from GBAN admins")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove GBAN admin {user_id}: {e}")
            return False
    
    async def subscribe_chat(self, chat_id: int, chat_title: str, subscribed_by: int) -> bool:
        """Subscribe chat to GBAN system"""
        try:
            # Add to database
            await self.db.connection.execute(
                "INSERT OR REPLACE INTO gban_subscriptions (chat_id, chat_title, subscribed_by) VALUES (?, ?, ?)",
                (chat_id, chat_title, subscribed_by)
            )
            await self.db.connection.commit()
            
            # Add to memory
            self.subscribed_chats.add(chat_id)
            
            logger.info(f"Chat {chat_id} subscribed to GBAN system by {subscribed_by}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe chat {chat_id} to GBAN: {e}")
            return False
    
    async def unsubscribe_chat(self, chat_id: int) -> bool:
        """Unsubscribe chat from GBAN system"""
        try:
            # Remove from database
            await self.db.connection.execute(
                "DELETE FROM gban_subscriptions WHERE chat_id = ?", (chat_id,)
            )
            await self.db.connection.commit()
            
            # Remove from memory
            self.subscribed_chats.discard(chat_id)
            
            logger.info(f"Chat {chat_id} unsubscribed from GBAN system")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unsubscribe chat {chat_id} from GBAN: {e}")
            return False
    
    async def is_gban_admin(self, user_id: int) -> bool:
        """Check if user is a GBAN admin"""
        return user_id in self.gban_admins
    
    async def is_chat_subscribed(self, chat_id: int) -> bool:
        """Check if chat is subscribed to GBAN system"""
        return chat_id in self.subscribed_chats
    
    async def get_gban_stats(self) -> Dict:
        """Get GBAN system statistics"""
        total_gbans = len(self.gban_list)
        permanent_gbans = sum(1 for entry in self.gban_list.values() if entry.is_permanent)
        temporary_gbans = total_gbans - permanent_gbans
        subscribed_chats = len(self.subscribed_chats)
        gban_admins = len(self.gban_admins)
        
        return {
            'total_gbans': total_gbans,
            'permanent_gbans': permanent_gbans,
            'temporary_gbans': temporary_gbans,
            'subscribed_chats': subscribed_chats,
            'gban_admins': gban_admins
        }
    
    async def search_gban(self, query: str) -> List[GBanEntry]:
        """Search GBAN entries by username, name, or reason"""
        results = []
        query = query.lower()
        
        for entry in self.gban_list.values():
            if (query in entry.username.lower() or 
                query in entry.first_name.lower() or 
                query in entry.reason.lower()):
                results.append(entry)
        
        return results[:10]  # Limit to 10 results
    
    async def export_gban_list(self) -> str:
        """Export GBAN list for backup/sharing"""
        try:
            export_data = []
            
            for entry in self.gban_list.values():
                export_data.append({
                    'user_id': entry.user_id,
                    'username': entry.username,
                    'first_name': entry.first_name,
                    'reason': entry.reason,
                    'banned_by': entry.banned_by,
                    'timestamp': entry.timestamp.isoformat(),
                    'is_permanent': entry.is_permanent
                })
            
            return json.dumps(export_data, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Failed to export GBAN list: {e}")
            return ""
    
    async def cleanup_expired_gbans(self):
        """Clean up expired temporary GBANs"""
        expired_users = []
        now = datetime.utcnow()
        
        for user_id, entry in self.gban_list.items():
            if not entry.is_permanent and entry.expires_at and now > entry.expires_at:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            await self.ungban_user(user_id, 0)  # System removal
        
        if expired_users:
            logger.info(f"Cleaned up {len(expired_users)} expired GBANs")
    
    async def _delete_after(self, chat_id: int, message_id: int, delay: int):
        """Delete message after delay"""
        await asyncio.sleep(delay)
        try:
            await self.client.delete_messages(chat_id, message_id)
        except:
            pass