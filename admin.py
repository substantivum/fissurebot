# admin.py
import discord
from discord.ui import View, Button, Modal, TextInput
from database import BotDatabase
from utils import logger
from discord.ext import commands  # Обязательно добавьте этот импорт

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
    
    @bot.command(name="adminpanel")
    @is_admin()
    async def admin_panel(ctx):
        class AdminPanelView(View):
            def __init__(self):
                super().__init__(timeout=None)
                self.load_roles()

            def load_roles(self):
                cursor = db.conn.cursor()
                cursor.execute("SELECT role_name FROM role_shop")
                self.roles = cursor.fetchall()

            async def interaction_check(self, interaction: discord.Interaction):
                return not interaction.user.bot

            async def create_button_callback(self, role_name: str, price: int):
                async def button_callback(interaction: discord.Interaction):
                    user_id = str(interaction.user.id)
                    guild = interaction.guild
                    role = discord.utils.get(guild.roles, name=role_name)

                    if not role:
                        await interaction.response.send_message(f"❌ Роль `{role_name}` не найдена на сервере.", ephemeral=True)
                        return

                    if role in interaction.user.roles:
                        await interaction.response.send_message(f"❌ У вас уже есть роль `{role_name}`.", ephemeral=True)
                        return

                    cursor = db.conn.cursor()
                    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
                    result = cursor.fetchone()
                    balance = result[0] if result else 0

                    if balance < price:
                        await interaction.response.send_message(f"❌ Недостаточно средств для покупки `{role_name}`.", ephemeral=True)
                        return

                    db.update_balance(user_id, -price)
                    await interaction.user.add_roles(role)
                    await interaction.response.send_message(f"✅ Куплена роль `{role_name}` за {price} fissure coins!", ephemeral=True)

                return button_callback

        embed = discord.Embed(title="🔒 Админ-панель", description="Доступ только для администраторов", color=0x00ffcc)
        view = AdminPanelView()

        for role_name, price in view.roles:
            embed.add_field(name=role_name, value=f"{price} fissure coins", inline=False)

        for role_name, price in view.roles:
            button = Button(
                label=f"Купить {role_name}", 
                custom_id=f"buyrole_{role_name.lower()}", 
                style=discord.ButtonStyle.primary
            )
            button.callback = await view.create_button_callback(role_name, price)
            view.add_item(button)

        await ctx.send(embed=embed, view=view)

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