import asyncio
import psycopg2

from mes_recipe_engine import RecipeEngine
from mes_scheduler import MACHINE_TOOLS, TOOL_TO_SLOT, ASSEMBLY_MACHINES
from plc_client import (
    read_unloading_snapshot,
    send_to_plc,
    send_machine_command,
    read_warehouse_counts,
    pulse_unload_request,
    write_tool_configuration,
    read_warehouse_snapshot,
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
    "T5": 30,
    "T6": 25,
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
                print(f"[MES] Database schema check failed: {exc}")
                print("[MES] Run: psql -p 5000 -U postgres -d erp_db -f Database/shared_schema.sql")
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
                SELECT id, orderid, piece_type, quantity_ordered,
                       quantity_produced, status, production_day
                FROM production_orders
                WHERE quantity_produced < quantity_ordered
                  AND status IN ('Pending', 'In Progress')
                  AND COALESCE(production_day, 1) <= %s
                ORDER BY id ASC
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

    async def process_cycle(self):
        if not self._ensure_schema_ready():
            return

        if not self._tools_configured:
            tool_map, tool_times = self._build_tool_configuration()
            configured = await write_tool_configuration(tool_map, tool_times)
            if configured:
                self._tools_configured = True
                print("[MES] Tool configuration pushed to PLC.")
            else:
                print("[MES] Failed to push tool configuration to PLC.")

        current_day = self._get_current_day()
        open_items = self.get_open_order_items(current_day)
        if not open_items:
            if not self._no_open_items_logged:
                future_items = self.count_future_open_items(current_day)
                if future_items > 0:
                    print(
                        f"[MES] No due order items for Day {current_day}. "
                        f"Future queued items: {future_items}."
                    )
                else:
                    print("[MES] No open order items.")
                self._no_open_items_logged = True
            self.sync_order_status()
            return

        self._no_open_items_logged = False

        async def _pulse_unload_with_wait(unload_key, material_id, timeout_s=8.0, poll_s=0.2):
            before = await read_warehouse_counts()
            ok = await pulse_unload_request(unload_key, material_id)
            if not ok:
                return False
            if before is None:
                await asyncio.sleep(2.5)
                return True

            start = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start) < timeout_s:
                await asyncio.sleep(poll_s)
                after = await read_warehouse_counts()
                if after is None:
                    continue
                if after != before:
                    return True
            return True

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

            piece_dict = getattr(piece, "__dict__", None)
            if piece_dict:
                try:
                    return int(piece_dict.get("Type_ID", 0))
                except Exception:
                    return 0

            body = getattr(piece, "Body", None)
            if isinstance(body, (bytes, bytearray)) and body:
                first_byte = int(body[0])
                le_uint16 = int.from_bytes(body[:2], "little") if len(body) >= 2 else first_byte
                print(
                    f"[MES] ExtensionObject Body={body!r} first_byte={first_byte} le_uint16={le_uint16}"
                )
                return le_uint16

            return 0

        async def _wait_for_w1_increment(start_w1, timeout_s=6.0, poll_s=0.2):
            start = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start) < timeout_s:
                await asyncio.sleep(poll_s)
                counts = await read_warehouse_counts()
                if counts is None:
                    continue
                w1_count, _ = counts
                if w1_count > start_w1:
                    return w1_count
            return start_w1

        def _est_inventory():
            return {
                "legs": self._est_w1["legs"] + self._est_w2["legs"],
                "tops": self._est_w1["tops"] + self._est_w2["tops"],
            }

        def _log_snapshot(values, max_items, label):
            limit = min(max_items, len(values))
            for idx in range(limit):
                raw = values[idx]
                type_id = _extract_type_id(raw)
                print(f"[MES] {label}[{idx}] raw={raw!r} parsed_type={type_id}")

        first_item = open_items[0]
        inventory = _est_inventory()
        snapshot = await read_warehouse_snapshot()
        w1_count = w2_count = 0
        if snapshot is not None:
            w1_count, w2_count, top_values, bottom_values = snapshot
            _log_snapshot(top_values, w1_count, "W1")
            _log_snapshot(bottom_values, w2_count, "W2")

        remaining_final = max(
            0,
            int(first_item["quantity_ordered"]) - int(first_item["quantity_completed"]),
        )
        required_legs = remaining_final * 2
        required_tops = remaining_final
        print(
            "[MES] Required parts: "
            f"legs={required_legs}, tops={required_tops}, remaining_final={remaining_final}."
        )
        if self._last_w1_count != w1_count:
            print(f"[MES] Warehouse counts: W1={w1_count}, W2={w2_count}.")
            self._last_w1_count = w1_count
        op = self.recipe_engine.next_operation(
            piece_type=first_item["piece_type"],
            ordered_qty=first_item["quantity_ordered"],
            completed_qty=first_item["quantity_completed"],
            inventory=inventory,
        )

        if op is None:
            self.sync_order_status()
            return

        machine = self._find_machine_for_tool(op.tool)
        if not machine:
            print(f"[MES] No machine found for tool {op.tool}")
            return

        if op.action == "TRANSFORM":
            counts = await read_warehouse_counts()
            if counts is not None:
                w1_count, w2_count = counts
                total_wip = w1_count + w2_count
                if total_wip >= MAX_WAREHOUSE_WIP:
                    print(
                        "[MES] Warehouse full; skipping create-piece dispatch. "
                        f"W1={w1_count}, W2={w2_count}, limit={MAX_WAREHOUSE_WIP}."
                    )
                    return

            legs_available = inventory["legs"]
            tops_available = inventory["tops"]
            if op.target_id in (5, 8) and legs_available >= required_legs:
                print("[MES] Legs already satisfied; skipping leg transform.")
                return
            if op.target_id in (3, 4, 6, 7) and tops_available >= required_tops:
                print("[MES] Tops already satisfied; skipping top transform.")
                return

            before_w1 = w1_count

            print(
                f"[MES] Dispatching transform for {op.piece_type}: "
                f"tool={op.tool}, target={op.target_id}, machine={machine}, "
                f"production_day={first_item['production_day']}, current_day={current_day}"
            )
            print(
                "[MES] Spawning material: "
                f"material_id={op.material_id}, target_id={op.target_id}, tool={op.tool}."
            )
            input_lines = ["I1", "I2", "I3", "I4", "I5"]
            material_key = 1 if op.material_id == 1 else 2
            next_index = self._next_input_index[material_key] % len(input_lines)
            chosen_input = input_lines[next_index]
            self._next_input_index[material_key] = next_index + 1

            create_ok = await send_to_plc(
                machine,
                op.tool,
                "CREATE",
                operations_count=1,
                input_line=chosen_input,
            )
            if not create_ok:
                print("[MES] PLC create-piece failed; dispatch aborted.")
                return

            new_w1 = await _wait_for_w1_increment(before_w1)
            if new_w1 == before_w1:
                print(
                    "[MES] Create-piece did not increase W1 count; skipping further creates."
                )
                return
            if op.target_id in (5, 8):
                self._est_w1["legs"] += 1
            elif op.target_id in (3, 4, 6, 7):
                self._est_w1["tops"] += 1

            tool_slot = TOOL_TO_SLOT.get(machine, {}).get(op.tool)
            if tool_slot is None:
                print(f"[MES] No tool slot mapping for {machine} {op.tool}.")
                return

            command = {
                "action_type": 1,
                "process_ms": int(op.duration_s * 1000),
                "target_id": int(op.target_id),
                "needed_tool_slot": int(tool_slot),
                "req_top_id": 0,
                "req_leg_id": 0,
                "req_join_tool": 0,
            }
            plc_ok = await send_machine_command(machine, command)
        else:
            print(
                f"[MES] Dispatching assembly for {op.piece_type}: "
                f"tool={op.tool}, target={op.target_id}, machine={machine}, "
                f"production_day={first_item['production_day']}, current_day={current_day}"
            )
            if machine not in ASSEMBLY_MACHINES:
                print(f"[MES] Machine {machine} is not configured for assembly.")
                return

            unload_key = ASSEMBLY_UNLOAD_MAP.get(machine)
            if not unload_key:
                print(f"[MES] No unload conveyor mapping for {machine}.")
                return

            unload_material_ids = []
            if int(op.req_leg_id) > 0:
                unload_material_ids.extend([int(op.req_leg_id), int(op.req_leg_id)])
            if int(op.req_top_id) > 0:
                unload_material_ids.append(int(op.req_top_id))

            if unload_material_ids:
                # Move needed parts from W2 -> W1 via U1 before unloading to machines.
                for material_id in unload_material_ids:
                    if material_id in (5, 8) and self._est_w1["legs"] > 0:
                        continue
                    if material_id in (3, 4, 6, 7) and self._est_w1["tops"] > 0:
                        continue
                    transfer_ok = await _pulse_unload_with_wait("U1", material_id)
                    if not transfer_ok:
                        print(
                            f"[MES] Failed to transfer material {material_id} from W2 via U1."
                        )
                        return

                    if material_id in (5, 8):
                        self._est_w2["legs"] = max(0, self._est_w2["legs"] - 1)
                        self._est_w1["legs"] += 1
                    elif material_id in (3, 4, 6, 7):
                        self._est_w2["tops"] = max(0, self._est_w2["tops"] - 1)
                        self._est_w1["tops"] += 1

                for material_id in unload_material_ids:
                    unload_ok = await _pulse_unload_with_wait(unload_key, material_id)
                    if not unload_ok:
                        print(
                            f"[MES] Failed to trigger unload request for {unload_key} "
                            f"material={material_id}."
                        )
                        return
                    if material_id in (5, 8):
                        self._est_w1["legs"] = max(0, self._est_w1["legs"] - 1)
                    elif material_id in (3, 4, 6, 7):
                        self._est_w1["tops"] = max(0, self._est_w1["tops"] - 1)

            tool_slot = TOOL_TO_SLOT.get(machine, {}).get(op.tool)
            if tool_slot is None:
                print(f"[MES] No tool slot mapping for {machine} {op.tool}.")
                return

            command = {
                "action_type": 3,
                "process_ms": int(op.duration_s * 1000),
                "target_id": int(op.target_id),
                "needed_tool_slot": int(tool_slot),
                "req_top_id": int(op.req_top_id),
                "req_leg_id": int(op.req_leg_id),
                "req_join_tool": int(op.req_join_tool),
            }
            plc_ok = await send_machine_command(machine, command)
            if plc_ok:
                self._est_w2["final"] += 1
        if not plc_ok:
            print("[MES] PLC dispatch failed; order progress was not updated.")
            return

        self._record_machine_tool_stats(machine, op.tool, 1, op.piece_type)

        unload_snapshot = await read_unloading_snapshot()
        if unload_snapshot:
            self._record_unloading_stats(unload_snapshot)

        if op.action == "ASSEMBLE":
            self.update_item_completion(first_item["id"], produced_count=1)
        self._apply_inventory_delta(first_item["piece_type"], op)
        self.sync_order_status()


async def run_mes_loop(poll_seconds=2.0):
    service = MESService()
    while True:
        try:
            await service.process_cycle()
        except Exception as exc:
            print(f"[MES] Loop error: {exc}")
        await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    asyncio.run(run_mes_loop())
