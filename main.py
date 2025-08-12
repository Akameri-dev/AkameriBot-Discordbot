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
bot = commands.Bot(command_prefix='.', intents = intents)
    

@bot.command()
async def prueba(ctx):
    await ctx.send("Nada de help, chambea a la verga")


async def load_cogs():
    await bot.load_extension('cogs.dados')









@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    await load_cogs()


if __name__ == "__main__":
    from webserver import keep_alive 
    keep_alive()
    bot.run(TOKEN)