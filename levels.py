import discord
from discord.ext import commands
import utils
import time

LEVEL_UP_EXPERIENCE = 100

def setup(bot, db):
    @bot.event
    async def on_message(message):
        # Ignore messages from the bot itself
        if message.author.bot:
            return

        # Skip experience gain if the message starts with the command prefix
        if message.content.startswith(bot.command_prefix):
            # Process the command first so the bot can respond
            await bot.process_commands(message)
            return

        # Handle experience gain for regular messages
        await handle_message_xp(bot, db, message)

        # Continue processing other commands
        await bot.process_commands(message)

    @bot.command(name="stats")
    async def stats(ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        
        # Получаем данные с проверкой на существование
        user_data = db.get_user(user_id) or {
            "level": 1,
            "experience": 0,
            "balance": 0
        }
        stats = db.get_user_stats(user_id) or {
            "messages": 0,
            "join_timestamp": time.time(),
            "daily_streak": 0
        }

        # Рассчитываем необходимые значения
        current_level = user_data.get("level", 1)
        current_exp = user_data.get("experience", 0)
        needed_exp = get_required_exp(current_level)
        total_time = time.time() - stats.get("join_timestamp", time.time())
        days, remainder = divmod(total_time, 86400)
        hours, _ = divmod(remainder, 3600)

        # Создаем embed
        embed = discord.Embed(
            title=f"📊 Статистика {target.display_name}",
            color=0x00ffcc
        )
        
        # Добавляем поля с информацией
        embed.add_field(name="🏆 Уровень", value=str(current_level), inline=True)
        embed.add_field(name="✨ Опыт", value=f"{current_exp}/{needed_exp}", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)  # Пустое поле для выравнивания
        
        embed.add_field(name="💬 Сообщения", value=str(stats.get("messages", 0)), inline=True)
        embed.add_field(name="🕒 На сервере", value=f"{int(days)}д {int(hours)}ч", inline=True)
        embed.add_field(name="💰 Баланс", value=f"{user_data.get('balance', 0)} монет", inline=True)

        # Добавляем прогресс-бар уровня
        progress = min(current_exp / needed_exp, 1.0)
        progress_bar = f"[{'█' * int(progress * 20)}{'░' * (20 - int(progress * 20))}] {progress*100:.1f}%"
        embed.add_field(name="Прогресс уровня", value=progress_bar, inline=False)

        await ctx.send(embed=embed)

def get_required_exp(level: int) -> int:
    """Returns the experience required for the next level with exponential growth."""
    return 100 * (2 ** (level - 1))

async def handle_message_xp(bot, db, message, xp_gain=5):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    user_data = db.get_user(user_id)

    if not user_data:
        db.create_user(user_id)
        user_data = db.get_user(user_id)

    level = user_data["level"]
    experience = user_data["experience"] + xp_gain

    leveled_up = False
    # Check if the user has gained enough experience to level up
    while experience >= LEVEL_UP_EXPERIENCE * (2 ** (level - 1)):  # Using LEVEL_UP_EXPERIENCE multiplier
        experience -= LEVEL_UP_EXPERIENCE * (2 ** (level - 1))  # Subtract experience for level-up
        level += 1  # Level up
        leveled_up = True

    # Update the user's experience and level in the database
    db.update_level_and_exp(user_id, level, experience)

    # Notify user about the level up if leveled up
    if leveled_up:
        try:
            await message.channel.send(
                f"🎉 {message.author.mention} повысил(а) уровень до **{level}**! Поздравляем!"
            )
        except discord.Forbidden:
            pass  # No permission to send message in the channel
