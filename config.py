"""Simple defaults; advanced CLI/experiment settings live in settings.py."""

SEED = 1111
WORKING_DAYS = 30
NUMBER_OF_ROOMS = 12

CLIENT_NAMES = (
    "Sqwore",
    "Gleb Viktorov",
    "Kishlak",
    "Nine Mice",
    "Kai Angel",
    "Zhenya Milkovskiy",
    "Nikita",
    "Israel Yehuda",
    "Zuzka",
    "Karinka",
    "Veronika",
    "Egor Kreed",
    "Dora",
    "Masha",
    "Vladislav",
    "Dmitriy",
    "Mikhail",
)

# Re-export these names so existing commands and test imports still work.
from settings import PRESETS, SimulationConfig
