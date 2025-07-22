"""
Admin panel and controls for Telegram Protection Bot
"""

import logging
from typing import Dict, Any
from pyrogram import Client
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
from filters import ContentFilter

logger = logging.getLogger(__name__)


class AdminPanel:
    """Admin panel for bot configuration"""

    def __init__(self, client: Client, db: Database,
                 content_filter: ContentFilter):
        self.client = client
        self.db = db
        self.content_filter = content_filter

    async def show_main_menu(self, message: Message):
        """Show main admin menu"""
        try:
            keyboard = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("🛡️ Security Settings",
                                         callback_data="security_settings"),
                    InlineKeyboardButton("📊 Statistics",
                                         callback_data="statistics")
                ],
                 [
                     InlineKeyboardButton("📋 View Logs",
                                          callback_data="view_logs"),
                     InlineKeyboardButton("🔧 Advanced",
                                          callback_data="advanced_settings")
                 ],
                 [
                     InlineKeyboardButton("📝 Keywords",
                                          callback_data="manage_keywords"),
                     InlineKeyboardButton("👥 Whitelist",
                                          callback_data="manage_whitelist")
                 ],
                 [InlineKeyboardButton("❌ Close",
                                       callback_data="close_menu")]])

            text = """
🛡️ **Admin Panel**

Choose an option to configure the bot:

• **Security Settings**: Toggle protection features
• **Statistics**: View group statistics
• **View Logs**: Check recent moderation actions
• **Advanced**: Configure thresholds and limits
• **Keywords**: Manage banned keywords
• **Whitelist**: Manage whitelisted users
            """

            await message.reply(text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing main menu: {e}")

    async def handle_callback(self, callback_query: CallbackQuery):
        """Handle callback queries from admin panel"""
        try:
            data = callback_query.data

            if data == "security_settings":
                await self.show_security_settings(callback_query)
            elif data == "statistics":
                await self.show_statistics(callback_query)
            elif data == "view_logs":
                await self.show_logs(callback_query)
            elif data == "advanced_settings":
                await self.show_advanced_settings(callback_query)
            elif data == "manage_keywords":
                await self.show_keyword_management(callback_query)
            elif data == "manage_whitelist":
                await self.show_whitelist_management(callback_query)
            elif data == "close_menu":
                await callback_query.message.delete()
            elif data.startswith("toggle_"):
                await self.handle_toggle(callback_query, data)
            elif data.startswith("keyword_"):
                await self.handle_keyword_action(callback_query, data)
            elif data == "back_to_main":
                await self.show_main_menu_edit(callback_query)

            await callback_query.answer()

        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            await callback_query.answer("An error occurred. Please try again.",
                                        show_alert=True)

    async def show_security_settings(self, callback_query: CallbackQuery):
        """Show security settings menu"""
        try:
            chat_id = callback_query.message.chat.id
            settings = await self.db.get_group_settings(chat_id)

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        f"Text Filter: {'✅' if settings.get('text_filter_enabled') else '❌'}",
                        callback_data="toggle_text_filter")
                ],
                [
                    InlineKeyboardButton(
                        f"Edit Monitor: {'✅' if settings.get('edit_monitor_enabled') else '❌'}",
                        callback_data="toggle_edit_monitor")
                ],
                [
                    InlineKeyboardButton(
                        f"Media Filter: {'✅' if settings.get('media_filter_enabled') else '❌'}",
                        callback_data="toggle_media_filter")
                ],
                [
                    InlineKeyboardButton(
                        f"Anti-Flood: {'✅' if settings.get('anti_flood_enabled') else '❌'}",
                        callback_data="toggle_anti_flood")
                ],
                [
                    InlineKeyboardButton(
                        f"Auto Delete: {'✅' if settings.get('auto_delete_enabled') else '❌'}",
                        callback_data="toggle_auto_delete")
                ],
                [
                    InlineKeyboardButton("⬅️ Back",
                                         callback_data="back_to_main")
                ]
            ])

            text = """
🛡️ **Security Settings**

Toggle protection features on/off:

• **Text Filter**: Scan messages for banned keywords
• **Edit Monitor**: Delete edited messages
• **Media Filter**: Scan media files for suspicious content
• **Anti-Flood**: Prevent message flooding
• **Auto Delete**: Automatically delete violations
            """

            await callback_query.message.edit_text(text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing security settings: {e}")

    async def show_statistics(self, callback_query: CallbackQuery):
        """Show group statistics"""
        try:
            chat_id = callback_query.message.chat.id
            logs = await self.db.get_moderation_logs(chat_id, 100)

            # Calculate statistics
            total_actions = len(logs)
            banned_content = len(
                [l for l in logs if l['action'] == 'Banned content detected'])
            spam_detected = len(
                [l for l in logs if l['action'] == 'Spam detected'])
            floods_detected = len(
                [l for l in logs if l['action'] == 'Flood detected'])
            edits_deleted = len(
                [l for l in logs if l['action'] == 'Message edited'])

            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")
            ]])

            text = f"""
📊 **Group Statistics**

**Recent Activity (Last 100 actions):**
• Total Actions: {total_actions}
• Banned Content: {banned_content}
• Spam Detected: {spam_detected}
• Floods Detected: {floods_detected}
• Edits Deleted: {edits_deleted}

**Protection Efficiency:**
• Content Filtered: {banned_content + spam_detected}
• Behavior Violations: {floods_detected + edits_deleted}
            """

            await callback_query.message.edit_text(text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing statistics: {e}")

    async def show_logs(self, callback_query: CallbackQuery):
        """Show recent moderation logs"""
        try:
            chat_id = callback_query.message.chat.id
            logs = await self.db.get_moderation_logs(chat_id, 10)

            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")
            ]])

            if not logs:
                text = "📋 **Recent Logs**\n\nNo moderation actions found."
            else:
                text = "📋 **Recent Logs**\n\n"

                for log in logs:
                    user_name = log.get('user_name', 'Unknown')
                    action = log['action']
                    timestamp = log['timestamp']

                    text += f"• {action}\n"
                    text += f"  User: {user_name}\n"
                    text += f"  Time: {timestamp}\n\n"

                    if len(text) > 3000:  # Telegram message limit
                        text += "... (truncated)\n"
                        break

            await callback_query.message.edit_text(text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing logs: {e}")

    async def show_advanced_settings(self, callback_query: CallbackQuery):
        """Show advanced settings"""
        try:
            chat_id = callback_query.message.chat.id
            settings = await self.db.get_group_settings(chat_id)

            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")
            ]])

            text = f"""
🔧 **Advanced Settings**

**Current Configuration:**
• Max Messages/Minute: {settings.get('max_messages_per_minute', 10)}
• Flood Threshold: {settings.get('flood_threshold', 5)}

**Note:** To modify these values, use the following commands:
• `/set_max_messages <number>` - Set max messages per minute
• `/set_flood_threshold <number>` - Set flood threshold

**AI Integration Status:**
• Image Analysis: 🚧 Coming Soon
• Text Analysis: ✅ Active
• Media Scanning: 🚧 Coming Soon
            """

            await callback_query.message.edit_text(text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing advanced settings: {e}")

    async def show_keyword_management(self, callback_query: CallbackQuery):
        """Show keyword management menu"""
        try:
            categories = self.content_filter.get_keyword_categories()

            keyboard_buttons = []
            for category in categories:
                keyword_count = len(
                    self.content_filter.get_keywords_by_category(category))
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        f"{category.replace('_', ' ').title()} ({keyword_count})",
                        callback_data=f"keyword_view_{category}")
                ])

            keyboard_buttons.append([
                InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")
            ])
            keyboard = InlineKeyboardMarkup(keyboard_buttons)

            text = """
📝 **Keyword Management**

Click on a category to view and manage keywords:

**Categories:**
• Hate Speech
• Violence
• Drugs
• Adult Content
• Hindi Offensive

**Note:** Use `/add_keyword <category> <keyword>` to add new keywords
Use `/remove_keyword <category> <keyword>` to remove keywords
            """

            await callback_query.message.edit_text(text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing keyword management: {e}")

    async def show_whitelist_management(self, callback_query: CallbackQuery):
        """Show whitelist management menu"""
        try:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="back_to_main")
            ]])

            text = """
👥 **Whitelist Management**

**Whitelisted Users:**
Currently, all group admins are automatically whitelisted.

**Commands:**
• `/whitelist @username` - Add user to whitelist
• `/unwhitelist @username` - Remove user from whitelist
• `/whitelist_list` - View all whitelisted users

**Note:** Whitelisted users bypass all content filters but edit monitoring may still apply.
            """

            await callback_query.message.edit_text(text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing whitelist management: {e}")

    async def handle_toggle(self, callback_query: CallbackQuery, data: str):
        """Handle toggle switches"""
        try:
            chat_id = callback_query.message.chat.id
            settings = await self.db.get_group_settings(chat_id)

            setting_map = {
                "toggle_text_filter": "text_filter_enabled",
                "toggle_edit_monitor": "edit_monitor_enabled",
                "toggle_media_filter": "media_filter_enabled",
                "toggle_anti_flood": "anti_flood_enabled",
                "toggle_auto_delete": "auto_delete_enabled"
            }

            if data in setting_map:
                setting_key = setting_map[data]
                current_value = settings.get(setting_key, True)
                settings[setting_key] = not current_value

                await self.db.update_group_settings(chat_id, settings)

                # Refresh the security settings menu
                await self.show_security_settings(callback_query)

        except Exception as e:
            logger.error(f"Error handling toggle: {e}")

    async def handle_keyword_action(self, callback_query: CallbackQuery,
                                    data: str):
        """Handle keyword-related actions"""
        try:
            if data.startswith("keyword_view_"):
                category = data.replace("keyword_view_", "")
                keywords = self.content_filter.get_keywords_by_category(
                    category)

                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back",
                                         callback_data="manage_keywords")
                ]])

                text = f"""
📝 **{category.replace('_', ' ').title()} Keywords**

**Current Keywords:**
{', '.join(keywords) if keywords else 'No keywords in this category'}

**Management:**
• Use `/add_keyword {category} <keyword>` to add
• Use `/remove_keyword {category} <keyword>` to remove
                """

                await callback_query.message.edit_text(text,
                                                       reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error handling keyword action: {e}")

    async def show_main_menu_edit(self, callback_query: CallbackQuery):
        """Show main menu by editing current message"""
        try:
            keyboard = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("🛡️ Security Settings",
                                         callback_data="security_settings"),
                    InlineKeyboardButton("📊 Statistics",
                                         callback_data="statistics")
                ],
                 [
                     InlineKeyboardButton("📋 View Logs",
                                          callback_data="view_logs"),
                     InlineKeyboardButton("🔧 Advanced",
                                          callback_data="advanced_settings")
                 ],
                 [
                     InlineKeyboardButton("📝 Keywords",
                                          callback_data="manage_keywords"),
                     InlineKeyboardButton("👥 Whitelist",
                                          callback_data="manage_whitelist")
                 ],
                 [InlineKeyboardButton("❌ Close",
                                       callback_data="close_menu")]])

            text = """
🛡️ **Admin Panel**

Choose an option to configure the bot:

• **Security Settings**: Toggle protection features
• **Statistics**: View group statistics
• **View Logs**: Check recent moderation actions
• **Advanced**: Configure thresholds and limits
• **Keywords**: Manage banned keywords
• **Whitelist**: Manage whitelisted users
            """

            await callback_query.message.edit_text(text, reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error showing main menu edit: {e}")
