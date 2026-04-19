import psycopg2
import socket
import json
import time
import erp_mps

DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "erp_db"
DB_USER = "postgres"
DB_PASS = "IIND20266"

def dispatch_day(current_day):
    try:
        mps = erp_mps.generate_mps()

        if not mps:
            print(f"  ✅ No pending orders in the MPS.")
            return

        erp_mps.print_full_mps()

        # Collect all orders due for production today (production_day <= current_day)
        todays_orders = []
        for prod_day, orders in mps.items():
            if prod_day <= current_day:
                todays_orders.extend(orders)

        if not todays_orders:
            print(f"  ℹ️  No production scheduled for Day {current_day}.")
            return

        # Send to MES
        print(f"\n  🚀 Dispatching {len(todays_orders)} order line(s) to MES...")
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', 7777))
        client.send(json.dumps(todays_orders).encode('utf-8'))
        client.close()

        # Mark as Scheduled in DB
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()
        dispatched_ids = list({o["OrderID"] for o in todays_orders})
        cur.execute(
            "UPDATE Orders SET Status = 'Scheduled' WHERE OrderID = ANY(%s);",
            (dispatched_ids,)
        )
        conn.commit()
        cur.close()
        conn.close()

        print(f"  ✅ Dispatch complete. {len(dispatched_ids)} order(s) marked as 'Scheduled'.")

    except ConnectionRefusedError:
        print("  ❌ Could not reach MES. Is mes_server.py running on port 7777?")
    except Exception as e:
        print(f"  ❌ Error: {e}")

def run():
    print("🏭 ERP Dispatcher started — ticking every 60 seconds (1 tick = 1 simulation day)\n")

    while True:
        current_day = erp_mps.advance_day()

        print(f"\n{'='*60}")
        print(f"  🕐 Simulation Day {current_day}  (real time: {current_day * erp_mps.SECONDS_PER_DAY}s elapsed)")
        print(f"{'='*60}")

        dispatch_day(current_day)

        print(f"\n  ⏳ Waiting {erp_mps.SECONDS_PER_DAY}s for next simulation day...\n")
        time.sleep(erp_mps.SECONDS_PER_DAY)

if __name__ == "__main__":
    run()
