import discord
import random
import yt_dlp
import asyncio
from discord.ext import commands
from discord.ui import Button, View
import urllib.parse
import urllib.request
from presetMessage import *
import time

radio_stations = [
    {'name': "Ретро FM", 'url': "https://retro.hostingradio.ru:8043/retro256.mp3",
     'thumbnail': 'https://is3-ssl.mzstatic.com/image/thumb/Purple122/v4/20/fb/36/20fb3643-cf6e-030e-d1ac-2b2950b48dc2/AppIcon-1x_U007emarketing-0-10-0-0-85-220.jpeg/1200x600wa.png'},
    {'name': "Русское Радио", 'url': "https://rusradio.hostingradio.ru/rusradio96.aacp",
     'thumbnail': "https://rusradio.ru/uploads/38/d4/c97387c1e083603bb6ce6d394276.png"},
    {'name': "Дорожное радио", 'url': "https://dorognoe.hostingradio.ru/dorognoe",
     'thumbnail': "https://i.ytimg.com/vi/vapkbFPA8yY/maxresdefault.jpg?sqp=-oaymwEmCIAKENAF8quKqQMa8AEB-AH-CYAC0AWKAgwIABABGH8gHygeMA8=&rs=AOn4CLBqxkPxzAFnPWRPRY0XMeL5g6BVrw"},
    {'name': "Радио Шансон",
     'url': "https://chanson.hostingradio.ru:8041/chanson256.mp3?md5=KjdTfiXMsfAjrUam0zxNxA&e=1733434339",
     'thumbnail': "https://vinodel-dk.stv.muzkult.ru/media/2023/02/06/1290852800/Zvezdi_shansona.jpeg"}
]


