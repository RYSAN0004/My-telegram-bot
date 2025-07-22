"""
Welcome and Farewell System for Telegram Protection Bot
Supports custom messages, media, buttons, and user verification
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
from pyrogram.client import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatMember
from pyrogram.enums import ChatMemberStatus
from database import Database
from captcha import CaptchaSystem

logger = logging.getLogger(__name__)

@dataclass
class WelcomeConfig:
    """Welcome message configuration"""
    enabled: bool = True
    message: str = "Welcome {mention} to {chat_title}!"
    media_type: Optional[str] = None  # 'photo', 'video', 'document', 'sticker'
    media_file_id: Optional[str] = None
    buttons: List[Dict] = None  # [{'text': 'Rules', 'url': 'https://...'}]
    delete_after: Optional[int] = None  # seconds
    verify_users: bool = False
    captcha_type: str = "button"  # 'text', 'math', 'button'
    mute_until_verified: bool = True

@dataclass
class FarewellConfig:
    """Farewell message configuration"""
    enabled: bool = True
    message: str = "Goodbye {first_name}!"
    delete_after: Optional[int] = 30

class WelcomeSystem:
    """Welcome and farewell message system"""
    
    def __init__(self, client: Client, db: Database, captcha_system: CaptchaSystem):
        self.client = client
        self.db = db
        self.captcha_system = captcha_system
        
        # Configuration cache
        self.welcome_configs: Dict[int, WelcomeConfig] = {}
        self.farewell_configs: Dict[int, FarewellConfig] = {}
        
        # Initialize database tables
        asyncio.create_task(self._create_welcome_tables())
    
    async def _create_welcome_tables(self):
        """Create welcome system database tables"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS welcome_configs (
                chat_id INTEGER PRIMARY KEY,
                enabled BOOLEAN DEFAULT TRUE,
                message TEXT DEFAULT 'Welcome {mention} to {chat_title}!',
                media_type TEXT,
                media_file_id TEXT,
                buttons TEXT,
                delete_after INTEGER,
                verify_users BOOLEAN DEFAULT FALSE,
                captcha_type TEXT DEFAULT 'button',
                mute_until_verified BOOLEAN DEFAULT TRUE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS farewell_configs (
                chat_id INTEGER PRIMARY KEY,
                enabled BOOLEAN DEFAULT TRUE,
                message TEXT DEFAULT 'Goodbye {first_name}!',
                delete_after INTEGER DEFAULT 30,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS welcome_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        for table_sql in tables:
            await self.db.connection.execute(table_sql)
        
        await self.db.connection.commit()
    
    async def get_welcome_config(self, chat_id: int) -> WelcomeConfig:
        """Get welcome configuration for a chat"""
        # Check cache first
        if chat_id in self.welcome_configs:
            return self.welcome_configs[chat_id]
        
        try:
            cursor = await self.db.connection.execute(
                "SELECT * FROM welcome_configs WHERE chat_id = ?", (chat_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                buttons = json.loads(row[5]) if row[5] else []
                config = WelcomeConfig(
                    enabled=bool(row[1]),
                    message=row[2],
                    media_type=row[3],
                    media_file_id=row[4],
                    buttons=buttons,
                    delete_after=row[6],
                    verify_users=bool(row[7]),
                    captcha_type=row[8],
                    mute_until_verified=bool(row[9])
                )
            else:
                # Default configuration
                config = WelcomeConfig()
            
            # Cache the configuration
            self.welcome_configs[chat_id] = config
            return config
            
        except Exception as e:
            logger.error(f"Error getting welcome config: {e}")
            return WelcomeConfig()
    
    async def get_farewell_config(self, chat_id: int) -> FarewellConfig:
        """Get farewell configuration for a chat"""
        # Check cache first
        if chat_id in self.farewell_configs:
            return self.farewell_configs[chat_id]
        
        try:
            cursor = await self.db.connection.execute(
                "SELECT * FROM farewell_configs WHERE chat_id = ?", (chat_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                config = FarewellConfig(
                    enabled=bool(row[1]),
                    message=row[2],
                    delete_after=row[3]
                )
            else:
                # Default configuration
                config = FarewellConfig()
            
            # Cache the configuration
            self.farewell_configs[chat_id] = config
            return config
            
        except Exception as e:
            logger.error(f"Error getting farewell config: {e}")
            return FarewellConfig()
    
    async def set_welcome_config(self, chat_id: int, config: WelcomeConfig) -> bool:
        """Set welcome configuration for a chat"""
        try:
            buttons_json = json.dumps(config.buttons) if config.buttons else None
            
            await self.db.connection.execute(
                """INSERT OR REPLACE INTO welcome_configs 
                   (chat_id, enabled, message, media_type, media_file_id, buttons, 
                    delete_after, verify_users, captcha_type, mute_until_verified, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    chat_id, config.enabled, config.message, config.media_type,
                    config.media_file_id, buttons_json, config.delete_after,
                    config.verify_users, config.captcha_type, config.mute_until_verified,
                    datetime.utcnow()
                )
            )
            await self.db.connection.commit()
            
            # Update cache
            self.welcome_configs[chat_id] = config
            
            logger.info(f"Welcome config updated for chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting welcome config: {e}")
            return False
    
    async def set_farewell_config(self, chat_id: int, config: FarewellConfig) -> bool:
        """Set farewell configuration for a chat"""
        try:
            await self.db.connection.execute(
                """INSERT OR REPLACE INTO farewell_configs 
                   (chat_id, enabled, message, delete_after, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (chat_id, config.enabled, config.message, config.delete_after, datetime.utcnow())
            )
            await self.db.connection.commit()
            
            # Update cache
            self.farewell_configs[chat_id] = config
            
            logger.info(f"Farewell config updated for chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting farewell config: {e}")
            return False
    
    async def handle_new_member(self, message: Message, new_members: List[ChatMember]):
        """Handle new member join"""
        chat_id = message.chat.id
        config = await self.get_welcome_config(chat_id)
        
        if not config.enabled:
            return
        
        for member in new_members:
            user = member.user
            
            # Skip bots unless configured otherwise
            if user.is_bot:
                continue
            
            # Log the join
            await self._log_welcome_event(chat_id, user.id, "user_joined")
            
            # Start verification if enabled
            if config.verify_users:
                # Mute user until verified
                if config.mute_until_verified:
                    try:
                        await self.client.restrict_chat_member(
                            chat_id, user.id,
                            until_date=datetime.utcnow() + timedelta(minutes=10)
                        )
                    except Exception as e:
                        logger.error(f"Failed to mute new user {user.id}: {e}")
                
                # Start captcha verification
                success = await self.captcha_system.start_verification(
                    chat_id, user.id, config.captcha_type
                )
                
                if not success:
                    logger.error(f"Failed to start verification for user {user.id}")
                    continue
            
            # Send welcome message
            await self._send_welcome_message(chat_id, user, config)
    
    async def _send_welcome_message(self, chat_id: int, user, config: WelcomeConfig):
        """Send welcome message to new member"""
        try:
            # Get chat info
            chat = await self.client.get_chat(chat_id)
            
            # Format message
            message_text = self._format_message(
                config.message, user, chat.title if chat else "this group"
            )
            
            # Create inline keyboard if buttons are configured
            keyboard = None
            if config.buttons:
                keyboard_buttons = []
                for button_row in config.buttons:
                    row = []
                    if isinstance(button_row, list):
                        for button in button_row:
                            if 'url' in button:
                                row.append(InlineKeyboardButton(button['text'], url=button['url']))
                            elif 'callback_data' in button:
                                row.append(InlineKeyboardButton(button['text'], callback_data=button['callback_data']))
                    else:
                        # Single button
                        if 'url' in button_row:
                            row.append(InlineKeyboardButton(button_row['text'], url=button_row['url']))
                        elif 'callback_data' in button_row:
                            row.append(InlineKeyboardButton(button_row['text'], callback_data=button_row['callback_data']))
                    
                    if row:
                        keyboard_buttons.append(row)
                
                if keyboard_buttons:
                    keyboard = InlineKeyboardMarkup(keyboard_buttons)
            
            # Send message with media if configured
            welcome_msg = None
            
            if config.media_type and config.media_file_id:
                if config.media_type == 'photo':
                    welcome_msg = await self.client.send_photo(
                        chat_id, config.media_file_id, 
                        caption=message_text, reply_markup=keyboard
                    )
                elif config.media_type == 'video':
                    welcome_msg = await self.client.send_video(
                        chat_id, config.media_file_id,
                        caption=message_text, reply_markup=keyboard
                    )
                elif config.media_type == 'document':
                    welcome_msg = await self.client.send_document(
                        chat_id, config.media_file_id,
                        caption=message_text, reply_markup=keyboard
                    )
                elif config.media_type == 'sticker':
                    welcome_msg = await self.client.send_sticker(chat_id, config.media_file_id)
                    if message_text.strip():
                        # Send text separately for stickers
                        await self.client.send_message(chat_id, message_text, reply_markup=keyboard)
            else:
                # Send text message
                welcome_msg = await self.client.send_message(
                    chat_id, message_text, reply_markup=keyboard
                )
            
            # Schedule deletion if configured
            if config.delete_after and welcome_msg:
                asyncio.create_task(
                    self._delete_message_after(chat_id, welcome_msg.id, config.delete_after)
                )
            
            logger.info(f"Welcome message sent to user {user.id} in chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")
    
    async def handle_member_left(self, message: Message, left_member: ChatMember):
        """Handle member leaving"""
        chat_id = message.chat.id
        user = left_member.user
        
        # Skip bots
        if user.is_bot:
            return
        
        config = await self.farewell_config(chat_id)
        
        if not config.enabled:
            return
        
        # Log the leave
        await self._log_welcome_event(chat_id, user.id, "user_left")
        
        try:
            # Format farewell message
            message_text = self._format_message(config.message, user, "")
            
            # Send farewell message
            farewell_msg = await self.client.send_message(chat_id, message_text)
            
            # Schedule deletion if configured
            if config.delete_after:
                asyncio.create_task(
                    self._delete_message_after(chat_id, farewell_msg.id, config.delete_after)
                )
            
            logger.info(f"Farewell message sent for user {user.id} in chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error sending farewell message: {e}")
    
    def _format_message(self, template: str, user, chat_title: str = "") -> str:
        """Format message template with user and chat info"""
        # Create user mention
        mention = f"[{user.first_name}](tg://user?id={user.id})"
        
        # Replace placeholders
        formatted = template.replace('{mention}', mention)
        formatted = formatted.replace('{first_name}', user.first_name or "User")
        formatted = formatted.replace('{last_name}', user.last_name or "")
        formatted = formatted.replace('{username}', f"@{user.username}" if user.username else "")
        formatted = formatted.replace('{user_id}', str(user.id))
        formatted = formatted.replace('{chat_title}', chat_title)
        
        return formatted
    
    async def _delete_message_after(self, chat_id: int, message_id: int, delay: int):
        """Delete message after specified delay"""
        await asyncio.sleep(delay)
        try:
            await self.client.delete_messages(chat_id, message_id)
        except Exception as e:
            logger.error(f"Failed to delete message {message_id}: {e}")
    
    async def _log_welcome_event(self, chat_id: int, user_id: int, action: str):
        """Log welcome system events"""
        try:
            await self.db.connection.execute(
                "INSERT INTO welcome_stats (chat_id, user_id, action, timestamp) VALUES (?, ?, ?, ?)",
                (chat_id, user_id, action, datetime.utcnow())
            )
            await self.db.connection.commit()
        except Exception as e:
            logger.error(f"Failed to log welcome event: {e}")
    
    async def get_welcome_stats(self, chat_id: int, days: int = 7) -> Dict:
        """Get welcome system statistics"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get join stats
            cursor = await self.db.connection.execute(
                "SELECT COUNT(*) FROM welcome_stats WHERE chat_id = ? AND action = 'user_joined' AND timestamp > ?",
                (chat_id, cutoff_date)
            )
            joins = (await cursor.fetchone())[0]
            
            # Get leave stats
            cursor = await self.db.connection.execute(
                "SELECT COUNT(*) FROM welcome_stats WHERE chat_id = ? AND action = 'user_left' AND timestamp > ?",
                (chat_id, cutoff_date)
            )
            leaves = (await cursor.fetchone())[0]
            
            return {
                'joins': joins,
                'leaves': leaves,
                'net_growth': joins - leaves,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting welcome stats: {e}")
            return {'joins': 0, 'leaves': 0, 'net_growth': 0, 'period_days': days}
    
    async def test_welcome_message(self, chat_id: int, user_id: int) -> bool:
        """Test welcome message for a user"""
        try:
            config = await self.get_welcome_config(chat_id)
            user = await self.client.get_users(user_id)
            
            if isinstance(user, list):
                user = user[0] if user else None
            
            if user:
                await self._send_welcome_message(chat_id, user, config)
                return True
            
        except Exception as e:
            logger.error(f"Error testing welcome message: {e}")
        
        return False
    
    async def set_welcome_media(self, chat_id: int, media_type: str, file_id: str) -> bool:
        """Set welcome media (photo, video, document, sticker)"""
        try:
            config = await self.get_welcome_config(chat_id)
            config.media_type = media_type
            config.media_file_id = file_id
            
            return await self.set_welcome_config(chat_id, config)
            
        except Exception as e:
            logger.error(f"Error setting welcome media: {e}")
            return False
    
    async def remove_welcome_media(self, chat_id: int) -> bool:
        """Remove welcome media"""
        try:
            config = await self.get_welcome_config(chat_id)
            config.media_type = None
            config.media_file_id = None
            
            return await self.set_welcome_config(chat_id, config)
            
        except Exception as e:
            logger.error(f"Error removing welcome media: {e}")
            return False
    
    async def add_welcome_button(self, chat_id: int, text: str, url: str = None, 
                                callback_data: str = None) -> bool:
        """Add button to welcome message"""
        try:
            config = await self.get_welcome_config(chat_id)
            
            if not config.buttons:
                config.buttons = []
            
            button = {'text': text}
            if url:
                button['url'] = url
            elif callback_data:
                button['callback_data'] = callback_data
            else:
                return False
            
            config.buttons.append(button)
            
            return await self.set_welcome_config(chat_id, config)
            
        except Exception as e:
            logger.error(f"Error adding welcome button: {e}")
            return False
    
    async def remove_welcome_buttons(self, chat_id: int) -> bool:
        """Remove all welcome buttons"""
        try:
            config = await self.get_welcome_config(chat_id)
            config.buttons = []
            
            return await self.set_welcome_config(chat_id, config)
            
        except Exception as e:
            logger.error(f"Error removing welcome buttons: {e}")
            return False
    
    async def enable_verification(self, chat_id: int, captcha_type: str = "button") -> bool:
        """Enable user verification for new members"""
        try:
            config = await self.get_welcome_config(chat_id)
            config.verify_users = True
            config.captcha_type = captcha_type
            
            return await self.set_welcome_config(chat_id, config)
            
        except Exception as e:
            logger.error(f"Error enabling verification: {e}")
            return False
    
    async def disable_verification(self, chat_id: int) -> bool:
        """Disable user verification"""
        try:
            config = await self.get_welcome_config(chat_id)
            config.verify_users = False
            
            return await self.set_welcome_config(chat_id, config)
            
        except Exception as e:
            logger.error(f"Error disabling verification: {e}")
            return False