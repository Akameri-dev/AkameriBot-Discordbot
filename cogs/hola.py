import discord
from discord import app_commands
from discord.ext import commands

class Test(commands.GroupCog, name="test"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__()

    @app_commands.command(name="hola", description="Responde con un saludo")
    async def hola(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"¡Hola {interaction.user.mention}! 👋")

async def setup(bot: commands.Bot):
    await bot.add_cog(Test(bot))
