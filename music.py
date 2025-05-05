import utils
print(utils.__file__)
import os
import yt_dlp
import asyncio
import time
import discord
from discord import FFmpegPCMAudio
from utils import voice_clients, queues, current_playing, logger
from database import BotDatabase

def setup(bot, db):
    async def play_next(guild_id, ctx):
        guild_queues = queues.get(guild_id, [])
        guild_voice_client = voice_clients.get(guild_id)
        if not guild_queues or not guild_voice_client:
            current_playing[guild_id] = None
            return
        next_track = guild_queues.pop(0)
        filename, title = next_track['filename'], next_track['title']
        
        def after_playing(error):
            try:
                if os.path.exists(filename):
                    os.remove(filename)
                coro = play_next(guild_id, ctx)
                fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
                fut.result()
            except Exception as e:
                logger.error(f"Error during next play cleanup: {e}")
        
        current_playing[guild_id] = filename
        guild_voice_client.play(FFmpegPCMAudio(filename), after=after_playing)
        await ctx.send(f"🎶 Now playing: {title}")
    
    @bot.command(name="play")
    async def play(ctx, url):
        try:
            guild_id = ctx.guild.id
            if ctx.author.voice is None:
                await ctx.send("You need to join a voice channel first!")
                return
            
            channel = ctx.author.voice.channel
            guild_queues = queues.setdefault(guild_id, [])
            
            if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
                voice_clients[guild_id] = await channel.connect()
            elif voice_clients[guild_id].channel != channel:
                await voice_clients[guild_id].move_to(channel)
            
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
            
            guild_queues.append({'filename': filename, 'title': info.get('title', url)})
            await ctx.send(f"✅ Added to queue: {info.get('title', url)}")
            
            if not voice_clients[guild_id].is_playing() and guild_id not in current_playing:
                await play_next(guild_id, ctx)
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")
    
    @bot.command(name="queue")
    async def queue(ctx):
        guild_id = ctx.guild.id
        guild_queue = queues.get(guild_id, [])
        if not guild_queue:
            await ctx.send("❌ Queue is empty!")
        else:
            queue_list = "\n".join([f"{idx + 1}. {track['title']}" for idx, track in enumerate(guild_queue)])
            await ctx.send(f"🎶 Current queue:\n{queue_list}")
    
    @bot.command(name="skip")
    async def skip(ctx):
        guild_id = ctx.guild.id
        voice_client = voice_clients.get(guild_id)
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await ctx.send("⏭️ Skipped current track")
        else:
            await ctx.send("❌ No track is playing")
    
    @bot.command(name="stop")
    async def stop(ctx):
        guild_id = ctx.guild.id
        voice_client = voice_clients.get(guild_id)
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            queues[guild_id] = []
            current_playing[guild_id] = None
            await ctx.send("⏹️ Stopped playback and disconnected")
        else:
            await ctx.send("❌ Not connected to a voice channel")
    
    @bot.command(name="clearqueue")
    async def clear_queue(ctx):
        guild_id = ctx.guild.id
        if guild_id in queues:
            queues[guild_id] = []
            await ctx.send("🗑️ Queue cleared")
        else:
            await ctx.send("❌ Queue is already empty")
    
    @bot.command(name="join")
    async def join(ctx):
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            if ctx.voice_client:
                await ctx.voice_client.move_to(channel)
            else:
                voice_clients[channel.guild.id] = await channel.connect()
            await ctx.send(f"✅ Joined {channel.name}")
        else:
            await ctx.send("❌ You need to be in a voice channel")
    
    @bot.command(name="leave")
    async def leave(ctx):
        guild_id = ctx.guild.id
        if guild_id in voice_clients and voice_clients[guild_id].is_connected():
            await voice_clients[guild_id].disconnect()
            queues[guild_id] = []
            current_playing[guild_id] = None
            await ctx.send("🚪 Left voice channel")
        else:
            await ctx.send("❌ Not connected to a voice channel")
    
    @bot.command(name="volume")
    async def volume(ctx, volume: float):
        guild_id = ctx.guild.id
        if guild_id in voice_clients and voice_clients[guild_id].is_playing():
            voice_clients[guild_id].source = discord.PCMVolumeTransformer(voice_clients[guild_id].source)
            voice_clients[guild_id].source.volume = volume
            await ctx.send(f"🔊 Volume set to {volume*100}%")
        else:
            await ctx.send("❌ No audio is playing")
    
    @bot.command(name="nowplaying")
    async def now_playing(ctx):
        guild_id = ctx.guild.id
        if guild_id in current_playing and current_playing[guild_id]:
            await ctx.send(f"🎶 Now playing: {current_playing[guild_id]}")
        else:
            await ctx.send("❌ Nothing is playing right now")