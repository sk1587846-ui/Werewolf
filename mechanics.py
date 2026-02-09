import logging
import random
import asyncio
from datetime import datetime
from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import os

from enums import GamePhase, Team, Role
from game import Game, Player, active_games
from roles import ROLE_NARRATIVES, get_role_action_buttons, get_voting_buttons
from config import (
    PHASE_GIFS, 
    DEATH_GIFS, 
    ACTION_GIFS, 
    WIN_GIFS, 
    MISC_GIFS,
    NIGHT_ACTION_TIME_LIMIT, 
    VOTING_TIME_LIMIT, 
    DAY_DISCUSSION_TIME
)
from ranking import (
    record_batch_game_results, 
    generate_final_reveal_message,
    on_player_protect,
    on_player_vote_lynch,
    send_player_breakdowns,
    on_player_eliminated_early
)
from custom_game_handler import custom_game_configs
# ============================================================================
# COMPREHENSIVE SITUATION-SPECIFIC NARRATIVE MESSAGES
# ============================================================================

DEATH_NARRATIVES = {
    # ==================== WOLF SCENARIOS ====================
    "wolf_killed_by_hunter": {
        "wolf": "💀 **YOU HAVE BEEN KILLED**\n\nYou attacked the Hunter tonight.\nTheir reflexes were faster. An arrow pierced your heart.\n\nYou are now dead and cannot participate further.",
        "hunter": "🏹⚔️ **YOU WERE ATTACKED!**\n\nA wolf lunged at you in the darkness, but your reflexes were faster!\n\nYour arrow found its mark. The wolf lies dead at your feet.\nYou survived the night.",
        "pack": "🐺⚠️ **PACK ALERT**\n\nYour packmate {wolf_name} attacked the Hunter and was killed by their arrow.\n\nThe pack must be more careful...",
        "group": "🏹💀 **DEADLY DEFENSE**\n\n{wolf_name} attacked {hunter_name} in the darkness!\nBut the Hunter was faster—their arrow flew true.\n\nThe wolf lies dead. The Hunter survives."
    },
    
    "wolf_killed_by_serial_killer": {
        "wolf": "💀 **YOU HAVE BEEN KILLED**\n\nYou attacked the Serial Killer tonight.\nIt was a fatal mistake.\n\nYou are now dead and cannot participate further.",
        "sk": "🔪⚔️ **YOU WERE ATTACKED!**\n\nThe werewolves tried to hunt you tonight, but you fought back with deadly precision!\n\nOne of the wolves lies dead at your feet. Your bloodlust remains unsatisfied... for now.",
        "pack": "🐺⚠️ **PACK ALERT**\n\nYour packmate {wolf_name} attacked the Serial Killer and was killed in the confrontation.\n\nThe pack must be more careful...",
        "group": "🔪⚔️ **A PREDATOR FALLS**\n\n{wolf_name} hunted in the darkness, but encountered something more deadly.\nThe Serial Killer fought back with savage fury.\n\nWhen dawn broke, the wolf lay dead, torn to pieces."
    },
    
    "wolf_normal_kill": {
        "victim": "💀 **YOU HAVE BEEN KILLED**\n\nThe wolf struck before you could react.\nYour life ends in darkness.\n\nYou are dead.",
        "wolves": "🐺✅ **SUCCESSFUL HUNT**\n\nThe pack hunted {victim_name} tonight.\nTheir screams echo no more.\n\nAnother threat eliminated.",
        "group": "🌑 **SLAIN BY WOLVES**\n\nThe howls echoed through the darkness.\nWhen dawn broke, {victim_name} was found torn to pieces by savage claws."
    },
    
    # ==================== HUNTER SCENARIOS ====================
    "hunter_killed_by_wolves": {
        "hunter": "💀 **YOU HAVE BEEN KILLED**\n\nThe wolf struck before you could react.\nYour bow falls from your grasp.\n\nYou are dead.",
        "wolves": "🐺✅ **SUCCESSFUL HUNT**\n\nYou attacked the Hunter tonight.\nAfter a brief struggle, the pack prevailed.\n\nThe Hunter is dead.",
        "group": "🐺💀 **HUNTER FALLS**\n\n{hunter_name} fought bravely, but the wolves overwhelmed them.\nTheir bow lies shattered in the dirt."
    },
    
    "hunter_revenge_lynch_prompt": {
        "hunter": "🏹 **YOUR FINAL MOMENT**\n\nThe noose tightens, but you still have one arrow left.\n\nChoose wisely - you have 30 seconds:",
        "group_waiting": "🏹 {hunter_name} readies their final shot..."
    },
    
    "hunter_revenge_lynch_success": {
        "hunter": "🏹 You have shot {target_name}.",
        "group": "🏹💀 {hunter_name}'s arrow flies true and strikes {target_name}!\n\nBoth fall to the ground, dead."
    },
    
    "hunter_revenge_lynch_timeout": {
        "group": "🏹⏰ Time ran out! {hunter_name}'s final arrow flies wild and strikes {target_name}!"
    },
    
    "hunter_revenge_lynch_no_shot": {
        "group": "🏹 {hunter_name}'s bow falls from their grasp... no final shot."
    },
    
    "hunter_revenge_night_auto": {
        "hunter": "🏹⚔️ **AUTO-REVENGE ACTIVATED**\n\nAs you fall, your arrow flies instinctively!\nIt strikes {target_name} dead.\n\nYou take one of them with you.",
        "group": "🏹💀 **HUNTER'S REVENGE**\n\nAs {hunter_name} fell to the wolves, their final arrow struck {target_name}!\n\nBoth lie dead in the darkness."
    },
    
    # ==================== SERIAL KILLER SCENARIOS ====================
    "sk_killed_hunter": {
        "sk": "🔪✅ **SUCCESSFUL KILL**\n\nYou hunted the Hunter tonight.\nYour blade was faster than their arrow.\n\nAnother victim falls to your cunning.",
        "hunter": "💀 **YOU HAVE BEEN KILLED**\n\nThe Serial Killer struck with deadly efficiency.\nYou reached for your bow, but it was too late.\n\nYour story ends here.",
        "group": "🔪💀 **BRUTAL MURDER**\n\n{hunter_name} was found in a pool of blood.\nThe wounds are methodical, precise, terrifying.\n\nThe Serial Killer strikes again."
    },
    
    "sk_killed_by_hunter": {
        "sk": "💀 **YOU HAVE BEEN KILLED**\n\nYou attacked the Hunter tonight.\nTheir reflexes were faster. An arrow found your heart.\n\nYour killing spree has ended.",
        "hunter": "🏹🔪 **DEADLY ENCOUNTER!**\n\nThe Serial Killer lunged at you with brutal precision!\nBut your hunter instincts kicked in—you fired first!\n\nThe Serial Killer lies dead. You survived the night.",
        "group": "🏹💀 **PREDATOR SLAIN**\n\n{hunter_name} confronted the Serial Killer in the darkness!\nA single arrow ended the killing spree.\n\n{sk_name} lies dead. The Hunter survives."
    },
    
    "sk_normal_kill": {
        "victim": "💀 **YOU HAVE BEEN KILLED**\n\nThe Serial Killer found you in the darkness.\nYour death was swift, methodical.\n\nYour story ends here.",
        "sk": "🔪✅ **ANOTHER VICTIM**\n\nYou hunted {victim_name} tonight.\nYour blade struck true.\n\nThe body count rises.",
        "group": "🔪 **BRUTAL MURDER**\n\n{victim_name} was found in a pool of blood.\nThe wounds are methodical, precise, terrifying.\n\nThis was no animal attack. A predator stalks the village."
    },
    
    # ==================== VIGILANTE SCENARIOS ====================
    "vigilante_killed_innocent": {
        "vigilante": "💀 **YOU KILLED AN INNOCENT**\n\n{victim_name} was a {role_name}—a member of the village.\n\nOverwhelmed by guilt, you take your own life.\n\nYou are now dead.",
        "victim": "💀 **YOU HAVE BEEN KILLED**\n\nThe Vigilante struck you down in the darkness.\nYou were innocent.\n\nYour story ends here.",
        "group": "⚔️💀 **VIGILANTE JUSTICE GONE WRONG**\n\nThe Vigilante killed {victim_name} in the shadows.\nBut {victim_name} was a {role_name}—innocent!\n\nOvercome with guilt, the Vigilante took their own life.\n\nTwo bodies lie in the dust."
    },
    
    "vigilante_killed_evil": {
        "vigilante": "⚔️✅ **JUSTICE SERVED**\n\nYou killed {victim_name} tonight.\nThey were {role_name}—evil purged from the village.\n\nYour conscience is clear.",
        "victim": "💀 **JUSTICE FINDS YOU**\n\nThe Vigilante's blade found you in the darkness.\nYour evil deeds end here.\n\nYou are dead.",
        "group": "⚔️💀 **VIGILANTE JUSTICE**\n\nJustice was swift and merciless.\n{victim_name} was executed in the shadows.\n\nThey were the {role_name}."
    },
    
    # ==================== FIRE TEAM SCENARIOS ====================
    "fire_douse": {
        "arsonist": "🔥 You have doused {target_name} in gasoline.\nThey reek of accelerant, ready to burn.",
        "fire_starter": "🔥 You have doused {target_name} in gasoline.\nThey are marked for the flames.",
        "target": None,  # Target doesn't know
        "group": None  # Hidden action
    },
    
    "fire_ignite": {
        "igniter": "🔥 You have ignited the fire! All doused players will burn tonight.",
        "doused_victim": "💀 **YOU BURN ALIVE**\n\nFlames erupt from nowhere!\nYour skin blisters, your lungs fill with smoke.\n\nYou were doused. Now you burn.\n\nYou are dead.",
        "group": "🔥💀 **INFERNO UNLEASHED**\n\n{victim_name} bursts into flames!\nTheir screams are drowned by the roaring fire.\n\nOnly ashes remain."
    },
    
    # ==================== WITCH SCENARIOS ====================
    "witch_poison": {
        "witch": "☠️✅ **POISON DELIVERED**\n\nYou poisoned {victim_name} tonight.\nThey will not see another dawn.",
        "victim": "💀 **POISONED**\n\nA foul substance courses through your veins.\nYour vision blurs, your heart slows...\n\nYou are dead.",
        "group": "☠️💀 **DARK MAGIC**\n\nA foul stench fills the air.\n{victim_name} lies still, poisoned by dark magic."
    },
    
    "witch_heal": {
        "witch": "💊✅ **LIFE RESTORED**\n\nYou used your heal potion on {target_name}.\nThey were dead, but now they live again.\n\nYour magic saved them.",
        "healed": "💊✨ **YOU HAVE BEEN REVIVED**\n\nDarkness surrounded you...\nBut a warm light pulled you back!\n\nYou are alive again!",
        "group": "✨ **MIRACULOUS REVIVAL**\n\n{healed_name} was dead...\nBut the Witch's magic brought them back to life!\n\nThey live once more."
    },
    
    # ==================== DOCTOR/PROTECTION SCENARIOS ====================
    "doctor_saved": {
        "doctor": "💊✅ **LIFE SAVED**\n\nYou healed {target_name} tonight.\nThey were attacked, but your medicine saved them.\n\nYou are a hero.",
        "saved": "💊 **YOU WERE SAVED**\n\nYou felt death's cold touch tonight...\nBut someone intervened. You survived.\n\nThank your guardian angel.",
        "group": "🙏 **DIVINE INTERVENTION**\n\nDeath came for {target_name}… but a gentle light shielded them.\nThey survived the night."
    },
    
    "doctor_wasted": {
        "doctor": "💊 **PROTECTION UNUSED**\n\nYou healed {target_name} tonight.\nFortunately, they were not attacked.\n\nYour protection went unused.",
        "protected": None,  # They don't know
        "group": None  # Hidden
    },
    
    "bodyguard_sacrifice": {
        "bodyguard": "💀 **HEROIC SACRIFICE**\n\nYou threw yourself in front of {target_name}!\nThe attack meant for them struck you instead.\n\nYou are now dead. But they live because of you.",
        "protected": "🛡️ **SOMEONE DIED FOR YOU**\n\nAn attack came in the darkness!\nBut someone leapt in front of you—taking the blow themselves.\n\nYou survived. They did not.",
        "group": "🛡️💀 **HEROIC SACRIFICE**\n\n{bodyguard_name} threw themselves in front of {target_name}!\nThey took the fatal blow.\n\n{bodyguard_name} is dead. {target_name} lives."
    },
    
    "bodyguard_wasted": {
        "bodyguard": "🛡️ **GUARD DUTY**\n\nYou guarded {target_name} tonight.\nFortunately, they were not attacked.\n\nYour watch was peaceful.",
        "protected": None,
        "group": None
    },
    
    # ==================== PRIEST SCENARIOS ====================
    "priest_prevented_conversion": {
        "priest": "⛪✅ **BLESSING SAVED THEM**\n\nYou blessed {target_name} tonight.\nThe wolves tried to convert them, but your blessing blocked it!\n\nThey remain pure.",
        "blessed": "⛪ **YOU FEEL PROTECTED**\n\nA holy warmth surrounds you.\nYou feel shielded from dark magic.",
        "group": None  # Hidden
    },
    
    "priest_blessed_but_killed": {
        "priest": "⛪ **BLESSING INCOMPLETE**\n\nYou blessed {target_name} tonight.\nYour blessing prevented conversion, but they were still killed.\n\nYour magic has limits.",
        "blessed": "⛪💀 **BLESSED BUT SLAIN**\n\nA holy warmth surrounds you... but it fades.\nThe blessing protected your soul, but not your body.\n\nYou are dead.",
        "group": None  # Hidden
    },
    
    # ==================== CONVERSION SCENARIOS ====================
    "alpha_wolf_conversion": {
        "converted": "🌑 **CURSED TRANSFORMATION**\n\nYour blood burns with the curse of the wolf.\nBy the next moonrise, you will howl with the pack.\n\nYou are now a Werewolf 🐺.",
        "wolves": "🐺✨ **NEW PACK MEMBER**\n\n{converted_name} has been bitten and turned!\nThey join the pack tonight.\n\nWelcome them, brothers.",
        "group": None  # Hidden from group
    },
    
    "cursed_villager_conversion": {
        "converted": "😨🐺 **THE CURSE AWAKENS**\n\nThe wolf's claws tore into you...\nBut instead of dying, something else happened.\n\nThe dormant curse activates. You are now a Werewolf 🐺!",
        "wolves": "🐺✨ **THE CURSE REVEALED**\n\n{converted_name} was a Cursed Villager!\nThe attack triggered their transformation.\n\nThey join the pack tonight!",
        "group": None  # Hidden from group
    },
    
    # ==================== PLAGUE SCENARIOS ====================
    "plague_infected": {
        "target": "🦠 You feel feverish and weak... something is wrong.\nYou have been **infected with the plague**!\n\nYou will succumb to the disease tomorrow night unless cured.",
        "plague_doctor": "🦠 You have infected {target_name} with the plague.\nThey will die in two nights unless saved.",
        "group": None  # Hidden
    },
    
    "plague_death": {
        "victim": "💀 **THE PLAGUE CLAIMS YOU**\n\nYour body burns with fever.\nThe infection has spread too far.\n\nYou succumb to the disease.",
        "group": "🦠💀 **PLAGUE VICTIM**\n\nThe disease finally claimed its victim.\n{victim_name} succumbed to the plague."
    },
    
    # ==================== LYNCH SCENARIOS ====================
    "lynch": {
        "victim": "💀 **THE VILLAGE HAS CONDEMNED YOU**\n\nThe rope tightens around your neck.\nThe mob's judgment is final.\n\nYour story ends here.",
        "group": "🔔💀 **LYNCHED**\n\nThe mob surrounds {victim_name}.\nBy the end of the day, the rope swings...\n\n{victim_name} is dead. They were the {role_name}."
    },
    
    "lynch_jester_win": {
        "jester": "🤡✅ **PERFECT DECEPTION**\n\nThey lynched you!\nYour foolish act was perfect.\n\n**YOU WIN!**",
        "group": "🔔💀 The mob surrounds {victim_name}.\nBy the end of the day, the rope swings…\n\nThey were the 🤡 **Jester**.\n\n🤡 The villagers laugh as the fool swings…\nYet the Jester grins. His twisted game is complete."
    },
    
    "lynch_executioner_win": {
        "executioner": "🪓✅ **TARGET ELIMINATED**\n\nYour target has been lynched!\nYour contract is complete.\n\n**YOU WIN!**",
        "group": "🔔💀 The mob surrounds {victim_name}.\nBy the end of the day, the rope swings…\n\nThey were the {role_name}.\n\n🪓 {executioner_name} smiles coldly. Their target has been eliminated.\nThe Executioner wins!"
    },
    
    # ==================== SPECIAL SCENARIOS ====================
    "lover_grief": {
        "lover": "💔 **YOUR BELOVED HAS FALLEN**\n\n{beloved_name} is dead.\nYou cannot bear to live without them.\n\nYou take your own life.\n\nYou are dead.",
        "group": "💔 {lover_name} dies of grief after {beloved_name}'s death.\n\nThe lovers are reunited in death."
    },
    
    "afk_removal": {
        "victim": "🚫 **REMOVED FOR INACTIVITY**\n\nYou've been inactive for {afk_count} consecutive rounds.\nYou have been removed from the game.",
        "group": "⏰ {victim_name} was removed from the game due to inactivity (AFK)."
    },
    
    "seer_inherit": {
        "apprentice": "🔮 **THE VISIONS COME TO YOU**\n\nThe Seer has fallen. Their visions now flow through you.\n\nYou are now the Seer.",
        "group": None  # Hidden
    },
    
    "executioner_target_died": {
        "executioner": "💔 **YOUR TARGET HAS DIED**\n\nYour target died without being lynched.\nYour contract is void.\n\nYou are now a regular Villager.",
        "group": None  # Hidden
    },
    
    # ==================== PEACEFUL SCENARIOS ====================
    "no_deaths": {
        "group": "🌙 The night passed quietly… no blood was spilled.\n\nEveryone survived the night."
    },
    
    "no_lynch_tie": {
        "group": "🤔 The villagers argue until the sun sets.\nNo one was chosen today. (Tie between: {candidates})\n\nThe shadows return as night begins."
    },
    
    "no_lynch_abstain": {
        "group": "🤔 The villagers mostly abstained. No one is lynched today.\n\nThe night falls peacefully."
    }
}


