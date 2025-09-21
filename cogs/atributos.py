import discord
from discord import app_commands
from discord.ext import commands

class Atributos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @property
    def conn(self):
            return self.bot.conn

    atributos = app_commands.Group(name="atributos", description="Gestión de atributos")
    

    @atributos.command(name="crear", description="Crea un nuevo atributo en el servidor (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    async def atributo_crear(self, interaction: discord.Interaction, nombre: str, default: int = 0, min_value: int = None, max_value: int = None):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO attribute_defs (name, default_value, min_value, max_value)
                VALUES (%s, %s, %s, %s)
            """, (nombre, default, min_value, max_value))
            self.conn.commit()
            await interaction.response.send_message(f"Atributo **{nombre}** creado.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(" se atributo ya existe.", ephemeral=True)
        finally:
            cur.close()

    @atributos.command(name="set", description="Asigna un valor de atributo a un personaje")
    async def atributo_set(self, interaction: discord.Interaction, personaje: str, atributo: str, valor: int):
        cur = self.conn.cursor()

        # validar personaje
        cur.execute("SELECT id, attributes FROM characters WHERE guild_id=%s AND name=%s",
                    (str(interaction.guild.id), personaje))
        pj = cur.fetchone()
        if not pj:
            await interaction.response.send_message("No existe ese personaje.", ephemeral=True)
            cur.close()
            return
        personaje_id, attributes = pj
        attributes = attributes or {}

        cur.execute("SELECT min_value, max_value FROM attribute_defs WHERE name=%s", (atributo,))
        atr = cur.fetchone()
        if not atr:
            await interaction.response.send_message("Ese atributo no está definido.", ephemeral=True)
            cur.close()
            return

        min_val, max_val = atr
        if min_val is not None and valor < min_val:
            await interaction.response.send_message(f"El valor mínimo de {atributo} es {min_val}.", ephemeral=True)
            cur.close()
            return
        if max_val is not None and valor > max_val:
            await interaction.response.send_message(f"El valor máximo de {atributo} es {max_val}.", ephemeral=True)
            cur.close()
            return

        # actualizar JSONB
        cur.execute("""
            UPDATE characters
            SET attributes = jsonb_set(attributes, %s, %s, true)
            WHERE id=%s
        """, (f'{{{atributo}}}', str(valor), personaje_id))
        self.conn.commit()
        cur.close()

        await interaction.response.send_message(f"{atributo} de **{personaje}** ahora es {valor}.", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = Atributos(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.atributos)
