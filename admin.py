import discord
from discord.ui import View, Button, Modal, TextInput
from database import BotDatabase
from utils import logger
from discord.ext import commands  # Обязательно добавьте этот импорт
import os  # Needed for clear_downloads
import shutil
import re

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
        """Отображает список доступных команд с описаниями"""
        embed = discord.Embed(
            title="📘 Справка по командам Fissure Bot",
            description="Доступные функции и их использование",
            color=0x1E90FF
        )
        
        # Добавляем команды вручную для точного контроля порядка и описания
        commands_info = [
            {
                "name": "fissdaily",
                "description": "Получить ежедневную награду в монетах",
                "usage": "!fissdaily"
            },
            {
                "name": "balance",
                "description": "Проверить текущий баланс монет",
                "usage": "!balance [пользователь]"
            },
            {
                "name": "leaderboard",
                "description": "Посмотреть таблицу лидеров по балансу",
                "usage": "!leaderboard"
            },
            {
                "name": "mystats",
                "description": "Показать личную статистику пользователя",
                "usage": "!mystats [пользователь]"
            },
            {
                "name": "roleshop",
                "description": "Посмотреть и купить роли в магазине",
                "usage": "!roleshop"
            }
        ]

        for cmd in commands_info:
            embed.add_field(
                name=f"🔸 {cmd['name']}",
                value=f"**Описание:** {cmd['description']}\n**Использование:** `{cmd['usage']}`",
                inline=False
            )

        # Добавляем дополнительные сведения
        embed.add_field(
            name="🎯 Уровни и опыт",
            value="За каждое сообщение вы получаете опыт, который повышает ваш уровень",
            inline=False
        )
        embed.add_field(
            name="💬 Статистика",
            value="Бот отслеживает ваши сообщения, любимые эмодзи и часто используемые слова",
            inline=False
        )

        await ctx.send(embed=embed)


    
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