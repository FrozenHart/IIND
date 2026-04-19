import socket
import json
import psycopg2

# Database connection details
DB_HOST = "localhost"
DB_PORT = "5433"         # <-- ADD THIS LINE
DB_NAME = "erp_db"
DB_USER = "postgres"
DB_PASS = "IIND20266"  # <-- CHANGE THIS

def process_and_save_order(order_data):
    """Parses the JSON dictionary and inserts it into PostgreSQL"""
    try:
        # Connect to the database
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT,database=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()

        # 1. Insert the Client 
        # ON CONFLICT DO NOTHING ensures we don't crash if the client already exists from a previous order
        cur.execute("""
            INSERT INTO Clients (NIF, Name)
            VALUES (%s, %s)
            ON CONFLICT (NIF) DO NOTHING;
        """, (order_data['Client_NIF'], order_data['Client_Name']))

        # 2. Insert the main Order details
        cur.execute("""
            INSERT INTO Orders (OrderID, Client_NIF, Delivery_Date, Penalty_Per_Sec, Max_Penalty)
            VALUES (%s, %s, %s, %s, %s);
        """, (
            order_data['OrderID'], order_data['Client_NIF'], 
            order_data['Delivery_Date'], order_data['Penalty_Per_Sec'], 
            order_data['Max_Penalty']
        ))

        # 3. Loop through and insert all requested Pieces (Order Items)
        for item in order_data['Items']:
            cur.execute("""
                INSERT INTO Order_Items (OrderID, Piece_Type, Quantity_Ordered)
                VALUES (%s, %s, %s);
            """, (order_data['OrderID'], item['Piece_Type'], item['Quantity']))

        # Save changes and close
        conn.commit()
        print(f"✅ Successfully saved Order {order_data['OrderID']} to database!")
        
        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Database error: {e}")

def start_erp_server():
    """Starts the TCP socket listener on Port 6666"""
    # Create the TCP socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Bind to all available interfaces (0.0.0.0) on port 6666
    server.bind(('0.0.0.0', 6666))
    server.listen(5)
    
    print("🚀 ERP System is running...")
    print("🎧 Listening for incoming JSON orders on TCP Port 6666\n")

    while True:
        # Wait for a client (the external order sender) to connect
        client_socket, address = server.accept()
        
        # Receive the data (up to 4096 bytes) and decode the text
        raw_data = client_socket.recv(4096).decode('utf-8')
        
        if raw_data:
            try:
                # Convert the incoming JSON string into a Python dictionary
                json_payload = json.loads(raw_data)
                print(f"📥 Received new order from {address}: {json_payload['OrderID']}")
                
                # Send it to the database function
                process_and_save_order(json_payload)
                
            except json.JSONDecodeError:
                print("⚠️ Received invalid JSON format.")
        
        client_socket.close()

if __name__ == "__main__":
    start_erp_server()