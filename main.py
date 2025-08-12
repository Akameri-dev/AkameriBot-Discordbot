# Importacion de modulos necesarios
import os
import discord
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")





# programa principal y cogs
intents = discord.Intents.default()  
intents.message_content = True 
bot = commands.Bot(command_prefix='.', intents = intents, help_command=None)
    

@bot.command()
async def prueba(ctx):
    await ctx.send("chambea a la verga")


async def load_cogs():
    await bot.load_extension('cogs.dados')
    await bot.load_extension('utils.help')












@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")

    await load_cogs()

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.competing,
            name=".help"
        ),
        status=discord.Status.do_not_disturb,
        afk=False
    )


if __name__ == "__main__":
    from webserver import keep_alive 
    keep_alive()
    bot.run(TOKEN)