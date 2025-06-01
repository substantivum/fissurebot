# main.py
import os
import asyncio
import discord
from dotenv import load_dotenv
from discord import Intents
from discord.ext import commands
from utils import logger

ALLOWED_CHANNEL_IDS = [1367800241029644310, 1375854037811069009]
load_dotenv()

# Настройка интентов
intents = Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.reactions = True

# Инициализация бота
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD= discord.Object(int(os.getenv("GUILD_ID")))
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None  # This completely disables the default help
)

@bot.before_invoke
async def ensure_correct_channel(ctx):
    if ctx.channel.id not in ALLOWED_CHANNEL_IDS:
        # Отправляем сообщение и запоминаем его
        msg = await ctx.send(f"❌ Команды можно использовать только в специальных каналах")
        # Устанавливаем таймер на удаление через 10 секунд
        await asyncio.sleep(10)
        try:
            await msg.delete()
        except discord.NotFound:
            pass  # Сообщение уже удалено или не найдено
        raise commands.CommandError("Команда вызвана не в том канале")
        
# Импорты модулей (после создания бота)
import levels
from database import BotDatabase
from events import setup as setup_events
from music import setup as setup_music
from economy import setup as setup_economy
from admin import setup as setup_admin
from levels import setup as setup_levels
from games import setup as setup_games
from rooms import setup as setup_rooms
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
setup_games(bot, db)
setup_rooms(bot)

# @bot.event
# async def on_ready():
#     await bot.tree.sync(guild=GUILD)
#     logger.info("Commands synced to server")
    
    
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")