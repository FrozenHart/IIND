import time
import json
import paho.mqtt.publish as mqtt_publish
import psycopg2

TB_HOST   = "thingsboard.cloud"
TB_PORT   = 1883
MES_TOKEN = "cjoFwM5Jq2VpHFaChwaq"
ERP_TOKEN = "5CN037YqnYc9lHUpdg4J"

DSN = "postgresql://iind_user:IIND20266@localhost:5000/erp_db"

INTERVAL = 5  # seconds


def fetch_mes_stats(conn):
    payload = {}
    with conn.cursor() as cur:
        # ── Machine stats with totals ─────────────────────────────────────────
        cur.execute("""
            SELECT machine_id, total_operating_sec, tool_changes, pieces_processed
            FROM machine_stats
        """)
        total_pieces = 0
        total_tool_changes = 0
        for machine_id, op_sec, tool_changes, pieces in cur.fetchall():
            key = machine_id.lower().replace(" ", "_")
            payload[f"{key}_operating_sec"]    = op_sec
            payload[f"{key}_occupation_pct"]   = round(op_sec / 28800 * 100, 1)
            payload[f"{key}_tool_changes"]     = tool_changes
            payload[f"{key}_pieces_processed"] = pieces
            total_pieces += pieces or 0
            total_tool_changes += tool_changes or 0
        payload["total_pieces_produced"] = total_pieces
        payload["total_tool_changes"]    = total_tool_changes

        # ── Unloading dock totals ─────────────────────────────────────────────
        cur.execute("""
            SELECT dock_id, SUM(quantity_unloaded)
            FROM unloading_stats
            GROUP BY dock_id
        """)
        for dock_id, qty in cur.fetchall():
            payload[f"dock_{str(dock_id).lower()}_pieces"] = qty or 0

        # ── Production orders status ──────────────────────────────────────────
        try:
            cur.execute("SELECT status, COUNT(*) FROM production_orders GROUP BY status")
            active_orders = 0
            for status, count in cur.fetchall():
                key = f"production_{status.lower().replace(' ', '_')}"
                payload[key] = count
                if status.lower() in ('pending', 'in_progress', 'in progress'):
                    active_orders += count
            payload["active_orders"] = active_orders
        except Exception:
            payload["active_orders"] = 0

        # ── Tool stats (per machine + tool) ───────────────────────────────────
        try:
            cur.execute("SELECT machine_id, tool_id, operating_sec FROM tool_stats")
            for machine_id, tool_id, op_sec in cur.fetchall():
                key = f"tool_{machine_id.lower().replace(' ', '_')}_{tool_id.lower()}_sec"
                payload[key] = op_sec
        except Exception:
            pass

        # ── Pieces by type (aggregated across all machines) ──────────────────
        try:
            cur.execute("""
                SELECT piece_type, SUM(pieces_processed)
                FROM machine_piece_stats
                GROUP BY piece_type
            """)
            for piece_type, total in cur.fetchall():
                if piece_type and total:
                    payload[f"pieces_{piece_type.lower()}"] = total
        except Exception:
            pass

        # ── Loading stats (per conveyor) ──────────────────────────────────────
        try:
            cur.execute("""
                SELECT conveyor_id, SUM(quantity_loaded)
                FROM loading_stats
                GROUP BY conveyor_id
            """)
            for conveyor_id, total in cur.fetchall():
                if conveyor_id is not None and total is not None:
                    payload[f"loaded_{str(conveyor_id).lower()}"] = total
        except Exception:
            pass

        # ── Total production cost ─────────────────────────────────────────────
        try:
            cur.execute("SELECT COALESCE(SUM(production_cost), 0) FROM production_feedback")
            row = cur.fetchone()
            payload["total_production_cost"] = float(row[0]) if row and row[0] is not None else 0.0
        except Exception:
            payload["total_production_cost"] = 0.0

        # ── Overdue orders (estimated completion > due date) ──────────────────
        try:
            cur.execute("""
                SELECT COUNT(*)
                FROM orders
                WHERE estimated_completion_day IS NOT NULL
                  AND estimated_completion_day > ddate
            """)
            payload["overdue_orders"] = cur.fetchone()[0]
        except Exception:
            payload["overdue_orders"] = 0

    return payload


def fetch_erp_stats(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT current_day FROM simulation_state LIMIT 1")
        row = cur.fetchone()
        day = row[0] if row else 0

        cur.execute("SELECT COUNT(*) FROM orders")
        total = cur.fetchone()[0]

        cur.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
        status_counts = {row[0]: row[1] for row in cur.fetchall()}

    return {
        "simulation_day":     day,
        "orders_total":       total,
        "orders_done":        status_counts.get("Done", 0),
        "orders_in_progress": status_counts.get("In Progress", 0),
        "orders_scheduled":   status_counts.get("Scheduled", 0),
        "orders_pending":     status_counts.get("Pending", 0),
    }


def publish(token, payload):
    mqtt_publish.single(
        topic="v1/devices/me/telemetry",
        payload=json.dumps(payload),
        hostname=TB_HOST,
        port=TB_PORT,
        auth={"username": token, "password": ""},
    )


def connect_db():
    while True:
        try:
            conn = psycopg2.connect(DSN)
            print("[MQTT Publisher] Connected to erp_db.")
            return conn
        except Exception as e:
            print(f"[MQTT Publisher] erp_db not available ({e}) — retrying in 5s...")
            time.sleep(5)


def main():
    print("[MQTT Publisher] Starting...")
    conn = connect_db()

    while True:
        try:
            mes_payload = fetch_mes_stats(conn)
            erp_payload = fetch_erp_stats(conn)

            publish(MES_TOKEN, mes_payload)
            publish(ERP_TOKEN, erp_payload)

            print(f"[MQTT Publisher] MES → {mes_payload}")
            print(f"[MQTT Publisher] ERP → {erp_payload}")

        except psycopg2.OperationalError as e:
            print(f"[MQTT Publisher] DB connection lost ({e}) — reconnecting...")
            conn = connect_db()
        except Exception as e:
            print(f"[MQTT Publisher] Error: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
