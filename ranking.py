import logging
import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from enums import Team, Role
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

def escape_markdown(text: str) -> str:
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

class Tier(Enum):
    PEASANT = "Peasant"
    APPRENTICE = "Apprentice"
    VILLAGER = "Villager"
    GUARDIAN = "Guardian"
    SEEKER = "Seeker"
    ELDER = "Elder"
    SHADOW_WALKER = "Shadow Walker"
    ANCIENT = "Ancient"


@dataclass
class GameResult:
    user_id: int
    username: str
    first_name: str
    won: bool
    team: str
    role: str
    is_alive: bool
    actions: Dict[str, int] = None
    penalties: Dict[str, bool] = None

class RankingManager:
    def migrate_database(self):
        """Migrate database to latest schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if points_earned column exists in game_history
            cursor.execute("PRAGMA table_info(game_history)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'points_earned' not in columns:
                logger.info("Adding points_earned column to game_history table")
                cursor.execute('ALTER TABLE game_history ADD COLUMN points_earned INTEGER DEFAULT 0')
            
            if 'was_mvp' not in columns:
                logger.info("Adding was_mvp column to game_history table")
                cursor.execute('ALTER TABLE game_history ADD COLUMN was_mvp BOOLEAN DEFAULT FALSE')
            
            if 'actions_performed' not in columns:
                logger.info("Adding actions_performed column to game_history table")
                cursor.execute('ALTER TABLE game_history ADD COLUMN actions_performed TEXT DEFAULT "{}"')
            
            # Check player_stats table columns
            cursor.execute("PRAGMA table_info(player_stats)")
            player_columns = [column[1] for column in cursor.fetchall()]
            
            missing_player_columns = [
                ('mvp_awards', 'INTEGER DEFAULT 0'),
                ('investigations_correct', 'INTEGER DEFAULT 0'),
                ('investigations_wrong', 'INTEGER DEFAULT 0'),
                ('protections_successful', 'INTEGER DEFAULT 0'),
                ('protections_wasted', 'INTEGER DEFAULT 0'),
                ('evil_eliminated', 'INTEGER DEFAULT 0'),
                ('village_mislynched', 'INTEGER DEFAULT 0'),
                ('early_deaths', 'INTEGER DEFAULT 0'),
                ('total_penalties', 'INTEGER DEFAULT 0'),
                ('favorite_role', 'TEXT DEFAULT "Villager"'),
                ('role_stats', 'TEXT DEFAULT "{}"'),
                ('highest_game', 'INTEGER DEFAULT 0'),
                ('lowest_ever', 'INTEGER DEFAULT 0'),
                ('points_lost_penalties', 'INTEGER DEFAULT 0'),
                ('tier_changes', 'INTEGER DEFAULT 0')
            ]
            
            for col_name, col_def in missing_player_columns:
                if col_name not in player_columns:
                    logger.info(f"Adding {col_name} column to player_stats table")
                    cursor.execute(f'ALTER TABLE player_stats ADD COLUMN {col_name} {col_def}')
            
            conn.commit()
            
            # Update existing players with 0 points to start with 100 points
            cursor.execute('''
                UPDATE player_stats 
                SET total_points = 100, current_tier = 'Villager' 
                WHERE total_points = 0
            ''')
            affected_rows = cursor.rowcount
            if affected_rows > 0:
                logger.info(f"Updated {affected_rows} existing players to start with 100 points")
            
            conn.commit()
            logger.info("Database migration completed successfully")

    def init_database(self):
        """Initialize SQLite database with migration support"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS player_stats (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    total_points INTEGER DEFAULT 100,
                    current_tier TEXT DEFAULT 'Villager',
                    games_played INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    current_streak INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0,
                    worst_streak INTEGER DEFAULT 0,
                    mvp_awards INTEGER DEFAULT 0,
                    
                    -- Performance tracking
                    investigations_correct INTEGER DEFAULT 0,
                    investigations_wrong INTEGER DEFAULT 0,
                    protections_successful INTEGER DEFAULT 0,
                    protections_wasted INTEGER DEFAULT 0,
                    evil_eliminated INTEGER DEFAULT 0,
                    village_mislynched INTEGER DEFAULT 0,
                    early_deaths INTEGER DEFAULT 0,
                    total_penalties INTEGER DEFAULT 0,
                    
                    -- Role statistics
                    favorite_role TEXT DEFAULT 'Villager',
                    role_stats TEXT DEFAULT '{}',
                    
                    -- Meta data
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_game TIMESTAMP,
                    highest_game INTEGER DEFAULT 0,
                    lowest_ever INTEGER DEFAULT 0,
                    points_lost_penalties INTEGER DEFAULT 0,
                    tier_changes INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT,
                    user_id INTEGER,
                    game_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    role TEXT,
                    team TEXT,
                    won BOOLEAN,
                    points_earned INTEGER DEFAULT 0,
                    was_mvp BOOLEAN DEFAULT FALSE,
                    actions_performed TEXT DEFAULT '{}',
                    FOREIGN KEY (user_id) REFERENCES player_stats (user_id)
                )
            ''')
            
            conn.commit()
            logger.info("Database tables created successfully")
            
            # Run migration to add any missing columns
            self.migrate_database()

    def __init__(self, db_path: str = "werewolf_rankings.db"):
        self.db_path = db_path
        self.init_database()
        
        # Tier system with lower point values for gradual progression
        self.TIER_SYSTEM = {
            Tier.PEASANT: {"range": (0, 49), "emoji": "🟤", "multiplier": 2.0, "penalty_reduction": 0.5},
            Tier.APPRENTICE: {"range": (50, 99), "emoji": "🟫", "multiplier": 1.8, "penalty_reduction": 0.6},
            Tier.VILLAGER: {"range": (100, 199), "emoji": "⚪", "multiplier": 1.5, "penalty_reduction": 0.7},
            Tier.GUARDIAN: {"range": (200, 349), "emoji": "🟢", "multiplier": 1.3, "penalty_reduction": 0.8},
            Tier.SEEKER: {"range": (350, 549), "emoji": "🔵", "multiplier": 1.1, "penalty_reduction": 0.9},
            Tier.ELDER: {"range": (550, 799), "emoji": "🟣", "multiplier": 1.0, "penalty_reduction": 1.0},
            Tier.SHADOW_WALKER: {"range": (800, 1199), "emoji": "🟠", "multiplier": 0.8, "penalty_reduction": 1.2},
            Tier.ANCIENT: {"range": (1200, float('inf')), "emoji": "🔴", "multiplier": 0.6, "penalty_reduction": 1.5}
        }
        
        # Lower victory points for gradual progression
        self.VICTORY_POINTS = {
            "village_victory": 3,
            "wolf_solo_victory": 6,
            "wolf_team_victory": {"2": 5, "3": 4, "4+": 3},
            "fire_solo_victory": 6,
            "fire_team_victory": {"2": 5, "3": 4, "4+": 3},
            "serial_killer_victory": 8,
            "neutral_victory": 5
        }
        
        # Reduced penalties for less harsh punishment
        self.LOSS_PENALTIES = {
            "villager_loss": -2,
            "wolf_loss": -2,
            "fire_loss": -2,
            "neutral_loss": -3,
            "early_elimination": -1,
            "serial_killer_loss": -2,
            "major_mistake": -2
        }
        
        # Lower action points for gradual accumulation
        self.ACTION_POINTS = {
            # Positive Actions (1-2 points)
            "investigate_evil": 2,
            "successful_protection": 2,
            "lynch_evil": 1,
            "eliminate_investigative": 2,
            "hunter_revenge_evil": 2,
            "witch_save": 2,
            "witch_poison_evil": 2,
            "good_vote": 1,
            "survival_bonus": 1,
            
            # Negative Actions (lower penalties)
            "investigate_wrong": -1,
            "mislynch_village": -1,
            "vote_revealed_mayor": -2,
            "vigilante_kill_village": -3,
            "wasted_protection": -1,
            "helped_enemy_team": -1
        }
        
        # Lower role bonuses (5-15 points instead of 20-30)
        self.ROLE_BONUSES = {
            # Basic Roles (5 points)
            Role.VILLAGER: 5, Role.CURSED_VILLAGER: 5, Role.FOOL: 5,
            Role.TWINS: 6, Role.WEREWOLF: 6,
            
            # Investigative Roles (7-9 points)
            Role.SEER: 7, Role.ORACLE: 8, Role.DETECTIVE: 9,
            Role.SERIAL_KILLER: 18,
            Role.APPRENTICE_SEER: 6, Role.INSOMNIAC: 6,
            
            # Protective Roles (7-8 points)
            Role.DOCTOR: 7, Role.BODYGUARD: 8, Role.PRIEST: 7,
            
            # Power Roles (9-12 points)
            Role.HUNTER: 9, Role.WITCH: 12, Role.VIGILANTE: 10,
            Role.MAYOR: 8, Role.GRAVE_ROBBER: 12, Role.PLAGUE_DOCTOR: 12,
            
            # Evil Roles
            Role.ALPHA_WOLF: 10, Role.WOLF_SHAMAN: 8,
            Role.ARSONIST: 12, Role.BLAZEBRINGER: 8, Role.ACCELERANT_EXPERT: 7,
            
            # Neutral Roles (15 points - hardest to win)
            Role.JESTER: 15, Role.EXECUTIONER: 15, Role.CUPID: 15, Role.DOPPELGANGER: 15,  
        Role.WEBKEEPER: 18,      # Must protect SK
        
        # Cursed neutrals (can never win)
        Role.MIRROR_PHANTOM: 0,  # Cannot win
        Role.THIEF: 0,           # Cannot win
        
        # New villager role
        Role.STRAY: 7,  
        }

    def get_player_tier(self, points: int) -> Tier:
        """Get player tier based on points"""
        for tier, data in self.TIER_SYSTEM.items():
            min_pts, max_pts = data["range"]
            if min_pts <= points <= max_pts:
                return tier
        return Tier.ANCIENT

    def get_tier_info(self, tier: Tier) -> Dict:
        """Get tier information"""
        return self.TIER_SYSTEM[tier]

    def calculate_game_points(self, result: GameResult, current_points: int = 0) -> int:
        tier = self.get_player_tier(current_points)
        tier_info = self.get_tier_info(tier)
        multiplier = tier_info["multiplier"]
        penalty_reduction = tier_info["penalty_reduction"]
    
        base_points = 0
    
    # Convert team to string if it's an enum
        team_str = result.team
        if hasattr(result.team, 'value'):
            team_str = result.team.value
        elif hasattr(result.team, 'name'):
            team_str = result.team.name
        else:
            team_str = str(result.team)
    
    # Convert role to enum if it's a string
        role_enum = result.role
        if isinstance(result.role, str):
            try:
        # Try by name first (WEREWOLF)
                if hasattr(Role, result.role):
                    role_enum = getattr(Role, result.role)
        # Try by value (Werewolf)
                else:
                    role_enum = Role(result.role)
            except (ValueError, AttributeError):
                role_enum = None
    
    # Victory/Loss points
        if result.won:
        # Base victory points
            if team_str == "VILLAGER":
                base_points += self.VICTORY_POINTS["village_victory"]
            elif team_str == "WOLF":
                base_points += self.VICTORY_POINTS["wolf_solo_victory"]  # Simplified
            elif team_str == "FIRE":
                base_points += self.VICTORY_POINTS["fire_solo_victory"]  # Simplified
            elif team_str == "SERIAL_KILLER":  # NEW
                base_points += self.VICTORY_POINTS["serial_killer_victory"]
            elif team_str == "NEUTRAL":
                base_points += self.VICTORY_POINTS["neutral_victory"]
        
        # Add role bonus if we successfully converted to enum
            if role_enum and isinstance(role_enum, Role):
                role_bonus = self.ROLE_BONUSES.get(role_enum, 0)
                base_points += role_bonus
        else:
        # Loss penalty - use team_str instead of result.team.value
            loss_penalty = self.LOSS_PENALTIES.get(f"{team_str.lower()}_loss", -5)
            base_points += int(loss_penalty * penalty_reduction)
    
    # Action bonuses/penalties
        if result.actions:
            VALID_ACTIONS = {
                'investigate_evil', 'investigate_wrong', 'successful_protection',
                'wasted_protection', 'lynch_evil', 'mislynch_village', 'witch_save',
                'witch_poison_evil', 'hunter_revenge_evil', 'survival_bonus',
                'vigilante_kill_village', 'major_mistake', 'early_death'
}
            for action, count in result.actions.items():
                if action not in VALID_ACTIONS:
                    logger.warning(f"Unknown action '{action}' for user {result.user_id}")
                    continue
    
                action_points = self.ACTION_POINTS.get(action, 0)
                if action_points < 0:
                    base_points += int(action_points * count * penalty_reduction)
                else:
                    base_points += action_points * count
    
    # Survival bonus
        if result.is_alive:
            base_points += 1
        elif not result.won:
        # Early death penalty for losers
            base_points += int(-1 * penalty_reduction)
    
    # Apply multiplier
        final_points = int(base_points * multiplier)
    
    # Minimum -5 points per game
        return max(-5, final_points)

    def update_player_stats(self, result: GameResult):
        """Update player statistics after a game"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
        
        # Get or create player
            cursor.execute('SELECT * FROM player_stats WHERE user_id = ?', (result.user_id,))
            player = cursor.fetchone()
         
            if not player:
            # Create new player
                cursor.execute('''
                    INSERT INTO player_stats (user_id, username, first_name)
                    VALUES (?, ?, ?)
                ''', (result.user_id, result.username, result.first_name))
            
                cursor.execute('SELECT * FROM player_stats WHERE user_id = ?', (result.user_id,))
                player = cursor.fetchone()
        
        # Convert to dict for easier access
            columns = [desc[0] for desc in cursor.description]
            player_dict = dict(zip(columns, player))
        
        # Calculate points earned
            points_earned = self.calculate_game_points(result, player_dict['total_points'])
            new_total = player_dict['total_points'] + points_earned
        
        # Update streak
            if result.won:
                new_streak = max(0, player_dict['current_streak']) + 1
                new_wins = player_dict['wins'] + 1
                new_losses = player_dict['losses']
            else:
                new_streak = min(0, player_dict['current_streak']) - 1
                new_wins = player_dict['wins']
                new_losses = player_dict['losses'] + 1
        
        # Update tier
            new_tier = self.get_player_tier(new_total)
            tier_changed = new_tier.value != player_dict['current_tier']
        
        # Role statistics - handle both string and enum roles
            role_stats = json.loads(player_dict.get('role_stats', '{}'))
        
        # Convert role to string for storage
            if hasattr(result.role, 'value'):
                role_key = result.role.value
            elif hasattr(result.role, 'name'):
                role_key = result.role.name
            else:
                role_key = str(result.role)
        
            if role_key not in role_stats:
                role_stats[role_key] = {"games": 0, "wins": 0}
            role_stats[role_key]["games"] += 1
            if result.won:
                role_stats[role_key]["wins"] += 1
        
        # Convert team and role to strings for database storage
            team_str = result.team
            if hasattr(result.team, 'value'):
                team_str = result.team.value
            elif hasattr(result.team, 'name'):
                team_str = result.team.name
            else:
                team_str = str(result.team)
        
            role_str = result.role
            if hasattr(result.role, 'value'):
                role_str = result.role.value
            elif hasattr(result.role, 'name'):
                role_str = result.role.name
            else:
                role_str = str(result.role)
        
        # Update database
            cursor.execute('''
                UPDATE player_stats SET
                    username = ?, first_name = ?, total_points = ?, current_tier = ?,
                    games_played = games_played + 1, wins = ?, losses = ?,
                    current_streak = ?, best_streak = CASE WHEN ? > best_streak THEN ? ELSE best_streak END,
                    worst_streak = CASE WHEN ? < worst_streak THEN ? ELSE worst_streak END,
                    last_game = ?, highest_game = CASE WHEN ? > highest_game THEN ? ELSE highest_game END,
                    lowest_ever = CASE WHEN ? < lowest_ever THEN ? ELSE lowest_ever END,
                    role_stats = ?,
                    tier_changes = CASE WHEN ? THEN tier_changes + 1 ELSE tier_changes END
                WHERE user_id = ?
            ''', (
                result.username, result.first_name, new_total, new_tier.value,
                new_wins, new_losses, new_streak, new_streak, new_streak,
                new_streak, new_streak, datetime.now().isoformat(),
                points_earned, points_earned, new_total, new_total,
                json.dumps(role_stats), tier_changed, result.user_id
            ))
        
        # Record game history - use string versions
            cursor.execute('''
                INSERT INTO game_history (game_id, user_id, role, team, won, points_earned, actions_performed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                f"game_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                result.user_id, role_str, team_str,
                result.won, points_earned, json.dumps(result.actions or {})
            ))
        
            conn.commit()
        
            logger.info(f"Updated stats for {result.first_name}: {points_earned:+d} points, tier: {new_tier.value}")
            return points_earned, new_tier, tier_changed


    def get_player_stats(self, user_id: int) -> Optional[Dict]:
        """Get player statistics"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM player_stats WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_leaderboard(self, limit: int = 20) -> List[Dict]:
        """Get leaderboard"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, first_name, total_points, current_tier, 
                       games_played, wins, current_streak, mvp_awards
                FROM player_stats 
                WHERE games_played > 0
                ORDER BY total_points DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def format_stats_message(self, user_id: int, username: str) -> str:
        """Format player stats message"""
        stats = self.get_player_stats(user_id)
        if not stats:
            return f"No statistics found for {username}. Play some games first!"
    
        tier = Tier(stats['current_tier'])
        tier_info = self.get_tier_info(tier)
    
    # Calculate next tier progress
        next_tier = None
        points_needed = 0
        tier_list = list(self.TIER_SYSTEM.keys())
        try:
            current_idx = tier_list.index(tier)
            if current_idx < len(tier_list) - 1:
                next_tier = tier_list[current_idx + 1]
                next_range = self.TIER_SYSTEM[next_tier]["range"]
                points_needed = next_range[0] - stats['total_points']
        except (ValueError, IndexError):
            pass
    
    # Win rate
        win_rate = (stats['wins'] / max(stats['games_played'], 1)) * 100
    
    # Streak formatting
        streak = stats['current_streak']
        if streak > 0:
            streak_text = f"🔥 {streak} wins"
        elif streak < 0:
            streak_text = f"💀 {abs(streak)} losses"
        else:
            streak_text = "None"
    
    # Role statistics
        role_stats = json.loads(stats.get('role_stats', '{}'))
        favorite_role = "Villager"
        best_winrate = 0
    
        for role_name, data in role_stats.items():
            if data['games'] >= 2:
                winrate = (data['wins'] / data['games']) * 100
                if winrate > best_winrate:
                    best_winrate = winrate
                    favorite_role = role_name
    
    # Build message WITHOUT special markdown formatting
        message = f"🌙 {stats['first_name']}'s Village Chronicle 🌙\n\n"
        message += f"Rank: {tier_info['emoji']} {tier.value} ({stats['total_points']} ⭐)\n"
        message += f"Multiplier: {tier_info['multiplier']}x • Penalty Reduction: {tier_info['penalty_reduction']}x\n"

        if next_tier and points_needed > 0:
            progress = max(0, 20 - int((points_needed / 50) * 20))
            progress_bar = "█" * progress + "░" * (20 - progress)
            message += f"\n📈 Progress to {next_tier.value}\n"
            message += f"{progress_bar} ({points_needed} points needed)\n"
        message += f"\n⚔️ Battle Record ({stats['games_played']} games)\n"
        message += f"├ Win Rate: {win_rate:.1f}% ({stats['wins']}W-{stats['losses']}L)\n"
        message += f"├ Current Streak: {streak_text}\n"
        message += f"├ Best Streak: {stats['best_streak']} 🔥\n"
        message += f"└ MVP Awards: {stats['mvp_awards']} 🏆\n"
    
        message += f"\n🎯 Performance Statistics\n"
        message += f"├ Evil Eliminated: {stats['evil_eliminated']}\n"
        message += f"├ Investigations: {stats['investigations_correct']}✓ {stats['investigations_wrong']}✗\n"
        message += f"├ Protections: {stats['protections_successful']}✓ {stats['protections_wasted']}✗\n"
        message += f"└ Early Deaths: {stats['early_deaths']}\n"
    
        message += f"\n💎 Career Highlights\n"
        message += f"├ Best Role: {favorite_role} ({best_winrate:.0f}% wins)\n"
        message += f"├ Highest Game: {stats['highest_game']} points\n"
        message += f"├ Lowest Ever: {stats['lowest_ever']}\n"
        message += f"└ Tier Changes: {stats['tier_changes']}\n"
    
        last_game = stats['last_game'][:10] if stats['last_game'] else 'Never'
        message += f"\n\"Last battle: {last_game}\""

        return message

    def format_leaderboard_message(self) -> str:
        """Format leaderboard message"""
        leaderboard = self.get_leaderboard(15)
        
        if not leaderboard:
            return "No players have completed games yet. Be the first!"
        
        message = "🏆 **Village Hall of Fame** 🏆\n\n"
        
        # Top players by tier
        ancients = [p for p in leaderboard if p['current_tier'] == 'Ancient'][:3]
        shadows = [p for p in leaderboard if p['current_tier'] == 'Shadow Walker'][:3]
        
        if ancients:
            message += "**🔴 Ancient Legends**\n"
            for i, player in enumerate(ancients, 1):
                streak = f" 🔥{player['current_streak']}" if player['current_streak'] > 0 else ""
                message += f"{i}. {player['first_name']} - {player['total_points']} pts{streak}\n"
            message += "\n"
        
        if shadows:
            message += "**🟠 Shadow Walkers**\n"
            for i, player in enumerate(shadows, 1):
                streak = f" 🔥{player['current_streak']}" if player['current_streak'] > 0 else ""
                message += f"{i}. {player['first_name']} - {player['total_points']} pts{streak}\n"
            message += "\n"
        
        # Overall top 10
        message += "**📊 Top Players**\n"
        for i, player in enumerate(leaderboard[:10], 1):
            tier_emoji = self.TIER_SYSTEM[Tier(player['current_tier'])]["emoji"]
            win_rate = (player['wins'] / max(player['games_played'], 1)) * 100
            message += f"{i}. {tier_emoji} {player['first_name']} - {player['total_points']} pts ({win_rate:.0f}% WR)\n"
        
        # Tier distribution
        tier_counts = {}
        for player in leaderboard:
            tier = player['current_tier']
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        
        message += f"\n**🏅 Active Players:** {len(leaderboard)}\n"
        message += f"**📈 Tier Multipliers:** Peasant 2.0x • Ancient 0.6x"
        
        return message

    def format_rank_info_message(self) -> str:
        """Format rank info message"""
        return """⚔️ **The Village Ranking System** ⚔️

**🎯 Point Values (Reduced Scale):**
• **Victory:** Village 3pts • Evil Solo 6pts • Team 3-5pts
• **Role Mastery:** 5-15pts (victory only)
• **Actions:** Investigation +2pts • Protection +2pts • Lynch Evil +1pts
• **Penalties:** Major Mistake -2pts • Team Loss -2pts

**🏅 Eight Tiers (Lower Thresholds):**
🟤 **Peasant** (0-49) • **2.0x points** • **50% less penalties**
🟫 **Apprentice** (50-99) • **1.8x points** • **40% less penalties**
⚪ **Villager** (100-199) • **1.5x points** • **30% less penalties**
🟢 **Guardian** (200-349) • **1.3x points** • **20% less penalties**
🔵 **Seeker** (350-549) • **1.1x points** • **10% less penalties**
🟣 **Elder** (550-799) • **1.0x points** • **Standard penalties**
🟠 **Shadow Walker** (800-1199) • **0.8x points** • **20% more penalties**
🔴 **Ancient** (1200+) • **0.6x points** • **50% more penalties**

**🔥 Key Features:**
• Gradual progression with lower point values
• Beginner protection with bonus multipliers
• Skill-based advancement for experienced players
• Every action matters but recovery is always possible
• Medieval werewolf atmosphere throughout

*"From humble peasant to ancient legend, every villager's tale is written in blood and moonlight..."*"""

