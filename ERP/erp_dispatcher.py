import psycopg2
import socket
import json

DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "erp_db"
DB_USER = "postgres"
DB_PASS = "IIND20266"

def dispatch_orders_to_mes():
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()

        # 1. Find all Pending items
        cur.execute("""
            SELECT Orders.OrderID, Order_Items.Piece_Type, (Order_Items.Quantity_Ordered - Order_Items.Quantity_Done) as Qty 
            FROM Order_Items 
            JOIN Orders ON Order_Items.OrderID = Orders.OrderID 
            WHERE Orders.Status = 'Pending';
        """)
        
        pending_items = cur.fetchall()
        
        if not pending_items:
            print("✅ No pending orders to dispatch to MES today.")
            return

        # 2. Package them into a JSON-friendly list of dictionaries
        production_payload = []
        for order_id, piece, qty in pending_items:
            production_payload.append({
                "OrderID": order_id,
                "Piece": piece,
                "Qty": qty
            })

        # 3. Send over TCP to the MES on Port 7777
        print("🚀 Sending Production Plan to MES...")
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', 7777))
        client.send(json.dumps(production_payload).encode('utf-8'))
        client.close()
        
        # 4. Update the Database so we don't send them again tomorrow
        cur.execute("UPDATE Orders SET Status = 'Scheduled' WHERE Status = 'Pending';")
        conn.commit()
        
        print("✅ Dispatch complete! Database updated to 'Scheduled'.")

        cur.close()
        conn.close()

    except ConnectionRefusedError:
        print("❌ Could not reach MES. Is mes_server.py running on port 7777?")
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    dispatch_orders_to_mes()