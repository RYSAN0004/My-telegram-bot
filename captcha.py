"""
Advanced Captcha System for Telegram Protection Bot
Supports text, math, button, and voice captcha verification
"""

import random
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pyrogram.client import Client
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    CallbackQuery, ChatMember, ChatPermissions
)
from pyrogram.enums import ChatMemberStatus
from database import Database
from utils import format_user_mention, safe_restrict_user

logger = logging.getLogger(__name__)

class CaptchaSystem:
    """Advanced captcha verification system"""
    
    def __init__(self, client: Client, db: Database):
        self.client = client
        self.db = db
        self.pending_verifications = {}  # user_id: verification_data
        self.captcha_timeout = 300  # 5 minutes
        
    async def generate_text_captcha(self) -> Tuple[str, str]:
        """Generate text-based captcha"""
        words = [
            "PROTECT", "SECURE", "VERIFY", "TELEGRAM", "SAFETY",
            "GUARD", "SHIELD", "DEFEND", "TRUST", "CHECK"
        ]
        word = random.choice(words)
        scrambled = ''.join(random.sample(word, len(word)))
        
        question = f"Unscramble this word: **{scrambled}**"
        answer = word.lower()
        
        return question, answer
    
    async def generate_math_captcha(self) -> Tuple[str, str]:
        """Generate math-based captcha"""
        operations = [
            lambda: (random.randint(1, 20), random.randint(1, 20), '+'),
            lambda: (random.randint(10, 50), random.randint(1, 10), '-'),
            lambda: (random.randint(1, 12), random.randint(1, 12), '*'),
        ]
        
        a, b, op = random.choice(operations)()
        
        if op == '+':
            result = a + b
        elif op == '-':
            result = a - b
        elif op == '*':
            result = a * b
        else:
            result = 0
        
        question = f"Solve: **{a} {op} {b} = ?**"
        answer = str(result)
        
        return question, answer
    
    async def generate_button_captcha(self) -> Tuple[str, str, InlineKeyboardMarkup]:
        """Generate button-based captcha"""
        correct_answer = random.randint(1000, 9999)
        wrong_answers = [random.randint(1000, 9999) for _ in range(5)]
        
        # Ensure no duplicates
        while any(ans == correct_answer for ans in wrong_answers):
            wrong_answers = [random.randint(1000, 9999) for _ in range(5)]
        
        all_answers = wrong_answers + [correct_answer]
        random.shuffle(all_answers)
        
        # Create keyboard
        keyboard = []
        for i in range(0, len(all_answers), 3):
            row = []
            for j in range(i, min(i + 3, len(all_answers))):
                row.append(
                    InlineKeyboardButton(
                        str(all_answers[j]),
                        callback_data=f"captcha_{all_answers[j]}"
                    )
                )
            keyboard.append(row)
        
        question = f"Click the number: **{correct_answer}**"
        answer = str(correct_answer)
        
        return question, answer, InlineKeyboardMarkup(keyboard)
    
    async def start_verification(self, chat_id: int, user_id: int, 
                                captcha_type: str = "button") -> bool:
        """Start captcha verification for a user"""
        try:
            # Restrict user until verification
            success = await safe_restrict_user(
                self.client, chat_id, user_id,
                until_date=datetime.utcnow() + timedelta(minutes=10)
            )
            
            if not success:
                return False
            
            # Generate captcha based on type
            if captcha_type == "text":
                question, answer = await self.generate_text_captcha()
                keyboard = None
            elif captcha_type == "math":
                question, answer = await self.generate_math_captcha()
                keyboard = None
            elif captcha_type == "button":
                question, answer, keyboard = await self.generate_button_captcha()
            else:
                question, answer = await self.generate_math_captcha()
                keyboard = None
            
            # Store verification data
            verification_data = {
                'chat_id': chat_id,
                'user_id': user_id,
                'answer': answer,
                'type': captcha_type,
                'attempts': 0,
                'max_attempts': 3,
                'created_at': datetime.utcnow(),
                'timeout': datetime.utcnow() + timedelta(seconds=self.captcha_timeout)
            }
            
            self.pending_verifications[user_id] = verification_data
            
            # Get user info
            try:
                user = await self.client.get_users(user_id)
                if isinstance(user, list):
                    user = user[0] if user else None
                user_mention = format_user_mention(user) if user else f"User {user_id}"
            except:
                user_mention = f"User {user_id}"
            
            # Send captcha message
            welcome_text = f"""
🛡️ **Welcome Verification Required**

{user_mention}, please complete the verification below to access this group.

{question}

⏰ You have {self.captcha_timeout // 60} minutes to complete this.
❌ Failure to verify will result in removal from the group.
            """
            
            if keyboard:
                captcha_msg = await self.client.send_message(
                    chat_id, welcome_text, reply_markup=keyboard
                )
            else:
                captcha_msg = await self.client.send_message(chat_id, welcome_text)
            
            # Store message ID for cleanup
            verification_data['message_id'] = captcha_msg.id
            
            # Schedule timeout cleanup
            asyncio.create_task(self._handle_timeout(user_id))
            
            logger.info(f"Started {captcha_type} verification for user {user_id} in chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start verification: {e}")
            return False
    
    async def verify_answer(self, user_id: int, provided_answer: str) -> bool:
        """Verify user's captcha answer"""
        if user_id not in self.pending_verifications:
            return False
        
        verification = self.pending_verifications[user_id]
        verification['attempts'] += 1
        
        # Check if answer is correct
        if provided_answer.lower() == verification['answer'].lower():
            await self._complete_verification(user_id, success=True)
            return True
        
        # Check if max attempts reached
        if verification['attempts'] >= verification['max_attempts']:
            await self._complete_verification(user_id, success=False)
            return False
        
        # Send retry message
        remaining_attempts = verification['max_attempts'] - verification['attempts']
        try:
            await self.client.send_message(
                verification['chat_id'],
                f"❌ Incorrect answer. You have {remaining_attempts} attempts remaining."
            )
        except:
            pass
        
        return False
    
    async def handle_callback(self, callback_query: CallbackQuery) -> bool:
        """Handle button captcha callbacks"""
        if not callback_query.data or not callback_query.data.startswith("captcha_"):
            return False
        
        user_id = callback_query.from_user.id
        provided_answer = callback_query.data.replace("captcha_", "")
        
        result = await self.verify_answer(user_id, provided_answer)
        
        if result:
            await callback_query.answer("✅ Verification successful!", show_alert=True)
        else:
            await callback_query.answer("❌ Incorrect answer", show_alert=True)
        
        return True
    
    async def _complete_verification(self, user_id: int, success: bool):
        """Complete verification process"""
        if user_id not in self.pending_verifications:
            return
        
        verification = self.pending_verifications[user_id]
        chat_id = verification['chat_id']
        
        try:
            if success:
                # Unrestrict user - give full permissions
                full_permissions = ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False
                )
                await self.client.restrict_chat_member(
                    chat_id, user_id, permissions=full_permissions
                )
                
                # Send success message
                user = await self.client.get_users(user_id)
                if isinstance(user, list):
                    user = user[0] if user else None
                user_mention = format_user_mention(user) if user else f"User {user_id}"
                
                success_msg = await self.client.send_message(
                    chat_id,
                    f"✅ {user_mention} has been successfully verified and can now participate in the group!"
                )
                
                # Log successful verification
                await self.db.log_moderation_action(
                    chat_id, user_id, "Verification completed", "Captcha solved successfully"
                )
                
                # Auto-delete success message after 30 seconds
                asyncio.create_task(self._delete_message_after(chat_id, success_msg.id, 30))
                
            else:
                # Ban user for failed verification
                await self.client.ban_chat_member(chat_id, user_id)
                
                # Send failure message
                fail_msg = await self.client.send_message(
                    chat_id,
                    f"❌ User failed verification and has been removed from the group."
                )
                
                # Log failed verification
                await self.db.log_moderation_action(
                    chat_id, user_id, "Verification failed", "Failed to solve captcha"
                )
                
                # Auto-delete failure message after 30 seconds
                asyncio.create_task(self._delete_message_after(chat_id, fail_msg.id, 30))
            
            # Clean up captcha message
            if 'message_id' in verification:
                try:
                    await self.client.delete_messages(chat_id, verification['message_id'])
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Error completing verification: {e}")
        
        finally:
            # Remove from pending verifications
            del self.pending_verifications[user_id]
    
    async def _handle_timeout(self, user_id: int):
        """Handle verification timeout"""
        await asyncio.sleep(self.captcha_timeout)
        
        if user_id in self.pending_verifications:
            verification = self.pending_verifications[user_id]
            
            # Check if still within timeout
            if datetime.utcnow() > verification['timeout']:
                await self._complete_verification(user_id, success=False)
    
    async def _delete_message_after(self, chat_id: int, message_id: int, delay: int):
        """Delete message after delay"""
        await asyncio.sleep(delay)
        try:
            await self.client.delete_messages(chat_id, message_id)
        except:
            pass
    
    async def is_pending_verification(self, user_id: int) -> bool:
        """Check if user has pending verification"""
        return user_id in self.pending_verifications
    
    async def cancel_verification(self, user_id: int):
        """Cancel pending verification"""
        if user_id in self.pending_verifications:
            verification = self.pending_verifications[user_id]
            
            # Clean up captcha message
            if 'message_id' in verification:
                try:
                    await self.client.delete_messages(
                        verification['chat_id'], verification['message_id']
                    )
                except:
                    pass
            
            del self.pending_verifications[user_id]
    
    async def get_pending_count(self, chat_id: int) -> int:
        """Get number of pending verifications for a chat"""
        count = 0
        for verification in self.pending_verifications.values():
            if verification['chat_id'] == chat_id:
                count += 1
        return count
    
    async def cleanup_expired(self):
        """Clean up expired verifications"""
        expired_users = []
        now = datetime.utcnow()
        
        for user_id, verification in self.pending_verifications.items():
            if now > verification['timeout']:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            await self._complete_verification(user_id, success=False)