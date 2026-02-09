        "players": [],
        "roles": {},
        "alive": {},
        "votes": {},
        "started": False,
        "start_time": None,
        "night_number": 0,
        "mayor_id": None,
        "doppelganger_role": None,
        "jester_lynched": False,
        "player_list_message": None,
        "join_open": True,
        "game_loop_task": None,
        "phase_active": False,
        "phase_end_time": None,
        "mayor_revealed": False,
        "active_buttons": {},
        "night_actions": {
            "wolf_votes": {},
            "doctor_save": None,
            "seer_checks": {},
            "alpha_convert": None,
            "alpha_used": set(),
            "cupid_picks": defaultdict(list),
            "lovers": set(),
            "witch_life": None,
            "witch_death": None,
            "witch_potions": {},
            "detective_checks": {},
            "vigilante_kills": {},
            "vigilante_guilt": set(),
            "hunter_revenge_pending": None,
            # NEW ROLE ACTIONS
            "oracle_checks": {},
            "oracle_results": {},
            "oracle_exclusion_tracking": defaultdict(dict),
            "bodyguard_protects": {},
            "shaman_blocks": {},
            "insomniac_visitors": {},
            "twins_revealed": False,
            "cursed_players": set(),
            "grave_robber_uses": {},
            "priest_blessings": {},
            "blessed_players": set(),
            "arsonist_doused": set(),
            "arsonist_ignited": False,
            "fire_starter_actions": {},
            "accelerant_actions": {},
            "fire_team_communication": {},
            "executioner_target": None,
            "plague_victims": {},
            "plagued_players": set(),
        },
        # NEW ROLE STATES
        "twins": [],
        "apprentice_active": False,
        "fool_investigations": {},
        "arsonist_team": [],
        "evil_team_type": None,  # "wolves" or "arsonists"
        "executioner_id": None,
        "executioner_won": False,
        "last_bodyguard_protect": {},
        "pending_wolf_messages": {},
    }

#============== ENHANCED ROLE DISTRIBUTION ==============

def build_role_list_validated(n_players: int):
    """Enhanced role distribution with validation"""
    if n_players < 4:
        raise ValueError("Need at least 4 players")
    if n_players > 20:
        n_players = 20  # Cap at 20 players for performance
    
    roles = build_role_list(n_players)
    
    # Validate role distribution
    if len(roles) != n_players:
        print(f"Warning: Role count mismatch. Expected {n_players}, got {len(roles)}")
        # Fix by padding with villagers or trimming
        while len(roles) < n_players:
            roles.append("villager")
        roles = roles[:n_players]
    
    return roles

