import sqlite3
from discord.ext import commands
import discord

class Personajes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("personajes.db")
        self.cursor = self.conn.cursor()

    @commands.command()
    async def registrar(self, ctx, Nombre: str, Imagen: str = None, *, Trasfondo: str = "Sin trasfondo"):
        User_id = str(ctx.author.id)
        Servidor_id = str(ctx.guild.id)

        self.cursor.execute("SELECT * FROM personajes WHERE Nombre=? AND Servidor_id=?", (Nombre, Servidor_id))
        if self.cursor.fetchone():
            return await ctx.send("Ya existe un personaje con ese nombre en este servidor.")
        
        self.cursor.execute("""
            INSERT INTO personajes (User_id, Servidor_id, Nombre, Trasfondo, Imagen)
            VALUES (?, ?, ?, ?, ?)
        """, (User_id, Servidor_id, Nombre, Trasfondo, Imagen))
        self.conn.commit()

        await ctx.send(f"✅ {ctx.author.mention}, tu personaje **{Nombre}** fue registrado y espera aprobación.")

    @commands.has_permissions(administrator=True)
    @commands.command()
    async def aprobar(self, ctx, Nombre: str):
        Servidor_id = str(ctx.guild.id)

        self.cursor.execute("UPDATE personajes SET Aprobado=1 WHERE Nombre=? AND Servidor_id=?", (Nombre, Servidor_id))
        if self.cursor.rowcount == 0:
            return await ctx.send("No encontré un personaje con ese nombre.")
        self.conn.commit()

        await ctx.send(f"El personaje **{Nombre}** fue aprobado.")

    @commands.command()
    async def eliminar(self, ctx, Nombre: str):
        Servidor_id = str(ctx.guild.id)
        User_id = str(ctx.author.id)

        self.cursor.execute("SELECT User_id FROM personajes WHERE Nombre=? AND Servidor_id=?", (Nombre, Servidor_id))
        personaje = self.cursor.fetchone()

        if not personaje:
            return await ctx.send("No encontré un personaje con ese nombre.")

        dueño_id = personaje[0]

        if ctx.author.guild_permissions.administrator or User_id == dueño_id:
            self.cursor.execute("DELETE FROM personajes WHERE Nombre=? AND Servidor_id=?", (Nombre, Servidor_id))
            self.conn.commit()
            return await ctx.send(f"El personaje **{Nombre}** fue eliminado.")
        else:
            return await ctx.send("No puedes eliminar un personaje que no es tuyo.")

    @commands.command()
    async def ficha(self, ctx, Nombre: str):
        Servidor_id = str(ctx.guild.id)

        self.cursor.execute("SELECT User_id, Nombre, Trasfondo, Imagen, Aprobado FROM personajes WHERE Nombre=? AND Servidor_id=?", (Nombre, Servidor_id))
        personaje = self.cursor.fetchone()

        if not personaje:
            return await ctx.send("No encontré un personaje con ese nombre.")

        user_id, Nombre, Trasfondo, Imagen, Aprobado = personaje
        estado = "Aprobado" if Aprobado == 1 else "Pendiente"

        embed = discord.Embed(title=f"Ficha de {Nombre}", description=Trasfondo, color=discord.Color.dark_gold())
        embed.add_field(name="Estado", value=estado, inline=False)
        embed.set_footer(text=f"Dueño: {user_id}")
        if Imagen:
            embed.set_thumbnail(url=Imagen)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Personajes(bot))
