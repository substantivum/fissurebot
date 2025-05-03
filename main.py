import os
import json
import random
import shutil
from typing import Final
from dotenv import load_dotenv
from discord import Intents, Client, Message, User, FFmpegPCMAudio
from discord.ext import commands
import yt_dlp
import discord
from discord.ui import View, Button

# === Экономика (управление балансами) ===
ECONOMY_FILE = "economy.json"

def load_economy():
    if not os.path.exists(ECONOMY_FILE):
        with open(ECONOMY_FILE, 'w') as f:
            json.dump({}, f)
    with open(ECONOMY_FILE, 'r') as f:
        return json.load(f)

def save_economy(data):
    with open(ECONOMY_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_balance(user_id: str) -> int:
    data = load_economy()
    return data.get(user_id, 0)

def change_balance(user_id: str, amount: int):
    data = load_economy()
    data[user_id] = data.get(user_id, 0) + amount
    if data[user_id] < 0:
        data[user_id] = 0
    save_economy(data)

def set_balance(user_id: str, amount: int):
    data = load_economy()
    data[user_id] = max(amount, 0)
    save_economy(data)

# === Магазин ролей ===
ROLE_SHOP = {
    "VIP": 500,
    "Legend": 1000,
    "Champion": 2000
}

# === Бот ===
load_dotenv()
TOKEN: Final[str] = os.getenv("DISCORD_TOKEN")
print(TOKEN)

intents: Intents = Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

if not os.path.exists('downloads'):
    os.makedirs('downloads')

current_playing = None
voice_channel = None

# Переменная для состояния магазина
shop_open = True

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

@bot.command(name="play")
async def play(ctx, url):
    global current_playing, voice_channel

    try:
        if ctx.author.voice is None:
            await ctx.send("You need to join a voice channel first!")
            return

        channel = ctx.author.voice.channel
        if voice_channel and voice_channel.is_connected():
            await ctx.send("I am already in a voice channel!")
            return

        voice_channel = await channel.connect()

        os.makedirs("downloads", exist_ok=True)

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            filename = os.path.splitext(filename)[0] + ".mp3"

        def after_playing(error):
            global current_playing
            try:
                if os.path.exists(filename):
                    os.remove(filename)
                if voice_channel.is_playing():
                    voice_channel.stop()
                coro = voice_channel.disconnect()
                fut = discord.utils.asyncio.run_coroutine_threadsafe(coro, bot.loop)
                fut.result()
            except Exception as e:
                print(f"Error during cleanup: {e}")
            current_playing = None

        current_playing = filename
        voice_channel.play(FFmpegPCMAudio(filename), after=after_playing)

        await ctx.send(f"Now playing: {info.get('title', url)}")

    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

@bot.command(name="stop")
async def stop(ctx):
    try:
        voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        if voice_channel and voice_channel.is_playing():
            voice_channel.stop()
            await voice_channel.disconnect()
            await ctx.send("Music stopped and disconnected from the voice channel.")
        else:
            await ctx.send("No music is currently playing.")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

@bot.command(name="skip")
async def skip(ctx):
    global current_playing, voice_channel

    if current_playing is None:
        await ctx.send("No music is currently playing!")
        return

    if voice_channel and voice_channel.is_playing():
        voice_channel.stop()
        current_playing = None
        await ctx.send("Skipped the current song!")
    else:
        await ctx.send("No music is playing currently.")

@bot.command(name="join")
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Connected to {channel.name}")
    else:
        await ctx.send("You need to join a voice channel first!")

@bot.command(name="leave")
async def leave(ctx):
    voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_channel:
        await voice_channel.disconnect()
        await ctx.send("Disconnected from the voice channel.")
    else:
        await ctx.send("I am not connected to any voice channel.")

@bot.command(name="volume")
async def volume(ctx, volume: float):
    if 0.0 <= volume <= 2.0:
        voice_channel = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        if voice_channel:
            voice_channel.source = discord.PCMVolumeTransformer(voice_channel.source, volume)
            await ctx.send(f"Volume set to {volume * 100}%")
        else:
            await ctx.send("Not connected to a voice channel.")
    else:
        await ctx.send("Please enter a volume between 0.0 and 2.0.")

@bot.command(name="clear_downloads")
async def clear_downloads(ctx):
    downloads_folder = 'downloads'
    try:
        if os.path.exists(downloads_folder):
            shutil.rmtree(downloads_folder)
            os.makedirs(downloads_folder)
            await ctx.send("🧹 Downloads folder cleared successfully!")
        else:
            await ctx.send("Downloads folder does not exist.")
    except Exception as e:
        await ctx.send(f"An error occurred while clearing downloads: {str(e)}")

@bot.command(name="shutdown")
async def shutdown(ctx):
    YOUR_DISCORD_USER_ID = 241263515283750913
    if ctx.author.id == YOUR_DISCORD_USER_ID:
        await ctx.send("Shutting down...")
        await bot.close()
    else:
        await ctx.send("You do not have permission to shut down the bot.")

@bot.command(name="roleshop")
async def roleshop(ctx):
    embed = discord.Embed(title="🎖️ Role Shop", description="Click a button to buy a role!", color=0x00ff00)
    for role_name, price in ROLE_SHOP.items():
        embed.add_field(name=role_name, value=f"{price} fissure coins", inline=False)

    class RoleShopView(View):
        def __init__(self):
            super().__init__(timeout=None)
            for role_name, price in ROLE_SHOP.items():
                custom_id = f"buyrole_{role_name.lower()}"

                button = Button(label=f"Buy {role_name}", custom_id=custom_id, style=discord.ButtonStyle.primary)

                async def button_callback(interaction: discord.Interaction, role_name=role_name):
                    user_id = str(interaction.user.id)
                    balance = get_balance(user_id)
                    price = ROLE_SHOP[role_name]
                    guild = interaction.guild
                    role = discord.utils.get(guild.roles, name=role_name)

                    if role is None:
                        await interaction.response.send_message(f"❌ Role `{role_name}` does not exist on this server.", ephemeral=True)
                        return

                    if role in interaction.user.roles:
                        await interaction.response.send_message(f"❌ You already have the `{role_name}` role!", ephemeral=True)
                        return

                    if balance < price:
                        await interaction.response.send_message(f"❌ You don't have enough fissure coins to buy `{role_name}` role!", ephemeral=True)
                        return

                    change_balance(user_id, -price)
                    await interaction.user.add_roles(role)
                    await interaction.response.send_message(f"✅ You bought and received the `{role_name}` role!", ephemeral=True)

                button.callback = button_callback
                self.add_item(button)

            # Добавляем кнопку для администраторов для закрытия и открытия магазина
            self.admin_button = Button(label="Toggle Shop", style=discord.ButtonStyle.secondary)

            async def admin_button_callback(interaction: discord.Interaction):
                """Переключение состояния магазина (открыт/закрыт). Доступно только админам."""
                if interaction.user.guild_permissions.administrator:
                    global shop_open
                    shop_open = not shop_open
                    status = "opened" if shop_open else "closed"
                    await interaction.response.send_message(f"✅ The shop has been {status}.", ephemeral=True)

                    # Обновляем кнопки покупки
                    for button in self.children:
                        if isinstance(button, Button) and button.custom_id.startswith("buyrole"):
                            button.disabled = not shop_open

                    await interaction.message.edit(view=self)  # Обновляем view
                else:
                    await interaction.response.send_message("❌ You do not have permission to toggle the shop.", ephemeral=True)

            self.admin_button.callback = admin_button_callback
            self.add_item(self.admin_button)

    view = RoleShopView()

    # Если магазин закрыт, отключаем кнопки покупки
    if not shop_open:
        for button in view.children:
            if isinstance(button, Button) and button.custom_id.startswith("buyrole"):
                button.disabled = True

    await ctx.send(embed=embed, view=view)

@bot.command(name="bothelp")
async def bothelp_command(ctx):
    help_message = """
    **Музыкальные команды:**
    - `!play <url>`: Воспроизвести песню с YouTube.
    - `!stop`: Остановить текущую песню и отключиться.
    - `!skip`: Пропустить текущую песню.
    - `!join`: Присоединиться к голосовому каналу.
    - `!leave`: Покинуть голосовой канал.
    - `!volume <0.0-2.0>`: Установить громкость воспроизведения.

    **Экономика:**
    - `!balance`: Проверить баланс фишевых монет.
    - `!earn`: Заработать случайное количество монет.
    - `!pay @user amount`: Перевести монеты другому пользователю.

    **Магазин ролей:**
    - `!roleshop`: Посмотреть доступные роли.

    **Админ-команды:**
    - `!shutdown`: Выключить бота.
    - `!clear_downloads`: Очистить загрузки.
    """
    await ctx.send(help_message)

def main() -> None:
    bot.run(TOKEN)

if __name__ == '__main__':
    main()
