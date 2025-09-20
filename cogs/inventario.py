import discord
from discord import app_commands
from discord.ext import commands
import json

class Inventario(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def conn(self):
        return self.bot.conn

    inventario = app_commands.Group(name="inventario", description="Gestión de inventarios de personajes")

    @inventario.command(name="ver", description="Muestra el inventario de un personaje")
    async def ver_inventario(self, interaction: discord.Interaction, personaje: str):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT c.id, i.name, inv.quantity, inv.meta
            FROM characters c
            LEFT JOIN inventory inv ON c.id = inv.character_id
            LEFT JOIN items i ON inv.item_id = i.id
            WHERE c.guild_id=%s AND c.name=%s
        """, (str(interaction.guild.id), personaje))
        rows = cur.fetchall()
        cur.close()

        if not rows:
            await interaction.response.send_message("Ese personaje no existe o no tiene inventario.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Inventario de {personaje}", color=discord.Color.gold())
        for _, item_name, qty, meta in rows:
            if not item_name: 
                continue
            meta = meta or {}
            estado = "(Equipado)" if meta.get("equipado") else ""
            embed.add_field(name=item_name, value=f"{qty} {estado}", inline=False)

        await interaction.response.send_message(embed=embed)

    @inventario.command(name="transferir", description="Transfiere un ítem de un personaje a otro")
    async def transferir_item(
        self, interaction: discord.Interaction, origen: str, destino: str, item: str, cantidad: int
    ):
        cur = self.conn.cursor()
        try:

            cur.execute("SELECT id FROM characters WHERE guild_id=%s AND name=%s", (str(interaction.guild.id), origen))
            pj_origen = cur.fetchone()
            cur.execute("SELECT id FROM characters WHERE guild_id=%s AND name=%s", (str(interaction.guild.id), destino))
            pj_destino = cur.fetchone()
            if not pj_origen or not pj_destino:
                await interaction.response.send_message("Alguno de los personajes no existe.", ephemeral=True)
                return


            cur.execute("SELECT id FROM items WHERE name=%s", (item,))
            item_row = cur.fetchone()
            if not item_row:
                await interaction.response.send_message("Ese ítem no existe.", ephemeral=True)
                return
            item_id = item_row[0]


            cur.execute("SELECT quantity FROM inventory WHERE character_id=%s AND item_id=%s", (pj_origen[0], item_id))
            inv_row = cur.fetchone()
            if not inv_row or inv_row[0] < cantidad:
                await interaction.response.send_message("No hay suficiente cantidad en el inventario origen.", ephemeral=True)
                return

            cur.execute("UPDATE inventory SET quantity = quantity - %s WHERE character_id=%s AND item_id=%s",
                        (cantidad, pj_origen[0], item_id))

            cur.execute("DELETE FROM inventory WHERE character_id=%s AND item_id=%s AND quantity<=0",
                        (pj_origen[0], item_id))


            cur.execute("""
                INSERT INTO inventory (character_id, item_id, quantity)
                VALUES (%s, %s, %s)
                ON CONFLICT (character_id, item_id)
                DO UPDATE SET quantity = inventory.quantity + EXCLUDED.quantity
            """, (pj_destino[0], item_id, cantidad))

            self.conn.commit()
            await interaction.response.send_message(f"Se transfirieron {cantidad}x {item} de {origen} a {destino}.", ephemeral=False)
        finally:
            cur.close()


    @inventario.command(name="transferir_multiples", description="Transfiere múltiples ítems con formato espada*2,pocion*3")
    async def transferir_multiples(self, interaction: discord.Interaction, origen: str, destino: str, items: str):
        partes = [p.strip() for p in items.split(",")]
        for parte in partes:
            if "*" in parte:
                nombre, cantidad = parte.split("*")
                await self.transferir_item(interaction, origen, destino, nombre.strip(), int(cantidad))
            else:
                await self.transferir_item(interaction, origen, destino, parte.strip(), 1)


    @inventario.command(name="tirar", description="Tira un ítem de un inventario")
    async def tirar_item(self, interaction: discord.Interaction, personaje: str, item: str, cantidad: int):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT c.id FROM characters c WHERE c.guild_id=%s AND c.name=%s",
                        (str(interaction.guild.id), personaje))
            pj = cur.fetchone()
            if not pj:
                await interaction.response.send_message("Personaje no encontrado.", ephemeral=True)
                return

            cur.execute("SELECT id FROM items WHERE name=%s", (item,))
            it = cur.fetchone()
            if not it:
                await interaction.response.send_message("Ítem no encontrado.", ephemeral=True)
                return

            cur.execute("UPDATE inventory SET quantity = quantity - %s WHERE character_id=%s AND item_id=%s",
                        (cantidad, pj[0], it[0]))
            cur.execute("DELETE FROM inventory WHERE character_id=%s AND item_id=%s AND quantity<=0",
                        (pj[0], it[0]))
            self.conn.commit()
            await interaction.response.send_message(f"{personaje} tiró {cantidad}x {item}.", ephemeral=False)
        finally:
            cur.close()


    @inventario.command(name="equipar", description="Equipa un ítem de un inventario")
    async def equipar_item(self, interaction: discord.Interaction, personaje: str, item: str):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT c.id FROM characters c WHERE c.guild_id=%s AND c.name=%s",
                        (str(interaction.guild.id), personaje))
            pj = cur.fetchone()
            if not pj:
                await interaction.response.send_message("Personaje no encontrado.", ephemeral=True)
                return

            cur.execute("""
                UPDATE inventory
                SET meta = jsonb_set(meta, '{equipado}', 'true', true)
                WHERE character_id=%s AND item_id=(SELECT id FROM items WHERE name=%s)
            """, (pj[0], item))
            self.conn.commit()
            await interaction.response.send_message(f"{personaje} equipó {item}.", ephemeral=False)
        finally:
            cur.close()


    @inventario.command(name="give", description="Añade ítems mágicamente a un inventario (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_item(self, interaction: discord.Interaction, personaje: str, item: str, cantidad: int):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT c.id FROM characters c WHERE c.guild_id=%s AND c.name=%s",
                        (str(interaction.guild.id), personaje))
            pj = cur.fetchone()
            if not pj:
                await interaction.response.send_message("Personaje no encontrado.", ephemeral=True)
                return

            cur.execute("SELECT id FROM items WHERE name=%s", (item,))
            it = cur.fetchone()
            if not it:
                await interaction.response.send_message("Ítem no encontrado.", ephemeral=True)
                return

            cur.execute("""
                INSERT INTO inventory (character_id, item_id, quantity)
                VALUES (%s, %s, %s)
                ON CONFLICT (character_id, item_id)
                DO UPDATE SET quantity = inventory.quantity + EXCLUDED.quantity
            """, (pj[0], it[0], cantidad))
            self.conn.commit()
            await interaction.response.send_message(f"{cantidad}x {item} añadidos mágicamente al inventario de {personaje}.", ephemeral=False)
        finally:
            cur.close()

async def setup(bot):
    await bot.add_cog(Inventario(bot))
