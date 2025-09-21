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

    def _parse_json_field(self, field_str):
        """Convierte una cadena en formato clave:valor a JSON válido"""
        if not field_str:
            return {}
        
        try:

            return json.loads(field_str)
        except json.JSONDecodeError:

            result = {}
            pairs = field_str.split(',')
            for pair in pairs:
                if ':' in pair:
                    key, value = pair.split(':', 1)
                    result[key.strip()] = value.strip()
            return result

    @item.command(name="crear", description="Crea un nuevo ítem global en el servidor (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        nombre="Nombre del ítem",
        categoria="Categoría del ítem (opcional)",
        descripcion="Descripción del ítem (opcional)",
        imagen="URL de la imagen del ítem (opcional)",
        efectos="Efectos en formato clave:valor (ej: fuerza:2,agilidad:1) (opcional)",
        usos="Usos en formato clave:valor (opcional)",
        craft="Componentes de crafteo en formato clave:valor (opcional)",
        decompose="Componentes de descomposición en formato clave:valor (opcional)"
    )
    async def crear_item(
        self, 
        interaction: discord.Interaction, 
        nombre: str,
        categoria: str = None,
        descripcion: str = None,
        imagen: str = None,
        efectos: str = None,
        usos: str = None,
        craft: str = None,
        decompose: str = None
    ):
        cur = self.conn.cursor()
        try:

            efectos_json = self._parse_json_field(efectos)
            usos_json = self._parse_json_field(usos)
            craft_json = self._parse_json_field(craft)
            decompose_json = self._parse_json_field(decompose)

            cur.execute("""
                INSERT INTO items (name, category, description, image, effects, uses, craft, decompose)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
            """, (
                nombre, 
                categoria, 
                descripcion, 
                imagen,
                json.dumps(efectos_json), 
                json.dumps(usos_json), 
                json.dumps(craft_json), 
                json.dumps(decompose_json)
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
            SELECT name, category, description, image, effects, uses, craft, decompose, created_at
            FROM items WHERE name=%s
        """, (nombre,))
        row = cur.fetchone()
        cur.close()

        if not row:
            await interaction.response.send_message("No encontré ese ítem.", ephemeral=True)
            return

        name, category, description, image, effects, uses, craft, decompose, created_at = row

        embed = discord.Embed(
            title=f"Ítem: {name}", 
            description=description or "Sin descripción.",
            color=discord.Color.green()
        )
        
        if image:
            embed.set_image(url=image)
            
        embed.add_field(name="Categoría", value=category or "Ninguna", inline=True)
        embed.add_field(name="Creado el", value=str(created_at.date()), inline=True)

        if effects and effects != {}:
            efectos_str = "\n".join([f"{k}: {v}" for k, v in effects.items()])
            embed.add_field(name="Efectos", value=efectos_str, inline=False)
            
        if uses and uses != {}:
            usos_str = "\n".join([f"{k}: {v}" for k, v in uses.items()])
            embed.add_field(name="Usos", value=usos_str, inline=False)
            
        if craft and craft != {}:
            craft_str = "\n".join([f"{k}: {v}" for k, v in craft.items()])
            embed.add_field(name="Receta", value=craft_str, inline=False)
            
        if decompose and decompose != {}:
            decompose_str = "\n".join([f"{k}: {v}" for k, v in decompose.items()])
            embed.add_field(name="Descompone en", value=decompose_str, inline=False)

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

        embed = discord.Embed(title="Lista de Ítems", color=discord.Color.dark_gold())
        
    
        categorias = {}
        for name, category in rows:
            cat = category or "Sin categoría"
            if cat not in categorias:
                categorias[cat] = []
            categorias[cat].append(name)
        
        for categoria, items in categorias.items():
            embed.add_field(
                name=f"**{categoria}**",
                value="\n".join([f"- {item}" for item in items]),
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @item.command(name="eliminar", description="Elimina un ítem del servidor (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(nombre="Nombre del ítem a eliminar")
    async def eliminar_item(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        try:
        
            cur.execute("SELECT name FROM items WHERE name = %s", (nombre,))
            if not cur.fetchone():
                await interaction.response.send_message("No existe un ítem con ese nombre.", ephemeral=True)
                return
            

            cur.execute("DELETE FROM items WHERE name = %s", (nombre,))
            self.conn.commit()
            
            await interaction.response.send_message(f"Ítem **{nombre}** eliminado correctamente.", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Error al eliminar el ítem: {str(e)}", ephemeral=True)
        finally:
            cur.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(Items(bot))