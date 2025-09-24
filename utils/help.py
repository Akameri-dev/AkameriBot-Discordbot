import discord
from discord import app_commands
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Muestra la ayuda completa del bot")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎮 Sistema de RPG - Ayuda Completa",
            description="""**AkameriBot** es un bot de RPG completo con sistema de personajes, items, inventario, crafteo, mercado y combate.

**📋 Secciones disponibles:**
- 🎭 **Personajes**: Creación y gestión de personajes
- 🎒 **Items**: Sistema completo de objetos y equipamiento  
- 📦 **Inventario**: Gestión de inventarios y ranuras
- 🔨 **Crafteo**: Sistema de creación y descomposición
- 🏪 **Mercado**: Economía y comercio con múltiples precios
- ⚔️ **Combate**: Sistema de atributos y dados de combate
- ⚙️ **Comandos Personalizados**: Comandos creados por administradores""",
            color=discord.Color.dark_gold()
        )

        # Personajes
        embed.add_field(
            name="🎭 SISTEMA DE PERSONAJES",
            value="""`/personaje registrar` - Crear un nuevo personaje
`/personaje ver` - Ver ficha de personaje
`/personaje lista` - Listar todos los personajes
`/personaje aprobar` - Aprobar personaje (admin)
`/personaje eliminar` - Eliminar personaje
`/personaje agregar_rasgo` - Añadir rasgos (admin)
`/personaje eliminar_rasgo` - Quitar rasgos (admin)""",
            inline=False
        )

        # Items
        embed.add_field(
            name="🎒 SISTEMA DE ITEMS",
            value="""`/item crear` - Crear nuevo item (admin)
`/item ver` - Ver información de item
`/item lista` - Listar todos los items
`/item eliminar` - Eliminar item (admin)
`/item debug` - Información técnica de item (admin)

**Parámetros de items:**
- Equipable: Si/No
- Usos máximos: Número o ilimitados
- Ataque/Defensa: Dados personalizados
- Efectos: Modificadores de atributos
- Crafteo/Descomposición: Recetas""",
            inline=False
        )

        # Inventario
        embed.add_field(
            name="📦 SISTEMA DE INVENTARIO",
            value="""`/inventario ver` - Ver inventario en formato tabla
`/inventario transferir` - Transferir items entre personajes
`/inventario tirar` - Eliminar items del inventario
`/inventario usar` - Usar items con durabilidad
`/inventario give` - Dar items mágicamente (admin)
`/inventario limite` - Establecer límite de inventario (admin)

**Sistema de Ranuras:**
`/inventario ranura crear` - Crear ranura de equipamiento
`/inventario ranura eliminar` - Eliminar ranura
`/inventario ranura lista` - Listar ranuras
`/inventario equipar` - Equipar item en ranura
`/inventario desequipar` - Desequipar item""",
            inline=False
        )

        # Crafteo
        embed.add_field(
            name="🔨 SISTEMA DE CRAFTEO",
            value="""`/crafteo agregar` - Añadir receta de crafteo (admin)
`/crafteo lista` - Listar objetos crafteables
`/crafteo ver` - Ver receta de objeto
`/crafteo usar` - Craftear objeto

`/descomposicion agregar` - Añadir descomposición (admin)
`/descomposicion usar` - Descomponer objeto""",
            inline=False
        )

        # Mercado
        embed.add_field(
            name="🏪 SISTEMA DE MERCADO",
            value="""`/mercado crear` - Crear mercado (admin)
`/mercado eliminar` - Eliminar mercado (admin)
`/mercado lista` - Listar mercados
`/mercado ver` - Ver mercado en formato tabla
`/mercado add_item` - Añadir item con hasta 3 precios (admin)
`/mercado remove_item` - Quitar item (admin)
`/mercado comprar` - Comprar items
`/mercado inflacion` - Aplicar inflación (admin)

**Características:**
- Hasta 3 precios diferentes por item
- Sistema de stock dinámico
- Inflación aplicable a items específicos
- Interfaz tipo tabla profesional""",
            inline=False
        )

        # Combate
        embed.add_field(
            name="⚔️ SISTEMA DE COMBATE",
            value="""`/atributo establecer` - Establecer atributos base (admin)
`/atributo modificar` - Modificar atributos de personaje

`/dado ataque` - Tirada de ataque
`/dado defensa` - Tirada de defensa  
`/dado esquive` - Tirada de esquive

**Atributos base:**
- Ataque: Para tiradas ofensivas
- Defensa: Para tiradas defensivas
- Agilidad: Para esquivar y agilidad

**Items equipados** modifican automáticamente las tiradas.""",
            inline=False
        )

        # Comandos Personalizados
        embed.add_field(
            name="⚙️ COMANDOS PERSONALIZADOS",
            value="""`/comando crear` - Crear nuevo comando personalizado
`/comando editar` - Editar comando existente
`/comando eliminar` - Eliminar comando
`/comando lista` - Listar comandos disponibles
`/comando info` - Ver información de comando

**Uso:** Los comandos personalizados se ejecutan con punto (.) seguido del nombre:
`.nombrecomando`""",
            inline=False
        )

        embed.set_footer(text="Usa /help [comando] para más información sobre un comando específico")
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))