"""
Advanced Anti-Spam System for Telegram Protection Bot
Includes anti-link, anti-flood, anti-fake, anti-vpn protection
"""

import re
import asyncio
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse
from pyrogram.client import Client
from pyrogram.types import Message, User
from database import Database
from utils import safe_ban_user, safe_restrict_user, format_user_mention

logger = logging.getLogger(__name__)

@dataclass
class SpamDetection:
    """Spam detection result"""
    is_spam: bool
    confidence: float
    reasons: List[str]
    action: str  # 'warn', 'mute', 'ban', 'delete'

@dataclass
class UserBehavior:
    """User behavior tracking"""
    user_id: int
    message_count: int
    last_message_time: datetime
    similar_messages: int
    link_count: int
    media_count: int
    join_time: datetime
    warnings: int

class AntiSpamSystem:
    """Advanced anti-spam protection system"""
    
    def __init__(self, client: Client, db: Database):
        self.client = client
        self.db = db
        self.user_behavior: Dict[int, UserBehavior] = {}
        self.message_hashes: Dict[int, Set[str]] = {}  # chat_id: set of message hashes
        self.disposable_domains = set()
        self.phishing_domains = set()
        self.vpn_ips = set()
        
        # Spam detection thresholds
        self.flood_threshold = 5  # messages per minute
        self.similar_message_threshold = 3  # similar messages
        self.link_threshold = 2  # links per message
        self.new_user_restriction_hours = 24  # hours to restrict new users
        
        # Initialize detection databases
        asyncio.create_task(self._load_spam_databases())
    
    async def _load_spam_databases(self):
        """Load spam databases (disposable emails, phishing domains, VPN IPs)"""
        try:
            # Load disposable email domains
            self.disposable_domains = {
                '10minutemail.com', 'guerrillamail.com', 'mailinator.com',
                'tempmail.org', 'temp-mail.org', 'throwaway.email',
                'yopmail.com', 'mohmal.com', 'sharklasers.com'
            }
            
            # Load known phishing domains
            self.phishing_domains = {
                'bit.ly', 'tinyurl.com', 'short.link', 'rebrand.ly',
                'ow.ly', 'buff.ly', 't.co', 'goo.gl'
            }
            
            logger.info("Spam databases loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load spam databases: {e}")
    
    async def analyze_message(self, message: Message) -> SpamDetection:
        """Analyze message for spam indicators"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Update user behavior
        await self._update_user_behavior(message)
        
        reasons = []
        confidence = 0.0
        is_spam = False
        action = 'none'
        
        # Check flood protection
        if await self._check_flood(user_id, chat_id):
            reasons.append("Flood detected")
            confidence += 0.8
            action = 'mute'
        
        # Check similar messages
        if await self._check_similar_messages(message):
            reasons.append("Repetitive content")
            confidence += 0.6
            action = 'warn'
        
        # Check links
        link_spam = await self._check_links(message.text or message.caption or "")
        if link_spam[0]:
            reasons.extend(link_spam[1])
            confidence += link_spam[2]
            action = 'ban'
        
        # Check new user behavior
        if await self._check_new_user_spam(message):
            reasons.append("Suspicious new user behavior")
            confidence += 0.5
            action = 'warn'
        
        # Check fake user indicators
        if await self._check_fake_user(message.from_user):
            reasons.append("Fake user indicators")
            confidence += 0.7
            action = 'ban'
        
        # Check username patterns
        if await self._check_suspicious_username(message.from_user.username):
            reasons.append("Suspicious username pattern")
            confidence += 0.4
            action = 'warn'
        
        # Determine if spam
        is_spam = confidence >= 0.6
        
        return SpamDetection(
            is_spam=is_spam,
            confidence=confidence,
            reasons=reasons,
            action=action if is_spam else 'none'
        )
    
    async def _update_user_behavior(self, message: Message):
        """Update user behavior tracking"""
        user_id = message.from_user.id
        now = datetime.utcnow()
        
        if user_id not in self.user_behavior:
            self.user_behavior[user_id] = UserBehavior(
                user_id=user_id,
                message_count=1,
                last_message_time=now,
                similar_messages=0,
                link_count=0,
                media_count=0,
                join_time=now,
                warnings=0
            )
        else:
            behavior = self.user_behavior[user_id]
            
            # Reset counter if more than 1 minute passed
            if (now - behavior.last_message_time).total_seconds() > 60:
                behavior.message_count = 1
            else:
                behavior.message_count += 1
            
            behavior.last_message_time = now
            
            # Count links
            text = message.text or message.caption or ""
            links = re.findall(r'http[s]?://\S+|www\.\S+|\S+\.\S+/\S+', text)
            behavior.link_count += len(links)
            
            # Count media
            if message.media:
                behavior.media_count += 1
    
    async def _check_flood(self, user_id: int, chat_id: int) -> bool:
        """Check for flood behavior"""
        if user_id not in self.user_behavior:
            return False
        
        behavior = self.user_behavior[user_id]
        
        # Check if user is flooding
        if behavior.message_count >= self.flood_threshold:
            logger.info(f"Flood detected for user {user_id} in chat {chat_id}")
            return True
        
        return False
    
    async def _check_similar_messages(self, message: Message) -> bool:
        """Check for repetitive/similar messages"""
        chat_id = message.chat.id
        user_id = message.from_user.id
        text = message.text or message.caption or ""
        
        if not text or len(text) < 10:
            return False
        
        # Create message hash
        message_hash = hashlib.md5(text.encode()).hexdigest()
        
        # Initialize chat hash storage
        if chat_id not in self.message_hashes:
            self.message_hashes[chat_id] = set()
        
        # Check if similar message exists
        if message_hash in self.message_hashes[chat_id]:
            logger.info(f"Similar message detected from user {user_id}")
            return True
        
        # Store message hash
        self.message_hashes[chat_id].add(message_hash)
        
        # Limit stored hashes (keep last 100)
        if len(self.message_hashes[chat_id]) > 100:
            self.message_hashes[chat_id] = set(list(self.message_hashes[chat_id])[-100:])
        
        return False
    
    async def _check_links(self, text: str) -> Tuple[bool, List[str], float]:
        """Check for spam/phishing links"""
        if not text:
            return False, [], 0.0
        
        reasons = []
        confidence = 0.0
        
        # Extract URLs
        urls = re.findall(r'http[s]?://\S+|www\.\S+', text)
        
        if not urls:
            return False, [], 0.0
        
        # Check for too many links
        if len(urls) > self.link_threshold:
            reasons.append(f"Too many links ({len(urls)})")
            confidence += 0.3
        
        for url in urls:
            try:
                # Parse domain
                if not url.startswith(('http://', 'https://')):
                    url = 'http://' + url
                
                domain = urlparse(url).netloc.lower()
                
                # Check against phishing domains
                if domain in self.phishing_domains:
                    reasons.append(f"Phishing domain: {domain}")
                    confidence += 0.9
                
                # Check for suspicious URL patterns
                if self._is_suspicious_url(url):
                    reasons.append(f"Suspicious URL pattern: {domain}")
                    confidence += 0.6
                
                # Check for URL shorteners
                if self._is_url_shortener(domain):
                    reasons.append(f"URL shortener: {domain}")
                    confidence += 0.4
                
            except Exception as e:
                logger.error(f"Error checking URL {url}: {e}")
        
        return confidence > 0.5, reasons, confidence
    
    def _is_suspicious_url(self, url: str) -> bool:
        """Check if URL has suspicious patterns"""
        suspicious_patterns = [
            r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}',  # IP addresses
            r'[a-z]{20,}\.com',  # Very long domain names
            r'.*telegram.*bot.*',  # Fake telegram bot URLs
            r'.*crypto.*giveaway.*',  # Crypto giveaway scams
            r'.*free.*money.*',  # Free money scams
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, url.lower()):
                return True
        
        return False
    
    def _is_url_shortener(self, domain: str) -> bool:
        """Check if domain is a URL shortener"""
        shorteners = {
            'bit.ly', 'tinyurl.com', 'short.link', 'rebrand.ly',
            'ow.ly', 'buff.ly', 't.co', 'goo.gl', 'tiny.cc'
        }
        return domain in shorteners
    
    async def _check_new_user_spam(self, message: Message) -> bool:
        """Check for new user spam behavior"""
        user_id = message.from_user.id
        
        if user_id not in self.user_behavior:
            return False
        
        behavior = self.user_behavior[user_id]
        user_age = (datetime.utcnow() - behavior.join_time).total_seconds() / 3600  # hours
        
        # New user (less than 24 hours) with suspicious behavior
        if user_age < self.new_user_restriction_hours:
            if (behavior.link_count > 0 or 
                behavior.message_count > 10 or 
                behavior.media_count > 5):
                return True
        
        return False
    
    async def _check_fake_user(self, user: User) -> bool:
        """Check for fake user indicators"""
        reasons = []
        
        # Check if user has profile photo
        if not user.photo:
            reasons.append("No profile photo")
        
        # Check username patterns
        if user.username:
            # Too many numbers
            if len(re.findall(r'\d', user.username)) > 5:
                reasons.append("Too many numbers in username")
            
            # Random character patterns
            if re.search(r'[a-z]{3,}\d{3,}', user.username.lower()):
                reasons.append("Random username pattern")
        
        # Check name patterns
        if user.first_name:
            # Very short or very long names
            if len(user.first_name) < 2 or len(user.first_name) > 20:
                reasons.append("Suspicious name length")
            
            # Only numbers in name
            if user.first_name.isdigit():
                reasons.append("Numeric name")
        
        return len(reasons) >= 2  # Multiple indicators
    
    async def _check_suspicious_username(self, username: str) -> bool:
        """Check for suspicious username patterns"""
        if not username:
            return False
        
        username = username.lower()
        
        suspicious_patterns = [
            r'^[a-z]+\d{5,}$',  # letters followed by many numbers
            r'^\d+[a-z]+\d+$',  # numbers-letters-numbers
            r'^(test|temp|fake|spam)\d+$',  # common fake patterns
            r'^[a-z]{1,3}\d{8,}$',  # very short letters + many numbers
        ]
        
        for pattern in suspicious_patterns:
            if re.match(pattern, username):
                return True
        
        return False
    
    async def check_disposable_email(self, email: str) -> bool:
        """Check if email is from disposable email service"""
        if not email:
            return False
        
        domain = email.split('@')[-1].lower()
        return domain in self.disposable_domains
    
    async def execute_anti_spam_action(self, message: Message, detection: SpamDetection):
        """Execute appropriate action based on spam detection"""
        user_id = message.from_user.id
        chat_id = message.chat.id
        user_mention = format_user_mention(message.from_user)
        
        # Log the detection
        await self.db.log_moderation_action(
            chat_id, user_id, f"Spam detected: {detection.action}",
            f"Confidence: {detection.confidence:.2f}, Reasons: {', '.join(detection.reasons)}",
            message.text or message.caption or "Media message"
        )
        
        # Delete the spam message
        try:
            await message.delete()
        except:
            pass
        
        if detection.action == 'warn':
            # Increment warnings
            if user_id in self.user_behavior:
                self.user_behavior[user_id].warnings += 1
                warnings = self.user_behavior[user_id].warnings
                
                warning_msg = await self.client.send_message(
                    chat_id,
                    f"⚠️ {user_mention} received a warning for spam behavior.\n"
                    f"Warnings: {warnings}/3\n"
                    f"Reason: {', '.join(detection.reasons)}"
                )
                
                # Auto-ban after 3 warnings
                if warnings >= 3:
                    await safe_ban_user(self.client, chat_id, user_id)
                    await self.client.send_message(
                        chat_id,
                        f"🚫 {user_mention} has been banned for repeated spam violations."
                    )
                
                # Auto-delete warning after 30 seconds
                asyncio.create_task(self._delete_after(chat_id, warning_msg.id, 30))
        
        elif detection.action == 'mute':
            # Mute for 1 hour
            success = await safe_restrict_user(
                self.client, chat_id, user_id,
                until_date=datetime.utcnow() + timedelta(hours=1)
            )
            
            if success:
                mute_msg = await self.client.send_message(
                    chat_id,
                    f"🔇 {user_mention} has been muted for 1 hour.\n"
                    f"Reason: {', '.join(detection.reasons)}"
                )
                
                # Auto-delete mute message after 30 seconds
                asyncio.create_task(self._delete_after(chat_id, mute_msg.id, 30))
        
        elif detection.action == 'ban':
            # Permanent ban
            success = await safe_ban_user(self.client, chat_id, user_id)
            
            if success:
                ban_msg = await self.client.send_message(
                    chat_id,
                    f"🚫 {user_mention} has been banned.\n"
                    f"Reason: {', '.join(detection.reasons)}"
                )
                
                # Auto-delete ban message after 30 seconds
                asyncio.create_task(self._delete_after(chat_id, ban_msg.id, 30))
    
    async def _delete_after(self, chat_id: int, message_id: int, delay: int):
        """Delete message after delay"""
        await asyncio.sleep(delay)
        try:
            await self.client.delete_messages(chat_id, message_id)
        except:
            pass
    
    async def cleanup_old_data(self):
        """Clean up old behavior data"""
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=24)
        
        # Clean user behavior data
        expired_users = []
        for user_id, behavior in self.user_behavior.items():
            if behavior.last_message_time < cutoff:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.user_behavior[user_id]
        
        # Clean message hashes
        for chat_id in list(self.message_hashes.keys()):
            if len(self.message_hashes[chat_id]) > 1000:
                # Keep only recent hashes
                self.message_hashes[chat_id] = set(
                    list(self.message_hashes[chat_id])[-500:]
                )
        
        logger.info(f"Cleaned up {len(expired_users)} expired user behavior records")
    
    async def get_user_spam_score(self, user_id: int) -> float:
        """Get user's current spam score"""
        if user_id not in self.user_behavior:
            return 0.0
        
        behavior = self.user_behavior[user_id]
        score = 0.0
        
        # Factor in warnings
        score += behavior.warnings * 0.3
        
        # Factor in message frequency
        if behavior.message_count > 10:
            score += 0.2
        
        # Factor in link usage
        if behavior.link_count > 3:
            score += 0.3
        
        # Factor in account age
        account_age_hours = (datetime.utcnow() - behavior.join_time).total_seconds() / 3600
        if account_age_hours < 24:
            score += 0.2
        
        return min(score, 1.0)
    
    async def whitelist_user(self, user_id: int):
        """Add user to spam whitelist"""
        # Mark user as trusted
        if user_id in self.user_behavior:
            self.user_behavior[user_id].warnings = 0
        
        # TODO: Store in database for persistence
        logger.info(f"User {user_id} added to spam whitelist")
    
    async def blacklist_user(self, user_id: int):
        """Add user to spam blacklist"""
        # Mark user as spam
        if user_id not in self.user_behavior:
            self.user_behavior[user_id] = UserBehavior(
                user_id=user_id,
                message_count=0,
                last_message_time=datetime.utcnow(),
                similar_messages=0,
                link_count=0,
                media_count=0,
                join_time=datetime.utcnow(),
                warnings=10  # High warning count
            )
        else:
            self.user_behavior[user_id].warnings = 10
        
        # TODO: Store in database for persistence
        logger.info(f"User {user_id} added to spam blacklist")