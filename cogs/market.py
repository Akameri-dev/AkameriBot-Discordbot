import random
import json
import math
import discord
from discord import app_commands
from discord.ext import commands

class Market(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def conn(self):
        return self.bot.conn

    mercado = app_commands.Group(name="mercado", description="Sistema de mercados del servidor")

    def _item_id_by_name(self, cur, name: str):
        """Obtiene el ID de un item por su nombre"""
        cur.execute("SELECT id FROM items WHERE lower(name)=lower(%s) LIMIT 1", (name,))
        r = cur.fetchone()
        return r[0] if r else None

    def _parse_price_spec(self, price_spec: str, cur):
        """Convierte 'madera*2, piedra*1' en lista de componentes"""
        if not price_spec or not price_spec.strip():
            return [], None
        
        partes = [p.strip() for p in price_spec.split(",") if p.strip()]
        price_list = []
        
        for p in partes:
            if "*" in p:
                name, qty = p.split("*", 1)
                name = name.strip()
                qty = max(1, int(qty.strip()))
            else:
                name, qty = p.strip(), 1
            
            item_id = self._item_id_by_name(cur, name)
            if not item_id:
                return None, f"Item no encontrado: {name}"
            
            price_list.append({"item_id": item_id, "qty": qty})
        
        return price_list, None

    def _format_price_for_display(self, price_json, cur):
        """Formatea un precio para mostrarlo en la tabla"""
        if not price_json:
            return "N/A"
        
        try:
            price_data = json.loads(price_json) if isinstance(price_json, str) else price_json
            if not price_data or price_data == []:
                return "GRATIS"
            
            components = []
            for comp in price_data:
                cur.execute("SELECT name FROM items WHERE id = %s", (comp["item_id"],))
                item_name = cur.fetchone()[0]
                components.append(f"{comp['qty']}x{item_name}")
            
            return ", ".join(components)
        except:
            return "ERROR"

    @mercado.command(name="crear", description="Crear un mercado en este servidor (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    async def crear_mercado(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", 
                       (str(interaction.guild.id), nombre))
            if cur.fetchone():
                await interaction.response.send_message("Ya existe un mercado con ese nombre.", ephemeral=True)
                return
            
            cur.execute("INSERT INTO markets (guild_id, name, created_by) VALUES (%s,%s,%s)",
                        (str(interaction.guild.id), nombre, str(interaction.user.id)))
            self.conn.commit()
            
            embed = discord.Embed(
                title="Mercado Creado",
                description=f"El mercado **{nombre}** ha sido creado exitosamente.",
                color=discord.Color.dark_gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Error al crear el mercado: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @mercado.command(name="eliminar", description="Eliminar un mercado y sus listados (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    async def eliminar_mercado(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("DELETE FROM markets WHERE guild_id=%s AND lower(name)=lower(%s) RETURNING id", 
                       (str(interaction.guild.id), nombre))
            r = cur.fetchone()
            if not r:
                await interaction.response.send_message("No se encontró ese mercado.", ephemeral=True)
                return
            
            self.conn.commit()
            
            embed = discord.Embed(
                title="Mercado Eliminado",
                description=f"El mercado **{nombre}** ha sido eliminado.",
                color=discord.Color.dark_gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Error al eliminar el mercado: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @mercado.command(name="add_item", description="Añadir un item a un mercado con hasta 3 precios (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        mercado_nombre="Nombre del mercado",
        item_nombre="Nombre del item",
        precio1="Precio principal (ej: madera*2, oro*1)",
        precio2="Precio alternativo 1 (opcional)",
        precio3="Precio alternativo 2 (opcional)",
        stock_inicial="Stock inicial (opcional)"
    )
    async def add_item(self, interaction: discord.Interaction, mercado_nombre: str, item_nombre: str,
                      precio1: str, precio2: str = None, precio3: str = None, stock_inicial: int = None):
        cur = self.conn.cursor()
        try:
            # Verificar mercado
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", 
                       (str(interaction.guild.id), mercado_nombre))
            mercado = cur.fetchone()
            if not mercado:
                await interaction.response.send_message("Mercado no encontrado.", ephemeral=True)
                return
            market_id = mercado[0]

            # Verificar item
            item_id = self._item_id_by_name(cur, item_nombre)
            if not item_id:
                await interaction.response.send_message("Item no encontrado.", ephemeral=True)
                return

            # Parsear precios
            price1, error = self._parse_price_spec(precio1, cur)
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return

            price2, error = self._parse_price_spec(precio2, cur) if precio2 else ([], None)
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return

            price3, error = self._parse_price_spec(precio3, cur) if precio3 else ([], None)
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return

            # Stock inicial
            if stock_inicial is None:
                stock_inicial = random.randint(1, 10)

            # Insertar en la base de datos
            cur.execute("""
                INSERT INTO market_listings 
                (market_id, item_id, price, price2, price3, initial_price, initial_price2, initial_price3,
                 initial_stock, base_stock, current_stock)
                VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
                ON CONFLICT (market_id, item_id) 
                DO UPDATE SET 
                    price = EXCLUDED.price,
                    price2 = EXCLUDED.price2,
                    price3 = EXCLUDED.price3,
                    current_stock = EXCLUDED.current_stock
            """, (
                market_id, item_id,
                json.dumps(price1),
                json.dumps(price2) if price2 else '[]',
                json.dumps(price3) if price3 else '[]',
                json.dumps(price1),
                json.dumps(price2) if price2 else '[]',
                json.dumps(price3) if price3 else '[]',
                stock_inicial, stock_inicial, stock_inicial
            ))
            
            self.conn.commit()
            
            embed = discord.Embed(
                title="Item Añadido al Mercado",
                description=f"El item **{item_nombre}** ha sido añadido al mercado **{mercado_nombre}**.",
                color=discord.Color.dark_gold()
            )
            embed.add_field(name="Stock inicial", value=str(stock_inicial), inline=True)
            embed.add_field(name="Precio 1", value=self._format_price_for_display(json.dumps(price1), cur), inline=True)
            
            if price2:
                embed.add_field(name="Precio 2", value=self._format_price_for_display(json.dumps(price2), cur), inline=True)
            if price3:
                embed.add_field(name="Precio 3", value=self._format_price_for_display(json.dumps(price3), cur), inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Error al añadir el item: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @mercado.command(name="remove_item", description="Quitar un item de un mercado (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_item(self, interaction: discord.Interaction, mercado_nombre: str, item_nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", 
                       (str(interaction.guild.id), mercado_nombre))
            mercado = cur.fetchone()
            if not mercado:
                await interaction.response.send_message("Mercado no encontrado.", ephemeral=True)
                return
            market_id = mercado[0]

            item_id = self._item_id_by_name(cur, item_nombre)
            if not item_id:
                await interaction.response.send_message("Item no encontrado.", ephemeral=True)
                return

            cur.execute("DELETE FROM market_listings WHERE market_id=%s AND item_id=%s RETURNING id", 
                       (market_id, item_id))
            resultado = cur.fetchone()
            
            if not resultado:
                await interaction.response.send_message("Este item no estaba en el mercado.", ephemeral=True)
                return
            
            self.conn.commit()
            
            embed = discord.Embed(
                title="Item Removido",
                description=f"El item **{item_nombre}** ha sido removido del mercado **{mercado_nombre}**.",
                color=discord.Color.dark_gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Error al remover el item: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @mercado.command(name="lista", description="Lista todos los mercados del servidor")
    async def lista_mercados(self, interaction: discord.Interaction):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT name FROM markets WHERE guild_id=%s ORDER BY name", 
                       (str(interaction.guild.id),))
            mercados = [row[0] for row in cur.fetchall()]
            
            if not mercados:
                embed = discord.Embed(
                    title="Mercados del Servidor",
                    description="No hay mercados creados en este servidor.",
                    color=discord.Color.dark_gold()
                )
            else:
                embed = discord.Embed(
                    title="Mercados del Servidor",
                    description="\n".join([f"• {nombre}" for nombre in mercados]),
                    color=discord.Color.dark_gold()
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message("Error al obtener la lista de mercados.", ephemeral=True)
        finally:
            cur.close()

    @mercado.command(name="ver", description="Muestra los items y precios de un mercado en formato tabla")
    async def ver_mercado(self, interaction: discord.Interaction, mercado_nombre: str):
        cur = self.conn.cursor()
        try:
            # Verificar mercado
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", 
                       (str(interaction.guild.id), mercado_nombre))
            mercado = cur.fetchone()
            if not mercado:
                await interaction.response.send_message("Mercado no encontrado.", ephemeral=True)
                return
            market_id = mercado[0]

            # Obtener items del mercado
            cur.execute("""
                SELECT i.name, ml.price, ml.price2, ml.price3, ml.current_stock
                FROM market_listings ml
                JOIN items i ON ml.item_id = i.id
                WHERE ml.market_id = %s
                ORDER BY i.name
            """, (market_id,))
            
            items = cur.fetchall()

            if not items:
                embed = discord.Embed(
                    title=f"Mercado: {mercado_nombre}",
                    description="Este mercado no tiene items disponibles.",
                    color=discord.Color.dark_gold()
                )
                await interaction.response.send_message(embed=embed)
                return

            # Crear tabla en formato texto
            table_lines = []
            table_lines.append("```")
            table_lines.append("ITEM                 | STOCK | PRECIO 1")
            table_lines.append("-" * 50)

            for name, price1, price2, price3, stock in items:
                # Formatear nombre
                name_display = name[:18] + ".." if len(name) > 20 else name.ljust(20)
                
                # Formatear stock
                stock_display = str(stock).ljust(5)
                
                # Formatear precio 1
                precio1_display = self._format_price_for_display(price1, cur)
                if len(precio1_display) > 25:
                    precio1_display = precio1_display[:22] + "..."
                precio1_display = precio1_display.ljust(25)
                
                table_lines.append(f"{name_display} | {stock_display} | {precio1_display}")

            table_lines.append("```")

            # Crear embed principal
            embed = discord.Embed(
                title=f"Mercado: {mercado_nombre}",
                description="\n".join(table_lines),
                color=discord.Color.dark_gold()
            )

            # Agregar precios alternativos como fields separados
            for name, price1, price2, price3, stock in items:
                has_alternative_prices = False
                price2_display = self._format_price_for_display(price2, cur) if price2 and price2 != '[]' else None
                price3_display = self._format_price_for_display(price3, cur) if price3 and price3 != '[]' else None
                
                if price2_display and price2_display != "N/A":
                    embed.add_field(
                        name=f"{name} - Precio 2",
                        value=price2_display,
                        inline=True
                    )
                    has_alternative_prices = True
                
                if price3_display and price3_display != "N/A":
                    embed.add_field(
                        name=f"{name} - Precio 3", 
                        value=price3_display,
                        inline=True
                    )
                    has_alternative_prices = True

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"Error al mostrar el mercado: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @mercado.command(name="comprar", description="Comprar item de un mercado")
    @app_commands.describe(
        mercado_nombre="Nombre del mercado",
        personaje="Nombre del personaje",
        item_nombre="Nombre del item",
        precio_elegido="Número del precio a usar (1, 2 o 3)",
        cantidad="Cantidad a comprar"
    )
    async def comprar(self, interaction: discord.Interaction, mercado_nombre: str, personaje: str,
                     item_nombre: str, precio_elegido: int = 1, cantidad: int = 1):
        cur = self.conn.cursor()
        try:
            if cantidad < 1:
                await interaction.response.send_message("La cantidad debe ser al menos 1.", ephemeral=True)
                return

            # Verificar personaje
            cur.execute("SELECT id, user_id FROM characters WHERE guild_id=%s AND name=%s", 
                       (str(interaction.guild.id), personaje))
            char_info = cur.fetchone()
            if not char_info:
                await interaction.response.send_message("Personaje no encontrado.", ephemeral=True)
                return
            char_id, owner_id = char_info

            # Verificar permisos
            if str(interaction.user.id) != owner_id and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("No tienes permisos para usar este personaje.", ephemeral=True)
                return

            # Verificar mercado y item
            cur.execute("""
                SELECT ml.id, ml.price, ml.price2, ml.price3, ml.current_stock, i.id
                FROM market_listings ml
                JOIN items i ON ml.item_id = i.id
                JOIN markets m ON ml.market_id = m.id
                WHERE m.guild_id = %s AND m.name = %s AND i.name = %s
            """, (str(interaction.guild.id), mercado_nombre, item_nombre))
            
            listing = cur.fetchone()
            if not listing:
                await interaction.response.send_message("Item no encontrado en el mercado.", ephemeral=True)
                return

            listing_id, price1, price2, price3, stock, item_id = listing

            # Seleccionar precio
            precios = [price1, price2, price3]
            if precio_elegido < 1 or precio_elegido > 3:
                await interaction.response.send_message("El precio debe ser 1, 2 o 3.", ephemeral=True)
                return
            
            precio_json = precios[precio_elegido - 1]
            if not precio_json or precio_json == '[]':
                await interaction.response.send_message("Este precio no está disponible.", ephemeral=True)
                return

            # Verificar stock
            if stock < cantidad:
                await interaction.response.send_message("Stock insuficiente.", ephemeral=True)
                return

            # Parsear precio
            try:
                precio = json.loads(precio_json) if isinstance(precio_json, str) else precio_json
            except:
                await interaction.response.send_message("Error en el formato del precio.", ephemeral=True)
                return

            # Verificar que el personaje tiene los recursos
            for componente in precio:
                cur.execute("SELECT quantity FROM inventory WHERE character_id=%s AND item_id=%s", 
                           (char_id, componente["item_id"]))
                inv_row = cur.fetchone()
                cantidad_necesaria = componente["qty"] * cantidad
                
                if not inv_row or inv_row[0] < cantidad_necesaria:
                    cur.execute("SELECT name FROM items WHERE id=%s", (componente["item_id"],))
                    item_name = cur.fetchone()[0]
                    await interaction.response.send_message(
                        f"No tienes suficiente {item_name}. Necesitas {cantidad_necesaria}, tienes {inv_row[0] if inv_row else 0}.",
                        ephemeral=True
                    )
                    return

            # Realizar transacción
            # 1. Quitar recursos del comprador
            for componente in precio:
                cantidad_necesaria = componente["qty"] * cantidad
                cur.execute("UPDATE inventory SET quantity = quantity - %s WHERE character_id=%s AND item_id=%s", 
                           (cantidad_necesaria, char_id, componente["item_id"]))
                # Eliminar si la cantidad llega a 0
                cur.execute("DELETE FROM inventory WHERE character_id=%s AND item_id=%s AND quantity <= 0", 
                           (char_id, componente["item_id"]))

            # 2. Añadir item comprado al inventario
            cur.execute("""
                INSERT INTO inventory (character_id, item_id, quantity)
                VALUES (%s, %s, %s)
                ON CONFLICT (character_id, item_id)
                DO UPDATE SET quantity = inventory.quantity + EXCLUDED.quantity
            """, (char_id, item_id, cantidad))

            # 3. Actualizar stock del mercado
            cur.execute("UPDATE market_listings SET current_stock = current_stock - %s WHERE id=%s", 
                       (cantidad, listing_id))

            self.conn.commit()

            # Mensaje de confirmación
            embed = discord.Embed(
                title="Compra Exitosa",
                description=f"**{personaje}** ha comprado **{cantidad}x {item_nombre}** del mercado **{mercado_nombre}**.",
                color=discord.Color.dark_gold()
            )
            
            # Mostrar el precio pagado
            precio_pagado = []
            for componente in precio:
                cur.execute("SELECT name FROM items WHERE id=%s", (componente["item_id"],))
                item_name = cur.fetchone()[0]
                precio_pagado.append(f"{componente['qty'] * cantidad}x {item_name}")
            
            embed.add_field(name="Precio pagado", value=", ".join(precio_pagado), inline=False)
            embed.add_field(name="Stock restante", value=str(stock - cantidad), inline=True)
            
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"Error durante la compra: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @mercado.command(name="inflacion", description="Aplica inflación a TODOS los items en todos los mercados (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        porcentaje="Porcentaje de inflación (puede ser negativo)"
    )
    async def inflacion(self, interaction: discord.Interaction, porcentaje: float):
        cur = self.conn.cursor()
        try:
            ratio = 1.0 + (porcentaje / 100.0)

            # Obtener todos los listings del servidor
            cur.execute("""
                SELECT ml.id, ml.price, ml.price2, ml.price3 
                FROM market_listings ml
                JOIN markets m ON ml.market_id = m.id
                WHERE m.guild_id = %s
            """, (str(interaction.guild.id),))
            
            rows = cur.fetchall()
            modified = 0

            for listing_id, price1, price2, price3 in rows:
                precios = [price1, price2, price3]
                nuevos_precios = []
                changed = False

                for precio_json in precios:
                    if not precio_json or precio_json == '[]':
                        nuevos_precios.append(precio_json)
                        continue

                    try:
                        precio = json.loads(precio_json) if isinstance(precio_json, str) else precio_json
                        nuevo_precio = []
                        
                        for componente in precio:
                            # Aplicar inflación a CADA componente del precio
                            new_qty = max(1, math.ceil(componente["qty"] * ratio))
                            nuevo_precio.append({"item_id": componente["item_id"], "qty": new_qty})
                            changed = True
                        
                        nuevos_precios.append(json.dumps(nuevo_precio))
                    except Exception as e:
                        print(f"Error procesando precio: {e}")
                        nuevos_precios.append(precio_json)

                if changed:
                    cur.execute("""
                        UPDATE market_listings 
                        SET price = %s::jsonb, price2 = %s::jsonb, price3 = %s::jsonb
                        WHERE id = %s
                    """, (nuevos_precios[0], nuevos_precios[1], nuevos_precios[2], listing_id))
                    modified += 1

            self.conn.commit()
            
            embed = discord.Embed(
                title="Inflación Aplicada",
                description=f"Se aplicó {porcentaje}% de inflación a TODOS los items en todos los precios del mercado.",
                color=discord.Color.dark_gold()
            )
            embed.add_field(name="Listings modificados", value=str(modified), inline=True)
            
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"Error al aplicar inflación: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @mercado.command(name="reiniciar_inflacion", description="Reinicia TODOS los precios a los valores iniciales (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    async def reiniciar_inflacion(self, interaction: discord.Interaction):
        cur = self.conn.cursor()
        try:
            # Obtener todos los listings del servidor para contar cuántos se van a modificar
            cur.execute("""
                SELECT COUNT(*) 
                FROM market_listings ml
                JOIN markets m ON ml.market_id = m.id
                WHERE m.guild_id = %s
            """, (str(interaction.guild.id),))
            
            total_listings = cur.fetchone()[0]

            # Reiniciar todos los precios a sus valores iniciales
            cur.execute("""
                UPDATE market_listings 
                SET price = initial_price, 
                    price2 = initial_price2, 
                    price3 = initial_price3
                FROM markets
                WHERE market_listings.market_id = markets.id 
                AND markets.guild_id = %s
            """, (str(interaction.guild.id),))
            
            modified = cur.rowcount
            self.conn.commit()
            
            embed = discord.Embed(
                title="Inflación Reiniciada",
                description="Todos los precios han sido restablecidos a sus valores iniciales.",
                color=discord.Color.dark_gold()
            )
            embed.add_field(name="Listings modificados", value=f"{modified}/{total_listings}", inline=True)
            
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"Error al reiniciar la inflación: {str(e)}", ephemeral=True)
        finally:
            cur.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(Market(bot))