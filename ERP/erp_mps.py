import psycopg2

DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "erp_db"
DB_USER = "postgres"
DB_PASS = "IIND20266"

SECONDS_PER_DAY = 60

BOM = {
    "RWW": {"Wood": 3, "Metal": 0},
    "SWW": {"Wood": 3, "Metal": 0},
    "RWM": {"Wood": 1, "Metal": 2},
    "SWM": {"Wood": 1, "Metal": 2},
    "RMM": {"Wood": 0, "Metal": 3},
    "SMM": {"Wood": 0, "Metal": 3}
}

# Supplier table: {material: {supplier: {min_qty, price_per, lead_days}}}
SUPPLIERS = {
    "Wood":  {
        "A": {"min_qty": 2,  "price": 10, "lead_days": 0},
        "B": {"min_qty": 12, "price": 2,  "lead_days": 2},
    },
    "Metal": {
        "A": {"min_qty": 4,  "price": 15, "lead_days": 0},
        "B": {"min_qty": 8,  "price": 4,  "lead_days": 4},
    }
}

def _get_db():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS)

def get_current_day():
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("SELECT current_day FROM Simulation_State WHERE id = 1;")
    day = cur.fetchone()[0]
    cur.close()
    conn.close()
    return day

def advance_day():
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("UPDATE Simulation_State SET current_day = current_day + 1 WHERE id = 1;")
    conn.commit()
    cur.execute("SELECT current_day FROM Simulation_State WHERE id = 1;")
    day = cur.fetchone()[0]
    cur.close()
    conn.close()
    return day

def generate_mps():
    """
    Builds the Master Production Schedule from all pending orders.
    Strategy: schedule each order for production on (DDate - 1), minimum day 1.
    Returns: dict of {production_day: [list of order dicts]}
    """
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.OrderID, o.DDate, o.Penalty_Per_Day, oi.Piece_Type, oi.Quantity_Ordered
        FROM Orders o
        JOIN Order_Items oi ON o.OrderID = oi.OrderID
        WHERE o.Status = 'Pending';
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    mps = {}
    for order_id, ddate, penalty, piece_type, qty in rows:
        production_day = max(1, ddate - 1)
        mps.setdefault(production_day, []).append({
            "OrderID":        order_id,
            "Piece":          piece_type,
            "Qty":            qty,
            "DDate":          ddate,
            "Penalty_Per_Day": float(penalty)
        })
    return mps

def _materials_for_orders(orders):
    wood  = sum(BOM.get(o["Piece"], {}).get("Wood",  0) * o["Qty"] for o in orders)
    metal = sum(BOM.get(o["Piece"], {}).get("Metal", 0) * o["Qty"] for o in orders)
    return wood, metal

def _best_purchase(material, qty_needed, days_available):
    """Returns (supplier_label, qty_to_order, cost, lead_days) for the cheapest valid option."""
    s = SUPPLIERS[material]
    can_use_b = (days_available >= s["B"]["lead_days"]) and (qty_needed >= s["B"]["min_qty"] or
                 s["B"]["min_qty"] * s["B"]["price"] < max(qty_needed, s["A"]["min_qty"]) * s["A"]["price"])

    if can_use_b:
        qty  = max(qty_needed, s["B"]["min_qty"])
        return ("B", qty, qty * s["B"]["price"], s["B"]["lead_days"])
    else:
        qty  = max(qty_needed, s["A"]["min_qty"])
        return ("A", qty, qty * s["A"]["price"], s["A"]["lead_days"])

def generate_purchasing_plan(current_day, mps):
    """
    Returns a list of purchase recommendation strings for the given day.
    Covers:
      - Materials needed for today's production (Supplier A, instant).
      - Pre-orders for future production days where Supplier B is cheaper
        and lead time means we must order today.
    """
    recommendations = []

    for prod_day in sorted(mps.keys()):
        orders = mps[prod_day]
        wood, metal = _materials_for_orders(orders)
        days_until = prod_day - current_day

        for material, qty_needed in [("Wood", wood), ("Metal", metal)]:
            if qty_needed == 0:
                continue

            lead_b = SUPPLIERS[material]["B"]["lead_days"]

            # Today is the day we must order from B to arrive in time
            order_b_on_day = prod_day - lead_b

            if order_b_on_day == current_day:
                sup, qty, cost, lead = _best_purchase(material, qty_needed, days_until)
                recommendations.append(
                    f"  📦 {material}: Order {qty} from Supplier {sup} → "
                    f"€{cost} (arrives in {lead} days, for Day {prod_day} production)"
                )
            elif prod_day == current_day:
                # Production is today — must order from A (no time for B)
                sup_a = SUPPLIERS[material]["A"]
                qty = max(qty_needed, sup_a["min_qty"])
                cost = qty * sup_a["price"]
                recommendations.append(
                    f"  📦 {material}: Order {qty} from Supplier A → "
                    f"€{cost} (arrives instantly, for Day {prod_day} production)"
                )
            elif order_b_on_day > current_day:
                # Nothing to order yet — just inform when to order
                recommendations.append(
                    f"  🗓️  {material}: Pre-order from Supplier B on Day {order_b_on_day} "
                    f"({qty_needed} units for Day {prod_day} production)"
                )

    return recommendations

def print_full_mps():
    current_day = get_current_day()
    mps = generate_mps()

    print(f"\n{'='*60}")
    print(f"  📅 MASTER PRODUCTION SCHEDULE  —  Day {current_day}  ({current_day * SECONDS_PER_DAY}s elapsed)")
    print(f"{'='*60}")

    if not mps:
        print("  No pending orders.\n")
        return

    print(f"  {'Prod.Day':<10} {'OrderID':<14} {'Piece':<8} {'Qty':<6} {'Due Day':<10} {'Penalty/Day'}")
    print(f"  {'-'*58}")
    for day in sorted(mps.keys()):
        for o in mps[day]:
            flag = " ⚠️ OVERDUE" if day < current_day else ""
            print(f"  {day:<10} {o['OrderID']:<14} {o['Piece']:<8} {o['Qty']:<6} Day {o['DDate']:<6} €{o['Penalty_Per_Day']}/day{flag}")

    print(f"\n  🛒 PURCHASING RECOMMENDATIONS FOR DAY {current_day}:")
    recs = generate_purchasing_plan(current_day, mps)
    if recs:
        for r in recs:
            print(r)
    else:
        print("  No purchasing actions required today.")
    print()


if __name__ == "__main__":
    print_full_mps()
