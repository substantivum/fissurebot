# main.py
import os
from dotenv import load_dotenv
from discord import Intents
from discord.ext import commands

# Настройка интентов
intents = Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.reactions = True

# Инициализация бота
TOKEN = os.getenv("DISCORD_TOKEN") or "YOUR_BOT_TOKEN"
bot = commands.Bot(command_prefix="!", intents=intents)

# Импорты модулей (после создания бота)
from database import BotDatabase
from events import setup as setup_events
from music import setup as setup_music
from economy import setup as setup_economy
from admin import setup as setup_admin
from utils import logger

# Инициализация базы данных
db = BotDatabase()
logger.info("База данных инициализирована")

# Регистрация модулей
setup_events(bot, db)
setup_music(bot, db)
setup_economy(bot, db)
setup_admin(bot, db)