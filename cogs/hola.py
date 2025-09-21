import discord
from discord.ext import commands
from discord import app_commands

class Test(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Slash command de prueba
    @app_commands.command(name="hola", description="Responde con un saludo")
    async def hola(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"¡Hola {interaction.user.mention}! 👋")

# setup obligatorio
async def setup(bot: commands.Bot):
    await bot.add_cog(Test(bot))
