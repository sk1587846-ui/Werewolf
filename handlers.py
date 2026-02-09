import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.constants import ChatType
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.ext import MessageHandler, filters
import re
import asyncio
import random
from typing import List
from datetime import datetime
from game import active_games, Game, GamePhase, Player, Team, Role
from roles import assign_roles, get_role_action_buttons, get_voting_buttons
from mechanics import (
    start_night_phase, start_day_phase, start_voting_phase,
    process_voting_results, send_role_assignments, player_has_pending_action, kill_player, send_gif_message, end_game
)
from custom_game_handler import (
    custom_game_command,
    handle_customgame_callback,
    cleanup_custom_game,
    custom_game_configs
)

from ranking import (
    ranking_manager, 
    stats_command, 
    leaderboard_command, 
    rank_info_command,
    on_player_investigate,
    get_player_quick_stats
)

logger = logging.getLogger(__name__)

def escape_markdown_v2(text: str) -> str:
    escape_chars = r'_*\[\]()~`>#+-=|{}.!'
    return re.sub(f'([{"".join(re.escape(c) for c in escape_chars)}])', r'\\\1', text)


async def send_startup_message(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Werewolf bot started successfully.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text(
            "🐺 **Werewolf Bot** 🐺\n\n"
            "Add me to a group chat to start playing!\n\n"
            "Commands:\n"
            "• /newgame - Start a new game\n"
            "• /join - Join the current game\n"
            "• /leave - Leave the game\n"
            "• /players - Show players\n"
            "• /startgame - Start the game (min 5 players)\n"
            "• /endgame - End the game (admins only)",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "Werewolf Bot is ready!\nUse /newgame to start a game.",
            parse_mode='Markdown',
        )

async def new_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("This command works only in groups.")
        return
    if chat.id in active_games:
        game = active_games[chat.id]
        game.custom_game = False
        if game.phase != GamePhase.ENDED:
            await update.message.reply_text(
                f"A game is already active (phase: {game.phase.value})."
            )
            return
    
    game = Game(chat.id, chat.title or "Group")
    active_games[chat.id] = game
    logger.info(f"New game created in group {chat.id}")
    
    # Create join button
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Join Game", callback_data="join_game")]
    ])
    
    # Send initial message with button
    message_text = (
        "🐺 **New Werewolf Game Started!** 🐺\n\n"
        "Click the button below to join!\n"
        "Need 5-20 players to start.\n"
    )
    
    sent_message = await update.message.reply_text(
        message_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    
    # Store message ID for updates
    game.lobby_message_id = sent_message.message_id

    player_list_text = "**Players Joined:** 0/20\n_No players yet_"
    player_list_msg = await update.message.reply_text(
        player_list_text,
        parse_mode='Markdown'
    )
    
    # 🆕 Store player list message ID
    game.player_list_message_id = player_list_msg.message_id

    game.timer_start = datetime.now()
    await send_timer_message(context, game, chat.id)
    
    # 🆕 Schedule timer updates every 30 seconds
    for i in range(1, 5):  # 30s, 60s, 90s, 120s
        context.job_queue.run_once(
            update_timer_message,
            when=30 * i,
            data={'chat_id': chat.id},
            name=f"timer_update_{chat.id}_{i}"
        )
    
    # Schedule auto-start after 120 seconds
    context.job_queue.run_once(
        auto_start_game,
        when=120,
        data={'chat_id': chat.id},
        name=f"auto_start_{chat.id}"
    )
    
    logger.info(f"Scheduled auto-start for game {chat.id} in 120 seconds")

async def send_timer_message(context: ContextTypes.DEFAULT_TYPE, game: Game, chat_id: int):
    """Send timer message with join button"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Join Game", callback_data="join_game")]
    ])
    
    elapsed = (datetime.now() - game.timer_start).total_seconds()
    remaining = max(0, 120 - int(elapsed))
    
    minutes = remaining // 60
    seconds = remaining % 60
    
    message_text = (
        f"🐺 **Werewolf Game Lobby** 🐺\n\n"
        f"⏰ Game starts in: **{minutes}:{seconds:02d}**\n\n"
        f"Click below to join!"
    )
    
    sent_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=message_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    
    # Delete previous timer message if exists
    if hasattr(game, 'timer_message_id') and game.timer_message_id:
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=game.timer_message_id
            )
        except Exception as e:
            logger.error(f"Failed to delete old timer message: {e}")
    
    # Store new message ID
    game.timer_message_id = sent_msg.message_id


async def update_timer_message(context: ContextTypes.DEFAULT_TYPE):
    """Update timer message every 30 seconds"""
    job = context.job
    chat_id = job.data['chat_id']
    
    if chat_id not in active_games:
        return  # Game was ended or already started
    
    game = active_games[chat_id]
    
    if game.phase != GamePhase.LOBBY:
        return  # Game already started
    
    # Send new timer message (will auto-delete previous)
    await send_timer_message(context, game, chat_id)

async def auto_start_game(context: ContextTypes.DEFAULT_TYPE):
    """Auto-start game after 120 seconds"""
    job = context.job
    chat_id = job.data['chat_id']
    
    if chat_id not in active_games:
        logger.info(f"Auto-start skipped: game {chat_id} no longer exists")
        return  # Game was ended or already started
    
    game = active_games[chat_id]
    
    if game.phase != GamePhase.LOBBY:
        logger.info(f"Auto-start skipped: game {chat_id} already started (phase: {game.phase.value})")
        return  # Game already started
    
    from config import MIN_PLAYERS
    
    # Check if enough players joined
    if not game.can_start():
        logger.warning(f"Auto-start failed: game {chat_id} has {len(game.players)} players (need {MIN_PLAYERS})")
        
        # Remove all buttons
        if hasattr(game, 'timer_message_id') and game.timer_message_id:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=game.timer_message_id,
                    reply_markup=None
                )
            except Exception as e:
                logger.debug(f"Could not remove timer button: {e}")
        
        if hasattr(game, 'lobby_message_id') and game.lobby_message_id:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=game.lobby_message_id,
                    reply_markup=None
                )
            except Exception as e:
                logger.debug(f"Could not remove lobby button: {e}")
        
        # Send termination message
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ **Game Cancelled**\n\n"
                 f"Only {len(game.players)} player(s) joined.\n"
                 f"Need at least {MIN_PLAYERS} players to start.\n\n"
                 f"Use /newgame to start a new game.",
            parse_mode='Markdown'
        )
        
        # Terminate the game
        # Terminate the game
        del active_games[chat_id]

# Clean up any custom game config
        from custom_game_handler import custom_game_configs
        if chat_id in custom_game_configs:
            del custom_game_configs[chat_id]
            logger.info(f"Cleaned up abandoned custom game config for {chat_id}")

        logger.info(f"Game {chat_id} terminated due to insufficient players")
        return

    # Remove timer button
    if hasattr(game, 'timer_message_id') and game.timer_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=game.timer_message_id,
                reply_markup=None
            )
        except Exception:
            pass
    
    # Remove lobby join button
    if hasattr(game, 'lobby_message_id') and game.lobby_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=game.lobby_message_id,
                reply_markup=None
            )
        except Exception:
            pass
    
    # Start the game automatically
    if not assign_roles(game):
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Failed to assign roles. Game cancelled.",
            parse_mode='Markdown'
        )
        del active_games[chat_id]
        return
    
    game.phase = GamePhase.NIGHT
    game.game_start_time = datetime.now()
    game.start_time = datetime.now()
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ *Auto-starting game with {len(game.players)} players!*\n"
             f"Evil team: {game.evil_team_type.value}",
        parse_mode='Markdown'
    )
    
    await send_role_assignments(context, game)
    await start_night_phase(context, game)
    
    logger.info(f"Game {chat_id} auto-started with {len(game.players)} players")

async def check_gifs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to check which GIF files are available"""
    user = update.effective_user
    chat = update.effective_chat
    
    # Check if user is admin (optional - remove if you want anyone to use this)
    try:
        if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            member = await context.bot.get_chat_member(chat.id, user.id)
            if member.status not in ['creator', 'administrator']:
                await update.message.reply_text("Only admins can check GIF status.")
                return
    except Exception:
        pass
    
    from config import PHASE_GIFS, DEATH_GIFS, ACTION_GIFS, WIN_GIFS, MISC_GIFS
    import os
    
    all_gifs = {
        "Phase GIFs": PHASE_GIFS,
        "Death GIFs": DEATH_GIFS,
        "Action GIFs": ACTION_GIFS,
        "Victory GIFs": WIN_GIFS,
        "Misc GIFs": MISC_GIFS
    }
    
    # ✅ FIXED: Use plain text (no Markdown) to avoid parsing errors
    report = "🎬 GIF STATUS REPORT\n\n"
    
    total_count = 0
    found_count = 0
    
    for category, gif_dict in all_gifs.items():
        report += f"{category}:\n"
        for key, path in gif_dict.items():
            total_count += 1
            if os.path.exists(path):
                size = os.path.getsize(path)
                size_mb = size / (1024 * 1024)
                report += f"✅ {key}: {path} ({size_mb:.2f} MB)\n"
                found_count += 1
            else:
                report += f"❌ {key}: {path} (NOT FOUND)\n"
        report += "\n"
    
    report += f"Summary: {found_count}/{total_count} GIFs found\n"
    
    if found_count < total_count:
        report += f"\n⚠️ Missing {total_count - found_count} GIF files"
    else:
        report += f"\n✅ All GIF files present!"
    
    # ✅ CRITICAL FIX: Send WITHOUT parse_mode
    await update.message.reply_text(report)

async def extend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extend lobby timer by 30 seconds (admin only)"""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("This command works only in groups.")
        return
    
    if chat.id not in active_games:
        await update.message.reply_text("No active game in this group.")
        return
    
    game = active_games[chat.id]
    
    if game.phase != GamePhase.LOBBY:
        await update.message.reply_text("Can only extend time during lobby phase.")
        return
    
    # Check if user is admin
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ['creator', 'administrator']:
            await update.message.reply_text("Only admins can extend the timer.")
            return
    except Exception as e:
        logger.error(f"Failed to check admin status: {e}")
        await update.message.reply_text("Could not verify admin status.")
        return
    
    # Find current auto-start job
    current_jobs = context.job_queue.get_jobs_by_name(f"auto_start_{chat.id}")
    
    if not current_jobs:
        await update.message.reply_text("No active auto-start timer to extend.")
        return
    
    # Get the current job and calculate remaining time
    current_job = current_jobs[0]
    current_time = datetime.now().timestamp()
    
    # Calculate when the job was scheduled to run
    if hasattr(current_job, 'next_t'):
        original_expiry = current_job.next_t.timestamp()
        remaining_time = max(0, original_expiry - current_time)
    else:
        # Fallback if we can't get exact time
        remaining_time = 30
    
    # Remove old job
    for job in current_jobs:
        job.schedule_removal()
    
    # Schedule new job with remaining time + 30 seconds
    new_delay = remaining_time + 30
    context.job_queue.run_once(
        auto_start_game,
        when=new_delay,
        data={'chat_id': chat.id},
        name=f"auto_start_{chat.id}"
    )
    
    # Update timer message to reflect extension
    game.timer_start = datetime.fromtimestamp(current_time - (120 - new_delay))
    await send_timer_message(context, game, chat.id)
    
    await update.message.reply_text(
        f"⏰ Timer extended by 30 seconds!\n"
        f"Game will now start in {int(new_delay)} seconds.",
        parse_mode='Markdown'
    )
    
    logger.info(f"Admin {user.first_name} extended timer for game {chat.id} by 30s (new delay: {new_delay}s)")

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import MAX_PLAYERS

    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("This command works only in groups.")
        return
    if chat.id not in active_games:
        await update.message.reply_text("No active game. Use /newgame to start one.")
        return
    game = active_games[chat.id]
    if game.phase != GamePhase.LOBBY:
        await update.message.reply_text("Game has already started; joining not allowed.")
        return

    try:
        await context.bot.send_message(
            chat_id=user.id,
            text="✅ Bot access verified! You can join the game."
        )
    except Exception as e:
        logger.warning(f"User {user.first_name} hasn't started bot via /join: {e}")
        await update.message.reply_text(
            f"⚠️ {user.mention_markdown_v2()} needs to start the bot first\\!\n\n"
            f"👉 Click here: @{context.bot.username}\n"
            f"Then press START, and try /join again\\.",
            parse_mode='MarkdownV2'
        )
        return

    if game.add_player(user):
        # mention_markdown_v2() already returns escaped text; escape only added text
        extra_text = escape_markdown_v2(f" joined the game!\nPlayers: {len(game.players)}/{MAX_PLAYERS}")
        message = f"{user.mention_markdown_v2()}{extra_text}"
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.info(f"Player {user.first_name} joined game {chat.id}")
        await update_lobby_message(context, game, chat.id)
    else:
        await update.message.reply_text("Failed to join: already in game or full.")

async def leave_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import MAX_PLAYERS
    chat = update.effective_chat
    user = update.effective_user
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("This command works only in groups.")
        return
    if chat.id not in active_games:
        await update.message.reply_text("No active game in this group.")
        return
    game = active_games[chat.id]
    if game.remove_player(user.id):
        await update.message.reply_text(
            f"{user.mention_markdown_v2()} left the game.",
            parse_mode='MarkdownV2'
        )
        logger.info(f"Player {user.first_name} left game {chat.id}")
        
        # Update lobby message
        if game.phase == GamePhase.LOBBY:
            await update_lobby_message(context, game, chat.id)
    else:
        await update.message.reply_text("Could not leave: not in game or game started.")

async def handle_join_button(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Handle join button press"""
    user = query.from_user
    chat = query.message.chat
    
    # Find game
    if chat.id not in active_games:
        await query.answer("No active game in this group.", show_alert=True)
        return
    
    game = active_games[chat.id]
    
    if game.phase != GamePhase.LOBBY:
        await query.answer("Game has already started!", show_alert=True)
        return
    
    # Check if player already joined
    if user.id in game.players:
        await query.answer("You already joined!", show_alert=False)
        return
    
    # VERIFY PLAYER HAS STARTED BOT
    try:
        await context.bot.send_message(
            chat_id=user.id,
            text="✅ Bot access verified! You can join the game."
        )
    except Exception as e:
        logger.warning(f"User {user.first_name} hasn't started bot: {e}")
        
        # Send message in group mentioning the user
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"⚠️ {user.mention_markdown_v2()} needs to start the bot first\\!\n\n"
                     f"👉 Click here: @{context.bot.username}\n"
                     f"Then press START, and try joining again\\.",
                parse_mode='MarkdownV2'
            )
        except Exception as mention_error:
            logger.error(f"Failed to send group mention: {mention_error}")
        
        await query.answer(
            f"⚠️ Please start a chat with @{context.bot.username} first!",
            show_alert=True
        )
        return
    
    # Add player to game
    from config import MAX_PLAYERS
    if len(game.players) >= MAX_PLAYERS:
        await query.answer("Game is full!", show_alert=True)
        return
    
    if game.add_player(user):
        await query.answer("✅ Joined successfully!", show_alert=False)
        logger.info(f"Player {user.first_name} joined game {chat.id} via button")
        
        await update_lobby_message(context, game, chat.id)
    else:
        await query.answer("Failed to join.", show_alert=True)

