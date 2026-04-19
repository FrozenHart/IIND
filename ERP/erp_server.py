import socket
import json
import psycopg2

DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "erp_db"
DB_USER = "postgres"
DB_PASS = "IIND20266"

def process_and_save_order(payload):
    """Parses the spec-compliant JSON and inserts it into PostgreSQL.

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
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()

        nif = str(payload['NIF'])
        order_id = str(payload['OrderID'])

        # 1. Insert client (ignore if already exists)
        cur.execute("""
            INSERT INTO Clients (NIF, Name)
            VALUES (%s, %s)
            ON CONFLICT (NIF) DO NOTHING;
        """, (nif, payload['name']))

        # 2. Each entry in 'orders' is a separate order line with its own DDate and Penalty
        for order in payload['orders']:
            line_order_id = f"{order_id}-{order['type']}"

            cur.execute("""
                INSERT INTO Orders (OrderID, Client_NIF, DDate, Penalty_Per_Day)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (OrderID) DO NOTHING;
            """, (line_order_id, nif, order['DDate'], order['Penalty']))

            cur.execute("""
                INSERT INTO Order_Items (OrderID, Piece_Type, Quantity_Ordered)
                VALUES (%s, %s, %s);
            """, (line_order_id, order['type'], order['quantity']))

        conn.commit()
        print(f"✅ Successfully saved Order {order_id} ({len(payload['orders'])} lines) to database!")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Database error: {e}")

def start_erp_server():
    """Starts the TCP socket listener on Port 6666."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 6666))
    server.listen(5)

    print("🚀 ERP System is running...")
    print("🎧 Listening for incoming JSON orders on TCP Port 6666\n")

    while True:
        client_socket, address = server.accept()
        raw_data = client_socket.recv(4096).decode('utf-8')

        if raw_data:
            try:
                json_payload = json.loads(raw_data)
                print(f"📥 Received new order from {address}: OrderID {json_payload['OrderID']}")
                process_and_save_order(json_payload)
            except json.JSONDecodeError:
                print("⚠️ Received invalid JSON format.")

        client_socket.close()

if __name__ == "__main__":
    start_erp_server()
