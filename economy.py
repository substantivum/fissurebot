import discord
from discord.ext import commands
from discord.ui import View, Button
import sqlite3
import random
import time
import re
from datetime import datetime
from collections import defaultdict

# Константы
DAILY_COOLDOWN = 24 * 60 * 60  # 24 часа в секундах
EMOJI_REGEX = re.compile(r'<a?:(\w+):\d+>|[\U00010000-\U0010ffff]')

def setup(bot, db):

    @bot.event
    async def on_voice_state_update(member, before, after):
        user_id = str(member.id)
        # Пользователь зашел в голосовой канал
        if before.channel is None and after.channel is not None:
            db.set_voice_join_time(user_id, int(time.time()))
        # Пользователь вышел из голосового канала
        elif before.channel is not None and after.channel is None:
            join_time = db.get_voice_join_time(user_id)
            if join_time:
                time_spent = int(time.time()) - join_time
                db.update_voice_time(user_id, time_spent)
                db.set_voice_join_time(user_id, None)

    @bot.event
    async def on_message(message):
        if message.author.bot:
            return
        
        user_id = str(message.author.id)
        
        # Создаем пользователя, если его нет в базе
        if not db.get_user(user_id):
            db.create_user(user_id)
        
        # Обновляем статистику сообщений
        stats = db.get_user_stats(user_id)
        if stats:
            try:
                db.conn.execute("""
                    UPDATE user_stats SET messages = messages + 1 WHERE user_id = ?
                """, (user_id,))
                db.conn.commit()
            except sqlite3.Error as e:
                print(f"[ERROR] Ошибка при обновлении статистики сообщений: {e}")
        
        # Отслеживание всех типов эмодзи (включая анимированные)
        for match in EMOJI_REGEX.finditer(message.content):
            emoji_str = match.group()
            db.track_emoji(user_id, emoji_str)
        
        # Отслеживание слов (игнорируем команды)
        if not message.content.startswith(bot.command_prefix):
            words = message.content.lower().split()
            for word in words:
                # Удаляем знаки препинания
                word = ''.join(c for c in word if c.isalnum())
                if word:  # Проверяем, что слово не пустое после обработки
                    db.track_word(user_id, word)
           

    @bot.command(name="fissdaily")
    async def daily(ctx):
        user_id = str(ctx.author.id)
        user_data = db.get_user(user_id)
        stats = db.get_user_stats(user_id)
        
        if not user_data:
            db.create_user(user_id)
            user_data = db.get_user(user_id)
            stats = db.get_user_stats(user_id)

        # If last_daily is None, this is likely the first time
        last_daily = stats.get("last_daily", 0) or 0

        if time.time() - last_daily < DAILY_COOLDOWN:
            remaining = int(DAILY_COOLDOWN - (time.time() - last_daily))
            hours, remainder = divmod(remaining, 3600)
            minutes, seconds = divmod(remainder, 60)
            await ctx.send(f"⏳ Вы сможете получить награду через {hours}ч {minutes}м {seconds}с")
            return
        
        # Random coins between 35 and 50
        amount = random.randint(35, 50)

        # Level-based bonus (5 * level)
        level = user_data['level']  # Get the user's level
        level_bonus = 5 * level

        # Calculate total reward
        total = amount + level_bonus

        streak = stats["daily_streak"] or 0
        if time.time() - last_daily < DAILY_COOLDOWN * 2:
            streak += 1
        else:
            streak = 1
        
        bonus = min(streak * 5, 150)  # Max streak bonus of 150
        total += bonus

        db.update_balance(user_id, total)
        try:
            db.conn.execute("""
                UPDATE user_stats
                SET last_daily = ?, daily_streak = ?
                WHERE user_id = ?
            """, (int(time.time()), streak, user_id))
            db.conn.commit()
        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при обновлении ежедневной статистики: {e}")
        
        await ctx.send(
            f"🎉 Вы получили {amount} монет (серия: {streak} дней) + {bonus} бонус + {level_bonus} за уровень = **{total} монет**!\n"
            f"Ваш баланс: {user_data['balance'] + total}"
        )
        
    @bot.command(name="balance")
    async def balance(ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        user = db.get_user(user_id)
        
        if not user:
            db.create_user(user_id)
            user = db.get_user(user_id)
        
        extra = credit_time_based_coins(user_id, stats)
        await ctx.send(f"💰 {target.display_name} имеет {user['balance'] + extra} монет (включая +{extra} за онлайн)")

    
    @bot.command(name="leaderboard")
    async def leaderboard(ctx, top_n: int = 10):
        # Validate top_n input
        if top_n < 1 or top_n > 25:
            await ctx.send("❌ Пожалуйста, укажите число от 1 до 25")
            return

        try:
            # Get money leaderboard
            cursor = db.conn.cursor()
            cursor.execute("""
                SELECT user_id, balance 
                FROM users 
                ORDER BY balance DESC 
                LIMIT ?
            """, (top_n,))
            money_top = cursor.fetchall()

            embed = discord.Embed(title="🏆 Таблица лидеров", color=0xFFD700)

            if money_top:
                money_desc = []
                for idx, (user_id, balance) in enumerate(money_top, 1):
                    try:
                        user = await bot.fetch_user(int(user_id))
                        money_desc.append(f"{idx}. {user.display_name} — {balance} монет")
                    except Exception:
                        money_desc.append(f"{idx}. [Неизвестный] — {balance} монет")
                
                embed.add_field(
                    name="💰 Богатейшие игроки",
                    value="\n".join(money_desc),
                    inline=False
                )

            embed.set_footer(text=f"Показано топ-{top_n} игроков")
            await ctx.send(embed=embed)

        except sqlite3.Error as e:
            print(f"[ОШИБКА БД] Ошибка таблицы лидеров: {e}")
            await ctx.send("❌ Произошла ошибка при получении данных из базы.")
        except Exception as e:
            print(f"[ОШИБКА] Непредвиденная ошибка: {e}")
            await ctx.send("❌ Произошла непредвиденная ошибка.")
            
    @bot.command(name="roleshop")
    async def roleshop(ctx):
        class RoleShopView(View):
            def __init__(self):
                super().__init__(timeout=None)
                self.load_roles()
            
            def load_roles(self):
                try:
                    cursor = db.conn.cursor()
                    cursor.execute("SELECT role_name, price FROM role_shop")
                    self.roles = cursor.fetchall()
                except sqlite3.Error as e:
                    print(f"[ERROR] Ошибка при загрузке ролей: {e}")
                    self.roles = []

            async def create_button_callback(self, role_name: str, price: int):
                async def button_callback(interaction: discord.Interaction):
                    user_id = str(interaction.user.id)
                    guild = interaction.guild
                    role = discord.utils.get(guild.roles, name=role_name)

                    if not role:
                        await interaction.response.send_message(
                            f"❌ Роль `{role_name}` не найдена на этом сервере.",
                            ephemeral=True
                        )
                        return

                    if role in interaction.user.roles:
                        await interaction.response.send_message(
                            f"❌ У вас уже есть роль `{role_name}`.",
                            ephemeral=True
                        )
                        return

                    user = db.get_user(user_id)
                    if not user:
                        db.create_user(user_id)
                        user = db.get_user(user_id)

                    if user['balance'] < price:
                        await interaction.response.send_message(
                            f"❌ Недостаточно монет для покупки `{role_name}`.",
                            ephemeral=True
                        )
                        return

                    db.update_balance(user_id, -price)
                    try:
                        await interaction.user.add_roles(role)
                        await interaction.response.send_message(
                            f"✅ Вы купили роль `{role_name}` за {price} монет!",
                            ephemeral=True
                        )
                    except discord.Forbidden:
                        await interaction.response.send_message(
                            "❌ Не удалось выдать роль — недостаточно прав.",
                            ephemeral=True
                        )
                    except Exception as e:
                        print(f"[ERROR] Ошибка при выдаче роли: {e}")
                        await interaction.response.send_message(
                            "❌ Произошла ошибка при покупке роли.",
                            ephemeral=True
                        )
                return button_callback

        embed = discord.Embed(title="🎖️ Магазин ролей", color=0x00ff00)
        view = RoleShopView()

        try:
            cursor = db.conn.cursor()
            cursor.execute("SELECT role_name, price FROM role_shop")
            roles = cursor.fetchall()

            if not roles:
                embed.description = "В магазине пока нет ролей."
                await ctx.send(embed=embed)
                return

            description_lines = []

            for role_name, price in roles:
                role = discord.utils.get(ctx.guild.roles, name=role_name)
                if role:
                    description_lines.append(f"{role.mention} — {price} монет")
                else:
                    description_lines.append(f"`{role_name}` — {price} монет (роль не найдена)")

                button = Button(
                    label=f"Купить {role_name}",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"buy_{role_name}"
                )
                button.callback = await view.create_button_callback(role_name, price)
                view.add_item(button)

            embed.description = "\n".join(description_lines)
            await ctx.send(embed=embed, view=view)
        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при отображении магазина ролей: {e}")
            await ctx.send("❌ Не удалось загрузить магазин ролей.")
            
    # Автоматическое начисление коинов за время на сервере
    def credit_time_based_coins(user_id, stats):
        join_ts = stats.get("join_timestamp")
        if not join_ts:
            return 0

        credited_hours = stats.get("credited_hours", 0)
        total_hours = int((time.time() - join_ts) / 3600)
        delta_hours = total_hours - credited_hours

        if delta_hours <= 0:
            return 0

        reward = delta_hours * 6
        try:
            db.update_balance(user_id, reward)
            db.conn.execute("""
                UPDATE user_stats SET credited_hours = ? WHERE user_id = ?
            """, (total_hours, user_id))
            db.conn.commit()
        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при начислении пассивных коинов: {e}")
            return 0

        return reward
