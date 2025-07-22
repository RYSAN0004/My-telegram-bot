"""
Telegram Group Protection Bot - Main Entry Point
Advanced security bot for proactive group moderation
"""

import asyncio
import logging
import os
from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from config import Config
from database import Database
from enhanced_handlers import setup_enhanced_handlers
from logger import BotLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class TelegramProtectionBot:
    def __init__(self):
        self.app = None
        self.db = None
        self.bot_logger = None
        self.config = Config()
        
    async def initialize(self):
        """Initialize bot components"""
        try:
            # Initialize Pyrogram client
            self.app = Client(
                name="protection_bot",
                api_id=self.config.API_ID,
                api_hash=self.config.API_HASH,
                bot_token=self.config.BOT_TOKEN,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Initialize database
            self.db = Database()
            await self.db.initialize()
            
            # Initialize bot logger
            self.bot_logger = BotLogger(self.db)
            
            # Setup enhanced handlers with all protection features
            self.enhanced_handlers = setup_enhanced_handlers(self.app, self.db)
            
            logger.info("Bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
            
    async def start(self):
        """Start the bot"""
        try:
            await self.initialize()
            await self.app.start()
            
            # Get bot info
            me = await self.app.get_me()
            logger.info(f"Bot started: @{me.username}")
            
            # Keep bot running
            await idle()
            
        except Exception as e:
            logger.error(f"Bot startup failed: {e}")
            raise
        finally:
            if self.app:
                await self.app.stop()
            if self.db:
                await self.db.close()

async def main():
    """Main function"""
    bot = TelegramProtectionBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        logger.info("Bot shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
