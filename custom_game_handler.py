import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.constants import ChatType
from telegram.ext import ContextTypes
from datetime import datetime
from collections import Counter
from game import active_games, Game, GamePhase, Player, Role, Team

logger = logging.getLogger(__name__)

# Storage for custom game configurations
custom_game_configs = {}  # {chat_id: {"roles": [Role, ...], "locked": bool, "admin_id": int, "config_message_id": int}}


async def custom_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start custom game with role configuration (admin only)"""
    chat = update.effective_chat
    user = update.effective_user
    
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await update.message.reply_text("This command works only in groups.")
        return
    
    # Check if game already active
    if chat.id in active_games:
        game = active_games[chat.id]
        if game.phase != GamePhase.ENDED:
            await update.message.reply_text(
                f"A game is already active (phase: {game.phase.value})."
            )
            return
    
    # Check if user is admin
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ['creator', 'administrator']:
            await update.message.reply_text("Only admins can start custom games.")
            return
    except Exception as e:
        logger.error(f"Failed to check admin status: {e}")
        await update.message.reply_text("Could not verify admin status.")
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Add Villager Role", callback_data="customgame_category_villager")],
        [InlineKeyboardButton("🐺 Add Evil Role", callback_data="customgame_category_evil")],
        [InlineKeyboardButton("🎭 Add Neutral Role", callback_data="customgame_category_neutral")],
        [InlineKeyboardButton("📋 View Role Pool", callback_data="customgame_view_pool")],
        [InlineKeyboardButton("🗑️ Clear All Roles", callback_data="customgame_clear_all")],
        [InlineKeyboardButton("✅ Done & Start Lobby", callback_data="customgame_done")]
    ])
    
    sent_message = await update.message.reply_text(
        "🎮 **Custom Werewolf Game Setup**\n\n"
        "Configure roles before players join.\n"
        "Current roles: **0**\n\n"
        "⚠️ **Note:** Rankings are disabled for custom games\n"
        "🔓 **No validation - add any roles you want!**\n\n"
        "_Add roles one by one. You can add multiple copies of any role._",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    
    # Initialize custom game config with admin tracking
    custom_game_configs[chat.id] = {
        "roles": [],
        "locked": False,
        "admin_id": user.id,
        "config_message_id": sent_message.message_id
    }
    
    logger.info(f"Custom game setup initiated by admin {user.first_name} in group {chat.id}")


async def handle_customgame_callback(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom game configuration callbacks"""
    data = query.data
    chat = query.message.chat
    user = query.from_user
    
    # Verify admin
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status not in ['creator', 'administrator']:
            await query.answer("⛔ Only admins can configure custom games.", show_alert=True)
            return
    except Exception as e:
        logger.error(f"Admin verification failed: {e}")
        await query.answer("Admin verification failed.", show_alert=True)
        return
    
    # Initialize config if missing
    if chat.id not in custom_game_configs:
        await query.answer("Configuration expired. Please use /customgame again.", show_alert=True)
        return
    
    config = custom_game_configs[chat.id]
    
    # Check if locked (game started)
    if config.get("locked", False):
        await query.answer("⚠️ Configuration locked - game has started", show_alert=True)
        return
    
    current_count = len(config["roles"])
    
    # Handle clear all
    if data == "customgame_clear_all":
        if not config["roles"]:
            await query.answer("No roles to clear!", show_alert=False)
            return
        
        config["roles"] = []
        await query.answer("✅ All roles cleared!", show_alert=False)
        
        # Notify group
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"🗑️ {user.first_name} cleared all roles from the custom game.",
            parse_mode='Markdown'
        )
        
        await refresh_customgame_menu(query, chat.id)
    
    # Handle view pool
    elif data == "customgame_view_pool":
        if not config["roles"]:
            await query.answer("No roles added yet!", show_alert=True)
            return
        
        await show_role_pool(query, config)
    
    # Handle done
    elif data == "customgame_done":
        if len(config["roles"]) < 5:
            await query.answer("⚠️ Need at least 5 roles to start!", show_alert=True)
            return
        
        if len(config["roles"]) > 20:
            await query.answer("⚠️ Maximum 20 roles allowed!", show_alert=True)
            return
        
        # NO VALIDATION - just start
        await start_custom_game_lobby(query, context, chat, config)
    
    # Handle back to menu
    elif data == "customgame_back_to_menu":
        await refresh_customgame_menu(query, chat.id)
    
    # Handle category selection
    elif data == "customgame_category_villager":
        await show_customgame_role_menu(query, "villager", config, current_count)
    
    elif data == "customgame_category_evil":
        await show_customgame_role_menu(query, "evil", config, current_count)
    
    elif data == "customgame_category_neutral":
        await show_customgame_role_menu(query, "neutral", config, current_count)
    
    # Handle role addition
    elif data.startswith("customgame_add_"):
        if current_count >= 20:
            await query.answer("⚠️ Maximum 20 roles reached!", show_alert=True)
            return
        
        role_name = data.replace("customgame_add_", "")
        try:
            role = Role[role_name]
            
            # NO VALIDATION - just add it
            config["roles"].append(role)
            await query.answer(f"✅ Added {role.role_name} ({len(config['roles'])} total)", show_alert=False)
            
            # 🆕 NOTIFY GROUP ABOUT ROLE ADDITION
            role_emoji = get_role_emoji(role)
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"{role_emoji} {user.first_name} added **{role.role_name}** to the custom game.\n"
                     f"Total roles: **{len(config['roles'])}**",
                parse_mode='Markdown'
            )
            
            # Refresh menu
            category = get_role_category(role)
            current_count = len(config["roles"])
            await show_customgame_role_menu(query, category, config, current_count, refresh=True)
            
            logger.info(f"Added {role.role_name} to custom game {chat.id}")
            
        except KeyError:
            logger.error(f"Invalid role name: {role_name}")
            await query.answer("❌ Invalid role", show_alert=True)
    
    # Handle back from role selection
    elif data.startswith("customgame_back_from_"):
        await refresh_customgame_menu(query, chat.id)
    
    # Handle remove individual role from pool view
    elif data.startswith("customgame_remove_"):
        try:
            index = int(data.replace("customgame_remove_", ""))
            if 0 <= index < len(config["roles"]):
                removed_role = config["roles"].pop(index)
                await query.answer(f"✅ Removed {removed_role.role_name}", show_alert=False)
                
                # Notify group
                role_emoji = get_role_emoji(removed_role)
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"{role_emoji} {user.first_name} removed **{removed_role.role_name}** from the custom game.\n"
                         f"Total roles: **{len(config['roles'])}**",
                    parse_mode='Markdown'
                )
                
                if config["roles"]:
                    await show_role_pool(query, config)
                else:
                    await refresh_customgame_menu(query, chat.id)
            else:
                await query.answer("Invalid role index", show_alert=True)
        except ValueError:
            await query.answer("Invalid data format", show_alert=True)


