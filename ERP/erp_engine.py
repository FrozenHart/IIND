import psycopg2

DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "erp_db"
DB_USER = "postgres"
DB_PASS = "IIND20266"

# 1 simulation day = 60 real seconds
SECONDS_PER_DAY = 60

# Bill of Materials: final piece -> raw materials required
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

        # Fetch all pending items with their delivery deadline and penalty
        cur.execute("""
            SELECT oi.Piece_Type,
                   (oi.Quantity_Ordered - oi.Quantity_Done) AS Qty_Needed,
                   o.DDate,
                   o.Penalty_Per_Day
            FROM Order_Items oi
            JOIN Orders o ON oi.OrderID = o.OrderID
            WHERE o.Status = 'Pending' AND (oi.Quantity_Ordered - oi.Quantity_Done) > 0;
        """)

        pending_items = cur.fetchall()

        if not pending_items:
            print("✅ No pending orders require raw materials.")
            return

        total_wood = 0
        total_metal = 0

        print("\n📋 PENDING ORDERS:")
        for piece_type, qty, ddate, penalty in pending_items:
            deadline_secs = ddate * SECONDS_PER_DAY
            print(f"   {qty}x {piece_type} — due in {ddate} days ({deadline_secs}s) — penalty €{penalty}/day")
            if piece_type in BOM:
                total_wood  += BOM[piece_type]["Wood"]  * qty
                total_metal += BOM[piece_type]["Metal"] * qty

        print(f"\n📊 Raw Materials Required: {total_wood} Wood, {total_metal} Metal")

        # Supplier logic for WOOD
        # SupplierA: min 2, €10/piece, 0 days | SupplierB: min 12, €2/piece, 2 days
        print("\n🛒 PURCHASING PLAN (WOOD):")
        if total_wood > 0:
            if total_wood >= 12:
                print(f"   -> Order {total_wood} Wood from Supplier B. Cost: €{total_wood * 2} (arrives in 2 days)")
            else:
                cost_b = 12 * 2   # €24, minimum order
                cost_a = max(total_wood, 2) * 10
                if cost_b < cost_a:
                    print(f"   -> Order 12 Wood from Supplier B (cheaper than A). Cost: €24 (arrives in 2 days)")
                else:
                    qty_a = max(total_wood, 2)
                    print(f"   -> Order {qty_a} Wood from Supplier A. Cost: €{qty_a * 10} (arrives instantly)")
        else:
            print("   -> No wood required.")

        # Supplier logic for METAL
        # SupplierA: min 4, €15/piece, 0 days | SupplierB: min 8, €4/piece, 4 days
        print("\n🛒 PURCHASING PLAN (METAL):")
        if total_metal > 0:
            if total_metal >= 8:
                print(f"   -> Order {total_metal} Metal from Supplier B. Cost: €{total_metal * 4} (arrives in 4 days)")
            else:
                cost_b = 8 * 4    # €32, minimum order
                cost_a = max(total_metal, 4) * 15
                if cost_b < cost_a:
                    print(f"   -> Order 8 Metal from Supplier B (cheaper than A). Cost: €32 (arrives in 4 days)")
                else:
                    qty_a = max(total_metal, 4)
                    print(f"   -> Order {qty_a} Metal from Supplier A. Cost: €{qty_a * 15} (arrives instantly)")
        else:
            print("   -> No metal required.")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    calculate_purchasing_plan()
