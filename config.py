import os
import logging
from typing import Dict
from enums import Role

BOT_TOKEN = "7756296028:AAEdYJdvi7GfG-HCKfv1X0-CN5o94XgkVT4"  # Replace with your actual token

# Game Settings
MIN_PLAYERS = 5
MAX_PLAYERS = 20
EVIL_TEAM_RATIO = 0.25

# Timer durations in seconds
VOTING_TIME_LIMIT = 10  # 5 minutes
NIGHT_ACTION_TIME_LIMIT = 45  # 3 minutes
DAY_DISCUSSION_TIME = 5  # 30 seconds

GIF_DIR = os.path.join(os.path.dirname(__file__), 'gif')

# ═══════════════════════════════════════════════════════════
# PHASE TRANSITION GIFS
# ═══════════════════════════════════════════════════════════
PHASE_GIFS = {
    "night_begins": "gif/phases/night_begins.mp4",
    "day_begins": "gif/phases/day_begins.mp4",
    "voting_begins": "gif/phases/voting_begins.mp4",
    "game_end": "gif/phases/game_end.mp4"
}
# ═══════════════════════════════════════════════════════════
# ACTION GIFS
# ═══════════════════════════════════════════════════════════
ACTION_GIFS = {
    "wolf_hunt": os.path.join(GIF_DIR, "actions", "wolf_hunt.mp4"),
    "seer_check": os.path.join(GIF_DIR, "actions", "seer_check.mp4"),
    "doctor_heal": os.path.join(GIF_DIR, "actions", "doctor_heal.mp4"),
    "witch_poison": os.path.join(GIF_DIR, "actions", "witch_poison.mp4"),
    "witch_heal": os.path.join(GIF_DIR, "actions", "witch_heal.mp4"),
    "fire_douse": os.path.join(GIF_DIR, "actions", "fire_douse.mp4"),
    "fire_ignite": os.path.join(GIF_DIR, "actions", "fire_ignite.mp4"),
    "detective_investigate": os.path.join(GIF_DIR, "actions", "detective_investigate.mp4"),
    "mayor_reveal": os.path.join(GIF_DIR, "actions", "mayor_reveal.mp4"),
    "cupid_bind": os.path.join(GIF_DIR, "actions", "cupid_bind.mp4"),
}

DEATH_GIFS = {
    "wolves": "gif/deaths/wolves.mp4",
    "hunter_counter": "gif/deaths/hunter_counter.mp4",  # ⭐ ADD THIS
    "serial_killer": "gif/deaths/serial_killer.mp4",
    "serial_killer_defense": "gif/deaths/serial_killer_defense.mp4",  # ⭐ ADD THIS
    "fire": "gif/deaths/fire.mp4",
    "poison": "gif/deaths/poison.mp4",
    "plague": "gif/deaths/plague.mp4",
    "bodyguard_sacrifice": "gif/deaths/bodyguard_sacrifice.mp4",
    "lover_grief": "gif/deaths/lover_grief.mp4",
    "lynch": "gif/deaths/lynch.mp4",
    "vigilante": "gif/deaths/vigilante.mp4",
    "vigilante_fail": "gif/deaths/vigilante_fail.mp4",
    "doctor_save": "gif/deaths/doctor_save.mp4",
    "no_deaths": "gif/deaths/no_deaths.mp4",
    "unknown": "gif/deaths/unknown.mp4"
}

# ═══════════════════════════════════════════════════════════
# WIN CONDITION GIFS
# ═══════════════════════════════════════════════════════════
WIN_GIFS = {
    "villager_win": os.path.join(GIF_DIR, "wins", "villager_victory.mp4"),
    "wolf_win": os.path.join(GIF_DIR, "wins", "wolf_victory.mp4"),
    "fire_win": os.path.join(GIF_DIR, "wins", "fire_victory.mp4"),
    "serial_killer_win": os.path.join(GIF_DIR, "wins", "serial_killer_victory.mp4"),
    "killer_win": os.path.join(GIF_DIR, "wins", "serial_killer_victory.mp4"),  # ⭐ ADD (alias)
    "jester_win": os.path.join(GIF_DIR, "wins", "jester_victory.mp4"),
    "executioner_win": os.path.join(GIF_DIR, "wins", "executioner_victory.mp4"),
    "neutral_win": os.path.join(GIF_DIR, "wins", "jester_victory.mp4")  # ⭐ ADD (reuse)
}

