import discord
from discord import app_commands
from discord.ext import commands
import json

class Personajes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @property
    def conn(self):
        return self.bot.conn

    personaje = app_commands.Group(name="personaje", description="Gestión de personajes")

    @personaje.command(name="registrar", description="Crea tu personaje en este servidor")
    @app_commands.describe(
        nombre="Nombre del personaje",
        genero="Género del personaje",
        edad="Edad del personaje",
        imagen="URL de imagen para el personaje (opcional)",
        historia="Historia del personaje (opcional)",
        rasgos="Rasgos del personaje separados por comas (opcional)"
    )
    async def crear_personaje(self, interaction: discord.Interaction, nombre: str, genero: str = None, edad: int = None, 
                             imagen: str = None, historia: str = None, rasgos: str = None):
        cur = self.conn.cursor()
        try:
            # Verificar si el personaje ya existe
            cur.execute("SELECT id FROM characters WHERE guild_id=%s AND name=%s", (str(interaction.guild.id), nombre))
            if cur.fetchone():
                await interaction.response.send_message("Ya existe un personaje con ese nombre en este servidor.", ephemeral=True)
                return

            # Convertir rasgos a lista JSON
            rasgos_lista = []
            if rasgos:
                rasgos_lista = [r.strip() for r in rasgos.split(",") if r.strip()]

            # Insertar el personaje
            cur.execute("""
                INSERT INTO characters (user_id, guild_id, name, gender, age, image, lore, traits, attributes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            """, (str(interaction.user.id), str(interaction.guild.id), nombre, genero, edad, imagen, historia, json.dumps(rasgos_lista)))
            self.conn.commit()

            await interaction.response.send_message(f"Personaje **{nombre}** creado con éxito.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"No se pudo crear el personaje: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @personaje.command(name="ver", description="Muestra la ficha de un personaje")
    async def ver_personaje(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()

        try:
            # Obtener información básica del personaje
            cur.execute("""
                SELECT name, gender, age, attributes, traits, lore, image, approved, user_id, id
                FROM characters
                WHERE guild_id=%s AND name=%s
            """, (str(interaction.guild.id), nombre))
            row = cur.fetchone()

            if not row:
                await interaction.response.send_message("No encontré ese personaje.", ephemeral=True)
                return

            name, gender, age, attributes, traits, lore, image, approved, user_id, char_id = row

            is_owner = str(interaction.user.id) == user_id
            is_admin = interaction.user.guild_permissions.administrator
            
            if not approved and not is_owner and not is_admin:
                await interaction.response.send_message("Este personaje aún no ha sido aprobado y solo puede ser visto por su dueño o administradores.", ephemeral=True)
                return

            # Obtener items equipados y sus efectos
            cur.execute("""
                SELECT i.effects, i.attack, i.defense, inv.equipped_slot
                FROM inventory inv
                JOIN items i ON inv.item_id = i.id
                WHERE inv.character_id=%s AND inv.equipped_slot IS NOT NULL
            """, (char_id,))
            
            items_equipados = cur.fetchall()

            # Procesar atributos base y bonificaciones
            atributos_base = attributes or {}
            bonificaciones = {}
            items_activos = []

            for effects, attack, defense, slot in items_equipados:
                if effects:
                    try:
                        efectos_dict = json.loads(effects) if isinstance(effects, str) else effects
                        for attr, valor in efectos_dict.items():
                            if isinstance(valor, (int, float)):
                                if attr not in bonificaciones:
                                    bonificaciones[attr] = 0
                                bonificaciones[attr] += valor
                    except:
                        pass
                
                # Registrar item activo
                items_activos.append(slot)

            # Crear embed
            embed = discord.Embed(
                title=f"{name}",
                description=lore or "",
                color=discord.Color.dark_gold()
            )
            
            embed.add_field(name="Género", value=gender or "No definido", inline=True)
            embed.add_field(name="Edad", value=age or "Desconocida", inline=True)
            
            # Atributos con bonificaciones
            if atributos_base:
                atributos_str = ""
                for attr, valor_base in atributos_base.items():
                    bono = bonificaciones.get(attr, 0)
                    if bono != 0:
                        valor_final = valor_base + bono
                        simbolo = "+" if bono > 0 else ""
                        atributos_str += f"**{attr}**: {valor_base} ({simbolo}{bono}) = {valor_final}\n"
                    else:
                        atributos_str += f"**{attr}**: {valor_base}\n"
                
                embed.add_field(name="Atributos", value=atributos_str, inline=False)
            else:
                embed.add_field(name="Atributos", value="Ninguno", inline=False)
            
            # Items equipados
            if items_activos:
                embed.add_field(name="Equipado en", value=", ".join(items_activos), inline=True)
            else:
                embed.add_field(name="Equipado", value="Nada", inline=True)
            
            # Rasgos
            if traits and len(traits) > 0:
                rasgos_str = "\n".join([f"• {trait}" for trait in traits])
                embed.add_field(name="Rasgos", value=rasgos_str, inline=False)
            else:
                embed.add_field(name="Rasgos", value="Ninguno", inline=False)
                
            embed.add_field(name="Estado", value="Aprobado" if approved else "Pendiente", inline=True)
            
            if image:
                embed.set_image(url=image)
                
            if is_admin:
                try:
                    owner = await interaction.guild.fetch_member(int(user_id))
                    owner_name = owner.display_name
                except:
                    owner_name = f"Usuario con ID {user_id}"
                embed.set_footer(text=f"Dueño: {owner_name}")

            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"Error al mostrar el personaje: {str(e)}", ephemeral=True)
        finally:
            cur.close()
    
    @personaje.command(name="agregar_rasgo", description="Agrega rasgos a un personaje (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        nombre="Nombre del personaje",
        rasgos="Rasgos a agregar, separados por comas"
    )
    async def agregar_rasgo(self, interaction: discord.Interaction, nombre: str, rasgos: str):
        cur = self.conn.cursor()
        
        try:
            # Verificar que el personaje existe
            cur.execute("SELECT traits FROM characters WHERE guild_id=%s AND name=%s", 
                       (str(interaction.guild.id), nombre))
            resultado = cur.fetchone()
            
            if not resultado:
                await interaction.response.send_message("No encontré ese personaje.", ephemeral=True)
                return
                
            # Obtener rasgos actuales
            rasgos_actuales = resultado[0] or []
            
            # Convertir nuevos rasgos a lista
            nuevos_rasgos = [r.strip() for r in rasgos.split(",") if r.strip()]
            
            # Filtrar rasgos que ya existen
            rasgos_a_agregar = [r for r in nuevos_rasgos if r not in rasgos_actuales]
            
            if not rasgos_a_agregar:
                await interaction.response.send_message("Todos los rasgos ya existen en el personaje.", ephemeral=True)
                return
                
            # Combinar rasgos
            todos_los_rasgos = rasgos_actuales + rasgos_a_agregar
            
            # Actualizar en la base de datos
            cur.execute("""
                UPDATE characters 
                SET traits = %s::jsonb 
                WHERE guild_id=%s AND name=%s
            """, (json.dumps(todos_los_rasgos), str(interaction.guild.id), nombre))
            
            self.conn.commit()
            
            await interaction.response.send_message(
                f"Rasgos agregados a **{nombre}**: {', '.join(rasgos_a_agregar)}", 
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message(f"Error al agregar rasgos: {str(e)}", ephemeral=True)
        finally:
            cur.close()
    
    @personaje.command(name="eliminar_rasgo", description="Elimina rasgos de un personaje (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        nombre="Nombre del personaje",
        rasgos="Rasgos a eliminar, separados por comas"
    )
    async def eliminar_rasgo(self, interaction: discord.Interaction, nombre: str, rasgos: str):
        cur = self.conn.cursor()
        
        try:
            # Verificar que el personaje existe
            cur.execute("SELECT traits FROM characters WHERE guild_id=%s AND name=%s", 
                       (str(interaction.guild.id), nombre))
            resultado = cur.fetchone()
            
            if not resultado:
                await interaction.response.send_message("No encontré ese personaje.", ephemeral=True)
                return
                
            # Obtener rasgos actuales
            rasgos_actuales = resultado[0] or []
            
            # Convertir rasgos a eliminar a lista
            rasgos_a_eliminar = [r.strip() for r in rasgos.split(",") if r.strip()]
            
            # Filtrar rasgos que existen
            rasgos_existentes = [r for r in rasgos_a_eliminar if r in rasgos_actuales]
            
            if not rasgos_existentes:
                await interaction.response.send_message("Ninguno de los rasgos existe en el personaje.", ephemeral=True)
                return
                
            # Eliminar rasgos
            nuevos_rasgos = [r for r in rasgos_actuales if r not in rasgos_existentes]
            
            # Actualizar en la base de datos
            cur.execute("""
                UPDATE characters 
                SET traits = %s::jsonb 
                WHERE guild_id=%s AND name=%s
            """, (json.dumps(nuevos_rasgos), str(interaction.guild.id), nombre))
            
            self.conn.commit()
            
            await interaction.response.send_message(
                f"Rasgos eliminados de **{nombre}**: {', '.join(rasgos_existentes)}", 
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.response.send_message(f"Error al eliminar rasgos: {str(e)}", ephemeral=True)
        finally:
            cur.close()
    
    @personaje.command(name="eliminar", description="Elimina un personaje (solo dueño o admin)")
    async def eliminar_personaje(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        
        try:
            cur.execute("""
                SELECT user_id FROM characters 
                WHERE guild_id=%s AND name=%s
            """, (str(interaction.guild.id), nombre))
            result = cur.fetchone()
            
            if not result:
                await interaction.response.send_message("No encontré ese personaje.", ephemeral=True)
                return
                
            owner_id = result[0]
            is_owner = str(interaction.user.id) == owner_id
            is_admin = interaction.user.guild_permissions.administrator
            
            if not is_owner and not is_admin:
                await interaction.response.send_message("Solo el dueño del personaje o un administrador puede eliminarlo.", ephemeral=True)
                return
                
            cur.execute("""
                DELETE FROM characters 
                WHERE guild_id=%s AND name=%s
            """, (str(interaction.guild.id), nombre))
            self.conn.commit()
            
            await interaction.response.send_message(f"Personaje **{nombre}** eliminado con éxito.", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message("Ocurrió un error al eliminar el personaje.", ephemeral=True)
        finally:
            cur.close()
    
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

        await interaction.response.send_message(f"Personaje **{result[0]}** ha sido aprobado.", ephemeral=False)

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

        embed = discord.Embed(title="Personajes del servidor", color=discord.Color.dark_gold())
        for name, approved in rows:
            estado = "✅ Aprobado" if approved else "⏳ Pendiente"
            embed.add_field(name=name, value=estado, inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Personajes(bot))