import sqlite3
from discord.ext import commands
import discord

class Personajes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("personajes.db")
        self.cursor = self.conn.cursor()
        self.crear_tablas()


    def crear_tablas(self):
        # Tabla de personajes
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS personajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            servidor_id TEXT,
            nombre TEXT,
            trasfondo TEXT,
            imagen TEXT,
            aprobado INTEGER DEFAULT 0,
            economia INTEGER DEFAULT 0,
            inventario TEXT DEFAULT '[]'
        )
        """)
        # Tabla de stats
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS estadisticas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stat_nombre TEXT,
            valor INTEGER
        )
        """)
        self.conn.commit()







async def setup(bot):
    await bot.add_cog(Personajes(bot))