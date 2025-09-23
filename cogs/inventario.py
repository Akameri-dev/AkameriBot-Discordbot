import discord
from discord import app_commands
from discord.ext import commands
import json

class Inventario(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def conn(self):
        return self.bot.conn

    inventario = app_commands.Group(name="inventario", description="Gestión de inventarios de personajes")
    ranura = app_commands.Group(name="ranura", description="Gestión de ranuras de equipamiento", parent=inventario)

    @inventario.command(name="ver", description="Muestra el inventario de un personaje en formato tabla")
    async def ver_inventario(self, interaction: discord.Interaction, personaje: str):
        cur = self.conn.cursor()
        try:
            # Obtener información del personaje
            cur.execute("SELECT id FROM characters WHERE guild_id=%s AND name=%s", 
                       (str(interaction.guild.id), personaje))
            char_info = cur.fetchone()
            
            if not char_info:
                await interaction.response.send_message("Ese personaje no existe.", ephemeral=True)
                return

            char_id = char_info[0]

            # Obtener ranuras existentes
            cur.execute("SELECT name FROM equipment_slots WHERE guild_id=%s ORDER BY name", 
                       (str(interaction.guild.id),))
            ranuras = [row[0] for row in cur.fetchall()]

            # Crear la estructura de la tabla
            table_lines = []
            table_lines.append("```")
            table_lines.append("ITEM                 | CANT | USOS | RANURA")
            table_lines.append("-" * 50)

            # Primero: items equipados organizados por ranura
            for ranura in ranuras:
                cur.execute("""
                    SELECT i.name, inv.quantity, i.max_uses, inv.current_uses
                    FROM inventory inv
                    JOIN items i ON inv.item_id = i.id
                    WHERE inv.character_id=%s AND inv.equipped_slot=%s AND inv.quantity > 0
                    ORDER BY i.name
                """, (char_id, ranura))
                
                items_ranura = cur.fetchall()
                if items_ranura:
                    table_lines.append(f"--- {ranura.upper()} ---")
                    
                    for name, quantity, max_uses, current_uses in items_ranura:
                        # Formatear nombre
                        name_display = name[:18] + ".." if len(name) > 20 else name.ljust(20)
                        
                        # Formatear cantidad
                        cant_display = str(quantity).ljust(4)
                        
                        # Formatear usos
                        if max_uses and max_uses > 0 and current_uses is not None:
                            usos_display = f"{current_uses}/{max_uses}".ljust(5)
                        else:
                            usos_display = "S/U".ljust(5)  # Cambiado de "Sin usos" a "S/U"
                        
                        # Formatear ranura (abreviado)
                        ranura_display = ranura[:6].ljust(6)
                        
                        table_lines.append(f"{name_display} | {cant_display} | {usos_display} | {ranura_display}")

            # Segundo: inventario general (no equipado)
            cur.execute("""
                SELECT i.name, inv.quantity, i.max_uses, inv.current_uses
                FROM inventory inv
                JOIN items i ON inv.item_id = i.id
                WHERE inv.character_id=%s AND inv.equipped_slot IS NULL AND inv.quantity > 0
                ORDER BY i.name
            """, (char_id,))
            
            items_general = cur.fetchall()
            if items_general:
                table_lines.append("--- INVENTARIO GENERAL ---")
                
                for name, quantity, max_uses, current_uses in items_general:
                    name_display = name[:18] + ".." if len(name) > 20 else name.ljust(20)
                    cant_display = str(quantity).ljust(4)
                    
                    if max_uses and max_uses > 0 and current_uses is not None:
                        usos_display = f"{current_uses}/{max_uses}".ljust(5)
                    else:
                        usos_display = "S/U".ljust(5)
                    
                    ranura_display = "LIBRE".ljust(6)
                    
                    table_lines.append(f"{name_display} | {cant_display} | {usos_display} | {ranura_display}")

            if len(table_lines) <= 3:
                table_lines.append("El inventario está vacío")

            table_lines.append("```")

            embed = discord.Embed(
                title=f"Inventario de {personaje}", 
                description="\n".join(table_lines),
                color=discord.Color.dark_gold()
            )

            # Agregar imagen de la mochila
            embed.set_thumbnail(url="https://media.discordapp.net/attachments/1193596513469866094/1419918116367892490/1-removebg-preview.png?ex=68d3814b&is=68d22fcb&hm=521fea6d3f76825029a9d2e83865c2266493b3fa8a00ec785817cd061b3b9c6e&=&format=webp&quality=lossless")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"Error al mostrar el inventario: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @inventario.command(name="limite", description="Establece el límite de items en el inventario general (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(limite="Número máximo de items en el inventario")
    async def establecer_limite(self, interaction: discord.Interaction, limite: int):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                INSERT INTO inventory_limits (guild_id, general_limit) 
                VALUES (%s, %s)
                ON CONFLICT (guild_id) 
                DO UPDATE SET general_limit = EXCLUDED.general_limit, updated_at = NOW()
            """, (str(interaction.guild.id), limite))
            
            self.conn.commit()
            
            embed = discord.Embed(
                title="Límite del Inventario Actualizado",
                description=f"El límite del inventario general se estableció en **{limite}** items.",
                color=discord.Color.dark_gold()
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message("Error al establecer el límite.", ephemeral=True)
        finally:
            cur.close()

    @ranura.command(name="crear", description="Crea una nueva ranura de equipamiento (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        nombre="Nombre de la ranura",
        limite="Límite de items que se pueden equipar en esta ranura",
        requiere_equipable="¿Requiere que el item sea equipable? (si/no, por defecto: no)"
    )
    async def crear_ranura(self, interaction: discord.Interaction, nombre: str, limite: int = 1, requiere_equipable: str = "no"):
        cur = self.conn.cursor()
        try:
            requiere_equipable_bool = requiere_equipable.lower() in ['sí', 'si', 's', 'yes', 'y', 'true', '1']
            
            cur.execute("""
                INSERT INTO equipment_slots (guild_id, name, slot_limit, requiere_equipable)
                VALUES (%s, %s, %s, %s)
            """, (str(interaction.guild.id), nombre, limite, requiere_equipable_bool))
            
            self.conn.commit()
            
            tipo_ranura = "equipable" if requiere_equipable_bool else "general"
            await interaction.response.send_message(
                f"Ranura **{nombre}** creada ({tipo_ranura}) con límite de **{limite}** item(s).", 
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message("Error al crear la ranura (¿ya existe?).", ephemeral=True)
        finally:
            cur.close()

    @ranura.command(name="eliminar", description="Elimina una ranura de equipamiento (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(nombre="Nombre de la ranura a eliminar")
    async def eliminar_ranura(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                DELETE FROM equipment_slots 
                WHERE guild_id=%s AND name=%s
            """, (str(interaction.guild.id), nombre))
            
            self.conn.commit()
            
            if cur.rowcount > 0:
                await interaction.response.send_message(f"Ranura **{nombre}** eliminada.", ephemeral=True)
            else:
                await interaction.response.send_message("No se encontró la ranura especificada.", ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message("Error al eliminar la ranura.", ephemeral=True)
        finally:
            cur.close()

    @ranura.command(name="lista", description="Muestra todas las ranuras de equipamiento")
    async def lista_ranuras(self, interaction: discord.Interaction):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                SELECT name, slot_limit, requiere_equipable 
                FROM equipment_slots 
                WHERE guild_id=%s 
                ORDER BY name
            """, (str(interaction.guild.id),))
            
            rows = cur.fetchall()
            
            if not rows:
                await interaction.response.send_message("No hay ranuras de equipamiento definidas.", ephemeral=True)
                return

            embed = discord.Embed(title="🔸 Ranuras de Equipamiento", color=discord.Color.dark_gold())
            
            for name, limit, requiere_equipable in rows:
                tipo = "🔹 Equipable" if requiere_equipable else "📦 General"
                embed.add_field(
                    name=f"{tipo}: {name}",
                    value=f"Límite: {limit} item(s)",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message("Error al obtener la lista de ranuras.", ephemeral=True)
        finally:
            cur.close()

    @inventario.command(name="equipar", description="Equipa un item en una ranura específica")
    @app_commands.describe(
        personaje="Nombre del personaje",
        item="Nombre del item a equipar",
        ranura="Nombre de la ranura donde equipar"
    )
    async def equipar_item(self, interaction: discord.Interaction, personaje: str, item: str, ranura: str):
        cur = self.conn.cursor()
        try:
            # Verificar que la ranura existe
            cur.execute("SELECT slot_limit, requiere_equipable FROM equipment_slots WHERE guild_id=%s AND name=%s", 
                       (str(interaction.guild.id), ranura))
            slot_info = cur.fetchone()
            
            if not slot_info:
                await interaction.response.send_message("Esa ranura no existe.", ephemeral=True)
                return

            slot_limit, requiere_equipable = slot_info

            # Verificar que el personaje existe
            cur.execute("SELECT id FROM characters WHERE guild_id=%s AND name=%s", 
                       (str(interaction.guild.id), personaje))
            char_info = cur.fetchone()
            
            if not char_info:
                await interaction.response.send_message("Ese personaje no existe.", ephemeral=True)
                return

            char_id = char_info[0]

            # Verificar que el item existe
            cur.execute("SELECT id, equipable FROM items WHERE name=%s", (item,))
            item_info = cur.fetchone()
            
            if not item_info:
                await interaction.response.send_message("Ese item no existe.", ephemeral=True)
                return

            item_id, equipable = item_info
            
            # Verificar si la ranura requiere que el item sea equipable
            if requiere_equipable and not equipable:
                await interaction.response.send_message("Esta ranura requiere items equipables.", ephemeral=True)
                return

            # Verificar que el personaje tiene el item
            cur.execute("""
                SELECT id, quantity FROM inventory 
                WHERE character_id=%s AND item_id=%s AND quantity > 0
            """, (char_id, item_id))
            inv_info = cur.fetchone()
            
            if not inv_info:
                await interaction.response.send_message("El personaje no tiene ese item.", ephemeral=True)
                return

            inv_id, quantity = inv_info

            # Verificar límite de la ranura
            cur.execute("""
                SELECT COUNT(*) FROM inventory 
                WHERE character_id=%s AND equipped_slot=%s
            """, (char_id, ranura))
            current_count = cur.fetchone()[0]
            
            if current_count >= slot_limit:
                await interaction.response.send_message(
                    f"La ranura **{ranura}** ya está llena (límite: {slot_limit}).", 
                    ephemeral=True
                )
                return

            # Equipar el item
            cur.execute("""
                UPDATE inventory 
                SET equipped_slot = %s 
                WHERE id = %s
            """, (ranura, inv_id))
            
            self.conn.commit()
            
            await interaction.response.send_message(
                f"**{item}** equipado en la ranura **{ranura}** para **{personaje}**.", 
                ephemeral=False
            )

        except Exception as e:
            await interaction.response.send_message(f"Error al equipar el item: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @inventario.command(name="desequipar", description="Desequipa un item")
    @app_commands.describe(
        personaje="Nombre del personaje",
        item="Nombre del item a desequipar"
    )
    async def desequipar_item(self, interaction: discord.Interaction, personaje: str, item: str):
        cur = self.conn.cursor()
        try:
            # Verificar que el personaje existe
            cur.execute("SELECT id FROM characters WHERE guild_id=%s AND name=%s", 
                       (str(interaction.guild.id), personaje))
            char_info = cur.fetchone()
            
            if not char_info:
                await interaction.response.send_message("Ese personaje no existe.", ephemeral=True)
                return

            char_id = char_info[0]

            # Verificar que el item existe
            cur.execute("SELECT id FROM items WHERE name=%s", (item,))
            item_info = cur.fetchone()
            
            if not item_info:
                await interaction.response.send_message("Ese item no existe.", ephemeral=True)
                return

            item_id = item_info[0]

            # Desequipar el item
            cur.execute("""
                UPDATE inventory 
                SET equipped_slot = NULL 
                WHERE character_id=%s AND item_id=%s AND equipped_slot IS NOT NULL
            """, (char_id, item_id))
            
            self.conn.commit()
            
            if cur.rowcount > 0:
                await interaction.response.send_message(f"**{item}** desequipado de **{personaje}**.", ephemeral=False)
            else:
                await interaction.response.send_message("El item no estaba equipado.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message("Error al desequipar el item.", ephemeral=True)
        finally:
            cur.close()

    @inventario.command(name="usar", description="Usa un item del inventario (reduce sus usos)")
    @app_commands.describe(
        personaje="Nombre del personaje",
        item="Nombre del item a usar",
        cantidad="Cantidad de usos a consumir (por defecto 1)"
    )
    async def usar_item(self, interaction: discord.Interaction, personaje: str, item: str, cantidad: int = 1):
        cur = self.conn.cursor()
        try:
            # Verificar personaje y item
            cur.execute("""
                SELECT c.id, i.id, i.max_uses, inv.id, inv.current_uses, inv.quantity
                FROM characters c
                JOIN items i ON i.name = %s
                JOIN inventory inv ON inv.character_id = c.id AND inv.item_id = i.id
                WHERE c.guild_id = %s AND c.name = %s AND inv.quantity > 0
            """, (item, str(interaction.guild.id), personaje))
            
            info = cur.fetchone()
            
            if not info:
                await interaction.response.send_message("Personaje o item no encontrado.", ephemeral=True)
                return

            char_id, item_id, max_uses, inv_id, current_uses, quantity = info

            # Si el item no tiene usos limitados
            if max_uses <= 0:
                await interaction.response.send_message("Este item no tiene usos limitados.", ephemeral=True)
                return

            # Si es la primera vez que se usa, establecer usos actuales
            if current_uses is None:
                current_uses = max_uses

            # Verificar usos suficientes
            if current_uses < cantidad:
                await interaction.response.send_message("No hay suficientes usos disponibles.", ephemeral=True)
                return

            new_uses = current_uses - cantidad

            # Si se agotan los usos, eliminar el item
            if new_uses <= 0:
                if quantity > 1:
                    # Reducir cantidad y resetear usos
                    cur.execute("""
                        UPDATE inventory 
                        SET quantity = quantity - 1, current_uses = NULL 
                        WHERE id = %s
                    """, (inv_id,))
                else:
                    # Eliminar el item
                    cur.execute("DELETE FROM inventory WHERE id = %s", (inv_id,))
                
                message = f"**{item}** se ha consumido completamente."
            else:
                # Reducir usos
                cur.execute("UPDATE inventory SET current_uses = %s WHERE id = %s", (new_uses, inv_id))
                message = f"**{item}** usado. Usos restantes: {new_uses}/{max_uses}"

            self.conn.commit()
            await interaction.response.send_message(message, ephemeral=False)

        except Exception as e:
            await interaction.response.send_message(f"Error al usar el item: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @inventario.command(name="transferir", description="Transfiere un item de un personaje a otro")
    async def transferir_item(
        self, interaction: discord.Interaction, origen: str, destino: str, item: str, cantidad: int = 1
    ):
        cur = self.conn.cursor()
        try:
            # Verificar personajes
            cur.execute("SELECT id FROM characters WHERE guild_id=%s AND name=%s", (str(interaction.guild.id), origen))
            pj_origen = cur.fetchone()
            cur.execute("SELECT id FROM characters WHERE guild_id=%s AND name=%s", (str(interaction.guild.id), destino))
            pj_destino = cur.fetchone()
            
            if not pj_origen or not pj_destino:
                await interaction.response.send_message("Alguno de los personajes no existe.", ephemeral=True)
                return

            # Verificar item
            cur.execute("SELECT id FROM items WHERE name=%s", (item,))
            item_row = cur.fetchone()
            if not item_row:
                await interaction.response.send_message("Ese item no existe.", ephemeral=True)
                return
            item_id = item_row[0]

            # Verificar cantidad disponible
            cur.execute("""
                SELECT quantity, current_uses 
                FROM inventory 
                WHERE character_id=%s AND item_id=%s
            """, (pj_origen[0], item_id))
            inv_row = cur.fetchone()
            
            if not inv_row or inv_row[0] < cantidad:
                await interaction.response.send_message("No hay suficiente cantidad en el inventario origen.", ephemeral=True)
                return

            # Transferir (restar del origen)
            cur.execute("""
                UPDATE inventory 
                SET quantity = quantity - %s 
                WHERE character_id=%s AND item_id=%s
            """, (cantidad, pj_origen[0], item_id))

            # Eliminar si la cantidad llega a 0
            cur.execute("DELETE FROM inventory WHERE character_id=%s AND item_id=%s AND quantity <= 0", 
                       (pj_origen[0], item_id))

            # Agregar al destino (copiar current_uses si existe)
            current_uses = inv_row[1]  # Puede ser None
            
            cur.execute("""
                INSERT INTO inventory (character_id, item_id, quantity, current_uses)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (character_id, item_id)
                DO UPDATE SET 
                    quantity = inventory.quantity + EXCLUDED.quantity,
                    current_uses = CASE 
                        WHEN inventory.current_uses IS NULL THEN EXCLUDED.current_uses
                        ELSE inventory.current_uses
                    END
            """, (pj_destino[0], item_id, cantidad, current_uses))

            self.conn.commit()
            await interaction.response.send_message(f"Se transfirieron {cantidad}x {item} de {origen} a {destino}.", ephemeral=False)
        
        except Exception as e:
            await interaction.response.send_message(f"Error en la transferencia: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @inventario.command(name="give", description="Añade ítems mágicamente a un inventario (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_item(self, interaction: discord.Interaction, personaje: str, item: str, cantidad: int = 1):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT id FROM characters WHERE guild_id=%s AND name=%s", 
                       (str(interaction.guild.id), personaje))
            char_info = cur.fetchone()
            
            if not char_info:
                await interaction.response.send_message("Personaje no encontrado.", ephemeral=True)
                return

            cur.execute("SELECT id, max_uses FROM items WHERE name=%s", (item,))
            item_info = cur.fetchone()
            
            if not item_info:
                await interaction.response.send_message("Item no encontrado.", ephemeral=True)
                return

            item_id, max_uses = item_info
            current_uses = max_uses if max_uses > 0 else None

            cur.execute("""
                INSERT INTO inventory (character_id, item_id, quantity, current_uses)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (character_id, item_id)
                DO UPDATE SET 
                    quantity = inventory.quantity + EXCLUDED.quantity,
                    current_uses = CASE 
                        WHEN EXCLUDED.current_uses IS NOT NULL THEN EXCLUDED.current_uses
                        ELSE inventory.current_uses
                    END
            """, (char_info[0], item_id, cantidad, current_uses))
            
            self.conn.commit()
            await interaction.response.send_message(f"{cantidad}x {item} añadidos mágicamente al inventario de {personaje}.", ephemeral=False)
        
        except Exception as e:
            await interaction.response.send_message(f"Error al dar el item: {str(e)}", ephemeral=True)
        finally:
            cur.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(Inventario(bot))