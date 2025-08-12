# Importacion de modulos necesarios
import os
import discord
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


# edicion del help
class CustomHelp(commands.MinimalHelpCommand):
    def __init__(self):
        super().__init__()
        self.no_category = "Comandos Generales"
        self.command_attrs["help"] = "Muestra este mensaje de ayuda"
    
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="Ayuda de AkameriBot",
            description=f"Prefijo: `{bot.command_prefix}`\nUsa `{self.clean_prefix}help [comando]` para más detalles",
            color=0x00ff00
        )
        
        for cog, commands in mapping.items():
            if cog and cog.qualified_name == "Jishaku": continue  #Comando de debug
            
            filtered = await self.filter_commands(commands, sort=True)
            if command_names := [f"`{self.clean_prefix}{c.name}`" for c in filtered]:
                cog_name = getattr(cog, "qualified_name", self.no_category)
                embed.add_field(name=f"**{cog_name}**", value=", ".join(command_names), inline=False )

        channel = self.get_destination()
        await channel.send(embed=embed)

# programa principal y cogs
intents = discord.Intents.default()  
intents.message_content = True 
bot = commands.Bot(command_prefix='.', intents = intents)
bot.help_command = CustomHelp()
    

@bot.command()
async def prueba(ctx):
    await ctx.send("chambea a la verga")


async def load_cogs():
    await bot.load_extension('cogs.dados')












@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    await load_cogs()


    await bot.change_presence(
    activity=discord.Activity(  
        type=discord.ActivityType.competing,  
        name="Roleplay | .help",
        details="Apoyando a los Anarquistas"
    ),
    status=discord.Status.online,
    afk=False
)



if __name__ == "__main__":
    from webserver import keep_alive 
    keep_alive()
    bot.run(TOKEN)