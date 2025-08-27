import random
import re
from discord.ext import commands

class Dados(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(aliases=['d', 'r', 'tirar', 'roll'])
    async def dados(self, ctx, *, expresion: str = "1d6"):
        try:
            resultado, detalles, expandida = self.procesar_expresion(expresion)
            
            respuesta = f"``Tirada de: {ctx.author}``"
            respuesta += f"\n```{detalles}```"
            respuesta += f"``Resultado: {resultado}``\n"
            
            await ctx.send(respuesta)
            
        except Exception:
            await ctx.send(f"``Error``")

    def procesar_expresion(self, expresion):
        detalles = []
        partes_expandida = []  

        def reemplazar_dado(match):
            cantidad = int(match.group(1)) if match.group(1) else 1
            caras = int(match.group(2))
            if cantidad < 1 or caras < 1:
                raise ValueError("Cantidad y caras deben ser al menos 1")

            tiradas = [random.randint(1, caras) for _ in range(cantidad)]
            total_dado = sum(tiradas)

            detalle = f"- {cantidad}d{caras}: {', '.join(str(t) for t in tiradas)} = {total_dado}"
            detalles.append(detalle)

            partes_expandida.append("(" + "+".join(map(str, tiradas)) + ")")

            return str(total_dado)


        expresion_numerica = re.sub(r'(\d*)d(\d+)', reemplazar_dado, expresion)


        expresion_expandida = expresion
        for bloque in partes_expandida:
            expresion_expandida = re.sub(r'\d+', bloque, expresion_expandida, 1)

        if not re.match(r'^[\d\s+\-*/().]+$', expresion_numerica):
            raise ValueError("La expresión contiene caracteres no permitidos")

        try:
            resultado = eval(expresion_numerica)
        except Exception:
            raise ValueError("Expresión matemática inválida")

        return resultado, "\n".join(detalles), expresion_expandida

async def setup(bot):
    await bot.add_cog(Dados(bot))
