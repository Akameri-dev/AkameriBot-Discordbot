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
        atributo="Nombre del atributo (ataque_base, defensa_base, agilidad_base)",
        valor="Valor numérico del atributo"
    )
    async def establecer_atributo_base(self, interaction: discord.Interaction, atributo: str, valor: int):
        if atributo not in ['ataque_base', 'defensa_base', 'agilidad_base']:
            await interaction.response.send_message("Atributo no válido. Usa: ataque_base, defensa_base o agilidad_base", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Atributo base **{atributo}** establecido en **{valor}** para todos los personajes nuevos.",
            ephemeral=True
        )

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
        await self._tirar_dado_combate(interaction, personaje, "ataque")

    @dado.command(name="defensa", description="Realiza una tirada de defensa")
    @app_commands.describe(personaje="Nombre del personaje")
    async def tirar_defensa(self, interaction: discord.Interaction, personaje: str):
        await self._tirar_dado_combate(interaction, personaje, "defensa")

    @dado.command(name="esquive", description="Realiza una tirada de esquive")
    @app_commands.describe(personaje="Nombre del personaje")
    async def tirar_esquive(self, interaction: discord.Interaction, personaje: str):
        await self._tirar_dado_combate(interaction, personaje, "agilidad")

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
            atributo_base = attributes.get(f"{tipo}_base", 5)
            
            # Buscar items equipados que modifiquen este atributo
            cur.execute("""
                SELECT i.attack, i.defense, i.effects, inv.equipped_slot
                FROM inventory inv
                JOIN items i ON inv.item_id = i.id
                JOIN characters c ON inv.character_id = c.id
                WHERE c.guild_id = %s AND c.name = %s AND inv.equipped_slot IS NOT NULL
            """, (str(interaction.guild.id), personaje))
            
            items_equipados = cur.fetchall()
            
            dado_final = f"1d{atributo_base}"
            modificadores = []
            
            for attack, defense, effects, slot in items_equipados:
                efectos_dict = self._safe_json_load(effects) or {}
                
                # Aplicar efectos del item
                for efecto, valor in efectos_dict.items():
                    if tipo in efecto.lower():
                        if isinstance(valor, (int, float)):
                            atributo_base += valor
                            modificadores.append(f"{efecto}: {valor:+}")
                        elif isinstance(valor, str):
                            # Parsear expresiones como "ataque +1"
                            if f"{tipo} +" in valor.lower():
                                try:
                                    bonus = int(valor.split('+')[1].strip())
                                    atributo_base += bonus
                                    modificadores.append(f"{efecto}: +{bonus}")
                                except:
                                    pass
            
            # Aplicar dados específicos del item equipado
            for attack, defense, effects, slot in items_equipados:
                if tipo == "ataque" and attack:
                    dado_final = attack
                    break
                elif tipo == "defensa" and defense:
                    dado_final = defense
                    break

            # Realizar tirada de dados
            dados_cog = self.bot.get_cog('Dados')
            if hasattr(dados_cog, 'procesar_expresion'):
                resultado, detalles, expandida = dados_cog.procesar_expresion(dado_final)
                
                embed = discord.Embed(
                    title=f"Tirada de {tipo.capitalize()} - {personaje}",
                    color=discord.Color.dark_gold()
                )
                
                embed.add_field(name="Dado", value=f"`{dado_final}`", inline=True)
                embed.add_field(name="Resultado", value=f"**{resultado}**", inline=True)
                
                if modificadores:
                    embed.add_field(name="Modificadores", value="\n".join(modificadores), inline=False)
                
                embed.add_field(name="Detalles", value=f"```{detalles}```", inline=False)
                
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("Error: módulo de dados no disponible.", ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message("Error al realizar la tirada.", ephemeral=True)
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