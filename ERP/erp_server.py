import socket
import json
import psycopg2
import threading

DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "erp_db"
DB_USER = "postgres"
DB_PASS = "IIND20266"

def _get_db():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS)

# ---------------------------------------------------------------------------
# Client order handler (port 6666)
# ---------------------------------------------------------------------------

def process_and_save_order(payload):
    """
    Parses spec-compliant JSON and persists to erp_db.

    Expected format:
    {
        "name": "Client Name",
        "NIF": 123456789,
        "OrderID": 101,
        "orders": [
            { "type": "RWM", "quantity": 5, "DDate": 10, "Penalty": 2.0 },
            ...
        ]
    }
    """
    try:
        conn = _get_db()
        cur = conn.cursor()

        nif      = str(payload['NIF'])
        order_id = str(payload['OrderID'])

        cur.execute("""
            INSERT INTO Clients (NIF, Name)
            VALUES (%s, %s)
            ON CONFLICT (NIF) DO NOTHING;
        """, (nif, payload['name']))

        for order in payload['orders']:
            line_id = f"{order_id}-{order['type']}"

            cur.execute("""
                INSERT INTO Orders (OrderID, Client_NIF, DDate, Penalty_Per_Day)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (OrderID) DO NOTHING;
            """, (line_id, nif, order['DDate'], order['Penalty']))

            cur.execute("""
                INSERT INTO Order_Items (OrderID, Piece_Type, Quantity_Ordered)
                VALUES (%s, %s, %s);
            """, (line_id, order['type'], order['quantity']))

        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Saved Order {order_id} ({len(payload['orders'])} lines) to database!")

    except Exception as e:
        print(f"❌ Database error: {e}")

def start_order_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 6666))
    server.listen(5)
    print("🎧 Listening for client orders on TCP Port 6666")

    while True:
        client_socket, address = server.accept()
        raw_data = client_socket.recv(4096).decode('utf-8')
        if raw_data:
            try:
                payload = json.loads(raw_data)
                print(f"📥 Received order from {address}: OrderID {payload['OrderID']}")
                process_and_save_order(payload)
            except json.JSONDecodeError:
                print("⚠️ Invalid JSON received on port 6666.")
        client_socket.close()

# ---------------------------------------------------------------------------
# MES callback handler (port 6668)
# MES must send JSON: { "OrderID": "101-RWM", "Pieces_Produced": 5, "Production_Cost": 125.50 }
# ---------------------------------------------------------------------------

def process_mes_feedback(payload):
    """
    Receives production completion data from MES and stores it.
    Also updates Quantity_Done on Order_Items and marks order Completed if fully produced.
    """
    try:
        conn = _get_db()
        cur = conn.cursor()

        order_id        = payload['OrderID']
        pieces_produced = int(payload['Pieces_Produced'])
        production_cost = float(payload['Production_Cost'])

        # Store raw feedback
        cur.execute("""
            INSERT INTO Production_Feedback (OrderID, Pieces_Produced, Production_Cost)
            VALUES (%s, %s, %s);
        """, (order_id, pieces_produced, production_cost))

        # Update quantity done on the order item
        cur.execute("""
            UPDATE Order_Items
            SET Quantity_Done = Quantity_Done + %s
            WHERE OrderID = %s;
        """, (pieces_produced, order_id))

        # Update total cost on the order
        cur.execute("""
            UPDATE Orders
            SET Total_Cost = Total_Cost + %s
            WHERE OrderID = %s;
        """, (production_cost, order_id))

        # Mark order Completed if all pieces have been produced
        cur.execute("""
            UPDATE Orders SET Status = 'Completed'
            WHERE OrderID = %s
            AND (SELECT Quantity_Done FROM Order_Items WHERE OrderID = %s LIMIT 1)
               >= (SELECT Quantity_Ordered FROM Order_Items WHERE OrderID = %s LIMIT 1);
        """, (order_id, order_id, order_id))

        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ MES feedback recorded for {order_id}: {pieces_produced} pieces, €{production_cost}")

    except Exception as e:
        print(f"❌ MES feedback error: {e}")

def start_mes_callback_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 6668))
    server.listen(5)
    print("🎧 Listening for MES production feedback on TCP Port 6668")

    while True:
        client_socket, address = server.accept()
        raw_data = client_socket.recv(4096).decode('utf-8')
        if raw_data:
            try:
                payload = json.loads(raw_data)
                print(f"📥 MES feedback received from {address}: {payload.get('OrderID')}")
                process_mes_feedback(payload)
            except json.JSONDecodeError:
                print("⚠️ Invalid JSON received on port 6668.")
        client_socket.close()

# ---------------------------------------------------------------------------
# Entry point — runs both listeners on separate threads
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("🚀 ERP System is running...")

    mes_thread = threading.Thread(target=start_mes_callback_server, daemon=True)
    mes_thread.start()

    start_order_server()
