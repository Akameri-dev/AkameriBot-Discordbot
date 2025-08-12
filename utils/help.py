import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['ayuda', 'Ayuda', 'AYUDA', 'HELP'])
    async def help(self, ctx):
        embed = discord.Embed(
            title="INFORMACION",
            description=(
                "AkameriBot es un bot experimental hecho por **'Akameri'**, "
                "especializado en herramientas para la simulación de Roleplay. "
                "Aquí una lista de comandos disponibles:"
            ),
            color=discord.Color.dark_gold()
        )

        for command in self.bot.commands:
            if command.hidden:
                continue
            desc = " "
            embed.add_field(
                name=f"**.{command.name}**",
                value=desc,
                inline=False
            )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