class MusicBot:
    def __init__(self):
        self.queues = {}
        self.custom_voice_clients = {}
        self.ytdl = yt_dlp.YoutubeDL({
            "format": "bestaudio/best",
            "quiet": True,
            "extract_audio": True,
            "skip_download": True,
            "noplaylist": True,
            # "extract_flat": True,
            "default_search": 'ytsearch',
            # "n_threads": 4
        })
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -filter:a "volume=0.25"'
        }
        self.youtube_base_url = "https://www.youtube.com/"
        self.youtube_results_url = self.youtube_base_url + "results?"
        self.youtube_watch_url = self.youtube_base_url + "watch?v="
        self.stop_flags = {}
        self.is_playing = {}

    async def add_queue(self, ctx, query):
        await ctx.defer()
        # id сервера
        guild_id = ctx.guild.id
        print(f"Adding queue for guild: {guild_id}")
        message_queue = None

        # Проверяем человек в гк
        if not ctx.user.voice:
            await ctx.respond(random.choice(join_voice_channel_preset), ephemeral=True)
            return

        # Добавляем id сервера
        self.queues.setdefault(guild_id, [])

        # Проверяем query ссылка или нет
        parsed = urllib.parse.urlparse(query)
        if all([parsed.scheme, parsed.netloc]):
            result = self.ytdl.extract_info(query, download=False)
        else:
            result = self.ytdl.extract_info(f"ytsearch1:{query}", download=False)

        if 'entries' in result:
            result = result['entries'][0]
            if not result:
                await ctx.respond("Не удалось найти трек. Попробуйте снова.", ephemeral=True)
                return

        # Получаем данные из видео
        video_id = result.get("id")
        url = f"{self.youtube_watch_url}{video_id}" if video_id else None

        audio_url = result["url"]
        duration = result.get("duration", 0)
        title = result.get("title")
        duration_str = f"{duration // 60}:{duration % 60:02d}"
        thumbnail_url = result.get("thumbnail")

        if self.queues[guild_id]:
            # Создаём embed
            embed = discord.Embed(
                title=random.choice(added_to_queue_preset),
                description=f"[{title}](<{url}>)",
                color=0xD21414
            )
            embed.add_field(name="Продолжительность", value=duration_str, inline=True)
            embed.add_field(name="В очереди", value=f"{len(self.queues[guild_id])} треков", inline=True)
            embed.set_author(name=ctx.user.display_name, icon_url=ctx.user.avatar.url)
            embed.set_thumbnail(url=await self.get_square_thumbnail(thumbnail_url, 300, 300))
            embed.set_footer(text=random.choice(quotes))
            message_queue = await ctx.respond(embed=embed)

        # Добавляем URL в очередь
        queue_data = {
            'url': url,
            'audio_url': audio_url,
            'title': title,
            'duration': duration_str,
            'thumbnail': thumbnail_url,
            'author': ctx.user,
            'message_queue': message_queue,
        }
        self.queues[guild_id].append(queue_data)

        # Если музыка не воспроизводится, начинаем воспроизведение
        if self.custom_voice_clients.get(guild_id) and self.custom_voice_clients[guild_id].is_playing():
            return

        await self.play_music(ctx)

    async def search_music(self, ctx, query):
        pass

    async def play_music(self, ctx, radio=None):
        guild_id = ctx.guild.id

        # Проверяем играет ли музыка
        if self.is_playing.get(guild_id):
            return

        if not radio:
            # Проверяем есть ли треки в очереди
            if not self.queues.get(guild_id):
                print("Треков нет!")
                await self.stop_music(ctx)
                return

        # Подключение к гк
        if guild_id not in self.custom_voice_clients:
            self.custom_voice_clients[guild_id] = await ctx.user.voice.channel.connect()

        if not radio:
            # Получаем url и автора
            self.is_playing[guild_id] = True
            url = self.queues[guild_id][0]['url']
            audio_url = self.queues[guild_id][0]['audio_url']
            title = self.queues[guild_id][0]['title']
            duration = self.queues[guild_id][0]['duration']
            thumbnail = self.queues[guild_id][0]['thumbnail']
            author = self.queues[guild_id][0]['author']
            message_queue = self.queues[guild_id][0]['message_queue']
        else:
            audio_url = radio['url']
            title = radio['name']
            duration = "∞"
            thumbnail = radio['thumbnail']
            author = ctx.user
            message_queue = None

        try:
            embed = discord.Embed(
                title=random.choice(now_playing_preset),
                description=f"[{title}](<{url}>)" if not radio else f"{title}",
                color=0xD21414
            )

            embed.add_field(name="Продолжительность", value=duration, inline=True)
            embed.add_field(name="В очереди", value=f"{len(self.queues[guild_id]) - 1} треков",
                            inline=True) if not radio else None
            embed.set_author(name=author.display_name, icon_url=author.avatar.url)
            embed.set_thumbnail(url=await self.get_square_thumbnail(thumbnail, 300, 300))
            embed.set_footer(text=random.choice(quotes))

            pause_resume_button = Button(label="Pause", style=discord.ButtonStyle.green)
            skip_button = Button(label="Skip", style=discord.ButtonStyle.primary, custom_id="skip")
            stop_button = Button(label="Stop", style=discord.ButtonStyle.danger, custom_id="stop")
            queue_button = Button(label="Queue", style=discord.ButtonStyle.secondary, custom_id="queue")
            clear_queue_button = Button(label="Clear queue", style=discord.ButtonStyle.secondary,
                                        custom_id="clear_queue")

            async def pause_resumeCallback(interaction: discord.Interaction):
                guild_id = interaction.guild.id
                client = self.custom_voice_clients.get(guild_id)
                if client:
                    if client.is_paused():
                        await self.resume_music(interaction, interaction=interaction)
                        pause_resume_button.label = "Pause"
                        pause_resume_button.style = discord.ButtonStyle.green
                    elif client.is_playing():
                        await self.pause_music(interaction, interaction=interaction)
                        pause_resume_button.label = "Resume"
                        pause_resume_button.style = discord.ButtonStyle.danger

                    await interaction.response.edit_message(view=buttonManager)
                else:
                    await interaction.response.send_message(random.choice(nothing_playing_preset), ephemeral=True)

            async def skipCallback(interaction: discord.Interaction):
                await self.skip_music(interaction)

            async def stopCallback(interaction: discord.Interaction):
                await self.stop_music(interaction)

            async def queueCallback(interaction: discord.Interaction):
                await self.queue_music(interaction)

            async def clear_queueCallback(interaction: discord.Interaction):
                await self.clear_queue_music(interaction)

            buttonManager = View(pause_resume_button)
            buttonManager.add_item(skip_button) if not radio else None
            buttonManager.add_item(stop_button)
            buttonManager.add_item(queue_button) if not radio else None
            buttonManager.add_item(clear_queue_button) if not radio else None

            pause_resume_button.callback = pause_resumeCallback
            skip_button.callback = skipCallback
            stop_button.callback = stopCallback
            queue_button.callback = queueCallback
            clear_queue_button.callback = clear_queueCallback

            if message_queue:
                await message_queue.reply(embed=embed, view=buttonManager)
            else:
                try:
                    await ctx.send_followup(embed=embed, view=buttonManager)
                except:
                    await ctx.respond(embed=embed, view=buttonManager)

            player = discord.FFmpegOpusAudio(audio_url, **self.ffmpeg_options)
            self.custom_voice_clients[guild_id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                self.next_song(ctx), ctx.bot.loop))

        except Exception as e:
            print(f"Error during playback: {e}")
            await self.stop_music(ctx)
            self.is_playing[guild_id] = False

    async def next_song(self, ctx):
        guild_id = ctx.guild.id
        print(f"Calling next_song for guild {guild_id}")
        self.is_playing[guild_id] = False

        self.queues[guild_id].pop(0)
        if not self.queues.get(guild_id) or len(self.queues[guild_id]) == 0:
            await self.stop_music(ctx)
            return

        print(f"Queue after pop: {self.queues[guild_id]}")
        await self.play_music(ctx)

    async def stop_music(self, ctx):
        guild_id = ctx.guild.id

        # Проверяем, не выполняется ли уже остановка
        if self.stop_flags.get(guild_id, False):
            print(f"Music stop already in progress for guild: {guild_id}")
            return

        # Устанавливаем флаг остановки
        self.stop_flags[guild_id] = True

        # Проверяем наличие клиента перед отключением
        if guild_id in self.custom_voice_clients:
            client = self.custom_voice_clients[guild_id]
            if client.is_playing():
                client.stop()
            if client.is_connected():
                await client.disconnect()

            # Удаляем запись о клиенте
            del self.custom_voice_clients[guild_id]

        # Удаляем очередь, если она существует
        if guild_id in self.queues:
            del self.queues[guild_id]

        # Сбрасываем флаг остановки
        self.stop_flags[guild_id] = False

        await ctx.response.send_message(random.choice(stopped_music_preset), ephemeral=True)

    async def pause_music(self, ctx, interaction=None):
        guild_id = ctx.guild.id
        if client := self.custom_voice_clients.get(guild_id):
            if client.is_playing():
                client.pause()
                if interaction is None:  # Если вызвано через команду
                    await ctx.response.send_message(random.choice(pause_preset), ephemeral=True)
            else:
                if interaction is None:  # Если вызвано через команду
                    await ctx.response.send_message(random.choice(already_paused_preset), ephemeral=True)
        else:
            if interaction is None:  # Если вызвано через команду
                await ctx.response.send_message(random.choice(nothing_playing_preset), ephemeral=True)

    async def resume_music(self, ctx, interaction=None):
        guild_id = ctx.guild.id
        if client := self.custom_voice_clients.get(guild_id):
            if client.is_paused():
                client.resume()
                if interaction is None:  # Если вызвано через команду
                    await ctx.response.send_message(random.choice(resume_preset), ephemeral=True)
            else:
                if interaction is None:  # Если вызвано через команду
                    await ctx.response.send_message(random.choice(already_playing_preset), ephemeral=True)
        else:
            if interaction is None:  # Если вызвано через команду
                await ctx.response.send_message(random.choice(nothing_playing_preset), ephemeral=True)

    async def skip_music(self, ctx):
        guild_id = ctx.guild.id
        if client := self.custom_voice_clients.get(guild_id):
            if client.is_playing():
                client.stop()
                await ctx.response.send_message(random.choice(skip_track_preset), ephemeral=True)
            else:
                await ctx.response.send_message(random.choice(nothing_playing_preset), ephemeral=True)
        else:
            await ctx.response.send_message(random.choice(nothing_playing_preset), ephemeral=True)

    async def clear_queue_music(self, ctx):
        guild_id = ctx.guild.id
        if not self.queues.get(guild_id):
            await ctx.response.send_message(random.choice(queue_already_empty_preset), ephemeral=True)
            return

        if client := self.custom_voice_clients.get(guild_id):
            if client.is_playing():
                self.queues[guild_id] = [self.queues[guild_id][0]]
            else:
                self.queues[guild_id].clear()
        else:
            self.queues[guild_id].clear()

        await ctx.response.send_message(random.choice(queue_cleared_preset), ephemeral=True)

    async def queue_music(self, ctx):
        guild_id = ctx.guild.id

        # Проверяем, существует ли очередь для данного сервера
        if guild_id not in self.queues or not self.queues[guild_id]:
            await ctx.respond("🎵 Очередь пуста.", ephemeral=True)
            return

        queue = self.queues[guild_id]
        queue_without_current_track = queue[1:]
        if queue_without_current_track:
            # Создаем Embed
            embed = discord.Embed(
                title="🎵 Текущая очередь",
                color=0xD21414
            )
            embed.add_field(name="Текущая песня:",
                            value=f"[{queue[0]['title']}](<{queue[0]['url']}>)",
                            inline=False)

            queue_list = "\n"
            for i, data in enumerate(queue_without_current_track):
                queue_list += f"**{i + 1}.** [{data['title']}](<{data['url']}>)\n"

            embed.add_field(name="Треки в очереди:", value=queue_list, inline=False)
            embed.set_footer(text=f"Всего в очереди: {len(queue) - 1} треков")

            # Отправляем Embed
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            await ctx.respond("🎵 Очередь пуста.", ephemeral=True)

    async def get_square_thumbnail(self, image_url, width=300, height=300):
        # Параметры вашего Cloudinary аккаунта
        cloud_name = "dcfvhmzi3"

        # Кодируем URL изображения
        encoded_url = urllib.parse.quote(image_url, safe='')

        # Генерируем ссылку для кадрирования
        thumbnail_url = f"https://res.cloudinary.com/{cloud_name}/image/fetch/c_fill,w_{width},h_{height}/{encoded_url}"
        return thumbnail_url