# Global instance
ranking_manager = RankingManager()

# Command handlers for integration with your bot
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user = update.effective_user
    
    try:
        message = ranking_manager.format_stats_message(user.id, user.first_name or user.username or "Unknown")
        # REMOVE parse_mode completely - send as plain text with emojis
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await update.message.reply_text("An error occurred retrieving your statistics.")

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /leaderboard command"""
    try:
        message = ranking_manager.format_leaderboard_message()
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in leaderboard command: {e}")
        await update.message.reply_text("An error occurred loading the leaderboard.")

async def rank_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rank_info command"""
    try:
        message = ranking_manager.format_rank_info_message()
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in rank info command: {e}")
        await update.message.reply_text("An error occurred loading ranking information.")

def record_batch_game_results(game_id: str, total_players: int, results: List[Dict]) -> List[Dict]:
    """Process game results for ranking system"""
    processed_results = []
    player_breakdowns = {}
    
    for result_data in results:
        # Safely convert team and role
        team = result_data['team']
        if hasattr(team, 'value'):
            team = team.value
        elif hasattr(team, 'name'):
            team = team.name
        else:
            team = str(team)
        
        role = result_data['role']
        if hasattr(role, 'value'):
            role = role.value
        elif hasattr(role, 'name'):
            role = role.name
        else:
            role = str(role)
        logger.info(f"DEBUG record_batch - Converted role: {role}, type: {type(role)}")

        is_alive = result_data.get('is_alive', False)
        
        # Convert to GameResult object
        result = GameResult(
            user_id=result_data['user_id'],
            username=result_data.get('username', ''),
            first_name=result_data.get('first_name', 'Unknown'),
            won=result_data['won'],
            team=team,  # Now guaranteed to be a string
            role=role,  # Now guaranteed to be a string
            is_alive=result_data['is_alive'],
            actions=result_data.get('actions', {}),
            penalties=result_data.get('penalties', {})
        )
        
        # Update player stats and get results
        points_earned, new_tier, tier_changed = ranking_manager.update_player_stats(result)
        
        processed_results.append({
            'user_id': result.user_id,
            'first_name': result.first_name,
            'points_earned': points_earned,
            'new_tier': new_tier.value,
            'tier_changed': tier_changed,
            'won': result.won,
            'role': role,
            'team': team,
            'is_alive': is_alive
        })
    
    mvp_user_id = calculate_and_award_mvp(processed_results)
    
    # Mark MVP in processed results
    for result in processed_results:
        result['is_mvp'] = (result['user_id'] == mvp_user_id)
        if result['is_mvp']:
            result['points_earned'] += 10  # Reflect MVP bonus in display

        game_result = GameResult(
            user_id=result['user_id'],
            username='',
            first_name=result['first_name'],
            won=result['won'],
            team=result['team'],
            role=result['role'],
            is_alive=result['is_alive'],
            actions=result.get('actions', {})
        )
        
        tier = Tier(result['new_tier'])
        breakdown_msg = generate_player_performance_breakdown(
            game_result,
            result['points_earned'],
            tier,
            result['tier_changed'],
            result['is_mvp']
        )
        result['breakdown_message'] = breakdown_msg
    
    
    logger.info(f"Processed {len(processed_results)} player results for game {game_id}")
    if mvp_user_id:
        mvp_name = next((r['first_name'] for r in processed_results if r['user_id'] == mvp_user_id), 'Unknown')
        logger.info(f"MVP: {mvp_name} (user_id: {mvp_user_id})")
    
    return processed_results