async def update_lobby_message(context: ContextTypes.DEFAULT_TYPE, game: Game, chat_id: int):
    """Update the lobby message with current player list"""
    from config import MAX_PLAYERS
    from custom_game_handler import custom_game_configs
    
    player_count = len(game.players)
    
    # Check if this is a custom game
    if chat_id in custom_game_configs and custom_game_configs[chat_id].get("locked", False):
        max_players = len(custom_game_configs[chat_id]["roles"])
        game_type_label = "Custom Game"
    else:
        max_players = MAX_PLAYERS
        game_type_label = "Players Joined"
    
    # Build player list
    if player_count == 0:
        player_list = "_No players yet_"
    else:
        player_names = [f"{i}. {p.first_name}" for i, p in enumerate(game.players.values(), 1)]
        player_list = "\n".join(player_names)
    
    message_text = f"**{game_type_label}:** {player_count}/{max_players}\n{player_list}"
    
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Join Game", callback_data="join_game")]
    ])
    
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game.player_list_message_id,
            text=message_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Failed to update lobby message: {e}")

async def players_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in active_games:
        await update.message.reply_text("No active game in this group.")
        return
    game = active_games[chat.id]
    if not game.players:
        await update.message.reply_text("No players have joined yet.")
        return
    lines = []
    for i, player in enumerate(game.players.values(), 1):
        status_emoji = "🟢" if player.is_alive else "⚫"
        lines.append(f"{i}. {status_emoji} {player.mention}")
    await update.message.reply_text(
        "*Players in game:*\n" + "\n".join(lines),
        parse_mode='Markdown'
    )

async def start_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    from config import MIN_PLAYERS
    
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("This command works only in groups.")
        return
    
    if chat.id not in active_games:
        await update.message.reply_text("No active game in this group.")
        return
    
    game = active_games[chat.id]
    
    if game.phase != GamePhase.LOBBY:
        await update.message.reply_text("Game already started.")
        return
    
    if not game.can_start():
        await update.message.reply_text(f"Need at least {MIN_PLAYERS} players to start.")
        return
    
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ['creator', 'administrator']:
            if len(game.players) >= 8:
                await update.message.reply_text("Only admins can start games with 8+ players.")
                return
    except Exception:
        # Ignore membership check failures
        pass

    # Check if this is a custom game
    from custom_game_handler import custom_game_configs

    is_custom = (chat.id in custom_game_configs and 
             custom_game_configs[chat.id].get("locked", False))

    if is_custom:
    # Custom game - use custom role assignment
        from roles import assign_roles_custom
    
        config = custom_game_configs[chat.id]
        required_players = len(config["roles"])
        actual_players = len(game.players)
    
    # Check exact player count for custom games
        if actual_players != required_players:
            await update.message.reply_text(
                f"❌ Custom game requires exactly {required_players} players.\n"
                f"Currently have {actual_players} players."
            )
            return
    
        if not assign_roles_custom(game, config["roles"]):
            await update.message.reply_text("❌ Failed to assign custom roles.")
            return
    
        game.custom_game = True
        logger.info(f"Starting custom game {chat.id} with {len(game.players)} players")
    
        game_type_msg = "🎮 Custom"
        evil_team_msg = f"Evil team: {game.evil_team_type.value}\n🔴 Rankings disabled"
    else:
    # Normal game - use regular role assignment
        if not assign_roles(game):
            await update.message.reply_text("Failed to assign roles.")
            return
    
        game.custom_game = False  # Explicitly set
        logger.info(f"Starting normal game {chat.id} with {len(game.players)} players")
    
        game_type_msg = "🎮 Normal"
        evil_team_msg = f"Evil team: {game.evil_team_type.value}"
    
    game.phase = GamePhase.NIGHT
    game.game_start_time = datetime.now()
    game.start_time = datetime.now()
    
    await update.message.reply_text(
        f"{game_type_msg} game starting with {len(game.players)} players!\n{evil_team_msg}",
        parse_mode='Markdown',
    )
    
    await send_role_assignments(context, game)
    await start_night_phase(context, game)

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show game rules and role information"""
    rules_text = """📜 **Werewolf Game Rules**

**Objective:**
• Villagers: Eliminate all evil players
• Wolves: Achieve parity with villagers
• Fire Team: Burn everyone with ignite
• Serial Killer: Be last one standing
• Neutral Roles: Complete personal objectives

**Game Flow:**
1. 🌙 **Night** - Special roles act
2. ☀️ **Day** - Discuss who seems suspicious
3. 🗳️ **Voting** - Lynch one player

**Key Mechanics:**
• Dead players cannot communicate
• Evil teams coordinate during night
• AFK players get warned then kicked
• Some roles have limited-use abilities

**Role Categories:**
• Type `/roles villager` - Good team roles
• Type `/roles evil` - Wolf/Fire/SK roles
• Type `/roles neutral` - Independent roles

