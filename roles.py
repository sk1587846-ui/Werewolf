import logging
import random
from typing import Optional, Dict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from enums import Team, Role, GamePhase
from game import Game, Player
from config import MIN_PLAYERS, EVIL_TEAM_RATIO

logger = logging.getLogger(__name__)

# Role narrative introductions (sent privately to players)
ROLE_NARRATIVES = {
    Role.VILLAGER: """You are a Villager 👤.
No powers, only your voice and vote.
Trust your instincts and help guide the village.""",

    Role.WEREWOLF: """You are a Werewolf 🐺.
Hunt with your pack each night.
Devour the village before they discover you.""",

    Role.ALPHA_WOLF: """You are the Alpha Wolf 🐺🌑.
Lead the hunt and infect your prey.
Your bite may turn victims into wolves.""",

    Role.WOLF_SHAMAN: """You are the Wolf Shaman 🐺🔮.
Cast curses to silence or block powers.
You weaken the village without drawing blood.""",

    Role.SERIAL_KILLER: """You are the Serial Killer 🔪.
Kill one player each night.
Survive alone — even the wolves fear you.""",

    Role.SEER: """You are the Seer 🔮.
Each night, reveal one player’s alignment.
Use your visions to guide the village.""",

    Role.DOCTOR: """You are the Doctor 💊.
Protect one soul from death each night.
Your healing hands may save the innocent.""",

    Role.HUNTER: """You are the Hunter 🏹.
If killed, take someone with you.
Your final shot may change everything.""",

    Role.CUPID: """You are Cupid 💘.
Link two players in love on night one.
If one dies, the other follows in grief.""",

    Role.WITCH: """You are the Witch 🧙‍♀️.
One potion to save, one to kill.
Use each wisely — you hold life and death.""",

    Role.DETECTIVE: """You are the Detective 🕵️.
Each day, uncover one player’s role.
Expose evil with your investigations.""",

    Role.JESTER: """You are the Jester 🤡.
Convince the village to hang you.
If lynched, you win alone in chaos.""",

    Role.DOPPELGANGER: """You are the Doppelganger 🎭.
Copy the role of a dead villager.
Become what they were — powers and all.""",

    Role.VIGILANTE: """You are the Vigilante ⚔️.
Kill one soul at night.
If you slay an innocent, guilt will consume you.""",

    Role.MAYOR: """You are the Mayor 🏛️.
Reveal your role to double your vote.
The village respects your judgment.""",

    Role.ORACLE: """You are the Oracle 🌟.
Each night, learn one role a player is NOT.
Use elimination to uncover the truth.""",

    Role.BODYGUARD: """You are the Bodyguard 🛡️.
Protect one player with your life.
Die in their place if they’re attacked.""",

    Role.INSOMNIAC: """You are the Insomniac 👁️.
Each night, see who visited you.
Their intent remains a mystery.""",

    Role.TWINS: """You are a Twin 👥.
You know your sibling is innocent.
The village does not share your certainty.""",

    Role.CURSED_VILLAGER: """You are a Cursed Villager 😨.
You appear ordinary to all.
If attacked by wolves, you may become one.""",

    Role.GRAVE_ROBBER: """You are the Grave Robber ⚰️.
Borrow powers from the dead every other night.
Their whispers guide your choices.""",

    Role.FOOL: """You are the Fool 🤡❓.
You appear evil to Seer and Detective.
But in truth, you are a simple villager.""",

    Role.APPRENTICE_SEER: """You are the Apprentice Seer 🔮📚.
If the Seer dies, you inherit their powers.
Until then, you wait and watch.""",

    Role.PLAGUE_DOCTOR: """You are the Plague Doctor 🦠.
Infect one player each night.
Visitors to them may die by morning.""",

    Role.PRIEST: """You are the Priest ⛪.
Bless one soul each night.
They cannot be cursed or converted.""",

    Role.ARSONIST: """You are the Arsonist 🔥.
Douse players in oil each night.
Ignite later to burn them all.""",

    Role.BLAZEBRINGER: """You are the BLAZEBRINGER 🔥⚡.
Block powers or help douse targets.
But fire may spread beyond your control.""",

    Role.ACCELERANT_EXPERT: """You are the Accelerant Expert 🔥🧪.
Once per game, boost the Arsonist’s power.
They may douse two souls that night.""",

    Role.WEBKEEPER: """🕷️ Webkeeper
Trap actions targeting you or the Serial Killer.
You win only if the Killer survives.""",

    Role.STRAY: """🐾 Stray
Watch one player each night.
Learn who visited them and help the village.""",

    Role.MIRROR_PHANTOM: """🪞 Mirror Phantom
Once per game, steal a visitor’s ability.
Adopt their win condition and power.""",

    Role.THIEF: """🗝️ Thief
Steal one player’s ability once.
Cause impact and survive to the final five.""",

    Role.EXECUTIONER: """You are the Executioner 🪓.
Your goal: get {target} lynched.
If they die, you win — otherwise, fade into the crowd."""
}

