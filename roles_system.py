"""
Role-Based Permission System for Telegram Protection Bot
Implements Owner, Admin, Trusted, Muted roles with fine-grained permissions
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass
from pyrogram.client import Client
from pyrogram.types import ChatMember
from pyrogram.enums import ChatMemberStatus
from database import Database

logger = logging.getLogger(__name__)

class UserRole(Enum):
    """User role enumeration"""
    OWNER = "owner"
    ADMIN = "admin"
    TRUSTED = "trusted"
    MEMBER = "member"
    MUTED = "muted"
    BANNED = "banned"

@dataclass
class Permission:
    """Permission definition"""
    name: str
    description: str
    default_roles: Set[UserRole]

class RoleSystem:
    """Role-based permission management system"""
    
    def __init__(self, client: Client, db: Database):
        self.client = client
        self.db = db
        
        # Define all available permissions
        self.permissions = {
            # Basic messaging permissions
            'send_messages': Permission(
                'send_messages', 'Send text messages',
                {UserRole.OWNER, UserRole.ADMIN, UserRole.TRUSTED, UserRole.MEMBER}
            ),
            'send_media': Permission(
                'send_media', 'Send photos, videos, documents',
                {UserRole.OWNER, UserRole.ADMIN, UserRole.TRUSTED, UserRole.MEMBER}
            ),
            'send_stickers': Permission(
                'send_stickers', 'Send stickers and GIFs',
                {UserRole.OWNER, UserRole.ADMIN, UserRole.TRUSTED, UserRole.MEMBER}
            ),
            'send_polls': Permission(
                'send_polls', 'Create polls',
                {UserRole.OWNER, UserRole.ADMIN, UserRole.TRUSTED, UserRole.MEMBER}
            ),
            'add_web_previews': Permission(
                'add_web_previews', 'Add web page previews',
                {UserRole.OWNER, UserRole.ADMIN, UserRole.TRUSTED, UserRole.MEMBER}
            ),
            
            # Moderation permissions
            'delete_messages': Permission(
                'delete_messages', 'Delete messages',
                {UserRole.OWNER, UserRole.ADMIN}
            ),
            'ban_users': Permission(
                'ban_users', 'Ban/unban users',
                {UserRole.OWNER, UserRole.ADMIN}
            ),
            'mute_users': Permission(
                'mute_users', 'Mute/unmute users',
                {UserRole.OWNER, UserRole.ADMIN}
            ),
            'warn_users': Permission(
                'warn_users', 'Issue warnings',
                {UserRole.OWNER, UserRole.ADMIN}
            ),
            'promote_users': Permission(
                'promote_users', 'Promote users to trusted',
                {UserRole.OWNER, UserRole.ADMIN}
            ),
            
            # Group management permissions
            'change_info': Permission(
                'change_info', 'Change group info',
                {UserRole.OWNER, UserRole.ADMIN}
            ),
            'invite_users': Permission(
                'invite_users', 'Invite new users',
                {UserRole.OWNER, UserRole.ADMIN, UserRole.TRUSTED}
            ),
            'pin_messages': Permission(
                'pin_messages', 'Pin/unpin messages',
                {UserRole.OWNER, UserRole.ADMIN}
            ),
            
            # Bot administration permissions
            'manage_settings': Permission(
                'manage_settings', 'Manage bot settings',
                {UserRole.OWNER, UserRole.ADMIN}
            ),
            'view_logs': Permission(
                'view_logs', 'View moderation logs',
                {UserRole.OWNER, UserRole.ADMIN}
            ),
            'manage_filters': Permission(
                'manage_filters', 'Manage content filters',
                {UserRole.OWNER, UserRole.ADMIN}
            ),
            'global_ban': Permission(
                'global_ban', 'Issue global bans',
                {UserRole.OWNER}
            ),
            'manage_roles': Permission(
                'manage_roles', 'Manage user roles',
                {UserRole.OWNER}
            )
        }
        
        # User role cache
        self.user_roles: Dict[int, Dict[int, UserRole]] = {}  # chat_id -> user_id -> role
        
        # Initialize database tables
        asyncio.create_task(self._create_role_tables())
    
    async def _create_role_tables(self):
        """Create role system database tables"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS user_roles (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                assigned_by INTEGER,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                reason TEXT,
                PRIMARY KEY (chat_id, user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS role_permissions (
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                permission TEXT NOT NULL,
                granted BOOLEAN DEFAULT TRUE,
                modified_by INTEGER,
                modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, role, permission)
            )
            """
        ]
        
        for table_sql in tables:
            await self.db.connection.execute(table_sql)
        
        await self.db.connection.commit()
    
    async def get_user_role(self, chat_id: int, user_id: int) -> UserRole:
        """Get user's role in a chat"""
        # Check cache first
        if chat_id in self.user_roles and user_id in self.user_roles[chat_id]:
            return self.user_roles[chat_id][user_id]
        
        try:
            # Check database for custom role
            cursor = await self.db.connection.execute(
                "SELECT role, expires_at FROM user_roles WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id)
            )
            row = await cursor.fetchone()
            
            if row:
                role_str, expires_at = row
                
                # Check if role has expired
                if expires_at:
                    if datetime.fromisoformat(expires_at) <= datetime.utcnow():
                        # Role expired, remove it
                        await self.remove_user_role(chat_id, user_id)
                        role = await self._get_telegram_role(chat_id, user_id)
                    else:
                        role = UserRole(role_str)
                else:
                    role = UserRole(role_str)
            else:
                # Get role from Telegram
                role = await self._get_telegram_role(chat_id, user_id)
            
            # Cache the role
            if chat_id not in self.user_roles:
                self.user_roles[chat_id] = {}
            self.user_roles[chat_id][user_id] = role
            
            return role
            
        except Exception as e:
            logger.error(f"Error getting user role: {e}")
            return UserRole.MEMBER
    
    async def _get_telegram_role(self, chat_id: int, user_id: int) -> UserRole:
        """Get user's role based on Telegram chat member status"""
        try:
            member = await self.client.get_chat_member(chat_id, user_id)
            
            if member.status == ChatMemberStatus.OWNER:
                return UserRole.OWNER
            elif member.status == ChatMemberStatus.ADMINISTRATOR:
                return UserRole.ADMIN
            elif member.status == ChatMemberStatus.RESTRICTED:
                return UserRole.MUTED
            elif member.status == ChatMemberStatus.BANNED:
                return UserRole.BANNED
            else:
                return UserRole.MEMBER
                
        except Exception as e:
            logger.error(f"Error getting Telegram role: {e}")
            return UserRole.MEMBER
    
    async def set_user_role(self, chat_id: int, user_id: int, role: UserRole, 
                           assigned_by: int, reason: str = None, 
                           duration_hours: int = None) -> bool:
        """Set user's role in a chat"""
        try:
            expires_at = None
            if duration_hours:
                expires_at = datetime.utcnow() + timedelta(hours=duration_hours)
            
            # Save to database
            await self.db.connection.execute(
                """INSERT OR REPLACE INTO user_roles 
                   (chat_id, user_id, role, assigned_by, assigned_at, expires_at, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (chat_id, user_id, role.value, assigned_by, datetime.utcnow(), expires_at, reason)
            )
            await self.db.connection.commit()
            
            # Update cache
            if chat_id not in self.user_roles:
                self.user_roles[chat_id] = {}
            self.user_roles[chat_id][user_id] = role
            
            # Log the role change
            await self.db.log_moderation_action(
                chat_id, user_id, f"Role changed to {role.value}",
                f"Assigned by {assigned_by}. Reason: {reason or 'No reason'}"
            )
            
            logger.info(f"User {user_id} role set to {role.value} in chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting user role: {e}")
            return False
    
    async def remove_user_role(self, chat_id: int, user_id: int) -> bool:
        """Remove user's custom role (revert to Telegram role)"""
        try:
            # Remove from database
            await self.db.connection.execute(
                "DELETE FROM user_roles WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id)
            )
            await self.db.connection.commit()
            
            # Update cache with Telegram role
            if chat_id in self.user_roles and user_id in self.user_roles[chat_id]:
                del self.user_roles[chat_id][user_id]
            
            logger.info(f"Removed custom role for user {user_id} in chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing user role: {e}")
            return False
    
    async def has_permission(self, chat_id: int, user_id: int, permission: str) -> bool:
        """Check if user has a specific permission"""
        if permission not in self.permissions:
            return False
        
        user_role = await self.get_user_role(chat_id, user_id)
        
        # Check if role has permission by default
        if user_role in self.permissions[permission].default_roles:
            # Check for custom permission overrides
            cursor = await self.db.connection.execute(
                "SELECT granted FROM role_permissions WHERE chat_id = ? AND role = ? AND permission = ?",
                (chat_id, user_role.value, permission)
            )
            row = await cursor.fetchone()
            
            if row:
                return bool(row[0])
            else:
                return True  # Default permission
        
        return False
    
    async def grant_permission(self, chat_id: int, role: UserRole, permission: str, 
                              modified_by: int) -> bool:
        """Grant permission to a role"""
        if permission not in self.permissions:
            return False
        
        try:
            await self.db.connection.execute(
                """INSERT OR REPLACE INTO role_permissions 
                   (chat_id, role, permission, granted, modified_by, modified_at)
                   VALUES (?, ?, ?, TRUE, ?, ?)""",
                (chat_id, role.value, permission, modified_by, datetime.utcnow())
            )
            await self.db.connection.commit()
            
            logger.info(f"Permission {permission} granted to role {role.value} in chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error granting permission: {e}")
            return False
    
    async def revoke_permission(self, chat_id: int, role: UserRole, permission: str, 
                               modified_by: int) -> bool:
        """Revoke permission from a role"""
        if permission not in self.permissions:
            return False
        
        try:
            await self.db.connection.execute(
                """INSERT OR REPLACE INTO role_permissions 
                   (chat_id, role, permission, granted, modified_by, modified_at)
                   VALUES (?, ?, ?, FALSE, ?, ?)""",
                (chat_id, role.value, permission, modified_by, datetime.utcnow())
            )
            await self.db.connection.commit()
            
            logger.info(f"Permission {permission} revoked from role {role.value} in chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error revoking permission: {e}")
            return False
    
    async def get_role_permissions(self, chat_id: int, role: UserRole) -> Dict[str, bool]:
        """Get all permissions for a role"""
        permissions = {}
        
        for perm_name, perm_obj in self.permissions.items():
            # Check default permission
            has_default = role in perm_obj.default_roles
            
            # Check for custom override
            cursor = await self.db.connection.execute(
                "SELECT granted FROM role_permissions WHERE chat_id = ? AND role = ? AND permission = ?",
                (chat_id, role.value, perm_name)
            )
            row = await cursor.fetchone()
            
            if row:
                permissions[perm_name] = bool(row[0])
            else:
                permissions[perm_name] = has_default
        
        return permissions
    
    async def get_users_by_role(self, chat_id: int, role: UserRole) -> List[int]:
        """Get all users with a specific role"""
        try:
            cursor = await self.db.connection.execute(
                "SELECT user_id FROM user_roles WHERE chat_id = ? AND role = ? AND (expires_at IS NULL OR expires_at > ?)",
                (chat_id, role.value, datetime.utcnow())
            )
            rows = await cursor.fetchall()
            
            return [row[0] for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting users by role: {e}")
            return []
    
    async def promote_user(self, chat_id: int, user_id: int, promoted_by: int, 
                          reason: str = None) -> bool:
        """Promote user to trusted role"""
        current_role = await self.get_user_role(chat_id, user_id)
        
        if current_role == UserRole.MEMBER:
            return await self.set_user_role(
                chat_id, user_id, UserRole.TRUSTED, promoted_by, reason
            )
        
        return False
    
    async def demote_user(self, chat_id: int, user_id: int, demoted_by: int, 
                         reason: str = None) -> bool:
        """Demote user to member role"""
        current_role = await self.get_user_role(chat_id, user_id)
        
        if current_role in [UserRole.TRUSTED, UserRole.ADMIN]:
            return await self.set_user_role(
                chat_id, user_id, UserRole.MEMBER, demoted_by, reason
            )
        
        return False
    
    async def mute_user(self, chat_id: int, user_id: int, muted_by: int, 
                       duration_hours: int = None, reason: str = None) -> bool:
        """Mute user (temporary or permanent)"""
        return await self.set_user_role(
            chat_id, user_id, UserRole.MUTED, muted_by, reason, duration_hours
        )
    
    async def unmute_user(self, chat_id: int, user_id: int, unmuted_by: int) -> bool:
        """Unmute user"""
        return await self.remove_user_role(chat_id, user_id)
    
    async def cleanup_expired_roles(self):
        """Clean up expired temporary roles"""
        try:
            # Get expired roles
            cursor = await self.db.connection.execute(
                "SELECT chat_id, user_id FROM user_roles WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (datetime.utcnow(),)
            )
            expired_roles = await cursor.fetchall()
            
            # Remove expired roles
            await self.db.connection.execute(
                "DELETE FROM user_roles WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (datetime.utcnow(),)
            )
            await self.db.connection.commit()
            
            # Update cache
            for chat_id, user_id in expired_roles:
                if chat_id in self.user_roles and user_id in self.user_roles[chat_id]:
                    del self.user_roles[chat_id][user_id]
            
            if expired_roles:
                logger.info(f"Cleaned up {len(expired_roles)} expired roles")
            
        except Exception as e:
            logger.error(f"Error cleaning up expired roles: {e}")
    
    async def get_role_hierarchy(self) -> Dict[UserRole, int]:
        """Get role hierarchy (higher number = more permissions)"""
        return {
            UserRole.BANNED: -1,
            UserRole.MUTED: 0,
            UserRole.MEMBER: 1,
            UserRole.TRUSTED: 2,
            UserRole.ADMIN: 3,
            UserRole.OWNER: 4
        }
    
    async def can_modify_user(self, chat_id: int, modifier_id: int, target_id: int) -> bool:
        """Check if modifier can change target's role/permissions"""
        modifier_role = await self.get_user_role(chat_id, modifier_id)
        target_role = await self.get_user_role(chat_id, target_id)
        
        hierarchy = await self.get_role_hierarchy()
        
        return hierarchy[modifier_role] > hierarchy[target_role]
    
    async def get_user_role_info(self, chat_id: int, user_id: int) -> Dict:
        """Get comprehensive user role information"""
        role = await self.get_user_role(chat_id, user_id)
        permissions = await self.get_role_permissions(chat_id, role)
        
        # Get role expiry info
        cursor = await self.db.connection.execute(
            "SELECT expires_at, assigned_by, reason FROM user_roles WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id)
        )
        row = await cursor.fetchone()
        
        info = {
            'role': role.value,
            'permissions': permissions,
            'is_custom_role': row is not None,
            'expires_at': row[0] if row and row[0] else None,
            'assigned_by': row[1] if row else None,
            'reason': row[2] if row else None
        }
        
        return info