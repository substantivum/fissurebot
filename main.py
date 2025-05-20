# main.py
import os
from dotenv import load_dotenv
from discord import Intents
from discord.ext import commands

load_dotenv()

# Настройка интентов
intents = Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.reactions = True

# Инициализация бота
TOKEN = os.getenv("DISCORD_TOKEN")
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None  # This completely disables the default help
)

# Импорты модулей (после создания бота)
from database import BotDatabase
from events import setup as setup_events
from music import setup as setup_music
from economy import setup as setup_economy
from admin import setup as setup_admin
from levels import setup as setup_levels
from utils import logger

# Инициализация базы данных
db = BotDatabase()
logger.info("База данных инициализирована")

# Регистрация модулей   
setup_events(bot, db)
setup_music(bot, db)
setup_economy(bot, db)
setup_admin(bot, db)
setup_levels(bot, db)

if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")