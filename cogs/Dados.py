import random
from discord.ext import commands

class Dados(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['d'])
    async def roll(self, ctx, caras: int = 6):
        resultado = random.randint(1, caras)
        await ctx.send(f"**{resultado}**")

def setup(bot):
    bot.add_cog(Dados(bot))