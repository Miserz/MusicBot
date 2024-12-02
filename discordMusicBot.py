import os
import asyncio
import random
import re
import urllib.parse
import urllib.request
from discord.ext import commands
from discord import app_commands
from bs4 import BeautifulSoup
import yt_dlp
import requests
import discord

# Импорты для пресетов (ожидается, что presetMessage содержит предустановленные сообщения)
from presetMessage import *


class MusicBot(commands.Bot):
    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix, intents=intents)
        self.queues = {}
        self.custom_voice_clients = {}
        self.stop_flags = {}
        self.youtube_base_url = "https://www.youtube.com/"
        self.youtube_results_url = self.youtube_base_url + "results?"
        self.youtube_watch_url = self.youtube_base_url + "watch?v="
        self.ytdl = yt_dlp.YoutubeDL({"format": "bestaudio/best"})
        self.ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": '-vn -filter:a "volume=0.25"',
        }

    async def setup_hook(self):
        await self.add_cog(MusicCog(self))

    async def on_ready(self):
        print(f"{self.user} has connected to Discord!")
        try:
            await self.tree.sync()
            print("Commands synchronized!")
        except Exception as e:
            print(f"Error syncing commands: {e}")

    @staticmethod
    def fetch_youtube_title(url):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                title = soup.find("meta", property="og:title")
                return title["content"] if title else "Unknown Title"
        except Exception as e:
            print(f"Error fetching YouTube title: {e}")
        return "Error fetching title"

    async def send_message(self, interaction, message, ephemeral=False):
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(message, ephemeral=ephemeral)

    async def add_queue(self, interaction, query):
        await interaction.response.defer()

        guild_id = interaction.guild.id
        url = (
            self.youtube_watch_url + re.findall(r"/watch\?v=(.{11})", urllib.request.urlopen(
                self.youtube_results_url + urllib.parse.urlencode({"search_query": query})).read().decode())[0]
            if self.youtube_base_url not in query else query
        )

        self.queues.setdefault(guild_id, []).append(url)
        if len(self.queues[guild_id]) > 1:
            message = f"{random.choice(queue_preset)}[{self.fetch_youtube_title(url)}](<{url}>)"
            await self.send_message(interaction, message)
            return

        await self.play_music(interaction)

    async def play_music(self, interaction):
        guild_id = interaction.guild.id
        queue = self.queues.get(guild_id, [])

        if not queue:
            await self.send_message(interaction, random.choice(no_more_songs_preset), ephemeral=True)
            await self.stop_music(interaction)
            return

        url = queue[0]
        if guild_id not in self.custom_voice_clients:
            if not interaction.user.voice:
                await self.send_message(interaction, "You must join a voice channel first.", ephemeral=True)
                return
            voice_client = await interaction.user.voice.channel.connect()
            self.custom_voice_clients[guild_id] = voice_client

        message = f"{random.choice(plying_preset)}[{self.fetch_youtube_title(url)}](<{url}>)"
        await self.send_message(interaction, message)

        data = await asyncio.get_event_loop().run_in_executor(None, lambda: self.ytdl.extract_info(url, download=False))
        player = discord.FFmpegOpusAudio(data["url"], **self.ffmpeg_options)

        self.custom_voice_clients[guild_id].play(player, after=lambda _: self.next_song(interaction))

    def next_song(self, interaction):
        guild_id = interaction.guild.id

        if self.stop_flags.pop(guild_id, False):
            return

        queue = self.queues.get(guild_id, [])
        if queue:
            queue.pop(0)
            asyncio.run_coroutine_threadsafe(self.play_music(interaction), self.loop)

    async def stop_music(self, interaction):
        guild_id = interaction.guild.id
        self.stop_flags[guild_id] = True

        voice_client = self.custom_voice_clients.pop(guild_id, None)
        if voice_client:
            if voice_client.is_playing():
                voice_client.stop()
            if voice_client.is_connected():
                await voice_client.disconnect()

        self.queues.pop(guild_id, None)
        await self.send_message(interaction, random.choice(stop_music_preset))

    async def pause_music(self, interaction):
        guild_id = interaction.guild.id
        voice_client = self.custom_voice_clients.get(guild_id)

        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await self.send_message(interaction, random.choice(pause_preset))
        else:
            await self.send_message(interaction, random.choice(already_pause_preset), ephemeral=True)

    async def resume_music(self, interaction):
        guild_id = interaction.guild.id
        voice_client = self.custom_voice_clients.get(guild_id)

        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await self.send_message(interaction, random.choice(resume_preset))
        else:
            await self.send_message(interaction, random.choice(already_resume_preset), ephemeral=True)

    async def skip_music(self, interaction):
        guild_id = interaction.guild.id
        voice_client = self.custom_voice_clients.get(guild_id)

        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await self.send_message(interaction, random.choice(skip_preset))
        else:
            await self.send_message(interaction, random.choice(nothing_playing_preset), ephemeral=True)

    async def clear_queue(self, interaction):
        guild_id = interaction.guild.id
        queue = self.queues.get(guild_id, [])

        if queue:
            current_track = queue[:1]
            self.queues[guild_id] = current_track
            await self.send_message(interaction, random.choice(queue_cleared_preset))
        else:
            await self.send_message(interaction, random.choice(queue_already_empty_preset), ephemeral=True)


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="play", description="Play a track")
    @app_commands.describe(query="Name or URL of track to play")
    async def play(self, interaction: discord.Interaction, query: str):
        await self.bot.add_queue(interaction, query)

    @app_commands.command(name="stop", description="Disconnect the bot from the voice channel")
    async def stop(self, interaction: discord.Interaction):
        await self.bot.stop_music(interaction)

    @app_commands.command(name="pause", description="Pause the queue")
    async def pause(self, interaction: discord.Interaction):
        await self.bot.pause_music(interaction)

    @app_commands.command(name="resume", description="Resume the queue")
    async def resume(self, interaction: discord.Interaction):
        await self.bot.resume_music(interaction)

    @app_commands.command(name="skip", description="Skip the current track")
    async def skip(self, interaction: discord.Interaction):
        await self.bot.skip_music(interaction)

    @app_commands.command(name="clearqueue", description="Clear the queue and continues playing the current track")
    async def clearqueue(self, interaction: discord.Interaction):
        await self.bot.clear_queue(interaction)


def main():
    token = "MTMxMjg4MTE5OTI1Mjc3MDgzNg.GFJB5g.G3AXrFULKEW_nBXzJOzk9n0KpMa38fhEzIeh50"
    intents = discord.Intents.all()
    bot = MusicBot(command_prefix=".", intents=intents)
    bot.run(token)


if __name__ == "__main__":
    main()
