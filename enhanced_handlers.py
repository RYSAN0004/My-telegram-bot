"""
Enhanced Message handlers for Telegram Protection Bot
Integrates all advanced security and moderation features
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pyrogram.client import Client
from pyrogram import filters
from pyrogram.types import Message, CallbackQuery, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus
from database import Database
from filters import ContentFilter
from config import Config
from logger import BotLogger
from admin import AdminPanel
from utils import is_admin, get_user_info, format_user_mention, safe_ban_user, safe_restrict_user
from captcha import CaptchaSystem
from anti_spam import AntiSpamSystem
from gban_system import GBanSystem
from roles_system import RoleSystem, UserRole
from welcome_system import WelcomeSystem

logger = logging.getLogger(__name__)

class EnhancedHandlers:
    """Enhanced message handling system with all protection features"""
    
    def __init__(self, client: Client, db: Database):
        self.client = client
        self.db = db
        self.logger = logging.getLogger(__name__)
        
        # Initialize configuration and basic systems
        self.config = Config()
        self.content_filter = ContentFilter(self.config)
        self.bot_logger = BotLogger(db)
        self.admin_panel = AdminPanel(client, db, self.content_filter)
        
        # Initialize advanced systems
        self.captcha_system = CaptchaSystem(client, db)
        self.anti_spam_system = AntiSpamSystem(client, db)
        self.gban_system = GBanSystem(client, db)
        self.role_system = RoleSystem(client, db)
        self.welcome_system = WelcomeSystem(client, db, self.captcha_system)
        
        # Group state management
        self.locked_chats = set()
        self.message_tracker = {}
        
        self.register_handlers()
    
    def register_handlers(self):
        """Register all message handlers"""
        
        # Text message handler
        @self.client.on_message(filters.group & filters.text & ~filters.bot)
        async def handle_text_message(client: Client, message: Message):
            await self._handle_text_message(message)
        
        # Media message handler
        @self.client.on_message(filters.group & filters.media & ~filters.bot)
        async def handle_media_message(client: Client, message: Message):
            await self._handle_media_message(message)
        
        # New member handler
        @self.client.on_chat_member_updated()
        async def handle_member_update(client: Client, update: ChatMemberUpdated):
            await self._handle_member_update(update)
        
        # Callback query handler
        @self.client.on_callback_query()
        async def handle_callback(client: Client, callback_query: CallbackQuery):
            await self._handle_callback_query(callback_query)
        
        # Edit message handler
        @self.client.on_edited_message(filters.group & ~filters.bot)
        async def handle_edited_message(client: Client, message: Message):
            await self._handle_edited_message(message)
        
        # Command handlers
        @self.client.on_message(filters.command("start") & filters.private)
        async def start_command(client: Client, message: Message):
            await self._handle_start_command(message)
        
        @self.client.on_message(filters.command("help"))
        async def help_command(client: Client, message: Message):
            await self._handle_help_command(message)
        
        @self.client.on_message(filters.command(["gban", "globan"]))
        async def gban_command(client: Client, message: Message):
            await self._handle_gban_command(message)
        
        @self.client.on_message(filters.command(["ungban", "ungloban"]))
        async def ungban_command(client: Client, message: Message):
            await self._handle_ungban_command(message)
        
        @self.client.on_message(filters.command("lock"))
        async def lock_command(client: Client, message: Message):
            await self._handle_lock_command(message)
        
        @self.client.on_message(filters.command("unlock"))
        async def unlock_command(client: Client, message: Message):
            await self._handle_unlock_command(message)
        
        @self.client.on_message(filters.command("promote"))
        async def promote_command(client: Client, message: Message):
            await self._handle_promote_command(message)
        
        @self.client.on_message(filters.command("demote"))
        async def demote_command(client: Client, message: Message):
            await self._handle_demote_command(message)
        
        @self.client.on_message(filters.command("mute"))
        async def mute_command(client: Client, message: Message):
            await self._handle_mute_command(message)
        
        @self.client.on_message(filters.command("unmute"))
        async def unmute_command(client: Client, message: Message):
            await self._handle_unmute_command(message)
        
        @self.client.on_message(filters.command("setwelcome"))
        async def setwelcome_command(client: Client, message: Message):
            await self._handle_setwelcome_command(message)
        
        @self.client.on_message(filters.command("welcome"))
        async def welcome_command(client: Client, message: Message):
            await self._handle_welcome_settings_command(message)
    
    async def _handle_text_message(self, message: Message):
        """Handle text messages with all protection features"""
        try:
            chat_id = message.chat.id
            user_id = message.from_user.id
            
            # Add group and user to database
            await self.db.add_group(chat_id, message.chat.title)
            user_info = get_user_info(message.from_user)
            await self.db.add_user(
                user_info['id'], user_info['first_name'], 
                user_info['last_name'], user_info['username'],
                await is_admin(self.client, chat_id, user_id)
            )
            
            # Check if chat is locked
            if chat_id in self.locked_chats:
                user_role = await self.role_system.get_user_role(chat_id, user_id)
                if user_role not in [UserRole.OWNER, UserRole.ADMIN]:
                    await message.delete()
                    return
            
            # Check global ban
            gban_entry = await self.gban_system.check_user_gban(user_id)
            if gban_entry:
                await safe_ban_user(self.client, chat_id, user_id)
                await message.delete()
                
                notification = await self.client.send_message(
                    chat_id,
                    f"🚫 **Global Ban Detected**\n"
                    f"User {format_user_mention(message.from_user)} was globally banned.\n"
                    f"Reason: {gban_entry.reason}"
                )
                asyncio.create_task(self._delete_after(chat_id, notification.id, 30))
                return
            
            # Check user permissions
            if not await self.role_system.has_permission(chat_id, user_id, 'send_messages'):
                await message.delete()
                return
            
            # Anti-spam check
            spam_result = await self.anti_spam_system.analyze_message(message)
            if spam_result['is_spam']:
                await self._handle_spam_detection(message, spam_result)
                return
            
            # Content filtering
            settings = await self.db.get_group_settings(chat_id)
            if settings.get('text_filter_enabled', True):
                is_banned, categories, keywords = self.content_filter.check_text_content(message.text)
                
                if is_banned:
                    await self._handle_content_violation(message, categories, keywords)
                    return
            
            # Track message for edit monitoring
            self.message_tracker[message.id] = {
                'original_text': message.text,
                'chat_id': chat_id,
                'user_id': user_id,
                'timestamp': datetime.utcnow()
            }
            
            # Auto-delete old tracked messages (keep last 1000)
            if len(self.message_tracker) > 1000:
                old_keys = list(self.message_tracker.keys())[:-1000]
                for key in old_keys:
                    del self.message_tracker[key]
        
        except Exception as e:
            self.logger.error(f"Error handling text message: {e}")
    
    async def _handle_media_message(self, message: Message):
        """Handle media messages"""
        try:
            chat_id = message.chat.id
            user_id = message.from_user.id
            
            # Check permissions
            media_permission = None
            if message.photo:
                media_permission = 'send_media'
            elif message.sticker:
                media_permission = 'send_stickers'
            else:
                media_permission = 'send_media'
            
            if not await self.role_system.has_permission(chat_id, user_id, media_permission):
                await message.delete()
                return
            
            # Check if chat is locked
            if chat_id in self.locked_chats:
                user_role = await self.role_system.get_user_role(chat_id, user_id)
                if user_role not in [UserRole.OWNER, UserRole.ADMIN]:
                    await message.delete()
                    return
            
            # Anti-spam check for media
            spam_result = await self.anti_spam_system.analyze_message(message)
            if spam_result['is_spam']:
                await self._handle_spam_detection(message, spam_result)
                return
        
        except Exception as e:
            self.logger.error(f"Error handling media message: {e}")
    
    async def _handle_member_update(self, update: ChatMemberUpdated):
        """Handle member join/leave events"""
        try:
            if not update.new_chat_member:
                return
            
            chat_id = update.chat.id
            new_member = update.new_chat_member
            old_member = update.old_chat_member
            
            # Handle new member join
            if (old_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED] and 
                new_member.status == ChatMemberStatus.MEMBER):
                
                user_id = new_member.user.id
                
                # Check global ban first
                if await self.gban_system.handle_new_member(chat_id, user_id):
                    return  # User was gbanned and removed
                
                # Create a mock message object for welcome system compatibility
                class MockMessage:
                    def __init__(self, chat, user):
                        self.chat = chat
                        self.from_user = user
                
                mock_message = MockMessage(update.chat, new_member.user)
                await self.welcome_system.handle_new_member(mock_message, [new_member])
            
            # Handle member leave
            elif (old_member.status == ChatMemberStatus.MEMBER and 
                  new_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]):
                
                # Create mock message for farewell
                mock_message = MockMessage(update.chat, old_member.user)
                await self.welcome_system.handle_member_left(mock_message, old_member)
        
        except Exception as e:
            self.logger.error(f"Error handling member update: {e}")
    
    async def _handle_callback_query(self, callback_query: CallbackQuery):
        """Handle callback queries"""
        try:
            # Handle captcha callbacks
            if await self.captcha_system.handle_callback(callback_query):
                return
            
            # Handle admin panel callbacks
            await self.admin_panel.handle_callback(callback_query)
        
        except Exception as e:
            self.logger.error(f"Error handling callback query: {e}")
    
    async def _handle_edited_message(self, message: Message):
        """Handle message edits"""
        try:
            if message.id not in self.message_tracker:
                return
            
            original_data = self.message_tracker[message.id]
            
            # Check if edit is allowed
            settings = await self.db.get_group_settings(message.chat.id)
            if not settings.get('allow_edits', False):
                await message.delete()
                
                # Log the violation
                await self.bot_logger.log_violation(
                    message.chat.id, message.from_user.id,
                    "Edit attempt", f"Original: {original_data['original_text'][:100]}"
                )
                return
            
            # Check edited content
            if message.text:
                is_banned, categories, keywords = self.content_filter.check_text_content(message.text)
                if is_banned:
                    await self._handle_content_violation(message, categories, keywords)
                    return
        
        except Exception as e:
            self.logger.error(f"Error handling edited message: {e}")
    
    async def _handle_spam_detection(self, message: Message, spam_result: dict):
        """Handle detected spam"""
        try:
            await message.delete()
            
            # Log the spam detection
            await self.bot_logger.log_violation(
                message.chat.id, message.from_user.id,
                "Spam detected", f"Score: {spam_result['score']}, Reasons: {spam_result['reasons']}"
            )
            
            # Apply consequences based on spam severity
            if spam_result['score'] > 90:
                # High spam - ban user
                await safe_ban_user(self.client, message.chat.id, message.from_user.id)
                await self.client.send_message(
                    message.chat.id,
                    f"🚫 {format_user_mention(message.from_user)} has been banned for severe spam."
                )
            elif spam_result['score'] > 70:
                # Medium spam - mute user
                await self.role_system.mute_user(
                    message.chat.id, message.from_user.id, 
                    0, 24, "Spam detection"  # 24 hour mute
                )
        
        except Exception as e:
            self.logger.error(f"Error handling spam detection: {e}")
    
    async def _handle_content_violation(self, message: Message, categories: list, keywords: list):
        """Handle content filter violations"""
        try:
            await message.delete()
            
            # Log the violation
            await self.bot_logger.log_violation(
                message.chat.id, message.from_user.id,
                f"Content violation: {', '.join(categories)}",
                f"Keywords: {', '.join(keywords[:5])}"  # Log first 5 keywords
            )
            
            # Send warning message
            warning_msg = await self.client.send_message(
                message.chat.id,
                f"⚠️ {format_user_mention(message.from_user)}, your message was removed "
                f"for violating community guidelines."
            )
            
            # Auto-delete warning after 10 seconds
            asyncio.create_task(self._delete_after(message.chat.id, warning_msg.id, 10))
        
        except Exception as e:
            self.logger.error(f"Error handling content violation: {e}")
    
    # Command Handlers
    
    async def _handle_start_command(self, message: Message):
        """Handle /start command"""
        welcome_text = (
            "🛡️ **Group Guardian Bot**\n\n"
            "I'm an advanced protection bot that keeps your groups safe!\n\n"
            "**Features:**\n"
            "• Content filtering and spam protection\n"
            "• Anti-flood and anti-raid protection\n"
            "• Global ban system\n"
            "• Role-based permissions\n"
            "• Welcome/farewell messages\n"
            "• Captcha verification\n"
            "• Advanced moderation tools\n\n"
            "Add me to your group and promote me as admin to get started!"
        )
        
        await message.reply_text(welcome_text)
    
    async def _handle_help_command(self, message: Message):
        """Handle /help command"""
        if message.chat.type == "private":
            help_text = (
                "🛡️ **Group Guardian Bot Commands**\n\n"
                "**Moderation:**\n"
                "/lock - Lock group (admins only)\n"
                "/unlock - Unlock group\n"
                "/mute - Mute user\n"
                "/unmute - Unmute user\n"
                "/promote - Promote to trusted\n"
                "/demote - Demote user\n\n"
                "**Global Bans:**\n"
                "/gban - Global ban user\n"
                "/ungban - Remove global ban\n\n"
                "**Welcome System:**\n"
                "/setwelcome - Set welcome message\n"
                "/welcome - Welcome settings\n\n"
                "**Admin Panel:**\n"
                "/admin - Open admin panel\n\n"
                "Add me to your group as admin to use these features!"
            )
        else:
            help_text = (
                "🛡️ **Group Guardian Bot**\n\n"
                "I'm protecting this group with advanced security features.\n"
                "Send /help in private chat for full command list."
            )
        
        await message.reply_text(help_text)
    
    async def _handle_gban_command(self, message: Message):
        """Handle /gban command"""
        if not await self.gban_system.is_gban_admin(message.from_user.id):
            await message.reply_text("❌ You don't have permission to issue global bans.")
            return
        
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            reason = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "No reason provided"
        else:
            args = message.text.split()[1:]
            if len(args) < 2:
                await message.reply_text("Usage: /gban <user_id> <reason> or reply to a message with /gban <reason>")
                return
            
            try:
                target_user_id = int(args[0])
                target_user = await self.client.get_users(target_user_id)
                if isinstance(target_user, list):
                    target_user = target_user[0] if target_user else None
                reason = " ".join(args[1:])
            except:
                await message.reply_text("❌ Invalid user ID.")
                return
        
        if not target_user:
            await message.reply_text("❌ User not found.")
            return
        
        success = await self.gban_system.gban_user(
            target_user.id, reason, message.from_user.id
        )
        
        if success:
            await message.reply_text(
                f"✅ {format_user_mention(target_user)} has been globally banned.\n"
                f"Reason: {reason}"
            )
        else:
            await message.reply_text("❌ Failed to global ban user.")
    
    async def _handle_ungban_command(self, message: Message):
        """Handle /ungban command"""
        if not await self.gban_system.is_gban_admin(message.from_user.id):
            await message.reply_text("❌ You don't have permission to remove global bans.")
            return
        
        if message.reply_to_message:
            target_user_id = message.reply_to_message.from_user.id
        else:
            args = message.text.split()[1:]
            if len(args) < 1:
                await message.reply_text("Usage: /ungban <user_id> or reply to a message with /ungban")
                return
            
            try:
                target_user_id = int(args[0])
            except:
                await message.reply_text("❌ Invalid user ID.")
                return
        
        success = await self.gban_system.ungban_user(target_user_id, message.from_user.id)
        
        if success:
            await message.reply_text(f"✅ User {target_user_id} has been removed from global ban list.")
        else:
            await message.reply_text("❌ User is not globally banned or failed to remove ban.")
    
    async def _handle_lock_command(self, message: Message):
        """Handle /lock command"""
        if not await self.role_system.has_permission(message.chat.id, message.from_user.id, 'manage_settings'):
            await message.reply_text("❌ You don't have permission to lock the group.")
            return
        
        self.locked_chats.add(message.chat.id)
        await message.reply_text("🔒 Group locked. Only admins can send messages.")
    
    async def _handle_unlock_command(self, message: Message):
        """Handle /unlock command"""
        if not await self.role_system.has_permission(message.chat.id, message.from_user.id, 'manage_settings'):
            await message.reply_text("❌ You don't have permission to unlock the group.")
            return
        
        self.locked_chats.discard(message.chat.id)
        await message.reply_text("🔓 Group unlocked. All members can send messages.")
    
    async def _handle_promote_command(self, message: Message):
        """Handle /promote command"""
        if not await self.role_system.has_permission(message.chat.id, message.from_user.id, 'promote_users'):
            await message.reply_text("❌ You don't have permission to promote users.")
            return
        
        if not message.reply_to_message:
            await message.reply_text("❌ Reply to a user's message to promote them.")
            return
        
        target_user = message.reply_to_message.from_user
        reason = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "Promoted by admin"
        
        success = await self.role_system.promote_user(
            message.chat.id, target_user.id, message.from_user.id, reason
        )
        
        if success:
            await message.reply_text(f"✅ {format_user_mention(target_user)} has been promoted to trusted member.")
        else:
            await message.reply_text("❌ Failed to promote user.")
    
    async def _handle_demote_command(self, message: Message):
        """Handle /demote command"""
        if not await self.role_system.has_permission(message.chat.id, message.from_user.id, 'promote_users'):
            await message.reply_text("❌ You don't have permission to demote users.")
            return
        
        if not message.reply_to_message:
            await message.reply_text("❌ Reply to a user's message to demote them.")
            return
        
        target_user = message.reply_to_message.from_user
        reason = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "Demoted by admin"
        
        success = await self.role_system.demote_user(
            message.chat.id, target_user.id, message.from_user.id, reason
        )
        
        if success:
            await message.reply_text(f"✅ {format_user_mention(target_user)} has been demoted to regular member.")
        else:
            await message.reply_text("❌ Failed to demote user.")
    
    async def _handle_mute_command(self, message: Message):
        """Handle /mute command"""
        if not await self.role_system.has_permission(message.chat.id, message.from_user.id, 'mute_users'):
            await message.reply_text("❌ You don't have permission to mute users.")
            return
        
        if not message.reply_to_message:
            await message.reply_text("❌ Reply to a user's message to mute them.")
            return
        
        target_user = message.reply_to_message.from_user
        args = message.text.split()[1:]
        
        # Parse duration (default 1 hour)
        duration_hours = 1
        reason = "Muted by admin"
        
        if args:
            try:
                if args[0].endswith('h'):
                    duration_hours = int(args[0][:-1])
                    reason = " ".join(args[1:]) if len(args) > 1 else reason
                elif args[0].endswith('d'):
                    duration_hours = int(args[0][:-1]) * 24
                    reason = " ".join(args[1:]) if len(args) > 1 else reason
                else:
                    reason = " ".join(args)
            except:
                reason = " ".join(args)
        
        success = await self.role_system.mute_user(
            message.chat.id, target_user.id, message.from_user.id, duration_hours, reason
        )
        
        if success:
            await message.reply_text(
                f"🔇 {format_user_mention(target_user)} has been muted for {duration_hours} hours.\n"
                f"Reason: {reason}"
            )
        else:
            await message.reply_text("❌ Failed to mute user.")
    
    async def _handle_unmute_command(self, message: Message):
        """Handle /unmute command"""
        if not await self.role_system.has_permission(message.chat.id, message.from_user.id, 'mute_users'):
            await message.reply_text("❌ You don't have permission to unmute users.")
            return
        
        if not message.reply_to_message:
            await message.reply_text("❌ Reply to a user's message to unmute them.")
            return
        
        target_user = message.reply_to_message.from_user
        
        success = await self.role_system.unmute_user(
            message.chat.id, target_user.id, message.from_user.id
        )
        
        if success:
            await message.reply_text(f"🔊 {format_user_mention(target_user)} has been unmuted.")
        else:
            await message.reply_text("❌ Failed to unmute user or user is not muted.")
    
    async def _handle_setwelcome_command(self, message: Message):
        """Handle /setwelcome command"""
        if not await self.role_system.has_permission(message.chat.id, message.from_user.id, 'manage_settings'):
            await message.reply_text("❌ You don't have permission to set welcome message.")
            return
        
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.reply_text(
                "Usage: /setwelcome <message>\n\n"
                "Variables you can use:\n"
                "{mention} - Mention the user\n"
                "{first_name} - User's first name\n"
                "{chat_title} - Group name\n"
                "{username} - User's username"
            )
            return
        
        welcome_message = args[1]
        config = await self.welcome_system.get_welcome_config(message.chat.id)
        config.message = welcome_message
        
        success = await self.welcome_system.set_welcome_config(message.chat.id, config)
        
        if success:
            await message.reply_text("✅ Welcome message updated!")
        else:
            await message.reply_text("❌ Failed to update welcome message.")
    
    async def _handle_welcome_settings_command(self, message: Message):
        """Handle /welcome command for settings"""
        if not await self.role_system.has_permission(message.chat.id, message.from_user.id, 'manage_settings'):
            await message.reply_text("❌ You don't have permission to manage welcome settings.")
            return
        
        # Show current welcome configuration
        config = await self.welcome_system.get_welcome_config(message.chat.id)
        
        status = "✅ Enabled" if config.enabled else "❌ Disabled"
        verification = "✅ Enabled" if config.verify_users else "❌ Disabled"
        
        settings_text = (
            f"**🎉 Welcome Settings**\n\n"
            f"Status: {status}\n"
            f"Message: {config.message[:100]}...\n"
            f"Verification: {verification}\n"
            f"Captcha Type: {config.captcha_type}\n"
            f"Delete After: {config.delete_after or 'Never'} seconds"
        )
        
        await message.reply_text(settings_text)
    
    async def _delete_after(self, chat_id: int, message_id: int, delay: int):
        """Delete message after delay"""
        await asyncio.sleep(delay)
        try:
            await self.client.delete_messages(chat_id, message_id)
        except:
            pass


def setup_enhanced_handlers(client: Client, db: Database):
    """Setup enhanced handlers with all protection features"""
    return EnhancedHandlers(client, db)