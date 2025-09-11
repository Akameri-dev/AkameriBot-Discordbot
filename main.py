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
bot = commands.Bot(
    command_prefix='.',
    intents = intents, 
    help_command=None,
    activity=discord.Activity(type=discord.ActivityType.watching, name=".Help | AkameriBot"),
    status=discord.Status.do_not_disturb,
    )
    


async def load_cogs():
    await bot.load_extension('cogs.dados')
    await bot.load_extension('cogs.personaje')
    await bot.load_extension('utils.help')












@bot.event
async def on_ready():
    try:
        await load_cogs()

        synced = await bot.tree.sync()
        print(f"Slash commands sincronizados: {len(synced)} comandos")
    except Exception as e:
        print(f"Error al sincronizar slash commands: {e}")

    print(f"Bot conectado como {bot.user}")

    


#prueba de los bots:

@bot.command()
async def prueba(ctx):
    await ctx.send("chambea a la verga")

@bot.tree.command(name="pruebape", description="verificacion de los slash commands")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("No wey no quiero")





if __name__ == "__main__":
    from webserver import keep_alive 
    keep_alive()
    bot.run(TOKEN)