def get_death_narrative(situation: str, role: str, **kwargs) -> str:
    """Get narrative message for a specific death situation and role"""
    narratives = DEATH_NARRATIVES.get(situation, {})
    message = narratives.get(role)
    
    if message is None:
        return None
    
    # Format with provided kwargs
    try:
        return message.format(**kwargs)
    except (KeyError, ValueError) as e:
        logger.warning(f"Failed to format narrative {situation}/{role}: {e}")
        return message

logger = logging.getLogger(__name__)

async def send_role_assignments(context: ContextTypes.DEFAULT_TYPE, game: Game):
    """Send role assignments to all players via DM with images"""
    logger.info(f"Sending role assignments for game {game.group_id}")
    
    from config import ROLE_IMAGES
    
    for player in game.players.values():
        if not player.role:
            continue

        narrative = ROLE_NARRATIVES.get(player.role, "You have been assigned a role.")
        
        # Handle special roles (like Executioner with target)
        if player.role == Role.EXECUTIONER and player.executioner_target:
            target = game.players[player.executioner_target]
            narrative = narrative.format(target=target.mention)

        # Prepare caption
        caption = f"🎭 **Your Role:** {player.role.emoji} {player.role.role_name}\n\n{narrative}"
        
        try:
            # Try to send image with caption
            image_path = ROLE_IMAGES.get(player.role)
            
            if image_path:
                # METHOD 1: Local file
                if os.path.exists(image_path):
                    try:
                        with open(image_path, 'rb') as photo:
                            await context.bot.send_photo(
                                chat_id=player.user_id,
                                photo=photo,
                                caption=caption,
                                parse_mode='Markdown'
                            )
                        logger.debug(f"Sent role image from file to {player.first_name}")
                        continue
                    except Exception as e:
                        logger.warning(f"Failed to send local image for {player.role.role_name}: {e}")
                
                # METHOD 2: URL
                elif image_path.startswith('http://') or image_path.startswith('https://'):
                    try:
                        await context.bot.send_photo(
                            chat_id=player.user_id,
                            photo=image_path,
                            caption=caption,
                            parse_mode='Markdown'
                        )
                        logger.debug(f"Sent role image from URL to {player.first_name}")
                        continue
                    except Exception as e:
                        logger.warning(f"Failed to send URL image for {player.role.role_name}: {e}")
            
            # FALLBACK: Send text message if no image or image failed
            await context.bot.send_message(
                chat_id=player.user_id,
                text=caption,
                parse_mode='Markdown'
            )
            logger.debug(f"Sent role text to {player.first_name} (no image available)")
            
        except Exception as e:
            logger.error(f"Failed to send role to {player.first_name}: {e}")
            
            # Try to notify in group
            try:
                await context.bot.send_message(
                    chat_id=game.group_id,
                    text=f"⚠️ Could not send role to {player.mention}. Please start a chat with the bot first!",
                    parse_mode='Markdown'
                )
            except Exception as e2:
                logger.error(f"Failed to send group notification: {e2}")

async def send_gif_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    gif_key: str,
    gif_dict: dict,
    caption: str,
    parse_mode: str = 'Markdown'
) -> bool:
    """
    Universal GIF sender with fallback to text
    
    Args:
        context: Bot context
        chat_id: Target chat ID
        gif_key: Key to look up in gif_dict
        gif_dict: Dictionary of GIF paths (ACTION_GIFS, DEATH_GIFS, etc.)
        caption: Message caption/text
        parse_mode: Markdown or HTML
    
    Returns:
        True if sent successfully, False otherwise
    """
    gif_path = gif_dict.get(gif_key)
    success = False
    
    try:
        # Try local file
        if gif_path and os.path.exists(gif_path):
            try:
                with open(gif_path, 'rb') as gif_file:
                    await context.bot.send_animation(
                        chat_id=chat_id,
                        animation=gif_file,
                        caption=caption,
                        parse_mode=parse_mode
                    )
                logger.debug(f"✅ Sent GIF: {gif_key}")
                return True
            except Exception as e:
                logger.warning(f"⚠️ GIF failed ({gif_key}): {e}")
        
        # Try URL (if path is URL)
        elif gif_path and (gif_path.startswith('http://') or gif_path.startswith('https://')):
            try:
                await context.bot.send_animation(
                    chat_id=chat_id,
                    animation=gif_path,
                    caption=caption,
                    parse_mode=parse_mode
                )
                logger.debug(f"✅ Sent GIF URL: {gif_key}")
                return True
            except Exception as e:
                logger.warning(f"⚠️ GIF URL failed ({gif_key}): {e}")
        
        # Fallback to text
        await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode=parse_mode
        )
        logger.debug(f"📝 Sent text fallback for: {gif_key}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send message for {gif_key}: {e}")
        return False

async def send_phase_message(context: ContextTypes.DEFAULT_TYPE, game: Game, phase: str):
    """Send phase transition message with GIF and proper tracking"""
    
    # Initialize sent_phases tracker
    if not hasattr(game, 'sent_phases'):
        game.sent_phases = {}
    
    phase_key = f"{phase}_{game.day_number}"
    
    # Check if successfully sent
    if game.sent_phases.get(phase_key, False):
        logger.info(f"Phase {phase} day {game.day_number} already sent successfully")
        return True
    
    messages = {
        "night_begins": (
            "🌑 *Night falls across the village...*\n"
            "The doors are bolted, the torches dim.\n"
            "🌘 The shadows rise to claim their prey."
        ),
        "day_begins": (
            "🌞 *Dawn breaks over the village...*\n"
            "The bells ring, and the villagers gather in the square.\n"
            "⚰️ Who did not survive the night?"
        ),
        "voting_begins": (
            "🗣️ *The villagers whisper, argue, and shout...*\n"
            "🪓 Today, one must be chosen.\n"
            "⚖️ Who will face the noose?"
        ),
        "game_end": (
            "🎉 *The game has ended!*\n"
            "See the final fates revealed."
        )
    }

    message = messages.get(phase, f"📢 **{phase.replace('_', ' ').title()}**")
    gif_path = PHASE_GIFS.get(phase)
    success = False
    
    try:
        # METHOD 1: Try local file
        if gif_path and os.path.exists(gif_path):
            try:
                with open(gif_path, 'rb') as gif_file:
                    await context.bot.send_animation(
                        chat_id=game.group_id,
                        animation=gif_file,
                        caption=message,
                        parse_mode='Markdown'
                    )
                logger.info(f"✅ Sent phase animation from file for {phase}")
                success = True
            except Exception as e:
                logger.warning(f"⚠️ Local file animation failed: {e}")
        
        # METHOD 2: Try URL (if gif_path is a URL)
        elif gif_path and (gif_path.startswith('http://') or gif_path.startswith('https://')):
            try:
                await context.bot.send_animation(
                    chat_id=game.group_id,
                    animation=gif_path,
                    caption=message,
                    parse_mode='Markdown'
                )
                logger.info(f"✅ Sent phase animation from URL for {phase}")
                success = True
            except Exception as e:
                logger.warning(f"⚠️ URL animation failed: {e}")
        
        # METHOD 3: Fallback to text message
        if not success:
            await context.bot.send_message(
                chat_id=game.group_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"📝 Sent phase text fallback for {phase}")
            success = True
            
    except Exception as e:
        logger.error(f"❌ Failed to send any message for {phase}: {e}")
        success = False
    
    # Mark as sent only if successful
    game.sent_phases[phase_key] = success
    
    # Cleanup old phase tracking
    if success and game.day_number > 2:
        old_keys = [k for k in game.sent_phases.keys() 
                   if k.split('_')[-1].isdigit() and 
                      int(k.split('_')[-1]) < game.day_number - 1]
        for old_key in old_keys:
            del game.sent_phases[old_key]
    
    return success

def player_has_pending_action(player: Player, game: Game) -> bool:
    # Checks if player has pending night/time actions
    buttons = get_role_action_buttons(player, game, game.phase)
 # or whichever function you use
    return bool(buttons)


async def send_player_status(context: ContextTypes.DEFAULT_TYPE, game: Game):
    """Send current player status to group chat"""
    alive_count = len(game.get_alive_players())
    dead_count = len(game.dead_players)
    
    status_lines = [
        f"🌅 Dawn breaks over the bloodied village...",
        f"The villagers gather in fear, counting their numbers.",
        f"",
        f"💀 Lost: {dead_count} | 🙏 Alive: {alive_count}",
        f"",
        f"📜 Status:"
    ]

    # List all players with status
    for player in game.players.values():
        if player.is_alive:
            status_lines.append(f"🌱 {player.mention} — Alive")
        else:
            role_info = f" ({player.role.emoji} {player.role.role_name})" if player.role else ""
            status_lines.append(f"⚱️ {player.mention} — Dead{role_info}")

    message = "\n".join(status_lines) + "\n"
    
    try:
        await context.bot.send_message(
            chat_id=game.group_id,
            text=message,
            parse_mode='Markdown'
        )
        logger.info(f"Sent player status to group {game.group_id}")
    except Exception as e:
        logger.error(f"Failed to send player status: {e}")

async def handle_two_player_resolution(context: ContextTypes.DEFAULT_TYPE, game: Game) -> bool:
    """
    Handle automatic resolution when only 2 players remain.
    Returns True if game ended, False otherwise.
    """
    alive_players = game.get_alive_players()
    
    if len(alive_players) != 2:
        return False
    
    logger.info(f"Only 2 players remain - checking for automatic resolution")
    
    p1, p2 = alive_players[0], alive_players[1]
    
    # Check if Fire Team member with doused target
    fire_roles = {Role.ARSONIST, Role.BLAZEBRINGER, Role.ACCELERANT_EXPERT}
    if p1.role in fire_roles and getattr(p2, 'is_doused', False):
        await context.bot.send_message(
            chat_id=game.group_id,
            text=f"🔥 **FINAL INFERNO**\n\n{p1.mention} ignites the flames!\n{p2.mention} burns to death!\n\nThe village is consumed by fire.",
            parse_mode='Markdown'
        )
        await kill_player(context, game, p2, "fire")
        winner = game.check_win_condition()
        if winner:
            await end_game(context, game, winner)
            return True
    
    elif p2.role in fire_roles and getattr(p1, 'is_doused', False):
        await context.bot.send_message(
            chat_id=game.group_id,
            text=f"🔥 **FINAL INFERNO**\n\n{p2.mention} ignites the flames!\n{p1.mention} burns to death!\n\nThe village is consumed by fire.",
            parse_mode='Markdown'
        )
        await kill_player(context, game, p1, "fire")
        winner = game.check_win_condition()
        if winner:
            await end_game(context, game, winner)
            return True
    
    # Check for Wolf vs Hunter (50% chance each)
    wolf_roles = {Role.WEREWOLF, Role.ALPHA_WOLF}
    
    if p1.role in wolf_roles and p2.role == Role.HUNTER:
        logger.info("2-player: Wolf vs Hunter confrontation")
        if random.random() < 0.5:
            await context.bot.send_message(
                chat_id=game.group_id,
                text=f"🏹⚔️ **FINAL SHOWDOWN**\n\n{p1.mention} lunges at {p2.mention}!\nBut the Hunter's arrow flies faster!\n\nThe wolf falls dead.",
                parse_mode='Markdown'
            )
            await kill_player(context, game, p1, "hunter")
        else:
            await context.bot.send_message(
                chat_id=game.group_id,
                text=f"🐺⚔️ **FINAL SHOWDOWN**\n\n{p1.mention} strikes before {p2.mention} can react!\nThe Hunter falls to the wolf's claws.",
                parse_mode='Markdown'
            )
            await kill_player(context, game, p2, "wolves")
        
        winner = game.check_win_condition()
        if winner:
            await end_game(context, game, winner)
            return True
    
    elif p2.role in wolf_roles and p1.role == Role.HUNTER:
        logger.info("2-player: Hunter vs Wolf confrontation")
        if random.random() < 0.5:
            await context.bot.send_message(
                chat_id=game.group_id,
                text=f"🏹⚔️ **FINAL SHOWDOWN**\n\n{p2.mention} lunges at {p1.mention}!\nBut the Hunter's arrow flies faster!\n\nThe wolf falls dead.",
                parse_mode='Markdown'
            )
            await kill_player(context, game, p2, "hunter")
        else:
            await context.bot.send_message(
                chat_id=game.group_id,
                text=f"🐺⚔️ **FINAL SHOWDOWN**\n\n{p2.mention} strikes before {p1.mention} can react!\nThe Hunter falls to the wolf's claws.",
                parse_mode='Markdown'
            )
            await kill_player(context, game, p1, "wolves")
        
        winner = game.check_win_condition()
        if winner:
            await end_game(context, game, winner)
            return True
    
    # Check for Serial Killer vs Hunter (65% SK wins)
    if p1.role == Role.SERIAL_KILLER and p2.role == Role.HUNTER:
        logger.info("2-player: Serial Killer vs Hunter")
        if random.random() < 0.65:
            await context.bot.send_message(
                chat_id=game.group_id,
                text=f"🔪⚔️ **FINAL HUNT**\n\n{p1.mention} stalks {p2.mention} through the ruins!\nThe Serial Killer's blade finds its mark first!\n\nThe Hunter falls.",
                parse_mode='Markdown'
            )
            await kill_player(context, game, p2, "serial_killer")
        else:
            await context.bot.send_message(
                chat_id=game.group_id,
                text=f"🏹⚔️ **FINAL HUNT**\n\n{p2.mention} senses the predator's approach!\nOne perfect shot ends the killing spree!\n\nThe Serial Killer falls.",
                parse_mode='Markdown'
            )
            await kill_player(context, game, p1, "hunter")
        
        winner = game.check_win_condition()
        if winner:
            await end_game(context, game, winner)
            return True
    
    elif p2.role == Role.SERIAL_KILLER and p1.role == Role.HUNTER:
        logger.info("2-player: Hunter vs Serial Killer")
        if random.random() < 0.65:
            await context.bot.send_message(
                chat_id=game.group_id,
                text=f"🔪⚔️ **FINAL HUNT**\n\n{p2.mention} stalks {p1.mention} through the ruins!\nThe Serial Killer's blade finds its mark first!\n\nThe Hunter falls.",
                parse_mode='Markdown'
            )
            await kill_player(context, game, p1, "serial_killer")
        else:
            await context.bot.send_message(
                chat_id=game.group_id,
                text=f"🏹⚔️ **FINAL HUNT**\n\n{p1.mention} senses the predator's approach!\nOne perfect shot ends the killing spree!\n\nThe Serial Killer falls.",
                parse_mode='Markdown'
            )
            await kill_player(context, game, p2, "hunter")
        
        winner = game.check_win_condition()
        if winner:
            await end_game(context, game, winner)
            return True
    
    # Check for Evil vs Villager (Evil auto-wins)
    evil_teams = {Team.WOLF, Team.FIRE, Team.KILLER}
    
    if p1.role.team in evil_teams and p2.role.team == Team.VILLAGER:
        await context.bot.send_message(
            chat_id=game.group_id,
            text=f"💀 **INEVITABLE END**\n\n{p1.mention} corners the last villager!\n{p2.mention} has nowhere to run...\n\nEvil triumphs.",
            parse_mode='Markdown'
        )
        await kill_player(context, game, p2, "night")
        winner = game.check_win_condition()
        if winner:
            await end_game(context, game, winner)
            return True
    
    elif p2.role.team in evil_teams and p1.role.team == Team.VILLAGER:
        await context.bot.send_message(
            chat_id=game.group_id,
            text=f"💀 **INEVITABLE END**\n\n{p2.mention} corners the last villager!\n{p1.mention} has nowhere to run...\n\nEvil triumphs.",
            parse_mode='Markdown'
        )
        await kill_player(context, game, p1, "night")
        winner = game.check_win_condition()
        if winner:
            await end_game(context, game, winner)
            return True
    
    return False

