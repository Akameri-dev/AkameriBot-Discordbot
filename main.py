
import os
import asyncio
import discord
from dotenv import load_dotenv
from discord.ext import commands
from utils.db_init import init_db
import psycopg2

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Conexión DB (la dejamos global y la guardamos en bot)
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
init_db(conn)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix='.',
    intents=intents,
    help_command=None,
    activity=discord.Activity(type=discord.ActivityType.watching, name=".Help | AkameriBot"),
    status=discord.Status.do_not_disturb,
)

# Exponer conexión al resto de cogs
bot.conn = conn

# Lista de cogs que vas a cargar (ajusta nombres si tus ficheros son distintos)
COGS = [
    "cogs.dados",
    "cogs.personajes",   
    "cogs.atributos",
    "cogs.item",
    "cogs.inventario",
    "cogs.market",
    "cogs.craft",
    "utils.help",
]

async def load_cogs():
    for ext in COGS:
        try:
            await bot.load_extension(ext)
            print(f"[LOAD] Extension cargada: {ext}")
        except Exception as e:
            print(f"[ERROR LOAD] No se pudo cargar {ext}: {e}")

@bot.event
async def on_ready():
    print("=== bot.tree.walk_commands() antes sync ===")
    for c in bot.tree.walk_commands():
        print(" -", c.qualified_name)

    try:
        synced = await bot.tree.sync()
        print(f"Slash commands sincronizados: {len(synced)}")
        print("=== Comandos devueltos por sync ===")
        for c in synced:
            print(" *", getattr(c, "name", str(c)))
    except Exception as e:
        print(f"[ERROR] al sincronizar slash commands: {e}")

    print(f"Bot conectado como {bot.user}")


# Comando de prueba tradicional
@bot.command()
async def prueba(ctx):
    await ctx.send("chambea a la verga")

# Slash de prueba que siempre funciona (para comprobar infra)
@bot.tree.command(name="prueba", description="verificacion de los slash commands")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("No wey no quiero")


async def main():
    async with bot:
        # cargar extensiones antes de start evita condiciones raras
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    # si estás en render, sigue usando tu keep_alive si hace falta
    from webserver import keep_alive
    keep_alive()
    asyncio.run(main())
