import discord
from discord import app_commands
from discord.ext import commands
import json

class Craft(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def conn(self):
        return self.bot.conn

    craft = app_commands.Group(name="crafteo", description="Sistema de crafteo")
    decomp = app_commands.Group(name="descomposicion", description="Sistema de descomposición")


    @craft.command(name="agregar", description="Agrega una receta de crafteo (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    async def crafteo_agregar(self, interaction: discord.Interaction, objeto: str, componentes: str):
        """
        componentes → formato: item1*2,item2*4
        """
        cur = self.conn.cursor()


        cur.execute("SELECT id FROM items WHERE name=%s", (objeto,))
        result_item = cur.fetchone()
        if not result_item:
            await interaction.response.send_message("Ese objeto no existe.", ephemeral=True)
            cur.close()
            return
        result_item_id = result_item[0]


        comps = []
        for c in componentes.split(","):
            if "*" in c:
                nombre, qty = c.split("*")
                qty = int(qty)
            else:
                nombre, qty = c, 1
            cur.execute("SELECT id FROM items WHERE name=%s", (nombre.strip(),))
            row = cur.fetchone()
            if not row:
                await interaction.response.send_message(f"El objeto {nombre} no existe.", ephemeral=True)
                cur.close()
                return
            comps.append({"item_id": row[0], "qty": qty})

        # insertar receta
        cur.execute("""
            INSERT INTO recipes (result_item_id, components)
            VALUES (%s, %s)
        """, (result_item_id, json.dumps(comps)))
        self.conn.commit()
        cur.close()

        await interaction.response.send_message(f"Receta de **{objeto}** agregada.", ephemeral=True)

    @decomp.command(name="agregar", description="Agrega una regla de descomposición (solo admins)")
    @app_commands.checks.has_permissions(administrator=True)
    async def descomposicion_agregar(self, interaction: discord.Interaction, objeto: str, devuelve: str):
        """
        devuelve → formato: item1*2,item2*4
        """
        cur = self.conn.cursor()

        # buscar item
        cur.execute("SELECT id FROM items WHERE name=%s", (objeto,))
        item = cur.fetchone()
        if not item:
            await interaction.response.send_message("Ese objeto no existe.", ephemeral=True)
            cur.close()
            return
        item_id = item[0]

        comps = []
        for c in devuelve.split(","):
            if "*" in c:
                nombre, qty = c.split("*")
                qty = int(qty)
            else:
                nombre, qty = c, 1
            cur.execute("SELECT id FROM items WHERE name=%s", (nombre.strip(),))
            row = cur.fetchone()
            if not row:
                await interaction.response.send_message(f"El objeto {nombre} no existe.", ephemeral=True)
                cur.close()
                return
            comps.append({"item_id": row[0], "qty": qty})


        cur.execute("UPDATE items SET decompose=%s WHERE id=%s", (json.dumps(comps), item_id))
        self.conn.commit()
        cur.close()

        await interaction.response.send_message(f"Descomposición de **{objeto}** definida.", ephemeral=True)


    @craft.command(name="lista", description="Muestra los objetos que se pueden craftear")
    async def crafteo_lista(self, interaction: discord.Interaction):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT DISTINCT i.name
            FROM recipes r
            JOIN items i ON r.result_item_id = i.id
        """)
        rows = cur.fetchall()
        cur.close()

        if not rows:
            await interaction.response.send_message("No hay recetas definidas.", ephemeral=True)
            return

        lista = "\n".join(f"- {r[0]}" for r in rows)
        embed = discord.Embed(title="Objetos crafteables", description=lista, color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    @craft.command(name="ver", description="Muestra la receta de un objeto")
    async def crafteo_ver(self, interaction: discord.Interaction, objeto: str):
        cur = self.conn.cursor()

        cur.execute("SELECT id FROM items WHERE name=%s", (objeto,))
        row = cur.fetchone()
        if not row:
            await interaction.response.send_message("Ese objeto no existe.", ephemeral=True)
            cur.close()
            return
        item_id = row[0]

        cur.execute("SELECT components FROM recipes WHERE result_item_id=%s", (item_id,))
        rec = cur.fetchone()
        cur.close()

        if not rec:
            await interaction.response.send_message("Ese objeto no tiene receta.", ephemeral=True)
            return

        components = rec[0]
        lista = []
        for comp in components:
            cur = self.conn.cursor()
            cur.execute("SELECT name FROM items WHERE id=%s", (comp["item_id"],))
            comp_name = cur.fetchone()[0]
            cur.close()
            lista.append(f"{comp_name} x{comp['qty']}")

        embed = discord.Embed(
            title=f"Receta de {objeto}",
            description="\n".join(lista),
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

    @craft.command(name="usar", description="Intenta craftear un objeto")
    async def craftear(self, interaction: discord.Interaction, personaje: str, objeto: str):
        cur = self.conn.cursor()
        try:
            # Verificar personaje
            cur.execute("SELECT id FROM characters WHERE guild_id=%s AND name=%s", (str(interaction.guild.id), personaje))
            pj = cur.fetchone()
            if not pj:
                await interaction.response.send_message("Ese personaje no existe.", ephemeral=True)
                cur.close()
                return
            char_id = pj[0]

            # Verificar objeto
            cur.execute("SELECT id FROM items WHERE name=%s", (objeto,))
            row = cur.fetchone()
            if not row:
                await interaction.response.send_message("Ese objeto no existe.", ephemeral=True)
                cur.close()
                return
            result_item_id = row[0]

            # Obtener receta
            cur.execute("SELECT components FROM recipes WHERE result_item_id=%s", (result_item_id,))
            rec = cur.fetchone()
            if not rec:
                await interaction.response.send_message("Ese objeto no tiene receta.", ephemeral=True)
                cur.close()
                return

            components = rec[0]

            # Verificar materiales
            for comp in components:
                cur.execute("SELECT quantity FROM inventory WHERE character_id=%s AND item_id=%s",
                            (char_id, comp["item_id"]))
                inv = cur.fetchone()
                if not inv or inv[0] < comp["qty"]:
                    await interaction.response.send_message("No tienes todos los materiales necesarios.", ephemeral=True)
                    cur.close()
                    return

            # Consumir materiales
            for comp in components:
                cur.execute("""
                    UPDATE inventory
                    SET quantity = quantity - %s
                    WHERE character_id=%s AND item_id=%s
                """, (comp["qty"], char_id, comp["item_id"]))

            # Eliminar items con cantidad 0
            cur.execute("DELETE FROM inventory WHERE character_id=%s AND quantity <= 0", (char_id,))

            # Obtener información del item resultante (para max_uses)
            cur.execute("SELECT max_uses FROM items WHERE id=%s", (result_item_id,))
            item_info = cur.fetchone()
            max_uses = item_info[0] if item_info else 0

            # Agregar objeto final con current_uses si corresponde
            if max_uses > 0:
                cur.execute("""
                    INSERT INTO inventory (character_id, item_id, quantity, current_uses)
                    VALUES (%s, %s, 1, %s)
                    ON CONFLICT (character_id, item_id)
                    DO UPDATE SET 
                        quantity = inventory.quantity + EXCLUDED.quantity,
                        current_uses = CASE 
                            WHEN inventory.current_uses IS NULL THEN EXCLUDED.current_uses
                            ELSE inventory.current_uses
                        END
                """, (char_id, result_item_id, max_uses))
            else:
                cur.execute("""
                    INSERT INTO inventory (character_id, item_id, quantity)
                    VALUES (%s, %s, 1)
                    ON CONFLICT (character_id, item_id)
                    DO UPDATE SET quantity = inventory.quantity + EXCLUDED.quantity
                """, (char_id, result_item_id))

            self.conn.commit()
            cur.close()

            await interaction.response.send_message(f"Has crafteado **{objeto}** con éxito.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Error al craftear: {str(e)}", ephemeral=True)
            cur.close()

    @decomp.command(name="usar", description="Descompone un objeto en otros")
    async def descomponer(self, interaction: discord.Interaction, personaje: str, objeto: str):
        cur = self.conn.cursor()


        cur.execute("SELECT id FROM characters WHERE guild_id=%s AND name=%s", (str(interaction.guild.id), personaje))
        pj = cur.fetchone()
        if not pj:
            await interaction.response.send_message("Ese personaje no existe.", ephemeral=True)
            cur.close()
            return
        char_id = pj[0]


        cur.execute("SELECT id, decompose FROM items WHERE name=%s", (objeto,))
        row = cur.fetchone()
        if not row:
            await interaction.response.send_message("Ese objeto no existe.", ephemeral=True)
            cur.close()
            return
        item_id, decompose = row

        if not decompose or decompose == {}:
            await interaction.response.send_message("Este objeto no se puede descomponer.", ephemeral=True)
            cur.close()
            return


        cur.execute("SELECT quantity FROM inventory WHERE character_id=%s AND item_id=%s", (char_id, item_id))
        inv = cur.fetchone()
        if not inv or inv[0] < 1:
            await interaction.response.send_message("No tienes ese objeto en el inventario.", ephemeral=True)
            cur.close()
            return


        cur.execute("UPDATE inventory SET quantity = quantity - 1 WHERE character_id=%s AND item_id=%s",
                    (char_id, item_id))


        for comp in decompose:
            cur.execute("""
                INSERT INTO inventory (character_id, item_id, quantity)
                VALUES (%s, %s, %s)
                ON CONFLICT (character_id, item_id)
                DO UPDATE SET quantity = inventory.quantity + %s
            """, (char_id, comp["item_id"], comp["qty"], comp["qty"]))

        self.conn.commit()
        cur.close()

        await interaction.response.send_message(f"Has descompuesto **{objeto}**.", ephemeral=True)




async def setup(bot: commands.Bot):
    await bot.add_cog(Craft(bot))


