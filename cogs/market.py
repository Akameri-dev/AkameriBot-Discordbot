# cogs/market.py
import random
import json
import math
import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Tuple, Optional

def _parse_components_str(s: str) -> List[Tuple[str, int]]:
    """
    "madera*2, piedra*1" -> [("madera",2), ("piedra",1)]
    """
    partes = [p.strip() for p in s.split(",") if p.strip()]
    out = []
    for p in partes:
        if "*" in p:
            name, qty = p.split("*", 1)
            try:
                q = max(1, int(qty.strip()))
            except Exception:
                q = 1
            out.append((name.strip(), q))
        else:
            out.append((p, 1))
    return out


class Market(commands.GroupCog, name="mercado"):
    """
    Grupo de comandos /mercado
    """
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.bot = bot
        # aseguramos conexión y columnas extras en DB (price2/price3 y initial_price2/3)
        try:
            cur = self.conn.cursor()
            cur.execute("""
                ALTER TABLE market_listings
                ADD COLUMN IF NOT EXISTS price2 JSONB DEFAULT '[]'::jsonb,
                ADD COLUMN IF NOT EXISTS price3 JSONB DEFAULT '[]'::jsonb,
                ADD COLUMN IF NOT EXISTS initial_price2 JSONB DEFAULT '[]'::jsonb,
                ADD COLUMN IF NOT EXISTS initial_price3 JSONB DEFAULT '[]'::jsonb
            """)
            self.conn.commit()
            cur.close()
        except Exception:
            # si falla por cualquier razón, no rompemos el cog; la DB puede tener otro esquema
            try:
                cur.close()
            except Exception:
                pass

    @property
    def conn(self):
        return self.bot.conn

    # -------------------------
    # helpers DB / JSON
    # -------------------------
    def _item_id_by_name(self, cur, name: str):
        cur.execute("SELECT id FROM items WHERE lower(name)=lower(%s) LIMIT 1", (name,))
        r = cur.fetchone()
        return r[0] if r else None

    def _read_json_field(self, val):
        # admite str/jsonb/None
        if val is None:
            return []
        if isinstance(val, (str, bytes)):
            try:
                return json.loads(val)
            except Exception:
                return []
        return val  # ya es list/dict

    def _price_to_human(self, cur, price_json):
        price = self._read_json_field(price_json) or []
        parts = []
        for e in price:
            cur.execute("SELECT name FROM items WHERE id=%s", (e["item_id"],))
            r = cur.fetchone()
            n = r[0] if r else f"id{e['item_id']}"
            parts.append(f"{int(e.get('qty',0))}x {n}")
        return ", ".join(parts) if parts else "Gratis/No definido"

    def _is_price_zero(self, price_json):
        price = self._read_json_field(price_json) or []
        total = sum(int(p.get("qty", 0)) for p in price)
        return total == 0

    def _apply_factor_to_price(self, price_list, factor):
        """Aplica factor a una lista de precios (lista de dicts) y redondea"""
        out = []
        for e in price_list:
            qty = int(math.floor(int(e.get("qty", 0)) * factor + 0.5))
            qty = max(0, qty)
            out.append({"item_id": e["item_id"], "qty": qty})
        return out

    # -------------------------
    # ADMIN: crear / eliminar mercados
    # -------------------------
    @app_commands.command(name="crear", description="(Admin) Crear un mercado en este servidor")
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
            await interaction.response.send_message(f"Mercado {nombre} creado (id {mid}).", ephemeral=True)
        finally:
            cur.close()

    @app_commands.command(name="eliminar", description="(Admin) Eliminar un mercado y sus listados")
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
            await interaction.response.send_message(f"Mercado {nombre} eliminado.", ephemeral=True)
        finally:
            cur.close()

    # -------------------------
    # ADMIN: añadir/quitar item a un mercado
    # price_spec = "madera*2,moneda*1"
    # initial_stock optional (if omitted random 1-10)
    # Accept optional price_spec2 and price_spec3
    # -------------------------
    @app_commands.command(name="add_item", description="(Admin) Añadir un item a un mercado con precio (formato: item*qty, ... )")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(mercado_nombre="Nombre del mercado", item_nombre="Nombre del item", price_spec="Formato: item*qty, ...", price_spec2="Precio alternativo 2 (opcional)", price_spec3="Precio alternativo 3 (opcional)", initial_stock="Stock inicial (opcional)")
    async def add_item(self, interaction: discord.Interaction, mercado_nombre: str, item_nombre: str, price_spec: str, price_spec2: Optional[str] = None, price_spec3: Optional[str] = None, initial_stock: Optional[int] = None):
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

            # parse price1
            parsed = _parse_components_str(price_spec)
            price_list = []
            for nm, qty in parsed:
                iid = self._item_id_by_name(cur, nm)
                if not iid:
                    await interaction.response.send_message(f"El item de precio '{nm}' no existe (crea el item primero).", ephemeral=True)
                    return
                price_list.append({"item_id": iid, "qty": qty})

            # parse price2/3 if provided
            def parse_optional(spec):
                if not spec:
                    return []
                out = []
                for nm, qty in _parse_components_str(spec):
                    iid = self._item_id_by_name(cur, nm)
                    if not iid:
                        return None, nm
                    out.append({"item_id": iid, "qty": qty})
                return out, None

            price2_list, bad = parse_optional(price_spec2)
            if bad:
                await interaction.response.send_message(f"El item de precio2 '{bad}' no existe (crea el item primero).", ephemeral=True)
                return
            price3_list, bad = parse_optional(price_spec3)
            if bad:
                await interaction.response.send_message(f"El item de precio3 '{bad}' no existe (crea el item primero).", ephemeral=True)
                return

            if initial_stock is None:
                initial_stock = random.randint(1, 10)
            initial_stock = max(0, int(initial_stock))

            # insertar (tener en cuenta columnas price2/price3)
            cur.execute("""
                INSERT INTO market_listings 
                (market_id, item_id, price, initial_price, price2, initial_price2, price3, initial_price3, initial_stock, base_stock, current_stock)
                VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
                RETURNING id
            """, (
                market_id, item_id,
                json.dumps(price_list), json.dumps(price_list),
                json.dumps(price2_list or []), json.dumps(price2_list or []),
                json.dumps(price3_list or []), json.dumps(price3_list or []),
                initial_stock, initial_stock, initial_stock
            ))
            listing_id = cur.fetchone()[0]
            self.conn.commit()
            await interaction.response.send_message(f"{item_nombre} añadido al mercado {mercado_nombre} (stock inicial: {initial_stock}).", ephemeral=True)
        finally:
            cur.close()

    @app_commands.command(name="remove_item", description="(Admin) Quitar un item de un mercado")
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
            await interaction.response.send_message(f"{item_nombre} removido de {mercado_nombre}.", ephemeral=True)
        finally:
            cur.close()

    # -------------------------
    # ADMIN: resetear mercado (vuelve a initial_price / initial_stock)
    # -------------------------
    @app_commands.command(name="reset", description="(Admin) Reinicia precios y stock del mercado a sus valores iniciales")
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
                SET price = COALESCE(initial_price, '[]'::jsonb),
                    price2 = COALESCE(initial_price2, '[]'::jsonb),
                    price3 = COALESCE(initial_price3, '[]'::jsonb),
                    base_stock = initial_stock,
                    current_stock = initial_stock
                WHERE market_id=%s
            """, (market_id,))
            self.conn.commit()
            await interaction.response.send_message(f"Mercado {mercado_nombre} reiniciado a valores iniciales.", ephemeral=True)
        finally:
            cur.close()

    # -------------------------
    # ADMIN: actualizar mercado (ejecuta algoritmo semanal manualmente)
    # -------------------------
    @app_commands.command(name="actualizar", description="(Admin) Actualiza stocks aleatorios y ajusta precios según ventas")
    @app_commands.checks.has_permissions(administrator=True)
    async def actualizar_mercado(self, interaction: discord.Interaction, mercado_nombre: str):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT id FROM markets WHERE guild_id=%s AND lower(name)=lower(%s)", (str(interaction.guild.id), mercado_nombre))
            mk = cur.fetchone()
            if not mk:
                await interaction.response.send_message("No encontré ese mercado.", ephemeral=True)
                return
            market_id = mk[0]

            cur.execute("""
                SELECT id, price, price2, price3, initial_price, initial_price2, initial_price3, base_stock, current_stock
                FROM market_listings
                WHERE market_id=%s
            """, (market_id,))
            rows = cur.fetchall()
            if not rows:
                await interaction.response.send_message("Ese mercado no tiene items.", ephemeral=True)
                return

            updated = []
            for (listing_id, price_raw, price2_raw, price3_raw, init_raw, init2_raw, init3_raw, base_stock, current_stock) in rows:
                price = self._read_json_field(price_raw) or []
                price2 = self._read_json_field(price2_raw) or []
                price3 = self._read_json_field(price3_raw) or []
                initial_price = self._read_json_field(init_raw) or []
                initial_price2 = self._read_json_field(init2_raw) or initial_price
                initial_price3 = self._read_json_field(init3_raw) or initial_price

                base_stock = int(base_stock or 0)
                current_stock = int(current_stock or 0)
                sold = max(0, base_stock - current_stock)

                nueva_stock = random.randint(1, 10)

                # Decide factor por demanda
                mitad = math.ceil(base_stock / 2) if base_stock > 0 else 1
                factor = 1.5 if sold >= mitad else 0.5

                # Helper para producir new_price (restaurar si price==0)
                def adjust_or_restore(price_list, initial_list):
                    if self._is_price_zero(price_list):
                        return initial_list or []
                    else:
                        return self._apply_factor_to_price(price_list, factor)

                new_price = adjust_or_restore(price, initial_price)
                new_price2 = adjust_or_restore(price2, initial_price2)
                new_price3 = adjust_or_restore(price3, initial_price3)

                cur.execute("""
                    UPDATE market_listings
                    SET price=%s::jsonb, price2=%s::jsonb, price3=%s::jsonb,
                        base_stock=%s, current_stock=%s
                    WHERE id=%s
                """, (json.dumps(new_price), json.dumps(new_price2), json.dumps(new_price3), nueva_stock, nueva_stock, listing_id))
                updated.append(listing_id)

            self.conn.commit()
            await interaction.response.send_message(f"Mercado {mercado_nombre} actualizado. ({len(updated)} items)", ephemeral=True)
        finally:
            cur.close()

    # -------------------------
    # ADMIN: inflacion -- aplicar porcentaje a todas las ocurrencias de un 'currency' item
    # -------------------------
    @app_commands.command(name="inflacion", description="(Admin) Aplica un porcentaje de inflación a un item en todos los mercados")
    @app_commands.checks.has_permissions(administrator=True)
    async def inflacion(self, interaction: discord.Interaction, item_nombre: str, porcentaje: float):
        cur = self.conn.cursor()
        try:
            item_id = self._item_id_by_name(cur, item_nombre)
            if not item_id:
                await interaction.response.send_message("No existe ese item.", ephemeral=True)
                return
            ratio = 1.0 + (porcentaje / 100.0)

            cur.execute("SELECT id, price, price2, price3 FROM market_listings")
            rows = cur.fetchall()
            modified = 0
            for lid, price_raw, price2_raw, price3_raw in rows:
                changed_any = False

                price = self._read_json_field(price_raw) or []
                price2 = self._read_json_field(price2_raw) or []
                price3 = self._read_json_field(price3_raw) or []

                new_price = []
                changed = False
                for e in price:
                    if int(e.get("item_id")) == int(item_id):
                        new_qty = int(math.floor(int(e.get("qty",0)) * ratio + 0.5))
                        new_qty = max(0, new_qty)
                        new_price.append({"item_id": e["item_id"], "qty": new_qty})
                        changed = True
                    else:
                        new_price.append(e)
                if changed:
                    changed_any = True

                new_price2 = []
                changed2 = False
                for e in price2:
                    if int(e.get("item_id")) == int(item_id):
                        new_qty = int(math.floor(int(e.get("qty",0)) * ratio + 0.5))
                        new_qty = max(0, new_qty)
                        new_price2.append({"item_id": e["item_id"], "qty": new_qty})
                        changed2 = True
                    else:
                        new_price2.append(e)
                if changed2:
                    changed_any = True

                new_price3 = []
                changed3 = False
                for e in price3:
                    if int(e.get("item_id")) == int(item_id):
                        new_qty = int(math.floor(int(e.get("qty",0)) * ratio + 0.5))
                        new_qty = max(0, new_qty)
                        new_price3.append({"item_id": e["item_id"], "qty": new_qty})
                        changed3 = True
                    else:
                        new_price3.append(e)
                if changed3:
                    changed_any = True

                if changed_any:
                    # también actualizamos initial_price* para persistir la inflación
                    cur.execute("""
                        UPDATE market_listings
                        SET price=%s::jsonb, initial_price=%s::jsonb,
                            price2=%s::jsonb, initial_price2=%s::jsonb,
                            price3=%s::jsonb, initial_price3=%s::jsonb
                        WHERE id=%s
                    """, (
                        json.dumps(new_price), json.dumps(new_price),
                        json.dumps(new_price2), json.dumps(new_price2),
                        json.dumps(new_price3), json.dumps(new_price3),
                        lid
                    ))
                    modified += 1

            self.conn.commit()
            await interaction.response.send_message(f"Inflación aplicada: {porcentaje}% al item {item_nombre} en {modified} listings.", ephemeral=True)
        finally:
            cur.close()

    # -------------------------
    # USERS: listar mercados / ver mercado
    # -------------------------
    @app_commands.command(name="lista", description="Muestra los mercados disponibles en este servidor")
    async def listar_mercados(self, interaction: discord.Interaction):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT name FROM markets WHERE guild_id=%s ORDER BY name", (str(interaction.guild.id),))
            rows = cur.fetchall()
            cur.close()
            if not rows:
                await interaction.response.send_message("No hay mercados en este servidor.", ephemeral=True)
                return
            embed = discord.Embed(title="Mercados", color=discord.Color.dark_gold())
            embed.description = "\n".join(f"- {r[0]}" for r in rows)
            await interaction.response.send_message(embed=embed)
        finally:
            pass

    # Excel-style table helper
    def _format_market_table(self, cur, rows):
        # header widths
        ID_W = 4
        STOCK_W = 6
        ITEM_W = 28
        PRICE_W = 26

        header = f"{'ID':<{ID_W}} {'Stock':<{STOCK_W}} {'Item':<{ITEM_W}} {'Precio1':<{PRICE_W}} {'Precio2':<{PRICE_W}} {'Precio3':<{PRICE_W}}"
        sep = "-" * min(200, len(header))
        lines = [header, sep]
        for listing_id, item_name, image, price_raw, price2_raw, price3_raw, stock in rows:
            p1 = self._price_to_human(cur, price_raw)
            p2 = self._price_to_human(cur, price2_raw)
            p3 = self._price_to_human(cur, price3_raw)

            # truncate long fields
            item_name_trunc = (item_name[:ITEM_W-3] + "...") if len(item_name) > ITEM_W else item_name
            p1_trunc = (p1[:PRICE_W-3] + "...") if len(p1) > PRICE_W else p1
            p2_trunc = (p2[:PRICE_W-3] + "...") if len(p2) > PRICE_W else p2
            p3_trunc = (p3[:PRICE_W-3] + "...") if len(p3) > PRICE_W else p3

            lines.append(f"{str(listing_id):<{ID_W}} {str(stock):<{STOCK_W}} {item_name_trunc:<{ITEM_W}} {p1_trunc:<{PRICE_W}} {p2_trunc:<{PRICE_W}} {p3_trunc:<{PRICE_W}}")

        text = "```\n" + "\n".join(lines) + "\n```"
        # Discord embed max description ~4096, si pasa devolvemos None para indicar paginar/external
        if len(text) > 4000:
            return None, text  # devolvemos raw text para file
        return text, None

    @app_commands.command(name="ver", description="Muestra los items y precios de un mercado")
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
                SELECT ml.id, i.name, i.image, ml.price, ml.price2, ml.price3, ml.current_stock
                FROM market_listings ml
                JOIN items i ON ml.item_id = i.id
                WHERE ml.market_id=%s
                ORDER BY i.name
            """, (market_id,))
            rows = cur.fetchall()
            if not rows:
                await interaction.response.send_message("Ese mercado no tiene listings.", ephemeral=True)
                return

            table_text, raw_text = self._format_market_table(cur, rows)
            embed = discord.Embed(title=f"Mercado: {mercado_nombre}", color=discord.Color.dark_gold())
            if table_text:
                embed.description = table_text
                await interaction.response.send_message(embed=embed)
            else:
                # demasiado grande: mandamos como archivo de texto
                await interaction.response.send_message(f"Listado demasiado largo — se adjunta como archivo.", ephemeral=True)
                await interaction.followup.send(file=discord.File(fp=raw_text.encode("utf-8"), filename=f"mercado_{market_id}.txt"))
        finally:
            cur.close()

    # -------------------------
    # USERS: comprar
    # /mercado comprar <mercado> <personaje> <item> <cantidad> [precio_num]
    # precio_num: 1,2 o 3
    # -------------------------
    @app_commands.command(name="comprar", description="Comprar item de un mercado (usa inventario del personaje). Puedes elegir precio 1/2/3 con precio_num.")
    async def comprar(self, interaction: discord.Interaction, mercado_nombre: str, personaje: str, item_nombre: str, cantidad: int = 1, precio_num: int = 1):
        if cantidad < 1:
            await interaction.response.send_message("La cantidad debe ser 1 o más.", ephemeral=True)
            return
        if precio_num not in (1,2,3):
            await interaction.response.send_message("precio_num debe ser 1, 2 o 3.", ephemeral=True)
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

            # obtener listing y el price column seleccionado
            cur.execute("""
                SELECT id, price, price2, price3, current_stock
                FROM market_listings
                WHERE market_id=%s AND item_id=%s
                LIMIT 1
            """, (market_id, item_id))
            listing = cur.fetchone()
            if not listing:
                await interaction.response.send_message("Ese item no está en ese mercado.", ephemeral=True)
                return
            listing_id, price_raw, price2_raw, price3_raw, stock = listing
            stock = int(stock or 0)

            if stock < cantidad or stock <= 0:
                await interaction.response.send_message("No hay suficiente stock disponible (o agotado).", ephemeral=True)
                return

            # seleccionar columna de precio
            price_raw_selected = price_raw if precio_num == 1 else (price2_raw if precio_num == 2 else price3_raw)
            price = self._read_json_field(price_raw_selected) or []
            if self._is_price_zero(price):
                await interaction.response.send_message("Ese precio no es válido (precio vacío). Elija otra variante o contacte a un administrador.", ephemeral=True)
                return

            # comprobar inventario del personaje
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

            self.conn.commit()

            pay_lines = []
            for p in price:
                cur.execute("SELECT name FROM items WHERE id=%s", (p["item_id"],))
                nm = cur.fetchone()
                pretty = nm[0] if nm else f"id{p['item_id']}"
                pay_lines.append(f"{pretty} x{int(p.get('qty',0))*cantidad}")

            cur.execute("SELECT name FROM items WHERE id=%s", (item_id,))
            name_row = cur.fetchone()
            bought_name = name_row[0] if name_row else f"id{item_id}"

            embed = discord.Embed(title=f"Comprado: {bought_name}", color=discord.Color.dark_gold())
            embed.add_field(name="Cantidad comprada", value=str(cantidad), inline=True)
            embed.add_field(name="Pago", value="\n".join(pay_lines) or "Nada", inline=False)
            await interaction.response.send_message(embed=embed)
        finally:
            cur.close()


async def setup(bot: commands.Bot):
    await bot.add_cog(Market(bot))
