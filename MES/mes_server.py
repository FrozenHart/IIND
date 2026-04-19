import socket
import json
import psycopg2
import asyncio

# Import your custom factory modules
import mes_scheduler
from plc_client import send_to_plc

# MES Database connection details
DB_HOST = "localhost"
DB_PORT = "5433" 
DB_NAME = "mes_db" 
DB_USER = "postgres"
DB_PASS = "IIND20266"

def save_to_mes_database(production_plan):
    """Saves the incoming ERP orders to the MES persistent database."""
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()

        for order in production_plan:
            cur.execute("""
                INSERT INTO Production_Orders (OrderID, Piece_Type, Quantity_Ordered)
                VALUES (%s, %s, %s);
            """, (order['OrderID'], order['Piece'], order['Qty']))

        conn.commit()
        print("💾 Production plan safely saved to MES Database!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ MES Database error: {e}")

def start_mes_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 7777))
    server.listen(5)
    
    print("🏭 Autonomous MES System is ONLINE...")
    print("🎧 Listening for ERP Production Orders on TCP Port 7777\n")

    while True:
        client_socket, address = server.accept()
        raw_data = client_socket.recv(4096).decode('utf-8')
        
        if raw_data:
            try:
                production_plan = json.loads(raw_data)
                
                print(f"📥 RECEIVED DAILY PRODUCTION PLAN FROM ERP:")
                
                # 1. Persistence: Save to database
                save_to_mes_database(production_plan)
                
                # 2. Optimization: Run the scheduling algorithm
                schedule = mes_scheduler.generate_optimized_schedule(production_plan)
                
                # 3. Execution: Dispatch commands to the PLC via OPC-UA
                print("\n⚡ DISPATCHING TO FACTORY FLOOR:")
                for tool, count in schedule.items():
                    # Find which machine the scheduler assigned
                    assigned_machine = next((m for m, tools in mes_scheduler.MACHINE_TOOLS.items() if tool in tools), "Unknown")
                    
                    # Fire the command to Codesys (using asyncio to handle the async OPC-UA client)
                    print(f"   -> Instructing PLC: {assigned_machine} to load {tool} for {count} operations.")
                    asyncio.run(send_to_plc(assigned_machine, tool, "START"))
                
            except json.JSONDecodeError:
                print("⚠️ Received invalid JSON from ERP.")
            except Exception as e:
                print(f"⚠️ Pipeline execution error: {e}")
                
        client_socket.close()

if __name__ == "__main__":
    start_mes_server()