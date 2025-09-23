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

    def _safe_json_load(self, data):
        """Carga JSON de forma segura, manejando diferentes tipos de entrada"""
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return {}
        return {}

    @item.command(name="crear", description="Crea un nuevo item global en el servidor (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        nombre="Nombre del item",
        categoria="Categoría del item (opcional)",
        descripcion="Descripción del item (opcional)",
        imagen="URL de la imagen del item (opcional)",
        efectos="Efectos en formato clave:valor (ej: fuerza:2,agilidad:1) (opcional)",
        usos="Usos en formato clave:valor (opcional)",
        craft="Componentes de crafteo: item1*2,item2*3 (opcional)",
        decompose="Componentes de descomposición: item1*1,item2*2 (opcional)"
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
            

            craft_json = await self._parse_receta_field(craft, cur)
            decompose_json = await self._parse_receta_field(decompose, cur)

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
            await interaction.response.send_message(f"Item **{nombre}** creado con éxito.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"No se pudo crear el ítem: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    async def _parse_receta_field(self, field_str, cur):
        """Convierte formato item1*2,item2*3 a [{"item_id": X, "qty": Y}]"""
        if not field_str:
            return []
        
        try:
            componentes = []
            for componente in field_str.split(','):
                if '*' in componente:
                    nombre, qty = componente.split('*', 1)
                    nombre = nombre.strip()
                    qty = int(qty.strip())
                    
                    cur.execute("SELECT id FROM items WHERE name=%s", (nombre,))
                    item_row = cur.fetchone()
                    if item_row:
                        componentes.append({"item_id": item_row[0], "qty": qty})
                    else:
                        componentes.append({"item_name": nombre, "qty": qty})
                else:
                    nombre = componente.strip()
                    cur.execute("SELECT id FROM items WHERE name=%s", (nombre,))
                    item_row = cur.fetchone()
                    if item_row:
                        componentes.append({"item_id": item_row[0], "qty": 1})
                    else:
                        componentes.append({"item_name": nombre, "qty": 1})
            
            return componentes
        except Exception as e:
            print(f"Error parseando receta: {e}")
            return []

    @item.command(name="ver", description="Muestra la información de un item")
    async def ver_item(self, interaction: discord.Interaction, nombre: str):
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT id, name, category, description, image, effects, uses, craft, decompose, created_at
                FROM items WHERE name=%s
            """, (nombre,))
            row = cur.fetchone()

            if not row:
                await interaction.response.send_message("No encontré ese item.", ephemeral=True)
                cur.close()
                return

            item_id, name, category, description, image, effects, uses, craft, decompose, created_at = row

            effects_dict = self._safe_json_load(effects)
            uses_dict = self._safe_json_load(uses)
            craft_data = self._safe_json_load(craft)
            decompose_data = self._safe_json_load(decompose)

            embed = discord.Embed(
                title=f"Item: {name}", 
                description=description or "Sin descripción.",
                color=discord.Color.dark_gold()
            )
            
            if image:
                embed.set_image(url=image)
                
            embed.add_field(name="Categoría", value=category or "Ninguna", inline=True)
            embed.add_field(name="Creado el", value=str(created_at.date()), inline=True)


            if effects_dict:
                efectos_str = "\n".join([f"**{k}**: {v}" for k, v in effects_dict.items()])
                embed.add_field(name="Efectos", value=efectos_str, inline=False)
            else:
                embed.add_field(name="Efectos", value="No tiene efectos", inline=False)
                
            if uses_dict:
                usos_str = "\n".join([f"**{k}**: {v}" for k, v in uses_dict.items()])
                embed.add_field(name="Usos", value=usos_str, inline=False)
            else:
                embed.add_field(name="Usos", value="No tiene usos definidos", inline=False)

            craft_str = await self._formatear_receta(craft_data, "craft", cur)
            if craft_str:
                embed.add_field(name="🛠️ Receta de Crafteo", value=craft_str, inline=False)
            else:
                cur.execute("SELECT components FROM recipes WHERE result_item_id=%s", (item_id,))
                recipe_row = cur.fetchone()
                if recipe_row:
                    recipe_components = self._safe_json_load(recipe_row[0])
                    recipe_str = await self._formatear_receta(recipe_components, "recipe", cur)
                    if recipe_str:
                        embed.add_field(name="🛠️ Receta de Crafteo (Sistema)", value=recipe_str, inline=False)
                    else:
                        embed.add_field(name="🛠️ Receta de Crafteo", value="No se puede craftear", inline=False)
                else:
                    embed.add_field(name="🛠️ Receta de Crafteo", value="No se puede craftear", inline=False)

            decompose_str = await self._formatear_receta(decompose_data, "decompose", cur)
            if decompose_str:
                embed.add_field(name="Descompone en", value=decompose_str, inline=False)
            else:
                embed.add_field(name="Descompone en", value="No se puede descomponer", inline=False)

            cur.close()
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"Error en ver_item: {e}")  
            await interaction.response.send_message("Ocurrió un error al mostrar el item.", ephemeral=True)

    async def _formatear_receta(self, data, tipo, cur):
        """Formatea recetas de crafteo/descomposición de manera compatible"""
        if not data:
            return None
        
        try:
            if isinstance(data, list):
                componentes = []
                for comp in data:
                    item_id = comp.get('item_id')
                    qty = comp.get('qty', 1)
                    if item_id:
                        cur.execute("SELECT name FROM items WHERE id=%s", (item_id,))
                        item_row = cur.fetchone()
                        if item_row:
                            componentes.append(f"**{item_row[0]}** x{qty}")
                        else:
                            componentes.append(f"Item ID {item_id} x{qty}")
                return "\n".join(componentes) if componentes else None
            
            elif isinstance(data, dict):
                componentes = []
                for item_name, qty in data.items():
                    componentes.append(f"**{item_name}** x{qty}")
                return "\n".join(componentes) if componentes else None
            
            return str(data)
        except Exception as e:
            print(f"Error formateando {tipo}: {e}")
            return None
        
    @item.command(name="lista", description="Muestra todos los ítems del servidor")
    async def lista_items(self, interaction: discord.Interaction):
            try:
                cur = self.conn.cursor()
                cur.execute("SELECT name, category FROM items ORDER BY name ASC")
                rows = cur.fetchall()
                cur.close()

                if not rows:
                    await interaction.response.send_message("No hay ítems registrados aún.", ephemeral=True)
                    return

                embed = discord.Embed(title="Lista de Items", color=discord.Color.dark_gold())
                
                categorias = {}
                for name, category in rows:
                    cat = category or "Sin categoría"
                    if cat not in categorias:
                        categorias[cat] = []
                    categorias[cat].append(name)
                
                for categoria, items in categorias.items():
                    embed.add_field(
                        name=f"**{categoria}**",
                        value="\n".join([f"• {item}" for item in items]),
                        inline=False
                    )

                await interaction.response.send_message(embed=embed)
                
            except Exception as e:
                await interaction.response.send_message("Error al obtener la lista de ítems.", ephemeral=True)

    @item.command(name="eliminar", description="Elimina un item del servidor (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(nombre="Nombre del item a eliminar")
    async def eliminar_item(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT name FROM items WHERE name = %s", (nombre,))
            if not cur.fetchone():
                await interaction.response.send_message("No existe un item con ese nombre.", ephemeral=True)
                return
            
            cur.execute("DELETE FROM items WHERE name = %s", (nombre,))
            self.conn.commit()
            
            await interaction.response.send_message(f"Item **{nombre}** eliminado correctamente.", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Error al eliminar el item: {str(e)}", ephemeral=True)
        finally:
            cur.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(Items(bot))