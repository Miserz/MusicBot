import discord
import os
from dotenv import load_dotenv

# from presetMessage import *

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
# debug_guilds=[1194986148968284241]
bot = discord.Bot()


@bot.event
async def on_ready():
    print(f"{bot.user} is ready and Online!")


@bot.slash_command(name="reloadbot", description="Reload the bot.")
async def reload_bot(ctx: discord.ApplicationContext):
    bot.reload_extension("pycordMusicBot")
    await ctx.send_response("Reloaded the bot.", ephemeral=True)


@bot.event
async def on_error(event_name, *args, **kwargs):
    print("Catched in `on_error`", event_name)


bot.load_extension("pycordMusicBot")
bot.run(token)
