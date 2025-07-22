"""
Logging system for Telegram Protection Bot
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from database import Database

logger = logging.getLogger(__name__)

class BotLogger:
    """Centralized logging system for bot activities"""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def log_violation(self, group_id: int, user_id: int, action: str, 
                           reason: str, original_message: str = None, 
                           message_id: int = None):
        """Log a moderation violation"""
        try:
            await self.db.log_moderation_action(
                group_id=group_id,
                user_id=user_id,
                action=action,
                reason=reason,
                original_message=original_message,
                message_id=message_id
            )
            
            logger.info(f"Violation logged: {action} by user {user_id} in group {group_id}")
            
        except Exception as e:
            logger.error(f"Failed to log violation: {e}")
    
    async def log_edit(self, group_id: int, user_id: int, original_message: str,
                      edited_message: str, message_id: int):
        """Log message edit"""
        try:
            await self.db.log_moderation_action(
                group_id=group_id,
                user_id=user_id,
                action="Message edited",
                reason="Edit monitoring",
                original_message=original_message,
                edited_message=edited_message,
                message_id=message_id
            )
            
            logger.info(f"Edit logged: Message {message_id} by user {user_id} in group {group_id}")
            
        except Exception as e:
            logger.error(f"Failed to log edit: {e}")
    
    async def log_admin_action(self, group_id: int, admin_id: int, action: str, 
                              target_user_id: int = None, details: str = None):
        """Log admin actions"""
        try:
            reason = f"Admin action: {details}" if details else "Admin action"
            
            await self.db.log_moderation_action(
                group_id=group_id,
                user_id=target_user_id or admin_id,
                action=action,
                reason=reason
            )
            
            logger.info(f"Admin action logged: {action} by admin {admin_id} in group {group_id}")
            
        except Exception as e:
            logger.error(f"Failed to log admin action: {e}")
    
    async def log_system_event(self, group_id: int, event: str, details: str = None):
        """Log system events"""
        try:
            await self.db.log_moderation_action(
                group_id=group_id,
                user_id=0,  # System user ID
                action=f"System: {event}",
                reason=details or "System event"
            )
            
            logger.info(f"System event logged: {event} in group {group_id}")
            
        except Exception as e:
            logger.error(f"Failed to log system event: {e}")
    
    async def get_violation_summary(self, group_id: int, hours: int = 24) -> Dict:
        """Get violation summary for the last N hours"""
        try:
            logs = await self.db.get_moderation_logs(group_id, 1000)
            
            # Filter logs by time
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            recent_logs = [
                log for log in logs 
                if datetime.fromisoformat(log['timestamp']) > cutoff_time
            ]
            
            # Count violations by type
            violation_counts = {}
            for log in recent_logs:
                action = log['action']
                violation_counts[action] = violation_counts.get(action, 0) + 1
            
            return {
                'total_violations': len(recent_logs),
                'violation_counts': violation_counts,
                'time_period': f"{hours} hours"
            }
            
        except Exception as e:
            logger.error(f"Failed to get violation summary: {e}")
            return {}
    
    async def export_logs(self, group_id: int, days: int = 7) -> str:
        """Export logs to text format for appeals"""
        try:
            logs = await self.db.get_moderation_logs(group_id, 10000)
            
            # Filter logs by time
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            recent_logs = [
                log for log in logs 
                if datetime.fromisoformat(log['timestamp']) > cutoff_time
            ]
            
            # Generate export text
            export_text = f"""
TELEGRAM GROUP MODERATION LOG EXPORT
====================================

Group ID: {group_id}
Export Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
Period: Last {days} days
Total Actions: {len(recent_logs)}

SUMMARY:
--------
"""
            
            # Add summary
            summary = await self.get_violation_summary(group_id, days * 24)
            for action, count in summary.get('violation_counts', {}).items():
                export_text += f"{action}: {count}\n"
            
            export_text += "\nDETAILED LOGS:\n"
            export_text += "-" * 50 + "\n"
            
            # Add detailed logs
            for log in recent_logs:
                export_text += f"\nTimestamp: {log['timestamp']}\n"
                export_text += f"Action: {log['action']}\n"
                export_text += f"User: {log.get('user_name', 'Unknown')} (ID: {log['user_id']})\n"
                export_text += f"Reason: {log.get('reason', 'No reason')}\n"
                
                if log.get('original_message'):
                    export_text += f"Original Message: {log['original_message'][:100]}...\n"
                
                if log.get('edited_message'):
                    export_text += f"Edited Message: {log['edited_message'][:100]}...\n"
                
                export_text += "-" * 30 + "\n"
            
            export_text += f"""

AUTO-MODERATION EVIDENCE:
========================
This log demonstrates active content moderation to prevent harmful content.
All actions were performed automatically by the protection bot.

Bot Features Active:
- Text content filtering
- Edit message monitoring  
- Media content scanning
- Anti-flood protection
- Spam detection

This evidence can be used for Telegram appeals if the group faces false reporting.
            """
            
            return export_text
            
        except Exception as e:
            logger.error(f"Failed to export logs: {e}")
            return f"Error generating log export: {e}"
    
    async def cleanup_old_logs(self, days: int = 30):
        """Clean up old logs (called periodically)"""
        try:
            await self.db.cleanup_old_logs(days)
            logger.info(f"Cleaned up logs older than {days} days")
            
        except Exception as e:
            logger.error(f"Failed to cleanup logs: {e}")
    
    async def get_user_violation_count(self, group_id: int, user_id: int, days: int = 30) -> int:
        """Get violation count for a specific user"""
        try:
            logs = await self.db.get_moderation_logs(group_id, 1000)
            
            # Filter by user and time
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            user_logs = [
                log for log in logs 
                if (log['user_id'] == user_id and 
                    datetime.fromisoformat(log['timestamp']) > cutoff_time)
            ]
            
            return len(user_logs)
            
        except Exception as e:
            logger.error(f"Failed to get user violation count: {e}")
            return 0
    
    async def get_top_violators(self, group_id: int, days: int = 7, limit: int = 10) -> List[Dict]:
        """Get top violators in the group"""
        try:
            logs = await self.db.get_moderation_logs(group_id, 10000)
            
            # Filter by time
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            recent_logs = [
                log for log in logs 
                if datetime.fromisoformat(log['timestamp']) > cutoff_time
            ]
            
            # Count violations by user
            user_violations = {}
            for log in recent_logs:
                user_id = log['user_id']
                if user_id not in user_violations:
                    user_violations[user_id] = {
                        'user_id': user_id,
                        'user_name': log.get('user_name', 'Unknown'),
                        'username': log.get('username'),
                        'violation_count': 0
                    }
                user_violations[user_id]['violation_count'] += 1
            
            # Sort by violation count
            top_violators = sorted(
                user_violations.values(),
                key=lambda x: x['violation_count'],
                reverse=True
            )[:limit]
            
            return top_violators
            
        except Exception as e:
            logger.error(f"Failed to get top violators: {e}")
            return []