def generate_final_reveal_message(winner: Team, results: List[Dict], game_length: str) -> str:
    """Generate final game reveal message with ranking results"""

    # FIX: Handle different winner types
    if isinstance(winner, tuple):
        winner = winner[0]

    if hasattr(winner, 'name'):
        winning_team_name = winner.name.upper()
    elif hasattr(winner, 'value'):
        # Map value to name
        value_to_name = {
            "Villager": "VILLAGER",
            "Wolf": "WOLF",
            "Fire": "FIRE",
            "Killer": "KILLER",
            "Neutral": "NEUTRAL"
        }
        winning_team_name = value_to_name.get(str(winner.value), "NEUTRAL")
    elif isinstance(winner, str):
        winning_team_name = winner.upper()
    else:
        winning_team_name = str(winner).upper()
    
    # Separate winners and losers
    winners = [r for r in results if r['won']]
    losers = [r for r in results if not r['won']]
    
    # Sort by points earned (highest first)
    winners.sort(key=lambda x: -x['points_earned'])
    losers.sort(key=lambda x: -x['points_earned'])
    
    # Winner descriptions using UPPERCASE string keys
    winner_headers = {
        "VILLAGER": "👑 **VICTORIOUS HEROES** 👑\n*The light has triumphed over darkness*",
        "WOLF": "🐺 **THE PACK REIGNS** 🐺\n*The village falls to the howling shadows*",
        "FIRE": "🔥 **INFERNO UNLEASHED** 🔥\n*Ashes and embers are all that remain*",
        "KILLER": "🔪 **THE PREDATOR STANDS ALONE** 🔪\n*All others have fallen*",
        "NEUTRAL": "🎭 **CHAOS VICTORIOUS** 🎭\n*The trickster's grand design fulfilled*"
    }
    
    loser_headers = {
        "VILLAGER": "💀 **THE FALLEN** 💀",
        "WOLF": "⚔️ **DEFEATED EVIL** ⚔️",
        "FIRE": "🌊 **FLAMES EXTINGUISHED** 🌊",
        "KILLER": "⚰️ **THE HUNTERS** ⚰️",
        "NEUTRAL": "⚰️ **THE FALLEN** ⚰️"
    }
    
    message = f"""🎭 **GAME CONCLUDED** 🎭

**⏱️ Duration:** {game_length}

{winner_headers.get(winning_team_name, "👑 **VICTORIOUS**")}
"""
    
    # Display winners
    for result in winners:
        role_display = _format_role_display(result['role'])
        tier_info = ranking_manager.get_tier_info(Tier(result['new_tier']))
        tier_emoji = tier_info['emoji']
        points_text = f"{result['points_earned']:+d}"
        tier_change = " 📈" if result['tier_changed'] else ""
        mvp_badge = " 🏆 **MVP**" if result.get('is_mvp', False) else ""  

        message += f"👑 {result['first_name']} {role_display} - {points_text} pts {tier_emoji}{tier_change}{mvp_badge}\n"
    
    # Separator and losers section
    if losers:
        message += f"\n{'─' * 40}\n"
        message += f"{loser_headers.get(winning_team_name, '💀 **THE FALLEN**')}\n"
        
        for result in losers:
            role_display = _format_role_display(result['role'])
            tier_info = ranking_manager.get_tier_info(Tier(result['new_tier']))
            tier_emoji = tier_info['emoji']
            points_text = f"{result['points_earned']:+d}"
            tier_change = " 📉" if result['tier_changed'] else ""
            
            message += f"💀 {result['first_name']} {role_display} - {points_text} pts {tier_emoji}{tier_change}\n"

    return message


