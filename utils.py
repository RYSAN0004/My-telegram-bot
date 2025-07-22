"""
Utility functions for Telegram Protection Bot
"""

import logging
import asyncio
from typing import Dict, Optional, List
from pyrogram import Client
from pyrogram.types import User, ChatMember
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, ChatAdminRequired

logger = logging.getLogger(__name__)

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    """Check if user is admin in the chat"""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except (UserNotParticipant, ChatAdminRequired):
        return False
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

async def is_owner(client: Client, chat_id: int, user_id: int) -> bool:
    """Check if user is owner of the chat"""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status == ChatMemberStatus.OWNER
    except Exception as e:
        logger.error(f"Error checking owner status: {e}")
        return False

def get_user_info(user: User) -> Dict:
    """Extract user information safely"""
    return {
        'id': user.id,
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'username': user.username or '',
        'is_bot': user.is_bot or False,
        'is_premium': getattr(user, 'is_premium', False)
    }

def format_user_mention(user: User) -> str:
    """Format user mention with fallback"""
    if user.username:
        return f"@{user.username}"
    else:
        name = user.first_name or "Unknown"
        return f"[{name}](tg://user?id={user.id})"

async def get_chat_admins(client: Client, chat_id: int) -> List[int]:
    """Get list of chat admin user IDs"""
    try:
        admins = []
        async for member in client.get_chat_members(chat_id, filter="administrators"):
            admins.append(member.user.id)
        return admins
    except Exception as e:
        logger.error(f"Error getting chat admins: {e}")
        return []

async def safe_delete_message(client: Client, chat_id: int, message_id: int) -> bool:
    """Safely delete a message with error handling"""
    try:
        await client.delete_messages(chat_id, message_id)
        return True
    except Exception as e:
        logger.error(f"Failed to delete message {message_id}: {e}")
        return False

async def safe_restrict_user(client: Client, chat_id: int, user_id: int, 
                            until_date=None, permissions=None) -> bool:
    """Safely restrict a user with error handling"""
    try:
        await client.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            until_date=until_date,
            permissions=permissions
        )
        return True
    except Exception as e:
        logger.error(f"Failed to restrict user {user_id}: {e}")
        return False

async def safe_ban_user(client: Client, chat_id: int, user_id: int, 
                       until_date=None) -> bool:
    """Safely ban a user with error handling"""
    try:
        await client.ban_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            until_date=until_date
        )
        return True
    except Exception as e:
        logger.error(f"Failed to ban user {user_id}: {e}")
        return False

def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable format"""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minutes"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hours"
    else:
        days = seconds // 86400
        return f"{days} days"

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

async def get_bot_permissions(client: Client, chat_id: int) -> Dict:
    """Get bot's permissions in the chat"""
    try:
        me = await client.get_me()
        member = await client.get_chat_member(chat_id, me.id)
        
        permissions = {
            'can_delete_messages': member.can_delete_messages,
            'can_restrict_members': member.can_restrict_members,
            'can_pin_messages': member.can_pin_messages,
            'can_promote_members': member.can_promote_members,
            'can_change_info': member.can_change_info,
            'can_invite_users': member.can_invite_users
        }
        
        return permissions
    except Exception as e:
        logger.error(f"Error getting bot permissions: {e}")
        return {}

def validate_user_input(text: str, min_length: int = 1, max_length: int = 1000) -> bool:
    """Validate user input"""
    if not text or not isinstance(text, str):
        return False
    
    if len(text.strip()) < min_length:
        return False
    
    if len(text) > max_length:
        return False
    
    return True

async def rate_limit_user(user_id: int, action: str, limit: int = 5, 
                         window: int = 60) -> bool:
    """Simple rate limiting (in-memory)"""
    # This is a basic implementation
    # In production, you might want to use Redis or database
    import time
    
    current_time = time.time()
    rate_limit_key = f"{user_id}_{action}"
    
    # This would need proper storage implementation
    # For now, just return False (no rate limiting)
    return False

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    import re
    
    # Remove or replace dangerous characters
    sanitized = re.sub(r'[^\w\-_\.]', '_', filename)
    sanitized = sanitized[:100]  # Limit length
    
    return sanitized

async def check_user_permissions(client: Client, chat_id: int, user_id: int) -> Dict:
    """Check what permissions a user has"""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        
        permissions = {
            'status': member.status,
            'is_admin': member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR],
            'is_owner': member.status == ChatMemberStatus.OWNER,
            'can_send_messages': getattr(member, 'can_send_messages', True),
            'can_send_media': getattr(member, 'can_send_media_messages', True),
            'can_send_polls': getattr(member, 'can_send_polls', True),
            'can_send_other': getattr(member, 'can_send_other_messages', True),
            'can_add_previews': getattr(member, 'can_add_web_page_previews', True),
            'can_change_info': getattr(member, 'can_change_info', False),
            'can_invite_users': getattr(member, 'can_invite_users', False),
            'can_pin_messages': getattr(member, 'can_pin_messages', False)
        }
        
        return permissions
    except Exception as e:
        logger.error(f"Error checking user permissions: {e}")
        return {}

def generate_report_text(group_title: str, violations: List[Dict], 
                        time_period: str = "24 hours") -> str:
    """Generate a formatted report text"""
    report = f"""
🛡️ **Group Protection Report**
Group: {group_title}
Period: Last {time_period}

**Summary:**
Total Violations: {len(violations)}

**Breakdown:**
"""
    
    # Count violations by type
    violation_types = {}
    for violation in violations:
        v_type = violation.get('action', 'Unknown')
        violation_types[v_type] = violation_types.get(v_type, 0) + 1
    
    for v_type, count in violation_types.items():
        report += f"• {v_type}: {count}\n"
    
    report += "\n**Recent Actions:**\n"
    
    # Show recent violations
    for violation in violations[-10:]:  # Last 10
        timestamp = violation.get('timestamp', 'Unknown')
        action = violation.get('action', 'Unknown')
        user_name = violation.get('user_name', 'Unknown')
        
        report += f"• {timestamp} - {action} by {user_name}\n"
    
    return report

async def broadcast_to_admins(client: Client, chat_id: int, message: str):
    """Broadcast message to all admins"""
    try:
        admins = await get_chat_admins(client, chat_id)
        
        for admin_id in admins:
            try:
                await client.send_message(admin_id, message)
                await asyncio.sleep(0.1)  # Small delay to avoid flood
            except Exception as e:
                logger.error(f"Failed to send message to admin {admin_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error broadcasting to admins: {e}")

def escape_markdown(text: str) -> str:
    """Escape markdown characters in text"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

async def log_error(error: Exception, context: str = ""):
    """Log error with context"""
    logger.error(f"Error in {context}: {type(error).__name__}: {error}")
