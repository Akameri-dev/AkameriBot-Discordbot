# Importacion de modulos necesarios
import os
import webserver
import discord
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")




# programa principal
intents = discord.Intents.default()  
intents.message_content = True 
bot = commands.Bot(command_prefix='.', intents = intents)
















@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")



if __name__ == "__main__":
    webserver.keep_alive()
    bot.run(TOKEN)