import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, List
from enums import GamePhase, Team, Role
from telegram import User
from config import MAX_PLAYERS, MIN_PLAYERS

logger = logging.getLogger(__name__)

class Player:
    """Represents a player in the Werewolf game"""
    
    def __init__(self, user_id: int, username: str, first_name: str):
        self.user_id = user_id
        self.username = username or ""
        self.first_name = first_name
        self.role: Optional[Role] = None
        self.is_alive = True
        self.has_acted = False
        self.votes_received = 0
        self.has_voted = False
        self.voted_for: Optional[int] = None
        self.game_actions = {}
        self._death_announced = False

        # Role-specific attributes
        self.is_mayor_revealed = False
        self.lover_id: Optional[int] = None
        self.executioner_target: Optional[int] = None
        self.witch_heal_used = False
        self.witch_poison_used = False
        self.hunter_can_shoot = False
        self.vigilante_killed_innocent = False
        self.doppelganger_copied_role: Optional[Role] = None
        self.is_blessed = False
        self.is_doused = False
        self.accelerant_used = False
        self.accelerant_boost_next_night = False
        self.douse_count_tonight = 0
        self.max_douses_tonight = 1
        self.is_plagued = False
        self.night_visits: List[int] = []
        self.grave_robber_can_act = True
        self.grave_robber_borrowed_role = None
        self.grave_robber_can_borrow_tonight = True
        self.grave_robber_act_tonight = False
        self.afk_count = 0
        self.warned_afk = False
        self.webkeeper_marked_target = None        
        # Stray attributes
        self.stray_observed_target = None        
        # Mirror Phantom attributes
        self.mirror_ability_used = False
        self.mirror_stolen_role = None
        self.mirror_win_condition = None        
        # Thief attributes
        self.thief_ability_used = False
        self.thief_stolen_role = None
        self.thief_objective_complete = False
        
        logger.debug(f"Created player: {first_name} ({user_id})")

    @property
    def mention(self) -> str:
        return f"[{self.first_name}](tg://user?id={self.user_id})"

    @property
    def display_name(self) -> str:
        return f"{self.role.emoji} {self.mention}" if self.role else self.mention

