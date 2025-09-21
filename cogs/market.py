import random
import json
import math
import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Tuple

def _parse_components_str(s: str) -> List[Tuple[str, int]]:
    """
    "madera*2, piedra*1" -> [("madera",2), ("piedra",1)]
    """
    partes = [p.strip() for p in s.split(",") if p.strip()]
    out = []
    for p in partes:
        if "*" in p:
            name, qty = p.split("*", 1)
            out.append((name.strip(), max(1, int(qty.strip()))))
        else:
            out.append((p, 1))
    return out

class Market(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def conn(self):
        return self.bot.conn

    mercado = app_commands.Group(name="mercado", description="Sistema de mercados del servidor")

    # -------------------------
    # helpers DB
    # -------------------------
    def _item_id_by_name(self, cur, name: str):
        cur.execute("SELECT id FROM items WHERE lower(name)=lower(%s) LIMIT 1", (name,))
        r = cur.fetchone()
        return r[0] if r else None

    def _read_json_field(self, val):
        if val is None:
            return None
        if isinstance(val, (str, bytes)):
            try:
                return json.loads(val)
            except Exception:
                return val
        return val

    def _price_to_human(self, cur, price_json):
        """
        Convierte [{"item_id":X,"qty":Y},...] -> '2 Madera, 1 Moneda'
        """
        price = self._read_json_field(price_json) or []
        parts = []
        for e in price:
            cur.execute("SELECT name FROM items WHERE id=%s", (e["item_id"],))
            r = cur.fetchone()
            n = r[0] if r else f"id{e['item_id']}"
            parts.append(f"{e['qty']}x {n}")
        return ", ".join(parts) if parts else "Gratis/No definido"

    def _is_price_zero(self, price_json):
        price = self._read_json_field(price_json) or []
        total = sum(int(p.get("qty", 0)) for p in price)
        return total == 0

    # -------------------------
    # ADMIN: crear / eliminar mercados
    # -------------------------
    @mercado.command(name="crear", description="(Admin) Crear un mercado en este servidor")
    @app_commands.checks.has_permissions(administrator=True)
    async def crear_mercado(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", (str(interaction.guild.id), nombre))
            if cur.fetchone():
                await interaction.response.send_message("Ya existe un mercado con ese nombre en este servidor.", ephemeral=True)
                return
            cur.execute("INSERT INTO markets (guild_id, name, created_by) VALUES (%s,%s,%s) RETURNING id",
                        (str(interaction.guild.id), nombre, str(interaction.user.id)))
            mid = cur.fetchone()[0]
            self.conn.commit()
            await interaction.response.send_message(f"✅ Mercado **{nombre}** creado (id {mid}).", ephemeral=True)
        finally:
            cur.close()

    @mercado.command(name="eliminar", description="(Admin) Eliminar un mercado y sus listados")
    @app_commands.checks.has_permissions(administrator=True)
    async def eliminar_mercado(self, interaction: discord.Interaction, nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("DELETE FROM markets WHERE guild_id=%s AND lower(name)=lower(%s) RETURNING id", (str(interaction.guild.id), nombre))
            r = cur.fetchone()
            if not r:
                await interaction.response.send_message("No encontré ese mercado.", ephemeral=True)
                return
            self.conn.commit()
            await interaction.response.send_message(f"🗑️ Mercado **{nombre}** eliminado.", ephemeral=True)
        finally:
            cur.close()

    # -------------------------
    # ADMIN: añadir/quitar item a un mercado
    # price_spec = "madera*2,moneda*1"
    # initial_stock optional (if omitted random 1-10)
    # -------------------------
    @mercado.command(name="add_item", description="(Admin) Añadir un item a un mercado con precio (formato: item*qty, ... )")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_item(self, interaction: discord.Interaction, mercado_nombre: str, item_nombre: str, price_spec: str, initial_stock: int = None):
        cur = self.conn.cursor()
        try:
            # mercado
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", (str(interaction.guild.id), mercado_nombre))
            m = cur.fetchone()
            if not m:
                await interaction.response.send_message("No encontré ese mercado.", ephemeral=True)
                return
            market_id = m[0]

            # item a listar
            item_id = self._item_id_by_name(cur, item_nombre)
            if not item_id:
                await interaction.response.send_message("No existe ese item.", ephemeral=True)
                return

            # parse price
            parsed = _parse_components_str(price_spec)
            price_list = []
            for nm, qty in parsed:
                iid = self._item_id_by_name(cur, nm)
                if not iid:
                    await interaction.response.send_message(f"El item de precio **{nm}** no existe (crea el item primero).", ephemeral=True)
                    return
                price_list.append({"item_id": iid, "qty": qty})

            if initial_stock is None:
                initial_stock = random.randint(1, 10)
            initial_stock = max(0, int(initial_stock))

            # insertar
            cur.execute("""
                INSERT INTO market_listings (market_id, item_id, price, initial_price, initial_stock, base_stock, current_stock)
                VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, %s, %s)
                RETURNING id
            """, (market_id, item_id, json.dumps(price_list), json.dumps(price_list), initial_stock, initial_stock, initial_stock))
            listing_id = cur.fetchone()[0]
            self.conn.commit()
            await interaction.response.send_message(f" {item_nombre} añadido al mercado **{mercado_nombre}** (stock inicial: {initial_stock}).", ephemeral=True)
        finally:
            cur.close()

    @mercado.command(name="remove_item", description="(Admin) Quitar un item de un mercado")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_item(self, interaction: discord.Interaction, mercado_nombre: str, item_nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", (str(interaction.guild.id), mercado_nombre))
            m = cur.fetchone()
            if not m:
                await interaction.response.send_message("No encontré ese mercado.", ephemeral=True)
                return
            market_id = m[0]

            iid = self._item_id_by_name(cur, item_nombre)
            if not iid:
                await interaction.response.send_message("No existe ese item.", ephemeral=True)
                return

            cur.execute("DELETE FROM market_listings WHERE market_id=%s AND item_id=%s RETURNING id", (market_id, iid))
            r = cur.fetchone()
            if not r:
                await interaction.response.send_message("Ese item no estaba en ese mercado.", ephemeral=True)
                return
            self.conn.commit()
            await interaction.response.send_message(f"🗑️ {item_nombre} removido de **{mercado_nombre}**.", ephemeral=True)
        finally:
            cur.close()

    # -------------------------
    # ADMIN: resetear mercado (vuelve a initial_price / initial_stock)
    # -------------------------
    @mercado.command(name="reset", description="(Admin) Reinicia precios y stock del mercado a sus valores iniciales")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_mercado(self, interaction: discord.Interaction, mercado_nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", (str(interaction.guild.id), mercado_nombre))
            m = cur.fetchone()
            if not m:
                await interaction.response.send_message("No encontré ese mercado.", ephemeral=True)
                return
            market_id = m[0]

            cur.execute("""
                UPDATE market_listings
                SET price = initial_price,
                    base_stock = initial_stock,
                    current_stock = initial_stock
                WHERE market_id=%s
            """, (market_id,))
            self.conn.commit()
            await interaction.response.send_message(f"🔁 Mercado **{mercado_nombre}** reiniciado a valores iniciales.", ephemeral=True)
        finally:
            cur.close()

    # -------------------------
    # ADMIN: actualizar mercado (ejecuta algoritmo semanal manualmente)
    # -------------------------
    @mercado.command(name="actualizar", description="(Admin) Actualiza stocks aleatorios y ajusta precios según ventas")
    @app_commands.checks.has_permissions(administrator=True)
    async def actualizar_mercado(self, interaction: discord.Interaction, mercado_nombre: str):
        """
        Lógica: para cada listing:
        - sold = base_stock - current_stock
        - nueva_stock = random(1..10)
        - si sold >= ceil(base_stock/2)  => precio * 1.5
          si sold < ceil(base_stock/2)   => precio * 0.5
        - si precio actual era '0' -> se restaura a initial_price en vez de modificar
        - luego base_stock = nueva_stock, current_stock = nueva_stock
        """

        cur = self.conn.cursor()
        try:
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", (str(interaction.guild.id), mercado_nombre))
            mk = cur.fetchone()
            if not mk:
                await interaction.response.send_message("No encontré ese mercado.", ephemeral=True)
                return
            market_id = mk[0]

            cur.execute("""
                SELECT id, price, initial_price, base_stock, current_stock
                FROM market_listings
                WHERE market_id=%s
            """, (market_id,))
            rows = cur.fetchall()
            if not rows:
                await interaction.response.send_message("Ese mercado no tiene items.", ephemeral=True)
                return

            updated = []
            for listing_id, price_raw, initial_price_raw, base_stock, current_stock in rows:
                price = self._read_json_field(price_raw) or []
                initial_price = self._read_json_field(initial_price_raw) or []
                base_stock = int(base_stock or 0)
                current_stock = int(current_stock or 0)
                sold = max(0, base_stock - current_stock)

                nueva_stock = random.randint(1, 10)

                # Si precio actual es 0 (sum(qty)==0) -> restaurar a initial_price
                if self._is_price_zero(price):
                    new_price = initial_price
                else:
                    # evitar división por 0: si base_stock==0 usamos regla de disminucion por defecto
                    mitad = math.ceil(base_stock / 2) if base_stock > 0 else 1
                    factor = 1.5 if sold >= mitad else 0.5

                    # aplicar factor a todas las cantidades y redondear
                    new_price = []
                    for e in price:
                        new_qty = int(math.floor(e.get("qty", 0) * factor + 0.5))
                        # permitimos que llegue a 0 (entonces el item se vuelve no-comprable hasta la próxima actualizacion donde restaurará)
                        new_qty = max(0, new_qty)
                        new_price.append({"item_id": e["item_id"], "qty": new_qty})

                cur.execute("""
                    UPDATE market_listings
                    SET price=%s::jsonb, base_stock=%s, current_stock=%s
                    WHERE id=%s
                """, (json.dumps(new_price), nueva_stock, nueva_stock, listing_id))
                updated.append(listing_id)

            self.conn.commit()
            await interaction.response.send_message(f"✅ Mercado **{mercado_nombre}** actualizado. ({len(updated)} items)", ephemeral=True)
        finally:
            cur.close()

    # -------------------------
    # ADMIN: inflacion -- aplicar porcentaje a todas las ocurrencias de un 'currency' item
    # -------------------------
    @mercado.command(name="inflacion", description="(Admin) Aplica un porcentaje de inflación a un item en todos los mercados")
    @app_commands.checks.has_permissions(administrator=True)
    async def inflacion(self, interaction: discord.Interaction, item_nombre: str, porcentaje: float):
        """porcentaje puede ser positivo o negativo. Ej: 1.0 => +1%"""
        cur = self.conn.cursor()
        try:
            item_id = self._item_id_by_name(cur, item_nombre)
            if not item_id:
                await interaction.response.send_message("No existe ese item.", ephemeral=True)
                return
            ratio = 1.0 + (porcentaje / 100.0)

            # seleccionar todos los listings que contengan este item en price
            cur.execute("SELECT id, price FROM market_listings")
            rows = cur.fetchall()
            modified = 0
            for lid, price_raw in rows:
                price = self._read_json_field(price_raw) or []
                changed = False
                new_price = []
                for e in price:
                    if int(e.get("item_id")) == int(item_id):
                        new_qty = int(math.floor(e.get("qty", 0) * ratio + 0.5))
                        new_qty = max(0, new_qty)
                        new_price.append({"item_id": e["item_id"], "qty": new_qty})
                        changed = True
                    else:
                        new_price.append(e)
                if changed:
                    cur.execute("UPDATE market_listings SET price=%s::jsonb WHERE id=%s", (json.dumps(new_price), lid))
                    modified += 1

            self.conn.commit()
            await interaction.response.send_message(f"📈 Inflación aplicada: {porcentaje}% al item **{item_nombre}** en {modified} listings.", ephemeral=True)
        finally:
            cur.close()

    # -------------------------
    # USERS: listar mercados / ver mercado
    # -------------------------
    @mercado.command(name="lista", description="Muestra los mercados disponibles en este servidor")
    async def listar_mercados(self, interaction: discord.Interaction):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT name FROM markets WHERE guild_id=%s ORDER BY name", (str(interaction.guild.id),))
            rows = cur.fetchall()
            cur.close()
            if not rows:
                await interaction.response.send_message("No hay mercados en este servidor.", ephemeral=True)
                return
            embed = discord.Embed(title="Mercados", color=discord.Color.blurple())
            embed.description = "\n".join(f"- {r[0]}" for r in rows)
            await interaction.response.send_message(embed=embed)
        finally:
            pass

    @mercado.command(name="ver", description="Muestra los items y precios de un mercado")
    async def ver_mercado(self, interaction: discord.Interaction, mercado_nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", (str(interaction.guild.id), mercado_nombre))
            m = cur.fetchone()
            if not m:
                await interaction.response.send_message("No encontré ese mercado.", ephemeral=True)
                return
            market_id = m[0]

            cur.execute("""
                SELECT ml.item_id, i.name, i.image, ml.price, ml.current_stock
                FROM market_listings ml
                JOIN items i ON ml.item_id = i.id
                WHERE ml.market_id=%s
                ORDER BY i.name
            """, (market_id,))
            rows = cur.fetchall()
            if not rows:
                await interaction.response.send_message("Ese mercado no tiene listings.", ephemeral=True)
                return

            embed = discord.Embed(title=f"Mercado: {mercado_nombre}", color=discord.Color.gold())
            for item_id, name, image, price_json, stock in rows:
                price_text = self._price_to_human(cur, price_json)
                val = f"Stock: {stock}\nPrecio: {price_text}"
                embed.add_field(name=f"{name}", value=val, inline=False)
            await interaction.response.send_message(embed=embed)
        finally:
            cur.close()

    # -------------------------
    # USERS: comprar
    # /mercado comprar <mercado> <personaje> <item> <cantidad>
    # -------------------------
    @mercado.command(name="comprar", description="Comprar item de un mercado (usa inventario del personaje)")
    async def comprar(self, interaction: discord.Interaction, mercado_nombre: str, personaje: str, item_nombre: str, cantidad: int = 1):
        if cantidad < 1:
            await interaction.response.send_message("La cantidad debe ser 1 o más.", ephemeral=True)
            return

        cur = self.conn.cursor()
        try:
            # validar personaje y permisos
            cur.execute("SELECT id, user_id FROM characters WHERE guild_id=%s AND name=%s LIMIT 1", (str(interaction.guild.id), personaje))
            pj = cur.fetchone()
            if not pj:
                await interaction.response.send_message("Personaje no encontrado.", ephemeral=True)
                return
            char_id, owner_id = pj
            if str(interaction.user.id) != str(owner_id) and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("Solo el dueño del personaje o un admin puede comprar para él.", ephemeral=True)
                return

            # mercado + listing
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", (str(interaction.guild.id), mercado_nombre))
            mk = cur.fetchone()
            if not mk:
                await interaction.response.send_message("No encontré ese mercado.", ephemeral=True)
                return
            market_id = mk[0]

            item_id = self._item_id_by_name(cur, item_nombre)
            if not item_id:
                await interaction.response.send_message("Ese item no existe.", ephemeral=True)
                return

            cur.execute("""
                SELECT id, price, current_stock
                FROM market_listings
                WHERE market_id=%s AND item_id=%s
                LIMIT 1
            """, (market_id, item_id))
            listing = cur.fetchone()
            if not listing:
                await interaction.response.send_message("Ese item no está en ese mercado.", ephemeral=True)
                return
            listing_id, price_raw, stock = listing
            price = self._read_json_field(price_raw) or []
            stock = int(stock or 0)

            if stock < cantidad or stock <= 0:
                await interaction.response.send_message("No hay suficiente stock disponible (o agotado).", ephemeral=True)
                return

            # comprobar que personaje tenga los items precio multiplicado por cantidad
            missing = []
            for p in price:
                need = int(p.get("qty", 0)) * cantidad
                cur.execute("SELECT quantity FROM inventory WHERE character_id=%s AND item_id=%s", (char_id, p["item_id"]))
                q = cur.fetchone()
                have = int(q[0]) if q else 0
                if have < need:
                    cur.execute("SELECT name FROM items WHERE id=%s", (p["item_id"],))
                    nm = cur.fetchone()
                    pretty = nm[0] if nm else f"id{p['item_id']}"
                    missing.append(f"{pretty} (necesita {need}, tiene {have})")
            if missing:
                await interaction.response.send_message("No tienes los materiales necesarios:\n" + "\n".join(missing), ephemeral=True)
                return

            # deducir pagos
            for p in price:
                need = int(p.get("qty", 0)) * cantidad
                cur.execute("UPDATE inventory SET quantity = quantity - %s WHERE character_id=%s AND item_id=%s", (need, char_id, p["item_id"]))
                cur.execute("DELETE FROM inventory WHERE character_id=%s AND item_id=%s AND quantity<=0", (char_id, p["item_id"]))

            # añadir items comprados al inventario del personaje
            cur.execute("""
                INSERT INTO inventory (character_id, item_id, quantity)
                VALUES (%s, %s, %s)
                ON CONFLICT (character_id, item_id)
                DO UPDATE SET quantity = inventory.quantity + EXCLUDED.quantity
            """, (char_id, item_id, cantidad))

            # decrementar stock en listing
            cur.execute("UPDATE market_listings SET current_stock = current_stock - %s WHERE id=%s", (cantidad, listing_id))
            # no eliminamos el listing si llega a 0; permitimos que quede 0 hasta la proxima actualizacion

            self.conn.commit()


            pay_lines = []
            for p in price:
                cur.execute("SELECT name FROM items WHERE id=%s", (p["item_id"],))
                nm = cur.fetchone()
                pretty = nm[0] if nm else f"id{p['item_id']}"
                pay_lines.append(f"- {pretty} x{int(p.get('qty',0))*cantidad}")

            cur.execute("SELECT name FROM items WHERE id=%s", (item_id,))
            name_row = cur.fetchone()
            bought_name = name_row[0] if name_row else f"id{item_id}"

            embed = discord.Embed(title=f"🛒 Comprado: {bought_name}", color=discord.Color.dark_gold())
            embed.add_field(name="Cantidad comprada", value=str(cantidad), inline=True)
            embed.add_field(name="Pago", value="\n".join(pay_lines) or "Nada", inline=False)
            await interaction.response.send_message(embed=embed)
        finally:
            cur.close()

async def setup(bot: commands.Bot):
    cog = Market(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.mercado)
