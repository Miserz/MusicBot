import random
import yt_dlp
import time
import os
import sys
import logging
import discord
import asyncio
from asyncio import Queue

from discord import FFmpegPCMAudio, FFmpegOpusAudio
from discord.ext import commands
from discord.ui import Button, View
import urllib.parse
import urllib.request
from dotenv import load_dotenv
from presetMessage import *
from radioList import radio_stations

bot_version = "1.0"


class Bot:
    def __init__(self) -> None:
        # Создание логов
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger('discord')
        logger.setLevel(logging.DEBUG)

        # Словарь для хранения очередей треков по серверам
        self.queues = {}

        # Настройка FFmgeg
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -filter:a "volume=0.25"'
        }

    # Функция для проверки, находится ли пользователь в голосовом канале, и подключения бота
    @staticmethod
    async def ensure_voice(ctx: discord.ApplicationContext):
        if ctx.author.voice is None:  # Если пользователь не находится в голосовом канале
            await ctx.send("Вы должны быть в голосовом канале, чтобы использовать эту команду.")
            return

        voice_channel = ctx.author.voice.channel  # Получаем голосовой канал пользователя
        if ctx.voice_client is None:  # Если бот не подключен к голосовому каналу
            await voice_channel.connect()  # Подключаем бота

        return ctx.voice_client  # Возвращаем объект голосового клиента

    # Функция для получения данных о видео
    @staticmethod
    async def get_video_info(query):
        # Настройка ydl
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'extract_audio': True,
            'skip_download': True,
            'noplaylist': True,
            'default_search': 'ytsearch',
            'cookiefile': 'cookies.txt',
        }

        # Получаем данные
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Проверяем query ссылка или нет
            parsed = urllib.parse.urlparse(query)
            if all([parsed.scheme, parsed.netloc]):
                info = ydl.extract_info(query, download=False)
            else:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)

            if 'entries' in info:
                info = info['entries'][0]

            return {
                'video_url': info['webpage_url'],
                'url': info['url'],
                'title': info['title'],
                'duration': info['duration'],
                'thumbnail': info['thumbnails'][-1]['url'] if 'thumbnails' in info else ''
            }

    @staticmethod
    async def get_square_thumbnail(image_url, width=300, height=300):
        # Параметры вашего Cloudinary аккаунта
        cloud_name = "dcfvhmzi3"

        # Кодируем URL изображения
        encoded_url = urllib.parse.quote(image_url, safe='')

        # Генерируем ссылку для кадрирования
        thumbnail_url = f"https://res.cloudinary.com/{cloud_name}/image/fetch/c_fill,w_{width},h_{height}/{encoded_url}"
        return thumbnail_url

    async def music_embed(self, ctx: discord.ApplicationContext, title: str, url: str, duration: int, thumbnail: str,
                          play_or_queue: bool):
        duration = f"{duration // 60}:{duration % 60:02d}"
        embed = discord.Embed(
            title=random.choice(now_playing_preset) if play_or_queue else random.choice(added_to_queue_preset),
            description=f"[{title}](<{url}>)",
            color=0xD21414
        )
        embed.add_field(name="Продолжительность", value=f"`{duration}`", inline=True)
        embed.add_field(name="В очереди",
                        value=f"`{self.queues[ctx.guild.id].qsize()} треков`",
                        inline=True)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
        embed.set_thumbnail(url=await self.get_square_thumbnail(thumbnail, 300, 300))
        embed.set_footer(text=random.choice(quotes))
        return embed

    @staticmethod
    async def info_embed(*, ctx: discord.ApplicationContext = None, title: str = None, description: str = None):
        embed = discord.Embed(
            title=title,
            description=description,
            color=0xD21414
        )
        return embed

    async def play_next(self, ctx: discord.ApplicationContext) -> None:
        if ctx.guild.id in self.queues and not self.queues[ctx.guild.id].empty():  # Если очередь не пуста
            next_url = await self.queues[ctx.guild.id].get()  # Извлекаем следующий трек из очереди
            ctx.voice_client.play(
                FFmpegOpusAudio(next_url['url'], **self.ffmpeg_options),  # Воспроизводим аудио через FFmpeg
                # Запускаем следующий трек после завершения текущего
                after=lambda e: ctx.bot.loop.create_task(self.play_next(ctx))
            )
            embed = await self.music_embed(
                ctx, next_url['title'], next_url['video_url'], int(next_url['duration']),
                next_url['thumbnail'], True
            )
            try:
                await ctx.send_followup(embed=embed)
            except:
                await ctx.respond(embed=embed)
            # await ctx.send(f"Сейчас играет: {next_url['video_url']}")  # Уведомляем о текущем треке
        else:
            await ctx.voice_client.disconnect()  # Если очередь пуста, отключаем бота

    async def play(self, ctx: discord.ApplicationContext, query) -> None:
        voice_channel = await self.ensure_voice(ctx)  # Убеждаемся, что бот подключен к голосовому каналу
        if voice_channel is None:
            return

        if ctx.guild.id not in self.queues:  # Создаём очередь для сервера, если её ещё нет
            self.queues[ctx.guild.id] = Queue()

        video_info = await self.get_video_info(query)
        await self.queues[ctx.guild.id].put(video_info)  # Добавляем трек в очередь
        print(self.queues[ctx.guild.id])

        if not voice_channel.is_playing():  # Если бот не воспроизводит музыку
            await self.play_next(ctx)  # Запускаем следующий трек
        else:
            embed = await self.music_embed(
                ctx, video_info['title'], video_info['video_url'], int(video_info['duration']),
                video_info['thumbnail'], False
            )
            try:
                await ctx.send_followup(embed=embed)
            except:
                await ctx.respond(embed=embed)

    async def pause(self, ctx: discord.ApplicationContext) -> None:
        if ctx.voice_client is None:  # Проверяем, есть ли музыка
            await ctx.send_response(embed=await self.info_embed(
                description=f"{ctx.author.mention} {random.choice(nothing_playing_preset)}"), ephemeral=True)
            return

        if ctx.voice_client.is_paused():  # Проверяем, под паузой она
            await ctx.send_response(embed=await self.info_embed(
                description=f"{ctx.author.mention} {random.choice(already_paused_preset)}"), ephemeral=True)
            return

        ctx.voice_client.pause()  # Ставим воспроизведение на паузу
        await ctx.send_response(
            embed=await self.info_embed(description=f"{ctx.author.mention} {random.choice(pause_preset)}"))

    async def resume(self, ctx: discord.ApplicationContext) -> None:
        if ctx.voice_client is None:  # Проверяем, есть ли музыка
            await ctx.send_response(embed=await self.info_embed(
                description=f"{ctx.author.mention} {random.choice(nothing_playing_preset)}"), ephemeral=True)
            return

        if ctx.voice_client.is_playing():  # Проверяем, играет ли она
            await ctx.send_response(embed=await self.info_embed(
                description=f"{ctx.author.mention} {random.choice(already_playing_preset)}"), ephemeral=True)
            return

        ctx.voice_client.resume()  # Возобновляем воспроизведение
        await ctx.send_response(
            embed=await self.info_embed(description=f"{ctx.author.mention} {random.choice(resume_preset)}"))

    async def stop(self, ctx: discord.ApplicationContext) -> None:
        if ctx.voice_client is None:  # Проверяем, подключен ли бот к голосовому каналу
            await ctx.send_response(
                embed=await self.info_embed(
                    description=f"{ctx.author.mention} {random.choice(nothing_playing_preset)}"), ephemeral=True)
            return

        bot.queues.pop(ctx.guild.id, None)  # Очищаем очередь для сервера
        await ctx.voice_client.disconnect()  # Отключаем бота
        await ctx.send_response(
            embed=await self.info_embed(description=f"{ctx.author.mention} {random.choice(stopped_music_preset)}"))

    async def skip(self, ctx: discord.ApplicationContext) -> None:
        if ctx.voice_client is None or not ctx.voice_client.is_playing():  # Проверяем, воспроизводится ли музыка
            await ctx.send_response(embed=await self.info_embed(
                description=f"{ctx.author.mention} {random.choice(nothing_playing_preset)}"), ephemeral=True)
            return

        ctx.voice_client.stop()  # Останавливаем текущий трек
        await ctx.send_response(
            embed=await bot.info_embed(ctx=ctx, description=f"{ctx.author.mention} {random.choice(skip_track_preset)}"))


class BotCog(discord.Cog):
    @discord.slash_command(name="play", description="Play a track")
    async def play(self, ctx: discord.ApplicationContext,
                   query: discord.Option(str, description="Name or URL of track to play")) -> None:
        await ctx.defer()
        await bot.play(ctx, query)

    @discord.slash_command(name="pause", description="Pause the queue")
    async def pause(self, ctx: discord.ApplicationContext):
        await bot.pause(ctx)

    @discord.slash_command(name="resume", description="Resume the queue")
    async def resume(self, ctx: discord.ApplicationContext):
        await bot.resume(ctx)

    @discord.slash_command(name="stop", description="Disconnect the bot from the voice channel")
    async def stop(self, ctx: discord.ApplicationContext):
        await bot.stop(ctx)

    @discord.slash_command(name="skip", description="Skip the current track")
    async def skip(self, ctx: discord.ApplicationContext):
        await bot.skip(ctx)


bot: Bot = Bot()


def setup(bot: discord.Bot):
    bot.add_cog(BotCog())
