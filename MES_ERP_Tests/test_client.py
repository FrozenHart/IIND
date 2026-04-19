import socket
import json

# Updated test order requesting final products that exist in our BOM
test_order = {
    "Client_Name": "FEUP Furniture Co.",
    "Client_NIF": "987654321",
    "OrderID": "ORD-101", 
    "Delivery_Date": 600,
    "Penalty_Per_Sec": 1.50,
    "Max_Penalty": 250.00,
    "Items": [
        {"Piece_Type": "RWM", "Quantity": 5},  # Needs: 5 Wood, 10 Metal
        {"Piece_Type": "SMM", "Quantity": 4}   # Needs: 0 Wood, 12 Metal
    ]
}

def send_test_order():
    try:
        # Create a socket and connect to the ERP server
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', 6666))
        
        # Convert the dictionary to a JSON string and send it
        payload = json.dumps(test_order)
        client.send(payload.encode('utf-8'))
        
        print("📤 Final Product test order (ORD-101) sent successfully!")
        client.close()
        
    except ConnectionRefusedError:
        print("❌ Connection failed. Is the ERP server running on port 6666?")

if __name__ == "__main__":
    send_test_order()