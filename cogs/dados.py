import random
import re
from discord.ext import commands

class Dados(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(aliases=['d', 'r', 'tirar', 'roll'])
    async def dados(self, ctx, *, expresion: str = "1d6"):
        try:
            resultado, detalles = self.procesar_expresion(expresion)
            
            respuesta = f"**Tirada de {ctx.author.mention}**\n"
            respuesta += f"**Resultado:** `{resultado}`\n"
            respuesta += f"**Detalles:**\n{detalles}"
            
            await ctx.send(respuesta)
            
        except Exception as e:
            await ctx.send(f"Error wey")

    def procesar_expresion(self, expresion):

        expresion_original = expresion
        detalles = []
        
        def reemplazar_dado(match):
            cantidad = int(match.group(1)) if match.group(1) else 1
            caras = int(match.group(2))
            
            if cantidad < 1 or caras < 1:
                raise ValueError("Cantidad y caras deben ser al menos 1")
            
            tiradas = [random.randint(1, caras) for _ in range(cantidad)]
            total_dado = sum(tiradas)
            
            detalle = f"- {cantidad}d{caras}: {', '.join(str(t) for t in tiradas)} = {total_dado}"
            detalles.append(detalle)
            
            return str(total_dado)
        
        expresion_numerica = re.sub(r'(\d*)d(\d+)', reemplazar_dado, expresion)
        
        if not re.match(r'^[\d\s+\-*/().]+$', expresion_numerica):
            raise ValueError("La expresión contiene caracteres no permitidos")
        
        try:
            resultado = eval(expresion_numerica)
        except:
            if "division by zero" in str().lower():
                raise ValueError("No puedes dividir por cero")
            raise ValueError("Expresión matemática inválida")
        
        return resultado, "\n".join(detalles)

async def setup(bot):
    await bot.add_cog(Dados(bot))