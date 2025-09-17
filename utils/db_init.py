import psycopg2
import os

def init_db(conn):
    with open("sql/schema.sql", "r", encoding="utf-8") as f:
        sql = f.read()
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
