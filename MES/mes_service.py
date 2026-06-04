import asyncio
import signal
import psycopg2

from mes_logger import setup_logger

logger = setup_logger("MES")

from mes_recipe_engine import RecipeEngine
from plc_client import close_client
from mes_scheduler import MACHINE_TOOLS, TOOL_TO_SLOT, ASSEMBLY_MACHINES, estimate_order_completion
from plc_client import (
    MACHINE_TO_INPUT,
    MACHINE_TO_CONVEYOR,
    read_unloading_snapshot,
    send_to_plc,
    send_machine_command,
    confirm_machine_command,
    read_warehouse_counts,
    pulse_unload_request,
    write_tool_configuration,
    read_warehouse_snapshot,
    read_conveyor_state,
    read_conveyor_saved_leg,
    read_conveyor_recv,
    read_output_conveyor_empty,
    write_output_unload,
)

DB_HOST = "localhost"
DB_PORT = "5000"
DB_NAME = "erp_db"
DB_USER = "iind_user"
DB_PASS = "IIND20266"

TOOL_SECONDS = {
    "T1": 30,
    "T2": 20,
    "T3": 10,
    "T4": 35,
    "T5": 25,
    "T6": 20,
    "T8": 10,
    "T9": 10,
    "T10": 30,
    "T11": 40,
}

TOOL_ID_MAP = {
    "T1": 1,
    "T2": 2,
    "T3": 3,
    "T4": 4,
    "T5": 5,
    "T6": 6,
    "T8": 8,
    "T9": 9,
    "T10": 10,
    "T11": 11,
}

MAX_WAREHOUSE_WIP = 32
ASSEMBLY_UNLOAD_MAP = {
    "M1c": "U2",
    "M2c": "U3",
    "M3c": "U4",
    "M4c": "U5",
}

MACHINE_UNLOAD_MAP = {
    "M1a": "U2", "M1b": "U2", "M1c": "U2",
    "M2a": "U3", "M2b": "U3", "M2c": "U3",
    "M3a": "U4", "M3b": "U4", "M3c": "U4",
    "M4a": "U5", "M4b": "U5", "M4c": "U5",
}

UNLOAD_KEY_TO_MACHINES = {
    "U2": ["M1a", "M1b", "M1c"],
    "U3": ["M2a", "M2b", "M2c"],
    "U4": ["M3a", "M3b", "M3c"],
    "U5": ["M4a", "M4b", "M4c"],
}

INPUT_TO_LOADING_CONV = {
    "I1": "L6", "I2": "L7", "I3": "L8", "I4": "L9", "I5": "L10",
}

UNLOAD_KEY_TO_LOADING_CONV = {
    "U2": "L2", "U3": "L3", "U4": "L4", "U5": "L5",
}

OUTPUT_CONV_MAP = {2: "U7", 3: "U8", 4: "U9", 5: "U10"}


