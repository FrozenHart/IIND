import psycopg2
import math

# Database connection details
DB_HOST = "localhost"
DB_PORT = "5433" 
DB_NAME = "erp_db"
DB_USER = "postgres"
DB_PASS = "IIND20266"

# Bill of Materials (BOM) - How many raw pieces make a final product
# Example: RWM = 1 Wood (for the top) + 2 Metal (for the legs)
BOM = {
    "RWW": {"Wood": 3, "Metal": 0},
    "SWW": {"Wood": 3, "Metal": 0},
    "RWM": {"Wood": 1, "Metal": 2},
    "SWM": {"Wood": 1, "Metal": 2},
    "RMM": {"Wood": 0, "Metal": 3},
    "SMM": {"Wood": 0, "Metal": 3}
}

def calculate_purchasing_plan():
    print("🧠 Starting MRP Engine...")
    
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()

        # Get all pending items that haven't been produced yet
        cur.execute("""
            SELECT Piece_Type, (Quantity_Ordered - Quantity_Done) as Qty_Needed 
            FROM Order_Items 
            JOIN Orders ON Order_Items.OrderID = Orders.OrderID 
            WHERE Orders.Status = 'Pending' AND (Quantity_Ordered - Quantity_Done) > 0;
        """)
        
        pending_items = cur.fetchall()
        
        if not pending_items:
            print("✅ No pending orders require raw materials.")
            return

        total_wood_needed = 0
        total_metal_needed = 0

        # 1. Break down the orders into Raw Materials
        for piece_type, qty in pending_items:
            if piece_type in BOM:
                total_wood_needed += BOM[piece_type]["Wood"] * qty
                total_metal_needed += BOM[piece_type]["Metal"] * qty

        print(f"📊 Raw Materials Required for pending orders: {total_wood_needed} Wood, {total_metal_needed} Metal")

        # 2. Supplier Logic for WOOD
        print("\n🛒 PURCHASING PLAN (WOOD):")
        if total_wood_needed > 0:
            # Check if we should use Supplier B (Cheaper, but requires min 12)
            if total_wood_needed >= 12:
                cost = total_wood_needed * 2
                print(f"   -> Order {total_wood_needed} Wood from Supplier B. Cost: €{cost} (Arrives in 2 days)")
            else:
                # If we need less than 12, we evaluate if ordering the minimum from B is still cheaper than A
                cost_B_minimum = 12 * 2 # €24
                cost_A_exact = max(total_wood_needed, 2) * 10 # 10€ each, min 2
                
                if cost_B_minimum < cost_A_exact:
                    print(f"   -> Order minimum 12 Wood from Supplier B (Cheaper than A). Cost: €24 (Arrives in 2 days)")
                else:
                    qty_to_order = max(total_wood_needed, 2)
                    print(f"   -> Order {qty_to_order} Wood from Supplier A. Cost: €{qty_to_order * 10} (Arrives instantly)")

        # 3. Supplier Logic for METAL
        print("\n🛒 PURCHASING PLAN (METAL):")
        if total_metal_needed > 0:
            if total_metal_needed >= 8:
                cost = total_metal_needed * 4
                print(f"   -> Order {total_metal_needed} Metal from Supplier B. Cost: €{cost} (Arrives in 4 days)")
            else:
                cost_B_minimum = 8 * 4 # €32
                cost_A_exact = max(total_metal_needed, 4) * 15 # 15€ each, min 4
                
                if cost_B_minimum < cost_A_exact:
                    print(f"   -> Order minimum 8 Metal from Supplier B (Cheaper than A). Cost: €32 (Arrives in 4 days)")
                else:
                    qty_to_order = max(total_metal_needed, 4)
                    print(f"   -> Order {qty_to_order} Metal from Supplier A. Cost: €{qty_to_order * 15} (Arrives instantly)")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    calculate_purchasing_plan()