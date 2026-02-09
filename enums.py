import logging
from enum import Enum

logger = logging.getLogger(__name__)

class GamePhase(Enum):
    LOBBY = "lobby"
    NIGHT = "night"
    DAY = "day"
    VOTING = "voting"
    ENDED = "ended"

class Team(Enum):
    VILLAGER = "Villager"
    WOLF = "Wolf"
    FIRE = "Fire"
    NEUTRAL = "Neutral"
    KILLER = "Killer"

class Role(Enum):
    # Villager roles
    VILLAGER = ("👤", "Villager", Team.VILLAGER)
    SEER = ("🔮", "Seer", Team.VILLAGER)
    DOCTOR = ("💊", "Doctor", Team.VILLAGER)
    HUNTER = ("🏹", "Hunter", Team.VILLAGER)
    WITCH = ("🧙‍♀️", "Witch", Team.VILLAGER)
    DETECTIVE = ("🕵️", "Detective", Team.VILLAGER)
    VIGILANTE = ("⚔️", "Vigilante", Team.VILLAGER)
    MAYOR = ("🏛️", "Mayor", Team.VILLAGER)
    ORACLE = ("🌟", "Oracle", Team.VILLAGER)
    BODYGUARD = ("🛡️", "Bodyguard", Team.VILLAGER)
    INSOMNIAC = ("👁️", "Insomniac", Team.VILLAGER)
    TWINS = ("👥", "Twins", Team.VILLAGER)
    CURSED_VILLAGER = ("😨", "Cursed Villager", Team.VILLAGER)
    FOOL = ("🤡❓", "Fool", Team.VILLAGER)
    APPRENTICE_SEER = ("🔮📚", "Apprentice Seer", Team.VILLAGER)
    PLAGUE_DOCTOR = ("🦠", "Plague Doctor", Team.VILLAGER)
    PRIEST = ("⛪", "Priest", Team.VILLAGER)
    CUPID = ("💘", "Cupid", Team.VILLAGER)
    STRAY = ("🐾", "Stray", Team.VILLAGER)

    # Wolf roles
    WEREWOLF = ("🐺", "Werewolf", Team.WOLF)
    ALPHA_WOLF = ("🐺🌑", "Alpha Wolf", Team.WOLF)
    WOLF_SHAMAN = ("🐺🔮", "Wolf Shaman", Team.WOLF)


    SERIAL_KILLER = ("🔪", "Serial Killer",Team.KILLER)  
    WEBKEEPER = ("🕷️", "Webkeeper",Team.KILLER)

    # Fire team roles
    ARSONIST = ("🔥", "Arsonist", Team.FIRE)
    BLAZEBRINGER = ("🔥⚡", "Blaze bringer", Team.FIRE)
    ACCELERANT_EXPERT = ("🔥🧪", "Accelerant Expert", Team.FIRE)

    # Neutral roles
    JESTER = ("🤡", "Jester", Team.NEUTRAL)
    DOPPELGANGER = ("🎭", "Doppelganger", Team.NEUTRAL)
    EXECUTIONER = ("🪓", "Executioner", Team.NEUTRAL)
    GRAVE_ROBBER = ("⚰️", "Grave Robber", Team.NEUTRAL)
    MIRROR_PHANTOM = ("🪞", "Mirror Phantom", Team.NEUTRAL)
    THIEF = ("🗝️", "Thief", Team.NEUTRAL)

    def __init__(self, emoji, name, team):
        self.emoji = emoji
        self.role_name = name
        self.team = team

logger.info("Enums module loaded successfully")