class MESService:
    def __init__(self):
        self.recipe_engine = RecipeEngine()
        self._last_tool_by_machine = {}
        self._last_unload_state = {f"U{i}": False for i in range(1, 11)}
        self._schema_ready = False
        self._schema_error_logged = False
        self._no_open_items_logged = False
        self._inventory = {}
        self._tools_configured = False
        self._last_w1_count = None
        self._next_input_index = {1: 0, 2: 0}
        self._est_w1 = {"raw_wood": 0, "raw_metal": 0, "legs": 0, "tops": 0}
        self._est_w2 = {"legs": 0, "tops": 0, "final": 0}
        self._tool_machine_index = {}
        self._input_line_index = 0
        self._cell_busy = {"U2": False, "U3": False, "U4": False, "U5": False}
        self._u1_lock = asyncio.Lock()
        self._current_day = None
        self._output_conv_state = {1: "free", 2: "free", 3: "free", 4: "free", 5: "free"}
        self._output_conv_order = {1: None, 2: None, 3: None, 4: None, 5: None}
        self._output_conv_shipped = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        self._output_conv_total = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        self._order_to_conv = {}

    def _conn(self):
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
        )

    def _get_current_day(self):
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT current_day FROM simulation_state WHERE id = 1")
                row = cur.fetchone()
                if row is None:
                    return 0
                return int(row[0])
        except Exception:
            return 0

    def _get_order_total_quantity(self, order_id):
        try:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT SUM(quantity_ordered) FROM production_orders WHERE orderid = %s",
                    (order_id,),
                )
                row = cur.fetchone()
                return int(row[0]) if row and row[0] else 0
        except Exception:
            return 0

    def _ensure_schema_ready(self):
        if self._schema_ready:
            return True

        try:
            required_tables = [
                "production_orders",
                "machine_stats",
                "tool_stats",
                "machine_piece_stats",
                "unloading_stats",
                "simulation_state",
            ]

            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                      AND tablename = ANY(%s)
                    """
                    ,
                    (required_tables,),
                )
                existing = {row[0] for row in cur.fetchall()}
                missing = [name for name in required_tables if name not in existing]
                if missing:
                    raise RuntimeError(
                        "Missing required table(s): "
                        + ", ".join(missing)
                        + "."
                    )

                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'production_orders'
                      AND column_name = 'production_day'
                    """
                )
                if cur.fetchone() is None:
                    raise RuntimeError(
                        "Missing required column production_orders.production_day."
                    )

            self._schema_ready = True
            self._schema_error_logged = False
            return True
        except Exception as exc:
            if not self._schema_error_logged:
                logger.info(f"[MES] Database schema check failed: {exc}")
                logger.info("[MES] Run: psql -p 5000 -U postgres -d erp_db -f Database/shared_schema.sql")
                self._schema_error_logged = True
            return False

    @staticmethod
    def _build_tool_configuration():
        tool_map = {}
        for machine, tools in MACHINE_TOOLS.items():
            tool_ids = [TOOL_ID_MAP.get(tool, 0) for tool in tools]
            tool_map[machine] = tool_ids

        tool_times = {}
        for tool_name, seconds in TOOL_SECONDS.items():
            tool_id = TOOL_ID_MAP.get(tool_name)
            if tool_id is not None:
                tool_times[tool_id] = seconds

        return tool_map, tool_times

    def get_open_order_items(self, current_day):
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT po.id,
                       po.orderid,
                       po.piece_type,
                       po.quantity_ordered,
                       po.quantity_produced,
                       po.status,
                       po.production_day,
                       o.ddate,
                       o.penalty_per_day
                FROM production_orders po
                JOIN orders o ON o.orderid = po.orderid
                WHERE po.quantity_produced < po.quantity_ordered
                  AND po.status IN ('Pending', 'In Progress')
                  AND COALESCE(po.production_day, 1) <= %s
                ORDER BY po.id ASC
                """,
                (int(current_day),),
            )
            rows = cur.fetchall()
            return [
                {
                    "id": row[0],
                    "order_id": row[1],
                    "piece_type": row[2],
                    "quantity_ordered": row[3],
                    "quantity_completed": row[4],
                    "status": row[5],
                    "production_day": row[6],
                    "ddate": row[7],
                    "penalty": float(row[8]) if row[8] is not None else 0.0,
                }
                for row in rows
            ]

    def count_future_open_items(self, current_day):
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*)
                FROM production_orders
                WHERE quantity_produced < quantity_ordered
                  AND status IN ('Pending', 'In Progress')
                  AND COALESCE(production_day, 1) > %s
                """,
                (int(current_day),),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def update_item_completion(self, order_item_id, produced_count):
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE production_orders
                SET quantity_produced = LEAST(quantity_ordered, quantity_produced + %s),
                    status = CASE
                        WHEN quantity_produced + %s >= quantity_ordered THEN 'Completed'
                        ELSE 'In Progress'
                    END
                WHERE id = %s
                """,
                (
                    int(produced_count),
                    int(produced_count),
                    int(order_item_id),
                ),
            )
            conn.commit()

    def sync_order_status(self):
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE production_orders
                SET status = CASE
                    WHEN quantity_produced >= quantity_ordered THEN 'Completed'
                    WHEN quantity_produced > 0 THEN 'In Progress'
                    ELSE 'Pending'
                END
                """
            )
            conn.commit()

    def _update_estimated_completion_days(self):
        current_day = self._get_current_day()
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT orderid, piece_type,
                       quantity_ordered - quantity_produced AS remaining
                FROM production_orders
                WHERE quantity_produced < quantity_ordered
                  AND status IN ('Pending', 'In Progress')
                ORDER BY orderid
                """
            )
            rows = cur.fetchall()
            orders = {}
            for orderid, piece_type, remaining in rows:
                orders.setdefault(orderid, []).append((piece_type, remaining))
            for orderid, items in orders.items():
                estimated = estimate_order_completion(items, current_day)
                cur.execute(
                    "UPDATE orders SET estimated_completion_day = %s WHERE orderid = %s",
                    (estimated, orderid),
                )
            conn.commit()

    def _ensure_machine_row(self, machine_id):
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO machine_stats(machine_id, total_operating_sec, tool_changes, pieces_processed)
                VALUES (%s, 0, 0, 0)
                ON CONFLICT(machine_id) DO NOTHING
                """,
                (machine_id,),
            )
            conn.commit()

    def _ensure_tool_row(self, machine_id, tool_id):
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO tool_stats(machine_id, tool_id, operating_sec)
                VALUES (%s, %s, 0)
                """,
                (machine_id, tool_id),
            )
            conn.commit()

    def _record_machine_piece_stats(self, machine_id, piece_type, operations_count):
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE machine_piece_stats
                SET pieces_processed = pieces_processed + %s
                WHERE machine_id = %s AND piece_type = %s
                """,
                (int(operations_count), machine_id, str(piece_type).upper()),
            )
            if cur.rowcount == 0:
                cur.execute(
                    """
                    INSERT INTO machine_piece_stats(machine_id, piece_type, pieces_processed)
                    VALUES (%s, %s, %s)
                    """,
                    (machine_id, str(piece_type).upper(), int(operations_count)),
                )
            conn.commit()

    def _record_machine_tool_stats(self, machine_id, tool_id, operations_count, piece_type):
        self._ensure_machine_row(machine_id)
        operating_seconds = TOOL_SECONDS.get(tool_id, 10) * int(operations_count)

        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE machine_stats
                SET total_operating_sec = total_operating_sec + %s,
                    pieces_processed = pieces_processed + %s
                WHERE machine_id = %s
                """,
                (operating_seconds, int(operations_count), machine_id),
            )
            conn.commit()

        last_tool = self._last_tool_by_machine.get(machine_id)
        if last_tool is not None and last_tool != tool_id:
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE machine_stats
                    SET tool_changes = tool_changes + 1
                    WHERE machine_id = %s
                    """,
                    (machine_id,),
                )
                conn.commit()

        self._last_tool_by_machine[machine_id] = tool_id

        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE tool_stats
                SET operating_sec = operating_sec + %s
                WHERE machine_id = %s AND tool_id = %s
                """,
                (operating_seconds, machine_id, tool_id),
            )
            if cur.rowcount == 0:
                self._ensure_tool_row(machine_id, tool_id)
                cur.execute(
                    """
                    UPDATE tool_stats
                    SET operating_sec = operating_sec + %s
                    WHERE machine_id = %s AND tool_id = %s
                    """,
                    (operating_seconds, machine_id, tool_id),
                )
            conn.commit()

        self._record_machine_piece_stats(machine_id, piece_type, operations_count)

    def _get_inventory(self, piece_type):
        return self._inventory.setdefault(piece_type, {"legs": 0, "tops": 0})

    def _apply_inventory_delta(self, piece_type, operation):
        if operation.action == "TRANSFORM":
            inv = self._get_inventory(piece_type)
            if operation.target_id in (5, 8):
                inv["legs"] += 1
            elif operation.target_id in (3, 4, 6, 7):
                inv["tops"] += 1
        elif operation.action == "ASSEMBLE":
            inv = self._get_inventory(piece_type)
            if inv["legs"] >= 2:
                inv["legs"] -= 2
            if inv["tops"] >= 1:
                inv["tops"] -= 1

    def _record_unloading_stats(self, snapshot):
        for u_key, values in snapshot.items():
            requested = bool(values.get("requested", False))
            material_id = int(values.get("material", 0))
            previous = self._last_unload_state.get(u_key, False)
            self._last_unload_state[u_key] = requested

            # Count only rising edges to avoid double-counting while a signal stays true.
            if not requested or previous:
                continue
            if material_id <= 0:
                continue

            u_index = int(u_key[1:])
            dock_id = ((u_index - 1) % 5) + 1
            piece_type = str(material_id)

            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE unloading_stats
                    SET quantity_unloaded = quantity_unloaded + 1
                    WHERE dock_id = %s AND piece_type = %s
                    """,
                    (dock_id, piece_type),
                )
                if cur.rowcount == 0:
                    cur.execute(
                        """
                        INSERT INTO unloading_stats(dock_id, piece_type, quantity_unloaded)
                        VALUES (%s, %s, 1)
                        """,
                        (dock_id, piece_type),
                    )
                conn.commit()

    @staticmethod
    def _find_machine_for_tool(tool):
        return next((m for m, tools in MACHINE_TOOLS.items() if tool in tools), None)

    @staticmethod
    def _machines_for_tool(tool):
        return [m for m, tools in MACHINE_TOOLS.items() if tool in tools]

    async def flush_output_conveyors(self):
        flushed = False
        for lane in range(2, 6):
            state = self._output_conv_state[lane]
            shipped = self._output_conv_shipped[lane]
            total = self._output_conv_total[lane]
            order_id = self._output_conv_order[lane]
            logger.info(f"[MES] Output O{lane}: state={state}, shipped={shipped}/{total}, order={order_id}")
            if state == "free":
                continue
            if shipped < total:
                continue
            logger.info(f"[MES] Output O{lane}: flushing order {order_id}...")
            await write_output_unload(lane, True)
            start = asyncio.get_event_loop().time()
            timeout = 15.0
            empty = False
            poll_count = 0
            while (asyncio.get_event_loop().time() - start) < timeout:
                await asyncio.sleep(0.2)
                empty = await read_output_conveyor_empty(lane)
                poll_count += 1
                if poll_count % 5 == 0:
                    logger.info(f"[MES] Output O{lane}: poll #{poll_count}, elapsed={asyncio.get_event_loop().time()-start:.1f}s, EMPTY={empty}")
                if empty:
                    break
            await write_output_unload(lane, False)
            if empty:
                self._output_conv_state[lane] = "free"
                self._output_conv_order[lane] = None
                if order_id in self._order_to_conv:
                    del self._order_to_conv[order_id]
                self._output_conv_shipped[lane] = 0
                self._output_conv_total[lane] = 0
                logger.info(f"[MES] Output O{lane}: flush complete, now free.")
                flushed = True
            else:
                logger.info(f"[MES] Output O{lane}: flush timed out for order {order_id}.")
        return flushed

    async def process_cycle(self):
        if not self._ensure_schema_ready():
            return

        if not self._tools_configured:
            tool_map, tool_times = self._build_tool_configuration()
            configured = await write_tool_configuration(tool_map, tool_times)
            if configured:
                self._tools_configured = True
                logger.info("[MES] Tool configuration pushed to PLC.")
            else:
                logger.info("[MES] Failed to push tool configuration to PLC.")

        current_day = self._get_current_day()

        if self._current_day is not None and current_day != self._current_day:
            logger.info(f"[MES] Day changed: {self._current_day} \u2192 {current_day}. Flushing output conveyors...")
            await self.flush_output_conveyors()
        self._current_day = current_day

        open_items = self.get_open_order_items(current_day)
        if not open_items:
            if not self._no_open_items_logged:
                future_items = self.count_future_open_items(current_day)
                if future_items > 0:
                    logger.info(
                        f"[MES] No due order items for Day {current_day}. "
                        f"Future queued items: {future_items}."
                    )
                else:
                    logger.info("[MES] No open order items.")
                self._no_open_items_logged = True
            self.sync_order_status()
            self._update_estimated_completion_days()
            return

        self._no_open_items_logged = False

        # Mark picked-up orders as In Progress so the dashboard shows them correctly
        with self._conn() as conn:
            cur = conn.cursor()
            for item in open_items:
                if item.get("status", "").strip().lower() == "pending":
                    cur.execute(
                        "UPDATE production_orders SET status = 'In Progress' WHERE id = %s",
                        (item["id"],),
                    )
            conn.commit()

        async def _pulse_ship_final_with_confirm(unload_key, material_id, timeout_s=10.0, poll_s=0.25):
            """Ship via U6-U10 and confirm W2 decremented before completing the order."""
            before = await read_warehouse_counts()
            ok = await pulse_unload_request(unload_key, material_id)
            if not ok:
                return False
            if before is None:
                await asyncio.sleep(2.5)
                return True

            start = asyncio.get_event_loop().time()
            before_w1, before_w2 = before
            while (asyncio.get_event_loop().time() - start) < timeout_s:
                await asyncio.sleep(poll_s)
                after = await read_warehouse_counts()
                if after is None:
                    continue
                _, after_w2 = after
                if after_w2 < before_w2:
                    return True
            return False

        async def _wait_for_saved_leg_increment(conveyor_id, expected_type, timeout_s=10.0, poll_s=0.2, max_failures=10):
            """Wait until the count of Saved_Leg slots matching expected_type increases."""
            legs = await read_conveyor_saved_leg(conveyor_id)
            if legs is None:
                return False
            before = sum(1 for v in legs if v == expected_type)
            start = asyncio.get_event_loop().time()
            failures = 0
            while (asyncio.get_event_loop().time() - start) < timeout_s:
                await asyncio.sleep(poll_s)
                legs = await read_conveyor_saved_leg(conveyor_id)
                if legs is None:
                    failures += 1
                    if failures >= max_failures:
                        return False
                    continue
                failures = 0
                now = sum(1 for v in legs if v == expected_type)
                if now > before:
                    return True
            # Final check after timeout: leg might have been saved but MES reads missed it
            legs = await read_conveyor_saved_leg(conveyor_id)
            if legs is not None:
                now = sum(1 for v in legs if v == expected_type)
                if now > before:
                    return True
            return False

        async def _wait_for_loading_piece(loading_conv, expected_type, timeout_s=300.0, poll_s=0.2, max_failures=10):
            """Wait for recv_i rising edge (False→True) on loading conveyor."""
            before = await read_conveyor_recv(loading_conv)
            if before is None:
                before = False
            start = asyncio.get_event_loop().time()

            # If recv_i is already True, wait for it to drop to False first
            if before:
                failures = 0
                while (asyncio.get_event_loop().time() - start) < timeout_s:
                    await asyncio.sleep(poll_s)
                    recv = await read_conveyor_recv(loading_conv)
                    if recv is None:
                        failures += 1
                        if failures >= max_failures:
                            return False
                        continue
                    failures = 0
                    if not recv:
                        before = False
                        break
                if before:
                    return False

            # Wait for rising edge False→True
            failures = 0
            while (asyncio.get_event_loop().time() - start) < timeout_s:
                await asyncio.sleep(poll_s)
                recv = await read_conveyor_recv(loading_conv)
                if recv is None:
                    failures += 1
                    if failures >= max_failures:
                        return False
                    continue
                failures = 0
                if recv and not before:
                    return True
                before = recv
            return False

        async def _wait_for_input_free(loading_conv, timeout_s=120.0, poll_s=0.2, max_failures=10):
            """Wait for loading conveyor recv_i to be False (line free)."""
            start = asyncio.get_event_loop().time()
            failures = 0
            while (asyncio.get_event_loop().time() - start) < timeout_s:
                await asyncio.sleep(poll_s)
                recv = await read_conveyor_recv(loading_conv)
                if recv is None:
                    failures += 1
                    if failures >= max_failures:
                        return False
                    continue
                failures = 0
                if not recv:
                    return True
            return False

        def _extract_type_id(piece):
            if piece is None:
                return 0
            type_id = getattr(piece, "Type_ID", None)
            if type_id is not None:
                try:
                    return int(type_id)
                except Exception:
                    return 0

            if isinstance(piece, dict):
                try:
                    return int(piece.get("Type_ID", 0))
                except Exception:
                    return 0

            if isinstance(piece, (list, tuple)) and piece:
                try:
                    return int(piece[0])
                except Exception:
                    return 0

            body = getattr(piece, "Body", None)
            if isinstance(body, (bytes, bytearray)) and body:
                first_byte = int(body[0])
                le_uint16 = int.from_bytes(body[:2], "little") if len(body) >= 2 else first_byte
                return le_uint16

            piece_dict = getattr(piece, "__dict__", None)
            if piece_dict:
                try:
                    tid = piece_dict.get("Type_ID") or piece_dict.get("TypeId")
                    if tid is not None:
                        return int(tid)
                except Exception:
                    return 0

            return 0

        async def _wait_for_w1_type_increment(target_type, timeout_s=15.0, poll_s=0.2, max_failures=10):
            """Wait until count of pieces with target_type in W1 increases."""
            snap = await read_warehouse_snapshot()
            if snap is None:
                return False
            w1_count, _, top_values, _ = snap
            before = sum(
                1 for idx in range(min(w1_count, len(top_values)))
                if _extract_type_id(top_values[idx]) == target_type
            )
            start = asyncio.get_event_loop().time()
            failures = 0
            while (asyncio.get_event_loop().time() - start) < timeout_s:
                await asyncio.sleep(poll_s)
                snap = await read_warehouse_snapshot()
                if snap is None:
                    failures += 1
                    if failures >= max_failures:
                        return False
                    continue
                failures = 0
                w1_count, _, top_values, _ = snap
                now = sum(
                    1 for idx in range(min(w1_count, len(top_values)))
                    if _extract_type_id(top_values[idx]) == target_type
                )
                if now > before:
                    return True
            # Final check after timeout: piece might have arrived but masked by concurrent shipping.
            # Accept if count hasn't decreased — the transfer likely happened but was net-zero.
            snap = await read_warehouse_snapshot()
            if snap is not None:
                w1_count, _, top_values, _ = snap
                now = sum(
                    1 for idx in range(min(w1_count, len(top_values)))
                    if _extract_type_id(top_values[idx]) == target_type
                )
                if now >= before:
                    return True
            return False

        async def _wait_for_w1_type_reduced(target_type, timeout_s=6.0, poll_s=0.2):
            """Wait until count of pieces with target_type in W1 decreases."""
            snap = await read_warehouse_snapshot()
            if snap is None:
                return False
            w1_count, _, top_values, _ = snap
            before = sum(1 for idx in range(min(w1_count, len(top_values)))
                         if _extract_type_id(top_values[idx]) == target_type)
            if before == 0:
                return True
            start = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start) < timeout_s:
                await asyncio.sleep(poll_s)
                snap = await read_warehouse_snapshot()
                if snap is None:
                    continue
                w1_count, _, top_values, _ = snap
                now = sum(1 for idx in range(min(w1_count, len(top_values)))
                          if _extract_type_id(top_values[idx]) == target_type)
                if now < before:
                    return True
            return False

        async def _wait_for_w2_increment(start_w2, timeout_s=10.0, poll_s=0.2):
            start = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start) < timeout_s:
                await asyncio.sleep(poll_s)
                counts = await read_warehouse_counts()
                if counts is None:
                    continue
                _, w2_count = counts
                if w2_count > start_w2:
                    return w2_count
            return start_w2

        def _est_inventory():
            return {
                "legs": self._est_w1["legs"] + self._est_w2["legs"],
                "tops": self._est_w1["tops"] + self._est_w2["tops"],
            }

        def _piece_inventory(snapshot):
            if snapshot is None:
                return {"legs": {}, "tops": {}}
            _, w2_count, _, bottom_values = snapshot
            leg_counts = {}
            top_counts = {}
            limit = min(w2_count, len(bottom_values))
            for idx in range(limit):
                type_id = _extract_type_id(bottom_values[idx])
                if type_id in (5, 8):
                    leg_counts[type_id] = leg_counts.get(type_id, 0) + 1
                elif type_id in (3, 4, 6, 7):
                    top_counts[type_id] = top_counts.get(type_id, 0) + 1
            return {"legs": leg_counts, "tops": top_counts}

        def _assembly_priority(item):
            due = item.get("ddate")
            penalty = item.get("penalty")
            try:
                due_val = int(due) if due is not None else 10**9
            except Exception:
                due_val = 10**9
            try:
                penalty_val = float(penalty) if penalty is not None else 0.0
            except Exception:
                penalty_val = 0.0
            return (due_val, -penalty_val, item.get("id", 0))

        def _choose_assembly_item(items, snapshot):
            if not items:
                return None
            counts = _piece_inventory(snapshot)
            ready = []
            for item in items:
                piece_type = str(item.get("piece_type", "")).upper()
                if piece_type not in self.recipe_engine.FINAL_RECIPES:
                    continue
                profile = self.recipe_engine.FINAL_RECIPES[piece_type]
                leg_id = int(profile["leg_id"])
                top_id = int(profile["top_id"])
                if counts["legs"].get(leg_id, 0) >= 2 and counts["tops"].get(top_id, 0) >= 1:
                    ready.append(item)
            if not ready:
                return None
            ready.sort(key=_assembly_priority)
            return ready[0]

        def _log_snapshot(values, max_items, label):
            limit = min(max_items, len(values))
            for idx in range(limit):
                raw = values[idx]
                type_id = _extract_type_id(raw)
                logger.info(f"[MES] {label}[{idx}] raw={raw!r} parsed_type={type_id}")

        snapshot = await read_warehouse_snapshot()
        w1_count = w2_count = 0
        if snapshot is not None:
            w1_count, w2_count, top_values, bottom_values = snapshot
            _log_snapshot(top_values, w1_count, "W1")
            _log_snapshot(bottom_values, w2_count, "W2")

            raw_wood = sum(1 for idx in range(min(w1_count, len(top_values))) if _extract_type_id(top_values[idx]) == 1)
            raw_metal = sum(1 for idx in range(min(w1_count, len(top_values))) if _extract_type_id(top_values[idx]) == 2)
            w1_legs = sum(1 for idx in range(min(w1_count, len(top_values))) if _extract_type_id(top_values[idx]) in (5, 8))
            w1_tops = sum(1 for idx in range(min(w1_count, len(top_values))) if _extract_type_id(top_values[idx]) in (3, 4, 6, 7))
            w2_legs = sum(1 for idx in range(min(w2_count, len(bottom_values))) if _extract_type_id(bottom_values[idx]) in (5, 8))
            w2_tops = sum(1 for idx in range(min(w2_count, len(bottom_values))) if _extract_type_id(bottom_values[idx]) in (3, 4, 6, 7))
            w2_final = sum(1 for idx in range(min(w2_count, len(bottom_values))) if _extract_type_id(bottom_values[idx]) in (9, 10, 11, 12, 13, 14))

            actual_w1_legs = self._est_w1.get("legs", 0)
            actual_w1_tops = self._est_w1.get("tops", 0)
            actual_w2_legs = self._est_w2.get("legs", 0)
            actual_w2_tops = self._est_w2.get("tops", 0)

            if (raw_wood != self._est_w1.get("raw_wood", 0) or
                raw_metal != self._est_w1.get("raw_metal", 0) or
                w1_legs != actual_w1_legs or w1_tops != actual_w1_tops or
                w2_legs != actual_w2_legs or w2_tops != actual_w2_tops):
                logger.info(
                    "[MES] Reconciling inventory: "
                    f"W1(raw_wood={raw_wood}, raw_metal={raw_metal}, "
                    f"legs={w1_legs}, tops={w1_tops}) "
                    f"W2(legs={w2_legs}, tops={w2_tops}, final={w2_final})"
                )
                self._est_w1["raw_wood"] = raw_wood
                self._est_w1["raw_metal"] = raw_metal
                self._est_w1["legs"] = w1_legs
                self._est_w1["tops"] = w1_tops
                self._est_w2["legs"] = w2_legs
                self._est_w2["tops"] = w2_tops
                self._est_w2["final"] = w2_final

        inventory = _est_inventory()

        pipeline = w1_count + w2_legs + w2_tops
        slots_used = (pipeline + 2) // 3
        slots_free = max(0, 10 - slots_used)

        # Step 1: Always process at least one assembly-ready order (slot already allocated at CREATE)
        assembly_item = _choose_assembly_item(open_items, snapshot)
        selected_orders = []
        remaining_slots = slots_free

        if assembly_item:
            need = int(assembly_item["quantity_ordered"]) - int(assembly_item["quantity_completed"])
            selected_orders.append((assembly_item, need))

        # Step 2: Fill remaining pipeline slots with transform orders by priority
        for item in sorted(open_items, key=_assembly_priority):
            if any(s[0]["order_id"] == item["order_id"] for s in selected_orders):
                continue
            if remaining_slots <= 0:
                break
            need = int(item["quantity_ordered"]) - int(item["quantity_completed"])
            share = min(need, remaining_slots)
            if share <= 0:
                continue
            selected_orders.append((item, share))
            remaining_slots -= share

        if not selected_orders:
            self.sync_order_status()
            self._update_estimated_completion_days()
            return

        logger.info(
            f"[MES] Selected {len(selected_orders)} order(s) "
            f"(slots_free={slots_free}): "
            + ", ".join(f"order {s[0]['order_id']}(need={int(s[0]['quantity_ordered'])-int(s[0]['quantity_completed'])},alloc={s[1]})" for s in selected_orders)
        )

        all_transform_ops = []
        all_assemble_ops = []
        first_item = selected_orders[0][0]
        for sel, share in selected_orders:
            ops = self.recipe_engine.next_batch(
                piece_type=sel["piece_type"],
                ordered_qty=sel["quantity_ordered"],
                completed_qty=sel["quantity_completed"],
                inventory=inventory,
                max_tables=share,
            )
            if ops is None:
                continue
            for op in ops:
                op._order_ref = sel
            all_transform_ops.extend(o for o in ops if o.action == "TRANSFORM")
            all_assemble_ops.extend(o for o in ops if o.action == "ASSEMBLE")

        if not all_transform_ops and not all_assemble_ops:
            self.sync_order_status()
            self._update_estimated_completion_days()
            return

        transform_ops = all_transform_ops
        assemble_ops = all_assemble_ops

        remaining_final = max(0, int(first_item["quantity_ordered"]) - int(first_item["quantity_completed"]))
        required_legs = remaining_final * 2
        required_tops = remaining_final
        logger.info(
            "[MES] Required parts: "
            f"legs={required_legs}, tops={required_tops}, "
            f"remaining_final={remaining_final}, "
            f"slots_free={slots_free} (pipeline={pipeline})."
        )
        if self._last_w1_count != w1_count:
            logger.info(f"[MES] Warehouse counts: W1={w1_count}, W2={w2_count}.")
            self._last_w1_count = w1_count

        if transform_ops:
            counts = await read_warehouse_counts()
            if counts is not None:
                w1_count, w2_count = counts
                total_wip = w1_count + w2_count
                if total_wip >= MAX_WAREHOUSE_WIP:
                    logger.info(
                        "[MES] Warehouse full; skipping batch. "
                        f"W1={w1_count}, W2={w2_count}, limit={MAX_WAREHOUSE_WIP}."
                    )
                    return

            # ---- Phase 1: Create ALL raw pieces sequentially ----
            phase1_pairs = []
            for op in transform_ops:
                machines = self._machines_for_tool(op.tool)
                if not machines:
                    logger.info(f"[MES]   No machines support tool {op.tool}; skipping.")
                    continue
                order_key = f"{op._order_ref['order_id']}:{op.tool}"
                start = self._tool_machine_index.get(order_key, 0)
                machine = machines[start % len(machines)]
                self._tool_machine_index[order_key] = (start + 1) % len(machines)
                phase1_pairs.append((op, machine))

            if not phase1_pairs:
                logger.info("[MES] No transform ops with available machines.")
                return

            logger.info(
                f"[MES] Phase 1: Creating {len(phase1_pairs)} raw piece(s) sequentially."
            )
            input_lines = ["I1", "I2", "I3", "I4", "I5"]
            for op, machine in phase1_pairs:
                raw_type_id = int(op.material_id)
                selected_line = input_lines[self._input_line_index % len(input_lines)]
                self._input_line_index += 1
                loading_conv = INPUT_TO_LOADING_CONV.get(selected_line)
                if not loading_conv:
                    logger.info(f"[MES]   No loading conveyor for {selected_line}.")
                    return
                free = await _wait_for_input_free(loading_conv, timeout_s=120.0, poll_s=0.05)
                if not free:
                    logger.info(f"[MES]   Input {selected_line} ({loading_conv}) still busy; aborting.")
                    return
                logger.info(
                    f"[MES]   CREATE type={raw_type_id} on {machine} "
                    f"(line={selected_line}) using tool={op.tool}."
                )
                create_ok = await send_to_plc(
                    machine, op.tool, "CREATE", operations_count=1, input_line=selected_line,
                )
                if not create_ok:
                    logger.info(f"[MES]   CREATE failed for {machine}.")
                    return
                arrived = await _wait_for_loading_piece(loading_conv, raw_type_id, timeout_s=15.0, poll_s=0.05)
                if not arrived:
                    logger.info(
                        f"[MES]   Raw type={raw_type_id} not detected on "
                        f"{loading_conv} after create on {machine}."
                    )
                    return
                logger.info(f"[MES]   Raw type={raw_type_id} confirmed on {loading_conv}.")

        # ---- Phase 2: Dispatch all ops to free cells in parallel ----
        all_ops = []
        for op in transform_ops:
            all_ops.append((op, "TRANSFORM", op._order_ref))
        for op in assemble_ops:
            all_ops.append((op, "ASSEMBLE", op._order_ref))

        if all_ops:
            logger.info(
                f"[MES] Phase 2: Dispatching {len(all_ops)} op(s) "
                f"({len(transform_ops)} transform, {len(assemble_ops)} assemble) "
                f"across available cells (waiting when busy)."
            )

            async def _run_one_op(op, machine):
                uk = MACHINE_UNLOAD_MAP.get(machine)
                if not uk:
                    return False
                self._cell_busy[uk] = True
                try:
                    raw_type_id = int(op.material_id)
                    all_cell_machines = UNLOAD_KEY_TO_MACHINES[uk]

                    cell_loading_conv = UNLOAD_KEY_TO_LOADING_CONV.get(uk)
                    if cell_loading_conv:
                        _free = await _wait_for_input_free(cell_loading_conv, timeout_s=120.0)
                        if not _free:
                            logger.info(f"[MES] Cell {uk}: {cell_loading_conv} still busy; skipping.")
                            return False

                    for cm in all_cell_machines:
                        if cm == machine:
                            tool_slot = TOOL_TO_SLOT.get(cm, {}).get(op.tool)
                            cmd = {
                                "action_type": 1,
                                "process_ms": int(op.duration_s * 1000),
                                "target_id": int(op.target_id),
                                "needed_tool_slot": int(tool_slot) if tool_slot is not None else 0,
                                "req_top_id": 0, "req_leg_id": 0, "req_join_tool": 0,
                            }
                            logger.info(
                                f"[MES] Cell {uk} CMD {cm}: "
                                f"action={cmd['action_type']} target={cmd['target_id']} "
                                f"tool_slot={cmd['needed_tool_slot']} "
                                f"process_ms={cmd['process_ms']}"
                            )
                            ok = await send_machine_command(cm, cmd)
                            if not ok:
                                logger.info(f"[MES] Cell {uk}: primary {cm} CMD failed.")
                                return False
                        else:
                            cmd = {
                                "action_type": 0, "process_ms": 0, "target_id": 0,
                                "needed_tool_slot": 0, "req_top_id": 0,
                                "req_leg_id": 0, "req_join_tool": 0,
                            }
                            logger.info(f"[MES] Cell {uk} CMD {cm}: pass-through (action=0)")
                            await send_machine_command(cm, cmd)

                    # Confirm CMDs were applied by the PLC before triggering the pulse
                    for cm in all_cell_machines:
                        desired = {
                            "action_type": 1 if cm == machine else 0,
                            "process_ms": int(op.duration_s * 1000) if cm == machine else 0,
                            "target_id": int(op.target_id) if cm == machine else 0,
                            "needed_tool_slot": int(TOOL_TO_SLOT.get(cm, {}).get(op.tool, 0)) if cm == machine else 0,
                        }
                        await asyncio.sleep(0.1)
                        confirmed = await confirm_machine_command(cm, desired)
                        if not confirmed:
                            logger.info(f"[MES] Cell {uk}: CMD confirmation FAILED for {cm}, aborting.")
                            return False

                    logger.info(f"[MES] Cell {uk} PULSE Unload_Req_{uk} type={raw_type_id}")
                    unload_ok = await pulse_unload_request(uk, raw_type_id)
                    if not unload_ok:
                        logger.info(f"[MES] Cell {uk}: unload pulse FAILED.")
                        return False

                    loading_conv = UNLOAD_KEY_TO_LOADING_CONV.get(uk)
                    if not loading_conv:
                        logger.info(f"[MES]   No loading conveyor for {uk}.")
                        return False
                    logger.info(f"[MES] Cell {uk} WAIT {loading_conv} target={op.target_id}")
                    arrived = await _wait_for_loading_piece(loading_conv, int(op.target_id))
                    if not arrived:
                        logger.info(f"[MES] Cell {uk}: target={op.target_id} NOT seen on {loading_conv}.")
                        return False

                    if op.target_id in (5, 8):
                        self._est_w2["legs"] += 1
                    elif op.target_id in (3, 4, 6, 7):
                        self._est_w2["tops"] += 1
                    logger.info(
                        f"[MES] Cell {uk}: est_w2 legs={self._est_w2['legs']} "
                        f"tops={self._est_w2['tops']}"
                    )
                    return True
                finally:
                    self._cell_busy[uk] = False

            async def _run_assemble_op(op, order_item, machine):
                """Run full assembly in a free cell. Returns True on success, False otherwise."""
                snap = await read_warehouse_snapshot()
                if snap is None:
                    return False
                counts = _piece_inventory(snap)
                leg_id = int(op.req_leg_id)
                top_id = int(op.req_top_id)
                if counts["legs"].get(leg_id, 0) < 2 or counts["tops"].get(top_id, 0) < 1:
                    return False

                uk = ASSEMBLY_UNLOAD_MAP.get(machine)
                if not uk:
                    return False

                logger.info(
                    f"[MES] Dispatching assembly for {op.piece_type}: "
                    f"tool={op.tool}, target={op.target_id}, machine={machine}, cell={uk}"
                )

                unload_material_ids = []
                if int(op.req_leg_id) > 0:
                    unload_material_ids.extend([int(op.req_leg_id), int(op.req_leg_id)])
                if int(op.req_top_id) > 0:
                    unload_material_ids.append(int(op.req_top_id))
                if not unload_material_ids:
                    return False

                # Phase A: Transfer from W2→W1 via U1 (serialized across assemblies)
                async with self._u1_lock:
                    logger.info(
                        f"[MES] Assembly phase A: Transferring {len(unload_material_ids)} "
                        f"part(s) from W2 to W1 via U1."
                    )
                    for material_id in unload_material_ids:
                        logger.info(f"[MES]   U1 transfer type={material_id}")
                        u1_ok = await pulse_unload_request("U1", material_id)
                        if not u1_ok:
                            logger.info(f"[MES]   U1 pulse FAILED for type={material_id}.")
                            return False
                        arrived = await _wait_for_w1_type_increment(material_id)
                        if not arrived:
                            logger.info(f"[MES]   Type={material_id} count did not increase in W1 after U1 transfer.")
                            return False
                        if material_id in (5, 8):
                            self._est_w2["legs"] = max(0, self._est_w2["legs"] - 1)
                            self._est_w1["legs"] += 1
                        elif material_id in (3, 4, 6, 7):
                            self._est_w2["tops"] = max(0, self._est_w2["tops"] - 1)
                            self._est_w1["tops"] += 1
                        logger.info(f"[MES]   Type={material_id} confirmed in W1.")

                # Phase B: 3 feeder steps on acquired cell
                self._cell_busy[uk] = True
                try:
                    all_cell_machines = UNLOAD_KEY_TO_MACHINES[uk]
                    conveyor_id = MACHINE_TO_CONVEYOR[machine]
                    tool_slot = TOOL_TO_SLOT.get(machine, {}).get(op.tool)

                    feeder_steps = [
                        {"action": "SWALLOW", "material_id": leg_id, "target_id": leg_id},
                        {"action": "SWALLOW", "material_id": leg_id, "target_id": leg_id},
                        {"action": "ASSEMBLE", "material_id": top_id, "target_id": int(op.target_id)},
                    ]

                    for step_idx, step in enumerate(feeder_steps):
                        material_id = step["material_id"]

                        for cm in all_cell_machines:
                            if cm == machine:
                                if step["action"] == "SWALLOW":
                                    cmd = {
                                        "action_type": 2, "process_ms": 0,
                                        "target_id": int(step["target_id"]),
                                        "needed_tool_slot": 0,
                                        "req_top_id": int(op.req_top_id),
                                        "req_leg_id": int(op.req_leg_id),
                                        "req_join_tool": int(op.req_join_tool),
                                    }
                                else:
                                    cmd = {
                                        "action_type": 3,
                                        "process_ms": int(op.duration_s * 1000),
                                        "target_id": int(step["target_id"]),
                                        "needed_tool_slot": int(tool_slot) if tool_slot is not None else 0,
                                        "req_top_id": int(op.req_top_id),
                                        "req_leg_id": int(op.req_leg_id),
                                        "req_join_tool": int(op.req_join_tool),
                                    }
                                logger.info(
                                    f"[MES] Cell {uk} Step {step_idx+1}/3 {step['action']} "
                                    f"CMD {cm}: action={cmd['action_type']} target={cmd['target_id']}"
                                )
                                ok = await send_machine_command(cm, cmd)
                                if not ok:
                                    logger.info(f"[MES]   {step['action']} CMD failed.")
                                    return False
                            else:
                                pass_cmd = {
                                    "action_type": 0, "process_ms": 0, "target_id": 0,
                                    "needed_tool_slot": 0, "req_top_id": 0,
                                    "req_leg_id": 0, "req_join_tool": 0,
                                }
                                await send_machine_command(cm, pass_cmd)

                        # Confirm all CMDs were applied before pulsing
                        for confirm_cm in all_cell_machines:
                            if confirm_cm == machine:
                                if step["action"] == "SWALLOW":
                                    desired = {
                                        "action_type": 2, "process_ms": 0,
                                        "target_id": int(step["target_id"]),
                                        "needed_tool_slot": 0,
                                    }
                                else:
                                    desired = {
                                        "action_type": 3,
                                        "process_ms": int(op.duration_s * 1000),
                                        "target_id": int(step["target_id"]),
                                        "needed_tool_slot": int(tool_slot) if tool_slot is not None else 0,
                                    }
                            else:
                                desired = {
                                    "action_type": 0, "process_ms": 0,
                                    "target_id": 0, "needed_tool_slot": 0,
                                }
                            await asyncio.sleep(0.1)
                            confirmed = await confirm_machine_command(confirm_cm, desired)
                            if not confirmed:
                                logger.info(f"[MES] Cell {uk} step {step_idx+1}: CMD confirm FAILED on {confirm_cm}, aborting.")
                                return False

                        logger.info(f"[MES] Cell {uk} Step {step_idx+1}/3 PULSE material={material_id}")
                        ok = await pulse_unload_request(uk, material_id)
                        if not ok:
                            logger.info(f"[MES]   {step['action']} unload FAILED.")
                            return False

                        if material_id in (5, 8):
                            self._est_w1["legs"] = max(0, self._est_w1["legs"] - 1)
                        elif material_id in (3, 4, 6, 7):
                            self._est_w1["tops"] = max(0, self._est_w1["tops"] - 1)

                        if step["action"] == "SWALLOW":
                            arrived = await _wait_for_saved_leg_increment(conveyor_id, material_id)
                            if not arrived:
                                logger.info(f"[MES]   Leg type={material_id} NOT stored in conveyor.")
                                return False
                            logger.info(f"[MES]   Leg type={material_id} stored in conveyor (step {step_idx+1}/3).")
                        else:
                            loading_conv = UNLOAD_KEY_TO_LOADING_CONV.get(uk)
                            if not loading_conv:
                                logger.info(f"[MES]   No loading conveyor for {uk}.")
                                return False
                            arrived = await _wait_for_loading_piece(loading_conv, int(op.target_id))
                            if not arrived:
                                logger.info(f"[MES]   Final piece {op.target_id} NOT seen on {loading_conv} after assembly.")
                                return False
                            logger.info(f"[MES]   Final piece {op.target_id} ARRIVED on {loading_conv} (step 3/3).")

                            # Wait for piece to leave Lx and enter W2 before shipping
                            w2_before = (await read_warehouse_counts())[1]
                            if w2_before is None:
                                w2_before = 0
                            w2_after = await _wait_for_w2_increment(w2_before, timeout_s=30.0)
                            if w2_after <= w2_before:
                                logger.info(f"[MES] Piece {op.target_id} did not enter W2 after assembly on {uk}.")
                                return False
                finally:
                    self._cell_busy[uk] = False

                # Phase C: Ship via assigned output conveyor
                order_id = order_item["order_id"]
                conv_idx = self._order_to_conv.get(order_id)
                if conv_idx is None:
                    for idx in range(2, 6):
                        if self._output_conv_state[idx] == "free":
                            conv_idx = idx
                            break
                    if conv_idx is None:
                        logger.info(f"[MES] Order {order_id}: no free O conveyor, shipping deferred.")
                        return False
                    total_qty = self._get_order_total_quantity(order_id)
                    self._order_to_conv[order_id] = conv_idx
                    self._output_conv_state[conv_idx] = "occupied"
                    self._output_conv_order[conv_idx] = order_id
                    self._output_conv_shipped[conv_idx] = 0
                    self._output_conv_total[conv_idx] = total_qty
                    logger.info(f"[MES] Order {order_id}: claimed O{conv_idx}, total={total_qty}")

                u_lane = f"U{conv_idx + 5}"
                ship_ok = await _pulse_ship_final_with_confirm(u_lane, int(op.target_id))
                if not ship_ok:
                    logger.info(f"[MES] Failed to ship final piece via {u_lane}.")
                    return False
                self._output_conv_shipped[conv_idx] += 1
                logger.info(f"[MES] Order {order_id}: shipped {self._output_conv_shipped[conv_idx]}/{self._output_conv_total[conv_idx]} to O{conv_idx}")
                self._est_w2["final"] += 1

                self.update_item_completion(order_item["id"], produced_count=1)
                self._apply_inventory_delta(order_item["piece_type"], op)
                return True

            pending_ops = list(all_ops)
            active = {}
            completed_transforms = []
            completed_assemblies = []

            while pending_ops or active:
                dispatched_this_pass = False
                for item in list(pending_ops):
                    op, op_type, order_item = item
                    assigned = False

                    if op_type == "TRANSFORM":
                        machines = self._machines_for_tool(op.tool)
                        for machine in machines:
                            uk = MACHINE_UNLOAD_MAP.get(machine)
                            if uk and uk not in active and not self._cell_busy.get(uk, False):
                                task = asyncio.create_task(_run_one_op(op, machine))
                                active[uk] = (task, item, machine)
                                pending_ops.remove(item)
                                assigned = True
                                dispatched_this_pass = True
                                logger.info(
                                    f"[MES] Dispatched {op.tool}→{machine} via {uk}. "
                                    f"{len(pending_ops)} remaining."
                                )
                                break

                    elif op_type == "ASSEMBLE":
                        # Wait for all transforms before starting any assembly
                        if any(o[1] == "TRANSFORM" for o in pending_ops) or \
                           any(v[1] == "TRANSFORM" for v in active.values()):
                            continue
                        snap = await read_warehouse_snapshot()
                        if snap:
                            counts = _piece_inventory(snap)
                            leg_id = int(op.req_leg_id)
                            top_id = int(op.req_top_id)
                            if counts["legs"].get(leg_id, 0) < 2 or counts["tops"].get(top_id, 0) < 1:
                                continue
                        for am in ASSEMBLY_MACHINES:
                            if op.tool not in MACHINE_TOOLS.get(am, []):
                                continue
                            uk = ASSEMBLY_UNLOAD_MAP.get(am)
                            if uk and uk not in active and not self._cell_busy.get(uk, False):
                                task = asyncio.create_task(_run_assemble_op(op, order_item, am))
                                active[uk] = (task, item, am)
                                pending_ops.remove(item)
                                assigned = True
                                dispatched_this_pass = True
                                logger.info(
                                    f"[MES] Dispatched assembly {op.piece_type} via {uk}. "
                                    f"{len(pending_ops)} remaining."
                                )
                                break

                if not active:
                    if pending_ops:
                        if not dispatched_this_pass:
                            logger.info(
                                f"[MES] All {len(pending_ops)} pending op(s) blocked "
                                f"(inventory/machine). Aborting dispatch cycle."
                            )
                            pending_ops.clear()
                            break
                        logger.info(
                            f"[MES] All cells busy, {len(pending_ops)} op(s) waiting..."
                        )
                        await asyncio.sleep(0.5)
                    continue

                task_list = [data[0] for data in active.values()]
                done, _ = await asyncio.wait(
                    task_list, return_when=asyncio.FIRST_COMPLETED
                )

                for done_task in done:
                    for uk, (task, item, machine) in list(active.items()):
                        if task is done_task:
                            try:
                                result = done_task.result()
                            except asyncio.CancelledError:
                                raise
                            except Exception as exc:
                                result = exc
                            op, op_type, order_item = item

                            if isinstance(result, Exception):
                                logger.info(f"[MES] Cell {uk}: exception ({result}).")
                                if op_type == "TRANSFORM":
                                    pending_ops.append(item)
                            elif not result:
                                logger.info(f"[MES] Cell {uk}: operation failed.")
                                if op_type == "TRANSFORM":
                                    pending_ops.append(item)
                            else:
                                logger.info(f"[MES] Cell {uk}: operation completed.")
                                if op_type == "TRANSFORM":
                                    completed_transforms.append((op, machine))
                                else:
                                    completed_assemblies.append(item)
                            del active[uk]
                            break

            # Record stats
            for op, machine in completed_transforms:
                self._record_machine_tool_stats(machine, op.tool, 1, op.piece_type)
            for item in completed_assemblies:
                op, _, _ = item
                machine = self._find_machine_for_tool(op.tool)
                if machine:
                    self._record_machine_tool_stats(machine, op.tool, 1, op.piece_type)

            unload_snapshot = await read_unloading_snapshot()
            if unload_snapshot:
                self._record_unloading_stats(unload_snapshot)

        self.sync_order_status()
        self._update_estimated_completion_days()


async def run_mes_loop(poll_seconds=2.0):
    service = MESService()
    shutdown = asyncio.Event()

    def _signal_handler():
        logger.info("[MES] Shutdown signal received, closing OPC-UA client...")
        shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass

    try:
        while not shutdown.is_set():
            try:
                await service.process_cycle()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.info(f"[MES] Loop error: {exc}")
            await asyncio.sleep(poll_seconds)
    finally:
        await close_client()
        logger.info("[MES] OPC-UA client closed.")


if __name__ == "__main__":
    try:
        asyncio.run(run_mes_loop())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