def assign_roles_custom(game: Game, custom_pool: list) -> bool:
    """Assign roles from custom pool"""
    from config import MIN_PLAYERS
    
    player_count = len(game.players)
    
    if player_count < MIN_PLAYERS:
        logger.error(f"Not enough players: {player_count}")
        return False
    
    if len(custom_pool) < player_count:
        logger.error(f"Not enough roles in custom pool: {len(custom_pool)} roles for {player_count} players")
        return False
    
    # Shuffle and assign roles
    available_roles = custom_pool.copy()
    random.shuffle(available_roles)
    
    for i, player in enumerate(game.players.values()):
        if i < len(available_roles):
            player.role = available_roles[i]
        else:
            # Fallback to villager if pool is exhausted
            player.role = Role.VILLAGER
    
    # Detect evil team type
    has_wolves = any(p.role.team == Team.WOLF for p in game.players.values())
    has_fire = any(p.role.team == Team.FIRE for p in game.players.values())
    has_sk = any(p.role == Role.SERIAL_KILLER for p in game.players.values())
    
    if has_fire:
        game.evil_team_type = Team.FIRE
    elif has_wolves:
        game.evil_team_type = Team.WOLF
    elif has_sk:
        game.evil_team_type = Team.KILLER
    else:
        game.evil_team_type = Team.WOLF  # Default
    
    logger.info(f"Assigned {player_count} custom roles")
    return True

