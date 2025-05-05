# economy.py
import discord
from discord.ui import View, Button
from database import BotDatabase
from utils import logger, DAILY_COOLDOWN

def setup(bot, db):
    @bot.command(name="fissdaily")
    async def fissdaily(ctx):
        user_id = str(ctx.author.id)
        user_data = db.get_user(user_id)
        stats = db.get_user_stats(user_id)
        last_daily = stats["last_daily"]
        
        if time.time() - last_daily < DAILY_COOLDOWN:
            remaining = int(DAILY_COOLDOWN - (time.time() - last_daily))
            hours, remainder = divmod(remaining, 3600)
            minutes, seconds = divmod(remainder, 60)
            await ctx.send(f"⏳ You can claim daily reward in {hours}h {minutes}m {seconds}s")
            return
        
        amount = random.randint(10, 50)
        streak = stats["daily_streak"]
        
        if time.time() - last_daily < DAILY_COOLDOWN * 2:
            streak += 1
        else:
            streak = 1
        
        bonus = min(streak * 5, 100)
        total = amount + bonus
        
        db.update_balance(user_id, total)
        db.conn.execute("""
            UPDATE user_stats
            SET last_daily = ?, daily_streak = ?
            WHERE user_id = ?
        """, (time.time(), streak, user_id))
        db.conn.commit()
        
        await ctx.send(f"🎉 Earned {amount} fissure coins (streak: {streak} days) + {bonus} bonus = **{total} fissure coins**!\nYour balance: {user_data['balance'] + total}")

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
        cursor = db.conn.cursor()
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        balance = result[0] if result else 0
        await ctx.send(f"💰 {target.display_name} has {balance} fissure coins")

    @bot.command(name="leaderboard")
    async def leaderboard(ctx, top_n: int = 10):
        cursor = db.conn.cursor()
        cursor.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT ?", (top_n,))
        top_users = cursor.fetchall()
        if not top_users:
            await ctx.send("❌ No balance data found.")
            return
        
        embed = discord.Embed(title="💰 Leaderboard", color=0xFFD700)
        for idx, (user_id, balance) in enumerate(top_users, 1):
            try:
                user = await bot.fetch_user(int(user_id))
                embed.add_field(
                    name=f"{idx}. {user.display_name}",
                    value=f"{balance} fissure coins",
                    inline=False
                )
            except Exception as e:
                logger.error(f"Error fetching user {user_id}: {e}")
        
        await ctx.send(embed=embed)

    @bot.command(name="level")
    async def level(ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        stats = db.get_user_stats(user_id)
        user_data = db.get_user(user_id)
        embed = discord.Embed(title=f"📊 Level {target.display_name}", color=0x00ffcc)
        embed.add_field(name="🏆 Level", value=str(user_data["level"]), inline=False)
        embed.add_field(name="✨ Experience", value=f"{user_data['experience']} / {user_data['level'] * 100}", inline=False)
        embed.add_field(name="💬 Messages", value=str(stats["messages"]), inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="activity")
    async def activity(ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        stats = db.get_user_stats(user_id)
        user_data = db.get_user(user_id)
        embed = discord.Embed(title=f"📈 Activity {target.display_name}", color=0x00ffcc)
        total_time = time.time() - stats["joined_at"]
        days, remainder = divmod(total_time, 86400)
        hours, remainder = divmod(remainder, 3600)
        embed.add_field(name="🕒 Time on server", value=f"{days}d {hours}h", inline=False)
        embed.add_field(name="✉️ Messages", value=str(stats["messages"]), inline=False)
        embed.add_field(name="✨ Experience", value=str(user_data["experience"]), inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="topactivity")
    async def top_activity(ctx, top_n: int = 10):
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT u.user_id, u.experience, s.messages
            FROM users u
            LEFT JOIN user_stats s ON u.user_id = s.user_id
            ORDER BY u.experience + s.messages DESC
            LIMIT ?
        """, (top_n,))
        top_users = cursor.fetchall()
        if not top_users:
            await ctx.send("❌ No activity data found.")
            return
        
        embed = discord.Embed(title="🏆 Top by activity", color=0xFFD700)
        for idx, (user_id, experience, messages) in enumerate(top_users, 1):
            try:
                user = await bot.fetch_user(int(user_id))
                total_activity = experience + (messages if messages else 0)
                embed.add_field(
                    name=f"{idx}. {user.display_name}",
                    value=f"Activity: {total_activity} (exp: {experience}, messages: {messages})",
                    inline=False
                )
            except Exception as e:
                logger.error(f"Error fetching user {user_id}: {e}")
        
        await ctx.send(embed=embed)