def build_role_list(n_players: int):
    """Enhanced balanced role distribution with evil team randomization"""
    
    if n_players < 5:
        return ["werewolf", "seer", "doctor", "hunter"] + ["villager"] * (n_players - 4)
    
    # For 5+ players, randomly choose between Wolf Team or Fire Team
    evil_team_type = random.choice(["wolves", "arsonists"])
    
    if 5 <= n_players < 10:
        # Small-Medium game roles (5-9 players)
        roles = []
        
        # Essential good roles
        roles.extend(["seer", "doctor"])
        
        if evil_team_type == "wolves":
            # Wolf team (25-30% of players)
            wolf_count = max(1, n_players // 4)
            roles.append("werewolf")
            if wolf_count > 1:
                roles.append("alpha_wolf")
                # Add more wolves if needed
                for _ in range(wolf_count - 2):
                    roles.append("werewolf")
        else:  # fire team
            # Fire team (1 arsonist + helper for larger games)
            roles.append("arsonist")
            if n_players >= 7:
                roles.append("fire_starter")
        
        # Power roles for small-medium games
        power_roles = ["hunter", "detective", "bodyguard", "witch", "oracle"]
        
        # Fill remaining slots with power roles, then villagers
        remaining = n_players - len(roles)
        random.shuffle(power_roles)
        for i in range(min(remaining, len(power_roles))):
            roles.append(power_roles[i])
        
        # Fill rest with villagers
        while len(roles) < n_players:
            roles.append("villager")
            
        return roles
    
    else:  # 10+ players - Large games
        roles = []
        
        # Essential good core
        roles.extend(["seer", "doctor", "hunter"])
        
        if evil_team_type == "wolves":
            # Wolf team (25-30% of total players)
            target_wolves = max(2, n_players // 3)
            roles.extend(["werewolf", "alpha_wolf"])
            current_wolves = 2
            
            # Add more wolves if needed
            wolf_roles = ["werewolf", "wolf_shaman"]
            while current_wolves < target_wolves and len(roles) < n_players:
                if current_wolves == 2:
                    roles.append("wolf_shaman")
                else:
                    roles.append("werewolf")
                current_wolves += 1
                
        else:  # fire team
            # Fire team (1 arsonist + helpers for larger games)
            roles.append("arsonist")
            if n_players >= 12:
                roles.append("fire_starter")
            if n_players >= 15:
                roles.append("accelerant_expert")
        
        # Power roles pool
        village_power_roles = [
            "witch", "detective", "vigilante", "mayor", "cupid",
            "oracle", "bodyguard", "insomniac", "grave_robber",
            "apprentice_seer", "plague_doctor", "priest"
        ]
        
        # Chaotic roles (limited to 1-2 per game)
        chaotic_roles = ["jester", "doppelganger", "fool", "cursed_villager"]
        
        # Other third party roles
        other_third_party = ["executioner"]
        
        # Fill remaining slots
        remaining = n_players - len(roles)
        
        # Add 1 chaotic role randomly
        if remaining > 0 and random.random() < 0.7:
            roles.append(random.choice(chaotic_roles))
            remaining -= 1
        
        # Add other third party role for very large games
        if remaining > 0 and n_players >= 12 and random.random() < 0.4:
            roles.append(random.choice(other_third_party))
            remaining -= 1
        
        # Add twins (always in pairs)
        if remaining >= 2 and random.random() < 0.6:
            roles.extend(["twin", "twin"])
            remaining -= 2
        
        # Fill with power roles
        random.shuffle(village_power_roles)
        power_to_add = min(remaining, len(village_power_roles), remaining // 2)
        for i in range(power_to_add):
            roles.append(village_power_roles[i])
            remaining -= 1
        
        # Fill rest with villagers
        while len(roles) < n_players:
            roles.append("villager")
        
        return roles

def format_game_duration(start_time):
    """Format game duration as HH:MM:SS"""
    if not start_time:
        return "00:00:00"
    duration = time.time() - start_time
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

#============== ENHANCED HELPER FUNCTIONS ==============

async def get_name(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Get user's display name with embedded profile link"""
    try:
        chat = await context.bot.get_chat(user_id)
        name = chat.first_name or "Unknown"
        # Escape markdown special characters
        name = name.replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)')
        return f"[{name}](tg://user?id={user_id})"
    except Exception: 
        return f"[User {user_id}](tg://user?id={user_id})"

async def get_name_plain(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Get user's display name without link (for button labels)"""
    try:
        chat = await context.bot.get_chat(user_id)
        name = chat.first_name or str(user_id)
        # Limit name length for button display
        if len(name) > 20:
            name = name[:17] + "..."
        return name
    except Exception: 
        return f"User{str(user_id)[-4:]}"  # Show last 4 digits

def get_role_emoji(role: str) -> str:
    """Enhanced emoji mapping including all new roles"""
    emojis = {
        # Original roles
        "werewolf": "🐺", "alpha_wolf": "🐺👑", "seer": "🔮", "doctor": "💊",
        "hunter": "🏹", "cupid": "💘", "villager": "👤", "witch": "🧙♀️",
        "detective": "🕵️", "jester": "🃏", "doppelganger": "🎭", "vigilante": "⚔️",
        "mayor": "🏛️",
        
        # NEW ROLES
        "oracle": "🌟",
        "bodyguard": "🛡️",
        "wolf_shaman": "🐺🔮",
        "insomniac": "👁️",
        "twin": "👥",
        "cursed_villager": "😨",
        "grave_robber": "⚰️",
        "fool": "🤡",
        "apprentice_seer": "🔮📚",
        "plague_doctor": "🦠",
        "priest": "⛪",
        "arsonist": "🔥",
        "fire_starter": "🔥⚡",
        "accelerant_expert": "🔥🧪",
        "executioner": "🪓",
        "wolf_shaman": "🐺🔮",
        "apprentice_seer": "🔮📚",
        "fire_starter": "🔥⚡",
        "accelerant_expert": "🔥🧪"
    }
    return emojis.get(role, "👤")

def alive_players(chat_id: int):
    """Get list of living players"""
    g = games.get(chat_id, {})
    return [u for u in g.get("players", []) if g.get("alive", {}).get(u, False)]

def is_wolf(chat_id: int, uid: int) -> bool:
    """Check if player is a werewolf"""
    g = games.get(chat_id, {})
    return g.get("roles", {}).get(uid) in ("werewolf", "alpha_wolf", "wolf_shaman")

def is_fire_team(chat_id: int, uid: int) -> bool:
    """Check if player is part of fire team"""
    g = games.get(chat_id, {})
    return g.get("roles", {}).get(uid) in ("arsonist", "fire_starter", "accelerant_expert")

def lovers_pair(chat_id: int):
    """Get the lovers pair if exists"""
    g = games.get(chat_id, {})
    l = set(g.get("night_actions", {}).get("lovers", set()))
    return tuple(l) if len(l) == 2 else None

async def dm_action_buttons(chat_id: int, user_id: int, text: str, buttons: list, context: ContextTypes.DEFAULT_TYPE, action_type: str = None):
    """Send action buttons to player via DM with expiry tracking"""
    g = games.get(chat_id, {})
    if not g.get("alive", {}).get(user_id, False) or not buttons: 
        return
    
    # Track this as an active button
    if action_type:
        if "active_buttons" not in g:
            g["active_buttons"] = {}
        if user_id not in g["active_buttons"]:
            g["active_buttons"][user_id] = set()
        g["active_buttons"][user_id].add(action_type)
    
    markup = InlineKeyboardMarkup(buttons)
    try: 
        await context.bot.send_message(
            chat_id=user_id, 
            text=f"{text}\n\n⏰ You have {PHASE_DURATION} seconds to act!", 
            reply_markup=markup, 
            parse_mode="Markdown"
        )
    except:
        try: 
            await context.bot.send_message(
                chat_id=chat_id, 
                text=f"⚠️ {await get_name(user_id, context)} must /start bot in private to play.", 
                parse_mode="Markdown"
            )
        except: 
            pass

async def player_name_buttons_with_labels(chat_id: int, ids, prefix, context, exclude=None):
    """Create buttons with player names and safe callback data"""
    exclude = exclude or set()
    rows, row = [], []
    
    for uid in ids:
        if uid in exclude:
            continue
            
        label = await get_name_plain(uid, context)
        
        # Create safe callback data within Telegram's 64-byte limit
        # Use a mapping system for long chat IDs
        chat_key = str(abs(chat_id) % 100000)  # Use last 5 digits
        callback_data = f"{prefix}_{chat_key}_{uid}"
        
        # Final safety check
        if len(callback_data.encode('utf-8')) > 60:  # Leave buffer
            # Fallback to even shorter format
            callback_data = f"{prefix[:3]}_{chat_key}_{uid}"
        
        row.append(InlineKeyboardButton(label, callback_data=callback_data))
        
        if len(row) == 3:
            rows.append(row)
            row = []
    
    if row:
        rows.append(row)
    
    return rows
    
    return rows

async def send_player_status(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Send player status with profile links"""
    g = games.get(chat_id)
    if not g or not g.get("players"): 
        return
    
    alive_count = len(alive_players(chat_id))
    total = len(g["players"])
    
    txt = (
        f"🌅 **Dawn breaks over the village...**\n"
        f"💀 Lost: {total-alive_count} | 🙏 Alive: {alive_count}/{total}\n\n"
        f"📜 **Village Status:**\n"
    )
    
    for uid in g["players"]:
        name = await get_name(uid, context)
        role = g["roles"].get(uid, "villager")
        emoji = get_role_emoji(role)
        
        if g["alive"].get(uid, False):
            txt += f"🌱 {name} - Alive\n"
        else:
            rn = "Alpha Wolf" if role == "alpha_wolf" else role.title().replace("_", " ")
            txt += f"⚱️ {name} - Dead ({rn} {emoji})\n"
    
    try:
        await context.bot.send_message(chat_id=chat_id, text=txt, parse_mode="Markdown")
    except:
        pass

#============== ENHANCED ROLE DESCRIPTIONS ==============

def get_role_description(role: str) -> str:
    """Enhanced role descriptions including all new roles"""
    descriptions = {
        # ORIGINAL ROLES
        "werewolf": (
            "🐺 **Werewolf**\nYou are a deadly creature of the night! 🌙\n\n"
            "🔹 Each night, join other wolves to choose a victim.\n"
            "🔹 During the day, blend in and pretend to be innocent.\n\n"
            "**Goal:** Eliminate all villagers without getting caught."
        ),
        "alpha_wolf": (
            "🐺👑 **Alpha Wolf**\nYou're the leader of the pack! 🩸\n\n"
            "🔹 Choose a victim with other wolves each night.\n"
            "🔹 **Special:** Once per game, you have a 20% chance to **convert** a villager into a wolf.\n\n"
            "**Goal:** Lead your wolves to victory!"
        ),
        "seer": (
            "🔮 **Seer**\nYou have the gift of foresight! ✨\n\n"
            "🔹 Every night, you can **peek** at one player's true role.\n"
            "🔹 Use hints and logic to guide villagers **without revealing yourself**.\n\n"
            "**Goal:** Help villagers find and eliminate the wolves."
        ),
        "doctor": (
            "💊 **Doctor**\nYou're the village's protector! 🏥\n\n"
            "🔹 Every night, choose **one player to save** from attacks.\n"
            "🔹 If wolves target them, your protection keeps them alive.\n\n"
            "**Goal:** Keep key allies safe and outsmart the wolves."
        ),
        "hunter": (
            "🏹 **Hunter**\nYou never go down without a fight! 🎯\n\n"
            "🔹 If you die — whether by vote or wolves — you **instantly shoot one player** to take with you.\n\n"
            "**Goal:** Use your revenge wisely to balance the game."
        ),
        "cupid": (
            "💘 **Cupid**\nThe village's matchmaker! 💞\n\n"
            "🔹 On the **first night**, choose **two lovers**.\n"
            "🔹 If one dies, the other dies of heartbreak.\n\n"
            "**Goal:** Create drama and alliances… even across teams!"
        ),
        "witch": (
            "🧙‍♀️ **Witch**\nA mysterious sorceress with **two potions**. 🧪\n\n"
            "🔹 **Healing potion:** Save a player from dying once.\n"
            "🔹 **Poison potion:** Kill a player of your choice once.\n\n"
            "**Goal:** Use your powers wisely — you can shift the balance instantly."
        ),
        "detective": (
            "🕵️ **Detective**\nThe sharp-eyed investigator! 🔍\n\n"
            "🔹 Each night, you can **investigate** one player to learn if they're a wolf or not.\n"
            "🔹 Share your info carefully… or become the wolves' next target.\n\n"
            "**Goal:** Help villagers expose the wolves."
        ),
        "jester": (
            "🃏 **Jester**\nThe chaotic wildcard! 😈\n\n"
            "🔹 Your goal is **to get voted out** by villagers.\n"
            "🔹 If you succeed, **you win instantly**.\n\n"
            "**Goal:** Confuse everyone and make them suspicious of you — without being too obvious!"
        ),
        "doppelganger": (
            "🎭 **Doppelganger**\nThe ultimate copycat! 🪞\n\n"
            "🔹 At the start, you secretly choose one player.\n"
            "🔹 If they die, you **inherit their role** and powers.\n\n"
            "**Goal:** Stay alive until your target dies — then take over their destiny."
        ),
        "vigilante": (
            "⚔️ **Vigilante**\nA villager with a gun! 🔫\n\n"
            "🔹 Once per game, you can **shoot any player** at night.\n"
            "🔹 But beware: **if you shoot a villager, you die too**.\n\n"
            "**Goal:** Use your power wisely to help the village."
        ),
        "mayor": (
            "🏛️ **Mayor**\nThe respected leader of the village! 👑\n\n"
            "🔹 During the day, when you reveal yourself, your **vote counts as 2**.\n"
            "🔹 Wolves will want you dead — stay cautious.\n\n"
            "**Goal:** Lead discussions and guide villagers to victory."
        ),
        "villager": (
            "👤 **Villager**\nYou're an ordinary townsperson. 🏡\n\n"
            "🔹 You have **no special powers**.\n"
            "🔹 Use discussion, logic, and voting to find wolves.\n\n"
            "**Goal:** Survive and help your team defeat the werewolves."
        ),
        
                # NEW ROLES
        "oracle": (
            "🌟 **Oracle**\nThe village's divine truth-seeker! ✨\n\n"
            "🔹 Each night, choose one player to investigate.\n"
            "🔹 You'll learn what role they are **NOT**.\n"
            "🔹 Example: 'They are not a Werewolf' or 'They are not the Seer'\n\n"
            "**Goal:** Use process of elimination to guide the village to truth!"
        ),
        "bodyguard": (
            "🛡️ **Bodyguard**\nThe ultimate protector! 💪\n\n"
            "🔹 Each night, choose someone to guard with your life.\n"
            "🔹 If they're attacked, you die instead of them.\n"
            "🔹 You cannot protect the same person twice in a row.\n\n"
            "**Goal:** Sacrifice yourself to save key villagers."
        ),
        "wolf_shaman": (
            "🐺🔮 **Wolf Shaman**\nA mystical werewolf with dark powers! 🌙\n\n"
            "🔹 Join the pack in choosing victims each night.\n"
            "🔹 **Special:** Block one player's night power each night.\n"
            "🔹 Your magic can stop doctors, seers, and other threats.\n\n"
            "**Goal:** Lead your pack to victory through cunning and magic!"
        ),
        "insomniac": (
            "👁️ **Insomniac**\nYou never sleep and see everything! 🌃\n\n"
            "🔹 Each night, you learn who visited you.\n"
            "🔹 Know if wolves, doctors, or others targeted you.\n\n"
            "**Goal:** Use your observations to catch the wolves."
        ),
        "twin": (
            "👥 **Twin**\nYou have an unbreakable bond! 💫\n\n"
            "🔹 You know your twin's identity and they know yours.\n"
            "🔹 You both know you're innocent villagers.\n"
            "🔹 Work together to find the wolves.\n\n"
            "**Goal:** Use your trusted ally to coordinate village strategy."
        ),
        "cursed_villager": (
            "😨 **Cursed Villager**\nYou carry a dark curse! 🌑\n\n"
            "🔹 You appear as a normal villager.\n"
            "🔹 **Curse:** If werewolves attack you, you become a werewolf instead of dying!\n\n"
            "**Goal:** Hope the wolves never find you... or do you?"
        ),
        "grave_robber": (
            "⚰️ **Grave Robber**\nYou steal power from the dead! 💀\n\n"
            "🔹 Once per game, choose a dead player.\n"
            "🔹 Use their role's power for one night.\n"
            "🔹 Cannot use werewolf powers.\n\n"
            "**Goal:** Make the dead serve the living's cause."
        ),
        "fool": (
            "🤡 **Fool**\nYou're not what you seem! 😵‍💫\n\n"
            "🔹 You appear as a **werewolf** to seers and detectives.\n"
            "🔹 But you're actually on the villagers' side.\n"
            "🔹 Confuse investigators and create chaos.\n\n"
            "**Goal:** Survive and help villagers despite the confusion."
        ),
        "apprentice_seer": (
            "🔮📚 **Apprentice Seer**\nLearning the mystical arts! 📖\n\n"
            "🔹 You start with no powers.\n"
            "🔹 **If the Seer dies, you inherit their vision abilities.**\n"
            "🔹 Then you can check one player each night.\n\n"
            "**Goal:** Be ready to take over when tragedy strikes."
        ),
        "plague_doctor": (
            "🦠 **Plague Doctor**\nYou bring sickness and death! ☠️\n\n"
            "🔹 Once per game, infect someone with plague.\n"
            "🔹 They will die the following night (cannot be saved).\n"
            "🔹 Choose your timing wisely.\n\n"
            "**Goal:** Use your deadly disease to help the village."
        ),
        "priest": (
            "⛪ **Priest**\nHoly protector against evil! ✨\n\n"
            "🔹 Once per game, bless one player.\n"
            "🔹 Blessed players cannot be converted by Alpha Wolves.\n"
            "🔹 Choose your blessing wisely.\n\n"
            "**Goal:** Protect the innocent from corruption."
        ),
        
        # FIRE TEAM ROLES
        "arsonist": (
            "🔥 **Arsonist**\nMaster of flames and destruction! 💥\n\n"
            "🔹 Each night, choose to douse one player with gasoline.\n"
            "🔹 Once you've doused enough players, you can ignite them all.\n"
            "🔹 Work with your Fire Team helpers in larger games.\n"
            "🔹 **You win if you eliminate all other players.**\n\n"
            "**Goal:** Burn down the entire village!"
        ),
        "fire_starter": (
            "🔥⚡ **Fire Starter**\nThe arsonist's trusted accomplice! 🔥\n\n"
            "🔹 You know who the Arsonist is and work together.\n"
            "🔹 Each night, choose to either:\n"
            "   • **Douse** a player to help the arsonist\n"
            "   • **Block** someone's power to protect your team\n"
            "🔹 **You win when the Arsonist wins.**\n\n"
            "**Goal:** Help your leader burn everything down!"
        ),
        "accelerant_expert": (
            "🔥🧪 **Accelerant Expert**\nChemical warfare specialist! 💀\n\n"
            "🔹 You know who your fire team members are.\n"
            "🔹 Once per game, you can **boost the ignition**:\n"
            "   • Makes ignition work even if some players aren't doused\n"
            "   • Guarantees successful fire spread\n"
            "🔹 **You win when the Arsonist wins.**\n\n"
            "**Goal:** Ensure the flames consume everyone!"
        ),
        "executioner": (
            "🪓 **Executioner**\nYou have a job to finish! ⚖️\n\n"
            "🔹 You have been assigned a specific target.\n"
            "🔹 **You win if your target gets lynched by the village.**\n"
            "🔹 If your target dies another way, you become a regular villager.\n\n"
            "**Goal:** Manipulate the village into executing your target!"
        )
    }
    
    return descriptions.get(role, descriptions["villager"])

#============== ENHANCED ROLE ASSIGNMENT ==============

async def assign_special_roles(chat_id: int, context):
    """Handle special role assignments that need setup"""
    g = games.get(chat_id)
    if not g:
        return
    
    # Determine evil team type
    if any(g["roles"].get(uid) in ("werewolf", "alpha_wolf", "wolf_shaman") for uid in g["players"]):
        g["evil_team_type"] = "wolves"
    elif any(g["roles"].get(uid) in ("arsonist", "fire_starter", "accelerant_expert") for uid in g["players"]):
        g["evil_team_type"] = "arsonists"
        await assign_fire_team(chat_id, context)
    
    # Find twins and set them up
    twin_players = [uid for uid, role in g["roles"].items() if role == "twin"]
    if len(twin_players) >= 2:
        g["twins"] = twin_players[:2]
        
        twin1, twin2 = g["twins"][0], g["twins"][1]
        
        try:
            name1 = await get_name_plain(twin1, context)
            name2 = await get_name_plain(twin2, context)
            
            await context.bot.send_message(
                twin1,
                text=f"👥 **Twin Connection!** Your twin is {name2}. You both know you're innocent!",
                parse_mode="Markdown"
            )
            await context.bot.send_message(
                twin2,
                text=f"👥 **Twin Connection!** Your twin is {name1}. You both know you're innocent!",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Could not notify twins: {e}")
    
    # Set up executioner target
    executioner_id = next((uid for uid, role in g["roles"].items() if role == "executioner"), None)
    if executioner_id:
        g["executioner_id"] = executioner_id
        potential_targets = [uid for uid, role in g["roles"].items() 
                           if role == "villager" and uid != executioner_id]
        if potential_targets:
            target = random.choice(potential_targets)
            g["night_actions"]["executioner_target"] = target
            
            try:
                target_name = await get_name(target, context)
                await context.bot.send_message(
                    executioner_id,
                    text=f"🪓 **Your target:** {target_name}\nYou must get them lynched to win!",
                    parse_mode="Markdown"
                )
            except:
                pass
    
    # Mark cursed villagers
    cursed_players = [uid for uid, role in g["roles"].items() if role == "cursed_villager"]
    g["night_actions"]["cursed_players"] = set(cursed_players)
    
    # Initialize oracle exclusion tracking
    oracle_players = [uid for uid, role in g["roles"].items() if role == "oracle"]
    for oracle_id in oracle_players:
        g["night_actions"]["oracle_exclusion_tracking"][oracle_id] = {}

async def assign_fire_team(chat_id: int, context):
    """Fixed fire team assignment with proper communication setup"""
    g = games.get(chat_id)
    if not g:
        return
    
    # Initialize fire team communication if missing
    if "pending_fire_messages" not in g:
        g["pending_fire_messages"] = {}
    
    # Find fire team members
    fire_members = [uid for uid, role in g["roles"].items() 
                   if role in ("arsonist", "fire_starter", "accelerant_expert")]
    
    if len(fire_members) < 1:
        return
    
    g["arsonist_team"] = fire_members
    
    # Find specific roles
    arsonist_id = next((uid for uid, role in g["roles"].items() if role == "arsonist"), None)
    fire_starter_id = next((uid for uid, role in g["roles"].items() if role == "fire_starter"), None)
    accelerant_id = next((uid for uid, role in g["roles"].items() if role == "accelerant_expert"), None)
    
    if not arsonist_id:
        return
    
    # Notify arsonist of their team
    team_text = "🔥 **Fire Team Assembled!**\n"
    if fire_starter_id:
        starter_name = await get_name(fire_starter_id, context)
        team_text += f"⚡ **Fire Starter:** {starter_name}\n"
    if accelerant_id:
        accelerant_name = await get_name(accelerant_id, context)
        team_text += f"🧪 **Accelerant Expert:** {accelerant_name}\n"
    
    team_text += "🎯 Lead them to burn down the village!"
    
    try:
        await context.bot.send_message(arsonist_id, text=team_text, parse_mode="Markdown")
    except:
        pass
    
    # Notify fire starter of the arsonist
    if fire_starter_id:
        arsonist_name = await get_name(arsonist_id, context)
        team_text = f"🔥⚡ **Your Fire Leader:** {arsonist_name}\n"
        if accelerant_id:
            accelerant_name = await get_name(accelerant_id, context)
            team_text += f"🧪 **Accelerant Expert:** {accelerant_name}\n"
        team_text += "🎯 Help them douse and ignite the village!"
        
        try:
            await context.bot.send_message(fire_starter_id, text=team_text, parse_mode="Markdown")
        except:
            pass
    
    # Notify accelerant expert of the team
    if accelerant_id:
        arsonist_name = await get_name(arsonist_id, context)
        team_text = f"🔥🧪 **Your Fire Leader:** {arsonist_name}\n"
        if fire_starter_id:
            starter_name = await get_name(fire_starter_id, context)
            team_text += f"⚡ **Fire Starter:** {starter_name}\n"
        team_text += "🎯 Use your chemicals to guarantee success!"
        
        try:
            await context.bot.send_message(accelerant_id, text=team_text, parse_mode="Markdown")
        except:
            pass

async def create_mayor_reveal_button(chat_id: int):
    """Create mayor reveal button with proper callback data"""
    return [[InlineKeyboardButton(
        "🏛️ Reveal Mayor Identity", 
        callback_data=f"reveal_mayor_{chat_id}"
    )]]

#============== RAMPAGE JOIN LOGIC ==============

async def rampage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new game with join phase"""
    chat_id = update.effective_chat.id
    g = games.get(chat_id)
    
    if g and g.get("started"): 
        await update.message.reply_text(
            "🚫 **Game already running!**\n⚔️ A battle is underway...",
            parse_mode="Markdown"
        )
        return
    
    if g and g.get("game_loop_task") and not g["game_loop_task"].done():
        g["game_loop_task"].cancel()
    
    init_game(chat_id)
    
    join_button = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚔️ Join Hunt", callback_data=f"join_game_{chat_id}")
    ]])
    
    await update.message.reply_text(
        "🔥 **THE RAMPAGE BEGINS!**\n"
        "⚡ Join the hunt! You have 120 seconds!\n"
        "🎯 Click below or use /join",
        reply_markup=join_button,
        parse_mode="Markdown"
    )
    
    msg = await update.message.reply_text(
        "🎭 **Gathering Players:**\n👻 No one has joined yet...",
        parse_mode="Markdown"
    )
    games[chat_id]["player_list_message"] = msg

    async def close_join():
        try:
            await asyncio.sleep(120)
            if chat_id not in games or not games[chat_id].get("join_open"):
                return
                
            games[chat_id]["join_open"] = False
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    text=(
                        msg.text + 
                        "\n\n🚪 **Gates closed!** No more players can join."
                    ),
                    parse_mode="Markdown"
                )
            except: 
                pass
            
            if len(games[chat_id]["players"]) < 4:
                await context.bot.send_message(
                    chat_id,
                    text=(
                        "💔 **Not enough players...**\n"
                        "😔 Need at least 4 to start the hunt."
                    ),
                    parse_mode="Markdown"
                )
                games.pop(chat_id, None)
                return
            
            fake = Update(update.update_id, message=update.message)
            await startgame(fake, context)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in close_join for chat {chat_id}: {e}")
    
    games[chat_id]["game_loop_task"] = asyncio.create_task(close_join())

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Player joins the current game"""
    chat_id = update.effective_chat.id
    uid = update.effective_user.id
    name = update.effective_user.first_name or "Unknown"
    
    if chat_id not in games or not games[chat_id].get("join_open"):
        await update.message.reply_text(
            "🚫 **No game to join!**\n⚰️ Use /rampage to start one.",
            parse_mode="Markdown"
        )
        return
    
    g = games[chat_id]
    if uid in g["players"]: 
        await update.message.reply_text(
            "⚔️ **You're already in!**\n🛡️ Ready for battle.",
            parse_mode="Markdown"
        )
        return
    
    try:
        await context.bot.send_message(
            uid,
            "🎭 **You joined the hunt!**\nYour role will be revealed when the game starts...",
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text(
            "🚫 **Cannot reach you!**\n📱 You must /start the bot privately first.",
            parse_mode="Markdown"
        )
        return
    
    g["players"].append(uid)
    g["alive"][uid] = True
    
    await update.message.reply_text(
        f"⚔️ **{name} joins the hunt!**\n🌟 Welcome, brave soul!",
        parse_mode="Markdown"
    )
    
    try:
        player_names = []
        for i, p in enumerate(g["players"], 1):
            pname = await get_name(p, context)
            player_names.append(f"{i}. {pname}")
        
        names_text = "\n".join(player_names)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=g["player_list_message"].message_id,
            text=(
                f"🎭 **Gathering Players:**\n"
                f"👥 {len(g['players'])} joined:\n\n{names_text}\n\n"
                f"🌙 Waiting for more..."
            ),
            parse_mode="Markdown"
        )
    except:
        pass

        
#============== START GAME ==============

async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the actual werewolf game"""
    chat_id = update.effective_chat.id
    g = games.get(chat_id)
    
    if not g: 
        await update.message.reply_text(
            "🚫 **No game to start!**\n💀 Use /rampage first.",
            parse_mode="Markdown"
        )
        return
        
    if g.get("started"):
        await update.message.reply_text(
            "🌙 **Game already started!**\n⚔️ The hunt is underway.",
            parse_mode="Markdown"
        )
        return
    
    # Check if user is admin (skip this check if called from rampage auto-start)
    if hasattr(update.message, 'from_user') and update.message.from_user:
        try:
            member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
            if member.status not in ("administrator", "creator"):
                await update.message.reply_text(
                    "👑 **Admin only!**\n⚖️ Only admins can force start.",
                    parse_mode="Markdown"
                )
                return
        except:
            await update.message.reply_text(
                "❓ **Cannot verify permissions...**\nTry again.",
                parse_mode="Markdown"
            )
            return
    
    if len(g["players"]) < 4:
        await update.message.reply_text(
            "💔 **Need more players!**\n👥 At least 4 required to start.",
            parse_mode="Markdown"
        )
        return

    # Record game start time
    g["start_time"] = time.time()

    # Assign roles using enhanced system
    rlist = build_role_list(len(g["players"]))
    random.shuffle(g["players"])
    random.shuffle(rlist)
    g["roles"] = dict(zip(g["players"], rlist))
    
    for uid in g["players"]: 
        g["alive"][uid] = True
    
    # Clear previous game state
    g["votes"].clear()
    g["night_number"] = 0
    g["jester_lynched"] = False
    g["doppelganger_role"] = None
    
    # Reset night actions
    for key in g["night_actions"]:
        v = g["night_actions"][key]
        if isinstance(v, dict): 
            v.clear()
        elif isinstance(v, set): 
            v.clear()
        elif isinstance(v, list): 
            v[:] = []
        else: 
            g["night_actions"][key] = None
    
    # Re-initialize oracle tracking
    g["night_actions"]["oracle_exclusion_tracking"] = {}
    
    # Init witch potions
    for uid, role in g["roles"].items():
        if role == "witch": 
            g["night_actions"]["witch_potions"][uid] = {"life": True, "death": True}
    
    # Set mayor
    g["mayor_id"] = next((u for u, r in g["roles"].items() if r == "mayor"), None)
    g["started"] = True
    g["join_open"] = False

    # Set up special roles
    await assign_special_roles(chat_id, context)

    # DM roles to players
    wolf_ids = [u for u in g["players"] if is_wolf(chat_id, u)]
    wolf_names = [await get_name(w, context) for w in wolf_ids]
    
    # Announce evil team type to chat
    evil_announcement = ""
    if g.get("evil_team_type") == "wolves":
        evil_announcement = "🐺 **The wolves prowl tonight...**"
    elif g.get("evil_team_type") == "arsonists":
        evil_announcement = "🔥 **Fire spreads in the darkness...**"
    
    for uid in g["players"]:
        try:
            role = g["roles"][uid]
            msg = f"🌙 **Your role:** **{role.upper()}**\n\n"
            msg += get_role_description(role)
            
            # Add pack info for wolves
            if is_wolf(chat_id, uid) and len(wolf_ids) > 1:
                others = [n for i, n in enumerate(wolf_names) if wolf_ids[i] != uid]
                msg += f"\n\n🐺 Your pack: {', '.join(others)}"
            
            # Send message with mayor button if mayor
            if role == "mayor":
                button = await create_mayor_reveal_button(chat_id)
                await context.bot.send_message(uid, msg, reply_markup=InlineKeyboardMarkup(button), parse_mode="Markdown")
            else:
                await context.bot.send_message(uid, msg, parse_mode="Markdown")
        except Exception as e:
            await context.bot.send_message(chat_id, text=f"⚠️ Couldn't send role to {await get_name(uid, context)}")

    await context.bot.send_message(
        chat_id,
        text=(
            "🎭 **Roles assigned!**\n"
            f"{evil_announcement}\n"
            "🌙 The hunt begins!\n"
            "🔮 Check your private messages for your role."
        ),
        parse_mode="Markdown"
    )
    
    # Start the game loop for THIS specific chat
    games[chat_id]["game_loop_task"] = asyncio.create_task(game_loop(chat_id, context))

#============== GAME LOOP ==============

async def game_loop(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced game loop with better error handling"""
    g = games.get(chat_id)
    if not g:
        return

    try:
        while g.get("started"):
            # Check if game was cancelled
            if not games.get(chat_id, {}).get("started"):
                break
                
            g["night_number"] += 1

            await context.bot.send_message(
                chat_id,
                text=(
                    f"🌌 **Night {g['night_number']} falls...**\n"
                    f"🐺 Darkness stirs. Will anyone survive?"
                ),
                parse_mode="Markdown"
            )

            await send_night_action_buttons(chat_id, context)
            await asyncio.sleep(PHASE_DURATION)
            await resolve_night(chat_id, context)

            if await try_end(chat_id, context):
                break

            await context.bot.send_message(
                chat_id, 
                text="🌅 **Dawn breaks!** Time to discuss and find the truth!",
                parse_mode="Markdown"
            )
            
            await send_day_phase_buttons(chat_id, context)
            await asyncio.sleep(PHASE_DURATION)
            await resolve_detective_investigations(chat_id, context)

            await context.bot.send_message(
                chat_id, 
                text="⚖️ **Voting time!** Who do you suspect?",
                parse_mode="Markdown"
            )
            
            await send_vote_buttons(chat_id, context)
            await asyncio.sleep(PHASE_DURATION)
            await resolve_day(chat_id, context)

            if await try_end(chat_id, context):
                break

    except asyncio.CancelledError:
        await context.bot.send_message(
            chat_id, 
            text="⚠️ **Game cancelled!**",
            parse_mode="Markdown"
        )
        cleanup_game_state(g)
    except Exception as e:
        print(f"Game loop error in chat {chat_id}: {e}")
        try:
            await context.bot.send_message(
                chat_id, 
                text=f"💥 **Game error occurred!** The hunt has ended.",
                parse_mode="Markdown"
            )
        except:
            pass
        cleanup_game_state(g)
        g["started"] = False

#============== ENHANCED NIGHT ACTION BUTTONS ==============

async def send_night_action_buttons(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Send night action buttons to all relevant players including new roles"""
    g = games.get(chat_id)
    if not g:
        return
        
    g["phase_active"] = True
    g["phase_end_time"] = time.time() + PHASE_DURATION
    g["active_buttons"] = {}
        
    alive_ids = alive_players(chat_id)
    
    # Send wolf pack communication first
    await send_wolf_pack_communication_buttons(chat_id, context)
    
    # Send fire team actions if fire team game
    if g.get("evil_team_type") == "arsonists":
        await send_fire_team_buttons(chat_id, context)
    
    # Werewolves - choose victim
    for uid in [u for u in alive_ids if is_wolf(chat_id, u)]:
        targets = [t for t in alive_ids if t != uid]
        btns = await player_name_buttons_with_labels(chat_id, targets, "kill", context)
        await dm_action_buttons(
            chat_id, uid, 
            "🐺 **Choose your prey:**", 
            btns, context, "kill"
        )

    for uid in alive_ids:
        if g["roles"].get(uid) == "wolf_shaman":
            targets = [t for t in alive_ids if t != uid]
            btns = await player_name_buttons_with_labels(chat_id, targets, "shamanblock", context)
            await dm_action_buttons(
                chat_id, uid, 
                "🐺🔮 **Whose power will you block tonight?**", 
                btns, context, "shamanblock"
            )
    
    # Seer - peek at someone's role
    for uid in alive_ids:
        if g["roles"].get(uid) == "seer":
            targets = [t for t in alive_ids if t != uid]
            btns = await player_name_buttons_with_labels(chat_id, targets, "check", context)
            await dm_action_buttons(
                chat_id, uid, 
                "🔮 **Who do you want to check?**", 
                btns, context, "check"
            )
    
    # Oracle - learn what someone is NOT
    for uid in alive_ids:
        if g["roles"].get(uid) == "oracle":
            targets = [t for t in alive_ids if t != uid]
            btns = await player_name_buttons_with_labels(chat_id, targets, "oracle_check", context)
            await dm_action_buttons(
                chat_id, uid, 
                "🌟 **Choose someone to divine what they are NOT:**", 
                btns, context, "oracle_check"
            )
    
    # Doctor - save someone
    for uid in alive_ids:
        if g["roles"].get(uid) == "doctor":
            btns = await player_name_buttons_with_labels(chat_id, alive_ids, "save", context)
            await dm_action_buttons(
                chat_id, uid, 
                "💊 **Who do you want to protect?**", 
                btns, context, "save"
            )
    
    # Bodyguard - protect someone with your life
    for uid in alive_ids:
        if g["roles"].get(uid) == "bodyguard":
            last_protected = g.get("last_bodyguard_protect", {}).get(uid)
            targets = [t for t in alive_ids if t != uid and t != last_protected]
            btns = await player_name_buttons_with_labels(chat_id, targets, "bodyguard", context)
            await dm_action_buttons(
                chat_id, uid, 
                "🛡️ **Who will you guard with your life?**", 
                btns, context, "bodyguard"
            )
    
    # Vigilante - choose target to kill
    for uid in alive_ids:
        if g["roles"].get(uid) == "vigilante" and uid not in g["night_actions"]["vigilante_guilt"]:
            targets = [t for t in alive_ids if t != uid]
            btns = await player_name_buttons_with_labels(chat_id, targets, "vigkill", context)
            await dm_action_buttons(
                chat_id, uid, 
                "⚔️ **Choose your target (be careful!):**", 
                btns, context, "vigkill"
            )
    
    # Witch - potion management
    for uid in alive_ids:
        if g["roles"].get(uid) == "witch":
            pots = g["night_actions"]["witch_potions"].get(uid, {"life": False, "death": False})
            if pots["life"] or pots["death"]: 
                await send_witch_options(chat_id, uid, context)
    
    # Cupid - choose lovers (Night 1 only)
    if g["night_number"] == 1:
        for uid in alive_ids:
            if g["roles"].get(uid) == "cupid":
                targets = [t for t in alive_ids if t != uid]
                btns = await player_name_buttons_with_labels(chat_id, targets, "cupid", context)
                await dm_action_buttons(
                    chat_id, uid, 
                    "💘 **Choose the first lover:**", 
                    btns, context, "cupid"
                )
    
    # Grave Robber - use dead person's power (once per game)
    for uid in alive_ids:
        if (g["roles"].get(uid) == "grave_robber" and 
            uid not in g["night_actions"]["grave_robber_uses"]):
            
            dead_players = [p for p in g["players"] if not g["alive"].get(p, False)]
            useable_dead = [p for p in dead_players if g["roles"].get(p) not in ("werewolf", "alpha_wolf", "wolf_shaman", "arsonist", "fire_starter", "accelerant_expert")]
            
            if useable_dead:
                btns = await player_name_buttons_with_labels(chat_id, useable_dead, "graveuse", context)
                btns.append([InlineKeyboardButton("⏭️ Skip", callback_data=f"graveuse_skip_{chat_id}")])
                await dm_action_buttons(
                    chat_id, uid, 
                    "⚰️ **Whose power will you steal?**", 
                    btns, context, "graveuse"
                )
    
    # Priest - bless someone (once per game)
    for uid in alive_ids:
        if (g["roles"].get(uid) == "priest" and 
            uid not in g["night_actions"]["priest_blessings"]):
            
            targets = [t for t in alive_ids if t != uid]
            btns = await player_name_buttons_with_labels(chat_id, targets, "bless", context)
            btns.append([InlineKeyboardButton("⏭️ Skip", callback_data=f"bless_skip_{chat_id}")])
            await dm_action_buttons(
                chat_id, uid, 
                "⛪ **Who will you bless against corruption?**", 
                btns, context, "bless"
            )
    
    # Plague Doctor - infect someone (once per game)
    for uid in alive_ids:
        if (g["roles"].get(uid) == "plague_doctor" and 
            uid not in g["night_actions"]["plague_victims"]):
            
            targets = [t for t in alive_ids if t != uid]
            btns = await player_name_buttons_with_labels(chat_id, targets, "plague", context)
            btns.append([InlineKeyboardButton("⏭️ Skip", callback_data=f"plague_skip_{chat_id}")])
            await dm_action_buttons(
                chat_id, uid, 
                "🦠 **Who will you infect with plague?**", 
                btns, context, "plague"
            )
    
    # Set up automatic phase ending
    asyncio.create_task(end_phase_after_delay(chat_id, PHASE_DURATION, context, "night"))

#============== FIRE TEAM NIGHT ACTIONS ==============

async def send_fire_team_buttons(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Send specialized fire team action buttons"""
    g = games.get(chat_id)
    if not g or g.get("evil_team_type") != "arsonists":
        return
        
    alive_ids = alive_players(chat_id)
    fire_team = [uid for uid in g.get("arsonist_team", []) if g["alive"].get(uid, False)]
    
    if not fire_team:
        return
    
    for member_id in fire_team:
        member_role = g["roles"].get(member_id)
        
        if member_role == "arsonist":
            await send_arsonist_buttons(chat_id, member_id, context)
        elif member_role == "fire_starter":
            await send_fire_starter_buttons(chat_id, member_id, context)
        elif member_role == "accelerant_expert":
            await send_accelerant_expert_buttons(chat_id, member_id, context)

async def send_arsonist_buttons(chat_id: int, arsonist_id: int, context):
    """Send arsonist's douse/ignite options"""
    g = games.get(chat_id)
    if not g:
        return
        
    doused = g["night_actions"]["arsonist_doused"]
    alive_ids = set(alive_players(chat_id))
    fire_team = set(g.get("arsonist_team", []))
    
    # Check if everyone except fire team is doused
    undoused = alive_ids - doused - fire_team
    
    btns = []
    
    if undoused:
        # Still people to douse
        douse_btns = await player_name_buttons_with_labels(chat_id, list(undoused), "douse", context)
        btns.extend(douse_btns)
        
        if doused:  # Has doused some people
            btns.append([InlineKeyboardButton("🔥 Ignite All", callback_data=f"ignite_{chat_id}")])
    else:
        # Everyone is doused - can only ignite
        btns.append([InlineKeyboardButton("🔥 Ignite All", callback_data=f"ignite_{chat_id}")])
    
    # Communication with fire team
    fire_team_alive = [m for m in g.get("arsonist_team", []) if g["alive"].get(m, False) and m != arsonist_id]
    if fire_team_alive:
        for other_id in fire_team_alive:
            other_name = await get_name_plain(other_id, context)
            btns.append([InlineKeyboardButton(
                f"💬 Message {other_name}", 
                callback_data=f"fire_msg_{chat_id}_{other_id}"
            )])
    
    btns.append([InlineKeyboardButton("⏭️ Do Nothing", callback_data=f"arson_skip_{chat_id}")])
    
    doused_count = len(doused)
    undoused_count = len(undoused)
    
    try:
        await context.bot.send_message(
            arsonist_id,
            text=(
                f"🔥 **Arsonist Night Action**\n"
                f"🛢️ Doused: {doused_count} players\n"
                f"👥 Undoused: {undoused_count} players\n\n"
                f"Choose your action:"
            ),
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode="Markdown"
        )
    except:
        pass

async def send_fire_starter_buttons(chat_id: int, fire_starter_id: int, context):
    """Send Fire Starter's dual action options"""
    g = games.get(chat_id)
    if not g:
        return
        
    alive_ids = alive_players(chat_id)
    fire_team = g.get("arsonist_team", [])
    doused = g["night_actions"]["arsonist_doused"]
    undoused = set(alive_ids) - doused - set(fire_team)
    
    btns = []
    
    # Option 1: Douse someone
    if undoused:
        douse_btns = await player_name_buttons_with_labels(chat_id, list(undoused), "firedouse", context)
        btns.extend(douse_btns)
    
    # Option 2: Block someone's power
    blockable_targets = [uid for uid in alive_ids if uid != fire_starter_id and uid not in fire_team]
    if blockable_targets:
        block_btns = await player_name_buttons_with_labels(chat_id, blockable_targets, "fireblock", context)
        # Add a separator
        btns.append([InlineKeyboardButton("━━━ OR BLOCK POWER ━━━", callback_data="separator")])
        btns.extend(block_btns)
    
    # Communication with team
    fire_team_alive = [m for m in fire_team if g["alive"].get(m, False) and m != fire_starter_id]
    if fire_team_alive:
        for other_id in fire_team_alive:
            other_name = await get_name_plain(other_id, context)
            btns.append([InlineKeyboardButton(
                f"💬 Message {other_name}", 
                callback_data=f"fire_msg_{chat_id}_{other_id}"
            )])
    
    btns.append([InlineKeyboardButton("⏭️ Do Nothing", callback_data=f"fire_skip_{chat_id}")])
    
    try:
        await context.bot.send_message(
            fire_starter_id,
            text=(
                "🔥⚡ **Fire Starter Action**\n"
                f"🛢️ Doused players: {len(doused)}\n"
                f"👥 Undoused players: {len(undoused)}\n\n"
                "Choose to either **DOUSE** someone or **BLOCK** a power:"
            ),
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode="Markdown"
        )
    except:
        pass

async def send_accelerant_expert_buttons(chat_id: int, expert_id: int, context):
    """Send Accelerant Expert's boost options"""
    g = games.get(chat_id)
    if not g:
        return
    
    # Check if already used boost
    if expert_id in g["night_actions"]["accelerant_actions"]:
        try:
            await context.bot.send_message(
                expert_id,
                text="🔥🧪 **Accelerant already used!** You have no more actions.",
                parse_mode="Markdown"
            )
        except:
            pass
        return
        
    fire_team = g.get("arsonist_team", [])
    doused = g["night_actions"]["arsonist_doused"]
    
    btns = [
        [InlineKeyboardButton("🧪 Use Accelerant Boost", callback_data=f"accelerant_boost_{chat_id}")],
        [InlineKeyboardButton("⏭️ Save for Later", callback_data=f"accelerant_skip_{chat_id}")]
    ]
    
    # Communication with team
    fire_team_alive = [m for m in fire_team if g["alive"].get(m, False) and m != expert_id]
    if fire_team_alive:
        for other_id in fire_team_alive:
            other_name = await get_name_plain(other_id, context)
            btns.append([InlineKeyboardButton(
                f"💬 Message {other_name}", 
                callback_data=f"fire_msg_{chat_id}_{other_id}"
            )])
    
    try:
        await context.bot.send_message(
            expert_id,
            text=(
                "🔥🧪 **Accelerant Expert**\n"
                f"🛢️ Currently doused: {len(doused)} players\n\n"
                "💥 **Accelerant Boost** (once per game):\n"
                "• Makes ignition work even with undoused players\n"
                "• Guarantees fire spreads to everyone\n\n"
                "Use now or save for the perfect moment?"
            ),
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode="Markdown"
        )
    except:
        pass

#============== WOLF PACK COMMUNICATION ==============

async def send_wolf_pack_communication_buttons(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Send wolf pack communication options during night phase"""
    g = games.get(chat_id)
    if not g:
        return
        
    alive_wolves = [uid for uid in alive_players(chat_id) if is_wolf(chat_id, uid)]
    
    if len(alive_wolves) < 2:
        return  # No point in communication if only one wolf
    
    for wolf_id in alive_wolves:
        other_wolves = [w for w in alive_wolves if w != wolf_id]
        if not other_wolves:
            continue
            
        comm_buttons = []
        for other_wolf in other_wolves:
            other_name = await get_name_plain(other_wolf, context)
            comm_buttons.append([InlineKeyboardButton(
                f"💬 Message {other_name}", 
                callback_data=f"wolf_msg_{chat_id}_{other_wolf}"
            )])
        
        if len(alive_wolves) > 2:
            comm_buttons.append([InlineKeyboardButton(
                "📢 Message Pack", 
                callback_data=f"wolf_group_{chat_id}"
            )])
        
        comm_buttons.append([InlineKeyboardButton(
            "🚫 No Messages", 
            callback_data=f"wolf_skip_{chat_id}"
        )])
        
        try:
            await context.bot.send_message(
                chat_id=wolf_id,
                text=(
                    "🐺 **Pack Communication Available**\n"
                    "🌙 Choose who to send a message to:\n"
                    f"⏰ Communication available for {PHASE_DURATION} seconds"
                ),
                reply_markup=InlineKeyboardMarkup(comm_buttons),
                parse_mode="Markdown"
            )
        except:
            pass

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages for team communication"""
    if not update.message or not update.message.text:
        return
    user_id = update.effective_user.id
    message_text = update.message.text
    # Check if this user has pending messages in any game
    for chat_id, game in games.items():
        # Check wolf messages
        if game.get("pending_wolf_messages", {}).get(user_id):
            await handle_wolf_message(update, context, chat_id, user_id, message_text)
            break
        # Check fire team messages
        if game.get("pending_fire_messages", {}).get(user_id):
            await handle_fire_message(update, context, chat_id, user_id, message_text)
            break
async def handle_wolf_message(update, context, chat_id, user_id, message_text):
    """Handle wolf pack message sending"""
    g = games[chat_id]
    pending = g["pending_wolf_messages"][user_id]
    if not g["alive"].get(user_id, False) or not is_wolf(chat_id, user_id):
        del g["pending_wolf_messages"][user_id]
        return
    sender_name = await get_name_plain(user_id, context)
    if pending["type"] == "group":
        alive_wolves = [w for w in alive_players(chat_id) if is_wolf(chat_id, w) and w != user_id]
        for wolf_id in alive_wolves:
            try:
                await context.bot.send_message(
                    chat_id=wolf_id,
                    text=(
                        f"🐺 **Pack Message from {sender_name}:**\n"
                        f"💬 \"{message_text}\""
                    ),
                    parse_mode="Markdown"
                )
            except:
                pass
        await update.message.reply_text(
            f"📢 **Message sent to the pack!**\n💬 \"{message_text}\"",
            parse_mode="Markdown"
        )
    elif pending["type"] == "direct":
        target_id = pending["target"]
        if not g["alive"].get(target_id, False) or not is_wolf(chat_id, target_id):
            await update.message.reply_text("❌ **Target is no longer available.**")
            del g["pending_wolf_messages"][user_id]
            return
        target_name = await get_name_plain(target_id, context)
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"🐺 **Private message from {sender_name}:**\n"
                    f"💬 \"{message_text}\""
                ),
                parse_mode="Markdown"
            )
            await update.message.reply_text(
                f"💬 **Message sent to {target_name}!**\n📝 \"{message_text}\"",
                parse_mode="Markdown"
            )
        except:
            await update.message.reply_text("❌ **Could not deliver message.**")
    del g["pending_wolf_messages"][user_id]
async def handle_fire_message(update, context, chat_id, user_id, message_text):
    """Handle fire team message sending"""
    g = games[chat_id]
    if "pending_fire_messages" not in g:
        g["pending_fire_messages"] = {}
    pending = g["pending_fire_messages"].get(user_id)
    if not pending or not g["alive"].get(user_id, False) or not is_fire_team(chat_id, user_id):
        if user_id in g["pending_fire_messages"]:
            del g["pending_fire_messages"][user_id]
        return
    sender_name = await get_name_plain(user_id, context)
    target_id = pending["target"]
    if not g["alive"].get(target_id, False) or not is_fire_team(chat_id, target_id):
        await update.message.reply_text("❌ **Target is no longer available.**")
        del g["pending_fire_messages"][user_id]
        return
    target_name = await get_name_plain(target_id, context)
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"🔥 **Fire team message from {sender_name}:**\n"
                f"💬 \"{message_text}\""
            ),
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            f"🔥 **Message sent to {target_name}!**\n📝 \"{message_text}\"",
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text("❌ **Could not deliver message.**")
    del g["pending_fire_messages"][user_id]


    
#============== ADDITIONAL NIGHT ACTIONS ==============

async def send_day_phase_buttons(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Send day phase action buttons (Detective investigations)"""
    g = games.get(chat_id)
    if not g:
        return
        
    alive_ids = alive_players(chat_id)
    for uid in alive_ids:
        if g["roles"].get(uid) == "detective":
            targets = [t for t in alive_ids if t != uid]
            btns = await player_name_buttons_with_labels(chat_id, targets, "detect", context)
            await dm_action_buttons(
                chat_id, uid, 
                "🕵️ **Who do you want to investigate?**", 
                btns, context
            )

async def resolve_detective_investigations(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Process detective day investigations"""
    g = games.get(chat_id)
    if not g:
        return
        
    for det, target in g["night_actions"]["detective_checks"].items():
        if g["alive"].get(det, False) and g["alive"].get(target, False):
            r = g["roles"].get(target, "villager")
            rn = "Alpha Wolf" if r == "alpha_wolf" else r.title()
            target_name = await get_name(target, context)
            
            try: 
                await context.bot.send_message(
                    det,
                    text=f"🕵️ **Investigation result:** {target_name} is **{rn}**",
                    parse_mode="Markdown"
                )
            except: 
                pass
    g["night_actions"]["detective_checks"].clear()

async def send_witch_options(chat_id: int, witch_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Send witch potion selection menu"""
    g = games.get(chat_id)
    if not g:
        return
        
    pots = g["night_actions"]["witch_potions"].get(witch_id, {"life": False, "death": False})
    btns = []; row = []
    
    if pots["life"]: 
        row.append(InlineKeyboardButton("💚 Life Potion", callback_data=f"witch_life_menu_{chat_id}"))
    if pots["death"]: 
        row.append(InlineKeyboardButton("💀 Death Potion", callback_data=f"witch_death_menu_{chat_id}"))
    if row: 
        btns.append(row)
    btns.append([InlineKeyboardButton("⏭️ Skip", callback_data=f"witch_skip_{chat_id}")])
    
    try: 
        await context.bot.send_message(
            chat_id=witch_id,
            text="🧙‍♀️ **Choose your potion:**",
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode="Markdown"
        )
    except: 
        pass

async def end_phase_after_delay(chat_id: int, delay: int, context: ContextTypes.DEFAULT_TYPE, phase_type: str):
    """End the current phase after delay and notify about timeouts"""
    await asyncio.sleep(delay)
    
    g = games.get(chat_id)
    if not g or not g.get("phase_active"):
        return
    
    g["phase_active"] = False
    g["phase_end_time"] = None
    
    timed_out_players = []
    
    if phase_type == "night":
        for user_id, button_types in g.get("active_buttons", {}).items():
            if button_types and g["alive"].get(user_id, False):
                player_name = await get_name_plain(user_id, context)
                timed_out_players.append(player_name)
                
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="⏰ **Time's up!** You didn't take any night action.",
                        parse_mode="Markdown"
                    )
                except:
                    pass
                    
    elif phase_type == "voting":
        alive_ids = alive_players(chat_id)
        for user_id in alive_ids:
            if user_id not in g.get("votes", {}):
                player_name = await get_name_plain(user_id, context)
                timed_out_players.append(player_name)
                
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="⏰ **Time's up!** You didn't cast your vote.",
                        parse_mode="Markdown"
                    )
                except:
                    pass
    
    g["active_buttons"] = {}
    
    if timed_out_players:
        timeout_message = f"⏰ **Phase ended!** {len(timed_out_players)} player(s) didn't act in time."
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=timeout_message,
                parse_mode="Markdown"
            )
        except:
            pass

#============== VOTING SYSTEM ==============

async def send_vote_buttons(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Send voting buttons to all living players with timeout handling"""
    g = games.get(chat_id)
    if not g:
        return
        
    g["phase_active"] = True
    g["phase_end_time"] = time.time() + PHASE_DURATION
    g["active_buttons"] = {}
        
    alive_ids = alive_players(chat_id)
    if len(alive_ids) <= 1:
        return
        
    for uid in alive_ids:
        targets = [t for t in alive_ids if t != uid]
        if targets:
            btns = await player_name_buttons_with_labels(chat_id, targets, "vote", context)
            btns.append([InlineKeyboardButton("🚫 Skip Vote", callback_data=f"vote_skip_{chat_id}")])
            await dm_action_buttons(
                chat_id, uid, 
                "🗳️ **Who do you vote to eliminate?**", 
                btns, context, "vote"
            )
    
    asyncio.create_task(end_phase_after_delay(chat_id, PHASE_DURATION, context, "voting"))

async def resolve_day(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Resolve the voting phase and execute lynch"""
    g = games.get(chat_id)
    if not g:
        return
        
    if not g["votes"]:
        await context.bot.send_message(
            chat_id,
            text="🤐 **No votes cast. No one dies today.**",
            parse_mode="Markdown"
        )
        await send_player_status(chat_id, context)
        return
    
    vote_counts = defaultdict(int)
    skip_count = 0
    
    for voter, target in g["votes"].items():
        if target == "skip":
            skip_count += 1
        elif g["alive"].get(target, False): 
            # Check if voter is the revealed mayor (double vote)
            vote_power = 2 if voter == g.get("mayor_id") and g.get("mayor_revealed", False) else 1
            vote_counts[target] += vote_power
    
    total_voters = len(g["votes"])
    summary_lines = [f"📊 **Vote Results** ({total_voters} voted):"]
    
    if skip_count > 0:
        summary_lines.append(f"🤐 Skipped: {skip_count}")
    
    for target, count in sorted(vote_counts.items(), key=lambda x: x[1], reverse=True):
        target_name = await get_name(target, context)
        summary_lines.append(f"👆 {target_name}: {count} votes")
    
    await context.bot.send_message(
        chat_id, 
        text="\n".join(summary_lines), 
        parse_mode="Markdown"
    )
    
    if not vote_counts: 
        await context.bot.send_message(
            chat_id,
            text="🌫️ **Everyone skipped. No execution today.**",
            parse_mode="Markdown"
        )
        g["votes"].clear()
        await send_player_status(chat_id, context)
        return
    
    max_votes = max(vote_counts.values())
    candidates = [t for t, v in vote_counts.items() if v == max_votes]
    
    if len(candidates) > 1:
        names = [await get_name(c, context) for c in candidates]
        await context.bot.send_message(
            chat_id,
            text=f"⚖️ **Tie vote!** No one dies. ({', '.join(names)})",
            parse_mode="Markdown"
        )
        g["votes"].clear()
        await send_player_status(chat_id, context)
        return
    
    target = candidates[0]
    target_name = await get_name(target, context)
    target_role = g["roles"].get(target, "villager")
    
    # Check for Jester win condition
    if target_role == "jester":
        role_display = "Alpha Wolf" if target_role == "alpha_wolf" else target_role.title()
        await context.bot.send_message(
            chat_id,
            text=(
                f"🎪 {target_name} **laughs as they're executed!**\n"
                f"💀 They were the {role_display} {get_role_emoji(target_role)}!\n"
                f"🎉 **JESTER WINS!**"
            ),
            parse_mode="Markdown"
        )
        g["jester_lynched"] = True
        await send_final_game_summary(chat_id, context, "jester")
        g["started"] = False
        return
    
    # Check for Executioner win condition
    if g.get("executioner_id") and target == g["night_actions"].get("executioner_target"):
        g["executioner_won"] = True
    
    # Regular lynch
    role_display = "Alpha Wolf" if target_role == "alpha_wolf" else target_role.title().replace("_", " ")
    await context.bot.send_message(
        chat_id,
        text=(
            f"⚰️ {target_name} **is executed by the village!**\n"
            f"💀 They were {role_display} {get_role_emoji(target_role)}"
        ),
        parse_mode="Markdown"
    )
    
    await kill_player(chat_id, target, context, "lynch")
    g["votes"].clear()
    
    await send_player_status(chat_id, context)

#============== PLAYER DEATH MECHANICS ==============

async def notify_player_death(chat_id: int, player_id: int, context: ContextTypes.DEFAULT_TYPE, cause: str = "unknown", saved_by: str = None):
    """Notify a player of their death or salvation"""
    g = games.get(chat_id)
    if not g:
        return
    
    try:
        if saved_by:
            save_messages = {
                "doctor": "💊 **You were saved by the Doctor!** They protected you from harm tonight.",
                "witch": "✨ **The Witch saved your life!** Their healing potion brought you back from death's door.",
                "bodyguard": "🛡️ **The Bodyguard died protecting you!** Their sacrifice saved your life."
            }
            message = save_messages.get(saved_by, f"🛡️ **You were saved by {saved_by}!**")
            
            await context.bot.send_message(
                chat_id=player_id,
                text=message,
                parse_mode="Markdown"
            )
        else:
            death_messages = {
                "wolves": "🐺 **You have been killed by the werewolves!** The pack claimed another victim in the darkness.",
                "lynch": "⚰️ **You were executed by the village!** The majority has spoken.",
                "witch": "☠️ **You were poisoned by the witch!** A deadly potion sealed your fate.",
                "vigilante": "⚔️ **You were shot by the vigilante!** Justice (or vengeance) has been served.",
                "hunter": "🏹 **You were shot by the dying hunter!** Their final arrow found its mark.",
                "guilt": "💔 **You died of guilt!** The weight of killing an innocent was too much to bear.",
                "heartbreak": "💔 **You died of heartbreak!** Your love's death was too much to endure.",
                "arsonist": "🔥 **You were burned alive!** The flames consumed everything.",
                "bodyguard": "🛡️ **You died protecting someone!** Your noble sacrifice will be remembered.",
                "plague": "🦠 **You succumbed to the plague!** The disease finally claimed your life."
            }
            
            message = death_messages.get(cause, "💀 **You have died!** Your role in this story has ended.")
            message += f"\n\n👻 You are now a spectator. The game continues..."
            
            await context.bot.send_message(
                chat_id=player_id,
                text=message,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        print(f"Could not notify player {player_id} of death/salvation: {e}")

async def kill_player(chat_id: int, uid: int, context: ContextTypes.DEFAULT_TYPE, cause: str):
    """Handle player death and associated mechanics with notifications"""
    g = games.get(chat_id)
    if not g or not g.get("alive", {}).get(uid, False): 
        return
    
    g["alive"][uid] = False
    
    await notify_player_death(chat_id, uid, context, cause)
    
    # Handle lover chain death
    lovers = lovers_pair(chat_id)
    if lovers and uid in lovers:
        other_lover = lovers[0] if lovers[1] == uid else lovers[1]
        if g["alive"].get(other_lover, False):
            g["alive"][other_lover] = False
            other_name = await get_name(other_lover, context)
            other_role = g["roles"].get(other_lover, "villager")
            other_role_name = "Alpha Wolf" if other_role == "alpha_wolf" else other_role.title()
            
            await notify_player_death(chat_id, other_lover, context, "heartbreak")
            
            await context.bot.send_message(
                chat_id=chat_id, 
                text=(
                    f"💔 {other_name} **dies of heartbreak!**\n"
                    f"💀 They were {other_role_name} {get_role_emoji(other_role)}"
                ),
                parse_mode="Markdown"
            )

    # Enhanced Hunter revenge mechanics
    if g["roles"].get(uid) == "hunter" and cause != "hunter":
        alive_targets = [t for t in alive_players(chat_id) if t != uid]
        if alive_targets:
            if random.random() < 0.5:
                g["night_actions"]["hunter_revenge_pending"] = uid
                
                btns = await player_name_buttons_with_labels(chat_id, alive_targets, f"shoot{uid}", context)
                
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=(
                            "🏹 **REVENGE TIME!**\n"
                            "💀 As you die, you have one final shot!\n"
                            f"⏰ Choose your target quickly - you have {PHASE_DURATION} seconds!"
                        ),
                        reply_markup=InlineKeyboardMarkup(btns),
                        parse_mode="Markdown"
                    )
                    
                    asyncio.create_task(remove_hunter_revenge_after_delay(chat_id, uid, PHASE_DURATION, context))
                    
                except Exception as e:
                    print(f"Could not send hunter revenge to {uid}: {e}")
            else:
                hunter_name = await get_name(uid, context)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🏹 {hunter_name} **died too quickly for revenge!** No final shot.",
                    parse_mode="Markdown"
                )

async def remove_hunter_revenge_after_delay(chat_id: int, hunter_id: int, delay: int, context: ContextTypes.DEFAULT_TYPE):
    """Remove hunter revenge option after delay"""
    await asyncio.sleep(delay)
    
    g = games.get(chat_id)
    if g and g["night_actions"].get("hunter_revenge_pending") == hunter_id:
        g["night_actions"]["hunter_revenge_pending"] = None
        
        try:
            await context.bot.send_message(
                chat_id=hunter_id,
                text="⏰ **Time's up!** Your revenge shot opportunity has expired.",
                parse_mode="Markdown"
            )
        except:
            pass

            
#============== ENHANCED CALLBACK ROUTER ==============

def validate_role_action(g: dict, user_id: int, required_role: str, alive_only: bool = True) -> bool:
    """Validate if user can perform a role action"""
    if not g:
        return False
    if alive_only and not g["alive"].get(user_id, False):
        return False
    return g["roles"].get(user_id) == required_role
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced callback router with reliable chat_id extraction"""
    query = update.callback_query
    if not query:
        return
        
    data = query.data
    user_id = query.from_user.id
    
    # First try to get chat_id from the update itself
    chat_id = None
    if update.effective_chat:
        chat_id = update.effective_chat.id
    
    # If that fails, search through active games
    if chat_id is None or chat_id not in games:
        for cid, game in games.items():
            if user_id in game.get("players", []):
                chat_id = cid
                break
    
    # Final fallback: try to parse from callback data
    if chat_id is None:
        try:
            parts = data.split("_")
            for part in parts:
                if part.lstrip('-').isdigit():
                    potential_id = int(part)
                    # Reconstruct full chat_id if using shortened version
                    for cid in games.keys():
                        if abs(cid) % 100000 == abs(potential_id):
                            chat_id = cid
                            break
                    if chat_id:
                        break
        except:
            pass
    
    # Validate that we have a valid chat_id and game exists
    if chat_id is None or chat_id not in games:
        await query.answer("❌ Game not found...")
        try:
            await query.edit_message_text("💫 **Game ended or not found.**")
        except:
            pass
        return
    
    g = games[chat_id]

    if data.startswith(("kill_", "check_", "save_", "vigkill_", "witch_", "oracle_", "bodyguard_", "shamanblock_")):
        role_map = {
            "kill_": ["werewolf", "alpha_wolf", "wolf_shaman"],
            "check_": ["seer"],
            "save_": ["doctor"],
            "vigkill_": ["vigilante"],
            "witch_": ["witch"],
            "oracle_": ["oracle"],
            "bodyguard_": ["bodyguard"],
            "shamanblock_": ["wolf_shaman"]
        }
        
        action_prefix = next((prefix for prefix in role_map.keys() if data.startswith(prefix)), None)
        if action_prefix:
            valid_roles = role_map[action_prefix]
            user_role = g["roles"].get(user_id)
            
            if user_role not in valid_roles:
                await query.answer("You cannot perform this action!", show_alert=True)
                try:
                    await query.edit_message_text("🚫 **Unauthorized action.** This incident will be reported.")
                except:
                    pass
                return
            
            if not g["alive"].get(user_id, False):
                await query.answer("Dead players cannot act!", show_alert=True)
                try:
                    await query.edit_message_text("👻 **You are dead and cannot perform actions.**")
                except:
                    pass
                return
    
    
    # Check if the action is still valid (phase hasn't ended)
    if g.get("phase_end_time") and time.time() > g["phase_end_time"]:
        if not data.startswith("shoot"):
            await query.answer("⏰ Time's up! This phase has ended.", show_alert=True)
            try:
                await query.edit_message_text("⏰ **Time expired** - This action is no longer available.")
            except:
                pass
            return
    
    # Route to appropriate handler based on callback data
    try:
        if data.startswith("join_game_"):
            await handle_join_button(update, context, chat_id)
        elif data.startswith((
    "kill_", "check_", "save_", "cupid_", "detect_", "vigkill_",
    "oracle_check_", "bodyguard_", "firedouse_", "fireblock_", 
    "douse_", "ignite_", "accelerant_boost_", "witch_", "vote_"
)):
            await handle_night_button(update, context, chat_id)
            if user_id in g.get("active_buttons", {}):
                action_type = data.split("_")[0]
                g["active_buttons"][user_id].discard(action_type)
        elif data.startswith("oracle_check_"):
            await handle_oracle_check(update, context, chat_id)
        elif data.startswith("bodyguard_"):
            await handle_bodyguard_action(update, context, chat_id)
        elif data.startswith(("firedouse_", "fireblock_", "douse_", "ignite_", "accelerant_")):
            await handle_fire_team_action(update, context, chat_id)
        elif data.startswith("witch_"):
            await handle_witch_action(update, context, chat_id)
        elif data.startswith("vote_"):
            await handle_vote(update, context, chat_id)
            if user_id in g.get("active_buttons", {}):
                g["active_buttons"][user_id].discard("vote")
        elif data.startswith(("wolf_", "fire_msg_")):
            await handle_team_communication(update, context, chat_id)
        elif data.startswith("shoot"):
            hunter_id = int(data.split("shoot")[1].split("_")[0])
            if g["night_actions"].get("hunter_revenge_pending") == hunter_id:
                await handle_hunter_shot(update, context, chat_id)
            else:
                await query.answer("⏰ Revenge opportunity expired!", show_alert=True)
        elif data.startswith("reveal_mayor"):
            await handle_mayor_reveal(update, context, chat_id)
        elif data == "separator":
            await query.answer("Choose an option above or below")
        else:
            await query.answer("❌ Unknown command...")
            
    except Exception as e:
        print(f"Error in callback handler: {e}")
        await query.answer("⚡ Action failed...")

#============== JOIN BUTTON HANDLER ==============

async def handle_join_button(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle join button press"""
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    
    if chat_id not in games or not games[chat_id].get("join_open"):
        await q.answer("🚫 No game to join or joining closed!", show_alert=True)
        return
    
    g = games[chat_id]
    if uid in g["players"]: 
        await q.answer("⚔️ You're already in the game!", show_alert=True)
        return
    
    try:
        await context.bot.send_message(
            uid,
            "🎭 **You joined the hunt!**\nYour role will be revealed when the game starts...",
            parse_mode="Markdown"
        )
    except:
        await q.answer("🚫 You must /start the bot privately first!", show_alert=True)
        return
    
    g["players"].append(uid)
    g["alive"][uid] = True
    
    user_name = await get_name(uid, context)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⚔️ {user_name} **joins the hunt!** 🌟",
        parse_mode="Markdown"
    )
    
    try:
        player_names = []
        for i, p in enumerate(g["players"], 1):
            pname = await get_name(p, context)
            player_names.append(f"{i}. {pname}")
        
        names_text = "\n".join(player_names)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=g["player_list_message"].message_id,
            text=(
                f"🎭 **Gathering Players:**\n"
                f"👥 {len(g['players'])} joined:\n\n{names_text}\n\n"
                f"🌙 Waiting for more..."
            ),
            parse_mode="Markdown"
        )
    except:
        pass

#============== NIGHT BUTTON HANDLING ==============

async def handle_night_button(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle night action button presses"""
    q = update.callback_query
    await q.answer()
    data = q.data
    actor = q.from_user.id
    g = games.get(chat_id)
    
    if not g or not g["alive"].get(actor, False): 
        await q.edit_message_text("💀 **You're dead. No actions for you.**")
        return
    
    try: 
        parts = data.split("_")
        action = parts[0]
        target = int(parts[-1])
    except: 
        return
    
    target_name = await get_name(target, context)
    
    if action == "kill" and is_wolf(chat_id, actor): 
        g["night_actions"]["wolf_votes"][actor] = target
        await q.edit_message_text(
            f"🐺 **You chose {target_name} as your target.**",
            parse_mode="Markdown"
        )
    elif action == "check" and g["roles"].get(actor) == "seer": 
        g["night_actions"]["seer_checks"][actor] = target
        await q.edit_message_text(
            f"🔮 **Checking {target_name}... results at dawn.**",
            parse_mode="Markdown"
        )
    elif action == "detect" and g["roles"].get(actor) == "detective": 
        g["night_actions"]["detective_checks"][actor] = target
        await q.edit_message_text(
            f"🕵️ **Investigating {target_name}...**",
            parse_mode="Markdown"
        )
    elif action == "save" and g["roles"].get(actor) == "doctor": 
        g["night_actions"]["doctor_save"] = target
        await q.edit_message_text(
            f"💊 **Protecting {target_name} tonight.**",
            parse_mode="Markdown"
        )
    elif action == "vigkill" and g["roles"].get(actor) == "vigilante":
        if actor in g["night_actions"]["vigilante_guilt"]: 
            await q.edit_message_text("💔 **You're too guilty to act...**")
        else: 
            g["night_actions"]["vigilante_kills"][actor] = target
            await q.edit_message_text(
                f"⚔️ **Targeting {target_name}. Hope they're evil...**",
                parse_mode="Markdown"
            )
    elif action == "shamanblock" and g["roles"].get(actor) == "wolf_shaman":
        g["night_actions"]["shaman_blocks"][actor] = target
        await q.edit_message_text(
            f"🐺🔮 **You blocked {target_name}'s power tonight.**",
            parse_mode="Markdown"
        )
    elif action == "cupid" and g["roles"].get(actor) == "cupid" and g["night_number"] == 1:
        picks = g["night_actions"]["cupid_picks"][actor]
        if target in picks: 
            await q.edit_message_text("💕 **Already chosen. Pick someone else.**")
            return
        if len(picks) >= 2: 
            await q.edit_message_text("💞 **Both lovers already chosen!**")
            return
        
        picks.append(target)
        if len(picks) == 1:
            await q.edit_message_text(
                f"💘 **First lover: {target_name}. Now pick the second one.**",
                parse_mode="Markdown"
            )
            alive_ids = [t for t in alive_players(chat_id) if t not in (actor, target)]
            btns = await player_name_buttons_with_labels(chat_id, alive_ids, "cupid", context)
            await dm_action_buttons(
                chat_id, actor, 
                "💖 **Choose the second lover:**", 
                btns, context
            )
        else:
            l1, l2 = picks
            g["night_actions"]["lovers"] = {l1, l2}
            n1, n2 = await get_name(l1, context), await get_name(l2, context)
            await q.edit_message_text(
                f"💞 **Lovers bound: {n1} and {n2}!**",
                parse_mode="Markdown"
            )
            try: 
                await context.bot.send_message(
                    l1,
                    text=f"💘 **You're in love with {n2}!** If they die, so do you.",
                    parse_mode="Markdown"
                )
                await context.bot.send_message(
                    l2,
                    text=f"💘 **You're in love with {n1}!** If they die, so do you.",
                    parse_mode="Markdown"
                )
            except: 
                pass
    elif action == "graveuse" and g["roles"].get(actor) == "grave_robber":
        if actor in g["night_actions"]["grave_robber_uses"]:
            await q.edit_message_text("⚰️ **You already used your grave robbing power.**")
            return
        
        try:
            target_id = int(data.split("_")[-1])
            dead_role = g["roles"].get(target_id)
            if dead_role and not g["alive"].get(target_id, False):
                g["night_actions"]["grave_robber_uses"][actor] = target_id
                target_name = await get_name(target_id, context)
                role_display = "Alpha Wolf" if dead_role == "alpha_wolf" else dead_role.title().replace("_", " ")
                await q.edit_message_text(
                    f"⚰️ **You will use {target_name}'s {role_display} power tonight.**",
                    parse_mode="Markdown"
                )
            else:
                await q.edit_message_text("❌ **Invalid target for grave robbing.**")
        except:
            await q.edit_message_text("⚡ **Grave robbing failed.**")
    elif action == "bless" and g["roles"].get(actor) == "priest":
        if actor in g["night_actions"]["priest_blessings"]:
            await q.edit_message_text("⛪ **You already used your blessing.**")
            return
        
        try:
            target_id = int(data.split("_")[-1])
            g["night_actions"]["priest_blessings"][actor] = target_id
            g["night_actions"]["blessed_players"].add(target_id)
            target_name = await get_name(target_id, context)
            await q.edit_message_text(
                f"⛪ **You blessed {target_name} against corruption.**",
                parse_mode="Markdown"
            )
        except:
            await q.edit_message_text("⚡ **Blessing failed.**")
    elif action == "plague" and g["roles"].get(actor) == "plague_doctor":
        if actor in g["night_actions"]["plague_victims"]:
            await q.edit_message_text("🦠 **You already infected someone.**")
            return
        
        try:
            target_id = int(data.split("_")[-1])
            g["night_actions"]["plague_victims"][actor] = target_id
            target_name = await get_name(target_id, context)
            await q.edit_message_text(
                f"🦠 **You infected {target_name} with plague. They will die tomorrow night.**",
                parse_mode="Markdown"
            )
        except:
            await q.edit_message_text("⚡ **Plague infection failed.**")
    elif data.endswith("_skip") or "skip" in data:
        # Handle various skip actions
        if "graveuse_skip" in data:
            await q.edit_message_text("⚰️ **You decide not to use any dead player's power tonight.**")
        elif "bless_skip" in data:
            await q.edit_message_text("⛪ **You save your blessing for another time.**")
        elif "plague_skip" in data:
            await q.edit_message_text("🦠 **You decide not to spread plague tonight.**")
        else:
            role = g["roles"].get(actor, "unknown")
            role_emoji = get_role_emoji(role)
            await q.edit_message_text(f"{role_emoji} **You do nothing tonight.**")

async def handle_oracle_check(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle Oracle's investigation with exclusion logic"""
    q = update.callback_query
    await q.answer()
    data = q.data
    actor = q.from_user.id
    g = games.get(chat_id)
    
    if not g or not g["alive"].get(actor, False) or g["roles"].get(actor) != "oracle":
        await q.edit_message_text("🚫 **Not authorized for oracle powers.**")
        return
    
    try:
        target_id = int(data.split("_")[-1])
    except:
        await q.edit_message_text("⚡ **Oracle targeting failed.**")
        return
    
    target_name = await get_name(target_id, context)
    target_role = g["roles"].get(target_id, "villager")
    
    # Initialize tracking if not exists
    if actor not in g["night_actions"]["oracle_exclusion_tracking"]:
        g["night_actions"]["oracle_exclusion_tracking"][actor] = {}
    if target_id not in g["night_actions"]["oracle_exclusion_tracking"][actor]:
        g["night_actions"]["oracle_exclusion_tracking"][actor][target_id] = []
    
    # All possible roles in the game
    all_roles = list(set(g["roles"].values()))
    previously_excluded = g["night_actions"]["oracle_exclusion_tracking"][actor][target_id]
    
    # Find roles that can still be excluded
    possible_exclusions = [role for role in all_roles if role != target_role and role not in previously_excluded]
    
    if not possible_exclusions:
        await q.edit_message_text(
            f"🌟 **Divine revelation!** Through elimination, {target_name} **must be** {target_role.title().replace('_', ' ')}!",
            parse_mode="Markdown"
        )
        return
    
    # Pick a random role they are NOT
    excluded_role = random.choice(possible_exclusions)
    
    # Track this exclusion
    g["night_actions"]["oracle_exclusion_tracking"][actor][target_id].append(excluded_role)
    g["night_actions"]["oracle_checks"][actor] = target_id
    
    # Format role name nicely
    role_display = "Alpha Wolf" if excluded_role == "alpha_wolf" else excluded_role.title().replace("_", " ")
    
    await q.edit_message_text(
        f"🌟 **Oracle Vision:** {target_name} is **NOT** a {role_display}.",
        parse_mode="Markdown"
    )
    

    
async def handle_bodyguard_action(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle bodyguard protection action"""
    q = update.callback_query
    await q.answer()
    data = q.data
    actor = q.from_user.id
    g = games.get(chat_id)
    
    if not g or not g["alive"].get(actor, False) or g["roles"].get(actor) != "bodyguard":
        await q.edit_message_text("🚫 **Not authorized for bodyguard powers.**")
        return
    
    try:
        target_id = int(data.split("_")[-1])
    except:
        await q.edit_message_text("⚡ **Bodyguard targeting failed.**")
        return
    
    # Check if trying to protect same person twice in a row
    last_protected = g.get("last_bodyguard_protect", {}).get(actor)
    if target_id == last_protected:
        await q.edit_message_text("🚫 **Cannot protect the same person twice in a row.**")
        return
    
    g["night_actions"]["bodyguard_protects"][actor] = target_id
    g["last_bodyguard_protect"][actor] = target_id
    
    target_name = await get_name(target_id, context)
    await q.edit_message_text(
        f"🛡️ **You will die protecting {target_name} if they're attacked.**",
        parse_mode="Markdown"
    )

async def execute_grave_robber_power(chat_id: int, robber_id: int, dead_player_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Execute the stolen power of a dead player"""
    g = games.get(chat_id)
    if not g:
        return
        
    stolen_role = g["roles"].get(dead_player_id, "villager")
    alive_ids = alive_players(chat_id)
    
    if stolen_role == "seer":
        # Let grave robber check someone
        targets = [t for t in alive_ids if t != robber_id]
        if targets:
            target = random.choice(targets)
            target_role = g["roles"].get(target, "villager")
            
            # Check if target is Fool (appears as werewolf to seer)
            if target_role == "fool":
                result = "werewolf"
            else:
                result = "werewolf" if is_wolf(chat_id, target) else "villager"
            
            target_name = await get_name(target, context)
            try:
                await context.bot.send_message(
                    robber_id,
                    text=f"⚰️🔮 **Grave Vision:** {target_name} is a **{result}**",
                    parse_mode="Markdown"
                )
            except:
                pass
    
    elif stolen_role == "doctor":
        # Protect someone
        targets = alive_ids
        if targets:
            target = random.choice(targets)
            g["night_actions"]["doctor_save"] = target
            target_name = await get_name(target, context)
            try:
                await context.bot.send_message(
                    robber_id,
                    text=f"⚰️💊 **Grave Protection:** You protected {target_name}",
                    parse_mode="Markdown"
                )
            except:
                pass

#============== FIRE TEAM ACTION HANDLERS ==============

async def handle_fire_team_action(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle fire team action button presses"""
    q = update.callback_query
    await q.answer()
    data = q.data
    actor = q.from_user.id
    g = games.get(chat_id)
    
    if not g or not g["alive"].get(actor, False) or not is_fire_team(chat_id, actor):
        await q.edit_message_text("🚫 **Not authorized for fire team actions.**")
        return
    
    if data.startswith("douse_"):
        try:
            target_id = int(data.split("_")[-1])
            g["night_actions"]["arsonist_doused"].add(target_id)
            target_name = await get_name(target_id, context)
            await q.edit_message_text(
                f"🔥 **You doused {target_name} with gasoline.**",
                parse_mode="Markdown"
            )
        except:
            await q.edit_message_text("⚡ **Dousing failed.**")
    
    elif data.startswith("firedouse_"):
        try:
            target_id = int(data.split("_")[-1])
            g["night_actions"]["arsonist_doused"].add(target_id)
            g["night_actions"]["fire_starter_actions"][actor] = {"action": "douse", "target": target_id}
            target_name = await get_name(target_id, context)
            await q.edit_message_text(
                f"🔥⚡ **You helped douse {target_name} with gasoline.**",
                parse_mode="Markdown"
            )
        except:
            await q.edit_message_text("⚡ **Fire starting failed.**")
    
    elif data.startswith("fireblock_"):
        try:
            target_id = int(data.split("_")[-1])
            g["night_actions"]["fire_starter_actions"][actor] = {"action": "block", "target": target_id}
            g["night_actions"]["shaman_blocks"][actor] = target_id  # Reuse shaman block logic
            target_name = await get_name(target_id, context)
            await q.edit_message_text(
                f"🔥🚫 **You blocked {target_name}'s power tonight.**",
                parse_mode="Markdown"
            )
        except:
            await q.edit_message_text("⚡ **Power blocking failed.**")
    
    elif data.startswith("ignite_"):
        doused_count = len(g["night_actions"]["arsonist_doused"])
        fire_team_count = len([uid for uid in g.get("arsonist_team", []) if g["alive"].get(uid, False)])
        alive_count = len(alive_players(chat_id))
        
        # Check if enough are doused (everyone except fire team)
        if doused_count >= (alive_count - fire_team_count):
            g["night_actions"]["arsonist_ignited"] = True
            await q.edit_message_text("🔥💥 **IGNITION! The flames consume everything!**")
        else:
            undoused_count = alive_count - fire_team_count - doused_count
            await q.edit_message_text(
                f"🔥❌ **Cannot ignite yet!** {undoused_count} players still undoused."
            )
    
    elif data.startswith("teamignite_"):
        # Check if accelerant expert boosted
        accelerant_boost = any(
            "boost" in action.get("boost", {}) if isinstance(action, dict) else False
            for action in g["night_actions"]["accelerant_actions"].values()
        )
        
        doused_count = len(g["night_actions"]["arsonist_doused"])
        fire_team_count = len([uid for uid in g.get("arsonist_team", []) if g["alive"].get(uid, False)])
        alive_count = len(alive_players(chat_id))
        
        if accelerant_boost or doused_count >= (alive_count - fire_team_count):
            g["night_actions"]["arsonist_ignited"] = True
            boost_text = " (Accelerant boosted!)" if accelerant_boost else ""
            await q.edit_message_text(f"🔥💥 **TEAM IGNITION!{boost_text}** The flames consume everything!")
        else:
            undoused_count = alive_count - fire_team_count - doused_count
            await q.edit_message_text(
                f"🔥❌ **Cannot ignite yet!** {undoused_count} players still undoused."
            )
    
    elif data.startswith("accelerant_boost_"):
        g["night_actions"]["accelerant_actions"][actor] = {"boost": True}
        await q.edit_message_text(
            "🔥🧪 **Accelerant ready!** Next ignition attempt will be guaranteed to succeed!"
        )
    
    elif data.startswith(("arson_skip_", "fire_skip_", "accelerant_skip_")):
        role = g["roles"].get(actor, "unknown")
        role_emoji = get_role_emoji(role)
        await q.edit_message_text(f"{role_emoji} **You do nothing tonight.**")

async def handle_misc_actions(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle miscellaneous role actions like grave robber, priest, plague doctor"""
    q = update.callback_query
    await q.answer()
    data = q.data
    actor = q.from_user.id
    g = games.get(chat_id)
    
    if not g or not g["alive"].get(actor, False):
        await q.edit_message_text("💀 **You're dead. No actions for you.**")
        return
    
    if data.startswith("graveuse_"):
        if "skip" in data:
            await q.edit_message_text("⚰️ **You decide not to use any dead player's power tonight.**")
        else:
            try:
                target_id = int(data.split("_")[-1])
                g["night_actions"]["grave_robber_uses"][actor] = target_id
                target_name = await get_name(target_id, context)
                await q.edit_message_text(
                    f"⚰️ **You will use {target_name}'s power tonight.**",
                    parse_mode="Markdown"
                )
            except:
                await q.edit_message_text("⚡ **Grave robbing failed.**")
                
    elif data.startswith("bless_"):
        if "skip" in data:
            await q.edit_message_text("⛪ **You save your blessing for another time.**")
        else:
            try:
                target_id = int(data.split("_")[-1])
                g["night_actions"]["priest_blessings"][actor] = target_id
                g["night_actions"]["blessed_players"].add(target_id)
                target_name = await get_name(target_id, context)
                await q.edit_message_text(
                    f"⛪ **You blessed {target_name} against corruption.**",
                    parse_mode="Markdown"
                )
            except:
                await q.edit_message_text("⚡ **Blessing failed.**")
                
    elif data.startswith("plague_"):
        if "skip" in data:
            await q.edit_message_text("🦠 **You decide not to spread plague tonight.**")
        else:
            try:
                target_id = int(data.split("_")[-1])
                g["night_actions"]["plague_victims"][actor] = target_id
                target_name = await get_name(target_id, context)
                await q.edit_message_text(
                    f"🦠 **You infected {target_name} with plague. They will die tomorrow night.**",
                    parse_mode="Markdown"
                )
            except:
                await q.edit_message_text("⚡ **Plague infection failed.**")

async def handle_skip_actions(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle various skip actions"""
    q = update.callback_query
    await q.answer()
    data = q.data
    actor = q.from_user.id
    g = games.get(chat_id)
    
    if not g:
        return
    
    role = g["roles"].get(actor, "unknown")
    role_emoji = get_role_emoji(role)
    
    if "wolf_skip" in data:
        await q.edit_message_text("🐺 **Staying silent in the pack tonight.**")
    elif "arson_skip" in data:
        await q.edit_message_text(f"{role_emoji} **You do nothing tonight.**")
    elif "fire_skip" in data:
        await q.edit_message_text(f"{role_emoji} **You do nothing tonight.**")
    elif "accelerant_skip" in data:
        await q.edit_message_text(f"{role_emoji} **You save your accelerant for later.**")
    else:
        await q.edit_message_text(f"{role_emoji} **You do nothing tonight.**")


#============== TEAM COMMUNICATION HANDLERS ==============

async def handle_team_communication(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle team communication setup"""
    q = update.callback_query
    await q.answer()
    data = q.data
    sender_id = q.from_user.id
    g = games.get(chat_id)
    
    if not g or not g["alive"].get(sender_id, False):
        await q.edit_message_text("🚫 **Not authorized for team communication.**")
        return
    
    # Wolf communication
    if data.startswith("wolf_"):
        if not is_wolf(chat_id, sender_id):
            await q.edit_message_text("🚫 **Not authorized for pack communication.**")
            return
        
        if data.startswith("wolf_skip_"):
            await q.edit_message_text("🐺 **Staying silent in the pack tonight.**")
            return
        elif data.startswith("wolf_group_"):
            await q.edit_message_text("📢 **Type your message to the pack:**")
            g["pending_wolf_messages"] = g.get("pending_wolf_messages", {})
            g["pending_wolf_messages"][sender_id] = {"type": "group", "target": None}
        elif data.startswith("wolf_msg_"):
            try:
                target_id = int(data.split("_")[-1])
                if not g["alive"].get(target_id, False) or not is_wolf(chat_id, target_id):
                    await q.edit_message_text("❌ **Target is not available.**")
                    return
                
                target_name = await get_name_plain(target_id, context)
                await q.edit_message_text(f"💬 **Type your message to {target_name}:**")
                g["pending_wolf_messages"] = g.get("pending_wolf_messages", {})
                g["pending_wolf_messages"][sender_id] = {"type": "direct", "target": target_id}
            except:
                await q.edit_message_text("❌ **Invalid target.**")
    
    # Fire team communication
    elif data.startswith("fire_msg_"):
        if not is_fire_team(chat_id, sender_id):
            await q.edit_message_text("🚫 **Not authorized for fire team communication.**")
            return
        
        try:
            target_id = int(data.split("_")[-1])
            if not g["alive"].get(target_id, False) or not is_fire_team(chat_id, target_id):
                await q.edit_message_text("❌ **Target is not available.**")
                return
            
            target_name = await get_name_plain(target_id, context)
            await q.edit_message_text(f"🔥 **Type your message to {target_name}:**")
            g["pending_fire_messages"] = g.get("pending_fire_messages", {})
            g["pending_fire_messages"][sender_id] = {"target": target_id}
        except:
            await q.edit_message_text("❌ **Invalid target.**")

#============== WITCH ACTION HANDLING ==============

async def handle_witch_action(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle witch potion actions"""
    q = update.callback_query
    await q.answer()
    data = q.data
    actor = q.from_user.id
    g = games.get(chat_id)
    
    if not g or not g["alive"].get(actor, False) or g["roles"].get(actor) != "witch":
        await q.edit_message_text("🚫 **Not a witch or dead.**")
        return
    
    pots = g["night_actions"]["witch_potions"].get(actor, {"life": False, "death": False})
    if not any(pots.values()):
        await q.edit_message_text("🧙‍♀️ **You have no potions left.**")
        return
    
    if data.startswith(f"witch_skip_{chat_id}"):
        await q.edit_message_text("🧙‍♀️ **Witch does nothing tonight.**")
        
    elif data.startswith(f"witch_life_menu_{chat_id}"):
        if not pots["life"]:
            await q.edit_message_text("💔 **Life potion already used.**")
            return
        
        await q.edit_message_text("💚 **Life potion ready. Will save first death tonight.**")
        g["night_actions"]["witch_life"] = "auto"
        g["night_actions"]["witch_potions"][actor]["life"] = False
        
    elif data.startswith(f"witch_death_menu_{chat_id}"):
        if not pots["death"]:
            await q.edit_message_text("☠️ **Death potion already used.**")
            return
            
        alive_ids = [t for t in alive_players(chat_id) if t != actor]
        if not alive_ids:
            await q.edit_message_text("🌫️ **No one to poison.**")
            return
            
        btns = await player_name_buttons_with_labels(chat_id, alive_ids, "witch_death", context)
        await q.edit_message_text("💀 **Choose who to poison:**")
        
        if btns:
            try:
                await context.bot.send_message(
                    chat_id=actor,
                    text="☠️ **Who gets the poison?**",
                    reply_markup=InlineKeyboardMarkup(btns),
                    parse_mode="Markdown"
                )
            except:
                pass
                
    elif data.startswith(f"witch_death_{chat_id}_"):
        if not pots["death"]:
            await q.edit_message_text("☠️ **Death potion already used.**")
            return
            
        try:
            target = int(data.split("_")[-1])
            if not g["alive"].get(target, False):
                await q.edit_message_text("👻 **Target already dead.**")
                return
                
            g["night_actions"]["witch_death"] = target
            g["night_actions"]["witch_potions"][actor]["death"] = False
            tn = await get_name(target, context)
            await q.edit_message_text(f"☠️ **{tn} will be poisoned tonight.**", parse_mode="Markdown")
        except:
            await q.edit_message_text("⚡ **Poison targeting failed.**")
    else:
        await q.edit_message_text("🌀 **Unknown witch action.**")


        
#============== VOTE HANDLING ==============
async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle voting actions"""
    q = update.callback_query
    await q.answer()
    data = q.data
    actor = q.from_user.id

    g = games.get(chat_id)
    if not g or not g["alive"].get(actor, False):
        await q.edit_message_text("👻 **Dead players can't vote.**")
        return

    if actor in g["votes"]:
        await q.edit_message_text("🗳️ **You already voted.**")
        return

    if data == f"vote_skip_{chat_id}":
        g["votes"][actor] = "skip"
        await q.edit_message_text("🚫 **You skip voting.**")
        an = await get_name(actor, context)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🤐 {an} **skips voting.**",
            parse_mode="Markdown"
        )
    else:
        try:
            target = int(data.split("_")[-1])
        except:
            await q.edit_message_text("⚡ **Vote failed.**")
            return

        if not g["alive"].get(target, False):
            await q.edit_message_text("💀 **Can't vote for dead players.**")
            return

        if target == actor:
            await q.edit_message_text("🚫 **Can't vote for yourself.**")
            return

        g["votes"][actor] = target
        tn = await get_name(target, context)
        an = await get_name(actor, context)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚖️ {an} **votes for** {tn}!",
            parse_mode="Markdown"
        )
        await q.edit_message_text(f"⚖️ **You voted for** {tn}.", parse_mode="Markdown")

    # ✅ Always clear vote after voting
    if actor in g.get("active_buttons", {}):
        g["active_buttons"][actor].discard("vote")



#============== MAYOR REVEAL & HUNTER SHOT ==============

async def handle_mayor_reveal(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle mayor identity revelation"""
    q = update.callback_query
    await q.answer()
    actor = q.from_user.id
    g = games.get(chat_id)
    
    if not g or not g["alive"].get(actor, False): 
        await q.edit_message_text("👻 **Dead mayors have no power.**")
        return
        
    if g["roles"].get(actor) != "mayor": 
        await q.edit_message_text("🚫 **You're not the mayor.**")
        return
        
    if actor != g.get("mayor_id"): 
        await q.edit_message_text("⚡ **Mayor verification failed.**")
        return
    
    nm = await get_name(actor, context)
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"👑 {nm} **reveals as MAYOR!**\n"
            f"⚖️ Their vote now counts as 2!"
        ),
        parse_mode="Markdown"  # Fixed: moved parse_mode inside the function call
    )
    await q.edit_message_text("👑 **You revealed as Mayor! Your vote counts double.**", parse_mode="Markdown")
    g["mayor_revealed"] = True  # Track that mayor has been revealed


async def handle_hunter_shot(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Handle hunter's revenge shot when dying"""
    q = update.callback_query
    await q.answer()
    
    try: 
        parts = q.data.split("_")
        dead_hunter_str = parts[0]
        dead_id = int(dead_hunter_str.replace("shoot", ""))
        target = int(parts[-1])
    except: 
        await q.edit_message_text("⚡ **Shot failed.**")
        return
    
    actor = q.from_user.id
    g = games.get(chat_id)
    
    if not g:
        await q.edit_message_text("🌫️ **Game ended.**")
        return
    
    if actor != dead_id: 
        await q.edit_message_text("🚫 **Not your revenge to take.**")
        return
    
    if g["alive"].get(target, False):
        tn = await get_name(target, context)
        r = g["roles"].get(target, "villager")
        rn = "Alpha Wolf" if r == "alpha_wolf" else r.title()
        
        await q.edit_message_text(f"🏹 **You shoot** {tn}!", parse_mode="Markdown")
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🏹 {await get_name(actor, context)} **shoots** {tn} **in revenge!**\n"
                f"💀 They were {rn} {get_role_emoji(r)}!"
            ),
            parse_mode="Markdown"
        )
        
        await kill_player(chat_id, target, context, "hunter")
    else:
        await q.edit_message_text("👻 **Target already dead.**")

#============== ENHANCED NIGHT RESOLUTION ==============
async def resolve_night(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced night resolution with all new role mechanics"""
    g = games.get(chat_id)
    if not g:
        return
        
    alive_ids = set(alive_players(chat_id))
    deaths_this_night = []
    saved_players = []
    
    # === SEER INVESTIGATIONS ===
    for seer_id, target in g["night_actions"]["seer_checks"].items():
        if g["alive"].get(seer_id, False) and target in alive_ids:
            target_role = g["roles"].get(target, "villager")
            
            # Check if target is Fool (appears as werewolf to seer)
            if target_role == "fool":
                result = "werewolf"
                g["night_actions"]["fool_investigations"][target] = g["night_actions"]["fool_investigations"].get(target, []) + [seer_id]
            else:
                result = "werewolf" if is_wolf(chat_id, target) else "villager"
            
            target_name = await get_name(target, context)
            try:
                await context.bot.send_message(
                    chat_id=seer_id,
                    text=f"🔮 **Vision:** {target_name} is a **{result}**",
                    parse_mode="Markdown"
                )
            except: 
                pass

    # === GRAVE ROBBER POWER USAGE ===
    for robber_id, dead_player_id in g["night_actions"]["grave_robber_uses"].items():
        if g["alive"].get(robber_id, False):
            await execute_grave_robber_power(chat_id, robber_id, dead_player_id, context)

    # === WOLF SHAMAN BLOCKING ===
    blocked_players = set()
    for shaman_id, target in g["night_actions"]["shaman_blocks"].items():
        if g["alive"].get(shaman_id, False) and is_wolf(chat_id, shaman_id) and g["roles"].get(shaman_id) == "wolf_shaman":
            blocked_players.add(target)

    # Apply blocking to various night actions
    if blocked_players:
        # Block seer checks
        g["night_actions"]["seer_checks"] = {k: v for k, v in g["night_actions"]["seer_checks"].items() if v not in blocked_players}
        # Block doctor saves
        if g["night_actions"]["doctor_save"] in blocked_players:
            g["night_actions"]["doctor_save"] = None
        # Block oracle checks
        g["night_actions"]["oracle_checks"] = {k: v for k, v in g["night_actions"]["oracle_checks"].items() if v not in blocked_players}
        # Block bodyguard protections
        g["night_actions"]["bodyguard_protects"] = {k: v for k, v in g["night_actions"]["bodyguard_protects"].items() if k not in blocked_players}

    # === FIRE TEAM ACTIONS (if fire team game) ===
    if g.get("evil_team_type") == "arsonists" and g["night_actions"].get("arsonist_ignited", False):
        # Check if accelerant expert boosted ignition
        accelerant_boost = any(
            action.get("boost", False) for action in g["night_actions"]["accelerant_actions"].values()
        )
        
        doused_players = g["night_actions"]["arsonist_doused"]
        fire_team = set(g.get("arsonist_team", []))
        alive_fire_team = [uid for uid in fire_team if g["alive"].get(uid, False)]
        
        if accelerant_boost:
            # Accelerant makes ignition kill everyone except fire team
            for player_id in alive_ids:
                if player_id not in fire_team:
                    deaths_this_night.append((player_id, "arsonist"))
        else:
            # Normal ignition only kills doused players
            for player_id in doused_players:
                if g["alive"].get(player_id, False) and player_id not in fire_team:
                    deaths_this_night.append((player_id, "arsonist"))
        
        # Announce the ignition
        if deaths_this_night:
            fire_names = [await get_name(uid, context) for uid in alive_fire_team]
            boost_text = " with chemical acceleration" if accelerant_boost else ""
            
            await context.bot.send_message(
                chat_id,
                text=(
                    f"🔥💥 **IGNITION!**{boost_text}\n"
                    f"🔥 {', '.join(fire_names)} set the village ablaze!\n"
                    f"💀 The flames consume everything!"
                ),
                parse_mode="Markdown"
            )
    
    # === WOLF ATTACK (only if not fire team game) ===
    wolf_target = None  # Initialize wolf_target here
    hunter_kills_wolf = False
    killed_wolf = None
    
    if g.get("evil_team_type") != "arsonists":
        wolf_votes = g["night_actions"]["wolf_votes"]
        
        if wolf_votes:
            alive_wolves = [w for w in wolf_votes.keys() if g["alive"].get(w, False)]
            valid_votes = {w: t for w, t in wolf_votes.items() if w in alive_wolves and t in alive_ids}
            
            if valid_votes:
                vote_counts = defaultdict(int)
                for target in valid_votes.values():
                    vote_counts[target] += 1
                
                max_votes = max(vote_counts.values())
                top_targets = [t for t, v in vote_counts.items() if v == max_votes]
                wolf_target = random.choice(top_targets) if top_targets else None
                
                # Check if wolves attacked the hunter
                if wolf_target is not None and g["roles"].get(wolf_target) == "hunter":
                    attacking_wolves = [w for w, t in valid_votes.items() if t == wolf_target]
                    if attacking_wolves:
                        killed_wolf = random.choice(attacking_wolves)
                        hunter_kills_wolf = True
                        
                        deaths_this_night.append((wolf_target, "wolves"))
                        deaths_this_night.append((killed_wolf, "hunter_counter"))
                        
                        hunter_name = await get_name(wolf_target, context)
                        wolf_name = await get_name(killed_wolf, context)
                        
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=(
                                f"🏹 **{hunter_name} fights back!**\n"
                                f"🐺 As the wolves attack, the hunter's arrow finds {wolf_name}!\n"
                                f"💀 Both hunter and wolf fall together!"
                            ),
                            parse_mode="Markdown"
                        )
        
        # === ALPHA WOLF CONVERSION ===
        if wolf_target and wolf_target in alive_ids and not hunter_kills_wolf:
            alpha_wolves = [w for w in alive_players(chat_id) if g["roles"].get(w) == "alpha_wolf"]
            
            if alpha_wolves and random.random() < 0.20 and not is_wolf(chat_id, wolf_target):
                # Check if target is blessed (immune to conversion)
                if wolf_target not in g["night_actions"]["blessed_players"]:
                    # Convert instead of kill
                    old_role = g["roles"].get(wolf_target, "villager")
                    g["roles"][wolf_target] = "werewolf"
                    wolf_target = None  # Don't kill, just convert
                    
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="🐺 **A howl echoes! Someone has been converted to a werewolf!**",
                        parse_mode="Markdown"
                    )
                    
                    try:
                        pack_members = [await get_name(w, context) for w in alive_players(chat_id) 
                                      if is_wolf(chat_id, w) and w != wolf_target]
                        pack_text = f"\n🐺 Your pack: {', '.join(pack_members)}" if pack_members else ""
                        
                        await context.bot.send_message(
                            wolf_target,
                            text=f"🐺 **You've been turned into a Werewolf!**{pack_text}",
                            parse_mode="Markdown"
                        )
                    except:
                        pass

    # === BODYGUARD PROTECTION ===
    bodyguard_saves = {}
    for bodyguard_id, protected_id in g["night_actions"]["bodyguard_protects"].items():
        if g["alive"].get(bodyguard_id, False) and g["alive"].get(protected_id, False):
            bodyguard_saves[protected_id] = bodyguard_id

    # === DOCTOR SAVE ===
    doctor_save = g["night_actions"]["doctor_save"]

    # === VIGILANTE KILLS ===
    vigilante_kills = []
    new_guilt = []
    
    for vig_id, target in g["night_actions"]["vigilante_kills"].items():
        if g["alive"].get(vig_id, False) and target in alive_ids:
            vigilante_kills.append((vig_id, target))
            if not is_wolf(chat_id, target) and not is_fire_team(chat_id, target):
                new_guilt.append(vig_id)

    # === WITCH POISON ===
    witch_poison = g["night_actions"]["witch_death"]

    # === PLAGUE DEATHS (from previous night) ===
    plague_deaths = []
    for victim in g["night_actions"]["plagued_players"]:
        if g["alive"].get(victim, False):
            plague_deaths.append((victim, "plague"))

    # === INSOMNIAC NOTIFICATIONS ===
    for insomniac_id in alive_ids:
        if g["roles"].get(insomniac_id) == "insomniac":
            visitors = []
            
            # Check who visited the insomniac
            if wolf_target is not None and insomniac_id == wolf_target:
                visitors.append("werewolves")
            if insomniac_id == g["night_actions"]["doctor_save"]:
                visitors.append("doctor")
            if insomniac_id in g["night_actions"]["bodyguard_protects"].values():
                visitors.append("bodyguard")
            if insomniac_id == g["night_actions"]["witch_death"]:
                visitors.append("witch")
            if insomniac_id in g["night_actions"]["vigilante_kills"].values():
                visitors.append("vigilante")
            
            try:
                if visitors:
                    visitor_text = ", ".join(visitors)
                    await context.bot.send_message(
                        insomniac_id,
                        text=f"👁️ **You saw these visitors tonight:** {visitor_text}",
                        parse_mode="Markdown"
                    )
                else:
                    await context.bot.send_message(
                        insomniac_id,
                        text="👁️ **No one visited you tonight.**",
                        parse_mode="Markdown"
                    )
            except:
                pass

    # === COMPILE DEATH LIST (if not fire team ignition) ===
    if not (g.get("evil_team_type") == "arsonists" and g["night_actions"].get("arsonist_ignited", False)):
        # Wolf kill (only if not hunter counter-attack)
        if wolf_target and not hunter_kills_wolf:
            # Check bodyguard protection first
            if wolf_target in bodyguard_saves:
                bodyguard_id = bodyguard_saves[wolf_target]
                deaths_this_night.append((bodyguard_id, "bodyguard"))
                saved_players.append((wolf_target, "bodyguard"))
            elif wolf_target == doctor_save:
                saved_players.append((wolf_target, "doctor"))
            else:
                # Check if cursed villager
                if wolf_target in g["night_actions"]["cursed_players"]:
                    # Convert to werewolf instead of killing
                    g["roles"][wolf_target] = "werewolf"
                    g["night_actions"]["cursed_players"].discard(wolf_target)
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="🌑 **The curse activates! A villager transforms into a werewolf!**",
                        parse_mode="Markdown"
                    )
                    try:
                        pack_members = [await get_name(w, context) for w in alive_players(chat_id) 
                                      if is_wolf(chat_id, w) and w != wolf_target]
                        pack_text = f"\n🐺 Your pack: {', '.join(pack_members)}" if pack_members else ""
                        await context.bot.send_message(
                            wolf_target,
                            text=f"😨 **Your curse activated! You're now a Werewolf!**{pack_text}",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                else:
                    deaths_this_night.append((wolf_target, "wolves"))
        
        # Witch poison
        if witch_poison:
            if witch_poison in bodyguard_saves:
                bodyguard_id = bodyguard_saves[witch_poison]
                deaths_this_night.append((bodyguard_id, "bodyguard"))
                saved_players.append((witch_poison, "bodyguard"))
            elif witch_poison == doctor_save:
                saved_players.append((witch_poison, "doctor"))
            elif witch_poison not in [d[0] for d in deaths_this_night]:
                deaths_this_night.append((witch_poison, "witch"))
        
        # Vigilante kills
        for vig_id, target in vigilante_kills:
            if target in bodyguard_saves:
                bodyguard_id = bodyguard_saves[target]
                deaths_this_night.append((bodyguard_id, "bodyguard"))
                saved_players.append((target, "bodyguard"))
            elif target == doctor_save:
                saved_players.append((target, "doctor"))
            elif target not in [d[0] for d in deaths_this_night]:
                deaths_this_night.append((target, "vigilante"))
        
        # Add plague deaths
        deaths_this_night.extend(plague_deaths)

    # === WITCH LIFE POTION SAVES ===
    witch_auto_save = None
    for witch_id in alive_ids:
        if (g["roles"].get(witch_id) == "witch" and 
            g["night_actions"]["witch_life"] == "auto" and
            g["night_actions"]["witch_potions"].get(witch_id, {}).get("life", False)):
            
            if deaths_this_night:
                # Save the first person who would die
                saved_victim = deaths_this_night[0][0]
                witch_auto_save = saved_victim
                
                # Remove from death list
                deaths_this_night = [(pid, cause) for pid, cause in deaths_this_night if pid != saved_victim]
                saved_players.append((saved_victim, "witch"))
                
                # Use up the potion
                g["night_actions"]["witch_potions"][witch_id]["life"] = False
                break

    # === DOPPELGANGER TRANSFORMATION ===
    if deaths_this_night:
        first_death_id = deaths_this_night[0][0]
        first_death_role = g["roles"].get(first_death_id)
        
        # Find doppelgangers who can transform
        for player_id in alive_ids:
            if (g["roles"].get(player_id) == "doppelganger" and 
                not g.get("doppelganger_role")):  # Only if not already transformed
                
                if first_death_role and first_death_role not in ("doppelganger", "jester"):
                    g["roles"][player_id] = first_death_role
                    g["doppelganger_role"] = first_death_role
                    
                    role_name = "Alpha Wolf" if first_death_role == "alpha_wolf" else first_death_role.title().replace("_", " ")
                    
                    try:
                        role_desc = get_role_description(first_death_role)
                        await context.bot.send_message(
                            player_id,
                            text=(
                                f"🎭 **TRANSFORMATION!**\n"
                                f"💀 {await get_name(first_death_id, context)} has died!\n"
                                f"✨ You are now a **{role_name}**!\n\n"
                                f"{role_desc}"
                            ),
                            parse_mode="Markdown"
                        )
                        
                        # If becoming a wolf, inform the pack
                        if first_death_role in ("werewolf", "alpha_wolf", "wolf_shaman"):
                            pack_members = [await get_name(w, context) for w in alive_players(chat_id) 
                                          if is_wolf(chat_id, w) and w != player_id]
                            if pack_members:
                                pack_text = f"\n🐺 Your pack: {', '.join(pack_members)}"
                                await context.bot.send_message(
                                    player_id,
                                    text=pack_text,
                                    parse_mode="Markdown"
                                )
                                
                                # Notify existing wolves
                                dopple_name = await get_name(player_id, context)
                                for wolf_id in [w for w in alive_players(chat_id) if is_wolf(chat_id, w) and w != player_id]:
                                    try:
                                        await context.bot.send_message(
                                            wolf_id,
                                            text=f"🎭 {dopple_name} **has joined the pack!**",
                                            parse_mode="Markdown"
                                        )
                                    except:
                                        pass
                        
                    except Exception as e:
                        print(f"Could not notify doppelganger {player_id} of transformation: {e}")
                break  # Only one doppelganger can transform per death

    # === EXECUTE DEATHS ===
    for victim_id, cause in deaths_this_night:
        await kill_player(chat_id, victim_id, context, cause)

    # === APPRENTICE SEER ACTIVATION ===
    for death_id, cause in deaths_this_night:
        if g["roles"].get(death_id) == "seer":
            # Find apprentice seer and activate them
            for player_id in alive_ids:
                if g["roles"].get(player_id) == "apprentice_seer" and not g.get("apprentice_active", False):
                    g["apprentice_active"] = True
                    g["roles"][player_id] = "seer"  # Transform apprentice into seer
                    
                    try:
                        await context.bot.send_message(
                            player_id,
                            text="🔮📚 **Your master has fallen! You are now the Seer!** You can check players each night.",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                    break

    # === NOTIFY SAVED PLAYERS ===
    for saved_id, saved_by in saved_players:
        await notify_player_death(chat_id, saved_id, context, saved_by=saved_by)

    # === VIGILANTE GUILT DEATHS ===
    guilt_deaths = []
    for vig_id in new_guilt:
        if g["alive"].get(vig_id, False):
            g["night_actions"]["vigilante_guilt"].add(vig_id)
            await kill_player(chat_id, vig_id, context, "guilt")
            guilt_deaths.append(vig_id)

    # === NIGHT SUMMARY ===
    if not deaths_this_night and not guilt_deaths and not saved_players:
        await context.bot.send_message(
            chat_id, 
            text="🌙 **Peaceful night. Everyone survived.**",
            parse_mode="Markdown"
        )
    else:
        summary_parts = ["💀 **Night Results:**"]
        
        for victim_id, cause in deaths_this_night:
            if not g["alive"].get(victim_id, False):
                victim_name = await get_name(victim_id, context)
                victim_role = g["roles"].get(victim_id, "villager")
                role_display = "Alpha Wolf" if victim_role == "alpha_wolf" else victim_role.title()
                
                if cause == "wolves":
                    summary_parts.append(f"🐺 {victim_name} was killed by werewolves")
                elif cause == "witch":
                    summary_parts.append(f"☠️ {victim_name} was poisoned by the witch")
                elif cause == "vigilante":
                    summary_parts.append(f"⚔️ {victim_name} was shot by vigilante")
                elif cause == "hunter_counter":
                    summary_parts.append(f"🏹 {victim_name} was killed by hunter's counter-attack")
                elif cause == "arsonist":
                    summary_parts.append(f"🔥 {victim_name} burned to death")
                elif cause == "bodyguard":
                    summary_parts.append(f"🛡️ {victim_name} died protecting someone")
                elif cause == "plague":
                    summary_parts.append(f"🦠 {victim_name} succumbed to plague")
                
                summary_parts.append(f"   🎭 They were {role_display} {get_role_emoji(victim_role)}")
        
        for guilt_victim in guilt_deaths:
            guilt_name = await get_name(guilt_victim, context)
            summary_parts.append(f"💔 {guilt_name} died of guilt (killed innocent)")
        
        for saved_id, saved_by in saved_players:
            saved_name = await get_name(saved_id, context)
            if saved_by == "doctor":
                summary_parts.append(f"💊 {saved_name} was saved by the Doctor")
            elif saved_by == "witch":
                summary_parts.append(f"✨ {saved_name} was revived by the Witch")
            elif saved_by == "bodyguard":
                summary_parts.append(f"🛡️ {saved_name} was protected by the Bodyguard")
        
        if summary_parts:
            await context.bot.send_message(chat_id, text="\n".join(summary_parts), parse_mode="Markdown")

    # === CLEAR NIGHT ACTIONS ===
    actions_to_clear = [
        "wolf_votes", "seer_checks", "vigilante_kills", "cupid_picks",
        "oracle_checks", "bodyguard_protects", "fire_starter_actions",
        "shaman_blocks", "detective_checks", "grave_robber_uses",
        "priest_blessings", "plague_victims"
    ]
    for action in actions_to_clear:
        if action in g["night_actions"]:
            if isinstance(g["night_actions"][action], dict):
                g["night_actions"][action].clear()
            elif isinstance(g["night_actions"][action], list):
                g["night_actions"][action][:] = []
    
    # Clear single-use actions
    single_actions = ["doctor_save", "witch_life", "witch_death", "hunter_revenge_pending"]
    for action in single_actions:
        g["night_actions"][action] = None
    
    # Clear communication dictionaries
    g["pending_wolf_messages"] = {}
    if "pending_fire_messages" not in g:
        g["pending_fire_messages"] = {}
    g["pending_fire_messages"] = {}
    
    # Update plague progression
    current_plagued = set(g["night_actions"]["plague_victims"].values())
    g["night_actions"]["plagued_players"] = current_plagued
    g["night_actions"]["plague_victims"].clear()  # Reset for next night
    
    await send_player_status(chat_id, context)

#============== ENHANCED WIN CONDITIONS ==============

def cleanup_game_state(g: dict):
    """Clean up game state resources"""
    # Cancel any running tasks
    if g.get("game_loop_task") and not g["game_loop_task"].done():
        g["game_loop_task"].cancel()
    
    # Clear all active buttons
    g["active_buttons"] = {}
    g["phase_active"] = False
    g["phase_end_time"] = None
    
    # Clear communication states
    g["pending_wolf_messages"] = {}
    g["pending_fire_messages"] = {}
    
    # Clear temporary game flags
    g["join_open"] = False


async def try_end(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if game should end and declare winners with enhanced conditions"""
    g = games.get(chat_id)
    if not g or not g.get("started"):
        return True
        
    alive_ids = alive_players(chat_id)
    lovers = list(g["night_actions"].get("lovers", []))
    
    def end_game(winner_type: str) -> bool:
        """Helper to properly end game"""
        cleanup_game_state(g)
        g["started"] = False
        return True
    
    # Jester already won
    if g.get("jester_lynched"): 
        await send_final_game_summary(chat_id, context, "jester")
        return end_game("jester")
    
    # Check Executioner win
    if g.get("executioner_won", False):
        executioner_id = g.get("executioner_id")
        if executioner_id:
            executioner_name = await get_name(executioner_id, context)
            target_id = g["night_actions"].get("executioner_target")
            target_name = await get_name(target_id, context) if target_id else "Unknown"
            await context.bot.send_message(
                chat_id,
                text=(
                    f"🪓 **EXECUTIONER WINS!**\n"
                    f"⚖️ {executioner_name} successfully got {target_name} lynched!"
                ),
                parse_mode="Markdown"
            )
            await send_final_game_summary(chat_id, context, "executioner")
            return end_game("executioner")
    
    # Check Fire Team win
    if g.get("evil_team_type") == "arsonists":
        fire_team = g.get("arsonist_team", [])
        living_fire_team = [uid for uid in fire_team if g["alive"].get(uid, False)]
        
        # Fire team wins if they ignited successfully
        if g["night_actions"].get("arsonist_ignited", False) and living_fire_team:
            team_names = [await get_name(uid, context) for uid in living_fire_team]
            await context.bot.send_message(
                chat_id,
                text=(
                    f"🔥💥 **FIRE TEAM WINS!**\n"
                    f"🔥 {', '.join(team_names)} burn down the entire village!\n"
                    f"💀 The flames consume everything!"
                ),
                parse_mode="Markdown"
            )
            await send_final_game_summary(chat_id, context, "fire_team")
            return end_game("fire_team")
        
        # Fire team wins if they're the only ones left
        if alive_ids and set(alive_ids) == set(living_fire_team):
            team_names = [await get_name(uid, context) for uid in living_fire_team]
            await context.bot.send_message(
                chat_id,
                text=(
                    f"🔥 **FIRE TEAM WINS!**\n"
                    f"💀 {', '.join(team_names)} are the last survivors!\n"
                    f"🏆 The fire cult claims victory!"
                ),
                parse_mode="Markdown"
            )
            await send_final_game_summary(chat_id, context, "fire_team")
            return end_game("fire_team")
        
        # Check if fire team is eliminated
        if not living_fire_team:
            await context.bot.send_message(
                chat_id, 
                text="🎉 **VILLAGERS WIN!** The fire threat has been eliminated!",
                parse_mode="Markdown"
            )
            await send_final_game_summary(chat_id, context, "villagers")
            return end_game("villagers")
        
        # Check for lovers win among remaining players
        if len(lovers) == 2 and len(alive_ids) == 2 and all(l in alive_ids for l in lovers):
            lover_names = [await get_name(l, context) for l in lovers]
            await context.bot.send_message(
                chat_id, 
                text=(
                    f"💘 **LOVERS WIN!**\n"
                    f"💕 {lover_names[0]} and {lover_names[1]} survive together!"
                ),
                parse_mode="Markdown"
            )
            await send_final_game_summary(chat_id, context, "lovers")
            return end_game("lovers")
        
        return False  # Fire team game continues
    
    # Regular wolf team game logic
    else:
        wolves = [u for u in alive_ids if is_wolf(chat_id, u)]
        villagers = [u for u in alive_ids if not is_wolf(chat_id, u)]
        
        # Check for lovers win (only lovers left alive)
        if len(lovers) == 2 and len(alive_ids) == 2 and all(l in alive_ids for l in lovers):
            lover_names = [await get_name(l, context) for l in lovers]
            await context.bot.send_message(
                chat_id, 
                text=(
                    f"💘 **LOVERS WIN!**\n"
                    f"💕 {lover_names[0]} and {lover_names[1]} survive together!"
                ),
                parse_mode="Markdown"
            )
            await send_final_game_summary(chat_id, context, "lovers")
            return end_game("lovers")
        
        # Check for villager win (no wolves left)
        if not wolves:
            winner_type = "villagers_and_lovers" if any(l in villagers for l in lovers) else "villagers"
            await context.bot.send_message(
                chat_id, 
                text="🎉 **VILLAGERS WIN!** All werewolves eliminated!",
                parse_mode="Markdown"
            )
            await send_final_game_summary(chat_id, context, winner_type)
            return end_game(winner_type)
        
        # Check for werewolf win (wolves >= villagers)
        if len(wolves) >= len(villagers):
            winner_type = "werewolves_and_lovers" if any(l in wolves for l in lovers) else "werewolves"
            await context.bot.send_message(
                chat_id, 
                text="🐺 **WEREWOLVES WIN!** They outnumber the villagers!",
                parse_mode="Markdown"
            )
            await send_final_game_summary(chat_id, context, winner_type)
            return end_game(winner_type)
    
    # Game continues
    return False

#============== ENHANCED FINAL GAME SUMMARY ==============

async def send_final_game_summary(chat_id: int, context: ContextTypes.DEFAULT_TYPE, winners: str):
    """Send comprehensive game summary with all role types"""
    g = games.get(chat_id)
    if not g:
        return
        
    alive_count = len(alive_players(chat_id))
    total_players = len(g["players"])
    game_duration = format_game_duration(g.get("start_time"))
    lovers = list(g["night_actions"].get("lovers", []))
    
    # Header with game stats
    summary_lines = [
        "🏆 **═══ GAME OVER ═══**",
        f"⏰ Game Duration: **{game_duration}**",
        f"🌙 Nights Survived: **{g.get('night_number', 0)}**",
        f"💀 Deaths: **{total_players - alive_count}/{total_players}**",
        f"🎭 Evil Team: **{g.get('evil_team_type', 'unknown').title()}**",
        ""
    ]
    
    # Special handling for unique wins
    if winners == "jester":
        summary_lines.extend([
            "🃏 **═══ JESTER WINS ═══**",
            "🎪 Chaos triumphs over order!",
            ""
        ])
        
    elif winners == "executioner":
        summary_lines.extend([
            "🪓 **═══ EXECUTIONER WINS ═══**",
            "⚖️ Justice served through manipulation!",
            ""
        ])
        
    elif winners == "fire_team":
        summary_lines.extend([
            "🔥 **═══ FIRE TEAM WINS ═══**",
            "💥 The flames consumed all!",
            ""
        ])
        
    elif winners == "lovers":
        summary_lines.extend([
            "💘 **═══ LOVE WINS ═══**",
            "💕 True love conquers all!",
            ""
        ])

    # Separate teams for display
    wolf_players = []
    fire_players = []
    village_players = []
    neutral_players = []
    
    for player_id in g["players"]:
        name = await get_name(player_id, context)
        role = g["roles"].get(player_id, "villager")
        role_display = "Alpha Wolf" if role == "alpha_wolf" else role.title().replace("_", " ")
        emoji = get_role_emoji(role)
        status = "🙂 Alive" if g["alive"].get(player_id, False) else "💀 Dead"
        lover_mark = " 💘" if player_id in lovers else ""
        
        player_line = f"{name}: {status} - {role_display} {emoji}{lover_mark}"
        
        if is_wolf(chat_id, player_id):
            wolf_players.append(player_line)
        elif is_fire_team(chat_id, player_id):
            fire_players.append(player_line)
        elif role in ("jester", "executioner"):
            neutral_players.append(player_line)
        else:
            village_players.append(player_line)
    
    # Determine win/loss status
    if winners.startswith("villagers"):
        village_status = "🏆 **WINNERS**"
        evil_status = "💀 **DEFEATED**"
    elif winners.startswith("werewolves"):
        village_status = "💀 **DEFEATED**"
        evil_status = "🏆 **WINNERS**"
    elif winners == "fire_team":
        village_status = "💀 **DEFEATED**"
        evil_status = "🏆 **WINNERS**"
    elif winners in ("lovers", "jester", "executioner"):
        village_status = evil_status = "💔 **DEFEATED**"
    else:
        village_status = evil_status = "❓ **UNKNOWN**"
    
    # Add team sections
    if wolf_players:
        summary_lines.extend([
            f"🐺 **WOLF PACK ({evil_status}):**",
            *[f"  {player}" for player in wolf_players],
            ""
        ])
    
    if fire_players:
        summary_lines.extend([
            f"🔥 **FIRE TEAM ({evil_status}):**",
            *[f"  {player}" for player in fire_players],
            ""
        ])
    
    if village_players:
        summary_lines.extend([
            f"🏡 **VILLAGERS ({village_status}):**",
            *[f"  {player}" for player in village_players],
            ""
        ])
    
    if neutral_players:
        summary_lines.extend([
            f"🎭 **NEUTRAL ROLES:**",
            *[f"  {player}" for player in neutral_players],
            ""
        ])
    
    # Special achievements
    if "lovers" in winners and len(lovers) == 2:
        lover_names = [await get_name(l, context) for l in lovers]
        summary_lines.extend([
            f"💘 **LOVE CONQUERED ALL!**",
            f"💕 {' & '.join(lover_names)} proved love is strongest!",
            ""
        ])
    
    # Closing
    summary_lines.extend([
        f"🌟 **Thanks for {game_duration} of fun!** 🎮"
    ])
    
    await context.bot.send_message(chat_id, text="\n".join(summary_lines), parse_mode="Markdown")

#============== ADMIN COMMANDS ==============

async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to forcibly stop the current game"""
    chat_id = update.effective_chat.id
    
    try:
        member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text(
                "👑 **Admin only!** Only admins can stop games.",
                parse_mode="Markdown"
            )
            return
    except:
        await update.message.reply_text(
            "❓ **Cannot verify admin status.**",
            parse_mode="Markdown"
        )
        return
    
    g = games.get(chat_id)
    if not g:
        await update.message.reply_text(
            "🌫️ **No game running here.**",
            parse_mode="Markdown"
        )
        return
    
    if not g.get("started") and not g.get("join_open"):
        await update.message.reply_text(
            "⚰️ **Game already ended.**",
            parse_mode="Markdown"
        )
        return
    
    if g.get("game_loop_task") and not g["game_loop_task"].done():
        g["game_loop_task"].cancel()
    
    games.pop(chat_id, None)
    await update.message.reply_text(
        "⚡ **Game stopped by admin!** All supernatural forces banished.",
        parse_mode="Markdown"
    )

async def game_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current game status"""
    chat_id = update.effective_chat.id
    g = games.get(chat_id)
    
    if not g:
        await update.message.reply_text(
            "🌫️ **No game here.** Use /rampage to start one!",
            parse_mode="Markdown"
        )
        return
    
    if not g.get("started"):
        player_count = len(g.get("players", []))
        join_status = "open" if g.get("join_open") else "closed"
        await update.message.reply_text(
            f"🎭 **Join phase active**\n"
            f"👥 {player_count} players joined\n"
            f"🚪 Joining is {join_status}",
            parse_mode="Markdown"
        )
    else:
        night_num = g.get("night_number", 0)
        game_duration = format_game_duration(g.get("start_time"))
        evil_team = g.get("evil_team_type", "unknown").title()
        await update.message.reply_text(
            f"🌙 **Game active - Night {night_num}**\n"
            f"⏰ Running for {game_duration}\n"
            f"🎭 Evil team: {evil_team}",
            parse_mode="Markdown"
        )
        await send_player_status(chat_id, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    help_text = """
🐺 **ENHANCED WEREWOLF BOT COMMANDS**

🌙 **Start Game:**
⚡ `/rampage` - Start new game (120s join window)
🗡️ `/join` - Join the current game
👑 `/startgame` - Force start (Admin only)

📊 **Info:**
🔮 `/status` - Check game state
❓ `/help` - Show this help

⚖️ **Admin:**
🛑 `/stop` - End current game (Admin only)

🎯 **How to Play:**
1. Use `/rampage` to start gathering players
2. Players `/join` within 120 seconds
3. Game auto-starts or admin can `/startgame`
4. Follow private messages for your role
5. Vote during day, use powers at night

⚠️ **IMPORTANT:** You must `/start` this bot privately to play!

🎲 **Evil Teams (Random):**
🐺 **Wolf Team:** Traditional werewolves with pack mechanics
🔥 **Fire Team:** Arsonists who douse and ignite players

🎭 **Enhanced Roles Include:**
**Original:** 🐺 Werewolf, 🔮 Seer, 💊 Doctor, 🏹 Hunter, 💘 Cupid, 🧙‍♀️ Witch, 🕵️ Detective, 🃏 Jester, 🎭 Doppelganger, ⚔️ Vigilante, 🏛️ Mayor, 👤 Villager

**New Village:** 🌟 Oracle, 🛡️ Bodyguard, 👁️ Insomniac, 👥 Twin, ⚰️ Grave Robber, 🔮📚 Apprentice Seer, 🦠 Plague Doctor, ⛪ Priest

**New Evil:** 🐺🔮 Wolf Shaman, 🔥 Arsonist, 🔥⚡ Fire Starter, 🔥🧪 Accelerant Expert

**Chaos:** 😨 Cursed Villager, 🤡 Fool

**Neutral:** 🪓 Executioner

🏆 **Win Conditions:**
🎉 Villagers: Eliminate all evil players
🐺 Werewolves: Equal or outnumber villagers
🔥 Fire Team: Ignite all players OR be last standing
💘 Lovers: Be the last two alive
🃏 Jester: Get executed by village
🪓 Executioner: Get your target lynched

🌟 **New Features:**
- Evil team randomization (Wolf vs Fire)
- Team communication systems
- Enhanced role interactions
- Balanced player scaling (4-15+ players)

🍀 **Good luck and have fun!**
    """
    await update.message.reply_text(help_text.strip(), parse_mode="Markdown")

#============== MAIN RUNNER ==============
def main():
    """Main function to start and run the enhanced werewolf bot with error handling"""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Error: Please set your BOT_TOKEN in the config section!")
        return
    
    # Configure logging to reduce noise from network errors
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.WARNING  # Only show warnings and errors
    )
    
    # Reduce httpx and telegram library logging
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("telegram").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    
    print("🌙 ════════════════════════════")
    print("🐺    ENHANCED WEREWOLF BOT   🐺")
    print("🌙 ════════════════════════════")
    print("⚡ Starting up...")
    
    # Create application with better network settings
    app = (ApplicationBuilder()
           .token(BOT_TOKEN)
           .connect_timeout(30)      # 30 second connection timeout
           .read_timeout(30)         # 30 second read timeout
           .write_timeout(30)        # 30 second write timeout
           .pool_timeout(30)         # 30 second pool timeout
           .build())
    
    # Add command handlers
    app.add_handler(CommandHandler("rampage", rampage))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("stop", stop_game))
    app.add_handler(CommandHandler("status", game_status))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", help_command))
    
    # Add callback query handler for all button interactions
    app.add_handler(CallbackQueryHandler(callback_router))
    
    # Add message handler for team communication
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Add error handler
    async def error_handler(update, context):
        """Handle errors caused by updates."""
        if isinstance(context.error, (NetworkError, TimedOut)):
            print(f"⚠️  Network issue (will retry): {context.error}")
            return  # Don't log network errors, they're expected
        else:
            print(f"💥 Update {update} caused error: {context.error}")
    
    app.add_error_handler(error_handler)
    
    # Success message
    print("✅ Bot handlers loaded!")
    print("🎮 Enhanced multi-chat werewolf bot ready!")
    print("🌙 ═══ READY TO HUNT ═══")
    print("📜 Send /help in groups for guidance!")
    print("⚠️  Players must /start bot privately!")
    print("🔄 Press Ctrl+C to stop")
    print("🌙 ════════════════════════════")
    
    # Run the bot with retry logic
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        try:
            print("🚀 **ENHANCED BOT RUNNING!**")
            app.run_polling(
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query', 'inline_query'],
                close_loop=False  # Don't close the event loop on error
            )
            break  # If we get here, polling ended normally
            
        except KeyboardInterrupt:
            print("\n🛑 ═══ SHUTDOWN REQUESTED ═══")
            print("👤 Bot stopped by user...")
            break
            
        except (NetworkError, TimedOut) as e:
            retry_count += 1
            wait_time = min(60, 5 * retry_count)  # Progressive backoff, max 60 seconds
            print(f"\n⚠️  Network error (attempt {retry_count}/{max_retries}): {e}")
            print(f"⏳ Retrying in {wait_time} seconds...")
            
            if retry_count >= max_retries:
                print("💥 Max retries reached. Giving up.")
                break
                
            try:
                import time
                time.sleep(wait_time)
            except KeyboardInterrupt:
                print("\n🛑 Shutdown during retry wait...")
                break
                
        except Exception as e:
            print(f"\n💥 ═══ UNEXPECTED ERROR ═══")
            print(f"⚡ {e}")
            retry_count += 1
            
            if retry_count >= max_retries:
                print("💥 Max retries reached. Giving up.")
                break
                
            print(f"⏳ Retrying in 10 seconds... (attempt {retry_count}/{max_retries})")
            try:
                import time
                time.sleep(10)
            except KeyboardInterrupt:
                print("\n🛑 Shutdown during retry wait...")
                break
    
    print("🌅 ═══ BOT SHUTDOWN ═══")
    print("👻 All games ended...")
    print("👋 **Enhanced Werewolf Bot - Goodbye!**")
    print("🌙 ════════════════════════════")

if __name__ == "__main__":
    main()
