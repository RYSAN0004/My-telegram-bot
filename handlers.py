"""
Enhanced Message handlers for Telegram Protection Bot
Integrates all advanced security and moderation features
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pyrogram.client import Client
from pyrogram import filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus, MessageMediaType
from database import Database
from filters import ContentFilter
from config import Config
from logger import BotLogger
from admin import AdminPanel
from utils import is_admin, get_user_info, format_user_mention
from captcha import CaptchaSystem
from anti_spam import AntiSpamSystem
from gban_system import GBanSystem
from roles_system import RoleSystem, UserRole
from welcome_system import WelcomeSystem

logger = logging.getLogger(__name__)

def setup_handlers(app: Client, db: Database, bot_logger: BotLogger):
    """Setup all message handlers"""
    config = Config()
    content_filter = ContentFilter(config)
    admin_panel = AdminPanel(app, db, content_filter)
    
    # Dictionary to track message edits
    message_tracker = {}
    
    @app.on_message(filters.group & filters.text & ~filters.bot)
    async def handle_text_message(client: Client, message: Message):
        """Handle text messages in groups"""
        try:
            # Add group and user to database
            await db.add_group(message.chat.id, message.chat.title)
            user_info = get_user_info(message.from_user)
            await db.add_user(
                user_info['id'], 
                user_info['first_name'], 
                user_info['last_name'], 
                user_info['username'],
                await is_admin(client, message.chat.id, user_info['id'])
            )
            
            # Get group settings
            settings = await db.get_group_settings(message.chat.id)
            
            # Check if user is admin (admins bypass filters)
            if await is_admin(client, message.chat.id, message.from_user.id):
                return
            
            # Anti-flood check
            if settings.get('anti_flood_enabled', True):
                if await db.check_flood(message.chat.id, message.from_user.id):
                    await handle_flood_user(client, message, db, bot_logger)
                    return
            
            # Text content filtering
            if settings.get('text_filter_enabled', True):
                is_banned, categories, keywords = content_filter.check_text_content(message.text)
                
                if is_banned:
                    await handle_banned_content(client, message, db, bot_logger, categories, keywords)
                    return
            
            # Spam score check
            spam_score = content_filter.calculate_spam_score(message.text)
            if spam_score > 70:  # High spam score threshold
                await handle_spam_message(client, message, db, bot_logger, spam_score)
                return
            
            # Track message for edit monitoring
            message_tracker[message.id] = {
                'original_text': message.text,
                'user_id': message.from_user.id,
                'chat_id': message.chat.id,
                'timestamp': datetime.utcnow()
            }
            
            # Clean old tracked messages (keep only last 1000)
            if len(message_tracker) > 1000:
                oldest_keys = list(message_tracker.keys())[:100]
                for key in oldest_keys:
                    del message_tracker[key]
            
        except Exception as e:
            logger.error(f"Error handling text message: {e}")
    
    @app.on_edited_message(filters.group & filters.text & ~filters.bot)
    async def handle_edited_message(client: Client, message: Message):
        """Handle edited messages"""
        try:
            settings = await db.get_group_settings(message.chat.id)
            
            # Check if edit monitoring is enabled
            if not settings.get('edit_monitor_enabled', True):
                return
            
            # Check if user is admin
            if await is_admin(client, message.chat.id, message.from_user.id):
                return
            
            # Get original message if tracked
            original_data = message_tracker.get(message.id)
            original_text = original_data['original_text'] if original_data else "Unknown"
            
            # Log the edit
            await bot_logger.log_edit(
                message.chat.id, 
                message.from_user.id, 
                original_text, 
                message.text,
                message.id
            )
            
            # Delete edited message
            try:
                await message.delete()
                
                # Send warning message
                user_mention = format_user_mention(message.from_user)
                warning_msg = await client.send_message(
                    message.chat.id,
                    f"⚠️ {user_mention}, edited messages are not allowed and have been deleted."
                )
                
                # Auto-delete warning after 10 seconds
                await asyncio.sleep(10)
                await warning_msg.delete()
                
            except Exception as e:
                logger.error(f"Failed to delete edited message: {e}")
            
        except Exception as e:
            logger.error(f"Error handling edited message: {e}")
    
    @app.on_message(filters.group & filters.media & ~filters.bot)
    async def handle_media_message(client: Client, message: Message):
        """Handle media messages"""
        try:
            settings = await db.get_group_settings(message.chat.id)
            
            # Check if media filtering is enabled
            if not settings.get('media_filter_enabled', True):
                return
            
            # Check if user is admin
            if await is_admin(client, message.chat.id, message.from_user.id):
                return
            
            # Check filename for suspicious content
            filename = None
            if message.document:
                filename = message.document.file_name
            elif message.video:
                filename = message.video.file_name
            elif message.audio:
                filename = message.audio.file_name
            
            if filename:
                is_suspicious, reasons = content_filter.check_media_filename(filename)
                if is_suspicious:
                    await handle_suspicious_media(client, message, db, bot_logger, reasons)
                    return
            
            # TODO: Add AI-based content detection here
            # This is where you would integrate with image/video analysis APIs
            
        except Exception as e:
            logger.error(f"Error handling media message: {e}")
    
    @app.on_message(filters.command(["start", "help"]))
    async def handle_start_help(client: Client, message: Message):
        """Handle start and help commands"""
        try:
            help_text = """
