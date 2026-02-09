import logging
import asyncio
import sys
import signal
from telegram.ext import ApplicationBuilder
from config import BOT_TOKEN
from handlers import setup_handlers, send_startup_message
from game import active_games
from mechanics import cleanup_game_buttons

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global application instance for signal handling
application = None

async def cleanup_and_shutdown():
    """Cleanup all active games and shutdown gracefully"""
    global application
    
    logger.info('Shutting down bot...')
    
    # Cleanup all active games
    if active_games:
        logger.info(f'Cleaning up {len(active_games)} active games...')
        for game in list(active_games.values()):
            try:
                await cleanup_game_buttons(application, game)
                await application.bot.send_message(
                    chat_id=game.group_id,
                    text="⚠️ Bot is shutting down. Game ended."
                )
            except Exception as e:
                logger.error(f"Error cleaning up game {game.group_id}: {e}")
    
    logger.info('Shutdown complete')

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    logger.info('Bot shutdown initiated via signal...')
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    global application
    
    logger.info("Starting Werewolf Bot...")
    
    # Build application with timeout settings
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )
    
    # Setup all command and callback handlers
    setup_handlers(application)
    
    logger.info("Bot started successfully! Press Ctrl+C to stop.")
    
    # Start the bot using run_polling (blocking call)
    application.run_polling(
        poll_interval=1.0,
        timeout=10,
        bootstrap_retries=-1,
        drop_pending_updates=False
    )

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()