def _format_role_display(role) -> str:
    """Helper to format role display consistently"""
    try:
        # Handle tuple input (rare fallback)
        if isinstance(role, tuple) and len(role) >= 2:
            emoji, name = role[0], role[1]
            return f"({emoji} {name})"

        # Handle string input
        elif isinstance(role, str):
            # Try to match enum by name (e.g., "FIRE_STARTER")
            if hasattr(Role, role):
                role_obj = getattr(Role, role)
                return f"({role_obj.emoji} {role_obj.role_name})"

            # Try to match by value (e.g., "Fire Starter")
            for r in Role:
                if r.value.lower() == role.lower() or r.name.lower() == role.lower():
                    return f"({r.emoji} {r.role_name})"

            # If not found, return as plain text
            return f"({role})"

        # Handle direct Role enum object
        elif isinstance(role, Role):
            return f"({role.emoji} {role.role_name})"

        # Handle Player object with role attribute
        elif hasattr(role, "role") and isinstance(role.role, Role):
            return f"({role.role.emoji} {role.role.role_name})"

        # Fallback for unknown or unsupported input
        return f"({str(role)})"

    except Exception as e:
        logger.error(f"Error formatting role display for {role}: {e}")
        return "(Unknown Role)"

def process_game_end_rankings(game_data: Dict) -> str:
    """Legacy function for compatibility - calls new system"""
    try:
        results = []
        for player_data in game_data.get('players', []):
            # Safe conversion of team and role to handle both enums and strings
            team = player_data.get('team', Team.VILLAGER)
            if hasattr(team, 'value'):
                team = team.value
            elif hasattr(team, 'name'):
                team = team.name
            else:
                team = str(team)
            
            role = player_data.get('role', Role.VILLAGER)
            if hasattr(role, 'value'):
                role = role.value
            elif hasattr(role, 'name'):
                role = role.name
            else:
                role = str(role)
            
            results.append({
                'user_id': player_data['user_id'],
                'username': player_data.get('username', ''),
                'first_name': player_data.get('first_name', 'Unknown'),
                'won': player_data.get('won', False),
                'team': team,  # Now guaranteed to be string
                'role': role,  # Now guaranteed to be string
                'is_alive': player_data.get('is_alive', False)
            })
        
        game_id = game_data.get('game_id', f"game_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        winner = game_data.get('winner', Team.VILLAGER)
        game_length = game_data.get('game_length', '0:00:00')
        
        processed_results = record_batch_game_results(game_id, len(results), results)
        return generate_final_reveal_message(winner, processed_results, game_length)
        
    except Exception as e:
        logger.error(f"Error processing game end rankings: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "Game ended! Rankings could not be processed at this time."

def track_player_action(user_id: int, action: str, success: bool = True):
    """Track individual player actions during gameplay for detailed analytics"""
    try:
        with sqlite3.connect(ranking_manager.db_path) as conn:
            cursor = conn.cursor()
            
            # Update action counters
            if action == "investigate" and success:
                cursor.execute('UPDATE player_stats SET investigations_correct = investigations_correct + 1 WHERE user_id = ?', (user_id,))
            elif action == "investigate" and not success:
                cursor.execute('UPDATE player_stats SET investigations_wrong = investigations_wrong + 1 WHERE user_id = ?', (user_id,))
            elif action == "protect" and success:
                cursor.execute('UPDATE player_stats SET protections_successful = protections_successful + 1 WHERE user_id = ?', (user_id,))
            elif action == "protect" and not success:
                cursor.execute('UPDATE player_stats SET protections_wasted = protections_wasted + 1 WHERE user_id = ?', (user_id,))
            elif action == "eliminate_evil":
                cursor.execute('UPDATE player_stats SET evil_eliminated = evil_eliminated + 1 WHERE user_id = ?', (user_id,))
            elif action == "mislynch_village":
                cursor.execute('UPDATE player_stats SET village_mislynched = village_mislynched + 1 WHERE user_id = ?', (user_id,))
            elif action == "early_death":
                cursor.execute('UPDATE player_stats SET early_deaths = early_deaths + 1 WHERE user_id = ?', (user_id,))
            
            conn.commit()
            logger.debug(f"Tracked action {action} for user {user_id}: {'success' if success else 'failure'}")
            
    except Exception as e:
        logger.error(f"Error tracking player action: {e}")

def get_player_quick_stats(user_id: int) -> Dict:
    """Get basic player stats for quick display"""
    stats = ranking_manager.get_player_stats(user_id)
    if not stats:
        return {"tier": "Peasant", "points": 0, "games": 0, "winrate": 0}
    
    tier = Tier(stats['current_tier'])
    tier_info = ranking_manager.get_tier_info(tier)
    winrate = (stats['wins'] / max(stats['games_played'], 1)) * 100
    
    return {
        "tier": tier.value,
        "tier_emoji": tier_info['emoji'],
        "points": stats['total_points'],
        "games": stats['games_played'],
        "wins": stats['wins'],
        "winrate": round(winrate, 1),
        "streak": stats['current_streak']
    }

def send_tier_notification(context: ContextTypes, user_id: int, old_tier: str, new_tier: str, points: int):
    """Send tier change notification to player"""
    try:
        new_tier_obj = Tier(new_tier)
        tier_info = ranking_manager.get_tier_info(new_tier_obj)
        
        if old_tier != new_tier:
            # Determine if promotion or demotion
            tier_list = list(ranking_manager.TIER_SYSTEM.keys())
            old_idx = tier_list.index(Tier(old_tier)) if old_tier in [t.value for t in tier_list] else 0
            new_idx = tier_list.index(new_tier_obj)
            
            if new_idx > old_idx:
                # Promotion
                message = f"""🎉 **Tier Advancement!** 🎉

You have ascended to **{tier_info['emoji']} {new_tier}**!
Current Points: **{points} ⭐**

**New Benefits:**
• Point Multiplier: **{tier_info['multiplier']}x**
• Penalty Reduction: **{tier_info['penalty_reduction']}x**

*The village recognizes your growing legend...*"""
            else:
                # Demotion
                message = f"""⬇️ **Tier Change** ⬇️

You have moved to **{tier_info['emoji']} {new_tier}**
Current Points: **{points} ⭐**

**Current Status:**
• Point Multiplier: **{tier_info['multiplier']}x**
• Penalty Reduction: **{tier_info['penalty_reduction']}x**

*Every legend faces setbacks. Rise again, brave soul.*"""
            
            # Send notification asynchronously
            import asyncio
            async def send_notification():
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to send tier notification to {user_id}: {e}")
            
            # Schedule the notification
            asyncio.create_task(send_notification())
            logger.info(f"Scheduled tier notification for user {user_id}: {old_tier} → {new_tier}")
    
    except Exception as e:
        logger.error(f"Error in tier notification: {e}")

def calculate_mvp_candidates(game_results: List[Dict]) -> List[int]:
    """Calculate MVP candidates based on performance"""
    mvp_scores = {}
    
    for result in game_results:
        score = 0
        user_id = result['user_id']
        
        # Base points for winning
        if result['won']:
            score += 3
        
        # Survival bonus
        if result['is_alive']:
            score += 2
        
        # Role difficulty bonus
        role_difficulties = {
            Role.JESTER: 5, Role.EXECUTIONER: 5, Role.DOPPELGANGER: 5,
            Role.WITCH: 4, Role.ARSONIST: 4, Role.PLAGUE_DOCTOR: 4,
            Role.ALPHA_WOLF: 3, Role.SEER: 3, Role.DETECTIVE: 3,
            Role.HUNTER: 2, Role.DOCTOR: 2, Role.VIGILANTE: 2
        }
        
        difficulty = role_difficulties.get(result['role'], 1)
        score += difficulty
        
        # Actions bonus
        actions = result.get('actions', {})
        score += actions.get('investigate_evil', 0) * 2
        score += actions.get('successful_protection', 0) * 2
        score += actions.get('lynch_evil', 0) * 1
        
        mvp_scores[user_id] = score
    
    # Return top 3 candidates
    sorted_candidates = sorted(mvp_scores.items(), key=lambda x: x[1], reverse=True)
    return [user_id for user_id, _ in sorted_candidates[:3]]

def generate_player_performance_breakdown(result: GameResult, points_earned: int, tier: Tier, tier_changed: bool, is_mvp: bool = False) -> str:
    """Generate detailed performance breakdown for individual player (plain text with emojis)"""
    
    tier_info = ranking_manager.get_tier_info(tier)
    
    # Header with result (NO MARKDOWN)
    if result.won:
        header = "🎉 VICTORY! 🎉\n"
        header += "Your team emerged victorious!\n"
    else:
        header = "💀 DEFEAT 💀\n"
        header += "Your team was eliminated...\n"
    
    # Role and team info
    role_str = result.role
    if hasattr(result.role, 'value'):
        role_str = result.role.value
    elif hasattr(result.role, 'name'):
        role_str = result.role.name
    
    team_str = result.team
    if hasattr(result.team, 'value'):
        team_str = result.team.value
    elif hasattr(result.team, 'name'):
        team_str = result.team.name
    
    message = header
    message += f"\n📜 Your Role: {role_str}"
    message += f"\n⚔️ Team: {team_str}"
    message += f"\n💓 Status: {'Survived' if result.is_alive else 'Died'}\n"
    
    # Points breakdown section
    message += f"\n{'─' * 40}"
    message += f"\n💰 POINTS BREAKDOWN\n"
    
    # Base points for win/loss
    current_points = ranking_manager.get_player_stats(result.user_id)
    if current_points:
        base_tier = ranking_manager.get_player_tier(current_points['total_points'])
        base_tier_info = ranking_manager.get_tier_info(base_tier)
        multiplier = base_tier_info['multiplier']
        penalty_reduction = base_tier_info['penalty_reduction']
    else:
        multiplier = 1.5
        penalty_reduction = 0.7
    
    points_breakdown = []
    
    # Victory/Loss base points
    if result.won:
        team_upper = team_str.upper()
        if team_upper == "VILLAGER":
            base_win = ranking_manager.VICTORY_POINTS["village_victory"]
            points_breakdown.append(f"  ✓ Village Victory: +{base_win} pts")
        elif team_upper == "WOLF":
            base_win = ranking_manager.VICTORY_POINTS["wolf_solo_victory"]
            points_breakdown.append(f"  ✓ Wolf Victory: +{base_win} pts")
        elif team_upper == "FIRE":
            base_win = ranking_manager.VICTORY_POINTS["fire_solo_victory"]
            points_breakdown.append(f"  ✓ Fire Team Victory: +{base_win} pts")
        elif team_upper == "SERIAL_KILLER" or team_upper == "KILLER":
            base_win = ranking_manager.VICTORY_POINTS["serial_killer_victory"]
            points_breakdown.append(f"  ✓ Serial Killer Victory: +{base_win} pts")
        elif team_upper == "NEUTRAL":
            base_win = ranking_manager.VICTORY_POINTS["neutral_victory"]
            points_breakdown.append(f"  ✓ Neutral Victory: +{base_win} pts")
        
        # Role mastery bonus
        role_enum = None
        if isinstance(result.role, str):
            try:
                if hasattr(Role, result.role):
                    role_enum = getattr(Role, result.role)
                else:
                    for r in Role:
                        if r.value == result.role or r.name == result.role:
                            role_enum = r
                            break
            except: pass
        elif isinstance(result.role, Role):
            role_enum = result.role
        
        if role_enum and role_enum in ranking_manager.ROLE_BONUSES:
            role_bonus = ranking_manager.ROLE_BONUSES[role_enum]
            if role_bonus > 0:
                points_breakdown.append(f"  ✓ Role Mastery ({role_str}): +{role_bonus} pts")
    else:
        team_lower = team_str.lower()
        loss_penalty = ranking_manager.LOSS_PENALTIES.get(f"{team_lower}_loss", -5)
        adjusted_penalty = int(loss_penalty * penalty_reduction)
        points_breakdown.append(f"  ✗ Team Defeat: {adjusted_penalty} pts")
    
    # Action bonuses/penalties
    if result.actions:
        action_lines = []
        for action, count in result.actions.items():
            if count == 0:
                continue
                
            action_points = ranking_manager.ACTION_POINTS.get(action, 0)
            if action_points == 0:
                continue
            
            # Format action name
            action_name = action.replace('_', ' ').title()
            
            if action_points > 0:
                total_action_pts = action_points * count
                if count > 1:
                    action_lines.append(f"  ✓ {action_name} (x{count}): +{total_action_pts} pts")
                else:
                    action_lines.append(f"  ✓ {action_name}: +{total_action_pts} pts")
            else:
                adjusted_penalty = int(action_points * count * penalty_reduction)
                if count > 1:
                    action_lines.append(f"  ✗ {action_name} (x{count}): {adjusted_penalty} pts")
                else:
                    action_lines.append(f"  ✗ {action_name}: {adjusted_penalty} pts")
        
        if action_lines:
            points_breakdown.append("")
            points_breakdown.append("Performance Actions:")
            points_breakdown.extend(action_lines)
    
    # Survival bonus
    if result.is_alive:
        points_breakdown.append("")
        points_breakdown.append(f"  ✓ Survival Bonus: +1 pt")
    elif not result.won:
        early_penalty = int(-1 * penalty_reduction)
        points_breakdown.append("")
        points_breakdown.append(f"  ✗ Eliminated Early: {early_penalty} pt")
    
    # MVP bonus
    if is_mvp:
        points_breakdown.append("")
        points_breakdown.append(f"  🏆 MVP Award: +10 pts")
    
    message += "\n".join(points_breakdown)
    
    # Tier multiplier info
    message += f"\n\n⚖️ Tier Multiplier: {multiplier}x ({tier.value})"
    if penalty_reduction != 1.0:
        message += f"\n🛡️ Penalty Reduction: {penalty_reduction}x"
    
    # Final total
    message += f"\n\n📊 TOTAL EARNED: {points_earned:+d} points"
    
    # Tier change notification
    message += f"\n{'─' * 40}\n"
    if tier_changed:
        message += f"🎖️ TIER CHANGE!\n"
        message += f"New Rank: {tier_info['emoji']} {tier.value}\n"
    else:
        message += f"Current Rank: {tier_info['emoji']} {tier.value}\n"
    
    # Progress hint
    stats = ranking_manager.get_player_stats(result.user_id)
    if stats:
        tier_list = list(ranking_manager.TIER_SYSTEM.keys())
        try:
            current_idx = tier_list.index(tier)
            if current_idx < len(tier_list) - 1:
                next_tier = tier_list[current_idx + 1]
                next_range = ranking_manager.TIER_SYSTEM[next_tier]["range"]
                points_needed = next_range[0] - (stats['total_points'] + points_earned)
                if points_needed > 0:
                    message += f"\n📈 Next Rank: {points_needed} pts to {next_tier.value}"
        except: pass
    
    message += f"\n\nType /stats to view your full profile!"
    
    return message

async def send_player_breakdowns(context: ContextTypes.DEFAULT_TYPE, processed_results: List[Dict]):
    """Send individual performance breakdowns to all players"""
    for result in processed_results:
        user_id = result['user_id']
        breakdown_msg = result.get('breakdown_message', '')
        
        if not breakdown_msg:
            continue
        
        try:
            # ✅ CRITICAL FIX: Send without parse_mode to avoid markdown issues
            await context.bot.send_message(
                chat_id=user_id,
                text=breakdown_msg
                # REMOVED: parse_mode='Markdown'
            )
            logger.info(f"Sent performance breakdown to {result['first_name']} ({user_id})")
        except Exception as e:
            logger.error(f"Failed to send breakdown to {result['first_name']}: {e}")
            # Try again with more sanitized text
            try:
                sanitized_msg = breakdown_msg.replace('**', '').replace('*', '').replace('_', '')
                await context.bot.send_message(
                    chat_id=user_id,
                    text=sanitized_msg
                )
                logger.info(f"Sent sanitized breakdown to {result['first_name']}")
            except Exception as e2:
                logger.error(f"Failed even with sanitized message: {e2}")
        
        # Small delay to avoid rate limiting
        await asyncio.sleep(0.3)

def calculate_and_award_mvp(game_results: List[Dict]) -> Optional[int]:
    """Calculate MVP and award bonus points"""
    if len(game_results) < 3:
        return None  # Too few players for meaningful MVP
    
    mvp_scores = {}
    
    for result in game_results:
        score = 0
        user_id = result['user_id']
        
        # Base points for winning (major factor)
        if result.get('won', False):
            score += 10
        
        # ✅ FIXED: Default is_alive to False if missing
        # Survival bonus (staying alive is valuable)
        if result.get('is_alive', False):
            score += 5
        
        # Points earned (performance indicator)
        score += max(0, result.get('points_earned', 0))
        
        # Actions bonus (skill-based)
        actions = result.get('actions', {})
        score += actions.get('investigate_evil', 0) * 3
        score += actions.get('successful_protection', 0) * 3
        score += actions.get('lynch_evil', 0) * 2
        score += actions.get('witch_save', 0) * 4
        score += actions.get('witch_poison_evil', 0) * 3
        score += actions.get('hunter_revenge_evil', 0) * 3
        
        # Penalty for mistakes
        score -= actions.get('mislynch_village', 0) * 2
        score -= actions.get('vigilante_kill_village', 0) * 5
        score -= actions.get('major_mistake', 0) * 3
        
        mvp_scores[user_id] = score
    
    # Find MVP (highest score)
    if not mvp_scores:
        return None
    
    sorted_candidates = sorted(mvp_scores.items(), key=lambda x: x[1], reverse=True)
    mvp_user_id, mvp_score = sorted_candidates[0]
    
    # Require significant score to be MVP (avoid random winners)
    if mvp_score < 5:
        return None
    
    # Award MVP in database
    try:
        with sqlite3.connect(ranking_manager.db_path) as conn:
            cursor = conn.cursor()
            
            # Award MVP bonus points (10 points)
            cursor.execute('''
                UPDATE player_stats 
                SET mvp_awards = mvp_awards + 1,
                    total_points = total_points + 10
                WHERE user_id = ?
            ''', (mvp_user_id,))
            
            # Mark in game history
            cursor.execute('''
                UPDATE game_history 
                SET was_mvp = TRUE,
                    points_earned = points_earned + 10
                WHERE user_id = ? 
                ORDER BY game_date DESC 
                LIMIT 1
            ''', (mvp_user_id,))
            
            conn.commit()
            logger.info(f"Awarded MVP to user {mvp_user_id} (+10 points)")
            
    except Exception as e:
        logger.error(f"Error awarding MVP: {e}")
    
    return mvp_user_id

def get_role_performance_stats(role: Role) -> Dict:
    """Get performance statistics for a specific role"""
    try:
        with sqlite3.connect(ranking_manager.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) as total_games,
                       SUM(CASE WHEN won = 1 THEN 1 ELSE 0 END) as wins,
                       AVG(points_earned) as avg_points
                FROM game_history 
                WHERE role = ?
            ''', (role.value,))
            
            result = cursor.fetchone()
            if result and result['total_games'] > 0:
                return {
                    'total_games': result['total_games'],
                    'wins': result['wins'],
                    'win_rate': (result['wins'] / result['total_games']) * 100,
                    'avg_points': round(result['avg_points'], 1)
                }
            else:
                return {'total_games': 0, 'wins': 0, 'win_rate': 0, 'avg_points': 0}
                
    except Exception as e:
        logger.error(f"Error getting role stats for {role.value}: {e}")
        return {'total_games': 0, 'wins': 0, 'win_rate': 0, 'avg_points': 0}

def cleanup_old_games(days_old: int = 90):
    """Clean up game history older than specified days"""
    try:
        with sqlite3.connect(ranking_manager.db_path) as conn:
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            cursor.execute('DELETE FROM game_history WHERE game_date < ?', (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logger.info(f"Cleaned up {deleted_count} old game records")
            return deleted_count
            
    except Exception as e:
        logger.error(f"Error cleaning up old games: {e}")
        return 0

# Integration hooks for your existing mechanics

def on_player_investigate(user_id: int, target_role: Role, is_evil: bool):
    """Hook for when a player investigates someone"""
    success = (target_role.team != Team.VILLAGER) == is_evil
    track_player_action(user_id, "investigate", success)

def on_player_protect(user_id: int, target_attacked: bool):
    """Hook for when a player protects someone"""
    track_player_action(user_id, "protect", target_attacked)

def on_player_vote_lynch(user_id: int, target_role: Role):
    """Hook for when a player votes to lynch someone"""
    if target_role.team != Team.VILLAGER:
        track_player_action(user_id, "eliminate_evil")
    else:
        track_player_action(user_id, "mislynch_village")

def on_player_eliminated_early(user_id: int):
    """Hook for when a player dies early (first 2 days)"""
    track_player_action(user_id, "early_death")

# Export all the functions your bot will need
__all__ = [
    'ranking_manager',
    'stats_command',
    'leaderboard_command', 
    'rank_info_command',
    'record_batch_game_results',
    'generate_final_reveal_message',
    'send_player_breakdowns',
    'process_game_end_rankings',
    'track_player_action',
    'get_player_quick_stats',
    'send_tier_notification',
    'calculate_mvp_candidates',
    'get_role_performance_stats',
    'cleanup_old_games',
    'on_player_investigate',
    'on_player_protect', 
    'on_player_vote_lynch',
    'on_player_eliminated_early'
]