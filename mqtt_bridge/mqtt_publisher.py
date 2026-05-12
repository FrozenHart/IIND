import time
import json
import paho.mqtt.client as mqtt
import psycopg2

TB_HOST   = "thingsboard.cloud"
TB_PORT   = 1883
MES_TOKEN = "k46vqnDJEI3ZFKRcABhU"
ERP_TOKEN = "dUJyNXoIX3UXQGN4QAtM"
DB_DSN    = "postgresql://iind_user:IIND20266@localhost:5000/erp_db"
INTERVAL  = 5  # seconds


def fetch_mes_stats(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT machine_id,
                   total_operating_sec,
                   tool_changes,
                   pieces_processed
            FROM machine_stats
        """)
        rows = cur.fetchall()
    payload = {}
    for machine_id, op_sec, tool_changes, pieces in rows:
        key = machine_id.lower().replace(" ", "_")
        payload[f"{key}_operating_sec"]    = op_sec
        payload[f"{key}_occupation_pct"]   = round(op_sec / 28800 * 100, 1)
        payload[f"{key}_tool_changes"]     = tool_changes
        payload[f"{key}_pieces_processed"] = pieces
    return payload


def fetch_erp_stats(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT current_day FROM simulation_state LIMIT 1")
        day = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'Done'")
        done = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'In Progress'")
        in_prog = cur.fetchone()[0]
    return {
        "simulation_day":     day,
        "orders_total":       total,
        "orders_done":        done,
        "orders_in_progress": in_prog,
        "orders_pending":     total - done - in_prog,
    }


def publish(token, payload):
    client = mqtt.Client()
    client.username_pw_set(token, "")
    client.connect(TB_HOST, TB_PORT, keepalive=60)
    client.publish("v1/devices/me/telemetry", json.dumps(payload))
    client.disconnect()


def main():
    conn = psycopg2.connect(DB_DSN)
    print("[MQTT Publisher] Connected to database. Publishing every 5s...")
    while True:
        try:
            publish(MES_TOKEN, fetch_mes_stats(conn))
            publish(ERP_TOKEN, fetch_erp_stats(conn))
            print("[MQTT Publisher] Published MES + ERP stats.")
        except Exception as e:
            print(f"[MQTT Publisher] Error: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
