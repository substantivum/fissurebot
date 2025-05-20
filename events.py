# events.py
import discord
from database import BotDatabase
from utils import DAILY_COOLDOWN
from levels import handle_message_xp

def setup(bot, db):
    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user}")
    
    @bot.event
    async def on_message(message):
        if not message.author.bot:
            db.update_message_count(str(message.author.id))
            await handle_message_xp(bot, db, message)
            await bot.process_commands(message)
    
    @bot.event
    async def on_reaction_add(reaction, user):
        if not user.bot:
            db.update_emoji_usage(str(user.id), str(reaction.emoji))