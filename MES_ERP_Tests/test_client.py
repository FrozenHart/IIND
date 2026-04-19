import socket
import json

# Spec-compliant test order (section 3.1 format)
# DDate = delivery in days from now (1 day = 60 seconds simulation time)
# Penalty = € per day of delay
test_order = {
    "name": "FEUP Furniture Co.",
    "NIF": 987654321,
    "OrderID": 101,
    "orders": [
        {"type": "RWM", "quantity": 5, "DDate": 3, "Penalty": 2.0},
        {"type": "SMM", "quantity": 4, "DDate": 5, "Penalty": 1.5}
    ]
}

def send_test_order():
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', 6666))
        client.send(json.dumps(test_order).encode('utf-8'))
        print("📤 Test order (OrderID 101) sent successfully!")
        client.close()
    except ConnectionRefusedError:
        print("❌ Connection failed. Is the ERP server running on port 6666?")

if __name__ == "__main__":
    send_test_order()
