"""
Content filtering system for Telegram Protection Bot
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from config import Config

logger = logging.getLogger(__name__)

class ContentFilter:
    """Content filtering and detection system"""
    
    def __init__(self, config: Config):
        self.config = config
        self.keywords = config.get_keywords()
        self.compiled_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Compile keyword patterns for faster matching"""
        patterns = {}
        
        for category, keywords in self.keywords.items():
            patterns[category] = []
            for keyword in keywords:
                # Create pattern for whole word matching
                pattern = re.compile(rf'\b{re.escape(keyword)}\b', re.IGNORECASE | re.UNICODE)
                patterns[category].append(pattern)
        
        return patterns
    
    def check_text_content(self, text: str) -> Tuple[bool, List[str], List[str]]:
        """
        Check text content for banned keywords
        Returns: (is_banned, matched_categories, matched_keywords)
        """
        if not text:
            return False, [], []
        
        matched_categories = []
        matched_keywords = []
        
        # Normalize text
        text = text.strip().lower()
        
        # Check against each category
        for category, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    if category not in matched_categories:
                        matched_categories.append(category)
                    
                    # Extract the actual matched keyword
                    match = pattern.search(text)
                    if match and match.group() not in matched_keywords:
                        matched_keywords.append(match.group())
        
        is_banned = len(matched_categories) > 0
        return is_banned, matched_categories, matched_keywords
    
    def check_suspicious_patterns(self, text: str) -> Tuple[bool, List[str]]:
        """
        Check for suspicious patterns that might indicate harmful content
        Returns: (is_suspicious, reasons)
        """
        if not text:
            return False, []
        
        suspicious_patterns = [
            # Excessive caps
            (r'[A-Z]{10,}', 'Excessive caps'),
            # Repeated characters
            (r'(.)\1{5,}', 'Repeated characters'),
            # Multiple exclamation/question marks
            (r'[!?]{5,}', 'Excessive punctuation'),
            # Potential spam patterns
            (r'(?i)(click|join|visit).{0,20}(link|channel|group)', 'Potential spam'),
            # Suspicious URLs
            (r'(?i)(bit\.ly|tinyurl|t\.co|shortened)', 'Suspicious URL'),
            # Potential scam patterns
            (r'(?i)(free|win|prize|lottery|claim|gift).{0,30}(money|bitcoin|crypto|cash)', 'Potential scam'),
        ]
        
        reasons = []
        for pattern, reason in suspicious_patterns:
            if re.search(pattern, text):
                reasons.append(reason)
        
        return len(reasons) > 0, reasons
    
    def check_media_filename(self, filename: str) -> Tuple[bool, List[str]]:
        """
        Check media filename for suspicious content
        Returns: (is_suspicious, reasons)
        """
        if not filename:
            return False, []
        
        filename = filename.lower()
        suspicious_extensions = [
            '.exe', '.scr', '.bat', '.cmd', '.com', '.pif', '.vbs', '.js',
            '.jar', '.apk', '.deb', '.rpm', '.dmg', '.pkg'
        ]
        
        suspicious_names = [
            'virus', 'malware', 'hack', 'crack', 'keygen', 'patch',
            'trojan', 'backdoor', 'exploit', 'payload'
        ]
        
        reasons = []
        
        # Check extensions
        for ext in suspicious_extensions:
            if filename.endswith(ext):
                reasons.append(f'Suspicious file extension: {ext}')
        
        # Check filename content
        for name in suspicious_names:
            if name in filename:
                reasons.append(f'Suspicious filename content: {name}')
        
        return len(reasons) > 0, reasons
    
    def is_potential_raid_message(self, text: str) -> bool:
        """
        Check if message could be part of a raid attack
        """
        if not text:
            return False
        
        raid_patterns = [
            r'(?i)(raid|spam|flood|attack).{0,20}(this|group|chat)',
            r'(?i)(join|invite).{0,20}(everyone|all|friends)',
            r'(?i)(copy|paste|share).{0,20}(this|message)',
            r'(?i)(spread|forward).{0,20}(message|this)'
        ]
        
        for pattern in raid_patterns:
            if re.search(pattern, text):
                return True
        
        return False
    
    def calculate_spam_score(self, text: str) -> int:
        """
        Calculate spam score for a message (0-100)
        Higher score = more likely to be spam
        """
        if not text:
            return 0
        
        score = 0
        
        # Length checks
        if len(text) > 1000:
            score += 20
        elif len(text) < 3:
            score += 10
        
        # Repetition checks
        words = text.split()
        if len(words) > 5:
            unique_words = len(set(words))
            repetition_ratio = 1 - (unique_words / len(words))
            score += int(repetition_ratio * 30)
        
        # Special character density
        special_chars = re.findall(r'[^\w\s]', text)
        if len(special_chars) > len(text) * 0.3:
            score += 25
        
        # Caps ratio
        caps_ratio = sum(1 for c in text if c.isupper()) / len(text) if text else 0
        if caps_ratio > 0.7:
            score += 20
        
        # Suspicious patterns
        is_suspicious, _ = self.check_suspicious_patterns(text)
        if is_suspicious:
            score += 30
        
        # Potential raid
        if self.is_potential_raid_message(text):
            score += 40
        
        return min(score, 100)
    
    def update_keywords(self, new_keywords: Dict[str, List[str]]):
        """Update keyword list and recompile patterns"""
        self.keywords = new_keywords
        self.compiled_patterns = self._compile_patterns()
        
        # Save to config
        try:
            self.config.save_keywords(new_keywords)
            logger.info("Keywords updated successfully")
        except Exception as e:
            logger.error(f"Failed to save keywords: {e}")
    
    def add_keyword(self, category: str, keyword: str) -> bool:
        """Add a keyword to a category"""
        try:
            if category not in self.keywords:
                self.keywords[category] = []
            
            if keyword.lower() not in [k.lower() for k in self.keywords[category]]:
                self.keywords[category].append(keyword.lower())
                self.update_keywords(self.keywords)
                return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to add keyword: {e}")
            return False
    
    def remove_keyword(self, category: str, keyword: str) -> bool:
        """Remove a keyword from a category"""
        try:
            if category in self.keywords and keyword.lower() in [k.lower() for k in self.keywords[category]]:
                self.keywords[category] = [k for k in self.keywords[category] if k.lower() != keyword.lower()]
                self.update_keywords(self.keywords)
                return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to remove keyword: {e}")
            return False
    
    def get_keyword_categories(self) -> List[str]:
        """Get all keyword categories"""
        return list(self.keywords.keys())
    
    def get_keywords_by_category(self, category: str) -> List[str]:
        """Get keywords for a specific category"""
        return self.keywords.get(category, [])