async def process_night_actions(context: ContextTypes.DEFAULT_TYPE, game: Game):
    """Process all night actions and determine outcomes"""
    actions = game.night_actions
    killed_players = set()
    saved_players = []
    converted_players = []
    blocked_players = []   
    logger.info(f"=" * 60)
    logger.info(f"🌙 PROCESSING NIGHT {game.day_number} FOR GAME {game.group_id}")
    logger.info(f"📋 STORED ACTIONS ({len(actions)} total):")
    for key, value in actions.items():
        actor_name = game.players[value['actor']].first_name if value.get('actor') in game.players else 'Unknown'
        target_name = game.players[value['target']].first_name if value.get('target') and value['target'] in game.players else 'None'
        logger.info(f"   ✓ {key}: {actor_name} → {target_name}")
    logger.info(f"=" * 60)
    
    logger.info(f"Processing night actions for game {game.group_id}: {list(actions.keys())}")

    # Process blocking actions first
    for key in list(actions.keys()):
        if key.startswith("shaman_block_"):
            blocked_id = actions["shaman_block"]["target"]
            blocked_players.append(blocked_id)
            logger.debug(f"Wolf shaman blocked player {blocked_id}")

        if key.startswith("fire_starter_block_"):
            blocked_id = actions["fire_starter_block"]["target"]
            blocked_players.append(blocked_id)
            logger.debug(f"Fire starter blocked player {blocked_id}")

    # Collect wolf hunt votes
    wolf_hunt_votes = {}
    wolf_voters = {}  # Track which wolf voted for which target

    for key in list(actions.keys()):
        if key.startswith("wolf_hunt_") and not actions[key].get("handled", False):
            actor_id = actions[key]["actor"]
            target_id = actions[key]["target"]
        
            if target_id is not None:  # Skip if wolf skipped
                wolf_hunt_votes[target_id] = wolf_hunt_votes.get(target_id, 0) + 1
                if target_id not in wolf_voters:
                    wolf_voters[target_id] = []
                wolf_voters[target_id].append(actor_id)

