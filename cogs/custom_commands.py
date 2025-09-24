import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import re

class CustomCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def conn(self):
        return self.bot.conn

    comando = app_commands.Group(name="comando", description="Sistema de comandos personalizados")

    # Helper functions simplificadas
    def _parse_requirement(self, req_str: str):
        """Parsea un requisito en formato tipo:valor - Solo objetos y roles"""
        if ':' not in req_str:
            return None, "Formato incorrecto. Usa: tipo:valor"
        
        req_type, value = req_str.split(':', 1)
        req_type = req_type.strip().lower()
        value = value.strip()
        
        # Solo permitir objetos y roles
        if req_type not in ['rol', 'item']:
            return None, "Solo se permiten requisitos de tipo 'rol' o 'item'"
        
        return {'type': req_type, 'value': value}, None

    def _parse_action(self, action_str: str):
        """Parsea una acción en formato tipo@parametros - Acciones simplificadas"""
        if '@' not in action_str:
            return None, "Formato incorrecto. Usa: tipo@parametros"
        
        action_type, params = action_str.split('@', 1)
        action_type = action_type.strip().lower()
        params = params.strip()
        
        # Solo acciones permitidas (quitamos dinero y experiencia)
        allowed_actions = ["mensaje", "embed", "imagen", "dado", "dar_item", "quitar_item", "efecto", "teleport"]
        if action_type not in allowed_actions:
            return None, f"Tipo de acción no permitido. Permitidos: {', '.join(allowed_actions)}"
        
        return {'type': action_type, 'params': params}, None

    def _execute_action(self, action_type: str, params: str, message: discord.Message):
        """Ejecuta una acción basada en su tipo - Versión simplificada"""
        try:
            if action_type == "mensaje":
                return params
            
            elif action_type == "embed":
                title, description = params.split('|', 1) if '|' in params else (params, "")
                embed = discord.Embed(title=title.strip(), description=description.strip(), color=discord.Color.dark_gold())
                return embed
            
            elif action_type == "imagen":
                return params.strip()
            
            elif action_type == "dado":
                if 'd' in params:
                    partes = params.split('d')
                    cantidad = int(partes[0]) if partes[0] else 1
                    caras = int(partes[1])
                    tiradas = [random.randint(1, caras) for _ in range(cantidad)]
                    resultado = sum(tiradas)
                    return f"🎲 {params}: {tiradas} = **{resultado}**"
                else:
                    return f"🎲 Dado: {params}"
            
            elif action_type == "dar_item":
                parts = params.split(',')
                if len(parts) >= 2:
                    item_name = parts[0].strip()
                    quantity = int(parts[1].strip())
                    # Lógica para dar item (simplificada)
                    return f"Recibes {quantity}x {item_name}"
                return "Error en formato: dar_item@nombre_item,cantidad"
            
            elif action_type == "quitar_item":
                parts = params.split(',')
                if len(parts) >= 2:
                    item_name = parts[0].strip()
                    quantity = int(parts[1].strip())
                    return f"Pierdes {quantity}x {item_name}"
                return "Error en formato: quitar_item@nombre_item,cantidad"
            
            elif action_type == "efecto":
                return f"Efecto aplicado: {params}"
            
            elif action_type == "teleport":
                return f"Teletransporte a: {params}"
            
            else:
                return f"Tipo de acción desconocido: {action_type}"
                
        except Exception as e:
            return f"Error ejecutando acción: {str(e)}"

    def _check_requirement(self, req_type: str, value: str, user: discord.Member, guild_id: str):
        """Verifica si un usuario cumple un requisito - Solo objetos y roles"""
        cur = self.conn.cursor()
        
        try:
            if req_type == "rol":
                # Verificar si el usuario tiene el rol
                role = discord.utils.get(user.roles, name=value)
                return role is not None
                
            elif req_type == "item":
                # Verificar si tiene el item
                parts = value.split(',')
                item_name = parts[0].strip()
                quantity = int(parts[1].strip()) if len(parts) > 1 else 1
                
                cur.execute("""
                    SELECT inv.quantity FROM inventory inv
                    JOIN characters c ON inv.character_id = c.id
                    JOIN items i ON inv.item_id = i.id
                    WHERE c.user_id=%s AND c.guild_id=%s AND c.approved=true AND i.name ILIKE %s
                """, (str(user.id), guild_id, item_name))
                result = cur.fetchone()
                return result and result[0] >= quantity
                
            else:
                return False
                
        finally:
            cur.close()

    # Comandos de administración
    @comando.command(name="crear", description="Crea un nuevo comando personalizado")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        nombre="Nombre del comando (se usará con .nombre)",
        descripcion="Descripción del comando",
        accion_principal="Acción principal (tipo@parametros)",
        requisito1="Requisito 1 (opcional) - formato: tipo:valor (solo rol o item)",
        requisito2="Requisito 2 (opcional)",
        requisito3="Requisito 3 (opcional)", 
        mensaje_respuesta="Mensaje de respuesta adicional (opcional)"
    )
    async def crear_comando(self, interaction: discord.Interaction, 
                          nombre: str, 
                          descripcion: str,
                          accion_principal: str,
                          requisito1: str = None,
                          requisito2: str = None,
                          requisito3: str = None,
                          mensaje_respuesta: str = None):
        
        cur = self.conn.cursor()
        try:
            # Verificar que el nombre no exista
            cur.execute("SELECT id FROM custom_commands WHERE guild_id=%s AND name=%s", 
                       (str(interaction.guild.id), nombre.lower()))
            if cur.fetchone():
                await interaction.response.send_message("Ya existe un comando con ese nombre.", ephemeral=True)
                return

            # Parsear acción principal
            accion, error = self._parse_action(accion_principal)
            if error:
                await interaction.response.send_message(f"{error}", ephemeral=True)
                return

            # Parsear requisitos
            requisitos = []
            for req in [requisito1, requisito2, requisito3]:
                if req:
                    requisito_parsed, error = self._parse_requirement(req)
                    if error:
                        await interaction.response.send_message(f"{error}", ephemeral=True)
                        return
                    requisitos.append(requisito_parsed)

            # Insertar en la base de datos
            cur.execute("""
                INSERT INTO custom_commands 
                (guild_id, name, description, main_action, requirements, response_message, created_by)
                VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
            """, (
                str(interaction.guild.id),
                nombre.lower(),
                descripcion,
                json.dumps(accion),
                json.dumps(requisitos),
                mensaje_respuesta,
                str(interaction.user.id)
            ))
            
            self.conn.commit()
            
            embed = discord.Embed(
                title="Comando Personalizado Creado",
                description=f"El comando `.{nombre}` ha sido creado exitosamente.",
                color=discord.Color.dark_gold()
            )
            embed.add_field(name="Descripción", value=descripcion, inline=False)
            embed.add_field(name="Acción Principal", value=accion_principal, inline=False)
            embed.add_field(name="Requisitos", value=str(len(requisitos)) or "Ninguno", inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error al crear el comando: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @comando.command(name="eliminar", description="Elimina un comando personalizado")
    @app_commands.checks.has_permissions(administrator=True)
    async def eliminar_comando(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("DELETE FROM custom_commands WHERE guild_id=%s AND name=%s", 
                       (str(interaction.guild.id), nombre.lower()))
            
            if cur.rowcount > 0:
                await interaction.response.send_message(f"Comando `.{nombre}` eliminado.", ephemeral=True)
            else:
                await interaction.response.send_message("Comando no encontrado.", ephemeral=True)
                
            self.conn.commit()
        finally:
            cur.close()

    @comando.command(name="lista", description="Lista todos los comandos personalizados del servidor")
    async def lista_comandos(self, interaction: discord.Interaction):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                SELECT name, description, main_action, requirements 
                FROM custom_commands 
                WHERE guild_id=%s 
                ORDER BY name
            """, (str(interaction.guild.id),))
            
            comandos = cur.fetchall()
            
            if not comandos:
                embed = discord.Embed(
                    title="Comandos Personalizados",
                    description="No hay comandos personalizados en este servidor.",
                    color=discord.Color.dark_gold()
                )
                await interaction.response.send_message(embed=embed)
                return
            
            embed = discord.Embed(
                title=f"Comandos Personalizados ({len(comandos)})",
                color=discord.Color.dark_gold()
            )
            
            for name, description, main_action, requirements in comandos:
                # Parsear acción principal
                accion = json.loads(main_action) if isinstance(main_action, str) else main_action
                accion_str = f"{accion['type']}@{accion['params']}"
                
                # Parsear requisitos
                reqs = json.loads(requirements) if requirements else []
                requisitos_str = ""
                for req in reqs:
                    requisitos_str += f"- {req['type']}: {req['value']}\n"
                
                if not requisitos_str:
                    requisitos_str = "Sin requisitos"
                
                embed.add_field(
                    name=f".{name}",
                    value=f"**Descripción:** {description}\n**Acción:** {accion_str}\n**Requisitos:**\n{requisitos_str}",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"Error al listar comandos: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @comando.command(name="info", description="Muestra información detallada de un comando")
    async def info_comando(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                SELECT name, description, main_action, requirements, response_message, created_by
                FROM custom_commands 
                WHERE guild_id=%s AND name=%s
            """, (str(interaction.guild.id), nombre.lower()))
            
            comando = cur.fetchone()
            
            if not comando:
                await interaction.response.send_message("Comando no encontrado.", ephemeral=True)
                return
            
            name, description, main_action, requirements, response_message, created_by = comando
            
            embed = discord.Embed(
                title=f"Información del comando .{name}",
                color=discord.Color.dark_gold()
            )
            
            embed.add_field(name="Descripción", value=description, inline=False)
            
            # Parsear acción principal
            accion = json.loads(main_action) if isinstance(main_action, str) else main_action
            embed.add_field(name="Acción Principal", value=f"`{accion['type']}@{accion['params']}`", inline=False)
            
            # Parsear requisitos
            reqs = json.loads(requirements) if requirements else []
            if reqs:
                requisitos_str = ""
                for req in reqs:
                    requisitos_str += f"- **{req['type']}:** {req['value']}\n"
                embed.add_field(name="Requisitos", value=requisitos_str, inline=False)
            else:
                embed.add_field(name="Requisitos", value="Ninguno", inline=False)
            
            if response_message:
                embed.add_field(name="Mensaje Adicional", value=response_message, inline=False)
            
            # Obtener información del creador
            try:
                creator = await interaction.guild.fetch_member(int(created_by))
                creator_name = creator.display_name if creator else "Usuario no encontrado"
            except:
                creator_name = "Usuario no encontrado"
            
            embed.set_footer(text=f"Creado por: {creator_name}")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    # Manejador de mensajes para comandos personalizados
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.content.startswith('.'):
            return
        
        if not message.guild:
            return
        
        command_name = message.content[1:].split()[0].lower()
        
        cur = self.conn.cursor()
        try:
            cur.execute("""
                SELECT main_action, requirements, response_message
                FROM custom_commands 
                WHERE guild_id=%s AND name=%s
            """, (str(message.guild.id), command_name))
            
            comando = cur.fetchone()
            
            if not comando:
                return
            
            main_action, requirements, response_message = comando
            
            # Parsear JSON
            accion = json.loads(main_action) if isinstance(main_action, str) else main_action
            requisitos = json.loads(requirements) if requirements else []
            
            # Verificar requisitos
            for req in requisitos:
                if not self._check_requirement(req['type'], req['value'], message.author, str(message.guild.id)):
                    await message.channel.send(
                        f"{message.author.mention} No cumples los requisitos para usar este comando.",
                        delete_after=10
                    )
                    return
            
            # Ejecutar la acción principal
            resultado = self._execute_action(accion['type'], accion['params'], message)
            
            # Enviar respuesta
            if isinstance(resultado, str):
                response_text = resultado
                if response_message:
                    response_text += f"\n\n{response_message}"
                await message.channel.send(response_text)
            elif isinstance(resultado, discord.Embed):
                if response_message:
                    resultado.description = f"{resultado.description}\n\n{response_message}" if resultado.description else response_message
                await message.channel.send(embed=resultado)
            else:
                await message.channel.send("Error al ejecutar el comando.")
                
        except Exception as e:
            print(f"Error en comando personalizado: {e}")
        finally:
            cur.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(CustomCommands(bot))