🛡️ **Telegram Group Protection Bot**

This bot helps protect your group from harmful content and spam.

**Admin Commands:**
/settings - Open admin panel
/status - Check bot status
/logs - View moderation logs
/whitelist - Manage whitelisted users

**Features:**
✅ Text content filtering
✅ Edit message monitoring
✅ Media content scanning
✅ Anti-flood protection
✅ Spam detection
✅ Detailed logging

**Note:** Only group admins can use admin commands.
            """
            
            await message.reply(help_text)
            
        except Exception as e:
            logger.error(f"Error handling start/help command: {e}")
    
    @app.on_message(filters.command("settings"))
    async def handle_settings_command(client: Client, message: Message):
        """Handle settings command"""
        try:
            if not await is_admin(client, message.chat.id, message.from_user.id):
                await message.reply("❌ Only group admins can use this command.")
                return
            
            await admin_panel.show_main_menu(message)
            
        except Exception as e:
            logger.error(f"Error handling settings command: {e}")
    
    @app.on_message(filters.command("status"))
    async def handle_status_command(client: Client, message: Message):
        """Handle status command"""
        try:
            if not await is_admin(client, message.chat.id, message.from_user.id):
                await message.reply("❌ Only group admins can use this command.")
                return
            
            settings = await db.get_group_settings(message.chat.id)
            
            status_text = f"""
🔍 **Bot Status for {message.chat.title}**

**Current Settings:**
• Text Filter: {'✅' if settings.get('text_filter_enabled') else '❌'}
• Edit Monitor: {'✅' if settings.get('edit_monitor_enabled') else '❌'}
• Media Filter: {'✅' if settings.get('media_filter_enabled') else '❌'}
• Anti-Flood: {'✅' if settings.get('anti_flood_enabled') else '❌'}
• Auto Delete: {'✅' if settings.get('auto_delete_enabled') else '❌'}

**Limits:**
• Max Messages/Min: {settings.get('max_messages_per_minute', 10)}
• Flood Threshold: {settings.get('flood_threshold', 5)}

