from dotenv import load_dotenv
import os
import psycopg2
from discord.ext import commands
from discord import app_commands
import discord

class Personajes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        load_dotenv()
        DATABASE_URL = os.getenv("DATABASE_URL")
        print("URL de la DB:", DATABASE_URL)  
        self.conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        self.cursor = self.conn.cursor()

    # Crear tabla si no existe
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS personajes (
                Id SERIAL PRIMARY KEY,
                User_id TEXT,
                Servidor_id TEXT,
                Nombre TEXT,
                Trasfondo TEXT,
                Imagen TEXT,
                Aprobado INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    @app_commands.command(name="registrar", description="Registrar un nuevo personaje")
    async def registrar(self, interaction: discord.Interaction, Nombre: str, Imagen: str = None, Trasfondo: str = "Sin trasfondo"):
        User_id = str(interaction.user.id)
        Servidor_id = str(interaction.guild.id)

        self.cursor.execute("SELECT * FROM personajes WHERE Nombre=%s AND Servidor_id=%s", (Nombre, Servidor_id))
        if self.cursor.fetchone():
            return await interaction.response.send_message("Ya existe un personaje con ese nombre en este servidor.")
        
        self.cursor.execute("""
            INSERT INTO personajes (User_id, Servidor_id, Nombre, Trasfondo, Imagen)
            VALUES (%s, %s, %s, %s, %s)
        """, (User_id, Servidor_id, Nombre, Trasfondo, Imagen))
        self.conn.commit()

        await interaction.response.send_message(f"{interaction.user.mention}, tu personaje **{Nombre}** fue registrado y espera aprobación.")

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="aprobar", description="Aprobar un personaje (solo admins)")
    async def aprobar(self, interaction: discord.Interaction, Nombre: str):
        Servidor_id = str(interaction.guild.id)

        self.cursor.execute("UPDATE personajes SET Aprobado=1 WHERE Nombre=%s AND Servidor_id=%s", (Nombre, Servidor_id))
        if self.cursor.rowcount == 0:
            return await interaction.response.send_message("No encontré un personaje con ese nombre.")
        self.conn.commit()

        await interaction.response.send_message (f"El personaje **{Nombre}** fue aprobado.")

    @app_commands.command(name="eliminar", description="Eliminar un personaje propio o si eres admin")
    async def eliminar(self, interaction: discord.Interaction, Nombre: str):
        Servidor_id = str(interaction.guild.id)
        User_id = str(interaction.user.id)

        self.cursor.execute("SELECT User_id FROM personajes WHERE Nombre=%s AND Servidor_id=%s", (Nombre, Servidor_id))
        personaje = self.cursor.fetchone()

        if not personaje:
            return await interaction.response.send_message("No encontré un personaje con ese nombre.")

        dueño_id = personaje[0]

        if interaction.user.guild_permissions.administrator or User_id == dueño_id:
            self.cursor.execute("DELETE FROM personajes WHERE Nombre=%s AND Servidor_id=%s", (Nombre, Servidor_id))
            self.conn.commit()
            return await interaction.response.send_message(f"El personaje **{Nombre}** fue eliminado.")
        else:
            return await interaction.response.send_message("No puedes eliminar un personaje que no es tuyo.")

    @app_commands.command(name="ficha", description="Revisar Fichas del Usuario")
    async def ficha(self, interaction: discord.Interaction, Nombre: str = None):
            Servidor_id = str(interaction.guild.id)

            if Nombre:  
                self.cursor.execute("SELECT User_id, Nombre, Trasfondo, Imagen, Aprobado FROM personajes WHERE Nombre=%s AND Servidor_id=%s", (Nombre, Servidor_id))
                personaje = self.cursor.fetchone()

                if not personaje:
                    return await interaction.response.send_message ("No encontré un personaje con ese nombre.")

                user_id, Nombre, Trasfondo, Imagen, Aprobado = personaje
                estado = "Aprobado" if Aprobado == 1 else "Pendiente"

                miembro = interaction.guild.get_member(int(user_id))
                dueño = miembro.display_name if miembro else user_id

                embed = discord.Embed(title=f"Ficha de {Nombre}", description=Trasfondo, color=discord.Color.dark_gold())
                embed.add_field(name="Estado", value=estado, inline=False)
                embed.set_footer(text=f"Dueño: {dueño}")
                if Imagen:
                    embed.set_thumbnail(url=Imagen)

                return await interaction.response.send_message(embed=embed)

            else: 
                User_id = str(interaction.user.id)
                self.cursor.execute("SELECT Nombre FROM personajes WHERE User_id=%s AND Servidor_id=%s", (User_id, Servidor_id))
                personajes = self.cursor.fetchall()

                if not personajes:
                    return await interaction.response.send_message("No tienes personajes registrados en este servidor.")

                embed = discord.Embed(title=f"Personajes de {interaction.user.display_name}", color=discord.Color.dark_gold())
                for p in personajes:
                    embed.add_field(name="Nombre", value=p[0], inline=False)

                return await interaction.response.send_message(embed=embed)
            
async def setup(bot):
    await bot.add_cog(Personajes(bot))