class Game:
    """Represents a Werewolf game instance"""
    
    def __init__(self, group_id: int, group_name: str):
        self.group_id = group_id
        self.custom_game = False
        self.group_name = group_name
        self.players: Dict[int, Player] = {}
        self.phase = GamePhase.LOBBY
        self.day_number = 0
        self.votes: Dict[int, int] = {}
        self.lobby_message_id: Optional[int] = None    
        self.night_actions: Dict[str, Dict] = {}
        self.evil_team_type: Team = Team.WOLF
        self.start_time: Optional[datetime] = None
        self.game_start_time: Optional[datetime] = None
        self.phase_end_time: Optional[datetime] = None

        self.settings = {
            'night_time': 60,
            'day_time': 45,
            'voting_time': 60,
            'difficulty': 'normal',
            'afk_kick': True,
            'afk_threshold': 3,
        }
        
        # Game state tracking
        self.dead_players: List[Player] = []
        self.twins_ids: List[int] = []
        self.lovers_ids: List[int] = []
        self.seer_dead = False
        self.arsonist_ignited = False
        
        # ✅ NEW: Phase transition safety
        self._phase_lock = asyncio.Lock()
        self._phase_transitioning = False
        self._expected_phase_for_buttons: Dict[int, GamePhase] = {}  # message_id -> phase
        
        logger.info(f"Created new game in group {group_id} ({group_name})")

    def add_player(self, user: User) -> bool:
        """Add a player to the game"""
        if len(self.players) >= MAX_PLAYERS:
            logger.warning(f"Cannot add player {user.first_name}: game full ({len(self.players)}/{MAX_PLAYERS})")
            return False
            
        if user.id not in self.players:
            player = Player(user.id, user.username or "", user.first_name)
            self.players[user.id] = player
            logger.info(f"Player {player.first_name} ({user.id}) joined game in group {self.group_id}")
            return True
        
        logger.debug(f"Player {user.first_name} already in game")
        return False

    def remove_player(self, user_id: int) -> bool:
        """Remove a player from the game"""
        if user_id in self.players and self.phase == GamePhase.LOBBY:
            player = self.players.pop(user_id)
            logger.info(f"Player {player.first_name} ({user_id}) left game in group {self.group_id}")
            return True
        
        logger.warning(f"Cannot remove player {user_id}: not found or game in progress")
        return False

    def can_start(self) -> bool:
        """Check if game can start"""
        can_start = len(self.players) >= MIN_PLAYERS
        logger.debug(f"Game can start: {can_start} ({len(self.players)}/{MIN_PLAYERS})")
        return can_start

    def get_alive_players(self) -> List[Player]:
        """Get all alive players"""
        alive = [p for p in self.players.values() if p.is_alive]
        logger.debug(f"Alive players: {len(alive)}")
        return alive

    def get_players_by_team(self, team: Team) -> List[Player]:
        """Get all alive players from specific team"""
        team_players = [p for p in self.get_alive_players() if p.role and p.role.team == team]
        logger.debug(f"Team {team.value} players: {len(team_players)}")
        return team_players
    
    async def begin_phase_transition(self) -> bool:
        """
        Acquire phase transition lock. Returns True if acquired, False if already transitioning.
        Must be called before any phase transition.
        """
        if self._phase_transitioning:
            logger.warning(f"Phase transition already in progress for game {self.group_id}")
            return False
        
        await self._phase_lock.acquire()
        self._phase_transitioning = True
        logger.debug(f"Phase transition lock acquired for game {self.group_id}")
        return True
    
    def end_phase_transition(self):
        """Release phase transition lock after transition is complete"""
        if self._phase_lock.locked():
            self._phase_lock.release()
        self._phase_transitioning = False
        logger.debug(f"Phase transition lock released for game {self.group_id}")
    
    def is_transitioning(self) -> bool:
        """Check if game is currently transitioning between phases"""
        return self._phase_transitioning
    
    def register_button_phase(self, message_id: int, expected_phase: GamePhase):
        """Register expected phase for button message to validate stale clicks"""
        self._expected_phase_for_buttons[message_id] = expected_phase
        logger.debug(f"Registered button message {message_id} for phase {expected_phase.value}")
    
    def validate_button_phase(self, message_id: int) -> bool:
        """Validate that button click is for current phase (not stale)"""
        expected = self._expected_phase_for_buttons.get(message_id)
        if expected is None:
            # No registration means it's an old button or invalid
            logger.warning(f"Button message {message_id} not registered")
            return False
        
        if expected != self.phase:
            logger.warning(f"Stale button click: expected {expected.value}, current {self.phase.value}")
            return False
        
        return True
    
    def cleanup_old_button_registrations(self):
        """Remove button registrations that are no longer relevant"""
        # Keep only registrations for current phase
        to_remove = [msg_id for msg_id, phase in self._expected_phase_for_buttons.items() 
                     if phase != self.phase]
        for msg_id in to_remove:
            del self._expected_phase_for_buttons[msg_id]
        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} old button registrations")

    def check_win_condition(self) -> Optional[Team]:
        if hasattr(self, 'waiting_for_hunter') and self.waiting_for_hunter:
            logger.info("Skipping win condition check - waiting for Hunter revenge")
            return None
        alive_players = self.get_alive_players()
    
        if not alive_players:
            return Team.VILLAGER
    
        villager_count = 0
        wolf_count = 0
        fire_count = 0
        serial_killer_count = 0
        neutral_count = 0
    
        for player in alive_players:
            if not player.role:
                continue
           
            try:
                team = player.role.team
                if isinstance(team, str):
                    team = Team[team.upper()]
            except (AttributeError, KeyError):
                logger.error(f"Invalid team for player {player.first_name}: {player.role}")
        
            if player.role.team == Team.VILLAGER:
                villager_count += 1
            elif player.role.team == Team.WOLF:
                wolf_count += 1
            elif player.role.team == Team.FIRE:
                fire_count += 1
            elif player.role.team == Team.KILLER:
                serial_killer_count += 1
            elif player.role.team == Team.NEUTRAL:
                neutral_count += 1
    
        if serial_killer_count > 0 and villager_count == 0 and wolf_count == 0 and fire_count == 0:
            return Team.KILLER
    
        for player in alive_players:
            if player.role == Role.JESTER and getattr(player, 'achieved_objective', False):
                return Team.NEUTRAL
        
            if player.role == Role.EXECUTIONER and getattr(player, 'achieved_objective', False):
                return Team.NEUTRAL
    
        evil_count = wolf_count + fire_count + serial_killer_count
        if villager_count > 0 and evil_count == 0:
            return Team.VILLAGER
    
        non_wolf_count = villager_count + fire_count + neutral_count
        if wolf_count > 0 and wolf_count >= non_wolf_count:
            return Team.WOLF
    
        non_fire_count = villager_count + wolf_count + serial_killer_count + neutral_count
        if fire_count > 0 and fire_count >= non_fire_count:
            return Team.FIRE
    
        return None

# Global game storage
active_games: Dict[int, Game] = {}

logger.info("Game module loaded successfully")
