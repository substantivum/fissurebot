import discord
from discord.ui import View, Button, Modal, TextInput
from discord import app_commands
from database import BotDatabase
from utils import logger
from discord.ext import commands  # Обязательно добавьте этот импорт
import os  # Needed for clear_downloads
import shutil
import re
import asyncio
import levels

LEVEL_UP_EXPERIENCE=100
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
    async def help_command(ctx):
        """Интерактивная справка по командам бота (без админ-раздела)"""
        
        # Структура категорий и команд
        categories = {
            "🎵 Музыка": [
                {"name": "play", "description": "Проиграть музыку из YouTube", "usage": "!play <ссылка или название>"},
                {"name": "queue", "description": "Показать текущую очередь треков", "usage": "!queue"},
                {"name": "skip", "description": "Пропустить текущий трек", "usage": "!skip"},
                {"name": "stop", "description": "Остановить воспроизведение и отключиться", "usage": "!stop"},
                {"name": "clearqueue", "description": "Очистить очередь", "usage": "!clearqueue"},
                {"name": "join", "description": "Подключить бота к голосовому каналу", "usage": "!join"},
                {"name": "leave", "description": "Отключить бота от канала", "usage": "!leave"},
                {"name": "volume", "description": "Установить громкость (0.0 - 1.0)", "usage": "!volume 0.5"},
                {"name": "nowplaying", "description": "Показать, что сейчас играет", "usage": "!nowplaying"}
            ],
            "💰 Экономика": [
                {"name": "balance", "description": "Проверить свой или чужой баланс монет", "usage": "!balance [пользователь]"},
                {"name": "fissdaily", "description": "Получить ежедневную награду", "usage": "!fissdaily"}

            ],
            "📊 Уровни и статистика": [
                {"name": "leaderboard", "description": "Посмотреть таблицу лидеров", "usage": "!leaderboard"},
                {"name": "stats", "description": "Показать личную статистику пользователя", "usage": "!stats"}
            ],
            "🎮 Развлечения": [
                {"name": "duel", "description": "Вызвать пользователя на дуэль с монетами", "usage": "!duel @пользователь 50"},
                {"name": "accept", "description": "Принять вызов на дуэль", "usage": "!accept"},
                {"name": "coinflip", "description": "Сыграть в орёл/решка за удвоение ставки", "usage": "!coinflip 100"}
            ]
        }

        class HelpSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label=category, description=f"Команды из раздела {category}", emoji="🔘")
                    for category in categories.keys()
                ]
                super().__init__(placeholder="Выбери категорию...", options=options)

            async def callback(self, interaction: discord.Interaction):
                selected_category = self.values[0]
                commands_list = categories[selected_category]

                embed = discord.Embed(
                    title=f"📘 Команды — {selected_category}",
                    color=0x1E90FF
                )

                for cmd in commands_list:
                    value_text = f"**Описание:** {cmd['description']}\n**Использование:** `{cmd['usage']}`"
                    embed.add_field(
                        name=f"🔸 {cmd['name']}",
                        value=value_text,
                        inline=False
                    )

                await interaction.response.edit_message(embed=embed)

        class HelpView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(HelpSelect())

        # Отправляем начальное сообщение с меню выбора
        embed = discord.Embed(
            title="🤖 Система помощи Fissure Bot",
            description="Выбери категорию ниже, чтобы посмотреть доступные команды.",
            color=0x1E90FF
        )
        message = await ctx.send(embed=embed, view=HelpView())
        
        await asyncio.sleep(60)
        await message.delete()


    @bot.command(name="adminpanel")
    @is_admin()
    async def admin_panel(ctx):
        # Create a view that will contain the buttons
        class AdminPanelView(View):
            def __init__(self):
                super().__init__(timeout=30)  # Set a timeout for the view to expire after 30 seconds
                self.invoker = ctx.author  # Store the invoker (the person who called the command)
                
                # Add buttons directly in __init__
                self.add_item(self.AddRoleButton())
                self.add_item(self.RemoveRoleButton())
                self.add_item(self.SetPriceButton())
                self.add_item(self.GiveCoinsButton())

            # Override the interaction_check method to allow only the invoker to interact with buttons
            async def interaction_check(self, interaction: discord.Interaction):
                # Check if the user interacting with the button is the one who invoked the command
                if interaction.user != self.invoker:
                    await interaction.response.send_message(
                        "❌ У вас нет доступа к этой панели.",
                        ephemeral=True
                    )
                    return False
                return True
            
            class GiveCoinsButton(Button):
                def __init__(self):
                    super().__init__(
                        label="Выдать монеты",
                        style=discord.ButtonStyle.primary
                    )
                
                async def callback(self, interaction: discord.Interaction):
                    class GiveCoinsModal(Modal, title="Выдать монеты пользователю"):
                        member = TextInput(label="Укажите пользователя (ID или @)", placeholder="Введите ID или упомяните пользователя")
                        amount = TextInput(label="Количество монет", placeholder="Введите количество монет")
                        
                        async def on_submit(self, interaction: discord.Interaction):
                            member_id_input = self.member.value
                            amount_to_give = int(self.amount.value)
                            
                            # Check if the input is a user mention (e.g., @user, @!user, <@user_id>, <@!user_id>)
                            match = re.match(r"<@!?(\d+)>", member_id_input)  # Check for <@user_id> or <@!user_id>
                            
                            if match:
                                # Extract the user ID from the mention string
                                member_id = match.group(1)
                            elif member_id_input.startswith("@"):
                                # Handle plain @username or @!username mentions
                                member_name = member_id_input.lstrip("@")  # Remove @
                                member = discord.utils.get(interaction.guild.members, name=member_name)
                                if member:
                                    member_id = str(member.id)
                                else:
                                    await interaction.response.send_message(
                                        "❌ Пользователь с таким именем не найден.",
                                        ephemeral=True
                                    )
                                    return
                            elif member_id_input.isdigit():
                                # If it's a number, it's directly the user ID
                                member_id = member_id_input
                            else:
                                await interaction.response.send_message(
                                    "❌ Неверный формат ID или упоминания пользователя.",
                                    ephemeral=True
                                )
                                return
                            
                            # Fetch the member using the user ID
                            member = await interaction.guild.fetch_member(int(member_id))
                            
                            # Update the balance (ensure this is implemented in your db.update_balance method)
                            db.update_balance(str(member.id), amount_to_give)
                            
                            await interaction.response.send_message(
                                f"✅ Выдано {amount_to_give} fissure coins пользователю {member.display_name}",
                                ephemeral=True
                            )
                            logger.info(f"Given {amount_to_give} coins to {member.display_name}")
                    
                    await interaction.response.send_modal(GiveCoinsModal())

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
                            logger.info("Added new role " + self.role_name.value)
                    
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
                    
        # Send the embed privately to the invoking user (in their DM)
        embed = discord.Embed(
            title="🔒 Админ-панель", 
            description="Доступ только для администраторов", 
            color=0x00ffcc
        )
        embed.add_field(
            name="🛠️ Доступные действия", 
            value="""Добавление ролей
            Удаление ролей
            Изменение цен
            Выдача монет
            Сброс данных !resetuser @user""", 
            inline=False
        )

        try:
            # Attempt to send the message in the user's DM
            await ctx.author.send(embed=embed, view=AdminPanelView())
            await ctx.send("✅ Панель администратора отправлена в ваш личный канал.", ephemeral=True)
        except discord.Forbidden:
            await ctx.send("❌ Не удалось отправить панель администратора в ваш личный канал.", ephemeral=True)




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
            
    @bot.command(name="giveexp")
    @is_admin()
    async def give_xp(ctx, member: str, xp_amount: int):
        """Команда для выдачи опыта пользователю (только для администраторов)."""
        
        # Ensure the XP amount is a valid positive number
        if xp_amount <= 0:
            await ctx.send("❌ Опыт должен быть положительным числом.")
            return
        
        # Try to convert the member argument into a valid discord member
        if member.startswith('<@') and member.endswith('>'):
            member_id = member[3:-1]  # Remove the <@ and >
        else:
            member_id = member
        
        # Fetch the member object using the ID
        try:
            member_obj = await ctx.guild.fetch_member(int(member_id))
        except (discord.NotFound, ValueError):
            await ctx.send("❌ Пользователь не найден. Убедитесь, что введен правильный ID или упоминание.")
            return
        
        user_id = str(member_obj.id)
        user_data = db.get_user(user_id)  # Fetch current user data
        
        if not user_data:
            db.create_user(user_id)  # If user doesn't exist, create a new entry
            user_data = db.get_user(user_id)
        
        current_exp = user_data["experience"]
        current_level = user_data["level"]
        
        # Add the xp to the user's current experience
        new_exp = current_exp + xp_amount
        leveled_up = False
        
        # Level-up logic: Check if the user exceeds the required XP for the next level
        while new_exp >= levels.get_required_exp(current_level):  # Use the exponential XP formula
            new_exp -= levels.get_required_exp(current_level)  # Subtract the experience for level-up
            current_level += 1  # Increase the level
            leveled_up = True

        # Update the database with the new experience and level
        db.update_level_and_exp(user_id, current_level, new_exp)
        
        # Send a message confirming the experience given
        await ctx.send(f"✅ Вы выдали {xp_amount} опыта пользователю {member_obj.display_name}.")
        
        # If the user leveled up, notify them
        if leveled_up:
            await ctx.send(f"🎉 {member_obj.display_name} повысил(а) уровень до **{current_level}**!")
        else:
            await ctx.send(f"📊 Текущий опыт пользователя {member_obj.display_name}: {new_exp} (Уровень {current_level})")