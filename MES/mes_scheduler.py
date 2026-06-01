import math
from mes_recipe_engine import RecipeEngine

# Rough simulation-day length in seconds (no config available — tune as needed)
SECONDS_PER_SIM_DAY = 60
# Overhead per table (ship, transfer, between-step gaps)
OVERHEAD_PER_TABLE = 15


def estimate_completion_day(piece_type, remaining_tables, current_day):
    """Estimate the simulation day when the remaining tables finish.

    Pipeline: 10 parallel table slots.
    Per-table bottleneck = max(leg_tool_time, top_tool_time) + join_time + overhead.
    """
    piece_type = str(piece_type).upper()
    profile = RecipeEngine.FINAL_RECIPES.get(piece_type)
    if profile is None or remaining_tables <= 0:
        return current_day

    leg_time = int(profile["leg_time"])
    top_time = int(profile["top_time"])
    join_time = int(profile["join_time"])

    per_table_sec = max(leg_time, top_time) + join_time + OVERHEAD_PER_TABLE
    total_sec = remaining_tables * per_table_sec / 4
    days_needed = math.ceil(total_sec / SECONDS_PER_SIM_DAY)
    return current_day + days_needed


def estimate_order_completion(items, current_day):
    """Estimate completion day for an order with multiple recipe types.

    `items` — list of (piece_type, remaining_tables).
    Uses the slowest per-table bottleneck across all recipes in the order.
    """
    total_tables = 0
    worst_per_table = 0
    for piece_type, remaining in items:
        total_tables += int(remaining)
        profile = RecipeEngine.FINAL_RECIPES.get(str(piece_type).upper())
        if profile:
            pt = max(int(profile["leg_time"]), int(profile["top_time"])) + int(profile["join_time"]) + OVERHEAD_PER_TABLE
            if pt > worst_per_table:
                worst_per_table = pt
    if total_tables == 0:
        return current_day
    total_sec = total_tables * worst_per_table / 4
    days_needed = math.ceil(total_sec / SECONDS_PER_SIM_DAY)
    return current_day + days_needed


# Machine capabilities based on the project documentation
MACHINE_TOOLS = {
    "M1a": ["T1", "T2", "T3"], "M1b": ["T1", "T2", "T3"], "M1c": ["T8", "T9", "T11"],
    "M2a": ["T1", "T2", "T3"], "M2b": ["T1", "T2", "T3"], "M2c": ["T8", "T9", "T10"],
    "M3a": ["T4", "T5", "T6"], "M3b": ["T4", "T5", "T6"], "M3c": ["T8", "T9", "T11"],
    "M4a": ["T4", "T5", "T6"], "M4b": ["T4", "T5", "T6"], "M4c": ["T8", "T9", "T10"]
}

MACHINE_TO_CONVEYOR = {
    "M1a": "C6",
    "M1b": "C8",
    "M1c": "C10",
    "M2a": "C11",
    "M2b": "C13",
    "M2c": "C15",
    "M3a": "C16",
    "M3b": "C18",
    "M3c": "C20",
    "M4a": "C21",
    "M4b": "C23",
    "M4c": "C25",
}

TOOL_TO_SLOT = {
    "M1a": {"T1": 0, "T2": 1, "T3": 2},
    "M1b": {"T1": 0, "T2": 1, "T3": 2},
    "M1c": {"T8": 0, "T9": 1, "T11": 2},
    "M2a": {"T1": 0, "T2": 1, "T3": 2},
    "M2b": {"T1": 0, "T2": 1, "T3": 2},
    "M2c": {"T8": 0, "T9": 1, "T10": 2},
    "M3a": {"T4": 0, "T5": 1, "T6": 2},
    "M3b": {"T4": 0, "T5": 1, "T6": 2},
    "M3c": {"T8": 0, "T9": 1, "T11": 2},
    "M4a": {"T4": 0, "T5": 1, "T6": 2},
    "M4b": {"T4": 0, "T5": 1, "T6": 2},
    "M4c": {"T8": 0, "T9": 1, "T10": 2},
}

ASSEMBLY_MACHINES = {"M1c", "M2c", "M3c", "M4c"}

OPERATIONS = {
    "RWW": [{"tool": "T3", "qty": 2}, {"tool": "T1", "qty": 1}, {"tool": "T8", "qty": 1}],
    "SWW": [{"tool": "T3", "qty": 2}, {"tool": "T2", "qty": 1}, {"tool": "T8", "qty": 1}],
    "RWM": [{"tool": "T5", "qty": 2}, {"tool": "T1", "qty": 1}, {"tool": "T9", "qty": 1}],
    "SWM": [{"tool": "T5", "qty": 2}, {"tool": "T2", "qty": 1}, {"tool": "T9", "qty": 1}],
    "RMM": [{"tool": "T5", "qty": 2}, {"tool": "T4", "qty": 1}, {"tool": "T8", "qty": 1}],
    "SMM": [{"tool": "T5", "qty": 2}, {"tool": "T6", "qty": 1}, {"tool": "T8", "qty": 1}],
}

def generate_optimized_schedule(daily_orders):
    """
    Takes the JSON array from the ERP and creates an optimized machine schedule.
    """
    print("\nRunning MES Optimization Algorithm")
    
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
    print(f"Unloading Logistics: {total_final_pieces} pieces require {docks_needed} docks.")

    # 3. Optimize & Assign to Machines (Grouping by tool minimizes 30s changeovers)
    print("\nOPTIMIZED MACHINE SCHEDULE:")
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