def get_role_emoji(role: Role) -> str:
    """Get emoji for a role based on team"""
    if role.team == Team.VILLAGER:
        return "👥"
    elif role.team in [
Team.WOLF, Team.FIRE, Team.KILLER]:
        return "🐺"
    else:
        return "🎭"


async def show_role_pool(query: CallbackQuery, config: dict):
    """Show detailed role pool with remove buttons"""
    if not config["roles"]:
        await query.answer("No roles added yet!", show_alert=True)
        return
    
    role_counts = Counter(config["roles"])
    message = "**📋 Current Role Pool**\n\n"
    
    # Group by team
    villager_roles = [r for r in config["roles"] if r.team == Team.VILLAGER]
    evil_roles = [r for r in config["roles"] if r.team in [Team.WOLF, Team.FIRE, Team.KILLER]]
    neutral_roles = [r for r in config["roles"] if r.team == Team.NEUTRAL]
    
    if villager_roles:
        villager_counts = Counter(villager_roles)
        message += f"**👥 Villagers ({len(villager_roles)})**\n"
        for role, count in villager_counts.items():
            message += f"• {role.role_name} x{count}\n"
        message += "\n"
    
    if evil_roles:
        evil_counts = Counter(evil_roles)
        message += f"**🐺 Evil ({len(evil_roles)})**\n"
        for role, count in evil_counts.items():
            message += f"• {role.role_name} x{count}\n"
        message += "\n"
    
    if neutral_roles:
        neutral_counts = Counter(neutral_roles)
        message += f"**🎭 Neutral ({len(neutral_roles)})**\n"
        for role, count in neutral_counts.items():
            message += f"• {role.role_name} x{count}\n"
        message += "\n"
    
    message += f"**Total: {len(config['roles'])} roles**\n\n"
    message += "_Tap a role below to remove one copy_"
    
    # Create buttons for each role instance
    buttons = []
    for idx, role in enumerate(config["roles"]):
        buttons.append([
            InlineKeyboardButton(
                f"❌ {role.role_name}",
                callback_data=f"customgame_remove_{idx}"
            )
        ])
    
    buttons.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="customgame_back_to_menu")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')