# Process wolf hunt if there are votes
    if wolf_hunt_votes:
    # Find target with most votes
        max_votes = max(wolf_hunt_votes.values())
        candidates = [tid for tid, votes in wolf_hunt_votes.items() if votes == max_votes]
        wolf_victim = random.choice(candidates) if len(candidates) > 1 else candidates[0]
    
        victim = game.players[wolf_victim]
    
    # Determine which wolf actually attacks (for Hunter/SK counter)
        attacking_wolves = []
        for actor_id in wolf_voters.get(wolf_victim, []):
            wolf = game.players.get(actor_id)
            if wolf and wolf.is_alive and wolf.role in [Role.WEREWOLF, Role.ALPHA_WOLF]:
                attacking_wolves.append(wolf)
    
    # Sort by priority: WEREWOLF first, then ALPHA_WOLF
        if attacking_wolves:
            attacking_wolves.sort(key=lambda p: (0 if p.role == Role.WEREWOLF else 1))
            wolf_attacker = attacking_wolves[0]
            wolf_attacker_id = wolf_attacker.user_id
        else:
        # Fallback: use first voter
            wolf_attacker_id = wolf_voters[wolf_victim][0]
            wolf_attacker = game.players[wolf_attacker_id]
    
    # Check for Alpha Wolf conversion chance
        alive_wolves = [p for p in game.get_alive_players() if p.role in {Role.WEREWOLF, Role.ALPHA_WOLF, Role.WOLF_SHAMAN}]
        alpha_alive = any(p.role == Role.ALPHA_WOLF for p in alive_wolves)
    
    # Handle different victim types
        victim_handled = False
    
        # HUNTER - 50% chance to counter-kill attacker
        if victim.role == Role.HUNTER and victim.is_alive:
            logger.info(f"Hunter {victim.first_name} was attacked by wolves!")
    
            if random.random() < 0.5:
        # Hunter survives AND kills the wolf (50% chance)
                wolf_attacker.is_alive = False
                killed_players.add(wolf_attacker_id)
        
                try:
                    hunter_msg = get_death_narrative("wolf_killed_by_hunter", "hunter")
                    await context.bot.send_message(
                        chat_id=victim.user_id,
                        text=hunter_msg,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify Hunter: {e}")          
                try:
                    wolf_msg = get_death_narrative("wolf_killed_by_hunter", "wolf")
                    await context.bot.send_message(
                        chat_id=wolf_attacker_id,
                        text=wolf_msg,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify dead wolf: {e}")
        
        # Notify other wolves
                alive_wolves_remaining = [
                    p for p in game.get_alive_players() 
                    if p.role in [Role.WEREWOLF, Role.ALPHA_WOLF, Role.WOLF_SHAMAN]
                    and p.user_id != wolf_attacker_id
                ]
        
                for wolf in alive_wolves_remaining:
                    try:
                        pack_msg = get_death_narrative(
                            "wolf_killed_by_hunter", 
                            "pack", 
                            wolf_name=wolf_attacker.first_name
                        )
                        await context.bot.send_message(
                            chat_id=wolf.user_id,
                            text=pack_msg,
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify the hunter")       
                victim_handled = True
            else:
        # Hunter dies (50% chance)
                killed_players.add(wolf_victim)
                try:
                    hunter_death_msg = get_death_narrative("hunter_killed_by_wolves", "hunter")
                    await context.bot.send_message(
                        chat_id=victim.user_id,
                        text=hunter_death_msg,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify Hunter: {e}")
        
        
                victim_handled = True
    
    # CURSED VILLAGER - always converts
        elif victim.role == Role.CURSED_VILLAGER:
            converted_players.append(wolf_victim)
            logger.info(f"Cursed villager {victim.first_name} converted to wolf")
            victim_handled = True
    
    # SERIAL KILLER - 65% chance to kill the attacking wolf
        elif victim.role == Role.SERIAL_KILLER and victim.is_alive:
            logger.info(f"Serial Killer {victim.first_name} was attacked by wolves!")
        
            if random.random() < 0.65:
            # Serial Killer wins the confrontation
                wolf_attacker.is_alive = False
                killed_players.add(wolf_attacker_id)
            
                logger.info(f"Serial Killer {victim.first_name} killed wolf {wolf_attacker.first_name}!")
            
            # Notify Serial Killer of successful defense
                try:
                    await context.bot.send_message(
                        chat_id=victim.user_id,
                        text=(
                                "🔪⚔️ **YOU WERE ATTACKED!**\n\n"
                                "The werewolves tried to hunt you tonight, "
                                "but you fought back with deadly precision!\n\n"
                                "One of the wolves lies dead at your feet. "
                                "Your bloodlust remains unsatisfied... for now."
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify SK of successful defense: {e}")
            
            # Notify the dead wolf
                try:
                    await context.bot.send_message(
                        chat_id=wolf_attacker_id,
                        text=(
                                "💀 **YOU HAVE BEEN KILLED**\n\n"
                                "You attacked the Serial Killer tonight.\n"
                                "It was a fatal mistake.\n\n"
                                "You are now dead and cannot participate further."
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify dead wolf: {e}")
            
            # Notify other wolves in the pack
                alive_wolves = [
                    p for p in game.get_alive_players() 
                    if p.role in [Role.WEREWOLF, Role.ALPHA_WOLF, Role.WOLF_SHAMAN]
                    and p.user_id != wolf_attacker_id
                ]
            
                for wolf in alive_wolves:
                    try:
                        await context.bot.send_message(
                            chat_id=wolf.user_id,
                            text=(
                                    "🐺⚠️ **PACK ALERT**\n\n"
                                    f"Your packmate {wolf_attacker.first_name} attacked the Serial Killer "
                                    "and was killed in the confrontation.\n\n"
                                    "The pack must be more careful..."
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify pack of SK counter: {e}")
            
                victim_handled = True
            else:
            # Serial Killer loses (35% chance) - wolves win
                killed_players.add(wolf_victim)
                logger.info(f"Serial Killer {victim.first_name} was killed by wolves")
            
            # Notify Serial Killer of death
                try:
                    await context.bot.send_message(
                        chat_id=victim.user_id,
                        text=(
                                "💀 **YOU HAVE BEEN KILLED**\n\n"
                                "The werewolf pack surrounded you tonight.\n"
                                "You fought viciously, but there were too many.\n\n"
                                "Your reign of terror has ended."
                         ),
                         parse_mode="Markdown"
                     )
                except Exception as e:
                    logger.error(f"Failed to notify SK of death: {e}")
            
            # Notify attacking wolf of victory
                try:
                    await context.bot.send_message(
                        chat_id=wolf_attacker_id,
                        text=(
                                "🐺✅ **SUCCESSFUL HUNT**\n\n"
                                "You attacked the Serial Killer tonight.\n"
                                "After a vicious struggle, the pack prevailed.\n\n"
                                "The Serial Killer is dead."
                        ),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify wolf of SK kill: {e}")
            
                victim_handled = True
    
    # ALPHA WOLF CONVERSION (20% chance, not Cursed or SK)
        if not victim_handled and alpha_alive and random.random() < 0.2:
            converted_players.append(wolf_victim)
            logger.info(f"Alpha wolf converted {victim.first_name} into a wolf!")
            victim_handled = True
    
    # NORMAL KILL - if not handled by above cases
        if not victim_handled:
            killed_players.add(wolf_victim)
            logger.info(f"Wolf killed {victim.first_name}")
    
    # Mark action as handled
        for key in list(actions.keys()):
            if key.startswith("wolf_hunt_"):
                actions[key]["handled"] = True

    # Process protective actions
    protected_players = []
    for key in list(actions.keys()):
        if key.startswith("webkeeper_mark_"):
            try:
                webkeeper_id = int(key.split("_")[2])
            except (IndexError, ValueError):
                logger.error(f"Invalid webkeeper key: {key}")
                continue
                
            marked_id = actions[key]["target"]
            webkeeper = game.players.get(webkeeper_id)
            
            if webkeeper and webkeeper.is_alive:
                sk_team = [p for p in game.get_alive_players() if p.role.team == Team.KILLER]
                sk_ids = [p.user_id for p in sk_team]
                
                for action_key, action_data in list(actions.items()):
                    target = action_data.get("target")
                    if target in sk_ids or target == webkeeper_id:
                        actor_id = action_data.get("actor")
                        if actor_id and actor_id not in blocked_players:
                            blocked_players.append(actor_id)
                            logger.info(f"Webkeeper {webkeeper_id} blocked {actor_id}'s action")

    # Doctor protection
    for key in list(actions.keys()):
        if key.startswith("doctor_") and key.split("_")[1].isdigit():
            actor_id = int(key.split("_")[1])
            if actor_id not in blocked_players:
                protected_id = actions[key]["target"]
                protected_players.append(protected_id)
            
                target_was_attacked = protected_id in killed_players
            
                if target_was_attacked:
                    killed_players.remove(protected_id)
                    saved_players.append(protected_id)
                    logger.info(f"Doctor {actor_id} saved player {protected_id}")
            
                if not getattr(game, 'custom_game', False):
                    from ranking import on_player_protect
                    on_player_protect(actor_id, target_was_attacked)
                
                    doctor = game.players.get(actor_id)
                    if doctor:
                        if not hasattr(doctor, 'game_actions'):
                            doctor.game_actions = {}
                    
                        if target_was_attacked:
                            doctor.game_actions['successful_protection'] = doctor.game_actions.get('successful_protection', 0) + 1
                        else:
                            doctor.game_actions['wasted_protection'] = doctor.game_actions.get('wasted_protection', 0) + 1

    # Bodyguard protection
    for key in list(actions.keys()):
        if key.startswith("bodyguard_"):
            try:
                bodyguard_id = int(key.split("_")[1])
            except (IndexError, ValueError):
                logger.error(f"Invalid bodyguard key format: {key}")
            continue
            
            if bodyguard_id not in blocked_players:
                protected_id = actions[key]["target"]
        
                target_was_attacked = protected_id in killed_players
        
                if target_was_attacked:
                    if protected_id in killed_players:
                        killed_players.remove(protected_id)
                    saved_players.append(protected_id)
            
                    protected_player = game.players[protected_id]
                    if protected_player.role.team != Team.WOLF:
                        killed_players.add(bodyguard_id)
                        logger.info(f"Bodyguard {bodyguard_id} died protecting {protected_id}")

            # ADD THIS ENTIRE BLOCK
                if not getattr(game, 'custom_game', False):
                    from ranking import on_player_protect
                    on_player_protect(bodyguard_id, target_was_attacked)
            
                    bodyguard = game.players.get(bodyguard_id)
                    if bodyguard:
                        if not hasattr(bodyguard, 'game_actions'):
                            bodyguard.game_actions = {}
                
                        if target_was_attacked:
                        # Heroic sacrifice or successful save
                            bodyguard.game_actions['successful_protection'] = bodyguard.game_actions.get('successful_protection', 0) + 3  # Extra points for sacrifice
                        else:
                            bodyguard.game_actions['wasted_protection'] = bodyguard.game_actions.get('wasted_protection', 0) + 1

    # Priest blessing (prevents conversion)
    for key in list(actions.keys()):
        if key.startswith("priest_"):
            try:
                priest_id = int(key.split("_")[1])
            except (IndexError, ValueError):
                logger.error(f"Invalid priest key format: {key}")
                continue
            
            if priest_id not in blocked_players:
                blessed_id = actions[key]["target"]
                blessed_player = game.players.get(blessed_id)
            
                if blessed_player:
                    blessed_player.is_blessed = True
            
                    if blessed_id in converted_players:
                        converted_players.remove(blessed_id)
                    # Still killed by wolves if attacked
                        if wolf_victim == blessed_id:
                            killed_players.add(blessed_id)
                            logger.info(f"Blessed player {blessed_id} avoided conversion but died")
                
                    logger.info(f"Priest {priest_id} blessed {blessed_id}")
    for key in list(actions.keys()):
        if key.startswith("serial_killer_kill_"):
            try:
                sk_id = int(key.split("_")[3])
            except (IndexError, ValueError):
                logger.error(f"Invalid serial killer key: {key}")
                continue
                
            if sk_id in blocked_players:
                continue
                
            sk_victim_id = actions[key]["target"]
            sk_victim = game.players.get(sk_victim_id)
        
            if sk_victim and sk_victim.role == Role.HUNTER and sk_victim.is_alive:
                logger.info(f"Serial Killer {sk_id} attacked Hunter {sk_victim.first_name}!")
            
                if random.random() < 0.5:
                    # Hunter survives AND kills SK
                    serial_killer = game.players.get(sk_id)
                    serial_killer.is_alive = False
                    killed_players.add(sk_id)        
                    logger.info(f"Hunter {sk_victim.first_name} counter-killed Serial Killer!")
            
            # Notify Hunter (survived and killed SK)
                    try:
                        await context.bot.send_message(
                            chat_id=sk_victim.user_id,
                            text=(
                                "🏹🔪 **DEADLY ENCOUNTER!**\n\n"
                                "The Serial Killer lunged at you with brutal precision!\n"
                                "But your hunter instincts kicked in—you fired first!\n\n"
                                "The Serial Killer lies dead. You survived the night."
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify Hunter of SK counter-kill: {e}")
            
            # Notify Serial Killer (dead)
                    try:
                        await context.bot.send_message(
                            chat_id=sk_id,
                            text=(
                                "💀 **YOU HAVE BEEN KILLED**\n\n"
                                "You attacked the Hunter tonight.\n"
                                "Their reflexes were faster. An arrow found your heart.\n\n"
                                "Your killing spree has ended."
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify dead Serial Killer: {e}")
            
            # Don't add Hunter to killed list - they survived!
            
                else:
            # Hunter dies (50% chance)
                    killed_players.add(sk_victim_id)
                    logger.info(f"Serial Killer successfully killed Hunter {sk_victim.first_name}")
            
            # Notify Hunter (dead)
                    try:
                        await context.bot.send_message(
                            chat_id=sk_victim.user_id,
                            text=(
                                "💀 **YOU HAVE BEEN KILLED**\n\n"
                                "The Serial Killer struck with deadly efficiency.\n"
                                "You reached for your bow, but it was too late.\n\n"
                                "Your story ends here."
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify dead Hunter: {e}")
            
            # Notify Serial Killer (successful kill)
                    try:
                        await context.bot.send_message(
                            chat_id=sk_id,
                            text=(
                                "🔪✅ **SUCCESSFUL KILL**\n\n"
                                "You hunted the Hunter tonight.\n"
                                "Your blade was faster than their arrow.\n\n"
                                "Another victim falls to your cunning."
                            ),
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify Serial Killer of successful hunt: {e}")
    
            elif sk_victim and sk_victim.is_alive:
        # Normal Serial Killer kill (non-Hunter target)
                killed_players.add(sk_victim_id)
                logger.info(f"Serial Killer killed {sk_victim.first_name}")

    # Vigilante kill
    for key in list(actions.keys()):
        if key.startswith("vigilante_kill_"):
            try:
                vigilante_id = int(key.split("_")[2])
            except (IndexError, ValueError):
                logger.error(f"Invalid vigilante key: {key}")
                continue
                
            if vigilante_id in blocked_players:
                continue
                
            victim_id = actions[key]["target"]
            vigilante = game.players[vigilante_id]
            victim = game.players[victim_id]

            if victim.role.team == Team.VILLAGER:
                # Vigilante killed innocent
                vigilante.vigilante_killed_innocent = True
                killed_players.extend([vigilante_id, victim_id])
                logger.info(f"Vigilante {vigilante_id} killed innocent {victim_id} and committed suicide")
                
                if not getattr(game, 'custom_game', False):
                    if not hasattr(vigilante, 'game_actions'):
                        vigilante.game_actions = {}
                    vigilante.game_actions['vigilante_kill_village'] = vigilante.game_actions.get('vigilante_kill_village', 0) + 1
            else:
                # Vigilante killed evil
                killed_players.add(victim_id)
                logger.info(f"Vigilante {vigilante_id} killed evil {victim_id}")
                
                if not getattr(game, 'custom_game', False):
                    if not hasattr(vigilante, 'game_actions'):
                        vigilante.game_actions = {}
                    vigilante.game_actions['lynch_evil'] = vigilante.game_actions.get('lynch_evil', 0) + 2


# Poison effect (kills target)
    for key in list(actions.keys()):
        if key.startswith("witch_poison_"):
            try:
                witch_id = int(key.split("_")[2])
            except (IndexError, ValueError):
                logger.error(f"Invalid witch poison key: {key}")
                continue
                
            poisoned_id = actions[key]["target"]
            poisoned_player = game.players.get(poisoned_id)
            
            if poisoned_player and poisoned_player.is_alive:
                killed_players.add(poisoned_id)
                logger.info(f"Witch {witch_id} poisoned {poisoned_player.first_name}")
                
                if not getattr(game, 'custom_game', False):
                    witch = game.players.get(witch_id)
                    if witch:
                        if not hasattr(witch, 'game_actions'):
                            witch.game_actions = {}
                        
                        if poisoned_player.role.team != Team.VILLAGER:
                            witch.game_actions['witch_poison_evil'] = witch.game_actions.get('witch_poison_evil', 0) + 2
                        else:
                            witch.game_actions['major_mistake'] = witch.game_actions.get('major_mistake', 0) + 1

    for key in list(actions.keys()):
        if key.startswith("witch_heal_"):
            try:
                witch_id = int(key.split("_")[2])
            except (IndexError, ValueError):
                logger.error(f"Invalid witch heal key: {key}")
                continue
                
            healed_id = actions[key]["target"]
            healed_player = game.players.get(healed_id)
            
            if healed_player and not healed_player.is_alive:
                healed_player.is_alive = True
                if healed_player in game.dead_players:
                    game.dead_players.remove(healed_player)
                logger.info(f"Witch {witch_id} revived {healed_player.first_name}")

# 🔥 IMPROVED FIRE TEAM DOUSING LOGIC
# --- Replacement Dousing Logic ---

    # 🔥 FIXED FIRE TEAM DOUSING LOGIC
    doused_targets = []
    boosted_douse = False
    
    # Check for accelerant boost from ANY accelerant expert
    for key in list(actions.keys()):
        if key.startswith("accelerant_expert_used_"):
            try:
                expert_id = int(key.split("_")[3])
            except (IndexError, ValueError):
                continue
                
            if expert_id not in blocked_players:
                boosted_douse = True
                logger.info(f"Accelerant Expert {expert_id} boost active")
                break

    if boosted_douse:
        # Find the arsonist and give them 3 douses
        for key in list(actions.keys()):
            if key.startswith("arsonist_douse_"):
                parts = key.split("_")
                if len(parts) >= 4 and parts[3].isdigit():
                    arsonist_id = int(parts[2])
                    douse_num = int(parts[3])
                    
                    if arsonist_id not in blocked_players and douse_num <= 3:
                        target_id = actions[key]["target"]
                        target_player = game.players.get(target_id)
                        if target_player and target_player.is_alive and not getattr(target_player, 'is_doused', False):
                            doused_targets.append(target_id)
                            logger.info(f"Arsonist {arsonist_id} boosted douse #{douse_num}: {target_player.first_name}")
    else:
        # Normal mode: Fire Team votes on ONE target
        douse_votes = {}
        
        # Collect votes from ALL arsonists and blazebringers
        for key in list(actions.keys()):
            if key.startswith("arsonist_douse_"):
                try:
                    arsonist_id = int(key.split("_")[2])
                except (IndexError, ValueError):
                    continue
                    
                if arsonist_id not in blocked_players:
                    target_id = actions[key]["target"]
                    douse_votes[target_id] = douse_votes.get(target_id, 0) + 1
            
            elif key.startswith("fire_starter_douse_"):
                try:
                    fire_starter_id = int(key.split("_")[3])
                except (IndexError, ValueError):
                    continue
                    
                if fire_starter_id not in blocked_players:
                    target_id = actions[key]["target"]
                    douse_votes[target_id] = douse_votes.get(target_id, 0) + 1
        
        # Select ONE target based on votes
        if douse_votes:
            max_votes = max(douse_votes.values())
            candidates = [pid for pid, count in douse_votes.items() if count == max_votes]
            
            valid_candidates = [
                pid for pid in candidates 
                if game.players.get(pid) 
                and game.players[pid].is_alive 
                and not getattr(game.players[pid], 'is_doused', False)
            ]
            
            if valid_candidates:
                chosen_target = random.choice(valid_candidates)
                doused_targets.append(chosen_target)
                logger.info(f"Fire Team consensus douse: {game.players[chosen_target].first_name}")
        
        # Blazebringer's 40% bonus douse (check ALL blazebringers)
        for key in list(actions.keys()):
            if key.startswith("fire_starter_douse_"):
                try:
                    fire_starter_id = int(key.split("_")[3])
                except (IndexError, ValueError):
                    continue
                    
                if fire_starter_id not in blocked_players:
                    if random.random() < 0.4:
                        alive_not_doused = [
                            p.user_id for p in game.get_alive_players() 
                            if p.user_id not in doused_targets 
                            and not getattr(p, 'is_doused', False)
                        ]
                        if alive_not_doused:
                            bonus_target = random.choice(alive_not_doused)
                            doused_targets.append(bonus_target)
                            logger.info(f"Blazebringer {fire_starter_id} bonus douse: {game.players[bonus_target].first_name}")
                        break  # Only one bonus per night

    # Mark all doused targets
    for doused_id in set(doused_targets):
        player = game.players.get(doused_id)
        if player and player.is_alive:
            player.is_doused = True
            logger.info(f"Player {player.first_name} is now doused")

    # ✅ FIX: Fire Team Ignite - Check ALL fire team members
    ignite_actor = None
    igniter_id = None
    
    for key in list(actions.keys()):
        if key.startswith("arsonist_ignite_"):
            try:
                igniter_id = int(key.split("_")[2])
                ignite_actor = "arsonist"
                break
            except (IndexError, ValueError):
                continue
        elif key.startswith("fire_starter_ignite_"):
            try:
                igniter_id = int(key.split("_")[3])
                ignite_actor = "fire_starter"
                break
            except (IndexError, ValueError):
                continue
        elif key.startswith("accelerant_expert_ignite_"):
            try:
                igniter_id = int(key.split("_")[3])
                ignite_actor = "accelerant_expert"
                break
            except (IndexError, ValueError):
                continue

    if ignite_actor and igniter_id:
        game.arsonist_ignited = True
        for player in game.players.values():
            if getattr(player, 'is_doused', False):
                killed_players.add(player.user_id)
        logger.info(f"{ignite_actor} {igniter_id} ignited, killing all doused players")

    # Check if Doppelganger needs to inherit a role after death
    for player in game.get_alive_players():
        if player.role == Role.CUPID and game.day_number == 1:
            if not hasattr(game, 'lovers_ids') or not game.lovers_ids:
                await send_cupid_target_menu(context, game, player)
                continue
            continue
        elif player.role == Role.DOPPELGANGER and player.doppelganger_copied_role is None:
            # Check if their chosen target died
            if hasattr(player, 'doppelganger_target_id') and player.doppelganger_target_id:
                target = game.players.get(player.doppelganger_target_id)
                if target and not target.is_alive and target.role:
                    # Copy the target's role
                    player.doppelganger_copied_role = target.role
                    player.role = target.role
                    try:
                        await context.bot.send_message(
                            chat_id=player.user_id,
                            text=f"🎭 Your target {target.first_name} has died!\n\nYou have become the {player.role.emoji} {player.role.role_name}.",
                            parse_mode='Markdown'
                        )
                        logger.info(f"Doppelganger {player.first_name} copied {target.first_name}'s role: {target.role.role_name}")
                    except Exception as e:
                        logger.error(f"Failed to notify Doppelganger {player.first_name}: {e}")
    # Process conversions
    for player_id in converted_players:
        player = game.players[player_id]
        player.role = Role.WEREWOLF
        await notify_player_converted(context, player)
        
        # Notify other wolves about new member
        wolves = game.get_players_by_team(Team.WOLF)
        for wolf in wolves:
            if wolf.user_id != player_id:
                try:
                    await context.bot.send_message(
                        chat_id=wolf.user_id,
                        text=f"🐺 {player.mention} has joined the pack!",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify wolf of conversion: {e}")


    game_ended = await handle_two_player_resolution(context, game)
    if game_ended:
        return

   
    # 1. Identify players dying from plague FIRST
    players_dying_from_plague = [
        p for p in game.players.values() 
        if getattr(p, 'is_plagued', False) and p.is_alive
    ]
    
    # 2. Process new infections from Plague Doctor's action
    newly_infected = set()
    
    for key in list(actions.keys()):
        if key.startswith("plague_doctor_infect_"):
            try:
                plague_id = int(key.split("_")[3])
            except (IndexError, ValueError):
                logger.error(f"Invalid plague doctor key: {key}")
                continue
                
            target_id = actions[key]["target"]
            target_player = game.players.get(target_id)
            
            if target_player and target_player.is_alive and not getattr(target_player, 'is_plagued', False):
                target_player.is_plagued = True
                newly_infected.add(target_id)
                logger.info(f"Plague Doctor {plague_id} infected {target_player.first_name}")

    # Process plague deaths and spread
    players_dying_from_plague = [
        p for p in game.players.values() 
        if getattr(p, 'is_plagued', False) and p.is_alive and p.user_id not in newly_infected
    ]
    
    # Spread infection through visits
    current_infected = [p for p in game.players.values() if getattr(p, 'is_plagued', False) and p.is_alive]
    
    for infected_player in current_infected:
        if infected_player.user_id in newly_infected:
            continue
        
        # Spread to visitors
        for visitor_id in getattr(infected_player, 'night_visits', []):
            visitor = game.players.get(visitor_id)
            if (visitor and visitor.is_alive and 
                not getattr(visitor, 'is_plagued', False) and
                visitor_id not in newly_infected):
                visitor.is_plagued = True
                newly_infected.add(visitor_id)
                logger.info(f"{visitor.first_name} infected by visiting plagued {infected_player.first_name}")
        
        # Spread to visited players
        for visited_id in getattr(infected_player, 'visited_players', []):
            visited = game.players.get(visited_id)
            if (visited and visited.is_alive and 
                not getattr(visited, 'is_plagued', False) and
                visited_id not in newly_infected):
                visited.is_plagued = True
                newly_infected.add(visited_id)
                logger.info(f"{visited.first_name} infected when plagued {infected_player.first_name} visited them")
    
    # Add plague deaths to kill list
    for plagued_player in players_dying_from_plague:
        killed_players.add(plagued_player.user_id)
        logger.info(f"Player {plagued_player.first_name} dying from plague")
    
    for player_id in killed_players:
        player = game.players[player_id]
        if player.is_alive:
            await kill_player(context, game, player, "night")

    # Notify newly infected players
    for infected_id in newly_infected:
        infected_player = game.players.get(infected_id)
        if infected_player and infected_player.is_alive:
            try:
                await context.bot.send_message(
                    chat_id=infected_player.user_id,
                    text="🦠 You feel feverish and weak... something is wrong.\n"
                         "You have been **infected with the plague**!\n"
                         "You will succumb to the disease tomorrow night unless cured.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify infected player: {e}")

    for key in list(actions.keys()):
        if key.startswith("seer_") and key.split("_")[1].isdigit():
            seer_id = int(key.split("_")[1])
            target_id = actions[key]["target"]
            seer = game.players.get(seer_id)
            target = game.players.get(target_id)
        
            if seer and seer.is_alive and target:
                alignment = "Villager" if target.role.team == Team.VILLAGER else "Evil"
                try:
                    await context.bot.send_message(
                        chat_id=seer.user_id,
                        text=f"🔮 **VISION REVEALED**\n\nYou see that {target.first_name} is aligned with the **{alignment}** team.",
                        parse_mode='Markdown'
                    )
                    if not getattr(game, 'custom_game', False):
                        from ranking import on_player_investigate
                        on_player_investigate(seer_id, target.role, target.role.team != Team.VILLAGER)
                        if not hasattr(seer, 'game_actions'):
                            seer.game_actions = {}
                    
                        if target.role.team != Team.VILLAGER:
                            seer.game_actions['investigate_evil'] = seer.game_actions.get('investigate_evil', 0) + 1
                        else:
                            seer.game_actions['investigate_wrong'] = seer.game_actions.get('investigate_wrong', 0) + 1
                    
                except Exception as e:
                    logger.error(f"Failed to send seer result: {e}")

    if "stray_observe" in actions:
        stray_id = actions["stray_observe"]["actor"]
        target_id = actions["stray_observe"]["target"]
        stray = game.players.get(stray_id)
        target = game.players.get(target_id)
        
        if stray and stray.is_alive and target:
            # Results will be sent at start of day phase
            pass

    for key in list(actions.keys()):
        if key.startswith("thief_steal_"):
            try:
                thief_id = int(key.split("_")[2])
            except (IndexError, ValueError):
                logger.error(f"Invalid thief key: {key}")
                continue
                
            target_id = actions[key]["target"]
            success = actions[key].get("success", False)
            
            if success:
                target_player = game.players.get(target_id)
                thief = game.players.get(thief_id)
                if thief and target_player:
                    thief.thief_stolen_role = target_player.role
                    thief.role = target_player.role
                    logger.info(f"Thief {thief_id} successfully stole {target_player.role.role_name}")
    
    # Mirror Phantom - steal from visitors
    for player in game.get_alive_players():
        if player.role == Role.MIRROR_PHANTOM and not getattr(player, 'mirror_ability_used', False):
            if hasattr(player, 'night_visits') and player.night_visits:
            # Get first visitor
                visitor_id = player.night_visits[0]
                visitor = game.players.get(visitor_id)
            
                if visitor and visitor.role and visitor.role != Role.VILLAGER:
                # Check if killer role attacks (50% kill chance)
                    if visitor.role in [Role.WEREWOLF, Role.ALPHA_WOLF, Role.SERIAL_KILLER, Role.VIGILANTE]:
                        if random.random() < 0.5:
                        # Killer succeeds - Mirror Phantom dies
                            killed_players.add(player.user_id)
                            logger.info(f"Mirror Phantom {player.first_name} was killed by {visitor.first_name}")
                        
                            try:
                                await context.bot.send_message(
                                    chat_id=player.user_id,
                                    text="🪞💀 **YOU WERE KILLED**\n\nA killer's strike shattered your reflection...",
                                    parse_mode='Markdown'
                                )
                            except Exception as e:
                                logger.error(f"Failed to notify killed Mirror Phantom: {e}")
                            continue  # Skip role exchange if dead
                
                # ROLE EXCHANGE (not just stealing)
                    stolen_role = visitor.role
                
                # Mirror Phantom becomes the visitor's role
                    player.mirror_stolen_role = stolen_role
                    player.role = stolen_role
                    player.mirror_ability_used = True
                    player.mirror_win_condition = stolen_role.team
                
                # Visitor becomes Mirror Phantom (CURSED)
                    visitor.role = Role.MIRROR_PHANTOM
                    visitor.mirror_ability_used = False  # They can now steal if visited
                
                    try:
                    # Notify Mirror Phantom (now has new role)
                        await context.bot.send_message(
                            chat_id=player.user_id,
                            text=f"🪞✨ **REFLECTION STOLEN!**\n\n"
                                 f"{visitor.first_name} visited you!\n\n"
                                 f"You absorbed their essence and became:\n"
                                 f"{player.role.emoji} **{player.role.role_name}**\n\n"
                                 f"They are now cursed as a Mirror Phantom.",
                            parse_mode='Markdown'
                        )
                    
                    # Notify visitor (now cursed as Mirror Phantom)
                        await context.bot.send_message(
                            chat_id=visitor.user_id,
                            text=f"🪞💀 **YOU HAVE BEEN CURSED!**\n\n"
                                 f"You visited the Mirror Phantom and your reflection was stolen!\n\n"
                                 f"You are now a **Mirror Phantom** yourself.\n"
                                 f"You cannot win - you can only observe and steal from visitors.\n\n"
                                 f"⚠️ **You lost your original role and win condition.**",
                            parse_mode='Markdown'
                        )
                    
                        logger.info(f"Mirror Phantom {player.first_name} stole {stolen_role.role_name} from {visitor.first_name}")
                        logger.info(f"{visitor.first_name} is now cursed as Mirror Phantom")
                    
                    except Exception as e:
                        logger.error(f"Failed to notify Mirror Phantom exchange: {e}")
    
    # Oracle results
    for key in list(actions.keys()):
        if key.startswith("oracle_"):
            try:
                oracle_id = int(key.split("_")[1])
            except (IndexError, ValueError):
                logger.error(f"Invalid oracle key format: {key}")
                continue
            
            target_id = actions[key]["target"]
            oracle = game.players.get(oracle_id)
            target = game.players.get(target_id)
        
            if oracle and oracle.is_alive and target:
                all_roles = [r for r in Role if r != target.role]
                not_role = random.choice(all_roles)
                try:
                    await context.bot.send_message(
                        chat_id=oracle.user_id,
                        text=f"🌟 **DIVINATION REVEALED**\n\nYou divine that {target.first_name} is **NOT** the {not_role.emoji} {not_role.role_name}.",
                        parse_mode='Markdown'
                    )
                    if not getattr(game, 'custom_game', False):
                        from ranking import on_player_investigate
                        on_player_investigate(oracle_id, target.role, True)                
                        if not hasattr(oracle, 'game_actions'):
                            oracle.game_actions = {}
                
                        oracle.game_actions['investigate_evil'] = oracle.game_actions.get('investigate_evil', 0) + 1
                
                except Exception as e:
                    logger.error(f"Failed to send oracle result: {e}")
    

    # Clear visits AFTER processing infections
    for p in game.players.values():
        if hasattr(p, 'night_visits'):
            p.night_visits.clear()
    
    # In process_night_actions, after processing all actions:
    for player in game.get_alive_players():
        if (player.role == Role.GRAVE_ROBBER and 
            getattr(player, 'grave_robber_act_tonight', False)):
        # They acted with borrowed role, now reset for next borrowing
            player.grave_robber_act_tonight = False
            player.grave_robber_can_borrow_tonight = True
            player.grave_robber_borrowed_role = None
            logger.info(f"Grave Robber {player.first_name} can borrow a new role next night")

    await send_night_outcome(context, game, killed_players, saved_players)

    for player_id in list(killed_players):  # Convert set to list
        player = game.players[player_id]
        if player.is_alive:  # Final safety check
            await kill_player(context, game, player, "night")


    # Clear night actions
    game.night_actions.clear()
    logger.info(f"Completed night action processing for game {game.group_id}")

async def kill_player(context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player, death_type: str):
    """Kill a player and handle death effects"""
    if not player.is_alive:
        logger.warning(f"Attempted to kill already dead player: {player.first_name}")
        return

    player.is_alive = False
    game.dead_players.append(player)

    # Track early elimination for ranking (non-custom games only)
    if not getattr(game, 'custom_game', False):
        if game.day_number <= 2:
            from ranking import on_player_eliminated_early
            on_player_eliminated_early(player.user_id)
    
    logger.info(f"Player {player.first_name} ({player.user_id}) died in game {game.group_id} ({death_type})")

    # ==================== SEND DEATH NOTIFICATION TO PLAYER ====================
    message = None
    
    if death_type == "night":
        # Check specific night scenarios
        if player.role == Role.HUNTER:
            message = get_death_narrative("hunter_killed_by_wolves", "hunter")
        else:
            # Generic night death (could be wolves, SK, etc.)
            message = get_death_narrative("wolf_normal_kill", "victim")
    
    elif death_type == "lynch":
        message = get_death_narrative("lynch", "victim")
    
    elif death_type == "hunter":
        # Killed by hunter's arrow
        target_name = player.first_name
        message = get_death_narrative("hunter_revenge_night_auto", "hunter", target_name=target_name)
    
    elif death_type == "serial_killer":
        message = get_death_narrative("sk_normal_kill", "victim")
    
    elif death_type == "fire":
        message = get_death_narrative("fire_ignite", "doused_victim")
    
    elif death_type == "afk":
        message = get_death_narrative("afk_removal", "victim", afk_count=player.afk_count)
    
    elif death_type == "wolves":
        message = get_death_narrative("wolf_normal_kill", "victim")
    
    elif death_type == "poison":
        message = get_death_narrative("witch_poison", "victim")
    
    elif death_type == "plague":
        message = get_death_narrative("plague_death", "victim")
    
    elif death_type == "vigilante":
        message = get_death_narrative("vigilante_killed_evil", "victim")
    
    # Fallback for unknown death types
    if not message:
        message = "💀 Darkness fell upon you… your story ends here."
    
    try:
        await context.bot.send_message(
            chat_id=player.user_id,
            text=message,
            parse_mode='Markdown'
        )
        logger.debug(f"Sent death notification to {player.first_name}")
    except Exception as e:
        logger.error(f"Failed to notify dead player: {e}")

    # ==================== HUNTER RETALIATION (NIGHT ONLY) ====================
    if player.role == Role.HUNTER and death_type == "night":
        wolves_alive = game.get_players_by_team(Team.WOLF)
        if wolves_alive:
            target_wolf = random.choice(wolves_alive)
            
            # Notify hunter of auto-revenge
            try:
                await context.bot.send_message(
                    chat_id=player.user_id,
                    text=get_death_narrative(
                        "hunter_revenge_night_auto",
                        "hunter",
                        target_name=target_wolf.first_name
                    ),
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify Hunter of auto-revenge: {e}")
            
            # Kill the wolf
            await kill_player(context, game, target_wolf, death_type="hunter_revenge")
            
            # Announce in group
            try:
                await context.bot.send_message(
                    chat_id=game.group_id,
                    text=get_death_narrative(
                        "hunter_revenge_night_auto",
                        "group",
                        hunter_name=player.mention,
                        target_name=target_wolf.mention
                    ),
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to announce Hunter revenge: {e}")
        
        # No shoot button next day because shot triggered immediately
        player.hunter_can_shoot = False

    # ==================== LOVER'S GRIEF ====================
    if player.lover_id and game.players[player.lover_id].is_alive:
        lover = game.players[player.lover_id]
        lover.is_alive = False
        lover.died_from_grief = True  # Flag for narrative detection
        game.dead_players.append(lover)
        
        # Notify lover with grief narrative
        try:
            await context.bot.send_message(
                chat_id=lover.user_id,
                text=get_death_narrative(
                    "lover_grief",
                    "lover",
                    beloved_name=player.first_name
                ),
                parse_mode='Markdown'
            )
            logger.info(f"Lover {lover.first_name} died of grief")
        except Exception as e:
            logger.error(f"Failed to notify grieving lover: {e}")
        
        # Announce in group with GIF
        await send_gif_message(
            context=context,
            chat_id=game.group_id,
            gif_key="lover_grief",
            gif_dict=DEATH_GIFS,
            caption=get_death_narrative(
                "lover_grief",
                "group",
                lover_name=lover.mention,
                beloved_name=player.mention
            ),
            parse_mode='Markdown'
        )

    # ==================== GRAVE ROBBER CLEANUP ====================
    if player.role == Role.GRAVE_ROBBER:
        player.grave_robber_act_tonight = False
        player.grave_robber_can_borrow_tonight = True
        player.grave_robber_borrowed_role = None

    # ==================== EXECUTIONER TARGET DIED (NOT LYNCHED) ====================
    if death_type != "lynch":
        for p in game.get_alive_players():
            if p.role == Role.EXECUTIONER and p.executioner_target == player.user_id:
                p.role = Role.VILLAGER  # Convert to villager
                try:
                    await context.bot.send_message(
                        chat_id=p.user_id,
                        text=get_death_narrative("executioner_target_died", "executioner"),
                        parse_mode='Markdown'
                    )
                    logger.info(f"Executioner {p.first_name} became Villager (target died)")
                except Exception as e:
                    logger.error(f"Failed to notify Executioner: {e}")

    # ==================== APPRENTICE SEER INHERITS POWER ====================
    if player.role == Role.SEER:
        game.seer_dead = True
        for p in game.get_alive_players():
            if p.role == Role.APPRENTICE_SEER:
                p.role = Role.SEER
                try:
                    await context.bot.send_message(
                        chat_id=p.user_id,
                        text=get_death_narrative("seer_inherit", "apprentice"),
                        parse_mode='Markdown'
                    )
                    logger.info(f"Apprentice Seer {p.first_name} inherited Seer powers")
                except Exception as e:
                    logger.error(f"Failed to notify new Seer: {e}")
                break

async def handle_hunter_revenge(context: ContextTypes.DEFAULT_TYPE, game: Game, hunter: Player):
    """Handle Hunter's final shot"""
    alive_players = game.get_alive_players()
    if not alive_players:
        logger.warning("Hunter died but no alive players for revenge")
        return

    # Create buttons for Hunter to choose target
    buttons = [
        [InlineKeyboardButton(f"🏹 Shoot {p.first_name}", callback_data=f"hunter_shoot_{p.user_id}")]
        for p in alive_players
    ]

    try:
        await context.bot.send_message(
            chat_id=hunter.user_id,
            text="🏹 You fall, but you have one final shot!\nChoose your target:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='Markdown'
        )
        logger.info(f"Sent Hunter revenge menu to {hunter.first_name}")
    except Exception as e:
        logger.error(f"Failed to send Hunter revenge menu: {e}")

async def notify_player_converted(context: ContextTypes.DEFAULT_TYPE, player: Player):
    """Notify player they've been converted to a wolf"""
    try:
        await context.bot.send_message(
            chat_id=player.user_id,
            text="🌑 Your blood burns with the curse of the wolf.\nBy the next moonrise, you will howl with the pack.\n\nYou are now a Werewolf 🐺.",
            parse_mode='Markdown'
        )
        logger.info(f"Notified {player.first_name} of conversion to wolf")
    except Exception as e:
        logger.error(f"Failed to notify converted player: {e}")

async def send_night_outcome(context: ContextTypes.DEFAULT_TYPE, game: Game, killed: List[int], saved: List[int]):
    """Send night outcome message to group with comprehensive narrative messages"""
    
    # ✅ CONVERT SET TO LIST if needed
    if isinstance(killed, set):
        killed = list(killed)
    
    # ✅ REMOVE THIS BROKEN CHECK - Players are already marked dead by kill_player()
    # We WANT to announce their deaths even though they're dead now!
    
    if killed:
        for player_id in killed:
            player = game.players[player_id]
            
            # ✅ FIXED: Only skip if this death was ALREADY announced
            if hasattr(player, '_death_announced') and player._death_announced:
                logger.warning(f"⚠️ Skipping duplicate death announcement for {player.first_name}")
                continue
            
            # Mark as announced to prevent duplicates in same night
            player._death_announced = True
            
            # Initialize
            caption = None
            gif_key = "unknown"
            
            logger.info(f"🎭 Processing death narrative for {player.first_name} (ID: {player_id})")
            
            
            # ==================== WOLF KILLS ====================
            # Check Wolf vs Serial Killer counter
            for key in list(game.night_actions.keys()):
                if key.startswith("wolf_hunt_"):
                    wolf_action = game.night_actions[key]
                    if wolf_action.get("actor") == player_id:
                        target_id = wolf_action.get("target")
                        if target_id:
                            target_player = game.players.get(target_id)
                            if target_player and target_player.role == Role.SERIAL_KILLER:
                                caption = get_death_narrative(
                                    "wolf_killed_by_serial_killer",
                                    "group",
                                    wolf_name=player.mention,
                                    sk_name=target_player.mention
                                )
                                gif_key = "serial_killer_defense"
                                logger.info(f"✅ Matched: Wolf killed by Serial Killer (gif={gif_key})")
                                break
            
            # Check Wolf vs Hunter counter
            if not caption:
                for key in list(game.night_actions.keys()):
                    if key.startswith("wolf_hunt_"):
                        wolf_action = game.night_actions[key]
                        if wolf_action.get("actor") == player_id:
                            target_id = wolf_action.get("target")
                            if target_id:
                                target_player = game.players.get(target_id)
                                if target_player and target_player.role == Role.HUNTER and target_player.is_alive:
                                    caption = get_death_narrative(
                                        "wolf_killed_by_hunter",
                                        "group",
                                        wolf_name=player.mention,
                                        hunter_name=target_player.mention
                                    )
                                    gif_key = "hunter_counter"
                                    logger.info(f"✅ Matched: Wolf killed by Hunter (gif={gif_key})")
                                    break
            
            # ==================== SERIAL KILLER SCENARIOS ====================
            # SK killed by Hunter
            if not caption and player.role == Role.SERIAL_KILLER:
                for key in list(game.night_actions.keys()):
                    if key.startswith("serial_killer_kill_"):
                        sk_action = game.night_actions[key]
                        target_id = sk_action.get("target")
                        if target_id:
                            target_player = game.players.get(target_id)
                            if target_player and target_player.role == Role.HUNTER and target_player.is_alive:
                                caption = get_death_narrative(
                                    "sk_killed_by_hunter",
                                    "group",
                                    hunter_name=target_player.mention,
                                    sk_name=player.mention
                                )
                                gif_key = "hunter_counter"
                                logger.info(f"✅ Matched: SK killed by Hunter (gif={gif_key})")
                                break
            
            # SK killed Hunter
            if not caption and player.role == Role.HUNTER:
                for key in list(game.night_actions.keys()):
                    if key.startswith("serial_killer_kill_"):
                        sk_action = game.night_actions[key]
                        if sk_action.get("target") == player_id:
                            sk_id = sk_action.get("actor")
                            sk_player = game.players.get(sk_id)
                            if sk_player:
                                caption = get_death_narrative(
                                    "sk_killed_hunter",
                                    "group",
                                    hunter_name=player.mention
                                )
                                gif_key = "serial_killer"
                                logger.info(f"✅ Matched: Hunter killed by SK (gif={gif_key})")
                                break
            
            # SK normal kill
            if not caption:
                for key in list(game.night_actions.keys()):
                    if key.startswith("serial_killer_kill_"):
                        sk_action = game.night_actions[key]
                        if sk_action.get("target") == player_id:
                            caption = get_death_narrative(
                                "sk_normal_kill",
                                "group",
                                victim_name=player.mention
                            )
                            gif_key = "serial_killer"
                            logger.info(f"✅ Matched: SK normal kill (gif={gif_key})")
                            break
            
            # ==================== HUNTER DEATHS ====================
            # Hunter killed by wolves (normal)
            if not caption and player.role == Role.HUNTER:
                for key in list(game.night_actions.keys()):
                    if key.startswith("wolf_hunt_"):
                        wolf_action = game.night_actions[key]
                        if wolf_action.get("target") == player_id:
                            caption = get_death_narrative(
                                "hunter_killed_by_wolves",
                                "group",
                                hunter_name=player.mention
                            )
                            gif_key = "wolves"
                            logger.info(f"✅ Matched: Hunter killed by wolves (gif={gif_key})")
                            break
            
            # ==================== VIGILANTE KILLS ====================
            if not caption:
                for key in list(game.night_actions.keys()):
                    if key.startswith("vigilante_kill_"):
                        vigilante_action = game.night_actions[key]
                        if vigilante_action.get("target") == player_id:
                            vigilante_id = vigilante_action.get("actor")
                            vigilante = game.players.get(vigilante_id)
                            
                            if player.role.team == Team.VILLAGER:
                                # Vigilante killed innocent
                                if vigilante and not vigilante.is_alive:
                                    caption = get_death_narrative(
                                        "vigilante_killed_innocent",
                                        "group",
                                        victim_name=player.mention,
                                        role_name=player.role.role_name
                                    )
                                    gif_key = "vigilante_fail"
                                    logger.info(f"✅ Matched: Vigilante killed innocent (gif={gif_key})")
                                else:
                                    caption = f"⚔️💀 {player.mention} was killed by the Vigilante.\nThey were the {player.role.emoji} {player.role.role_name}."
                                    gif_key = "vigilante"
                                    logger.info(f"✅ Matched: Vigilante killed (gif={gif_key})")
                            else:
                                # Vigilante killed evil
                                caption = get_death_narrative(
                                    "vigilante_killed_evil",
                                    "group",
                                    victim_name=player.mention,
                                    role_name=player.role.role_name
                                )
                                gif_key = "vigilante"
                                logger.info(f"✅ Matched: Vigilante killed evil (gif={gif_key})")
                            break
            
            # ==================== FIRE TEAM KILLS ====================
            # Fire ignite deaths
            if not caption and getattr(game, 'arsonist_ignited', False) and getattr(player, 'is_doused', False):
                caption = get_death_narrative(
                    "fire_ignite",
                    "group",
                    victim_name=player.mention
                )
                gif_key = "fire"
                logger.info(f"✅ Matched: Fire ignite (gif={gif_key})")
            
            # ==================== WITCH POISON ====================
            if not caption:
                for key in list(game.night_actions.keys()):
                    if key.startswith("witch_poison_"):
                        poison_action = game.night_actions[key]
                        if poison_action.get("target") == player_id:
                            caption = get_death_narrative(
                                "witch_poison",
                                "group",
                                victim_name=player.mention
                            )
                            gif_key = "poison"
                            logger.info(f"✅ Matched: Witch poison (gif={gif_key})")
                            break
            
            # ==================== PLAGUE DEATHS ====================
            if not caption and getattr(player, 'is_plagued', False):
                # Check if they were NEWLY infected this night (don't announce death for new infections)
                plague_action = None
                for key in list(game.night_actions.keys()):
                    if key.startswith("plague_doctor_infect_"):
                        if game.night_actions[key].get("target") == player_id:
                            plague_action = key
                            break
                
                if not plague_action:  # Not newly infected, died from existing plague
                    caption = get_death_narrative(
                        "plague_death",
                        "group",
                        victim_name=player.mention
                    )
                    gif_key = "plague"
                    logger.info(f"✅ Matched: Plague death (gif={gif_key})")
            
            # ==================== BODYGUARD SACRIFICE ====================
            if not caption:
                for key in list(game.night_actions.keys()):
                    if key.startswith("bodyguard_"):
                        bg_action = game.night_actions[key]
                        if bg_action.get("actor") == player_id:
                            protected_id = bg_action.get("target")
                            protected_player = game.players.get(protected_id)
                            if protected_player and protected_id in saved:
                                caption = get_death_narrative(
                                    "bodyguard_sacrifice",
                                    "group",
                                    bodyguard_name=player.mention,
                                    target_name=protected_player.mention
                                )
                                gif_key = "bodyguard_sacrifice"
                                logger.info(f"✅ Matched: Bodyguard sacrifice (gif={gif_key})")
                                break
            
            # ==================== WOLF NORMAL KILLS ====================
            if not caption:
                for key in list(game.night_actions.keys()):
                    if key.startswith("wolf_hunt_"):
                        wolf_action = game.night_actions[key]
                        if wolf_action.get("target") == player_id:
                            caption = get_death_narrative(
                                "wolf_normal_kill",
                                "group",
                                victim_name=player.mention
                            )
                            gif_key = "wolves"
                            logger.info(f"✅ Matched: Wolf normal kill (gif={gif_key})")
                            break
            
            # ==================== LOVER GRIEF ====================
            if not caption and hasattr(player, 'died_from_grief') and player.died_from_grief:
                lover_id = getattr(player, 'lover_id', None)
                beloved = game.players.get(lover_id) if lover_id else None
                if beloved:
                    caption = get_death_narrative(
                        "lover_grief",
                        "group",
                        lover_name=player.mention,
                        beloved_name=beloved.mention
                    )
                    gif_key = "lover_grief"
                    logger.info(f"✅ Matched: Lover grief (gif={gif_key})")
            
            # ==================== FALLBACK ====================
            if not caption:
                caption = f"💀 Death came for {player.mention} in the darkness. Their fate is sealed."
                gif_key = "death_generic"
                logger.warning(f"⚠️ Using fallback narrative for {player.first_name} (no specific scenario matched)")
            
            # ✅ LOG GIF ATTEMPT
            logger.info(f"🎬 Sending death message: player={player.first_name}, gif_key={gif_key}")
            logger.debug(f"   Caption preview: {caption[:100]}...")
            
            # Send the death message with GIF
            gif_sent = await send_gif_message(
                context=context,
                chat_id=game.group_id,
                gif_key=gif_key,
                gif_dict=DEATH_GIFS,
                caption=caption,
                parse_mode='Markdown'
            )
            
            # ✅ LOG RESULT
            if gif_sent:
                logger.info(f"✅ Successfully sent death message for {player.first_name}")
            else:
                logger.error(f"❌ Failed to send death message for {player.first_name}")
            
            await asyncio.sleep(1.5)

    # ==================== SAVED PLAYERS ====================
    if saved:
        logger.info(f"📢 Processing {len(saved)} saved players")
        for player_id in saved:
            player = game.players[player_id]
            
            # ✅ Skip if already dead (shouldn't happen, but safety check)
            if not player.is_alive:
                logger.warning(f"⚠️ Skipping save announcement for {player.first_name} (player is dead)")
                continue
            
            saved_by = "unknown"
            
            # Check who saved them
            for key in list(game.night_actions.keys()):
                if key.startswith("doctor_"):
                    doc_action = game.night_actions[key]
                    if doc_action.get("target") == player_id:
                        saved_by = "doctor"
                        logger.info(f"✅ {player.first_name} saved by Doctor")
                        break
                elif key.startswith("bodyguard_"):
                    bg_action = game.night_actions[key]
                    if bg_action.get("target") == player_id:
                        saved_by = "bodyguard"
                        logger.info(f"✅ {player.first_name} saved by Bodyguard")
                        break
            
            if saved_by == "doctor":
                save_message = get_death_narrative(
                    "doctor_saved",
                    "group",
                    target_name=player.mention
                )
                gif_key = "doctor_save"
            else:
                save_message = f"🙏 Death came for {player.mention}… but divine intervention kept them safe.\nThey survived the night."
                gif_key = "doctor_save"
            
            logger.info(f"🎬 Sending save message: player={player.first_name}, gif_key={gif_key}")
            
            gif_sent = await send_gif_message(
                context=context,
                chat_id=game.group_id,
                gif_key=gif_key,
                gif_dict=DEATH_GIFS,
                caption=save_message,
                parse_mode='Markdown'
            )
            
            if gif_sent:
                logger.info(f"✅ Successfully sent save message for {player.first_name}")
            else:
                logger.error(f"❌ Failed to send save message for {player.first_name}")
            
            await asyncio.sleep(1.5)

    # ==================== NO DEATHS ====================
    if not killed and not saved:
        logger.info(f"📢 No deaths tonight - sending peaceful message")
        
        peaceful_message = get_death_narrative("no_deaths", "group")
        
        logger.info(f"🎬 Sending no deaths GIF")
        
        gif_sent = await send_gif_message(
            context=context,
            chat_id=game.group_id,
            gif_key="no_deaths",
            gif_dict=DEATH_GIFS,
            caption=peaceful_message,
            parse_mode='Markdown'
        )
        
        if gif_sent:
            logger.info(f"✅ Successfully sent no deaths message")
        else:
            logger.error(f"❌ Failed to send no deaths message")
        
        await asyncio.sleep(1.5)
    
    logger.info(f"🏁 Completed send_night_outcome: {len(killed) if killed else 0} deaths, {len(saved) if saved else 0} saves")


# ============================================================
# ENHANCED GIF SENDER WITH BETTER LOGGING
# ============================================================
async def send_gif_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    gif_key: str,
    gif_dict: dict,
    caption: str,
    parse_mode: str = 'Markdown'
) -> bool:
    """
    Universal GIF sender with fallback to text and comprehensive logging
    """
    gif_path = gif_dict.get(gif_key)
    
    logger.info(f"🎬 GIF REQUEST: key='{gif_key}', path='{gif_path}'")
    
    # ✅ CHECK 1: Key exists in dictionary
    if gif_key not in gif_dict:
        logger.warning(f"⚠️ GIF key '{gif_key}' not found in gif_dict. Available keys: {list(gif_dict.keys())}")
    
    try:
        # Try local file
        if gif_path and os.path.exists(gif_path):
            logger.info(f"📁 Attempting local file: {gif_path}")
            try:
                # ✅ CHECK 2: File size
                file_size = os.path.getsize(gif_path)
                file_size_mb = file_size / (1024 * 1024)
                logger.info(f"📦 File size: {file_size_mb:.2f} MB")
                
                if file_size_mb > 50:
                    logger.error(f"❌ File too large: {file_size_mb:.2f} MB (Telegram limit: 50 MB)")
                    raise Exception("File too large for Telegram")
                
                with open(gif_path, 'rb') as gif_file:
                    await context.bot.send_animation(
                        chat_id=chat_id,
                        animation=gif_file,
                        caption=caption,
                        parse_mode=parse_mode
                    )
                logger.info(f"✅ Successfully sent local GIF: {gif_key}")
                return True
            except Exception as e:
                logger.error(f"❌ Local GIF failed ({gif_key}): {e}")
        
        # Try URL (if path is URL)
        elif gif_path and (gif_path.startswith('http://') or gif_path.startswith('https://')):
            logger.info(f"🌐 Attempting URL: {gif_path}")
            try:
                await context.bot.send_animation(
                    chat_id=chat_id,
                    animation=gif_path,
                    caption=caption,
                    parse_mode=parse_mode
                )
                logger.info(f"✅ Successfully sent URL GIF: {gif_key}")
                return True
            except Exception as e:
                logger.error(f"❌ URL GIF failed ({gif_key}): {e}")
        else:
            logger.warning(f"⚠️ No valid path for GIF key '{gif_key}'")
        
        # Fallback to text
        logger.info(f"📝 Sending text fallback for: {gif_key}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode=parse_mode
        )
        logger.info(f"✅ Text fallback sent successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Complete failure for {gif_key}: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

async def start_night_phase(context: ContextTypes.DEFAULT_TYPE, game: Game):
    """Start the night phase"""
    
    game.phase = GamePhase.NIGHT
    game.day_number += 1
    
    for p in game.players.values():
        p.has_acted = False
        p._death_announced = False
        # Initialize night_visits for EVERYONE
        if not hasattr(p, 'night_visits'):
            p.night_visits = []
        else:
            p.night_visits.clear()

        if not hasattr(p, 'visited_players'):
            p.visited_players = []
        else:
            p.visited_players.clear()
        
        # FIXED: Apply accelerant boost at START of night, then clear flag
        if p.role == Role.ARSONIST:
            p.douse_count_tonight = 0
            if getattr(p, 'accelerant_boost_next_night', False):
                p.max_douses_tonight = 3  # Boosted
                p.accelerant_boost_next_night = False  # Clear immediately
                logger.info(f"Arsonist {p.first_name} has accelerant boost: 3 douses")
            else:
                p.max_douses_tonight = 1  # Normal
    await send_phase_message(context, game, "night_begins")

    # In start_night_phase function, add this logic:
    for player in game.get_alive_players():
        # Special handling for Doppelganger on first night (choosing target)
        if player.role == Role.CUPID:
            # Check if lovers have been fully chosen
            if not hasattr(game, 'lovers_ids') or not game.lovers_ids or len(game.lovers_ids) < 2:
                # Only show on night 1 though
                if game.day_number == 1:
                    await send_cupid_target_menu(context, game, player)
                    continue
        
        # Special handling for Doppelganger on first night (choosing target)
        if player.role == Role.DOPPELGANGER and game.day_number == 1 and not hasattr(player, 'doppelganger_target_id'):
            await send_doppelganger_target_menu(context, game, player)
            continue
        
        if player.role == Role.GRAVE_ROBBER:
            # Initialize attributes if missing
            if not hasattr(player, 'grave_robber_can_borrow_tonight'):
                player.grave_robber_can_borrow_tonight = True
                player.grave_robber_act_tonight = False
                player.grave_robber_borrowed_role = None
                
            if (player.grave_robber_borrowed_role and 
                not getattr(player, 'grave_robber_can_borrow_tonight', True)):
                player.grave_robber_act_tonight = True
                logger.info(f"Grave Robber {player.first_name} can act with {player.grave_robber_borrowed_role.role_name} tonight")

    # Send action menus to players with night actions
    for player in game.get_alive_players():
        # Special handling for Grave Robber acting with borrowed role
        if (player.role == Role.GRAVE_ROBBER and
            getattr(player, 'grave_robber_act_tonight', False) and
            player.grave_robber_borrowed_role):
            
            original_role = player.role
            try:
                player.role = player.grave_robber_borrowed_role
                buttons = get_role_action_buttons(player, game, game.phase)
            finally:
                player.role = original_role  # Always restore
                
            if buttons:
                try:
                    borrowed_role_name = player.grave_robber_borrowed_role.role_name
                    msg = await context.bot.send_message(
                        chat_id=player.user_id,
                        text=f"🌙 Night {game.day_number}\n\n⚰️ Tonight you use the {borrowed_role_name}'s power!",
                        reply_markup=buttons,
                        parse_mode='Markdown'
                    )
                    player.last_action_message_id = msg.message_id
                    logger.debug(f"Sent borrowed role ({borrowed_role_name}) menu to Grave Robber {player.first_name}")
                except Exception as e:
                    logger.error(f"Failed to send borrowed role menu to {player.first_name}: {e}")
        
        else:
            # Regular button logic for all other players
            buttons = get_role_action_buttons(player, game, game.phase)
            if buttons:
                try:
                    role_name = player.role.role_name if player.role else "Unknown"
                    msg = await context.bot.send_message(
                        chat_id=player.user_id,
                        text=f"🌙 Night {game.day_number}\n\nWhat is your action, {role_name}?",
                        reply_markup=buttons,
                        parse_mode='Markdown'
                    )
                    player.last_action_message_id = msg.message_id  # store message id
                    player.has_acted_this_phase = False  # reset flag
                    logger.debug(f"Sent night menu to {player.first_name}")
                except Exception as e:
                    logger.error(f"Failed to send night menu to {player.first_name}: {e}")

    # Send team coordination messages
    await send_team_coordination(context, game)
    
    # Set timer for night phase
    game.phase_end_time = datetime.now().timestamp() + game.settings['night_time']

async def send_cupid_target_menu(context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player):
    """Send Cupid a menu to choose the first lover"""
    other_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]
    
    if len(other_players) < 2:
        logger.warning(f"Not enough players for Cupid to choose lovers")
        player.has_acted = True
        return
    
    buttons = [
        [InlineKeyboardButton(
            f"💘 Choose {p.first_name}", 
            callback_data=f"cupid_choose_{p.user_id}"
        )]
        for p in other_players
    ]
    
    try:
        msg = await context.bot.send_message(
            chat_id=player.user_id,
            text=(
                "💘 **Cupid - Bind Two Lovers**\n\n"
                "Choose the first person to be bound by love.\n"
                "Then you will choose a second person.\n\n"
                "⚠️ If one lover dies, the other dies too!\n"
                "Choose wisely - this decision is permanent!"
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='Markdown'
        )
        player.last_action_message_id = msg.message_id
        player.cupid_acted = True  # Mark as acted so they don't get menu again
        logger.info(f"Sent Cupid target menu to {player.first_name}")
    except Exception as e:
        logger.error(f"Failed to send Cupid menu to {player.first_name}: {e}")

async def send_doppelganger_target_menu(context: ContextTypes.DEFAULT_TYPE, game: Game, player: Player):
    """Send Doppelganger a menu to choose which player to copy when they die"""
    other_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]
    
    if not other_players:
        return
    
    buttons = [
        [InlineKeyboardButton(
            f"🎭 Choose {p.first_name}", 
            callback_data=f"doppelganger_choose_{p.user_id}"
        )]
        for p in other_players
    ]
    
    try:
        msg = await context.bot.send_message(
            chat_id=player.user_id,
            text=(
                "🎭 **Doppelganger - Choose Your Target**\n\n"
                "Choose a player to observe.\n"
                "When they die, you will take on their role and abilities.\n\n"
                "Choose wisely - this decision is permanent!"
            ),
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='Markdown'
        )
        player.last_action_message_id = msg.message_id
        logger.info(f"Sent Doppelganger target menu to {player.first_name}")
    except Exception as e:
        logger.error(f"Failed to send Doppelganger menu to {player.first_name}: {e}")

async def send_team_coordination(context: ContextTypes.DEFAULT_TYPE, game: Game):
    """Send team coordination messages to evil teams"""
    logger.debug(f"Sending team coordination for game {game.group_id}")
    
    # Wolf team coordination
    wolves = game.get_players_by_team(Team.WOLF)
    if len(wolves) > 1:
        wolf_names = [w.mention for w in wolves]
        wolf_message = f"🐺 Your pack: {', '.join(wolf_names)}\n\nCoordinate your hunt in this chat."
        
        for wolf in wolves:
            try:
                await context.bot.send_message(
                    chat_id=wolf.user_id,
                    text=wolf_message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to send wolf coordination to {wolf.first_name}: {e}")

    # Fire team coordination
    fire_team = game.get_players_by_team(Team.FIRE)
    if len(fire_team) > 1:
        fire_names = [f.mention for f in fire_team]
        fire_message = f"🔥 Your team: {', '.join(fire_names)}\n\nCoordinate your arson in this chat."
        
        for fire_player in fire_team:
            try:
                await context.bot.send_message(
                    chat_id=fire_player.user_id,
                    text=fire_message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to send fire coordination to {fire_player.first_name}: {e}")

    # Twins coordination
    if game.twins_ids and len(game.twins_ids) == 2:
        twin1 = game.players[game.twins_ids[0]]
        twin2 = game.players[game.twins_ids[1]]
        
        if twin1.is_alive and twin2.is_alive:
            try:
                await context.bot.send_message(
                    chat_id=twin1.user_id,
                    text=f"👥 Your twin: {twin2.mention}\nYou know they are pure.",
                    parse_mode='Markdown'
                )
                await context.bot.send_message(
                    chat_id=twin2.user_id,
                    text=f"👥 Your twin: {twin1.mention}\nYou know they are pure.",
                    parse_mode='Markdown'
                )
                logger.debug("Sent twins coordination")
            except Exception as e:
                logger.error(f"Failed to send twins coordination: {e}")

async def handle_hunter_lynch_revenge(context: ContextTypes.DEFAULT_TYPE, game: Game, hunter: Player):
    """Handle Hunter's 50% chance revenge shot after being lynched"""
    if not hunter.is_alive:
        logger.warning(f"Hunter {hunter.first_name} already dead - skipping revenge")
        return
    # ✅ 50% CHANCE CHECK FIRST (before killing hunter)
    if random.random() >= 0.9:
        # No revenge - kill hunter and proceed normally
        await kill_player(context, game, hunter, "lynch")
        
        await context.bot.send_message(
            chat_id=game.group_id,
            text=f"🏹 {hunter.mention}'s bow falls from their grasp... no final shot.",
            parse_mode='Markdown'
        )
        
        # Check win condition and proceed
        winner = game.check_win_condition()
        if winner:
            await end_game(context, game, winner)
        else:
            await asyncio.sleep(3)
            await start_night_phase(context, game)
        return
    
    # ✅ HUNTER GETS REVENGE - Set flags BEFORE showing menu
    game.waiting_for_hunter = True
    game.hunter_user_id = hunter.user_id
    game.phase = GamePhase.DAY  # Lock phase
    
    # Hunter is STILL ALIVE at this point
    alive_players = game.get_alive_players()
    
    if not alive_players:
        logger.warning("Hunter has revenge but no alive players to shoot")
        await kill_player(context, game, hunter, "lynch")
        
        # Clean up flags
        game.waiting_for_hunter = False
        game.hunter_user_id = None
        
        await asyncio.sleep(3)
        await start_night_phase(context, game)
        return
    
    # Set hunter flags
    hunter.hunter_can_shoot = True
    hunter.has_acted = False
    
    # Create shoot buttons
    buttons = [
        [InlineKeyboardButton(f"🏹 Shoot {p.first_name}", callback_data=f"hunter_shoot_{p.user_id}")]
        for p in alive_players
    ]
    
    try:
        msg = await context.bot.send_message(
            chat_id=hunter.user_id,
            text="🏹 **Your Final Moment**\n\nThe noose tightens, but you still have one arrow left.\n\nChoose wisely - you have 30 seconds:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='Markdown'
        )
        hunter.last_action_message_id = msg.message_id
        logger.info(f"Sent Hunter lynch revenge menu to {hunter.first_name}")
        
        # Notify group
        await context.bot.send_message(
            chat_id=game.group_id,
            text=f"🏹 {hunter.mention} readies their final shot...",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Failed to send Hunter revenge menu: {e}")
        
        # Fallback - auto-shoot random target
        await kill_player(context, game, hunter, "lynch")
        target = random.choice(alive_players)
        await kill_player(context, game, target, "hunter")
        
        await context.bot.send_message(
            chat_id=game.group_id,
            text=f"🏹 With dying breath, {hunter.mention} fires at {target.mention}!",
            parse_mode='Markdown'
        )
        
        # Clean up flags
        game.waiting_for_hunter = False
        game.hunter_user_id = None
        
        # Check win and proceed
        winner = game.check_win_condition()
        if winner:
            await end_game(context, game, winner)
        else:
            await asyncio.sleep(3)
            await start_night_phase(context, game)
        return
    
    # Set 30-second timer for Hunter action
    game.phase_end_time = datetime.now().timestamp() + 30
    
    logger.info(f"Waiting for Hunter {hunter.first_name} to shoot (30s timer)")

async def start_day_phase(context: ContextTypes.DEFAULT_TYPE, game: Game, lynch_target: Optional[Player] = None):
    """Start the day phase"""
    game.phase = GamePhase.DAY
    logger.info(f"Starting day {game.day_number} for game {game.group_id}")
    for p in game.players.values():
        p.has_acted = False

    for player in game.get_alive_players():
        if player.role == Role.STRAY and hasattr(player, 'stray_observed_target'):
            target_id = player.stray_observed_target
            target = game.players.get(target_id)
            
            if target and hasattr(target, 'night_visits') and target.night_visits:
                visitor_mentions = [game.players[uid].mention for uid in target.night_visits if uid in game.players]
                visits_text = ", ".join(visitor_mentions)
                try:
                    await context.bot.send_message(
                        chat_id=player.user_id,
                        text=f"🐾 **Your Observation**\n\n{target.first_name} was visited by: {visits_text}",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify Stray: {e}")
            else:
                try:
                    await context.bot.send_message(
                        chat_id=player.user_id,
                        text=f"🐾 **Your Observation**\n\n{target.first_name if target else 'Your target'} had no visitors last night.",
                        parse='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify Stray: {e}")
            
            player.stray_observed_target = None

    for player in game.get_alive_players():
        if player.role == Role.INSOMNIAC and player.is_alive:
            if player.night_visits:
                visitor_mentions = [game.players[uid].mention for uid in player.night_visits if uid in game.players]
                visits_text = ", ".join(visitor_mentions)
                try:
                    await context.bot.send_message(
                        chat_id=player.user_id,
                        text=f"👁️ During the night, you were visited by: {visits_text}."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify Insomniac {player.first_name} of visitors: {e}")
            else:
                try:
                    await context.bot.send_message(
                        chat_id=player.user_id,
                        text="👁️ During the night, no one visited you."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify Insomniac {player.first_name} of no visits: {e}")
            player.night_visits.clear()



    await process_night_actions(context, game)

    # Check win condition
    winner = game.check_win_condition()
    if winner:
        await end_game(context, game, winner)
        return


    # Send day message to group
    await send_phase_message(context, game, "day_begins")
    await send_player_status(context, game)

    for player in game.get_alive_players():
        buttons = get_role_action_buttons(player, game, game.phase)
        if buttons:
            try:
                role_name = player.role.role_name if player.role else "Unknown"
                msg = await context.bot.send_message(
                    chat_id=player.user_id,
                    text=f"☀️ Day {game.day_number}\n\nWhat is your action, {role_name}?",
                    reply_markup=buttons,
                    parse_mode='Markdown'
                )
                player.last_action_message_id = msg.message_id
                logger.debug(f"Sent day menu to {player.first_name}")
            except Exception as e:
                logger.error(f"Failed to send day menu to {player.first_name}: {e}")
    
    # Start voting phase after brief discussion time
    await asyncio.sleep(game.settings['day_time'])
    await start_voting_phase(context, game)

async def start_voting_phase(context: ContextTypes.DEFAULT_TYPE, game: Game):
    game.phase = GamePhase.VOTING
    game.votes.clear()

    # Reset vote tracking
    for player in game.players.values():
        player.has_acted = False
        player.has_voted = False
        player.voted_for = None
        player.votes_received = 0

    logger.info(f"Starting voting for day {game.day_number} in game {game.group_id}")

    # Detective investigation results - PROCESS ALL DETECTIVES
    for key in list(game.night_actions.keys()):
        if key.startswith("detective_"):
            try:
                detective_id = int(key.split("_")[1])
            except (IndexError, ValueError):
                logger.error(f"Invalid detective key format: {key}")
                continue
                
            target_id = game.night_actions[key]["target"]
            detective = game.players.get(detective_id)
            target = game.players.get(target_id)
        
            if detective and detective.is_alive and target:
                try:
                    await context.bot.send_message(
                        chat_id=detective.user_id,
                        text=f"🕵️ **INVESTIGATION COMPLETE**\n\n{target.first_name}'s role is {target.role.emoji} **{target.role.role_name}**.",
                        parse_mode='Markdown'
                    )
                    if not getattr(game, 'custom_game', False):
                        from ranking import on_player_investigate
                        on_player_investigate(detective_id, target.role, True)
                
                        if not hasattr(detective, 'game_actions'):
                            detective.game_actions = {}
                
                        # Detective gets exact role - bonus points
                        if target.role.team != Team.VILLAGER:
                            detective.game_actions['investigate_evil'] = detective.game_actions.get('investigate_evil', 0) + 2  # Double points
                        else:
                            detective.game_actions['investigate_evil'] = detective.game_actions.get('investigate_evil', 0) + 1  # Still useful info
                    
                except Exception as e:
                    logger.error(f"Failed to send detective result: {e}")

    # Send voting message to group
    await send_phase_message(context, game, "voting_begins")

    # Send voting buttons to all alive players
    for player in game.get_alive_players():
        buttons = get_voting_buttons(game, player.user_id)
        try:
            msg = await context.bot.send_message(
                chat_id=player.user_id,
                text="🗳️ Time to vote!\n\nWho do you believe is evil?",
                reply_markup=buttons,
                parse_mode='Markdown'
            )
            player.last_action_message_id = msg.message_id
            logger.debug(f"Sent voting menu to {player.first_name}")

        except Exception as e:
            logger.error(f"Failed to send voting menu to {player.first_name}: {e}")
 
    # Set timer for voting
    game.phase_end_time = datetime.now().timestamp() + game.settings['voting_time']

async def process_voting_results(context: ContextTypes.DEFAULT_TYPE, game: Game):
    """Process voting results and determine lynch target"""
    vote_counts = {}
    
    # Track votes ONLY for non-custom games
    if not getattr(game, 'custom_game', False):
        from ranking import on_player_vote_lynch
        
        for voter_id, target_id in game.votes.items():
            if target_id is not None:
                voter = game.players.get(voter_id)
                target = game.players.get(target_id)
                
                if voter and target:
                    # Call hook for stats database
                    on_player_vote_lynch(voter_id, target.role)
                    
                    # Track for point calculation
                    if not hasattr(voter, 'game_actions'):
                        voter.game_actions = {}
                    
                    if target.role.team != Team.VILLAGER:
                        # Voted for evil (good vote)
                        voter.game_actions['lynch_evil'] = voter.game_actions.get('lynch_evil', 0) + 1
                    else:
                        # Voted for villager (bad vote)
                        voter.game_actions['mislynch_village'] = voter.game_actions.get('mislynch_village', 0) + 1
    
    # ✅ COUNT VOTES FOR ALL GAMES (both custom and normal)
    for voter_id, target_id in game.votes.items():
        if target_id is not None:
            voter = game.players.get(voter_id)
            vote_weight = 2 if voter and voter.role == Role.MAYOR and voter.is_mayor_revealed else 1
            vote_counts[target_id] = vote_counts.get(target_id, 0) + vote_weight

    # ==================== NO VOTES - EVERYONE ABSTAINED ====================
    if not vote_counts:
        no_lynch_message = get_death_narrative("no_lynch_abstain", "group")
        
        await send_gif_message(
            context=context,
            chat_id=game.group_id,
            gif_key="no_lynch",
            gif_dict=MISC_GIFS,
            caption=no_lynch_message,
            parse_mode='Markdown'
        )
        
        await start_night_phase(context, game)
        return

    logger.info(f"Processing voting results for game {game.group_id}: {vote_counts}")

    # Find player(s) with most votes
    max_votes = max(vote_counts.values())
    lynch_candidates = [pid for pid, votes in vote_counts.items() if votes == max_votes]

    # ==================== TIE VOTE - NO LYNCH ====================
    if len(lynch_candidates) > 1:
        candidates = [game.players[pid].mention for pid in lynch_candidates]
        tie_message = get_death_narrative(
            "no_lynch_tie",
            "group",
            candidates=", ".join(candidates)
        )
        
        await send_gif_message(
            context=context,
            chat_id=game.group_id,
            gif_key="no_lynch",
            gif_dict=MISC_GIFS,
            caption=tie_message,
            parse_mode='Markdown'
        )
        
        # Check win condition after tie
        winner = game.check_win_condition()
        if winner:
            await end_game(context, game, winner)
            return

        await start_night_phase(context, game)
        return

    # ==================== LYNCH TARGET SELECTED ====================
    lynch_target_id = lynch_candidates[0]
    lynch_target = game.players[lynch_target_id]

    # ==================== JESTER WIN ====================
    if lynch_target.role == Role.JESTER:
        lynch_target.achieved_objective = True
        jester_message = get_death_narrative(
            "lynch_jester_win",
            "group",
            victim_name=lynch_target.mention
        )
        
        await send_gif_message(
            context=context,
            chat_id=game.group_id,
            gif_key="jester_win",
            gif_dict=WIN_GIFS,
            caption=jester_message,
            parse_mode='Markdown'
        )
        
        # Notify Jester personally
        try:
            await context.bot.send_message(
                chat_id=lynch_target.user_id,
                text=get_death_narrative("lynch_jester_win", "jester"),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify Jester: {e}")
        
        await end_game(context, game, Team.NEUTRAL)
        return

    # ==================== EXECUTIONER WIN ====================
    executioner = None
    for player in game.get_alive_players():
        if player.role == Role.EXECUTIONER and player.executioner_target == lynch_target_id:
            executioner = player
            executioner.achieved_objective = True
            break

    if executioner:
        exec_message = get_death_narrative(
            "lynch_executioner_win",
            "group",
            victim_name=lynch_target.mention,
            role_name=lynch_target.role.role_name,
            executioner_name=executioner.mention
        )
        
        await send_gif_message(
            context=context,
            chat_id=game.group_id,
            gif_key="executioner_win",
            gif_dict=WIN_GIFS,
            caption=exec_message,
            parse_mode='Markdown'
        )
        
        # Notify Executioner personally
        try:
            await context.bot.send_message(
                chat_id=executioner.user_id,
                text=get_death_narrative("lynch_executioner_win", "executioner"),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify Executioner: {e}")
        
        await end_game(context, game, Team.NEUTRAL)
        return

    # ==================== REGULAR LYNCH ====================
    lynch_message = get_death_narrative(
        "lynch",
        "group",
        victim_name=lynch_target.mention,
        role_name=lynch_target.role.role_name
    )
    
    await send_gif_message(
        context=context,
        chat_id=game.group_id,
        gif_key="lynch",
        gif_dict=DEATH_GIFS,
        caption=lynch_message,
        parse_mode='Markdown'
    )
    
    # ==================== HUNTER LYNCH REVENGE ====================
    if lynch_target.role == Role.HUNTER:
        # Don't kill hunter yet - let handle_hunter_lynch_revenge decide
        await handle_hunter_lynch_revenge(context, game, lynch_target)
        return  # Don't proceed to night yet - waiting for hunter shot
    
    # ==================== NON-HUNTER LYNCH ====================
    # Kill the lynched player
    await kill_player(context, game, lynch_target, "lynch")

    # Check win condition
    winner = game.check_win_condition()
    if winner:
        await end_game(context, game, winner)
    else:
        # Continue to next night
        await asyncio.sleep(5)
        await start_night_phase(context, game)
        
        # Reset detective flags for new day
        for player in game.get_alive_players():
            if player.role == Role.DETECTIVE:
                player.detective_acted_today = False
async def end_game(context: ContextTypes.DEFAULT_TYPE, game: Game, winner: Team):
    """End the game with thematic reveal message"""
    if game.phase == GamePhase.ENDED:
        return
        
    game.phase = GamePhase.ENDED
    logger.info(f"Game {game.group_id} ended. Winner: {winner}")

    # ✅ FIXED: Properly normalize winner to uppercase string
    if isinstance(winner, tuple):
        winner = winner[0]
    
    # Get the actual Team enum, not just the name/value
    if isinstance(winner, Team):
        winning_team = winner
        winning_team_name = winner.name.upper()  # Use .name not .value for consistency
    elif hasattr(winner, 'name'):
        winning_team_name = winner.name.upper()
        winning_team = winner
    elif hasattr(winner, 'value'):
        # Map value back to name (e.g., "Wolf" -> "WOLF")
        value_to_name = {
            "Villager": "VILLAGER",
            "Wolf": "WOLF", 
            "Fire": "FIRE",
            "Killer": "KILLER",
            "Neutral": "NEUTRAL"
        }
        winning_team_name = value_to_name.get(str(winner.value), "NEUTRAL")
        winning_team = winner
    else:
        # Fallback: try to match by string
        winning_team_name = str(winner).upper()
        try:
            winning_team = Team[winning_team_name]
        except:
            winning_team = Team.NEUTRAL
            winning_team_name = "NEUTRAL"
    
    logger.info(f"✅ Normalized winning team: {winning_team_name} (enum: {winning_team})")

    # ============================================================
    # ADD THIS ENTIRE SECTION - SURVIVAL BONUS
    # ============================================================
    if not getattr(game, 'custom_game', False):
        logger.info("Awarding survival bonuses to alive players")
        for player in game.get_alive_players():
            if not hasattr(player, 'game_actions'):
                player.game_actions = {}
            # Award 1 point for survival
            player.game_actions['survival_bonus'] = 1
            logger.debug(f"Survival bonus awarded to {player.first_name}")
    # ============================================================
    
    
    # 🆕 Team-specific victory messages (UPPERCASE KEYS)
    victory_messages = {
        "VILLAGER": """🌅 **THE VILLAGE STANDS VICTORIOUS** 🌅

Dawn breaks over the blood-soaked village. The evil has been vanquished!
The surviving villagers embrace, tears of relief streaming down their faces.
Children will play safely again. The nightmare is over.

*The light has triumphed over darkness.*""",
        
        "WOLF": """🌑 **THE PACK CLAIMS THE VILLAGE** 🌑

The howls grow louder as the last defenders fall.
The village is no more—only hunting grounds for the pack remain.
In the pale moonlight, yellow eyes gleam with hunger and triumph.

*The wolves have inherited the earth.*""",
        
        "FIRE": """🔥 **EVERYTHING BURNS** 🔥

The arsonists watch as flames consume the final structures.
Screams fade to silence. Embers dance in the scorched air.
Where once stood a village, now only ash and ruin remain.

*From the ashes, nothing shall rise.*""",

        "KILLER": """🔪 **THE PREDATOR REMAINS** 🔪

One by one, they all fell—villager and wolf alike.
The methodical hunter stands alone among the corpses.
The Serial Killer has achieved what none else could: absolute dominion through death.

*In the end, only the most patient predator survives.*""",
        
        "NEUTRAL": """🎭 **CHAOS REIGNS SUPREME** 🎭

The trickster's laughter echoes through the empty streets.
Neither good nor evil prevailed—only madness and chaos.
The game was rigged from the start, and the fool has won.

*Sometimes, the only winning move is to play a different game.*"""
    }
    
    # Send victory message
    victory_text = victory_messages.get(winning_team_name, victory_messages["NEUTRAL"])
    
    # ✅ FIXED: Map winning team to correct GIF key
    gif_key_map = {
        "VILLAGER": "villager_win",
        "WOLF": "wolf_win",
        "FIRE": "fire_win",
        "KILLER": "killer_win",  # Serial Killer uses neutral win
        "NEUTRAL": "neutral_win"
    }
    
    # Get the correct GIF key with proper fallback
    gif_key = gif_key_map.get(winning_team_name, "villager_win")
    
    logger.info(f"🎬 Sending victory message: Team={winning_team_name}, GIF={gif_key}")
    
    # Send victory GIF with fallback
    gif_sent = await send_gif_message(
        context=context,
        chat_id=game.group_id,
        gif_key=gif_key,
        gif_dict=WIN_GIFS,
        caption=victory_text,
        parse_mode='Markdown'
    )
    
    if not gif_sent:
        # Fallback: send text only if GIF fails
        try:
            await context.bot.send_message(
                chat_id=game.group_id,
                text=victory_text,
                parse_mode='Markdown'
            )
            logger.info("Sent victory message without GIF (fallback)")
        except Exception as e:
            logger.error(f"Failed to send victory message at all: {e}")
    
    await asyncio.sleep(2)
    
    # Generate game data
    game_id = f"{game.group_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Determine winners
    winners_user_ids = set()
    for p in game.players.values():
        if p.role and p.role.team.name.upper() == winning_team_name:
            winners_user_ids.add(p.user_id)
            
        # Special win conditions
        if p.role == Role.JESTER and getattr(p, 'achieved_objective', False):
            winners_user_ids.add(p.user_id)
    if not getattr(game, 'custom_game', False):
        # ONLY process rankings for non-custom games
        
        # Prepare results payload
        results_payload = []
        for player in game.players.values():
            if not player.role: 
                continue
           
            role_name = player.role.name
            team_name = player.role.team.name

            logger.info(f"DEBUG - Player: {player.first_name}")
            logger.info(f"DEBUG - player.role: {player.role}")
        
            results_payload.append({
                "user_id": player.user_id,
                "username": getattr(player, 'username', '') or "",
                "first_name": player.first_name,
                "won": player.user_id in winners_user_ids,
                "team": team_name,
                "role": role_name,
                "is_alive": player.is_alive,
                "actions": getattr(player, 'game_actions', {})
            })
        
        logger.info(f"DEBUG - Full results_payload: {results_payload}")

        # Process rankings
        processed_results = record_batch_game_results(game_id, len(game.players), results_payload)
        logger.info(f"DEBUG - Processed results: {processed_results}")
        
        # Calculate game length
        duration = datetime.now() - game.start_time
        game_length_str = str(duration).split('.')[0]
        
        # Generate final message with rankings
        final_message = generate_final_reveal_message(winner, processed_results, game_length_str)
        try:
            await send_player_breakdowns(context, processed_results)
            logger.info("Sent individual performance breakdowns to all players")
        except Exception as e:
            logger.error(f"Failed to send player breakdowns: {e}")
        
    else:
        # Custom game - no rankings
        logger.info(f"🔴 Skipping ranking updates for custom game {game.group_id}")
        
        # Generate simple final message without rankings
        final_message = "🎭 **FINAL REVEAL**\n\n"
        
        for player in game.players.values():
            if not player.role:
                continue
            status = "🌱 Survived" if player.is_alive else "💀 Died"
            role_info = f"{player.role.emoji} {player.role.role_name}"
            final_message += f"{status} | {player.mention} - {role_info}\n"
        
        final_message += f"\n⚠️ *Custom game - no rankings recorded*"
    # ============================================================
    # END OF CUSTOM GAME CHECK
    # ============================================================
   
    await context.bot.send_message(
        chat_id=game.group_id,
        text=final_message,
        parse_mode='Markdown'
    )

    if game.group_id in custom_game_configs:
        del custom_game_configs[game.group_id]
        logger.info(f"Cleaned up custom game config after game end")
    
    # Remove from active games
    from game import active_games
    if game.group_id in active_games:
        del active_games[game.group_id]
        logger.info(f"Removed game {game.group_id} from active games")

async def cleanup_game_buttons(context: ContextTypes.DEFAULT_TYPE, game: Game):
    """Remove all active buttons from ongoing game"""
    logger.info(f"Cleaning up buttons for game {game.group_id}")
    
    # 1. Remove timer message button (lobby)
    if hasattr(game, 'timer_message_id') and game.timer_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=game.group_id,
                message_id=game.timer_message_id,
                reply_markup=None
            )
            logger.info("Removed timer message button")
        except Exception as e:
            logger.debug(f"Timer message already gone: {e}")
    
    # 2. Remove all player action buttons
    for player in game.players.values():
        if hasattr(player, 'last_action_message_id') and player.last_action_message_id:
            try:
                await context.bot.edit_message_reply_markup(
                    chat_id=player.user_id,
                    message_id=player.last_action_message_id,
                    reply_markup=None
                )
                logger.info(f"Removed action buttons for {player.first_name}")
            except Exception as e:
                logger.debug(f"Action buttons already gone for {player.first_name}: {e}")
    
    # 3. Cancel all pending timer jobs
    job_names = [
        f"auto_start_{game.group_id}",
        f"timer_update_{game.group_id}_1",
        f"timer_update_{game.group_id}_2",
        f"timer_update_{game.group_id}_3",
        f"timer_update_{game.group_id}_4"
    ]
    
    for job_name in job_names:
        jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in jobs:
            job.schedule_removal()
            logger.info(f"Cancelled job: {job_name}")

async def send_final_reveal(context: ContextTypes.DEFAULT_TYPE, game: Game):
    """Send final role reveal"""
    reveal_lines = ["🎭 **FINAL REVEAL**", ""]

    for player in game.players.values():
        status = "🌱 Survived" if player.is_alive else "💀 Died"
        role_info = f"{player.role.emoji} {player.role.role_name}" if player.role else "Unknown"
        reveal_lines.append(f"{status} | {player.mention} - {role_info}")

    reveal_message = "\n".join(reveal_lines)
    
    try:
        await context.bot.send_message(
            chat_id=game.group_id,
            text=reveal_message,
            parse_mode='Markdown'
        )
        logger.info(f"Sent final reveal for game {game.group_id}")
    except Exception as e:
        logger.error(f"Failed to send final reveal: {e}")

logger.info("Mechanics module loaded successfully")
