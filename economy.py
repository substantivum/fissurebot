import discord
from discord.ext import commands
from discord.ui import View, Button
import sqlite3
import random
import time
import re
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional


# Константы
DAILY_COOLDOWN = 24 * 60 * 60  # 24 часа в секундах
EMOJI_REGEX = re.compile(r'<a?:(\w+):\d+>|[\U00010000-\U0010ffff]')
PASSIVE_INCOME_RATE = 6  # монет в час за онлайн

def setup(bot, db):
    @bot.event
    async def on_voice_state_update(member, before, after):
        """Обработка событий голосовых каналов"""
        user_id = str(member.id)
        
        # Пользователь зашел в голосовой канал
        if before.channel is None and after.channel is not None:
            db.set_voice_join_time(user_id, int(time.time()))
            db.set_join_timestamp(user_id, int(time.time()))
        
        # Пользователь вышел из голосового канала
        elif before.channel is not None and after.channel is None:
            join_time = db.get_voice_join_time(user_id)
            if join_time:
                time_spent = int(time.time()) - join_time
                db.update_voice_time(user_id, time_spent)
                db.set_voice_join_time(user_id, None)

    @bot.event
    async def on_message(message):
        """Обработка сообщений для экономики"""
        if message.author.bot:
            return
        
        user_id = str(message.author.id)
        
        # Создаем пользователя, если его нет в базе
        if not db.get_user(user_id):
            db.create_user(user_id)
        
        # Обновляем статистику сообщений
        db.update_message_count(user_id)
        
        # Отслеживание эмодзи
        for match in EMOJI_REGEX.finditer(message.content):
            emoji_str = match.group()
            db.track_emoji(user_id, emoji_str)
        
        # Отслеживание слов (игнорируем команды)
        if not message.content.startswith(bot.command_prefix):
            words = message.content.lower().split()
            for word in words:
                word = ''.join(c for c in word if c.isalnum())
                if len(word) >= 4:  # Игнорируем короткие слова
                    db.track_word(user_id, word)
                    
        if not db.get_user(user_id):
            db.create_user(user_id)
            db.add_first_message_time(user_id)

    def calculate_passive_income(user_id: str) -> int:
        stats = db.get_user_stats(user_id)
        if not stats or not stats.get('time_first_message'):
            return 0  # No first message = no income

        credited_hours = stats.get('credited_hours', 0)
        time_first_message = int(stats['time_first_message'])

        # Calculate total hours since the first message
        total_hours = int((time.time() - time_first_message) // 3600)
        new_hours = total_hours - credited_hours

        if new_hours <= 0:
            return 0

        reward = new_hours * PASSIVE_INCOME_RATE
        try:
            with db.conn:
                db.update_balance(user_id, reward)
                db.conn.execute(
                    "UPDATE user_stats SET credited_hours = ? WHERE user_id = ?",
                    (credited_hours + new_hours, user_id)
                )
            return reward
        except sqlite3.Error as e:
            logger.error(f"Passive income error: {e}")
            return 0


    @bot.command(name="fissdaily")
    async def daily(ctx):
        user_id = str(ctx.author.id)
        
        # Ensure user exists
        if not db.get_user(user_id):
            db.create_user(user_id)
        
        # Get fresh data after potential creation
        user_data = db.get_user(user_id)
        stats = db.get_user_stats(user_id)
        
        if not user_data or not stats:
            await ctx.send("❌ Не удалось загрузить данные пользователя. Попробуйте снова.")
            return

        now = int(time.time())
        last_daily = stats.get("last_daily", 0)
        elapsed = now - last_daily

        if elapsed < DAILY_COOLDOWN:
            remaining = DAILY_COOLDOWN - elapsed
            hours, rem = divmod(remaining, 3600)
            minutes, _ = divmod(rem, 60)
            await ctx.send(f"⏳ Вы сможете получить награду через {hours}ч {minutes}м")
            return

        streak = stats.get("daily_streak", 0)
        if elapsed < 2 * DAILY_COOLDOWN:
            streak = (streak % 7) + 1
        else:
            streak = 1

        base_rewards = [45, 50, 55, 60, 65, 70, 75]
        base_reward = base_rewards[min(streak - 1, 6)]
        total_reward = base_reward + user_data['level'] + streak

        try:
            with db.conn:
                db.update_balance(user_id, total_reward)
                db.conn.execute("""
                    UPDATE user_stats 
                    SET last_daily = ?, daily_streak = ? 
                    WHERE user_id = ?
                """, (now, streak, user_id))
            
            await ctx.send(
                f"🎁 День {streak}/7: Вы получили {base_reward} монет + {user_data['level']} за уровень + {streak} за ежедневную команду = **{total_reward} монет**\n"
                f"Ваш новый баланс: {user_data['balance'] + total_reward}"
            )
        except Exception as e:
            await ctx.send("❌ Произошла ошибка при обработке ежедневной награды")
            logger.error(f"Daily command error: {e}")

    @bot.command(name="balance")
    async def balance(ctx, member: Optional[discord.Member] = None):
        """Показывает баланс пользователя"""
        target = member or ctx.author
        user_id = str(target.id)
        user = db.get_user(user_id)
        
        if not user:
            db.create_user(user_id)
            user = db.get_user(user_id)
        
        passive_income = calculate_passive_income(user_id)
        total_balance = user['balance'] + passive_income
        
        await ctx.send(f"💰 {target.display_name} имеет {total_balance} монет.")

    @bot.command(name="leaderboard")
    async def leaderboard(ctx, top_n: int = 10):
        """Таблица лидеров по балансу"""
        if not 1 <= top_n <= 25:
            return await ctx.send("❌ Пожалуйста, укажите число от 1 до 25")

        try:
            cursor = db.conn.cursor()
            cursor.execute("""
                SELECT user_id, balance FROM users 
                ORDER BY balance DESC LIMIT ?
            """, (top_n,))
            
            embed = discord.Embed(title="🏆 Таблица лидеров", color=0xFFD700)
            
            leaderboard = []
            for idx, (user_id, balance) in enumerate(cursor.fetchall(), 1):
                try:
                    user = await bot.fetch_user(int(user_id))
                    leaderboard.append(f"{idx}. {user.display_name} — {balance} монет")
                except:
                    leaderboard.append(f"{idx}. [Неизвестный] — {balance} монет")
            
            embed.add_field(
                name="💰 Богатейшие игроки",
                value="\n".join(leaderboard) or "Нет данных",
                inline=False
            )
            
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send("❌ Произошла ошибка при получении данных")

    class RoleShopView(View):
        """View для магазина ролей"""
        def __init__(self, ctx, db):
            super().__init__(timeout=180)
            self.ctx = ctx
            self.db = db
            self.load_buttons()
        
        def load_buttons(self):
            """Загружает кнопки для ролей"""
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT role_name, price FROM role_shop")
            
            for role_name, price in cursor.fetchall():
                button = Button(
                    label=f"Купить {role_name} ({price} монет)",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"role_{role_name}_{int(time.time())}"
                )
                button.callback = self.create_callback(role_name, price)
                self.add_item(button)
        
        def create_callback(self, role_name: str, price: int):
            """Создает callback для кнопки"""
            async def callback(interaction: discord.Interaction):
                if interaction.user != self.ctx.author:
                    return await interaction.response.send_message(
                        "❌ Это не ваш магазин!", ephemeral=True)
                
                user_id = str(interaction.user.id)
                user = self.db.get_user(user_id)
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                
                if not role:
                    return await interaction.response.send_message(
                        f"❌ Роль {role_name} не найдена!", ephemeral=True)
                
                if role in interaction.user.roles:
                    return await interaction.response.send_message(
                        f"❌ У вас уже есть роль {role_name}!", ephemeral=True)
                
                if user['balance'] < price:
                    return await interaction.response.send_message(
                        f"❌ Недостаточно монет! Нужно {price}", ephemeral=True)
                
                try:
                    self.db.update_balance(user_id, -price)
                    await interaction.user.add_roles(role)
                    await interaction.response.send_message(
                        f"✅ Вы купили роль {role_name} за {price} монет!", 
                        ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ Ошибка: {str(e)}", ephemeral=True)
            
            return callback

    @bot.command(name="roleshop")
    async def roleshop(ctx):
        """Магазин ролей сервера"""
        cursor = db.conn.cursor()
        cursor.execute("SELECT role_name, price FROM role_shop")
        roles = cursor.fetchall()
        
        if not roles:
            return await ctx.send("🛒 Магазин ролей пуст!")
        
        embed = discord.Embed(title="🎖️ Магазин ролей", color=0x00FF00)
        description = []
        
        for role_name, price in roles:
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if role:
                description.append(f"{role.mention} — {price} монет")
            else:
                description.append(f"`{role_name}` — {price} монет (роль не найдена)")
        
        embed.description = "\n".join(description)
        await ctx.send(embed=embed, view=RoleShopView(ctx, db))