# ═══════════════════════════════════════════════════════════
# MISC EVENT GIFS
# ═══════════════════════════════════════════════════════════
MISC_GIFS = {
    "game_start": os.path.join(GIF_DIR, "misc", "game_start.mp4"),
    "tie_vote": os.path.join(GIF_DIR, "misc", "tie_vote.mp4"),
    "no_lynch": os.path.join(GIF_DIR, "misc", "tie_vote.mp4"),  # ⭐ ADD (reuse)
    "afk_warning": os.path.join(GIF_DIR, "misc", "afk_warning.mp4"),
    "afk_kick": os.path.join(GIF_DIR, "misc", "afk_kick.mp4"),
}

ROLE_IMAGES = {
    Role.VILLAGER: "assets/roles/villager.jpg",
    Role.WEREWOLF: "assets/roles/werewolf.jpg",
    Role.ALPHA_WOLF: "assets/roles/alpha_wolf.jpg",
    Role.SEER: "assets/roles/seer.jpg",
    Role.DOCTOR: "assets/roles/doctor.jpg",
    Role.HUNTER: "assets/roles/hunter.jpg",
    Role.WITCH: "assets/roles/witch.jpg",
    Role.DETECTIVE: "assets/roles/detective.jpg",
    Role.SERIAL_KILLER: "assets/roles/serial_killer.jpg",
    Role.ARSONIST: "assets/roles/arsonist.jpg",
    Role.BLAZEBRINGER: "assets/roles/blazebringer.jpg",
    Role.JESTER: "assets/roles/jester.jpg",
    Role.CUPID: "assets/roles/cupid.jpg",
    Role.MAYOR: "assets/roles/mayor.jpg",
    Role.BODYGUARD: "assets/roles/bodyguard.jpg",
    Role.PRIEST: "assets/roles/priest.jpg",
    Role.VIGILANTE: "assets/roles/vigilante.jpg",
    Role.ORACLE: "assets/roles/oracle.jpg",
    Role.DOPPELGANGER: "assets/roles/doppelganger.jpg",
    Role.GRAVE_ROBBER: "assets/roles/grave_robber.jpg",
    Role.PLAGUE_DOCTOR: "assets/roles/plague_doctor.jpg",
    Role.CURSED_VILLAGER: "assets/roles/cursed_villager.jpg",
    Role.FOOL: "assets/roles/fool.jpg",
    Role.INSOMNIAC: "assets/roles/insomniac.jpg",
    Role.TWINS: "assets/roles/twins.jpg",
    Role.APPRENTICE_SEER: "assets/roles/apprentice_seer.jpg",
    Role.WOLF_SHAMAN: "assets/roles/wolf_shaman.jpg",
    Role.ACCELERANT_EXPERT: "assets/roles/accelerant_expert.jpg",
    Role.WEBKEEPER: "assets/roles/webkeeper.jpg",
    Role.STRAY: "assets/roles/stray.jpg",
    Role.MIRROR_PHANTOM: "assets/roles/mirror_phantom.jpg",
    Role.THIEF: "assets/roles/thief.jpg",
    Role.EXECUTIONER: "assets/roles/executioner.jpg",
}

# ═══════════════════════════════════════════════════════════
# HELPER FUNCTION
# ═══════════════════════════════════════════════════════════
def get_gif_path(category: str, key: str) -> str:
    """
    Get GIF path from appropriate dictionary
    
    Args:
        category: "phase", "action", "death", "win", or "misc"
        key: The specific GIF key
    
    Returns:
        File path if exists, None otherwise
    """
    gif_dicts = {
        "phase": PHASE_GIFS,
        "action": ACTION_GIFS,
        "death": DEATH_GIFS,
        "win": WIN_GIFS,
        "misc": MISC_GIFS,
    }
    
    gif_dict = gif_dicts.get(category, {})
    path = gif_dict.get(key)
    
    if path and os.path.exists(path):
        return path
    return None

# ═══════════════════════════════════════════════════════════
# LOGGING CONFIGURATION
# ═══════════════════════════════════════════════════════════
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)