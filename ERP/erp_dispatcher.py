import psycopg2
import time
import erp_mps

DB_HOST = "localhost"
DB_PORT = "5000"
DB_NAME = "erp_db"
DB_USER = "iind_user"
DB_PASS = "IIND20266"
DISPATCH_POLL_SECONDS = 2

def dispatch_day(current_day):
    try:
        mps = erp_mps.generate_mps()

        if not mps:
            return 0

        # Queue all pending order lines into MES as soon as possible.
        # MES will execute only when production_day is reached.
        queued_orders = []
        for prod_day, orders in mps.items():
            for order in orders:
                queued_line = dict(order)
                queued_line["Production_Day"] = int(prod_day)
                queued_orders.append(queued_line)

        if not queued_orders:
            return 0

        # Send to MES by inserting production orders in shared DB tables.
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()
        inserted_lines = 0
        for line in queued_orders:
            cur.execute(
                """
                SELECT 1
                FROM Production_Orders
                WHERE OrderID = %s
                  AND Piece_Type = %s
                LIMIT 1;
                """,
                (line["OrderID"], line["Piece"]),
            )
            if cur.fetchone() is not None:
                continue

            cur.execute(
                """
                INSERT INTO Production_Orders (OrderID, Piece_Type, Quantity_Ordered, Production_Day)
                VALUES (%s, %s, %s, %s);
                """,
                (line["OrderID"], line["Piece"], line["Qty"], line["Production_Day"]),
            )
            inserted_lines += 1

        # Mark only due-now ERP orders as scheduled.
        due_now_ids = list(
            {
                o["OrderID"]
                for o in queued_orders
                if int(o["Production_Day"]) <= int(current_day)
            }
        )
        if due_now_ids:
            cur.execute(
                "UPDATE Orders SET Status = 'Scheduled' WHERE OrderID = ANY(%s);",
                (due_now_ids,)
            )
        conn.commit()
        cur.close()
        conn.close()

        if inserted_lines > 0:
            due_now = sum(1 for line in queued_orders if line["Production_Day"] <= current_day)
            print(
                f"  [ERP] Dispatch complete: {inserted_lines} MES line(s) queued "
                f"(due now: {due_now}), {len(due_now_ids)} ERP order(s) marked as 'Scheduled'."
            )

        return inserted_lines

    except Exception as e:
        print(f"  [ERP] Dispatch error: {e}")
        return 0


def run():
    print(
        "🏭 ERP Dispatcher started — 1 simulation day = "
        f"{erp_mps.SECONDS_PER_DAY}s, dispatch poll = {DISPATCH_POLL_SECONDS}s\n"
    )

    current_day = erp_mps.advance_day()
    day_started_at = time.monotonic()
    

    while True:
        dispatch_day(current_day)
        time.sleep(DISPATCH_POLL_SECONDS)

        if time.monotonic() - day_started_at >= erp_mps.SECONDS_PER_DAY:
            current_day = erp_mps.advance_day()
            day_started_at = time.monotonic()
            

if __name__ == "__main__":
    run()
