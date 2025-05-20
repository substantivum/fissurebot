import discord
from discord.ext import commands
import random

# Храним активные дуэли в памяти
pending_duels = {}

def setup(bot, db):
    @bot.command(name="duel")
    async def duel(ctx, opponent: discord.Member, bet: int):
        challenger_id = str(ctx.author.id)
        opponent_id = str(opponent.id)

        if opponent.bot or ctx.author == opponent:
            await ctx.send("❌ Нельзя вызвать самого себя или бота на дуэль.")
            return

        challenger_data = db.get_user(challenger_id)
        opponent_data = db.get_user(opponent_id)

        if challenger_data["experience"] < bet or opponent_data["experience"] < bet:
            await ctx.send("❌ У одного из игроков недостаточно опыта для ставки.")
            return

        if opponent_id in pending_duels:
            await ctx.send("⏳ У этого пользователя уже есть ожидающая дуэль.")
            return

        pending_duels[opponent_id] = {
            "challenger_id": challenger_id,
            "bet": bet,
            "channel_id": ctx.channel.id
        }

        await ctx.send(f"⚔️ {ctx.author.mention} вызвал {opponent.mention} на дуэль на **{bet}** опыта!\n"
                       f"{opponent.mention}, напиши `!accept` в течение 60 секунд, чтобы принять.")

    @bot.command(name="accept")
    async def accept(ctx):
        user_id = str(ctx.author.id)

        if user_id not in pending_duels:
            await ctx.send("❌ У тебя нет активных вызовов на дуэль.")
            return

        duel = pending_duels.pop(user_id)
        challenger_id = duel["challenger_id"]
        bet = duel["bet"]
        channel = bot.get_channel(duel["channel_id"])

        challenger_data = db.get_user(challenger_id)
        opponent_data = db.get_user(user_id)

        if challenger_data["experience"] < bet or opponent_data["experience"] < bet:
            await channel.send("❌ Один из участников больше не имеет нужного количества опыта.")
            return

        # Определяем победителя
        winner_id = random.choice([challenger_id, user_id])
        loser_id = challenger_id if winner_id == user_id else user_id

        db.update_experience(winner_id, bet)
        db.update_experience(loser_id, -bet)

        winner = await bot.fetch_user(int(winner_id))
        loser = await bot.fetch_user(int(loser_id))

        embed = discord.Embed(title="🏁 Результаты дуэли", color=0xFF5733)
        embed.add_field(name="🎯 Победитель", value=winner.display_name, inline=False)
        embed.add_field(name="💥 Проигравший", value=loser.display_name, inline=False)
        embed.add_field(name="💰 Ставка", value=f"{bet} опыта", inline=False)
        await channel.send(embed=embed)

    @bot.command()
    async def coinflip(ctx, amount: int):
        """50/50 шанс удвоить ставку"""
        user_id = str(ctx.author.id)
        user = db.get_user(user_id)

        if amount <= 0:
            await ctx.send("Ставка должна быть положительной.")
            return
        if user["balance"] < amount:
            await ctx.send("У тебя недостаточно баллов.")
            return

        result = random.choice(["win", "lose"])
        if result == "win":
            db.update_balance(user_id, amount)
            await ctx.send(f"🎉 Удача на твоей стороне! Ты выиграл {amount} баллов.")
        else:
            db.update_balance(user_id, -amount)
            await ctx.send(f"💀 Ты проиграл {amount} баллов. Удачи в следующий раз!")
