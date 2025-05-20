# economy.py
import discord
from discord.ui import View, Button
from database import BotDatabase
from utils import logger, DAILY_COOLDOWN
import random
import time
from datetime import datetime 

def setup(bot, db):
    
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
            
            # Начисляем опыт за сообщения
            exp_gain = random.randint(5, 15)
            try:
                db.conn.execute("""
                    UPDATE users SET experience = experience + ? WHERE user_id = ?
                """, (exp_gain, user_id))
                db.conn.commit()
            except sqlite3.Error as e:
                print(f"[ERROR] Ошибка при начислении опыта: {e}")
            
            # Проверка повышения уровня
            try:
                user = db.get_user(user_id)
                exp_needed = user['level'] * 100
                if user['experience'] >= exp_needed:
                    db.conn.execute("""
                        UPDATE users 
                        SET level = level + 1, experience = experience - ?
                        WHERE user_id = ?
                    """, (exp_needed, user_id))
                    db.conn.commit()
                    await message.channel.send(f"🎉 {message.author.mention} достиг уровня {user['level'] + 1}!")
            except sqlite3.Error as e:
                print(f"[ERROR] Ошибка при повышении уровня: {e}")
        
        await bot.process_commands(message)
    
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
        
        amount = random.randint(10, 50)
        streak = stats["daily_streak"] or 0
        if time.time() - last_daily < DAILY_COOLDOWN * 2:
            streak += 1
        else:
            streak = 1
        
        bonus = min(streak * 5, 100)
        total = amount + bonus

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
            f"🎉 Вы получили {amount} монет (серия: {streak} дней) + {bonus} бонус = **{total} монет**!\n"
            f"Ваш баланс: {user_data['balance'] + total}"
        )
    
    @bot.command(name="help")
    async def bothelp_command(ctx):
        embed = discord.Embed(
            title="📚 Список команд бота",
            description="Все доступные команды разделены по категориям",
            color=0x00ffcc
        )

        # Music Commands
        embed.add_field(
            name="🎵 Музыкальные команды",
            value="""
            `!play <url>` - Проиграть песню с YouTube
            `!queue` - Показать очередь
            `!skip` - Пропустить песню
            `!clearqueue` - Очистить очередь
            `!shufflequeue` - Перемешать очередь
            `!stop` - Остановить музыку
            `!join` - Подключиться к голосу
            `!leave` - Покинуть голосовой канал
            `!volume <0.0-2.0>` - Изменить громкость
            `!nowplaying` - Текущая песня
            """,
            inline=False
        )

        # Economy Commands
        embed.add_field(
            name="💰 Экономика",
            value="""
            `!balance` - Проверить баланс
            `!fissdaily` - Получить ежедневную награду
            `!pay @user amount` - Передать монеты
            `!leaderboard` - Таблица лидеров
            """,
            inline=False
        )

        # Statistics Commands
        embed.add_field(
            name="📊 Статистика",
            value="""
            `!level` - Проверить уровень и опыт
            `!activity` - Статистика активности
            `!topactivity` - Топ по активности
            """,
            inline=False
        )

        # Role Shop Commands
        embed.add_field(
            name="🎖️ Магазин ролей",
            value="`!roleshop` - Посмотреть доступные роли",
            inline=False
        )

        # Admin Commands
        if ctx.author.guild_permissions.administrator:
            embed.add_field(
                name="🔒 Админ-команды",
                value="""
                `!adminpanel` - Открыть админ-панель
                `!addrole <name> <price>` - Добавить роль
                `!removerole <name>` - Удалить роль
                `!setprice <name> <price>` - Изменить цену
                `!givecoins @user <amount>` - Выдать монеты
                `!resetuser @user` - Сбросить данные
                `!broadcast <message>` - Объявление
                `!cleardb` - Очистить базу
                `!shutdown` - Выключить бота
                `!clear_downloads` - Очистить загрузки
                """,
                inline=False
            )
        
        embed.set_footer(text=f"Запрошено {ctx.author.display_name}", icon_url=ctx.author.avatar.url)
        
        await ctx.send(embed=embed)
    
    @bot.command(name="roleshop")
    async def roleshop(ctx):
        class RoleShopView(View):
            def __init__(self):
                super().__init__(timeout=None)
                self.load_roles()

            def load_roles(self):
                cursor = db.conn.cursor()
                cursor.execute("SELECT role_name, price FROM role_shop")
                self.roles = cursor.fetchall()

            async def interaction_check(self, interaction: discord.Interaction):
                return not interaction.user.bot

            async def create_button_callback(self, role_name: str, price: int):
                async def button_callback(interaction: discord.Interaction):
                    user_id = str(interaction.user.id)
                    guild = interaction.guild
                    role = discord.utils.get(guild.roles, name=role_name)
                    
                    if not role:
                        await interaction.response.send_message(f"❌ Role `{role_name}` not found on this server.", ephemeral=True)
                        return
                    
                    if role in interaction.user.roles:
                        await interaction.response.send_message(f"❌ You already have the `{role_name}` role.", ephemeral=True)
                        return
                    
                    cursor = db.conn.cursor()
                    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
                    result = cursor.fetchone()
                    balance = result[0] if result else 0
                    
                    if balance < price:
                        await interaction.response.send_message(f"❌ Not enough coins to buy `{role_name}`.", ephemeral=True)
                        return
                    
                    db.update_balance(user_id, -price)
                    await interaction.user.add_roles(role)
                    await interaction.response.send_message(f"✅ Bought `{role_name}` for {price} fissure coins!", ephemeral=True)
                
                return button_callback

        embed = discord.Embed(title="🎖️ Role Shop", description="Select a role to purchase", color=0x00ff00)
        view = RoleShopView()
        
        for role_name, price in view.roles:
            embed.add_field(name=role_name, value=f"{price} fissure coins", inline=False)
        
        for role_name, price in view.roles:
            button = Button(
                label=f"Buy {role_name}", 
                custom_id=f"buyrole_{role_name.lower()}", 
                style=discord.ButtonStyle.primary
            )
            button.callback = await view.create_button_callback(role_name, price)
            view.add_item(button)
        
        await ctx.send(embed=embed, view=view)

    @bot.command(name="balance")
    async def balance(ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        user = db.get_user(user_id)
        
        if not user:
            db.create_user(user_id)
            user = db.get_user(user_id)
        
        await ctx.send(f"💰 {target.display_name} имеет {user['balance']} монет")
    
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

            # Get level/exp leaderboard
            cursor.execute("""
                SELECT user_id, level, experience 
                FROM users 
                ORDER BY level DESC, experience DESC 
                LIMIT ?
            """, (top_n,))
            level_top = cursor.fetchall()

            if not money_top and not level_top:
                await ctx.send("❌ Нет данных для таблицы лидеров.")
                return

            embed = discord.Embed(title="🏆 Таблица лидеров", color=0xFFD700)
            
            # Add money leaderboard if data exists
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

            # Add level leaderboard if data exists
            if level_top:
                level_desc = []
                for idx, (user_id, level, exp) in enumerate(level_top, 1):
                    try:
                        user = await bot.fetch_user(int(user_id))
                        level_desc.append(f"{idx}. {user.display_name} — Ур. {level} (Опыт: {exp})")
                    except Exception:
                        level_desc.append(f"{idx}. [Неизвестный] — Ур. {level} (Опыт: {exp})")
                
                embed.add_field(
                    name="🏅 Самые опытные игроки",
                    value="\n".join(level_desc),
                    inline=False
                )

            embed.set_footer(text=f"Показано топ-{top_n} игроков в каждой категории")
            await ctx.send(embed=embed)

        except sqlite3.Error as e:
            print(f"[ОШИБКА БД] Ошибка таблицы лидеров: {e}")
            await ctx.send("❌ Произошла ошибка при получении данных из базы.")
        except Exception as e:
            print(f"[ОШИБКА] Непредвиденная ошибка: {e}")
            await ctx.send("❌ Произошла непредвиденная ошибка.")
    
    @bot.command(name="mystats")
    async def mystats(ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        
        # Initialize user if not exists
        if not db.get_user(user_id):
            db.create_user(user_id)
        
        # Get all statistics
        top_emojis = db.get_top_emojis(user_id)
        top_words = db.get_top_words(user_id)
        voice_seconds = db.get_voice_time(user_id)
        stats = db.get_user_stats(user_id)
        user = db.get_user(user_id)
        level_info = db.get_level(user_id)  # Get level info
        
        # Format voice time
        hours, remainder = divmod(voice_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        voice_time_str = f"{int(hours)}ч {int(minutes)}м {int(seconds)}с"
        
        # Create embed
        embed = discord.Embed(
            title=f"📊 Статистика {target.display_name}",
            color=0x00ffcc
        )
        
        # Basic info
        embed.add_field(name="🏆 Уровень", value=str(level_info["level"]), inline=True)
        embed.add_field(
            name="✨ Опыт", 
            value=f"{level_info['experience']}/{level_info['next_level_exp']}", 
            inline=True
        )
        embed.add_field(name="💰 Баланс", value=f"{user['balance']} монет", inline=True)
        
        # Activity
        embed.add_field(name="💬 Сообщений", value=str(stats["messages"]), inline=True)
        embed.add_field(name="🎤 Время в голосе", value=voice_time_str, inline=True)
        
        # Top emojis
        if top_emojis:
            emoji_text = "\n".join([f"{emoji}: {count} раз" for emoji, count in top_emojis])
            embed.add_field(name="❤️ Топ эмодзи", value=emoji_text, inline=False)
        else:
            embed.add_field(name="❤️ Топ эмодзи", value="Нет данных", inline=False)
        
        # Top words (filter words used more than 3 times)
        if top_words:
            filtered_words = [(word, count) for word, count in top_words if count > 3]
            if filtered_words:
                words_text = "\n".join([f"'{word}': {count} раз" for word, count in filtered_words])
                embed.add_field(name="📝 Топ слов", value=words_text, inline=False)
            else:
                embed.add_field(name="📝 Топ слов", value="Нет слов, которые были сказаны более 3 раз", inline=False)
        else:
            embed.add_field(name="📝 Топ слов", value="Нет данных", inline=False)
        
        embed.set_thumbnail(url=target.avatar.url)
        await ctx.send(embed=embed)

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
                embed.description = "В магазине пока нет ролей"
                await ctx.send(embed=embed)
                return
            
            for role_name, price in roles:
                embed.add_field(name=role_name, value=f"{price} монет", inline=False)
                button = Button(
                    label=f"Купить {role_name}", 
                    style=discord.ButtonStyle.primary,
                    custom_id=f"buy_{role_name}"
                )
                button.callback = await view.create_button_callback(role_name, price)
                view.add_item(button)
            
            await ctx.send(embed=embed, view=view)
        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при отображении магазина ролей: {e}")
            await ctx.send("❌ Не удалось загрузить магазин ролей.")
