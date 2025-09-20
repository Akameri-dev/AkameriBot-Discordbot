import discord
from discord import app_commands
from discord.ext import commands
import json

class Items(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def conn(self):
        return self.bot.conn


    item = app_commands.Group(name="item", description="Gestión de ítems del servidor")


    @item.command(name="crear", description="Crea un nuevo ítem global en el servidor (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    async def crear_item(
        self, 
        interaction: discord.Interaction, 
        nombre: str,
        categoria: str = None,
        descripcion: str = None,
        efectos: str = None,     
        usos: str = None,        
        craft: str = None,       
        decompose: str = None,   
    ):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO items (name, category, description, effects, uses, craft, decompose)
                VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
            """, (
                nombre, 
                categoria, 
                descripcion, 
                efectos or '{}', 
                usos or '{}', 
                craft or '{}', 
                decompose or '{}'
            ))
            self.conn.commit()
            await interaction.response.send_message(f"Ítem **{nombre}** creado con éxito.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"No se pudo crear el ítem: {str(e)}", ephemeral=True)
        finally:
            cur.close()


    @item.command(name="ver", description="Muestra la información de un ítem")
    async def ver_item(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT name, category, description, effects, uses, craft, decompose, created_at
            FROM items WHERE name=%s
        """, (nombre,))
        row = cur.fetchone()
        cur.close()

        if not row:
            await interaction.response.send_message("No encontré ese ítem.", ephemeral=True)
            return

        name, category, description, effects, uses, craft, decompose, created_at = row

        embed = discord.Embed(
            title=f"Ítem: {name}", 
            description=description or "Sin descripción.",
            color=discord.Color.green()
        )
        embed.add_field(name="Categoría", value=category or "Ninguna", inline=True)
        embed.add_field(name="Creado el", value=str(created_at.date()), inline=True)

        if effects and effects != {}:
            embed.add_field(name="Efectos", value=json.dumps(effects, indent=2), inline=False)
        if uses and uses != {}:
            embed.add_field(name="Usos", value=json.dumps(uses, indent=2), inline=False)
        if craft and craft != {}:
            embed.add_field(name="Receta", value=json.dumps(craft, indent=2), inline=False)
        if decompose and decompose != {}:
            embed.add_field(name="Descompone en", value=json.dumps(decompose, indent=2), inline=False)

        await interaction.response.send_message(embed=embed)


    @item.command(name="lista", description="Muestra todos los ítems del servidor")
    async def lista_items(self, interaction: discord.Interaction):
        cur = self.conn.cursor()
        cur.execute("SELECT name, category FROM items ORDER BY name ASC")
        rows = cur.fetchall()
        cur.close()

        if not rows:
            await interaction.response.send_message("No hay ítems registrados aún.", ephemeral=True)
            return


        embed = discord.Embed(title="Lista de Ítems", color=discord.Color.purple())
        for name, category in rows:
            embed.add_field(name=name, value=f"Categoría: {category or 'Ninguna'}", inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Items(bot))