**Tips:**
• Pay attention to voting patterns
• Don't reveal your role publicly early
• Coordinate with confirmed allies
• Watch for behavioral tells"""
    
    await update.message.reply_text(rules_text, parse_mode='Markdown')

async def roles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show role category selection with buttons"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Villager Roles", callback_data="roles_villager")],
        [InlineKeyboardButton("🐺 Evil Roles", callback_data="roles_evil")],
        [InlineKeyboardButton("🎭 Neutral Roles", callback_data="roles_neutral")]
    ])
    
    await update.message.reply_text(
        "📜 **Werewolf Role Information**\n\n"
        "Select a category to view roles:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )



async def handle_roles_callback(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Handle role category button presses"""
    data = query.data
    
    role_categories = {
        'roles_villager': {
            'title': '👥 Villager Team Roles',
            'roles': [
                '👤 **Villager** - No powers except instincts and faith',
                '🔮 **Seer** - Check if player is good/evil',
                '🔮📚 **Apprentice Seer** - Replaces seer when he dies',
                '💊 **Doctor** - Protect one player from death',
                '🛡️ **Bodyguard** - Guard player, die in their place',
                '🏹 **Hunter** - Shoot someone when dying',
                '🧙 **Witch** - One heal, one poison (single use)',
                '🕵️ **Detective** - Learn exact role during day',
                '⛪ **Priest** - Prevent conversions',
                '🌟 **Oracle** - Learn what role someone is NOT',
                '⚔️ **Vigilante** - Kill at night (suicide if wrong)',
                '🏛️ **Mayor** - Vote counts double when revealed',
                '💘 **Cupid** - Bind two lovers (die together)',
                '👁️ **Insomniac** - See who visited you',
                '👥 **Twins** - Know each other are good',
                '🐾 **Stray** - See who visited your target',
                '🦠 **Plague Doctor** - Infect with deadly plague',
                '🤡❓ **Fool** - Appears evil to investigators',
                '😨 **Cursed Villager** - Becomes wolf if attacked'
            ]
        },
        'roles_evil': {
            'title': '🐺 Evil Team Roles',
            'roles': [
                '**🐺 WOLF PACK**',
                '🐺 **Werewolf** - Hunt villagers at night',
                '🐺🌑 **Alpha Wolf** - Can convert victims (20%)',
                '🔮 **Wolf Shaman** - Block player abilities',
                '',
                '**🔥 FIRE TEAM**',
                '🔥 **Arsonist** - Douse then ignite players',
                '⚡ **Blaze bringer** - Douse or block actions',
                '🧪 **Accelerant Expert** - Triple arsonist douses',
                '',
                '**🔪 SERIAL KILLER TEAM**',
                '🔪 **Serial Killer** - Solo killer, 65% counter wolves',
                '🕷️ **Webkeeper** - Protect Serial Killer team'
            ]
        },
        'roles_neutral': {
            'title': '🎭 Neutral Roles',
            'roles': [
                '**✅ CAN WIN:**',
                '🤡 **Jester** - Win by getting lynched',
                '🪓 **Executioner** - Get target lynched',
                '',
                '**❌ CURSED (Cannot Win):**',
                '🪞 **Mirror Phantom** - Copy visitor, cursed to observe',
                '🗝️ **Thief** - Steal abilities, cursed wanderer',
                '',
                '**🎭 OTHER:**',
                '⚰️ **Grave Robber** - Borrow dead player powers',
                '🎭 **Doppelganger** - Copy chosen player when they die'
            ]
        }
    }
    
    if data not in role_categories:
        await query.answer("Invalid category", show_alert=True)
        return
    
    cat_data = role_categories[data]
    message = f"{cat_data['title']}\n\n" + "\n\n".join(cat_data['roles'])
    
    # Add back button
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Categories", callback_data="roles_back")]
    ])
    
    await query.edit_message_text(
        message,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await query.answer()

async def handle_roles_back(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Handle back button to return to category selection"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Villager Roles", callback_data="roles_villager")],
        [InlineKeyboardButton("🐺 Evil Roles", callback_data="roles_evil")],
        [InlineKeyboardButton("🎭 Neutral Roles", callback_data="roles_neutral")]
    ])
    
    await query.edit_message_text(
        "📜 **Werewolf Role Information**\n\n"
        "Select a category to view roles:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    await query.answer()

def get_role_category(role: Role) -> str:
    """Get category name for a role"""
    if role.team == Team.VILLAGER:
        return "villager"
    elif role.team in [Team.WOLF, Team.FIRE] or role == Role.SERIAL_KILLER :
        return "evil"
    else:
        return "neutral"

async def end_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    # 1. Verify the command is in a group chat
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("This command only works in group chats.")
        return

    # 2. Check if the user is an admin
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ['creator', 'administrator']:
            await update.message.reply_text("Only an admin can end the game.")
            return
    except Exception as e:
        logger.error(f"Failed to verify admin status for user {user.id} in chat {chat.id}: {e}")
        await update.message.reply_text("Could not verify your admin status.")
        return

    # 3. Check if a game is active and end it
    if chat.id in active_games:
        game = active_games[chat.id]
    
    # 🆕 CLEANUP ALL BUTTONS FIRST
        from mechanics import cleanup_game_buttons
        await cleanup_game_buttons(context, game)
    
        del active_games[chat.id]
        await cleanup_custom_game(chat.id)

    # FIX: Use correct variable name
        from custom_game_handler import custom_game_configs
        if chat.id in custom_game_configs:
            del custom_game_configs[chat.id]
            logger.info(f"Cleaned up custom game config for game {chat.id}")
        
        await update.message.reply_text("The game has been ended and cleared by an admin.")
        logger.info(f"Game in chat {chat.id} was ended by admin {user.first_name} ({user.id}).")
    else:
        await update.message.reply_text("There is no active game to end.")

# ============================================================================
# SETTINGS SYSTEM - Add after status_command function
# ============================================================================

def format_settings_message(game: Game) -> str:
    """Format settings display message"""
    s = game.settings
    
    difficulty_emoji = {
        'easy': '😊',
        'normal': '😐',
        'hard': '😈'
    }
    
    return f"""⚙️ **Game Settings**

**Time Limits:**
├ Night Phase: {s['night_time']}s ({s['night_time']//60} min)
├ Day Phase: {s['day_time']}s ({s['day_time']//60} min)
└ Voting Phase: {s['voting_time']}s ({s['voting_time']//60} min)

**Gameplay:**
├ Difficulty: {difficulty_emoji.get(s['difficulty'], '😐')} {s['difficulty'].title()}
└ AFK Kick: {'✅ Enabled' if s['afk_kick'] else '❌ Disabled'} ({s['afk_threshold']} strikes)

_Use buttons below to change settings_"""


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configure game settings (admin only)"""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("This command works only in groups.")
        return
    
    if chat.id not in active_games:
        await update.message.reply_text("No active game. Use /newgame first.")
        return
    
    game = active_games[chat.id]
    
    if game.phase != GamePhase.LOBBY:
        await update.message.reply_text("Cannot change settings after game starts.")
        return
    
    # Check if user is admin
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ['creator', 'administrator']:
            await update.message.reply_text("Only admins can change settings.")
            return
    except Exception as e:
        logger.error(f"Failed to check admin status: {e}")
        await update.message.reply_text("Could not verify admin status.")
        return
    
    # Display current settings
    settings_text = format_settings_message(game)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏱️ Night Time", callback_data="setting_night_time"),
         InlineKeyboardButton("☀️ Day Time", callback_data="setting_day_time")],
        [InlineKeyboardButton("🗳️ Voting Time", callback_data="setting_voting_time")],
        [InlineKeyboardButton("🎲 Difficulty", callback_data="setting_difficulty")],
        [InlineKeyboardButton("🚫 AFK Detection", callback_data="setting_afk")],
        [InlineKeyboardButton("✅ Done", callback_data="setting_done")]
    ])
    
    await update.message.reply_text(
        settings_text,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )


async def handle_setting_callback(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Handle settings menu callbacks"""
    data = query.data
    chat = query.message.chat
    user = query.from_user
    
    if chat.id not in active_games:
        await query.answer("No active game.", show_alert=True)
        return
    
    game = active_games[chat.id]
    
    # Verify admin
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ['creator', 'administrator']:
            await query.answer("Only admins can change settings.", show_alert=True)
            return
    except Exception:
        await query.answer("Admin verification failed.", show_alert=True)
        return
    
    # Handle "Done" button
    if data == "setting_done":
        await query.edit_message_text(
            f"✅ Settings saved!\n\n{format_settings_message(game)}",
            parse_mode='Markdown'
        )
        return
    
    # Handle "Back" button
    elif data == "setting_back":
        settings_text = format_settings_message(game)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱️ Night Time", callback_data="setting_night_time"),
             InlineKeyboardButton("☀️ Day Time", callback_data="setting_day_time")],
            [InlineKeyboardButton("🗳️ Voting Time", callback_data="setting_voting_time")],
            [InlineKeyboardButton("🎲 Difficulty", callback_data="setting_difficulty")],
            [InlineKeyboardButton("🚫 AFK Detection", callback_data="setting_afk")],
            [InlineKeyboardButton("✅ Done", callback_data="setting_done")]
        ])
        await query.edit_message_text(settings_text, reply_markup=keyboard, parse_mode='Markdown')
        return
    
    # Handle submenu navigation
    elif data == "setting_night_time":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("1 min", callback_data="set_night_60"),
             InlineKeyboardButton("2 min", callback_data="set_night_120"),
             InlineKeyboardButton("3 min", callback_data="set_night_180")],
            [InlineKeyboardButton("4 min", callback_data="set_night_240"),
             InlineKeyboardButton("5 min", callback_data="set_night_300")],
            [InlineKeyboardButton("⬅️ Back", callback_data="setting_back")]
        ])
        await query.edit_message_text(
            f"⏱️ **Night Phase Duration**\n\nCurrent: {game.settings['night_time']}s\n\nChoose new duration:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    elif data == "setting_day_time":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("30 sec", callback_data="set_day_30"),
             InlineKeyboardButton("1 min", callback_data="set_day_60"),
             InlineKeyboardButton("2 min", callback_data="set_day_120")],
            [InlineKeyboardButton("3 min", callback_data="set_day_180"),
             InlineKeyboardButton("4 min", callback_data="set_day_240"),
             InlineKeyboardButton("5 min", callback_data="set_day_300")],
            [InlineKeyboardButton("⬅️ Back", callback_data="setting_back")]
        ])
        await query.edit_message_text(
            f"☀️ **Day Phase Duration**\n\nCurrent: {game.settings['day_time']}s\n\nChoose new duration:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    elif data == "setting_voting_time":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("30 sec", callback_data="set_voting_30"),
             InlineKeyboardButton("1 min", callback_data="set_voting_60"),
             InlineKeyboardButton("1.5 min", callback_data="set_voting_90")],
            [InlineKeyboardButton("2 min", callback_data="set_voting_120"),
             InlineKeyboardButton("3 min", callback_data="set_voting_180")],
            [InlineKeyboardButton("⬅️ Back", callback_data="setting_back")]
        ])
        await query.edit_message_text(
            f"🗳️ **Voting Phase Duration**\n\nCurrent: {game.settings['voting_time']}s\n\nChoose new duration:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    elif data == "setting_difficulty":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("😊 Easy", callback_data="set_diff_easy")],
            [InlineKeyboardButton("😐 Normal", callback_data="set_diff_normal")],
            [InlineKeyboardButton("😈 Hard", callback_data="set_diff_hard")],
            [InlineKeyboardButton("⬅️ Back", callback_data="setting_back")]
        ])
        
        current_diff = game.settings['difficulty']
        diff_descriptions = {
            'easy': "More villager roles, fewer evil roles, longer timers",
            'normal': "Balanced distribution, standard timers",
            'hard': "More evil roles, shorter timers, chaos!"
        }
        
        await query.edit_message_text(
            f"🎲 **Difficulty Level**\n\n"
            f"Current: **{current_diff.title()}**\n"
            f"_{diff_descriptions.get(current_diff, 'Balanced gameplay')}_\n\n"
            f"**😊 Easy:** {diff_descriptions['easy']}\n"
            f"**😐 Normal:** {diff_descriptions['normal']}\n"
            f"**😈 Hard:** {diff_descriptions['hard']}",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    elif data == "setting_afk":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Enable AFK Kick", callback_data="set_afk_on"),
             InlineKeyboardButton("❌ Disable AFK Kick", callback_data="set_afk_off")],
            [InlineKeyboardButton("2 Strikes", callback_data="set_afk_threshold_2"),
             InlineKeyboardButton("3 Strikes", callback_data="set_afk_threshold_3"),
             InlineKeyboardButton("4 Strikes", callback_data="set_afk_threshold_4")],
            [InlineKeyboardButton("⬅️ Back", callback_data="setting_back")]
        ])
        
        afk_status = "Enabled" if game.settings['afk_kick'] else "Disabled"
        
        await query.edit_message_text(
            f"🚫 **AFK Detection**\n\n"
            f"Status: **{afk_status}**\n"
            f"Threshold: **{game.settings['afk_threshold']} strikes**\n\n"
            f"Players who don't act for consecutive rounds will:\n"
            f"• Get warned at threshold - 1\n"
            f"• Get kicked at threshold\n\n"
            f"_Recommended: 3 strikes for casual games, 2 for competitive_",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    # Handle value changes - Night time
    elif data.startswith("set_night_"):
        try:
            value = int(data.split("_")[2])
            game.settings['night_time'] = value
            await query.answer(f"Night time set to {value}s", show_alert=False)
            
            # Show updated settings with back button
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Settings", callback_data="setting_back")]
            ])
            await query.edit_message_text(
                f"✅ Night time updated to **{value}s** ({value//60} min)\n\n{format_settings_message(game)}",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error setting night time: {e}")
            await query.answer("Failed to update setting", show_alert=True)
    
    # Handle value changes - Day time
    elif data.startswith("set_day_"):
        try:
            value = int(data.split("_")[2])
            game.settings['day_time'] = value
            await query.answer(f"Day time set to {value}s", show_alert=False)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Settings", callback_data="setting_back")]
            ])
            await query.edit_message_text(
                f"✅ Day time updated to **{value}s** ({value//60} min)\n\n{format_settings_message(game)}",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error setting day time: {e}")
            await query.answer("Failed to update setting", show_alert=True)
    
    # Handle value changes - Voting time
    elif data.startswith("set_voting_"):
        try:
            value = int(data.split("_")[2])
            game.settings['voting_time'] = value
            await query.answer(f"Voting time set to {value}s", show_alert=False)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Settings", callback_data="setting_back")]
            ])
            await query.edit_message_text(
                f"✅ Voting time updated to **{value}s** ({value//60} min)\n\n{format_settings_message(game)}",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error setting voting time: {e}")
            await query.answer("Failed to update setting", show_alert=True)
    
    # Handle value changes - Difficulty
    elif data.startswith("set_diff_"):
        try:
            difficulty = data.split("_")[2]
            game.settings['difficulty'] = difficulty
            await query.answer(f"Difficulty set to {difficulty}", show_alert=False)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Settings", callback_data="setting_back")]
            ])
            await query.edit_message_text(
                f"✅ Difficulty updated to **{difficulty.title()}**\n\n{format_settings_message(game)}",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error setting difficulty: {e}")
            await query.answer("Failed to update setting", show_alert=True)
    
    # Handle AFK toggle
    elif data == "set_afk_on":
        game.settings['afk_kick'] = True
        await query.answer("AFK kick enabled", show_alert=False)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to Settings", callback_data="setting_back")]
        ])
        await query.edit_message_text(
            f"✅ AFK kick **enabled**\n\n{format_settings_message(game)}",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    elif data == "set_afk_off":
        game.settings['afk_kick'] = False
        await query.answer("AFK kick disabled", show_alert=False)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back to Settings", callback_data="setting_back")]
        ])
        await query.edit_message_text(
            f"✅ AFK kick **disabled**\n\n{format_settings_message(game)}",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    # Handle AFK threshold changes
    elif data.startswith("set_afk_threshold_"):
        try:
            threshold = int(data.split("_")[3])
            game.settings['afk_threshold'] = threshold
            await query.answer(f"AFK threshold set to {threshold}", show_alert=False)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back to Settings", callback_data="setting_back")]
            ])
            await query.edit_message_text(
                f"✅ AFK threshold updated to **{threshold} strikes**\n\n{format_settings_message(game)}",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error setting AFK threshold: {e}")
            await query.answer("Failed to update setting", show_alert=True)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ REFACTORED: Added phase validation and transition guards
    """
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    parts = data.split('_')
    doused_targets = []

    logger.info(f"📞 CALLBACK DEBUG: Received data: '{data}' from {user.first_name}")
    logger.info(f"📞 CALLBACK DEBUG: Parts after split: {parts}")

    # ============================================================================
    # EARLY ROUTING (no game required)
    # ============================================================================
    if data.startswith("customgame_"):
        await handle_customgame_callback(query, context)
        return

    if data.startswith("roles_"):
        if data == "roles_back":
            await handle_roles_back(query, context)
        else:
            await handle_roles_callback(query, context)
        return

    if data.startswith("setting_") or data.startswith("set_"):
        await handle_setting_callback(query, context)
        return

    if data == "join_game":
        await handle_join_button(query, context)
        return

    # ============================================================================
    # GAME & PLAYER VALIDATION
    # ============================================================================
    game = None
    for g in active_games.values():
        if user.id in g.players:
            game = g
            break
    
    if not game:
        await query.edit_message_text("You are not in a game.")
        return

    player = game.players[user.id]
    
    if not player.is_alive:
        await query.edit_message_text("Dead players cannot perform actions.")
        return

    # ============================================================================
    # ✅ NEW: PHASE TRANSITION GUARD
    # ============================================================================
    if game.is_transitioning():
        await query.edit_message_text(
            "⏳ The game is transitioning between phases. Please wait a moment..."
        )
        logger.info(f"Blocked callback from {user.first_name} during phase transition")
        return

    # ============================================================================
    # ✅ NEW: BUTTON PHASE VALIDATION (prevent stale clicks)
    # ============================================================================
    if hasattr(player, 'last_action_message_id') and player.last_action_message_id:
        # Check if this button is from the current phase
        if query.message and query.message.message_id == player.last_action_message_id:
            if not game.validate_button_phase(player.last_action_message_id):
                await query.edit_message_text(
                    "⏰ This action is no longer available.\n"
                    "The game phase has changed since this button was sent."
                )
                logger.warning(
                    f"Rejected stale button click from {user.first_name} "
                    f"(message {player.last_action_message_id})"
                )
                return

    # ============================================================================
    # EXISTING ACTION ROUTING (unchanged)
    # ============================================================================
    action = parts[0]

    try:
        if action == "wolf" and parts[1] == "hunt":
            await handle_wolf_hunt(query, context, game, player, parts)
        elif action == "arsonist" and parts[1] == "ignite":
            await handle_arsonist_ignite(query, context, game, player, parts)
        elif action == "arsonist" and parts[1] == "douse":
            await handle_arsonist_douse(query, context, game, player, parts)
        elif data == "fire_starter_block_menu":  
            await handle_fire_starter_block_menu(query, context, game, player)
        elif data == "accelerant_expert_use":
            await handle_accelerant_expert_use(query, context, game, player, parts)
        elif data == "accelerant_expert_skip":
            player.has_acted = True
            await query.edit_message_text("You have skipped using your accelerant.")
        elif action == "serial" and parts[1] == "killer" and parts[2] == "kill":
            await handle_serial_killer_kill(query, context, game, player, parts)
        elif data == "serial_killer_skip":
            player.has_acted = True
            await query.edit_message_text("You chose not to kill anyone tonight.")      
        elif data == "fire_starter_ignite":
            await handle_fire_team_ignite(query, context, game, player, "fire_starter")
        elif data == "accelerant_expert_ignite":
            await handle_fire_team_ignite(query, context, game, player, "accelerant_expert")
        elif data.startswith("arsonist_douse_second_"):
            await handle_arsonist_douse_second_choice(query, context, game, player, parts)
        elif data.startswith("arsonist_douse_third_"):
            await handle_arsonist_douse_third_choice(query, context, game, player, parts)
        elif data == "fire_starter_action_choice":
            await handle_fire_starter_action_choice(query, context, game, player)
        elif data == "fire_starter_action_douse":
            await handle_fire_starter_douse_menu(query, context, game, player)
        elif data.startswith("fire_starter_douse_"):
            await handle_fire_starter_douse_choice(query, context, game, player, parts)
        elif data == "fire_starter_skip":
            player.has_acted = True
            await query.edit_message_text("You have skipped your action.")
        elif data.startswith("fire_starter_block_"):
            await handle_fire_starter_block(query, context, game, player, parts)
        elif data == "fire_starter_action_block": 
            await handle_fire_starter_block_menu(query, context, game, player)
        elif data == "fire_starter_block_skip": 
            player.has_acted = True
            await query.edit_message_text("You chose not to block anyone tonight.")
        elif action == "shaman" and parts[1] == "block":
            await handle_shaman_block(query, context, game, player, parts)
        elif action == "seer" and parts[1] == "check":
            await handle_seer_check(query, context, game, player, parts)
        elif action == "doctor" and parts[1] == "heal":
            await handle_doctor_heal(query, context, game, player, parts)
        elif data == "witch_heal_menu":
            await handle_witch_heal_menu(query, context, game, player)
        elif data == "witch_poison_menu":
            await handle_witch_poison_menu(query, context, game, player)
        elif data == "witch_heal_skip":
            player.has_acted = True
            await query.edit_message_text("You chose not to use your heal potion.")
        elif data == "witch_poison_skip":
            player.has_acted = True
            await query.edit_message_text("You chose not to use your poison.")
        elif data.startswith("witch_heal_") and data != "witch_heal_menu":
            await handle_witch_heal_choice(query, context, game, player, parts)
        elif data.startswith("witch_poison_") and data != "witch_poison_menu":
            await handle_witch_poison_choice(query, context, game, player, parts)
        elif data.startswith("grave_robber_borrow_"):
            await handle_grave_robber_borrow(query, context, game, player, parts)
        elif data == "grave_robber_skip_borrow":
            player.has_acted = True
            await query.edit_message_text("You chose not to borrow any role tonight.")
        elif data == "plague_doctor_skip":
            player.has_acted = True
            await query.edit_message_text("You chose not to infect anyone tonight.")
            return
        elif data.startswith("cupid_choose_"):
            await handle_cupid_choose(query, context, game, player, parts)
        elif data.startswith("doppelganger_choose_"):
            await handle_doppelganger_choose(query, context, game, player, parts)
        elif data.startswith("plague_doctor_infect_"):
            parts = data.split("_")
            if len(parts) == 4 and parts[3].isdigit():
                await handle_plague_doctor_infect(query, context, game, player, parts)
            else:
                await query.edit_message_text("Invalid infection selection.")
        elif action == "bodyguard" and parts[1] == "protect":
            await handle_bodyguard_protect(query, context, game, player, parts)
        elif action == "priest" and parts[1] == "bless":
            await handle_priest_bless(query, context, game, player, parts)
        elif action == "vigilante" and parts[1] == "kill":
            await handle_vigilante_kill(query, context, game, player, parts)
        elif action == "vote":
            await handle_vote(query, context, game, player, parts)
        elif action == "detective" and parts[1] == "check":
            await handle_detective_check(query, context, game, player, parts)
        elif action == "detective" and parts[1] == "check" and parts[2] == "skip":
            player.detective_acted_today = True
            await query.edit_message_text("You chose not to investigate anyone today.")
        elif action == "oracle" and parts[1] == "check":
            await handle_oracle_check(query, context, game, player, parts)
        elif action == "hunter" and parts[1] == "shoot":
            await handle_hunter_shoot(query, context, game, player, parts)
        elif data == "doctor_heal_skip":
            player.has_acted = True
            await query.edit_message_text("You chose not to heal anyone tonight.")
        elif data == "bodyguard_protect_skip":
            player.has_acted = True
            await query.edit_message_text("You chose not to guard anyone tonight.")
        elif data == "priest_bless_skip":
            player.has_acted = True
            await query.edit_message_text("You chose not to bless anyone tonight.")
        elif data.startswith("webkeeper_mark_"):
            await handle_webkeeper_mark(query, context, game, player, parts)
        elif data == "webkeeper_skip":
            player.has_acted = True
            await query.edit_message_text("You chose not to mark anyone tonight.")
        elif data.startswith("stray_observe_"):
            await handle_stray_observe(query, context, game, player, parts)
        elif data == "stray_skip":
            player.has_acted = True
            await query.edit_message_text("You chose not to observe anyone tonight.")
        elif data == "reveal_mayor":
            if player.role == Role.MAYOR and not player.is_mayor_revealed:
                player.is_mayor_revealed = True
                await context.bot.send_message(
                    chat_id=game.group_id,
                    text=f"👑 {player.mention} has revealed themselves as the **Mayor**!\nTheir vote now counts **double** in lynching decisions.",
                    parse_mode='Markdown'
                )
                await query.edit_message_text(
                    "👑 You have revealed yourself as Mayor!\nYour vote now counts double."
                )
            else:
                await query.edit_message_text("You cannot reveal mayor status.")
        else:
            await query.edit_message_text(f"Unknown action: {data}")
    except Exception as e:
        logger.error(f"Error handling callback {data}: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text("An error occurred processing your action.")


def has_night_action(player: Player, game: Game) -> bool:
    buttons = get_role_action_buttons(player, game, game.phase)
    return bool(buttons)

def log_insomniac_visit(visitor: Player, target: Player, logger):
    """Log a visit to track for Insomniac and Plague Doctor mechanics"""
    if not target.is_alive:
        return False
    
    # Track who visited the target
    if not hasattr(target, 'night_visits'):
        logger.warning(f"Initializing missing night_visits for {target.first_name}")
        target.night_visits = []
    
    # Track who the visitor visited (NEW)
    if not hasattr(visitor, 'visited_players'):
        logger.warning(f"Initializing missing visited_players for {visitor.first_name}")
        visitor.visited_players = []
    
    if visitor.user_id not in target.night_visits:
        target.night_visits.append(visitor.user_id)
        visitor.visited_players.append(target.user_id)  # NEW
        
        if target.role == Role.INSOMNIAC:
            logger.debug(f"Logged Insomniac visit: {visitor.first_name} -> {target.first_name}")
        
        if getattr(target, 'is_plagued', False):
            logger.debug(f"Logged plague visit: {visitor.first_name} -> plagued {target.first_name}")
        
        return True
    
    return False


async def handle_seer_check(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    if len(parts) < 3:
        await query.edit_message_text("Invalid selection.")
        return
    try:
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target for checking.")
            return
        log_insomniac_visit(player, target_player, logger)        
        await query.edit_message_text(f"🔮 You focus your vision on {target_player.first_name}...\n\nYour vision will come at dawn.")
        player.has_acted = True
        game.night_actions[f"seer_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        logger.info(f"Seer {player.first_name} checked {target_player.first_name} in game {game.group_id}")
    except Exception as e:
        logger.error(f"handle_seer_check error: {e}")
        await query.edit_message_text("An error occurred during checking.")

async def handle_vigilante_kill(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    if len(parts) < 3:
        await query.edit_message_text("Invalid vigilante kill selection.")
        return
    try:
        if parts[2] == "skip":
            game.night_actions.pop(f"vigilante_kill_{player.user_id}", None)
            await query.edit_message_text("You chose to skip the vigilante kill.")
            player.has_acted = True
            return
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target selected.")
            return
        log_insomniac_visit(player, target_player, logger)

        game.night_actions[f"vigilante_kill_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        await query.edit_message_text(f"You chose to kill {target_player.first_name}.")
        player.has_acted = True
        logger.info(f"Vigilante {player.user_id} chose to kill {target_id}")
    except Exception as e:
        logger.error(f"handle_vigilante_kill error: {e}")
        await query.edit_message_text("An error occurred while processing the vigilante kill.")

async def handle_priest_bless(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: list):
    if len(parts) < 3:
        await query.edit_message_text("Invalid blessing selection.")
        return

    try:
        # Verify priest role and alive status
        if player.role != Role.PRIEST or not player.is_alive:
            await query.edit_message_text("You cannot perform this action.")
            return

        target_id = int(parts[2])
        target_player = game.players.get(target_id)

        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target for blessing.")
            return
        log_insomniac_visit(player, target_player, logger)

        # Save blessing action (to be processed in night resolution)
        game.night_actions[f"priest_{player.user_id}"] = {"actor": player.user_id, "target": target_id}

        # Inform priest
        await query.edit_message_text(f"You have chosen to bless {target_player.first_name}.")
        player.has_acted = True

        # Log the action
        logger.info(f"Priest {player.first_name} blessed {target_player.first_name} in game {game.group_id}")
    except Exception as e:
        logger.error(f"Error handling priest bless: {e}")
        await query.edit_message_text("An error occurred processing your blessing.")

async def handle_wolf_hunt(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    if len(parts) < 3:
        await query.edit_message_text("Invalid hunt selection.")
        return
    try:
        if parts[2] == "skip":
            game.night_actions[f"wolf_hunt_{player.user_id}"] = {"actor": player.user_id, "target": None}
            await query.edit_message_text("You skipped the hunt.")
            player.has_acted = True
            await notify_universal_action(context, game, player, "skipped the hunt")
            return
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid hunt target.")
            player.has_acted = True
            return
        log_insomniac_visit(player, target_player, logger)
        game.night_actions[f"wolf_hunt_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        
        from config import ACTION_GIFS
        from mechanics import send_gif_message
        
        await send_gif_message(
            context=context,
            chat_id=player.user_id,
            gif_key="wolf_hunt",
            gif_dict=ACTION_GIFS,
            caption=f"🐺 You have chosen to hunt {target_player.first_name}.",
            parse_mode='Markdown'
        )
        await query.edit_message_text(f"✓ Vision complete for {target_player.first_name}.")
        player.has_acted = True
        await notify_universal_action(context, game, player, "chose to hunt", target_player.first_name)
        logger.info(f"Wolf {player.first_name} chose to hunt {target_player.first_name} in game {game.group_id}")
    except Exception as e:
        logger.error(f"handle_wolf_hunt error: {e}")
        await query.edit_message_text("An error occurred during hunting.")

async def handle_shaman_block(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: list):
    if len(parts) < 3:
        await query.answer("Invalid selection.")
        return

    # Check if player is alive and is a Wolf Shaman
    if not player.is_alive or player.role != Role.WOLF_SHAMAN:
        await query.answer("You are not allowed to perform this action.")
        return

    try:
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        # Check target validity
        if not target_player or not target_player.is_alive:
            await query.answer("Invalid target.")
            return

        log_insomniac_visit(player, target_player, logger)

        # Register block action if not already blocked or blocked by other effects
        game.night_actions[f"shaman_block_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        
        # Mark player as having acted this phase - prevents timeout penalties
        player.has_acted = True

        # Confirm choice to player
        await query.edit_message_text(f"You have chosen to block {target_player.first_name} tonight.")
        await notify_universal_action(context, game, player, "blocked", target_player.first_name)
        # Optionally log action
        logger.info(f"Wolf Shaman {player.first_name} blocks {target_player.first_name} in game {game.group_id}")

    except Exception as e:
        logger.error(f"Error in shaman_block handler: {e}")
        await query.answer("An error occurred processing your selection.")

async def handle_cupid_choose(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    """Handle Cupid choosing lovers"""
    if player.role != Role.CUPID or not player.is_alive:
        await query.edit_message_text("You cannot perform this action.")
        return
    
    # ✅ Remove day_number check - allow choosing anytime on night 1
    # (removed: if game.day_number != 1: ...)
    
    try:
        chosen_id = int(parts[2])
        chosen_player = game.players.get(chosen_id)
        
        if not chosen_player or not chosen_player.is_alive:
            await query.edit_message_text("Invalid choice.")
            return
        
        # Initialize lovers list if needed
        if not hasattr(game, 'lovers_ids'):
            game.lovers_ids = []
        
        # First lover chosen
        if len(game.lovers_ids) == 0:
            game.lovers_ids.append(chosen_id)
            
            # Show buttons for second lover (excluding first)
            remaining = [p for p in game.get_alive_players() 
                        if p.user_id != chosen_id and p.user_id != player.user_id]
            buttons = [
                [InlineKeyboardButton(f"💘 Choose {p.first_name}", callback_data=f"cupid_choose_{p.user_id}")]
                for p in remaining
            ]
            
            await query.edit_message_text(
                f"You chose {chosen_player.first_name} as the first lover.\n"
                f"Now choose the second lover:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        # Second lover chosen
        elif len(game.lovers_ids) == 1:
            if chosen_id == game.lovers_ids[0]:
                await query.edit_message_text("You cannot choose the same person twice.")
                return
            
            game.lovers_ids.append(chosen_id)
            
            # Set lover_id on both players
            lover1 = game.players[game.lovers_ids[0]]
            lover2 = game.players[game.lovers_ids[1]]
            lover1.lover_id = lover2.user_id
            lover2.lover_id = lover1.user_id
            
            # Notify Cupid
            await query.edit_message_text(
                f"💘 You have bound {lover1.first_name} and {lover2.first_name} together.\n"
                f"Their fates are now intertwined."
            )
            player.has_acted = True  # ✅ Mark as acted after BOTH chosen
            
            # Notify the lovers
            try:
                await context.bot.send_message(
                    chat_id=lover1.user_id,
                    text=f"💘 You feel a strange connection to {lover2.mention}.\n"
                         f"Your fates are bound - if one dies, so does the other.",
                    parse_mode='Markdown'
                )
                await context.bot.send_message(
                    chat_id=lover2.user_id,
                    text=f"💘 You feel a strange connection to {lover1.mention}.\n"
                         f"Your fates are bound - if one dies, so does the other.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify lovers: {e}")
            
            logger.info(f"Cupid bound {lover1.first_name} and {lover2.first_name} as lovers")
        
        else:
            # Safety: lovers already chosen
            await query.edit_message_text("Lovers have already been chosen.")
            player.has_acted = True
        
    except Exception as e:
        logger.error(f"handle_cupid_choose error: {e}")
        await query.edit_message_text("An error occurred.")

async def handle_arsonist_douse(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: list):
    if len(parts) < 3:
        await query.edit_message_text("Invalid selection.")
        player.has_acted = True
        return

    try:
        if player.role != Role.ARSONIST or not player.is_alive:
            await query.edit_message_text("You cannot perform this action.")
            return

        target_str = parts[2]
        
        if target_str == "skip":
    # FIXED: Reset douse tracking when skipping
            player.has_acted = True
            player.douse_count_tonight = 0  # ADD THIS
            player.max_douses_tonight = 1   # ADD THIS
            await notify_universal_action(context, game, player, "skipped dousing")
            await query.edit_message_text("You chose not to douse anyone tonight.")
            return

        target_id = int(target_str)
        target_player = game.players.get(target_id)
        log_insomniac_visit(player, target_player, logger)
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target for dousing.")
            return

        if getattr(target_player, 'is_doused', False):
            await query.edit_message_text(f"{target_player.first_name} is already doused.")
            return

        # Record the douse
        player.douse_count_tonight += 1
        douse_key = f"arsonist_douse_{player.user_id}_{player.douse_count_tonight}"
        game.night_actions[douse_key] = {"actor": player.user_id, "target": target_id}
        target_player.is_doused = True
        
        log_insomniac_visit(player, target_player, logger)
        await notify_universal_action(context, game, player, "doused", target_player.first_name)
        logger.info(f"Arsonist {player.first_name} made douse {player.douse_count_tonight}/{player.max_douses_tonight}")

        # Check if more douses are available
        if player.douse_count_tonight < player.max_douses_tonight:
            # Send next douse menu
            await send_next_arsonist_douse_menu(query, context, game, player)
        else:
            # All douses completed
            player.has_acted = True
            if hasattr(player, 'accelerant_boost_next_night'):
                player.accelerant_boost_next_night = False
            
            total_doused = player.douse_count_tonight
            await query.edit_message_text(f"🔥 You have completed all {total_doused} douses tonight!")

    except Exception as e:
        logger.error(f"Error handling arsonist douse: {e}")
        await query.edit_message_text("An error occurred while processing your douse action.")

async def send_next_arsonist_douse_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player):
    """Send the next douse selection menu"""
    
    # Get already doused targets from night actions
    doused_targets = set()
    for i in range(1, player.douse_count_tonight + 1):
        action_key = f"arsonist_douse_{i}"
        if action_key in game.night_actions:
            doused_targets.add(game.night_actions[action_key]["target"])
    
    # Get available targets (alive, not already doused, not self)
    available_targets = [
        p for p in game.get_alive_players() 
        if p.user_id != player.user_id 
        and p.user_id not in doused_targets 
        and not getattr(p, 'is_doused', False)
    ]
    
    if not available_targets:
        player.has_acted = True
        if hasattr(player, 'accelerant_boost_next_night'):
            player.accelerant_boost_next_night = False
        await query.edit_message_text("No more valid targets to douse.")
        return
    
    # Create buttons for next douse
    next_douse_num = player.douse_count_tonight + 1
    buttons = [
        [InlineKeyboardButton(f"🔥 Douse {p.first_name}", callback_data=f"arsonist_douse_{p.user_id}")]
        for p in available_targets
    ]
    buttons.append([InlineKeyboardButton("❌ Skip Remaining", callback_data="arsonist_douse_skip")])
    
    await query.edit_message_text(
        f"🔥 Choose your {next_douse_num}{get_ordinal_suffix(next_douse_num)} douse target:\n"
        f"({player.douse_count_tonight}/{player.max_douses_tonight} completed)",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

def get_ordinal_suffix(num: int) -> str:
    """Get ordinal suffix for numbers (1st, 2nd, 3rd, etc.)"""
    if 10 <= num % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
    return suffix


async def handle_arsonist_ignite(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: list):
    # Validate input (expect ['arsonist', 'ignite'])
    if len(parts) < 2:
        await query.edit_message_text("Invalid ignite command.")
        player.has_acted = True
        return

    try:
        # Verify the player is alive and Arsonist
        if player.role != Role.ARSONIST or not player.is_alive:
            await query.edit_message_text("You cannot perform this action.")
            return

        # Record the ignite action
        game.night_actions[f"arsonist_ignite_{player.user_id}"] = {"actor": player.user_id}

        # Mark the game as ignited to process deaths in night actions
        game.arsonist_ignited = True

        await query.edit_message_text("🔥 You have ignited the fire! All doused players will burn tonight.")
        player.has_acted = True
        logger.info(f"Arsonist {player.first_name} ignited fire in game {game.group_id}")

    except Exception as e:
        logger.error(f"Error handling arsonist ignite: {e}")
        await query.edit_message_text("An error occurred while processing your ignite action.")

async def handle_fire_starter_action_choice(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player):
    buttons = [
        [InlineKeyboardButton("🔥 Douse a player", callback_data="fire_starter_action_douse")],
        [InlineKeyboardButton("⚡ Block a player", callback_data="fire_starter_block_menu")],  # Fixed callback
        [InlineKeyboardButton("❌ Skip", callback_data="fire_starter_skip")]
    ]
    
    await query.edit_message_text(
        "🔥 Choose your night action:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def handle_fire_starter_douse_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player):
    alive_players = [p for p in game.get_alive_players() if p.user_id != player.user_id and not p.is_doused]
    buttons = [
        [InlineKeyboardButton(f"🔥 Douse {p.first_name}", callback_data=f"fire_starter_douse_{p.user_id}")]
        for p in alive_players
    ]
    buttons.append([InlineKeyboardButton("❌ Skip Dousing", callback_data="fire_starter_douse_skip")])
    await query.edit_message_text(
        "Select a player to douse or skip:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def handle_fire_starter_douse_choice(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    logger.info(f"🔥 FIRE STARTER DEBUG: Called with parts: {parts}")
    logger.info(f"🔥 FIRE STARTER DEBUG: Player role: {player.role}, alive: {player.is_alive}")
    
    if len(parts) < 4:
        logger.error(f"❌ FIRE STARTER: Invalid parts length: {len(parts)}")
        await query.edit_message_text("Invalid selection.")
        return

    target_str = parts[3]
    logger.info(f"🔥 FIRE STARTER: Target string: '{target_str}'")
    
    if target_str == "skip":
        game.night_actions.pop(f"fire_starter_douse_{player.user_id}", None)
        player.has_acted = True
        await notify_universal_action(context, game, player, "skipped dousing")
        await query.edit_message_text("You chose not to douse anyone tonight.")
        return

    try:
        target_id = int(target_str)
        logger.info(f"🔥 FIRE STARTER: Target ID: {target_id}")
        target_player = game.players.get(target_id)
        log_insomniac_visit(player, target_player, logger)
        logger.info(f"🔥 FIRE STARTER: Target found: {target_player is not None}")
        
        if not target_player:
            logger.error(f"❌ FIRE STARTER: Player {target_id} not found in game")
            await query.edit_message_text("Player not found.")
            return
        await notify_universal_action(context, game, player, "doused", target_player.first_name)       
        logger.info(f"🔥 FIRE STARTER: Target {target_player.first_name}, alive: {target_player.is_alive}")
        
        if not target_player.is_alive:
            logger.error(f"❌ FIRE STARTER: Target {target_player.first_name} is dead")
            await query.edit_message_text("Cannot target dead player.")
            return
            
        # Initialize is_doused if missing
        if not hasattr(target_player, 'is_doused'):
            logger.warning(f"⚠️ FIRE STARTER: Initializing missing is_doused for {target_player.first_name}")
            target_player.is_doused = False
            
        logger.info(f"🔥 FIRE STARTER: Target is_doused: {target_player.is_doused}")
            
        if target_player.is_doused:
            logger.warning(f"⚠️ FIRE STARTER: {target_player.first_name} already doused")
            await query.edit_message_text("Player is already doused.")
            return

        # Record the action
        game.night_actions[f"fire_starter_douse_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        await query.edit_message_text(f"You have chosen to douse {target_player.first_name}.")
        player.has_acted = True
        
        logger.info(f"✅ FIRE STARTER: Successfully doused {target_player.first_name}")

    except ValueError as e:
        logger.error(f"❌ FIRE STARTER: Cannot convert '{target_str}' to int: {e}")
        await query.edit_message_text("Invalid player ID.")
    except Exception as e:
        logger.error(f"❌ FIRE STARTER: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text("An error occurred processing your douse choice.")

async def handle_fire_starter_block(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: list):
    if len(parts) < 4:  # ✅ Changed from < 3 to < 4
        await query.edit_message_text("Invalid selection.")
        player.has_acted = True
        return

    if not player.is_alive or player.role != Role.BLAZEBRINGER:
        await query.edit_message_text("You cannot perform this action.")
        return

    try:
        target_id = int(parts[3]) 
        target_player = game.players.get(target_id)

        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target.")
            player.has_acted = True
            return

        # Register block action
        game.night_actions[f"fire_starter_block_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        player.has_acted = True

        await query.edit_message_text(f"You have chosen to block {target_player.first_name} tonight.")
        logger.info(f"Fire Starter {player.first_name} blocked {target_player.first_name} in game {game.group_id}")

        log_insomniac_visit(player, target_player, logger)

    except Exception as e:
        logger.error(f"handle_fire_starter_block error: {e}")
        await query.edit_message_text("An error occurred processing your action.")

async def handle_serial_killer_kill(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    if len(parts) < 4:
        await query.edit_message_text("Invalid selection.")
        return

    try:
        target_id = int(parts[3])
        target_player = game.players.get(target_id)
        
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target.")
            return

        log_insomniac_visit(player, target_player, logger)
        
        game.night_actions[f"serial_killer_kill_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        await query.edit_message_text(f"You have chosen to kill {target_player.first_name}.")
        player.has_acted = True
        
        logger.info(f"Serial Killer {player.first_name} chose to kill {target_player.first_name}")
    except Exception as e:
        logger.error(f"handle_serial_killer_kill error: {e}")
        await query.edit_message_text("An error occurred.")

async def handle_fire_team_ignite(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, role_type: str):
    """Handle ignite action from any fire team member"""
    try:
        game.night_actions[f"{role_type}_ignite_{player.user_id}"] = {"actor": player.user_id}
        game.arsonist_ignited = True
        
        await query.edit_message_text("🔥 You have ignited the fire! All doused players will burn tonight.")
        player.has_acted = True
        
        logger.info(f"{role_type} {player.first_name} ignited fire in game {game.group_id}")
    except Exception as e:
        logger.error(f"handle_fire_team_ignite error: {e}")
        await query.edit_message_text("An error occurred.")

async def handle_accelerant_expert_use(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    if getattr(player, "accelerant_used", False):
        await query.edit_message_text("You have already used your accelerant.")
        return

    player.accelerant_used = True
    player.has_acted = True
    
    # Find Arsonist and set boost
    arsonist = None
    for p in game.get_alive_players():
        if p.role == Role.ARSONIST:
            arsonist = p
            break
    
    if arsonist:
        arsonist.accelerant_boost_next_night = True
        arsonist.max_douses_tonight = 1  # Reset until next night
        
    game.night_actions[f"accelerant_expert_used_{player.user_id}"] = {"actor": player.user_id}
    await query.edit_message_text("💨 Accelerant activated! Arsonist can make 3 douses next night.")

async def handle_arsonist_douse_second_choice(query, context, game, player, parts):
    doused_targets = []
    if len(parts) < 3:
        await query.edit_message_text("Invalid selection.")
        return

    selection = parts[2]
    if selection == "skip":
        game.night_actions.pop("arsonist_douse_second", None)
        player.has_acted = True
        await query.edit_message_text("You chose to skip the second douse.")
        return

    try:
        target_id = int(selection)
        target_player = game.players.get(target_id)
        
        if not target_player or not target_player.is_alive or target_player.is_doused:
            await query.edit_message_text("Invalid target selected.")
            return

        game.night_actions["arsonist_douse_second"] = {"actor": player.user_id, "target": target_id}
        target_player.is_doused = True
        player.has_acted = True
        player.accelerant_boost_next_night = False  # Clear boost after use
        
        await query.edit_message_text(f"You doused {target_player.first_name} for the second time.")
        
    except Exception as e:
        await query.edit_message_text("An error occurred processing your second douse.")

async def handle_fire_starter_block_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player):
    """Show Fire Starter block target selection menu"""
    alive_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]
    
    if not alive_players:
        await query.edit_message_text("No players available to block.")
        player.has_acted = True
        return
    
    buttons = [
        [InlineKeyboardButton(f"⚡ Block {p.first_name}", callback_data=f"fire_starter_block_{p.user_id}")]
        for p in alive_players
    ]
    buttons.append([InlineKeyboardButton("❌ Skip Blocking", callback_data="fire_starter_block_skip")])
    
    await query.edit_message_text(
        "Select a player to block or skip:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def handle_webkeeper_mark(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    """Handle Webkeeper marking a target for protection"""
    if player.role != Role.WEBKEEPER or not player.is_alive:
        await query.edit_message_text("You cannot perform this action.")
        return
    
    try:
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target.")
            return
        
        # Mark the target
        player.webkeeper_marked_target = target_id
        game.night_actions[f"webkeeper_mark_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        player.has_acted = True
        
        await query.edit_message_text(f"🕷️ You have woven your web around {target_player.first_name}.")
        logger.info(f"Webkeeper {player.first_name} marked {target_player.first_name}")
        
    except Exception as e:
        logger.error(f"handle_webkeeper_mark error: {e}")
        await query.edit_message_text("An error occurred.")


async def handle_stray_observe(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    """Handle Stray observing who visited a target"""
    if player.role != Role.STRAY or not player.is_alive:
        await query.edit_message_text("You cannot perform this action.")
        return
    
    try:
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target.")
            return
        
        # Store observation
        player.stray_observed_target = target_id
        game.night_actions[f"stray_observe_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        player.has_acted = True
        
        await query.edit_message_text(f"🐾 You observe {target_player.first_name} from the shadows...")
        logger.info(f"Stray {player.first_name} is observing {target_player.first_name}")
        
    except Exception as e:
        logger.error(f"handle_stray_observe error: {e}")
        await query.edit_message_text("An error occurred.")


async def handle_thief_steal(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    """Handle Thief stealing an ability with probability-based success"""
    if player.role != Role.THIEF or not player.is_alive:
        await query.edit_message_text("You cannot perform this action.")
        return
    
    if getattr(player, 'thief_ability_used', False):
        await query.edit_message_text("You have already used your theft ability.")
        return
    
    try:
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target.")
            return
        
        # Unstealable roles
        unstealable_roles = [
            Role.VILLAGER,
            Role.FOOL, 
            Role.CURSED_VILLAGER,
            Role.TWINS,
            Role.MIRROR_PHANTOM,
            Role.THIEF
        ]
        
        if target_player.role in unstealable_roles:
            player.thief_ability_used = True
            player.has_acted = True
            
            await query.edit_message_text(
                f"🗝️ **NOTHING TO BEGIN WITH!** {target_player.first_name}'s house was empty."
            )
            logger.info(f"Thief {player.first_name} tried to steal unstealable role {target_player.role.role_name}")
            return
        
        # Define theft success probabilities by role
        theft_probabilities = {
            # Common power roles (50-60%)
            Role.SEER: 70,
            Role.DOCTOR: 65,
            Role.BODYGUARD: 60,
            Role.HUNTER: 40,
            Role.INSOMNIAC: 55,
            Role.STRAY: 65,
            
            # Medium power roles (40-50%)
            Role.WITCH: 55,
            Role.DETECTIVE: 35,
            Role.ORACLE: 55,
            Role.PRIEST: 55,
            Role.VIGILANTE: 50,
            Role.CUPID: 50,
            
            # Strong power roles (30-40%)
            Role.MAYOR: 45,
            Role.PLAGUE_DOCTOR: 20,
            Role.GRAVE_ROBBER: 20,
            Role.DOPPELGANGER: 30,
            
            # Evil roles - harder to steal (20-35%)
            Role.WEREWOLF: 25,
            Role.ALPHA_WOLF: 25,
            Role.WOLF_SHAMAN: 25,
            Role.ARSONIST: 30,
            Role.BLAZEBRINGER: 30,
            Role.ACCELERANT_EXPERT: 30,
            Role.SERIAL_KILLER: 20,
            Role.WEBKEEPER: 25,
            
            # Neutral roles (varies)
            Role.JESTER: 50,
            Role.EXECUTIONER: 45,
        }
        
        # Get success probability (default 45% if role not defined)
        success_chance = theft_probabilities.get(target_player.role, 45)
        
        # Roll for success
        roll = random.randint(1, 100)
        success = roll <= success_chance
        
        # Record attempt regardless of outcome
        game.night_actions[f"thief_steal_{player.user_id}"] = {
            "actor": player.user_id, 
            "target": target_id,
            "success": success,
            "roll": roll,
            "chance": success_chance
        }
        player.has_acted = True
        player.thief_ability_used = True
        
        log_insomniac_visit(player, target_player, logger)
        
        if success:
            # Successful theft
            player.thief_stolen_role = target_player.role
            player.role = target_player.role  # Transform into that role
            
            await query.edit_message_text(
                f"🗝️ **SUCCESS!** You have stolen the power of {target_player.first_name}!\n\n"
                f"You are now: {player.role.emoji} {player.role.role_name}\n"
            )
            logger.info(f"Thief {player.first_name} successfully stole {target_player.role.role_name} from {target_player.first_name} ({roll}/{success_chance})")
        else:
            # Failed theft
            await query.edit_message_text(
                f"🗝️ **FAILED!** You attempted to steal from {target_player.first_name}, but they sensed your presence!\n\n"
                f"You remain a Thief with no special ability.\n"
            )
            logger.info(f"Thief {player.first_name} failed to steal from {target_player.first_name} ({roll}/{success_chance})")
        
    except Exception as e:
        logger.error(f"handle_thief_steal error: {e}")
        await query.edit_message_text("An error occurred.")


async def handle_grave_robber_borrow(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: list):
    """Handle borrowing a new role"""
    if not player.grave_robber_can_borrow_tonight:
        await query.edit_message_text("You cannot borrow a role tonight.")
        return
    
    target_id = int(parts[3])  # grave_robber_borrow_{user_id}
    target_player = next((p for p in game.dead_players if p.user_id == target_id), None)
    
    if not target_player or not target_player.role:
        await query.edit_message_text("Cannot borrow this role - player not found.")
        return
    
    # PREVENT BORROWING GRAVE ROBBER OR VILLAGER
    if target_player.role in [Role.GRAVE_ROBBER, Role.VILLAGER]:
        await query.edit_message_text("Cannot borrow this role - invalid or basic villager.")
        return

    if not target_player.role or target_player.role == Role.VILLAGER:
        await query.edit_message_text("Cannot borrow this role - invalid or basic villager.")
        return
    
    # Borrow the role
    player.grave_robber_borrowed_role = target_player.role
    player.grave_robber_can_borrow_tonight = False
    player.grave_robber_act_tonight = False  # Can act next night
    player.has_acted = True
    game.night_actions[f"grave_robber_borrow_{player.user_id}_{target_id}"] = {
            "actor": player.user_id, 
            "target": target_id
        }
    
    await query.edit_message_text(f"⚰️ You will borrow {target_player.first_name}'s power tomorrow night.")

async def handle_doppelganger_choose(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    """Handle Doppelganger choosing their target"""
    if player.role != Role.DOPPELGANGER or not player.is_alive:
        await query.edit_message_text("You cannot perform this action.")
        return
    
    if game.day_number != 1:
        await query.edit_message_text("You can only choose your target on the first night.")
        return
    
    if hasattr(player, 'doppelganger_target_id') and player.doppelganger_target_id:
        await query.edit_message_text("You have already chosen your target.")
        return
    
    try:
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid choice.")
            return
        
        if target_id == player.user_id:
            await query.edit_message_text("You cannot choose yourself.")
            return
        
        # Store the target
        player.doppelganger_target_id = target_id
        player.has_acted = True
        
        await query.edit_message_text(
            f"🎭 You have chosen to observe {target_player.first_name}.\n\n"
            f"When they die, you will become them and inherit their role."
        )
        
        logger.info(f"Doppelganger {player.first_name} chose to copy {target_player.first_name}")
        
    except Exception as e:
        logger.error(f"handle_doppelganger_choose error: {e}")
        await query.edit_message_text("An error occurred.")

async def handle_oracle_check(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    if len(parts) < 3:
        await query.edit_message_text("Invalid oracle check selection.")
        player.has_acted = True
        return

    try:
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target for oracle check.")
            player.has_acted = True
            return
        game.night_actions[f"oracle_{player.user_id}"] = {"actor": player.user_id, "target": target_id}

        await query.edit_message_text(f"🌟 You commune with the spirits about {target_player.first_name}...\n\nYour divination will come at dawn.")
        player.has_acted = True

        logger.info(f"Oracle {player.first_name} checked {target_player.first_name} in game {game.group_id}")

        log_insomniac_visit(player, target_player, logger)
    except Exception as e:
        logger.error(f"handle_oracle_check error: {e}")
        await query.edit_message_text("An error occurred during oracle check.")

async def handle_witch_heal_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player):
    if player.witch_heal_used:
        await query.edit_message_text("You have already used your heal potion.")
        return
    dead_players = [p for p in game.dead_players if p.user_id != player.user_id]
    if not dead_players:
        await query.edit_message_text("No dead players to revive.")
        return
    buttons = [
        [InlineKeyboardButton(f"💊 Revive {p.first_name}", callback_data=f"witch_heal_{p.user_id}")]
        for p in dead_players
    ]
    buttons.append([InlineKeyboardButton("❌ Skip", callback_data="witch_heal_skip")])
    await query.edit_message_text(
        "Choose a player to revive or skip:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown'
    )

async def handle_witch_heal_choice(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: list):
    if player.witch_heal_used:
        await query.edit_message_text("You have already used your heal potion.")
        return

    try:
        if parts[2] == "skip":
            player.has_acted = True
            await query.edit_message_text("You chose not to use your heal potion.")
            return
            
        target_id = int(parts[2])
        target = game.players.get(target_id)
        
        if not target or target.is_alive:
            await query.edit_message_text("Invalid target - can only heal dead players.")
            return

        # Fix the typo here:
        player.witch_heal_used = True
        player.has_acted = True
        
        # Add heal action to night actions
        game.night_actions[f"witch_heal_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        
        await query.edit_message_text(f"You have chosen to revive {target.first_name}.")
        logger.info(f"Witch {player.first_name} chose to revive {target.first_name} in game {game.group_id}")
        
    except Exception as e:
        logger.error(f"Witch heal error: {e}")
        await query.edit_message_text("An error occurred during healing.")

async def handle_witch_poison_menu(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player):
    if player.witch_poison_used:
        await query.edit_message_text("You have already used your poison.")
        return
    alive_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]
    buttons = [
        [InlineKeyboardButton(f"☠️ Poison {p.first_name}", callback_data=f"witch_poison_{p.user_id}")]
        for p in alive_players
    ]
    buttons.append([InlineKeyboardButton("❌ Skip", callback_data="witch_poison_skip")])
    await query.edit_message_text(
        "Choose a player to poison or skip:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown'
    )

async def handle_witch_poison_choice(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: list):
    if player.witch_poison_used:
        await query.edit_message_text("You have already used your poison.")
        return

    try:
        if parts[2] == "skip":
            player.has_acted = True
            await query.edit_message_text("You chose not to use your poison.")
            return
            
        target_id = int(parts[2])
        target = game.players.get(target_id)
        log_insomniac_visit(player, target, logger)
        if not target or not target.is_alive:
            await query.edit_message_text("Invalid target.")
            return

        # Mark poison used
        player.witch_poison_used = True
        player.has_acted = True
        
        # Add poison action to night actions for processing
        game.night_actions[f"witch_poison_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        
        await query.edit_message_text(f"You have poisoned {target.first_name}.")
        logger.info(f"Witch {player.first_name} poisoned {target.first_name} in game {game.group_id}")
        
    except Exception as e:
        logger.error(f"Witch poison error: {e}")
        await query.edit_message_text("An error occurred during poisoning.")

async def handle_plague_doctor_infect(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    if len(parts) < 4 or not parts[3].isdigit():
        await query.edit_message_text("Invalid infection selection.")
        return

    try:
        target_id = int(parts[3])
        target_player = game.players.get(target_id)
        log_insomniac_visit(player, target_player, logger)   
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target for infection.")
            return

        if getattr(target_player, 'is_plagued', False):
            await query.edit_message_text(f"{target_player.first_name} is already infected.")
            return

        # Record the infection action (will be processed in night resolution)
        game.night_actions[f"plague_doctor_infect_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        
        await query.edit_message_text(f"You have infected {target_player.first_name} with the plague.")
        player.has_acted = True

        logger.info(f"Plague Doctor {player.first_name} infected {target_player.first_name} in game {game.group_id}")
        
    except Exception as e:
        logger.error(f"Error in plague doctor infect handler: {e}")
        await query.edit_message_text("An error occurred while processing your infection.")

async def handle_bodyguard_protect(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: list):
    if len(parts) < 3:
        await query.edit_message_text("Invalid selection.")
        player.has_acted = True
        return
    try:
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target.")
            player.has_acted = True
            return
        game.night_actions[f"bodyguard_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        await query.edit_message_text(f"You have chosen to protect {target_player.first_name}.")
        player.has_acted = True
        log_insomniac_visit(player, target_player, logger)
    except Exception as e:
        await query.edit_message_text("An error occurred while choosing target.")

async def handle_detective_check(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: list):
    if len(parts) < 3:
        await query.edit_message_text("Invalid selection.")
        player.has_acted = True
        return
    try:
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid target for investigation.")
            player.has_acted = True
            return

        # Record the detective's action to night actions
        game.night_actions[f"detective_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        
        await query.edit_message_text(f"🕵️ You begin investigating {target_player.first_name}...\n\nYour findings will be ready when voting begins.")
        player.has_acted = True
    
        # Log action
        logger.info(f"Detective {player.first_name} investigated {target_player.first_name} in game {game.group_id}")

    except Exception as e:
        logger.error(f"handle_detective_check error: {e}")
        await query.edit_message_text("An error occurred while investigating.")

async def handle_doctor_heal(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    if len(parts) < 3:
        await query.edit_message_text("Invalid heal selection.")
        return
    try:
        if parts[2] == "skip":
            game.night_actions.pop(f"doctor_{player.user_id}", None)
            await query.edit_message_text("You chose not to heal anyone.")
            return
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid heal target.")
            return
        game.night_actions[f"doctor_{player.user_id}"] = {"actor": player.user_id, "target": target_id}
        await query.edit_message_text(f"You have chosen to heal {target_player.first_name}.")
        player.has_acted = True
        logger.info(f"Doctor {player.first_name} chose to heal {target_player.first_name} in game {game.group_id}")
        log_insomniac_visit(player, target_player, logger)
    except Exception as e:
        logger.error(f"handle_doctor_heal error: {e}")
        await query.edit_message_text("An error occurred during healing.")

async def handle_team_message_universal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    '''Universal team communication handler for Wolves, Fire Team, Lovers, and Twins'''
    user = update.effective_user
    message = update.message
    
    if not message or not message.text:
        return
        
    # Find the game this player is in
    game = None
    player = None
    for g in active_games.values():
        if user.id in g.players:
            game = g
            player = g.players[user.id]
            break
    
    if not game or not player:
        return  # Player not in any game
    
    if not player.is_alive:
        await message.reply_text("💀 Dead players cannot communicate with teammates.")
        return
    
    # Check phase restrictions for different teams
    phase_restriction = get_team_phase_restriction(player, game)
    if phase_restriction:
        await message.reply_text(phase_restriction)
        return
    
    # Get team members based on relationship type
    teammates = get_team_members(player, game)
    
    if not teammates['members']:
        await message.reply_text(f"🚫 {teammates['no_members_msg']}")
        return
    
    # Format the team message
    formatted_message = f"**{player.first_name}**: {message.text}"
    
    # Send to all team members
    sent_count = 0
    for teammate in teammates['members']:
        try:
            await context.bot.send_message(
                chat_id=teammate.user_id,
                text=formatted_message,
                parse_mode="Markdown"
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send team message to {teammate.first_name}: {e}")
    
    # Confirm to sender
    if sent_count > 0:
        await message.reply_text(f"✅ Message sent to {sent_count} {teammates['team_type']}(s).")
    else:
        await message.reply_text("❌ Failed to send message to teammates.")

def get_team_phase_restriction(player: Player, game: Game) -> str:
    '''Check if player can communicate based on phase and team type'''
    # Wolves can only communicate during night
    if player.role and player.role.team == Team.WOLF:
        if game.phase != GamePhase.NIGHT:
            return "🌙 Wolf communication is only available during night phase."
    
    # Fire team can only communicate during night
    elif player.role and player.role.team == Team.FIRE:
        if game.phase != GamePhase.NIGHT:
            return "🌙 Fire team communication is only available during night phase."
    
    # Lovers and Twins can communicate anytime (except voting phase for fairness)
    elif game.phase == GamePhase.VOTING:
        return "🗳️ Team communication is disabled during voting phase."
    
    return None  # No restriction

def get_team_members(player: Player, game: Game) -> dict:
    '''Get team members based on player's relationships'''
    
    # 🐺 WOLF TEAM
    if player.role and player.role.team == Team.WOLF:
        teammates = [p for p in game.get_alive_players() 
                    if p.user_id != player.user_id 
                    and p.role 
                    and p.role.team == Team.WOLF]
        return {
            'members': teammates,
            'emoji': '🐺',
            'team_name': 'Wolf Pack Chat',
            'team_type': 'wolf teammate',
            'no_members_msg': 'No wolf teammates are alive.'
        }
    
    # 🔥 FIRE TEAM
    elif player.role and player.role.team == Team.FIRE:
        teammates = [p for p in game.get_alive_players() 
                    if p.user_id != player.user_id 
                    and p.role 
                    and p.role.team == Team.FIRE]
        return {
            'members': teammates,
            'emoji': '🔥',
            'team_name': 'Fire Team Chat',
            'team_type': 'fire teammate',
            'no_members_msg': 'No fire teammates are alive.'
        }
    
    # 💕 LOVERS
    elif hasattr(player, 'lover_id') and player.lover_id:
        lover = game.players.get(player.lover_id)
        teammates = [lover] if lover and lover.is_alive else []
        return {
            'members': teammates,
            'emoji': '💕',
            'team_name': 'Lovers Chat',
            'team_type': 'lover',
            'no_members_msg': 'Your lover is not alive.'
        }
    
    # 👯 TWINS
    elif player.user_id in game.twins_ids:
        twin_partner = None
        for twin_id in game.twins_ids:
            if twin_id != player.user_id:
                twin_partner = game.players.get(twin_id)
                break
        teammates = [twin_partner] if twin_partner and twin_partner.is_alive else []
        return {
            'members': teammates,
            'emoji': '👯',
            'team_name': 'Twin Chat',
            'team_type': 'twin',
            'no_members_msg': 'Your twin is not alive.'
        }
    
    # No team relationship
    return {
        'members': [],
        'emoji': '🚫',
        'team_name': '',
        'team_type': '',
        'no_members_msg': 'You have no team communication access.'
    }

async def notify_universal_action(context: ContextTypes.DEFAULT_TYPE, game: Game, 
                                  acting_player: Player, action: str, target_name: str = None):
    '''Universal action notification system for all teams'''
    
    # Get all possible team members
    team_data = get_team_members(acting_player, game)
    
    if not team_data['members']:
        return  # No teammates to notify
    
    # Format notification message
    if target_name:
        notification = f"{team_data['emoji']} **{acting_player.first_name}** {action} **{target_name}**"
    else:
        notification = f"{team_data['emoji']} **{acting_player.first_name}** {action}"
    
    # Send to all team members
    for teammate in team_data['members']:
        try:
            await context.bot.send_message(
                chat_id=teammate.user_id,
                text=notification,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to notify {team_data['team_type']} {teammate.first_name}: {e}")

async def handle_vote(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    if len(parts) < 2:
        await query.edit_message_text("Invalid vote.")
        return
    try:
        if parts[1] == "abstain":
            if player.has_voted:
                await query.edit_message_text("You have already voted.")
                return
            game.votes[player.user_id] = None
            player.has_voted = True
            await query.edit_message_text("You have abstained from voting.")
            # 🆕 Announce abstention in group
            try:
                await context.bot.send_message(
                    chat_id=game.group_id,
                    text=f"🗳️ {player.mention} has abstained from voting.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to announce abstention: {e}")
            return
            
        target_id = int(parts[1])
        if player.has_voted:
            await query.edit_message_text("You have already voted.")
            return
        if target_id not in game.players or not game.players[target_id].is_alive:
            await query.edit_message_text("Invalid vote target.")
            return
            
        target_player = game.players[target_id]
        game.votes[player.user_id] = target_id
        player.has_voted = True
        player.has_acted = True
        
        await query.edit_message_text(f"You voted for {target_player.first_name}.")
        
        # 🆕 Announce vote in group
        try:
            await context.bot.send_message(
                chat_id=game.group_id,
                text=f"🗳️ {player.mention} has cast their vote.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to announce vote: {e}")
            
        logger.info(f"{player.first_name} voted for {target_player.first_name} in game {game.group_id}")
    except Exception as e:
        logger.error(f"handle_vote error: {e}")
        await query.edit_message_text("An error occurred during voting.")

async def handle_hunter_shoot(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, parts: List[str]):
    """Handle Hunter shooting target (lynch revenge or other scenarios)"""
    
    # ✅ PREVENT DUPLICATE SHOTS
    if player.has_acted:
        await query.answer("You already took your shot!", show_alert=True)
        return
        
    if len(parts) < 3:
        await query.edit_message_text("Invalid shoot selection.")
        return
    
    try:
        # Check if this is a lynch revenge scenario
        is_lynch_revenge = hasattr(game, 'waiting_for_hunter') and game.waiting_for_hunter
        
        target_id = int(parts[2])
        target_player = game.players.get(target_id)
        
        if not target_player or not target_player.is_alive:
            await query.edit_message_text("Invalid shoot target.")
            return

        # Kill the chosen target
        await kill_player(context, game, target_player, death_type="hunter")
        
        # Announce in group
        await context.bot.send_message(
            chat_id=game.group_id,
            text=f"🏹💀 {player.mention}'s arrow flies true and strikes {target_player.mention}!",
            parse_mode='Markdown'
        )

        # ✅ If this was lynch revenge, NOW kill the hunter
        if is_lynch_revenge and player.is_alive:
            await kill_player(context, game, player, death_type="lynch")
            game.waiting_for_hunter = False
            game.hunter_user_id = None
        
        # Mark hunter shoot used
        player.hunter_can_shoot = False
        player.has_acted = True

        await query.edit_message_text(f"🏹 You have shot {target_player.first_name}.")

        # Track stats (if not custom game)
        if not getattr(game, 'custom_game', False):
            if not hasattr(player, 'game_actions'):
                player.game_actions = {}
        
            if target_player.role.team != Team.VILLAGER:
                player.game_actions['hunter_revenge_evil'] = player.game_actions.get('hunter_revenge_evil', 0) + 1
            else:
                player.game_actions['major_mistake'] = player.game_actions.get('major_mistake', 0) + 1

        # Check if other hunters still need to shoot
        hunters_left = [
            p for p in game.get_alive_players()
            if p.role == Role.HUNTER and getattr(p, "hunter_can_shoot", False) and not p.has_acted
        ]
        
        if not hunters_left:
            # All hunters done - clear phase timer
            game.phase_end_time = None

            alive_players = game.get_alive_players()
            if len(alive_players) == 2:
                from mechanics import handle_two_player_resolution
                game_ended = await handle_two_player_resolution(context, game)
                if game_ended:
                    return
            
            # Check win condition
            winner = game.check_win_condition()
            if winner:
                await end_game(context, game, winner)
            else:
                await asyncio.sleep(3)
                await start_night_phase(context, game)
        else:
            # Remind remaining hunters
            for h in hunters_left:
                try:
                    await context.bot.send_message(
                        chat_id=h.user_id,
                        text="🏹 You still have a final shot to take.",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to remind Hunter {h.first_name}: {e}")

        logger.info(f"Hunter {player.first_name} shot {target_player.first_name} in game {game.group_id}")

    except Exception as e:
        logger.error(f"handle_hunter_shoot error: {e}")
        await query.edit_message_text("An error occurred during shooting.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}")
    try:
        if update and hasattr(update, 'effective_chat'):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="An error occurred. Please try again."
            )
    except Exception:
        pass

async def check_game_timers(context: ContextTypes.DEFAULT_TYPE):
    current_time = datetime.now().timestamp()
    for game in list(active_games.values()):
        if not game.phase_end_time or current_time < game.phase_end_time:
            continue  # Timer not expired yet

        # ============================================================================
        # ✅ FIX 1: HUNTER LYNCH REVENGE TIMEOUT - CHECK THIS FIRST
        # ============================================================================
        if hasattr(game, 'waiting_for_hunter') and game.waiting_for_hunter:
            hunter_id = getattr(game, 'hunter_user_id', None)
            if hunter_id:
                hunter = game.players.get(hunter_id)
                
                if hunter and not hunter.has_acted:
                    # Hunter hasn't shot yet - TIMEOUT
                    logger.warning(f"Hunter {hunter.first_name} timed out on revenge shot")
                    
                    alive_players = game.get_alive_players()
                    if alive_players:
                        target = random.choice(alive_players)
                        
                        # Kill the target first
                        await kill_player(context, game, target, death_type="hunter")
                        
                        # NOW kill the hunter
                        await kill_player(context, game, hunter, death_type="lynch")
                        
                        await context.bot.send_message(
                            chat_id=game.group_id,
                            text=f"🏹⏰ Time ran out! {hunter.mention}'s final arrow flies wild and strikes {target.mention}!",
                            parse_mode='Markdown'
                        )
                    else:
                        # No targets - just kill hunter
                        await kill_player(context, game, hunter, death_type="lynch")
                        
                        await context.bot.send_message(
                            chat_id=game.group_id,
                            text=f"🏹⏰ {hunter.mention}'s final moment passes...",
                            parse_mode='Markdown'
                        )
                    
                    # Clean up flags
                    game.waiting_for_hunter = False
                    game.hunter_user_id = None
                    game.phase_end_time = None
                    
                    # NOW check win condition
                    winner = game.check_win_condition()
                    if winner:
                        await end_game(context, game, winner)
                    else:
                        await asyncio.sleep(3)
                        await start_night_phase(context, game)
                    
                    continue  # Skip rest of timer logic for this game
                else:
                    # Hunter already acted or is dead - clean up and proceed normally
                    game.waiting_for_hunter = False
                    game.hunter_user_id = None

        # ============================================================================
        # ✅ FIX 2: NORMAL HUNTER SHOOT DURING DAY PHASE (non-lynch scenario)
        # ============================================================================
        if game.phase == GamePhase.DAY:
            hunters_pending = [
                p for p in game.get_alive_players()
                if p.role == Role.HUNTER and getattr(p, "hunter_can_shoot", False) and not p.has_acted
            ]
            if hunters_pending:
                # Extend timer by 5 seconds and remind hunters
                game.phase_end_time = current_time + 5
                for hunter in hunters_pending:
                    try:
                        await context.bot.send_message(
                            chat_id=hunter.user_id,
                            text="🏹 **5 seconds remaining!** Take your final shot!",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to remind Hunter {hunter.first_name}: {e}")
                continue  # Skip phase advancement until hunter acts or times out

        # ============================================================================
        # NORMAL TIMEOUT HANDLING - NOTIFY MISSING PLAYERS
        # ============================================================================
        expected_actors = [
            p for p in game.get_alive_players() if player_has_pending_action(p, game)
        ]
        
        afk_players_to_kick = []
        
        for player in expected_actors:
            # Player acted - reset AFK counter
            if getattr(player, "has_acted", False):
                player.afk_count = 0
                player.warned_afk = False
                continue
            
            # Player didn't act - increment AFK
            if game.settings.get('afk_kick', True):
                player.afk_count += 1
                logger.info(f"Player {player.first_name} missed action. AFK count: {player.afk_count}")
                
                afk_threshold = game.settings.get('afk_threshold', 3)
                
                # Warn at threshold - 1
                if player.afk_count == afk_threshold - 1 and not player.warned_afk:
                    player.warned_afk = True
                    try:
                        await context.bot.send_message(
                            chat_id=player.user_id,
                            text=f"⚠️ **AFK WARNING**\n\n"
                                 f"You've been inactive for {player.afk_count} round(s).\n"
                                 f"Miss one more action and you'll be removed from the game!",
                            parse_mode='Markdown'
                        )
                        logger.info(f"Sent AFK warning to {player.first_name}")
                    except Exception as e:
                        logger.error(f"Failed to send AFK warning to {player.first_name}: {e}")
                
                # Kick at threshold
                elif player.afk_count >= afk_threshold:
                    afk_players_to_kick.append(player)
            
            # Handle Grave Robber stuck state
            if player.role == Role.GRAVE_ROBBER and getattr(player, 'grave_robber_act_tonight', False):
                player.grave_robber_act_tonight = False
                player.grave_robber_can_borrow_tonight = True
                player.grave_robber_borrowed_role = None
                logger.info(f"Reset stuck Grave Robber {player.first_name}")
            
            # Notify player of timeout
            try:
                if hasattr(player, "last_action_message_id"):
                    await context.bot.edit_message_reply_markup(
                        chat_id=player.user_id,
                        message_id=player.last_action_message_id,
                        reply_markup=None
                    )
                await context.bot.send_message(
                    chat_id=player.user_id,
                    text="⏰ Time's up! You missed your action."
                )
            except Exception as e:
                logger.error(f"Failed to notify player {player.first_name} of timeout: {e}")

        # ============================================================================
        # AFK KICK PROCESSING
        # ============================================================================
        for afk_player in afk_players_to_kick:
            logger.info(f"Kicking AFK player: {afk_player.first_name} ({afk_player.afk_count} strikes)")
            
            try:
                await context.bot.send_message(
                    chat_id=afk_player.user_id,
                    text=f"🚫 **Removed for Inactivity**\n\n"
                         f"You've been inactive for {afk_player.afk_count} consecutive rounds.\n"
                         f"You have been removed from the game.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify kicked player {afk_player.first_name}: {e}")
            
            # Kill the AFK player
            await kill_player(context, game, afk_player, "afk")
            
            # Notify group
            await context.bot.send_message(
                chat_id=game.group_id,
                text=f"⏰ {afk_player.mention} was removed from the game due to inactivity (AFK).",
                parse_mode='Markdown'
            )
        
        # Check win condition after AFK kicks
        if afk_players_to_kick:
            winner = game.check_win_condition()
            if winner:
                await end_game(context, game, winner)
                continue

        # ============================================================================
        # CLEAR PHASE END TIME
        # ============================================================================
        game.phase_end_time = None

        # ============================================================================
        # PROCEED TO NEXT PHASE
        # ============================================================================
        if game.phase == GamePhase.NIGHT:
            await start_day_phase(context, game)
            
        elif game.phase == GamePhase.DAY:
            await start_voting_phase(context, game)
            
        elif game.phase == GamePhase.VOTING:
            # Remove vote buttons from all players
            for player in game.get_alive_players():
                try:
                    if hasattr(player, "last_action_message_id"):
                        await context.bot.edit_message_reply_markup(
                            chat_id=player.user_id,
                            message_id=player.last_action_message_id,
                            reply_markup=None
                        )
                        logger.debug(f"Removed vote buttons for {player.first_name}")
                    
                    # Notify if they didn't vote
                    if not player.has_voted:
                        await context.bot.send_message(
                            chat_id=player.user_id,
                            text="⏰ Time's up! Your vote was not recorded (counted as abstain)."
                        )
                except Exception as e:
                    logger.error(f"Failed to remove vote buttons for {player.first_name}: {e}")

            await process_voting_results(context, game)

def setup_handlers(app):
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("newgame", new_game_command))
    app.add_handler(CommandHandler('rules', rules_command))
    app.add_handler(CommandHandler('roles', roles_command))
    app.add_handler(CommandHandler('customgame', custom_game_command))
    app.add_handler(CommandHandler("extend", extend_command))
    app.add_handler(CommandHandler("join", join_command))
    app.add_handler(CommandHandler('settings', settings_command))
    app.add_handler(CommandHandler("leave", leave_command))
    app.add_handler(CommandHandler("players", players_command))
    app.add_handler(CommandHandler("startgame", start_game_command))
    app.add_handler(CommandHandler("endgame", end_game_command))
    app.add_handler(CommandHandler('stats', stats_command))
    app.add_handler(CommandHandler('check_gifs', check_gifs_command))
    app.add_handler(CommandHandler('leaderboard', leaderboard_command))
    app.add_handler(CommandHandler('rank_info', rank_info_command))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,handle_team_message_universal))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_error_handler(error_handler)
    app.job_queue.run_repeating(check_game_timers, interval=30, first=30)

async def on_startup(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Werewolf bot started successfully.")
