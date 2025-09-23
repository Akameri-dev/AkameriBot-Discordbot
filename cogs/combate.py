import discord
from discord import app_commands
from discord.ext import commands
import random
import re
import json

class Combate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def conn(self):
        return self.bot.conn

    atributo = app_commands.Group(name="atributo", description="Gestión de atributos de combate")
    dado = app_commands.Group(name="dado", description="Tiradas de dados de combate")

    @atributo.command(name="establecer", description="Establece un atributo base para todos los personajes nuevos (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        atributo="Nombre del atributo (Ataque, Defensa, Agilidad)",
        valor="Valor numérico del atributo"
    )
    async def establecer_atributo_base(self, interaction: discord.Interaction, atributo: str, valor: int):
        atributos_validos = ['Ataque', 'Defensa', 'Agilidad']
        if atributo not in atributos_validos:
            await interaction.response.send_message(f"Atributo no válido. Usa: {', '.join(atributos_validos)}", ephemeral=True)
            return

        # Actualizar todos los personajes existentes que no tengan este atributo
        cur = self.conn.cursor()
        try:
            cur.execute("""
                UPDATE characters 
                SET attributes = jsonb_set(
                    COALESCE(attributes, '{}'::jsonb), 
                    %s, 
                    %s::text::jsonb,
                    true
                )
                WHERE guild_id = %s AND NOT attributes ? %s
            """, (f"{{{atributo}}}", str(valor), str(interaction.guild.id), atributo))
            
            self.conn.commit()
            await interaction.response.send_message(
                f"Atributo base **{atributo}** establecido en **{valor}** para todos los personajes nuevos.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    @atributo.command(name="modificar", description="Modifica un atributo de un personaje específico")
    @app_commands.describe(
        personaje="Nombre del personaje",
        atributo="Nombre del atributo",
        valor="Nuevo valor del atributo"
    )
    async def modificar_atributo(self, interaction: discord.Interaction, personaje: str, atributo: str, valor: int):
        cur = self.conn.cursor()
        try:
            cur.execute("""
                UPDATE characters 
                SET attributes = jsonb_set(
                    COALESCE(attributes, '{}'::jsonb), 
                    %s, 
                    %s::text::jsonb,
                    true
                )
                WHERE guild_id = %s AND name = %s
            """, (f"{{{atributo}}}", str(valor), str(interaction.guild.id), personaje))
            
            self.conn.commit()
            
            if cur.rowcount > 0:
                await interaction.response.send_message(
                    f"Atributo **{atributo}** de **{personaje}** establecido en **{valor}**.",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message("Personaje no encontrado.", ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message("Error al modificar el atributo.", ephemeral=True)
        finally:
            cur.close()

    @dado.command(name="ataque", description="Realiza una tirada de ataque")
    @app_commands.describe(personaje="Nombre del personaje")
    async def tirar_ataque(self, interaction: discord.Interaction, personaje: str):
        await self._tirar_dado_combate(interaction, personaje, "Ataque")

    @dado.command(name="defensa", description="Realiza una tirada de defensa")
    @app_commands.describe(personaje="Nombre del personaje")
    async def tirar_defensa(self, interaction: discord.Interaction, personaje: str):
        await self._tirar_dado_combate(interaction, personaje, "Defensa")

    @dado.command(name="esquive", description="Realiza una tirada de esquive")
    @app_commands.describe(personaje="Nombre del personaje")
    async def tirar_esquive(self, interaction: discord.Interaction, personaje: str):
        await self._tirar_dado_combate(interaction, personaje, "Agilidad")

    async def _tirar_dado_combate(self, interaction: discord.Interaction, personaje: str, tipo: str):
        cur = self.conn.cursor()
        try:
            # Obtener atributo base del personaje
            cur.execute("""
                SELECT attributes FROM characters 
                WHERE guild_id = %s AND name = %s
            """, (str(interaction.guild.id), personaje))
            
            result = cur.fetchone()
            
            if not result:
                await interaction.response.send_message("Personaje no encontrado.", ephemeral=True)
                return

            attributes = result[0] or {}
            atributo_base = attributes.get(tipo, 5)  # Usar el nombre directamente (Ataque, Defensa, Agilidad)
            
            # Buscar items equipados que modifiquen este atributo
            cur.execute("""
                SELECT i.attack, i.defense, i.effects, inv.equipped_slot
                FROM inventory inv
                JOIN items i ON inv.item_id = i.id
                JOIN characters c ON inv.character_id = c.id
                WHERE c.guild_id = %s AND c.name = %s AND inv.equipped_slot IS NOT NULL
            """, (str(interaction.guild.id), personaje))
            
            items_equipados = cur.fetchall()
            
            # Valor base del atributo
            valor_final = atributo_base
            modificadores = []
            dado_personalizado = None
            
            # Aplicar modificadores de items equipados
            for attack, defense, effects, slot in items_equipados:
                efectos_dict = self._safe_json_load(effects) or {}
                
                # Buscar efectos que modifiquen este atributo
                for efecto, valor in efectos_dict.items():
                    if tipo.lower() in efecto.lower():
                        if isinstance(valor, (int, float)):
                            valor_final += valor
                            modificadores.append(f"{slot}: {efecto} {valor:+}")
            
            # Buscar dados personalizados del item equipado
            for attack, defense, effects, slot in items_equipados:
                if tipo == "Ataque" and attack:
                    dado_personalizado = attack
                    break
                elif tipo == "Defensa" and defense:
                    dado_personalizado = defense
                    break

            # Determinar la expresión del dado a usar
            if dado_personalizado:
                dado_expresion = dado_personalizado
                fuente_dado = f"Item equipado ({slot})"
            else:
                dado_expresion = f"1d{valor_final}"
                fuente_dado = f"Atributo {tipo}"

            # Realizar tirada de dados
            dados_cog = self.bot.get_cog('Dados')
            if dados_cog and hasattr(dados_cog, 'procesar_expresion'):
                resultado, detalles, expandida = dados_cog.procesar_expresion(dado_expresion)
            else:
                # Fallback: tirada simple
                if 'd' in dado_expresion:
                    partes = dado_expresion.split('d')
                    cantidad = int(partes[0]) if partes[0] else 1
                    caras = int(partes[1])
                    tiradas = [random.randint(1, caras) for _ in range(cantidad)]
                    resultado = sum(tiradas)
                    detalles = f"{cantidad}d{caras}: {tiradas} = {resultado}"
                else:
                    resultado = int(dado_expresion)
                    detalles = f"Valor fijo: {resultado}"

            # Crear embed organizado
            embed = discord.Embed(
                title=f"{tipo} - {personaje}",
                color=discord.Color.dark_gold()
            )
            
            # Información principal
            embed.add_field(
                name="Atributo Base", 
                value=f"**{atributo_base}**", 
                inline=True
            )
            
            embed.add_field(
                name="Dado", 
                value=f"`{dado_expresion}`\n*({fuente_dado})*", 
                inline=True
            )
            
            embed.add_field(
                name="💥 Resultado", 
                value=f"**{resultado}**", 
                inline=True
            )
            
            # Modificadores (si hay)
            if modificadores:
                embed.add_field(
                    name="Modificadores", 
                    value="\n".join(modificadores), 
                    inline=False
                )
            
            # Detalles de la tirada
            embed.add_field(
                name="Detalles", 
                value=f"```{detalles}```", 
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
                
        except Exception as e:
            await interaction.response.send_message(f"Error al realizar la tirada: {str(e)}", ephemeral=True)
        finally:
            cur.close()

    def _safe_json_load(self, data):
        """Carga JSON de forma segura"""
        if data is None:
            return {}
        if isinstance(data, dict):
            return data
        if isinstance(data, str):
            try:
                return json.loads(data)
            except:
                return {}
        return {}

async def setup(bot: commands.Bot):
    await bot.add_cog(Combate(bot))