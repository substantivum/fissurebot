# admin.py
import discord
from discord.ui import View, Button, Modal, TextInput
from database import BotDatabase
from utils import logger
from discord.ext import commands  # Обязательно добавьте этот импорт
import os  # Needed for clear_downloads
import shutil

def is_admin():
    """Проверка прав администратора"""
    async def predicate(ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ У вас нет прав администратора для использования этой команды.")
            return False
        return True
    return commands.check(predicate)

def setup(bot, db):
    """Регистрация админ-команд бота"""
    bot.remove_command('help')
    
    @bot.command(name="bothelp")
    async def bothelp_command(ctx):
        help_message = """
        **Музыкальные команды:**
        - `!play <url>`: Проиграть песню с YouTube
        - `!queue`: Показать очередь
        - `!skip`: Пропустить песню
        - `!clearqueue`: Очистить очередь
        - `!shufflequeue`: Перемешать очередь
        - `!stop`: Остановить музыку
        - `!join`: Подключиться к голосу
        - `!leave`: Покинуть голосовой канал
        - `!volume <0.0-2.0>`: Изменить громкость
        - `!nowplaying`: Текущая песня

        **Экономика:**
        - `!balance`: Проверить баланс
        - `!fissdaily`: Получить ежедневную награду
        - `!pay @user amount`: Передать монеты
        - `!leaderboard`: Посмотреть таблицу лидеров

        **Статистика:**
        - `!level`: Проверить уровень и опыт
        - `!activity`: Статистика активности
        - `!topactivity`: Топ по активности

        **Магазин ролей:**
        - `!roleshop`: Посмотреть доступные роли

        **Админ-команды:**
        - `!adminpanel`: Открыть админ-панель
        - `!addrole <name> <price>`: Добавить роль в магазин
        - `!removerole <name>`: Удалить роль из магазина
        - `!setprice <name> <price>`: Изменить цену роли
        - `!givecoins @user <amount>`: Выдать монеты
        - `!resetuser @user`: Сбросить данные пользователя
        - `!broadcast <message>`: Отправить сообщение всем серверам
        - `!cleardb`: Очистить всю базу
        - `!shutdown`: Выключить бота
        - `!clear_downloads`: Очистить загрузки
        """
        await ctx.send(help_message)

    
    @bot.command(name="adminpanel")
    @is_admin()
    async def admin_panel(ctx):
        class AdminPanelView(View):
            def __init__(self):
                super().__init__(timeout=None)
                
                # Add buttons directly in __init__
                self.add_item(self.AddRoleButton())
                self.add_item(self.RemoveRoleButton())
                self.add_item(self.SetPriceButton())
            
            class AddRoleButton(Button):
                def __init__(self):
                    super().__init__(
                        label="Добавить роль",
                        style=discord.ButtonStyle.primary
                    )
                
                async def callback(self, interaction: discord.Interaction):
                    class AddRoleModal(Modal, title="Добавить роль в магазин"):
                        role_name = TextInput(label="Название роли")
                        role_price = TextInput(label="Цена", placeholder="Введите цену в fissure coins")
                        
                        async def on_submit(self, interaction: discord.Interaction):
                            cursor = db.conn.cursor()
                            cursor.execute("INSERT OR IGNORE INTO role_shop (role_name, price) VALUES (?, ?)", 
                                        (self.role_name.value, int(self.role_price.value)))
                            db.conn.commit()
                            await interaction.response.send_message(
                                f"✅ Роль `{self.role_name.value}` добавлена за {self.role_price.value} fissure coins", 
                                ephemeral=True
                            )
                    
                    await interaction.response.send_modal(AddRoleModal())
            
            class RemoveRoleButton(Button):
                def __init__(self):
                    super().__init__(
                        label="Удалить роль",
                        style=discord.ButtonStyle.danger
                    )
                
                async def callback(self, interaction: discord.Interaction):
                    class RemoveRoleSelect(discord.ui.Select):
                        def __init__(self):
                            cursor = db.conn.cursor()
                            cursor.execute("SELECT role_name FROM role_shop")
                            roles = cursor.fetchall()
                            options = [discord.SelectOption(label=role[0]) for role in roles]
                            super().__init__(placeholder="Выберите роль для удаления", options=options)
                        
                        async def callback(self, interaction: discord.Interaction):
                            role_name = self.values[0]
                            cursor = db.conn.cursor()
                            cursor.execute("DELETE FROM role_shop WHERE role_name=?", (role_name,))
                            db.conn.commit()
                            await interaction.response.send_message(
                                f"✅ Роль `{role_name}` удалена из магазина", 
                                ephemeral=True
                            )
                    
                    view = View()
                    view.add_item(RemoveRoleSelect())
                    await interaction.response.send_message(
                        "🗑️ Выберите роль для удаления:", 
                        view=view, 
                        ephemeral=True
                    )
            
            class SetPriceButton(Button):
                def __init__(self):
                    super().__init__(
                        label="Изменить цену",
                        style=discord.ButtonStyle.secondary
                    )
                
                async def callback(self, interaction: discord.Interaction):
                    class SetPriceModal(Modal, title="Изменить цену роли"):
                        role_name = TextInput(label="Название роли")
                        new_price = TextInput(label="Новая цена")
                        
                        async def on_submit(self, interaction: discord.Interaction):
                            cursor = db.conn.cursor()
                            cursor.execute("UPDATE role_shop SET price=? WHERE role_name=?", 
                                        (int(self.new_price.value), self.role_name.value))
                            db.conn.commit()
                            await interaction.response.send_message(
                                f"✅ Цена роли `{self.role_name.value}` изменена на {self.new_price.value} fissure coins", 
                                ephemeral=True
                            )
                    
                    await interaction.response.send_modal(SetPriceModal())

        embed = discord.Embed(
            title="🔒 Админ-панель", 
            description="Доступ только для администраторов", 
            color=0x00ffcc
        )
        embed.add_field(
            name="🛠️ Доступные действия", 
            value="""
            - Добавление ролей
            - Удаление ролей
            - Изменение цен
            - Выдача монет
            - Сброс данных
            - Отправка объявления
            - Очистка базы данных
            """, 
            inline=False
        )
        
        await ctx.send(embed=embed, view=AdminPanelView())

    @bot.command(name="addrole")
    @is_admin()
    async def add_role(ctx, role_name: str, price: int):
        cursor = db.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO role_shop (role_name, price) VALUES (?, ?)", (role_name, price))
        db.conn.commit()
        await ctx.send(f"✅ Роль `{role_name}` добавлена за {price} fissure coins")

    @bot.command(name="removerole")
    @is_admin()
    async def remove_role(ctx, role_name: str):
        cursor = db.conn.cursor()
        cursor.execute("DELETE FROM role_shop WHERE role_name=?", (role_name,))
        db.conn.commit()
        await ctx.send(f"✅ Роль `{role_name}` удалена из магазина")

    @bot.command(name="setprice")
    @is_admin()
    async def set_price(ctx, role_name: str, price: int):
        cursor = db.conn.cursor()
        cursor.execute("UPDATE role_shop SET price=? WHERE role_name=?", (price, role_name))
        db.conn.commit()
        await ctx.send(f"✅ Цена роли `{role_name}` изменена на {price} fissure coins")

    @bot.command(name="givecoins")
    @is_admin()
    async def give_coins(ctx, member: discord.Member, amount: int):
        user_id = str(member.id)
        db.update_balance(user_id, amount)
        await ctx.send(f"✅ Выдано {amount} fissure coins пользователю {member.display_name}")

    @bot.command(name="resetuser")
    @is_admin()
    async def reset_user(ctx, member: discord.Member):
        user_id = str(member.id)
        cursor = db.conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        cursor.execute("DELETE FROM user_stats WHERE user_id=?", (user_id,))
        db.conn.commit()
        await ctx.send(f"✅ Данные пользователя {member.display_name} сброшены")

    @bot.command(name="broadcast")
    @is_admin()
    async def broadcast(ctx, *, message: str):
        for guild in bot.guilds:
            try:
                general = discord.utils.find(lambda x: x.name == 'general', guild.text_channels)
                if general:
                    await general.send(f"📢 **Сообщение от админа:**\n{message}")
            except Exception as e:
                logger.error(f"Ошибка при отправке в {guild.name}: {e}")
        await ctx.send("✅ Сообщение отправлено всем серверам")

    @bot.command(name="cleardb")
    @is_admin()
    async def clear_db(ctx):
        cursor = db.conn.cursor()
        cursor.execute("DELETE FROM users")
        cursor.execute("DELETE FROM user_stats")
        cursor.execute("DELETE FROM emoji_usage")
        cursor.execute("DELETE FROM role_shop")
        db.conn.commit()
        await ctx.send("✅ База данных очищена")

    @bot.command(name="shutdown")
    @is_admin()
    async def shutdown(ctx):
        await ctx.send("🛑 Выключаю бота...")
        await bot.close()

    @bot.command(name="clear_downloads")
    @is_admin()
    async def clear_downloads(ctx):
        try:
            import shutil
            if os.path.exists('downloads'):
                shutil.rmtree('downloads')
            os.makedirs('downloads', exist_ok=True)
            await ctx.send("🗑️ Папка загрузок очищена!")
        except Exception as e:
            await ctx.send(f"❌ Ошибка при очистке: {str(e)}")