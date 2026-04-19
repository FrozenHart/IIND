import math

# Machine capabilities based on the project documentation
MACHINE_TOOLS = {
    "M1a": ["T1", "T2", "T3"], "M1b": ["T1", "T2", "T3"], "M1c": ["T8", "T9", "T11"],
    "M2a": ["T1", "T2", "T3"], "M2b": ["T1", "T2", "T3"], "M2c": ["T8", "T9", "T10"],
    "M3a": ["T4", "T5", "T6"], "M3b": ["T4", "T5", "T6"], "M3c": ["T8", "T9", "T11"],
    "M4a": ["T4", "T5", "T6"], "M4b": ["T4", "T5", "T6"], "M4c": ["T8", "T9", "T10"]
}

# Bill of Operations: Final Piece -> (Raw Material, Intermediate Tool, Final Assembly Tool)
# Note: We simplify here to show the optimization logic.
OPERATIONS = {
    "RWM": [{"material": "Wood", "tool": "T1", "qty": 1}, {"material": "Metal", "tool": "T5", "qty": 2}],
    "SMM": [{"material": "Metal", "tool": "T6", "qty": 1}, {"material": "Metal", "tool": "T5", "qty": 2}]
}

def generate_optimized_schedule(daily_orders):
    """
    Takes the JSON array from the ERP and creates an optimized machine schedule.
    """
    print("\n⚙️ Running MES Optimization Algorithm...")
    
    total_final_pieces = 0
    tool_queue = {}

    # 1. Deconstruct orders into required tool operations
    for order in daily_orders:
        piece = order['Piece']
        qty = order['Qty']
        total_final_pieces += qty
        
        if piece in OPERATIONS:
            for op in OPERATIONS[piece]:
                tool = op["tool"]
                total_ops = op["qty"] * qty
                
                if tool not in tool_queue:
                    tool_queue[tool] = 0
                tool_queue[tool] += total_ops

    # 2. Assign unloading docks (Max 6 per dock)
    docks_needed = math.ceil(total_final_pieces / 6)
    print(f"📦 Unloading Logistics: {total_final_pieces} pieces require {docks_needed} docks.")

    # 3. Optimize & Assign to Machines (Grouping by tool minimizes 30s changeovers)
    print("\n📋 OPTIMIZED MACHINE SCHEDULE:")
    for tool, count in tool_queue.items():
        # Find the first available machine that holds this tool
        assigned_machine = next((m for m, tools in MACHINE_TOOLS.items() if tool in tools), "Unknown")
        
        print(f"   -> Assigning {count}x operations with {tool} to {assigned_machine}.")
        print(f"      (Benefit: Doing all {tool} operations at once saves {(count-1)*30}s in tool-change penalties)")
        
    return tool_queue

# --- Test the logic locally ---
if __name__ == "__main__":
    test_data_from_erp = [
        {"OrderID": "ORD-101", "Piece": "RWM", "Qty": 5},
        {"OrderID": "ORD-101", "Piece": "SMM", "Qty": 4}
    ]
    generate_optimized_schedule(test_data_from_erp)