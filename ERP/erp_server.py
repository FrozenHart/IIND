import socket
import json
import psycopg2

DB_HOST = "localhost"
DB_PORT = "5000"
DB_NAME = "erp_db"
DB_USER = "iind_user"
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
        print(f"[ERP] Saved order {order_id} with {len(payload['orders'])} line(s) to database.")

    except Exception as e:
        print(f"[ERP] Database error while saving order: {e}")


def parse_client_payload(raw_data):
    """Parses one or many client-order payloads from raw JSON text."""
    parsed = json.loads(raw_data)
    if isinstance(parsed, list):
        return parsed
    return [parsed]

def start_order_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 6666))
    server.listen(5)
    print("[ERP] Listening for client orders on TCP port 6666.")

    while True:
        client_socket, address = server.accept()
        raw_data = client_socket.recv(4096).decode('utf-8')
        if raw_data:
            try:
                payloads = parse_client_payload(raw_data)
                print(f"[ERP] Received {len(payloads)} payload(s) from {address}.")
                for payload in payloads:
                    print(f"[ERP] Processing OrderID {payload.get('OrderID')}")
                    process_and_save_order(payload)
            except json.JSONDecodeError:
                print("[ERP] Invalid JSON received on port 6666.")
            except Exception as exc:
                print(f"[ERP] Error processing order payload: {exc}")
        client_socket.close()

if __name__ == "__main__":
    print("[ERP] ERP server is running.")
    print("[ERP] ERP↔MES communication mode: database-only.")
    start_order_server()