**Bot Info:**
• Status: 🟢 Online
• Version: 1.0.0
• Uptime: Running
            """
            
            await message.reply(status_text)
            
        except Exception as e:
            logger.error(f"Error handling status command: {e}")
    
    @app.on_message(filters.command("logs"))
    async def handle_logs_command(client: Client, message: Message):
        """Handle logs command"""
        try:
            if not await is_admin(client, message.chat.id, message.from_user.id):
                await message.reply("❌ Only group admins can use this command.")
                return
            
            logs = await db.get_moderation_logs(message.chat.id, 20)
            
            if not logs:
                await message.reply("📋 No moderation logs found.")
                return
            
            log_text = "📋 **Recent Moderation Logs:**\n\n"
            
            for log in logs[:10]:  # Show only last 10 logs
                user_name = log.get('user_name', 'Unknown')
                action = log['action']
                reason = log.get('reason', 'No reason')
                timestamp = log['timestamp']
                
                log_text += f"• {action} - {user_name}\n"
                log_text += f"  Reason: {reason}\n"
                log_text += f"  Time: {timestamp}\n\n"
            
            await message.reply(log_text)
            
        except Exception as e:
            logger.error(f"Error handling logs command: {e}")
    
    @app.on_callback_query()
    async def handle_callback_query(client: Client, callback_query: CallbackQuery):
        """Handle callback queries from inline keyboards"""
        try:
            if not await is_admin(client, callback_query.message.chat.id, callback_query.from_user.id):
                await callback_query.answer("❌ Only group admins can use this.", show_alert=True)
                return
            
            await admin_panel.handle_callback(callback_query)
            
        except Exception as e:
            logger.error(f"Error handling callback query: {e}")
    
    async def handle_banned_content(client: Client, message: Message, db: Database, 
                                   bot_logger: BotLogger, categories: list, keywords: list):
        """Handle banned content detection"""
        try:
            # Log the violation
            await bot_logger.log_violation(
                message.chat.id,
                message.from_user.id,
                "Banned content detected",
                f"Categories: {', '.join(categories)}, Keywords: {', '.join(keywords)}",
                message.text,
                message.id
            )
            
            # Delete the message
            await message.delete()
            
            # Send warning
            user_mention = format_user_mention(message.from_user)
            warning_msg = await client.send_message(
                message.chat.id,
                f"⚠️ {user_mention}, your message contained prohibited content and has been deleted.\n"
                f"Reason: {', '.join(categories)}"
            )
            
            # Auto-delete warning after 15 seconds
            await asyncio.sleep(15)
            await warning_msg.delete()
            
        except Exception as e:
            logger.error(f"Error handling banned content: {e}")
    
    async def handle_spam_message(client: Client, message: Message, db: Database, 
                                 bot_logger: BotLogger, spam_score: int):
        """Handle spam message detection"""
        try:
            # Log the spam
            await bot_logger.log_violation(
                message.chat.id,
                message.from_user.id,
                "Spam detected",
                f"Spam score: {spam_score}",
                message.text,
                message.id
            )
            
            # Delete the message
            await message.delete()
            
            # Send warning
            user_mention = format_user_mention(message.from_user)
            warning_msg = await client.send_message(
                message.chat.id,
                f"⚠️ {user_mention}, your message was detected as spam and has been deleted.\n"
                f"Spam score: {spam_score}/100"
            )
            
            # Auto-delete warning after 10 seconds
            await asyncio.sleep(10)
            await warning_msg.delete()
            
        except Exception as e:
            logger.error(f"Error handling spam message: {e}")
    
    async def handle_flood_user(client: Client, message: Message, db: Database, bot_logger: BotLogger):
        """Handle flood detection"""
        try:
            # Log the flood
            await bot_logger.log_violation(
                message.chat.id,
                message.from_user.id,
                "Flood detected",
                "User exceeded message limit",
                message.text,
                message.id
            )
            
            # Delete the message
            await message.delete()
            
            # Restrict user for 5 minutes
            try:
                await client.restrict_chat_member(
                    message.chat.id,
                    message.from_user.id,
                    until_date=datetime.utcnow() + timedelta(minutes=5)
                )
                
                user_mention = format_user_mention(message.from_user)
                warning_msg = await client.send_message(
                    message.chat.id,
                    f"🚫 {user_mention} has been muted for 5 minutes due to flooding."
                )
                
                # Auto-delete warning after 30 seconds
                await asyncio.sleep(30)
                await warning_msg.delete()
                
            except Exception as e:
                logger.error(f"Failed to restrict user: {e}")
            
        except Exception as e:
            logger.error(f"Error handling flood user: {e}")
    
    async def handle_suspicious_media(client: Client, message: Message, db: Database, 
                                     bot_logger: BotLogger, reasons: list):
        """Handle suspicious media detection"""
        try:
            # Log the suspicious media
            await bot_logger.log_violation(
                message.chat.id,
                message.from_user.id,
                "Suspicious media detected",
                f"Reasons: {', '.join(reasons)}",
                f"Media: {message.media}",
                message.id
            )
            
            # Delete the message
            await message.delete()
            
            # Send warning
            user_mention = format_user_mention(message.from_user)
            warning_msg = await client.send_message(
                message.chat.id,
                f"⚠️ {user_mention}, your media file was flagged as suspicious and has been deleted.\n"
                f"Reasons: {', '.join(reasons)}"
            )
            
            # Auto-delete warning after 15 seconds
            await asyncio.sleep(15)
            await warning_msg.delete()
            
        except Exception as e:
            logger.error(f"Error handling suspicious media: {e}")