async def start_custom_game_lobby(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, chat, config: dict):
    """Start the custom game lobby after configuration"""
    # Lock configuration
    config["locked"] = True
    
    # Create game instance
    game = Game(chat.id, chat.title or "Group")
    game.custom_game = True
    game.start_time = datetime.now()
    active_games[chat.id] = game
    
    # Update config message to show locked state
    await query.edit_message_text(
        f"✅ **Custom Game Configuration Locked!**\n\n"
        f"Roles configured: **{len(config['roles'])}**\n"
        f"Need exactly **{len(config['roles'])}** players\n\n"
        f"🔴 Rankings disabled for custom games\n\n"
        f"Opening lobby...",
        parse_mode='Markdown'
    )
    
    # Create join button
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Join Game", callback_data="join_game")]
    ])
    
    # Send join message
    message_text = (
        "🐺 **Custom Werewolf Game Started!** 🐺\n\n"
        f"Need exactly **{len(config['roles'])}** players to start.\n"
        f"⏰ Auto-starting in 2 minutes if full\n\n"
        "Click below to join!"
    )
    
    sent_message = await context.bot.send_message(
        chat_id=chat.id,
        text=message_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    
    game.lobby_message_id = sent_message.message_id
    
    # Send player list
    player_list_text = f"**Players Joined:** 0/{len(config['roles'])}\n_No players yet_"
    player_list_msg = await context.bot.send_message(
        chat_id=chat.id,
        text=player_list_text,
        parse_mode='Markdown'
    )
    game.player_list_message_id = player_list_msg.message_id
    
    # Set timer
    game.timer_start = datetime.now()
    
    # Import and send timer message
    from handlers import send_timer_message
    await send_timer_message(context, game, chat.id)
    
    # Schedule auto-start after 120 seconds
    context.job_queue.run_once(
        auto_start_custom_game,
        when=120,
        data={'chat_id': chat.id},
        name=f"auto_start_{chat.id}"
    )
    
    logger.info(f"Custom game lobby opened with {len(config['roles'])} roles in group {chat.id}")


async def refresh_customgame_menu(query: CallbackQuery, chat_id: int):
    """Refresh the main custom game menu"""
    if chat_id not in custom_game_configs:
        await query.answer("Configuration expired. Use /customgame to restart.", show_alert=True)
        return
    
    config = custom_game_configs[chat_id]
    current_count = len(config["roles"])
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Add Villager Role", callback_data="customgame_category_villager")],
        [InlineKeyboardButton("🐺 Add Evil Role", callback_data="customgame_category_evil")],
        [InlineKeyboardButton("🎭 Add Neutral Role", callback_data="customgame_category_neutral")],
        [InlineKeyboardButton("📋 View Role Pool", callback_data="customgame_view_pool")],
        [InlineKeyboardButton("🗑️ Clear All Roles", callback_data="customgame_clear_all")],
        [InlineKeyboardButton("✅ Done & Start Lobby", callback_data="customgame_done")]
    ])
    
    await query.edit_message_text(
        "🎮 **Custom Werewolf Game Setup**\n\n"
        "Configure roles before players join.\n"
        f"Current roles: **{current_count}**\n\n"
        "⚠️ **Note:** Rankings are disabled for custom games\n"
        "🔓 **No validation - add any roles you want!**\n\n"
        "_Add roles one by one. You can add multiple copies of any role._",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )


async def show_customgame_role_menu(query: CallbackQuery, category: str, config: dict, current_count: int, refresh: bool = False):
    """Show role addition menu for a category"""
    role_data = {
        'villager': {
            'title': '👥 Add Villager Role',
            'roles': [
                Role.VILLAGER, Role.SEER, Role.DOCTOR, Role.BODYGUARD, Role.HUNTER,
                Role.WITCH, Role.DETECTIVE, Role.PRIEST, Role.ORACLE,
                Role.VIGILANTE, Role.MAYOR, Role.INSOMNIAC, Role.TWINS,
                Role.PLAGUE_DOCTOR, Role.STRAY, Role.CUPID,
                Role.APPRENTICE_SEER, Role.FOOL,Role.CURSED_VILLAGER
            ]
        },
        'evil': {
            'title': '🐺 Add Evil Role',
            'roles': [
                Role.WEREWOLF, Role.ALPHA_WOLF, Role.WOLF_SHAMAN,
                Role.ARSONIST, Role.BLAZEBRINGER, Role.ACCELERANT_EXPERT,
                Role.SERIAL_KILLER, Role.WEBKEEPER
            ]
        },
        'neutral': {
            'title': '🎭 Add Neutral Role',
            'roles': [
                Role.JESTER, Role.EXECUTIONER, Role.DOPPELGANGER, 
                Role.MIRROR_PHANTOM, Role.THIEF, Role.GRAVE_ROBBER
            ]
        }
    }
    
    if category not in role_data:
        logger.error(f"Invalid category: {category}")
        await query.answer("Invalid category", show_alert=True)
        return
    
    cat = role_data[category]
    buttons = []
    
    for role in cat['roles']:
        # NO GRAYING OUT - all roles always available
        button_text = role.role_name
        callback = f"customgame_add_{role.name}"
        
        buttons.append([
            InlineKeyboardButton(button_text, callback_data=callback)
        ])
    
    buttons.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data=f"customgame_back_from_{category}")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    message = f"**{cat['title']}**\n\nTotal roles: {current_count}/20\n\n_Select a role to add (duplicates allowed)_"
    
    try:
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Failed to update role menu: {e}")


def get_role_category(role: Role) -> str:
    """Get category name for a role"""
    if role.team == Team.VILLAGER:
        return "villager"
    elif role.team in [Team.WOLF, Team.FIRE, Team.KILLER]:
        return "evil"
    else:
        return "neutral"