class MusicCog(discord.Cog):
    @discord.slash_command(name="play", description="Play a track")
    async def play(self, ctx: discord.ApplicationContext,
                   query: discord.Option(str, description="Name or URL of track to play")):
        await music_bot.add_queue(ctx, query)

    @discord.slash_command(name="search", description="Search and play track")
    async def search(self, ctx: discord.ApplicationContext,
                     query: discord.Option(str, description="Name of track to search for")):
        await music_bot.search_music(ctx, query)

    @discord.slash_command(name="stop", description="Disconnect the bot from the voice channel")
    async def stop(self, ctx: discord.ApplicationContext):
        await music_bot.stop_music(ctx)

    @discord.slash_command(name="pause", description="Pause the queue")
    async def pause(self, ctx: discord.ApplicationContext):
        await music_bot.pause_music(ctx)

    @discord.slash_command(name="resume", description="Resume the queue")
    async def resume(self, ctx: discord.ApplicationContext):
        await music_bot.resume_music(ctx)

    @discord.slash_command(name="skip", description="Skip the current track")
    async def skip(self, ctx: discord.ApplicationContext):
        await music_bot.skip_music(ctx)

    @discord.slash_command(name="clearqueue", description="Clear the queue and keeps the current track")
    async def clearqueue(self, ctx: discord.ApplicationContext):
        await music_bot.clear_queue_music(ctx)

    @discord.slash_command(name="queue", description="Show the queue")
    async def queue(self, ctx: discord.ApplicationContext):
        await music_bot.queue_music(ctx)

    async def autocompleteRadio(self, ctx: discord.AutocompleteContext):
        return [radio_stations[i]["name"] for i in range(len(radio_stations))]

    @discord.slash_command(name="radio", description="Turn on the radio")
    async def radio(self, ctx: discord.ApplicationContext,
                    radiostations: discord.Option(str, description="Select a radio station",
                                                  autocomplete=autocompleteRadio)):
        selected_station = next((station for station in radio_stations if station['name'] == radiostations), None)
        await music_bot.play_music(ctx, selected_station)


music_bot = MusicBot()


def setup(bot: discord.Bot):
    bot.add_cog(MusicCog())