def assign_roles(game) -> bool:
    """Assign balanced, mostly unique roles to all players in the game"""
    players = list(game.players.values())
    num_players = len(players)

    if num_players < MIN_PLAYERS:
        logging.error(f"Not enough players to assign roles: {num_players}/{MIN_PLAYERS}")
        return False

    logging.info(f"Assigning roles for {num_players} players")

    roles_to_assign = []

    # ═══════════════════════════════════════════════════════════
    # EVIL ROLE ASSIGNMENT LOGIC
    # ═══════════════════════════════════════════════════════════
    
    # Define available evil roles by tier
    basic_evil_roles = [Role.WEREWOLF, Role.ALPHA_WOLF, Role.SERIAL_KILLER, 
                        Role.ARSONIST, Role.BLAZEBRINGER]
    
    # Determine number of evil players
    difficulty = game.settings.get('difficulty', 'normal')

    if num_players < 7:
        if difficulty == 'easy':
            num_evil = 1
        elif difficulty == 'hard':
            num_evil = 2
        else:  # normal
            num_evil = random.choice([1, 2])

    elif num_players < 10:
        if difficulty == 'easy':
            num_evil = 2
        elif difficulty == 'hard':
            num_evil = 3
        else:  # normal
            num_evil = random.randint(2, 3)

    else:  # 10+ players
        base_evil = int(num_players * 0.3)
        if difficulty == 'easy':
            num_evil = max(2, base_evil - 1)
        elif difficulty == 'hard':
            num_evil = min(num_players // 2, base_evil + 1)
        else:  # normal
            num_evil = random.randint(3, max(3, base_evil))
    
    logging.info(f"Assigning {num_evil} evil roles for {num_players} players")
    
    # Select evil roles
    selected_evil = []
    
    if num_players < 7:
        # Pick 1-2 from basic evil roles (NO DUPLICATES YET)
        selected_evil = random.sample(basic_evil_roles, min(num_evil, len(basic_evil_roles)))
    
    elif num_players < 10:
        # Pick 2-3 from basic evil roles
        selected_evil = random.sample(basic_evil_roles, min(num_evil, len(basic_evil_roles)))
        
        # If we have wolf roles, potentially add Wolf Shaman
        if any(role in selected_evil for role in [Role.WEREWOLF, Role.ALPHA_WOLF]):
            if num_evil > len(selected_evil) and random.random() < 0.6:
                selected_evil.append(Role.WOLF_SHAMAN)
        
        # If we have fire roles, potentially add Accelerant Expert
        elif any(role in selected_evil for role in [Role.ARSONIST, Role.BLAZEBRINGER]):
            if num_evil > len(selected_evil) and random.random() < 0.6:
                selected_evil.append(Role.ACCELERANT_EXPERT)
        
        # ✅ FIXED: Only duplicate evil roles if we still need more AND we've exhausted unique options
        # This should rarely happen with proper num_evil calculation
        available_specialist = []
        if Role.WOLF_SHAMAN not in selected_evil and any(r in selected_evil for r in [Role.WEREWOLF, Role.ALPHA_WOLF]):
            available_specialist.append(Role.WOLF_SHAMAN)
        if Role.ACCELERANT_EXPERT not in selected_evil and any(r in selected_evil for r in [Role.ARSONIST, Role.BLAZEBRINGER]):
            available_specialist.append(Role.ACCELERANT_EXPERT)
        
        # Add specialists before duplicating
        while len(selected_evil) < num_evil and available_specialist:
            selected_evil.append(available_specialist.pop(0))
        
        # Only as last resort, duplicate (this indicates num_evil was too high)
        if len(selected_evil) < num_evil:
            logging.warning(f"Had to duplicate evil roles to reach {num_evil} evil players")
            duplicatable = [r for r in selected_evil if r in basic_evil_roles]
            while len(selected_evil) < num_evil and duplicatable:
                selected_evil.append(random.choice(duplicatable))
    
    else:  # 10+ players
        # Choose evil roles without duplicates
        available_evil = basic_evil_roles.copy()
        
        # Build the evil team uniquely
        while len(selected_evil) < num_evil and available_evil:
            chosen = random.choice(available_evil)
            selected_evil.append(chosen)
            available_evil.remove(chosen)  # ✅ Remove to prevent duplicates
            
            # Add specialist roles if team is forming and not already added
            if chosen in [Role.WEREWOLF, Role.ALPHA_WOLF] and Role.WOLF_SHAMAN not in selected_evil:
                if random.random() < 0.5 and Role.WOLF_SHAMAN not in available_evil:
                    available_evil.append(Role.WOLF_SHAMAN)
            
            if chosen in [Role.ARSONIST, Role.BLAZEBRINGER] and Role.ACCELERANT_EXPERT not in selected_evil:
                if random.random() < 0.5 and Role.ACCELERANT_EXPERT not in available_evil:
                    available_evil.append(Role.ACCELERANT_EXPERT)
        
        # ✅ FIXED: Only duplicate if absolutely necessary
        if len(selected_evil) < num_evil:
            logging.warning(f"Had to duplicate evil roles in 10+ player game")
            duplicatable = [r for r in selected_evil if r in basic_evil_roles]
            while len(selected_evil) < num_evil and duplicatable:
                selected_evil.append(random.choice(duplicatable))
    
    # Add selected evil roles to assignment list
    roles_to_assign.extend(selected_evil)
    
    # Determine evil team type for game mechanics
    if any(role in selected_evil for role in [Role.WEREWOLF, Role.ALPHA_WOLF, Role.WOLF_SHAMAN]):
        game.evil_team_type = Team.WOLF
    elif any(role in selected_evil for role in [Role.ARSONIST, Role.BLAZEBRINGER, Role.ACCELERANT_EXPERT]):
        game.evil_team_type = Team.FIRE
    else:
        game.evil_team_type = Team.NEUTRAL
    
    logging.info(f"Evil team composition: {[r.role_name for r in selected_evil]}")
    logging.info(f"Primary evil team type: {game.evil_team_type.value}")

    # Mandatory investigative and protective roles (pick one each)
    investigative_roles = [Role.SEER, Role.ORACLE, Role.DETECTIVE]
    protective_roles = [Role.DOCTOR, Role.BODYGUARD, Role.PRIEST]
    roles_to_assign.append(random.choice(investigative_roles))
    roles_to_assign.append(random.choice(protective_roles))

    # Define unique special roles (these should NEVER duplicate)
    special_roles = [
        Role.HUNTER, Role.WITCH, Role.VIGILANTE, Role.MAYOR, Role.FOOL,
        Role.INSOMNIAC, Role.CURSED_VILLAGER, Role.GRAVE_ROBBER,
        Role.APPRENTICE_SEER, Role.PLAGUE_DOCTOR
    ]

    # Define unique neutral roles (these should NEVER duplicate)
    neutral_roles = [
        Role.JESTER, Role.CUPID, Role.DOPPELGANGER, Role.EXECUTIONER
    ]

    # ✅ FIXED: Track which roles we've already assigned to prevent duplicates
    assigned_roles = set(roles_to_assign)
    
    # Add special roles without duplicates
    random.shuffle(special_roles)  # Randomize order
    for role in special_roles:
        if len(roles_to_assign) >= num_players:
            break
        if role not in assigned_roles:  # ✅ Check before adding
            roles_to_assign.append(role)
            assigned_roles.add(role)

    # Add neutral roles with low chance (never duplicate)
    random.shuffle(neutral_roles)
    for role in neutral_roles:
        if len(roles_to_assign) >= num_players:
            break
        if role not in assigned_roles and random.random() < 0.1:  # ✅ Check before adding
            roles_to_assign.append(role)
            assigned_roles.add(role)

    # Possibly add twins (must appear as a pair, this is the ONLY intentional duplicate)
    if len(roles_to_assign) <= num_players - 2 and Role.TWINS not in assigned_roles and random.random() < 0.2:
        roles_to_assign.extend([Role.TWINS, Role.TWINS])
        assigned_roles.add(Role.TWINS)

    # Fill remaining slots with villagers
    remaining_slots = num_players - len(roles_to_assign)
    if remaining_slots > 0:
        roles_to_assign.extend([Role.VILLAGER] * remaining_slots)
    
    # ✅ Safety check: verify we have exactly the right number
    if len(roles_to_assign) != num_players:
        logging.error(f"Role count mismatch! Expected {num_players}, got {len(roles_to_assign)}")
        return False

    # Shuffle roles and players
    random.shuffle(players)
    random.shuffle(roles_to_assign)

    twins_ids = []
    for player, role in zip(players, roles_to_assign):
        player.role = role

        if role == Role.TWINS:
            twins_ids.append(player.user_id)
            if len(twins_ids) == 2:
                game.twins_ids = twins_ids.copy()

        if role == Role.EXECUTIONER:
            possible_targets = [p for p in players if p != player]
            if possible_targets:
                target = random.choice(possible_targets)
                player.executioner_target = target.user_id

    logging.info(f"Assigned roles: {[p.role.role_name for p in players]}")
    
    # ✅ Final validation: check for unwanted duplicates
    role_counts = {}
    for p in players:
        role_counts[p.role] = role_counts.get(p.role, 0) + 1
    
    for role, count in role_counts.items():
        if count > 1 and role != Role.TWINS and role != Role.VILLAGER:
            logging.error(f"DUPLICATE ROLE DETECTED: {role.role_name} assigned {count} times!")
            # Don't return False here as game already started, but log it prominently
    
    return True

def get_role_action_buttons(player: Player, game: Game, current_phase: GamePhase) -> Optional[InlineKeyboardMarkup]:
    """Generate action buttons for a player's role during night phase"""
    if not player.role or not player.is_alive:
        return None

    alive_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]
    buttons = []
    role = player.role

    logger.debug(f"Generating action buttons for {player.first_name} ({role.role_name})")

    if game.phase == GamePhase.NIGHT:
        if role in [Role.WEREWOLF, Role.ALPHA_WOLF]:
            buttons = [
                [InlineKeyboardButton(f"🐺 Hunt {p.first_name}", callback_data=f"wolf_hunt_{p.user_id}")]
                for p in alive_players
            ]
            buttons.append([InlineKeyboardButton("❌ Skip Hunt", callback_data="wolf_hunt_skip")])
    
        elif role == Role.SERIAL_KILLER:
            buttons = [
                [InlineKeyboardButton(f"🔪 Kill {p.first_name}", callback_data=f"serial_killer_kill_{p.user_id}")]
                for p in alive_players
            ]
            buttons.append([InlineKeyboardButton("❌ Skip Kill", callback_data="serial_killer_skip")])

        elif role == Role.WOLF_SHAMAN:
            buttons = [
                [InlineKeyboardButton(f"🔮 Block {p.first_name}", callback_data=f"shaman_block_{p.user_id}")]
                for p in alive_players
            ]
            buttons.append([InlineKeyboardButton("❌ Skip Block", callback_data="shaman_block_skip")])

    # Villager investigative roles
        elif role == Role.SEER:
            buttons = [
                [InlineKeyboardButton(f"🔮 Check {p.first_name}", callback_data=f"seer_check_{p.user_id}")]
                for p in alive_players
            ]

         # If player is Doppelganger with copied role, use copied role instead
        # ✅ Create a temporary role variable for logic
        elif role == Role.DOPPELGANGER and player.doppelganger_copied_role:
            effective_role = player.doppelganger_copied_role
    # Use effective_role for button generation
            if effective_role == Role.SEER:
                buttons = [
                    [InlineKeyboardButton(f"🔮 Check {p.first_name}", callback_data=f"seer_check_{p.user_id}")]
                    for p in alive_players
                ]
    
            elif effective_role == Role.DOCTOR:
                buttons = [
                    [InlineKeyboardButton(f"💊 Heal {p.first_name}", callback_data=f"doctor_heal_{p.user_id}")]
                    for p in alive_players
                ]
                buttons.append([InlineKeyboardButton("❌ Skip Heal", callback_data="doctor_heal_skip")])
    
            elif effective_role == Role.BODYGUARD:
                buttons = [
                    [InlineKeyboardButton(f"🛡️ Guard {p.first_name}", callback_data=f"bodyguard_protect_{p.user_id}")]
                    for p in alive_players
                ]
                buttons.append([InlineKeyboardButton("❌ Skip Guard", callback_data="bodyguard_protect_skip")])
    
            elif effective_role in [Role.WEREWOLF, Role.ALPHA_WOLF]:
                buttons = [
                    [InlineKeyboardButton(f"🐺 Hunt {p.first_name}", callback_data=f"wolf_hunt_{p.user_id}")]
                    for p in alive_players
                ]
                buttons.append([InlineKeyboardButton("❌ Skip Hunt", callback_data="wolf_hunt_skip")])
    
    # Add other roles as needed...
            else:
                logger.warning(f"Doppelganger copied unsupported role: {effective_role.role_name}")
                return None
    
            return InlineKeyboardMarkup(buttons) if buttons else None

        elif role == Role.ORACLE:
            buttons = [
                [InlineKeyboardButton(f"🌟 Divine {p.first_name}", callback_data=f"oracle_check_{p.user_id}")]
                for p in alive_players
            ]

    # Protective roles
        elif role == Role.DOCTOR:
            buttons = [
                [InlineKeyboardButton(f"💊 Heal {p.first_name}", callback_data=f"doctor_heal_{p.user_id}")]
                for p in alive_players
            ]
            buttons.append([InlineKeyboardButton("❌ Skip Heal", callback_data="doctor_heal_skip")])

        elif role == Role.BODYGUARD:
            buttons = [
                [InlineKeyboardButton(f"🛡️ Guard {p.first_name}", callback_data=f"bodyguard_protect_{p.user_id}")]
                for p in alive_players
            ]
            buttons.append([InlineKeyboardButton("❌ Skip Guard", callback_data="bodyguard_protect_skip")])

        elif role == Role.PRIEST:
            buttons = [
                [InlineKeyboardButton(f"⛪ Bless {p.first_name}", callback_data=f"priest_bless_{p.user_id}")]
                for p in alive_players
            ]
            buttons.append([InlineKeyboardButton("❌ Skip Blessing", callback_data="priest_bless_skip")])

    # Other night actions
        elif role == Role.VIGILANTE and not player.vigilante_killed_innocent:
            buttons = [
                [InlineKeyboardButton(f"⚔️ Kill {p.first_name}", callback_data=f"vigilante_kill_{p.user_id}")]
                for p in alive_players
            ]
            buttons.append([InlineKeyboardButton("❌ Skip Kill", callback_data="vigilante_kill_skip")])

        elif role == Role.WITCH:
            if not player.witch_heal_used:
                buttons.append([InlineKeyboardButton("🧙‍♀️ Heal Potion", callback_data="witch_heal_menu")])
            if not player.witch_poison_used:
                buttons.append([InlineKeyboardButton("🧙‍♀️ Poison Potion", callback_data="witch_poison_menu")])
            if player.witch_heal_used and player.witch_poison_used:
                return None  # No actions available

    # Fire team actions
        elif role == Role.ARSONIST:
            doused_players = [p for p in alive_players if p.is_doused]
            doused_count = len(doused_players)
            buttons = []

    # If accelerant boost active and first douse chosen, show buttons for second douse
            if hasattr(player, "accelerant_boost") and player.accelerant_boost:  
        # If first douse not chosen
                if "arsonist_douse" not in game.night_actions:
                    buttons = [
                        [InlineKeyboardButton(f"🔥 Douse {p.first_name}", callback_data=f"arsonist_douse_{p.user_id}")]
                        for p in alive_players if not p.is_doused
                    ]
                    buttons.append([InlineKeyboardButton("❌ Skip", callback_data="arsonist_skip")])
                    return InlineKeyboardMarkup(buttons)
        # After first douse, for second douse
                elif "arsonist_douse" in game.night_actions and "arsonist_douse_second" not in game.night_actions:
                    excluded_ids = [game.night_actions["arsonist_douse"]["target"]]
                    buttons = [
                        [InlineKeyboardButton(f"🔥 Douse {p.first_name}", callback_data=f"arsonist_douse_second_{p.user_id}")]
                        for p in alive_players if p.user_id not in excluded_ids and not p.is_doused
                    ]
                    buttons.append([InlineKeyboardButton("❌ Skip", callback_data="arsonist_douse_second_skip")])
                    return InlineKeyboardMarkup(buttons)
                else:
                    buttons = []
            else:
                buttons = [
                    [InlineKeyboardButton(f"🔥 Douse {p.first_name}", callback_data=f"arsonist_douse_{p.user_id}")]
                    for p in alive_players if not p.is_doused
                ]
            if doused_count >= 1:
                buttons.append([InlineKeyboardButton("🔥🔥 IGNITE ALL", callback_data="arsonist_ignite")])
                buttons.append([InlineKeyboardButton("❌ Skip", callback_data="arsonist_skip")])
                return InlineKeyboardMarkup(buttons)


        # In get_role_action_buttons function, add:
        elif player.role == Role.BLAZEBRINGER and current_phase == GamePhase.NIGHT:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("🔥 Choose Action", callback_data="fire_starter_action_choice")]
            ])

        elif player.role == Role.ACCELERANT_EXPERT and current_phase == GamePhase.NIGHT:
            if not getattr(player, "accelerant_used", False):
                return InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚡ Use Accelerant", callback_data="accelerant_expert_use")],
                    [InlineKeyboardButton("❌ Skip", callback_data="accelerant_expert_skip")]
                ])
            return None

    # Special roles
        elif role == Role.CUPID and game.day_number == 0:  # First night only
            buttons = [
                [InlineKeyboardButton(f"💘 Choose {p.first_name}", callback_data=f"cupid_choose_{p.user_id}")]
                for p in alive_players
            ]

        elif player.role == Role.WEBKEEPER:
            if not player.has_acted:
                alive_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]
                buttons = [
                    [InlineKeyboardButton(f"🕷️ Mark {p.first_name}", callback_data=f"webkeeper_mark_{p.user_id}")]
                    for p in alive_players
                ]
                buttons.append([InlineKeyboardButton("Skip", callback_data="webkeeper_skip")])
                return InlineKeyboardMarkup(buttons)
    
    # Stray - observe who visited target
        elif player.role == Role.STRAY:
            if not player.has_acted:
                alive_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]
                buttons = [
                    [InlineKeyboardButton(f"🐾 Observe {p.first_name}", callback_data=f"stray_observe_{p.user_id}")]
                    for p in alive_players
                ]
                buttons.append([InlineKeyboardButton("Skip", callback_data="stray_skip")])
            return InlineKeyboardMarkup(buttons)
    
    # Mirror Phantom - passive (waits for visitors)
        elif player.role == Role.MIRROR_PHANTOM:
            if not getattr(player, 'mirror_ability_used', False):
            # Show status message instead of buttons
                buttons = [[InlineKeyboardButton("✓ Waiting for Visitors", callback_data="mirror_phantom_wait")]]
                return InlineKeyboardMarkup(buttons)
    
    # Thief - steal ability
        elif player.role == Role.THIEF:
            if not getattr(player, 'thief_ability_used', False) and not player.has_acted:
                alive_players = [p for p in game.get_alive_players() if p.user_id != player.user_id]
                buttons = [
                [InlineKeyboardButton(f"🗝️ Steal from {p.first_name}", callback_data=f"thief_steal_{p.user_id}")]
                    for p in alive_players
                ]
                buttons.append([InlineKeyboardButton("Skip", callback_data="thief_skip")])
                return InlineKeyboardMarkup(buttons)

        elif role == Role.GRAVE_ROBBER and game.dead_players:
            if player.grave_robber_can_borrow_tonight:
                buttons = [
                    [InlineKeyboardButton(f"⚰️ Borrow {dead.role.role_name}",
                                        callback_data=f"grave_robber_borrow_{dead.user_id}")]
                    for dead in game.dead_players if dead.role != Role.VILLAGER
                ]
                buttons.append([InlineKeyboardButton("❌ Skip Borrowing", callback_data="grave_robber_skip_borrow")])        
                if buttons:
                    return InlineKeyboardMarkup(buttons)
                return None
    
        elif player.grave_robber_act_tonight and player.grave_robber_borrowed_role:
        # ✅ FIXED: Direct role-based button generation (NO RECURSION)
            borrowed_role = player.grave_robber_borrowed_role
            logger.debug(f"Grave Robber {player.first_name} acting with {borrowed_role.role_name}")
        
        # Generate buttons directly based on borrowed role
            if borrowed_role == Role.SEER:
                buttons = [
                    [InlineKeyboardButton(f"🔮 Check {p.first_name}", 
                                        callback_data=f"seer_check_{p.user_id}")]
                    for p in alive_players
                ]
        
            elif borrowed_role == Role.DOCTOR:
                buttons = [
                    [InlineKeyboardButton(f"💊 Heal {p.first_name}", 
                                        callback_data=f"doctor_heal_{p.user_id}")]
                    for p in alive_players
                ]
                buttons.append([InlineKeyboardButton("❌ Skip Heal", callback_data="doctor_heal_skip")])
        
            elif borrowed_role == Role.BODYGUARD:
                buttons = [
                    [InlineKeyboardButton(f"🛡️ Guard {p.first_name}", 
                                        callback_data=f"bodyguard_protect_{p.user_id}")]
                    for p in alive_players
                ]
                buttons.append([InlineKeyboardButton("❌ Skip Guard", callback_data="bodyguard_protect_skip")])
        
            elif borrowed_role == Role.PRIEST:
                buttons = [
                    [InlineKeyboardButton(f"⛪ Bless {p.first_name}", 
                                        callback_data=f"priest_bless_{p.user_id}")]
                    for p in alive_players
                ]
                buttons.append([InlineKeyboardButton("❌ Skip Blessing", callback_data="priest_bless_skip")])
        
            elif borrowed_role == Role.ORACLE:
                 buttons = [
                    [InlineKeyboardButton(f"🌟 Divine {p.first_name}", 
                                        callback_data=f"oracle_check_{p.user_id}")]
                    for p in alive_players
                ]
        
            elif borrowed_role == Role.VIGILANTE:
            # Check if original player (not borrowed role) killed innocent
                if not getattr(player, 'vigilante_killed_innocent', False):
                    buttons = [
                        [InlineKeyboardButton(f"⚔️ Kill {p.first_name}", 
                                            callback_data=f"vigilante_kill_{p.user_id}")]
                        for p in alive_players
                    ]
                    buttons.append([InlineKeyboardButton("❌ Skip Kill", callback_data="vigilante_kill_skip")])
                else:
                    return None  # Can't kill if previous vigilante action killed innocent
        
            elif borrowed_role == Role.WITCH:
            # Use player's own witch status, not borrowed
                if not getattr(player, 'witch_heal_used', False):
                    buttons.append([InlineKeyboardButton("🧙♀️ Heal Potion", callback_data="witch_heal_menu")])
                if not getattr(player, 'witch_poison_used', False):
                    buttons.append([InlineKeyboardButton("🧙♀️ Poison Potion", callback_data="witch_poison_menu")])
            
                if getattr(player, 'witch_heal_used', False) and getattr(player, 'witch_poison_used', False):
                     return None  # No actions available
        
            elif borrowed_role in [Role.WEREWOLF, Role.ALPHA_WOLF]:
                buttons = [
                    [InlineKeyboardButton(f"🐺 Hunt {p.first_name}", 
                                        callback_data=f"wolf_hunt_{p.user_id}")]
                    for p in alive_players
                ]
                buttons.append([InlineKeyboardButton("❌ Skip Hunt", callback_data="wolf_hunt_skip")])
        
            elif borrowed_role == Role.WOLF_SHAMAN:
                buttons = [
                    [InlineKeyboardButton(f"🔮 Block {p.first_name}", 
                                        callback_data=f"shaman_block_{p.user_id}")]
                    for p in alive_players
                ]
                buttons.append([InlineKeyboardButton("❌ Skip Block", callback_data="shaman_block_skip")])
        
            elif borrowed_role == Role.ARSONIST:
            # Get doused players
                doused_players = [p for p in alive_players if getattr(p, 'is_doused', False)]
                doused_count = len(doused_players)
            
                buttons = [
                    [InlineKeyboardButton(f"🔥 Douse {p.first_name}", 
                                        callback_data=f"arsonist_douse_{p.user_id}")]
                    for p in alive_players if not getattr(p, 'is_doused', False)
                ]
            
                if doused_count >= 1:
                    buttons.append([InlineKeyboardButton("🔥🔥 IGNITE ALL", callback_data="arsonist_ignite")])
                buttons.append([InlineKeyboardButton("❌ Skip", callback_data="arsonist_skip")])
        
            elif borrowed_role == Role.BLAZEBRINGER:
                buttons = [[InlineKeyboardButton("🔥 Choose Action", callback_data="fire_starter_action_choice")]]
        
            elif borrowed_role == Role.PLAGUE_DOCTOR:
                if game.day_number % 3 == 1:  # Only on certain nights
                    buttons = [
                        [InlineKeyboardButton(f"🦠 Infect {p.first_name}", 
                                            callback_data=f"plague_doctor_infect_{p.user_id}")]
                        for p in alive_players if not getattr(p, 'is_plagued', False)
                    ]
                    buttons.append([InlineKeyboardButton("❌ Skip Infect", callback_data="plague_doctor_skip")])
                else:
                    return None
        
            else:
            # Unsupported borrowed role or no night action
                logger.warning(f"Grave Robber borrowed unsupported role: {borrowed_role.role_name}")
                return None
        
            return InlineKeyboardMarkup(buttons) if buttons else None

        elif role == Role.PLAGUE_DOCTOR:
            if game.day_number % 3 == 1:
                buttons = [
                    [InlineKeyboardButton(f"🦠 Infect {p.first_name}", callback_data=f"plague_doctor_infect_{p.user_id}")]
                    for p in alive_players if p.user_id != player.user_id and not p.is_plagued
                ]
                buttons.append([InlineKeyboardButton("❌ Skip Infect", callback_data="plague_doctor_skip")])
                return InlineKeyboardMarkup(buttons)
            else:
        # No buttons on other nights
                return None

    elif current_phase == GamePhase.DAY:
        if role == Role.DETECTIVE and not getattr(player, "detective_acted_today", False):
            buttons = [
                [InlineKeyboardButton(f"🕵️ Investigate {p.first_name}", callback_data=f"detective_check_{p.user_id}")]
                for p in alive_players
            ]
            buttons.append([InlineKeyboardButton("❌ Skip", callback_data="detective_check_skip")])
    
        elif role == Role.MAYOR and not player.is_mayor_revealed:
            buttons = [[InlineKeyboardButton("🏛️ Reveal Mayor", callback_data="mayor_reveal")]]
            logger.info(f"Added Mayor reveal button for player {player.first_name}")

    if buttons:
        logger.debug(f"Generated {len(buttons)} action buttons for {player.first_name}")
        return InlineKeyboardMarkup(buttons)
    
    logger.debug(f"No action buttons for {player.first_name}")
    return None

def get_voting_buttons(game: Game, voter_id: int) -> InlineKeyboardMarkup:
    """Generate voting buttons for day phase"""
    alive_players = [p for p in game.get_alive_players() if p.user_id != voter_id]
    
    buttons = [
        [InlineKeyboardButton(f"🗳️ Vote {p.first_name}", callback_data=f"vote_{p.user_id}")]
        for p in alive_players
    ]
    buttons.append([InlineKeyboardButton("❌ Abstain", callback_data="vote_abstain")])
    
    logger.debug(f"Generated voting buttons for player {voter_id}: {len(buttons)} options")
    return InlineKeyboardMarkup(buttons)

logger.info("Roles module loaded successfully")
