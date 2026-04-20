import asyncio
import psycopg2

from mes_recipe_engine import RecipeEngine
from mes_scheduler import MACHINE_TOOLS
from plc_client import read_unloading_snapshot, send_to_plc

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


class MESService:
    def __init__(self):
        self.recipe_engine = RecipeEngine()
        self._last_tool_by_machine = {}
        self._last_unload_state = {f"U{i}": False for i in range(1, 11)}
        self._schema_ready = False
        self._schema_error_logged = False
        self._no_open_items_logged = False

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
            with self._conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS production_orders (
                        id SERIAL PRIMARY KEY,
                        orderid VARCHAR(50) NOT NULL,
                        piece_type VARCHAR(10) NOT NULL,
                        quantity_ordered INT NOT NULL,
                        production_day INT DEFAULT 1,
                        quantity_produced INT DEFAULT 0,
                        status VARCHAR(20) DEFAULT 'Pending'
                    )
                    """
                )
                cur.execute(
                    """
                    ALTER TABLE production_orders
                    ADD COLUMN IF NOT EXISTS production_day INT DEFAULT 1
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS machine_stats (
                        machine_id VARCHAR(10) PRIMARY KEY,
                        total_operating_sec INT DEFAULT 0,
                        tool_changes INT DEFAULT 0,
                        pieces_processed INT DEFAULT 0
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tool_stats (
                        id SERIAL PRIMARY KEY,
                        machine_id VARCHAR(10) REFERENCES machine_stats(machine_id),
                        tool_id VARCHAR(10) NOT NULL,
                        operating_sec INT DEFAULT 0
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS machine_piece_stats (
                        id SERIAL PRIMARY KEY,
                        machine_id VARCHAR(10) REFERENCES machine_stats(machine_id),
                        piece_type VARCHAR(10) NOT NULL,
                        pieces_processed INT DEFAULT 0,
                        UNIQUE(machine_id, piece_type)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS unloading_stats (
                        id SERIAL PRIMARY KEY,
                        dock_id INT NOT NULL,
                        piece_type VARCHAR(10) NOT NULL,
                        quantity_unloaded INT DEFAULT 0
                    )
                    """
                )
                conn.commit()

            self._schema_ready = True
            self._schema_error_logged = False
            return True
        except Exception as exc:
            if not self._schema_error_logged:
                print(f"[MES] Database schema check failed: {exc}")
                print("[MES] Run: psql -p 5000 -U postgres -d erp_db -f Database/shared_schema.sql")
                self._schema_error_logged = True
            return False

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

        first_item = open_items[0]
        op = self.recipe_engine.next_operation(
            piece_type=first_item["piece_type"],
            ordered_qty=first_item["quantity_ordered"],
            completed_qty=first_item["quantity_completed"],
        )

        if op is None:
            self.sync_order_status()
            return

        machine = self._find_machine_for_tool(op.tool)
        if not machine:
            print(f"[MES] No machine found for tool {op.tool}")
            return

        print(
            f"[MES] Dispatching {op.step} for {op.piece_type}: "
            f"tool={op.tool}, count={op.quantity}, machine={machine}, "
            f"production_day={first_item['production_day']}, current_day={current_day}"
        )
        plc_ok = await send_to_plc(machine, op.tool, "START", operations_count=op.quantity)
        if not plc_ok:
            print("[MES] PLC dispatch failed; order progress was not updated.")
            return

        self._record_machine_tool_stats(machine, op.tool, op.quantity, op.piece_type)

        unload_snapshot = await read_unloading_snapshot()
        if unload_snapshot:
            self._record_unloading_stats(unload_snapshot)

        # This marks produced finals optimistically; replace with PLC feedback counters next.
        self.update_item_completion(first_item["id"], produced_count=1)
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
