import discord
from discord import app_commands
from discord.ext import commands

class Personajes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @property
    def conn(self):
            return self.bot.conn


    personaje = app_commands.Group(name="personaje", description="Gestión de personajes")

    @personaje.command(name="registrar", description="Crea tu personaje en este servidor")
    async def crear_personaje(self, interaction: discord.Interaction, nombre: str, genero: str = None, edad: int = None):
        cur = self.conn.cursor()

        try:
            cur.execute("""
                INSERT INTO characters (user_id, guild_id, name, gender, age)
                VALUES (%s, %s, %s, %s, %s)
            """, (str(interaction.user.id), str(interaction.guild.id), nombre, genero, edad))
            self.conn.commit()
            await interaction.response.send_message(f"Personaje **{nombre}** creado con éxito.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message("No se pudo crear el personaje (¿ya existe?).", ephemeral=True)
        finally:
            cur.close()

    @personaje.command(name="ver", description="Muestra la ficha de un personaje")
    async def ver_personaje(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()

        cur.execute("""
            SELECT name, gender, age, attributes, traits, lore, image, approved
            FROM characters
            WHERE guild_id=%s AND name=%s
        """, (str(interaction.guild.id), nombre))
        row = cur.fetchone()
        cur.close()

        if not row:
            await interaction.response.send_message("No encontré ese personaje.", ephemeral=True)
            return

        name, gender, age, attributes, traits, lore, image, approved = row

        embed = discord.Embed(title=f"{name}", description=lore or "", color=discord.Color.blue())
        embed.add_field(name="Género", value=gender or "No definido", inline=True)
        embed.add_field(name="Edad", value=age or "Desconocida", inline=True)
        embed.add_field(name="Atributos", value=str(attributes) if attributes else "Ninguno", inline=False)
        embed.add_field(name="Rasgos", value=", ".join(traits) if traits else "Ninguno", inline=False)
        embed.add_field(name="Estado", value="Aprobado" if approved else "Pendiente", inline=True)
        if image:
            embed.set_thumbnail(url=image)

        await interaction.response.send_message(embed=embed)
    
    @personaje.command(name="aprobar", description="Aprueba un personaje (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    async def aprobar_personaje(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE characters
            SET approved = TRUE
            WHERE guild_id=%s AND name=%s
            RETURNING name
        """, (str(interaction.guild.id), nombre))
        result = cur.fetchone()
        self.conn.commit()
        cur.close()

        if not result:
            await interaction.response.send_message("No encontré ese personaje.", ephemeral=True)
            return

        await interaction.response.send_message(f"✅ Personaje **{result[0]}** ha sido aprobado.", ephemeral=False)

    @personaje.command(name="lista", description="Lista todos los personajes del servidor")
    async def lista_personajes(self, interaction: discord.Interaction):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT name, approved FROM characters
            WHERE guild_id=%s
            ORDER BY name
        """, (str(interaction.guild.id),))
        rows = cur.fetchall()
        cur.close()

        if not rows:
            await interaction.response.send_message("No hay personajes registrados en este servidor.", ephemeral=True)
            return

        embed = discord.Embed(title="📜 Personajes del servidor", color=discord.Color.dark_gold())
        for name, approved in rows:
            estado = "✅ Aprobado" if approved else "⏳ Pendiente"
            embed.add_field(name=name, value=estado, inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Personajes(bot))