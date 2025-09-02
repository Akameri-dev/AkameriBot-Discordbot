
import sqlite3

conn = sqlite3.connect("personajes.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS personajes (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    User_id TEXT,
    Servidor_id TEXT,
    Nombre TEXT,
    Trasfondo TEXT,
    Imagen TEXT,
    Aprobado INTEGER DEFAULT 0
)
""")

conn.commit()
conn.close()

