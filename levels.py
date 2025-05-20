# leveling.py
import discord
from discord.ext import commands
import time

def setup(bot, db):
    @bot.command(name="level")
    async def level(ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        stats = db.get_user_stats(user_id)
        user_data = db.get_user(user_id)
        current_level = user_data["level"]
        current_exp = user_data["experience"]
        needed_exp = get_required_exp(current_level)

        embed = discord.Embed(title=f"📊 Уровень {target.display_name}", color=0x00ffcc)
        embed.add_field(name="🏆 Уровень", value=str(current_level), inline=False)
        embed.add_field(name="✨ Опыт", value=f"{current_exp} / {needed_exp}", inline=False)
        embed.add_field(name="💬 Сообщения", value=str(stats["messages"]), inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="activity")
    async def activity(ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        stats = db.get_user_stats(user_id)
        user_data = db.get_user(user_id)
        total_time = time.time() - stats["joined_at"]
        days, remainder = divmod(total_time, 86400)
        hours, _ = divmod(remainder, 3600)

        embed = discord.Embed(title=f"📈 Активность {target.display_name}", color=0x00ffcc)
        embed.add_field(name="🕒 Время на сервере", value=f"{int(days)}д {int(hours)}ч", inline=False)
        embed.add_field(name="✉️ Сообщения", value=str(stats["messages"]), inline=False)
        embed.add_field(name="✨ Опыт", value=str(user_data["experience"]), inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="topactivity")
    async def top_activity(ctx, top_n: int = 10):
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT u.user_id, u.experience, s.messages
            FROM users u
            LEFT JOIN user_stats s ON u.user_id = s.user_id
            ORDER BY u.experience + IFNULL(s.messages, 0) DESC
            LIMIT ?
        """, (top_n,))
        top_users = cursor.fetchall()

        if not top_users:
            await ctx.send("❌ Нет данных по активности.")
            return

        embed = discord.Embed(title="🏆 Топ по активности", color=0xFFD700)
        for idx, (user_id, exp, messages) in enumerate(top_users, 1):
            try:
                user = await bot.fetch_user(int(user_id))
                total = exp + (messages or 0)
                embed.add_field(name=f"{idx}. {user.display_name}", value=f"Очки активности: {total}", inline=False)
            except Exception as e:
                print(f"Error fetching user {user_id}: {e}")

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
    exp = user_data["experience"] + xp_gain

    leveled_up = False
    while exp >= get_required_exp(level):
        exp -= get_required_exp(level)
        level += 1
        leveled_up = True

    db.update_level_and_exp(user_id, level, exp)

    if leveled_up:
        try:
            await message.channel.send(
                f"🎉 {message.author.mention} повысил(а) уровень до **{level}**! Поздравляем!"
            )
        except discord.Forbidden:
            pass  # Нет прав на отправку сообщений в канал
