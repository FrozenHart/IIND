import time
import json
import paho.mqtt.publish as mqtt_publish
import psycopg2

TB_HOST   = "thingsboard.cloud"
TB_PORT   = 1883
MES_TOKEN = "k46vqnDJEI3ZFKRcABhU"
ERP_TOKEN = "dUJyNXoIX3UXQGN4QAtM"

ERP_DSN = "postgresql://femioyedotun@localhost:5433/erp_db"
MES_DSN = "postgresql://femioyedotun@localhost:5433/mes_db"

INTERVAL = 5  # seconds


def fetch_mes_stats(conn):
    payload = {}
    with conn.cursor() as cur:
        # Machine stats
        cur.execute("""
            SELECT machine_id, total_operating_sec, tool_changes, pieces_processed
            FROM machine_stats
        """)
        for machine_id, op_sec, tool_changes, pieces in cur.fetchall():
            key = machine_id.lower().replace(" ", "_")
            payload[f"{key}_operating_sec"]    = op_sec
            payload[f"{key}_occupation_pct"]   = round(op_sec / 28800 * 100, 1)
            payload[f"{key}_tool_changes"]     = tool_changes
            payload[f"{key}_pieces_processed"] = pieces

        # Unloading dock totals
        cur.execute("""
            SELECT dock_id, SUM(quantity_unloaded)
            FROM unloading_stats
            GROUP BY dock_id
        """)
        for dock_id, qty in cur.fetchall():
            payload[f"dock_{dock_id.lower()}_pieces"] = qty or 0

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


def connect_db(dsn, label):
    while True:
        try:
            conn = psycopg2.connect(dsn)
            print(f"[MQTT Publisher] Connected to {label}.")
            return conn
        except Exception as e:
            print(f"[MQTT Publisher] {label} not available ({e}) — retrying in 5s...")
            time.sleep(5)


def main():
    print("[MQTT Publisher] Starting...")
    erp_conn = connect_db(ERP_DSN, "erp_db")
    mes_conn = connect_db(MES_DSN, "mes_db")

    while True:
        try:
            mes_payload = fetch_mes_stats(mes_conn)
            erp_payload = fetch_erp_stats(erp_conn)

            publish(MES_TOKEN, mes_payload)
            publish(ERP_TOKEN, erp_payload)

            print(f"[MQTT Publisher] MES → {mes_payload}")
            print(f"[MQTT Publisher] ERP → {erp_payload}")

        except psycopg2.OperationalError as e:
            print(f"[MQTT Publisher] DB connection lost ({e}) — reconnecting...")
            erp_conn = connect_db(ERP_DSN, "erp_db")
            mes_conn = connect_db(MES_DSN, "mes_db")
        except Exception as e:
            print(f"[MQTT Publisher] Error: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
