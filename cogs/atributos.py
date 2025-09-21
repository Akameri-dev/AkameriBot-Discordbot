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
    @app_commands.describe(
        nombre="Nombre del atributo",
        default="Valor por defecto",
        min_value="Valor mínimo (opcional)",
        max_value="Valor máximo (opcional)"
    )
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
            await interaction.response.send_message("Este atributo ya existe.", ephemeral=True)
        finally:
            cur.close()

    @atributos.command(name="set", description="Asigna un valor de atributo a un personaje")
    @app_commands.describe(
        personaje="Nombre del personaje",
        atributo="Nombre del atributo",
        valor="Valor a asignar"
    )
    async def atributo_set(self, interaction: discord.Interaction, personaje: str, atributo: str, valor: int):
        cur = self.conn.cursor()

        # Validar personaje
        cur.execute("SELECT id, attributes FROM characters WHERE guild_id=%s AND name=%s",
                    (str(interaction.guild.id), personaje))
        pj = cur.fetchone()
        if not pj:
            await interaction.response.send_message("No existe ese personaje.", ephemeral=True)
            cur.close()
            return
        personaje_id, attributes = pj
        attributes = attributes or {}

        # Validar atributo
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

        # Actualizar atributo
        cur.execute("""
            UPDATE characters
            SET attributes = jsonb_set(COALESCE(attributes, '{}'::jsonb), %s, %s, true)
            WHERE id=%s
        """, (f'{{{atributo}}}', str(valor), personaje_id))
        self.conn.commit()
        cur.close()

        await interaction.response.send_message(f"{atributo} de **{personaje}** ahora es {valor}.", ephemeral=True)

    @atributos.command(name="lista", description="Muestra todos los atributos definidos en el servidor")
    async def atributos_lista(self, interaction: discord.Interaction):
        cur = self.conn.cursor()
        
        try:
            cur.execute("SELECT name, default_value, min_value, max_value FROM attribute_defs ORDER BY name")
            atributos = cur.fetchall()
            
            if not atributos:
                await interaction.response.send_message("No hay atributos definidos en este servidor.", ephemeral=True)
                return
            
            embed = discord.Embed(title="Atributos Definidos", color=discord.Color.dark_gold())
            
            for nombre, default, min_val, max_val in atributos:
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM characters 
                    WHERE guild_id = %s 
                    AND attributes ? %s
                """, (str(interaction.guild.id), nombre))
                count = cur.fetchone()[0]
                
                # Formatear la información del atributo
                info = f"**Default:** {default}\n"
                if min_val is not None:
                    info += f"**Mínimo:** {min_val}\n"
                if max_val is not None:
                    info += f"**Máximo:** {max_val}\n"
                info += f"**Personajes con este atributo:** {count}"
                
                embed.add_field(name=nombre, value=info, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message("Error al obtener la lista de atributos.", ephemeral=True)
        finally:
            cur.close()

    @atributos.command(name="eliminar", description="Elimina un atributo definido (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(nombre="Nombre del atributo a eliminar")
    async def atributo_eliminar(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        
        try:

            cur.execute("SELECT name FROM attribute_defs WHERE name = %s", (nombre,))
            if not cur.fetchone():
                await interaction.response.send_message("No existe un atributo con ese nombre.", ephemeral=True)
                return
            
            cur.execute("DELETE FROM attribute_defs WHERE name = %s", (nombre,))
            self.conn.commit()
            
            await interaction.response.send_message(f"Atributo **{nombre}** eliminado correctamente.", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message("Error al eliminar el atributo.", ephemeral=True)
        finally:
            cur.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(Atributos(bot))