async def auto_start_custom_game(context: ContextTypes.DEFAULT_TYPE):
    """Auto-start custom game after 120 seconds"""
    # Import here to avoid circular dependency
    from mechanics import send_role_assignments, start_night_phase
    from roles import assign_roles_custom
    
    job = context.job
    chat_id = job.data['chat_id']
    
    if chat_id not in active_games:
        logger.info(f"Auto-start skipped: custom game {chat_id} no longer exists")
        return
    
    game = active_games[chat_id]
    
    if game.phase != GamePhase.LOBBY:
        logger.info(f"Auto-start skipped: custom game {chat_id} already started (phase: {game.phase.value})")
        return
    
    if chat_id not in custom_game_configs:
        logger.error(f"Custom game config missing for {chat_id}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ **Game configuration error**\n\nGame cancelled.",
            parse_mode='Markdown'
        )
        if chat_id in active_games:
            del active_games[chat_id]
        return
    
    config = custom_game_configs[chat_id]
    required_players = len(config["roles"])
    actual_players = len(game.players)
    
    # Check if correct number of players
    if actual_players != required_players:
        logger.warning(f"Auto-start failed: custom game {chat_id} has {actual_players}/{required_players} players")
        
        # Remove buttons
        await cleanup_game_buttons(context, game, chat_id)
        
        # Send cancellation message
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ **Custom Game Cancelled**\n\n"
                 f"Only **{actual_players}/{required_players}** players joined.\n"
                 f"Need exactly **{required_players}** players.\n\n"
                 f"Use /customgame to start a new custom game.",
            parse_mode='Markdown'
        )
        
        # Cleanup
        if chat_id in active_games:
            del active_games[chat_id]
        if chat_id in custom_game_configs:
            del custom_game_configs[chat_id]
        
        logger.info(f"Custom game {chat_id} cancelled due to insufficient players")
        return
    
    # Remove buttons before starting
    await cleanup_game_buttons(context, game, chat_id)
    
    # Assign roles from custom pool
    try:
        if not assign_roles_custom(game, config["roles"]):
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ **Failed to assign roles**\n\nGame cancelled.",
                parse_mode='Markdown'
            )
            if chat_id in active_games:
                del active_games[chat_id]
            if chat_id in custom_game_configs:
                del custom_game_configs[chat_id]
            return
    except Exception as e:
        logger.error(f"Role assignment failed: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **Role assignment error**\n\n{str(e)}\n\nGame cancelled.",
            parse_mode='Markdown'
        )
        if chat_id in active_games:
            del active_games[chat_id]
        if chat_id in custom_game_configs:
            del custom_game_configs[chat_id]
        return
    
    # Set game phase and timestamps
    game.phase = GamePhase.NIGHT
    game.game_start_time = datetime.now()
    
    # Determine evil team type for display
    wolf_roles = [Role.WEREWOLF, Role.ALPHA_WOLF, Role.WOLF_SHAMAN]
    fire_roles = [Role.ARSONIST, Role.BLAZSBRINGER, Role.ACCELERANT_EXPERT]
    
    has_wolves = any(r in config["roles"] for r in wolf_roles)
    has_fire = any(r in config["roles"] for r in fire_roles)
    has_sk = Role.SERIAL_KILLER in config["roles"]
    
    evil_team_display = []
    if has_wolves:
        evil_team_display.append("🐺 Wolves")
    if has_fire:
        evil_team_display.append("🔥 Fire Team")
    if has_sk:
        evil_team_display.append("🔪 Serial Killer")
    
    evil_team_str = ", ".join(evil_team_display) if evil_team_display else "Various"
    
    # Announce game start
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ **Auto-starting custom game!**\n\n"
             f"Players: **{len(game.players)}**\n"
             f"Evil teams: {evil_team_str}\n\n"
             f"🔴 Rankings disabled\n\n"
             f"Roles are being assigned...",
        parse_mode='Markdown'
    )
    
    # Send role assignments
    try:
        await send_role_assignments(context, game)
    except Exception as e:
        logger.error(f"Failed to send role assignments: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **Failed to send role assignments**\n\n{str(e)}",
            parse_mode='Markdown'
        )
        return
    
    # Start night phase
    try:
        await start_night_phase(context, game)
        logger.info(f"Custom game {chat_id} auto-started successfully with {len(game.players)} players")
    except Exception as e:
        logger.error(f"Failed to start night phase: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ **Failed to start game**\n\n{str(e)}",
            parse_mode='Markdown'
        )


async def cleanup_game_buttons(context: ContextTypes.DEFAULT_TYPE, game: Game, chat_id: int):
    """Remove all buttons from lobby messages"""
    # Remove timer message button
    if hasattr(game, 'timer_message_id') and game.timer_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=game.timer_message_id,
                reply_markup=None
            )
            logger.debug("Removed timer message button")
        except Exception as e:
            logger.debug(f"Timer message button already removed: {e}")
    
    # Remove lobby message button
    if hasattr(game, 'lobby_message_id') and game.lobby_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=game.lobby_message_id,
                reply_markup=None
            )
            logger.debug("Removed lobby message button")
        except Exception as e:
            logger.debug(f"Lobby message button already removed: {e}")


async def cleanup_custom_game(chat_id: int):
    """Cleanup custom game configuration"""
    if chat_id in custom_game_configs:
        del custom_game_configs[chat_id]
        logger.info(f"Cleaned up custom game config for {chat_id}")
