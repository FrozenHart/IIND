from dataclasses import dataclass


@dataclass
class Operation:
    piece_type: str
    action: str
    tool: str
    duration_s: int
    target_id: int
    material_id: int = 0
    req_top_id: int = 0
    req_leg_id: int = 0
    req_join_tool: int = 0


class RecipeEngine:
    """Computes next MES operations with legs-before-tops policy."""

    FINAL_RECIPES = {
        "RWW": {
            "top_id": 3,
            "leg_id": 5,
            "top_tool": "T1",
            "top_time": 30,
            "leg_tool": "T3",
            "leg_time": 10,
            "join_tool": "T8",
            "join_time": 10,
        },
        "SWW": {
            "top_id": 4,
            "leg_id": 5,
            "top_tool": "T2",
            "top_time": 20,
            "leg_tool": "T3",
            "leg_time": 10,
            "join_tool": "T8",
            "join_time": 10,
        },
        "RWM": {
            "top_id": 3,
            "leg_id": 8,
            "top_tool": "T1",
            "top_time": 30,
            "leg_tool": "T6",
            "leg_time": 20,
            "join_tool": "T9",
            "join_time": 10,
        },
        "SWM": {
            "top_id": 4,
            "leg_id": 8,
            "top_tool": "T2",
            "top_time": 20,
            "leg_tool": "T6",
            "leg_time": 20,
            "join_tool": "T9",
            "join_time": 10,
        },
        "RMM": {
            "top_id": 6,
            "leg_id": 8,
            "top_tool": "T4",
            "top_time": 35,
            "leg_tool": "T6",
            "leg_time": 20,
            "join_tool": "T8",
            "join_time": 10,
        },
        "SMM": {
            "top_id": 7,
            "leg_id": 8,
            "top_tool": "T5",
            "top_time": 25,
            "leg_tool": "T6",
            "leg_time": 20,
            "join_tool": "T8",
            "join_time": 10,
        },
    }

    TOOL_TO_MATERIAL = {
        "T1": 1,
        "T2": 1,
        "T3": 1,
        "T10": 1,
        "T4": 2,
        "T5": 2,
        "T6": 2,
        "T11": 2,
    }

    def next_operation(self, piece_type, ordered_qty, completed_qty, inventory):
        """Return the next single pending operation (legacy)."""
        batch = self.next_batch(piece_type, ordered_qty, completed_qty, inventory)
        if batch:
            return batch[0]
        return None

    def next_batch(self, piece_type, ordered_qty, completed_qty, inventory, max_tables=None):
        """Return pending operations.

        `max_tables` limits how many tables' worth of raw materials to
        create this cycle (table-slot system — 10 max in pipeline).
        """
        piece_type = str(piece_type).upper()
        if piece_type not in self.FINAL_RECIPES:
            return None

        remaining_final = max(0, int(ordered_qty) - int(completed_qty))
        if remaining_final == 0:
            return None

        if max_tables is not None:
            tables_to_process = min(remaining_final, int(max_tables))
        else:
            tables_to_process = remaining_final

        profile = self.FINAL_RECIPES[piece_type]
        legs_have = int(inventory.get("legs", 0))
        tops_have = int(inventory.get("tops", 0))

        legs_needed = max(0, tables_to_process * 2 - legs_have)
        tops_needed = max(0, tables_to_process * 1 - tops_have)

        ops = []

        for _ in range(legs_needed):
            material_id = self.TOOL_TO_MATERIAL[profile["leg_tool"]]
            ops.append(Operation(
                piece_type=piece_type,
                action="TRANSFORM",
                tool=profile["leg_tool"],
                duration_s=profile["leg_time"],
                target_id=profile["leg_id"],
                material_id=material_id,
            ))

        for _ in range(tops_needed):
            material_id = self.TOOL_TO_MATERIAL[profile["top_tool"]]
            ops.append(Operation(
                piece_type=piece_type,
                action="TRANSFORM",
                tool=profile["top_tool"],
                duration_s=profile["top_time"],
                target_id=profile["top_id"],
                material_id=material_id,
            ))

        if legs_needed == 0 and tops_needed == 0 and legs_have >= 2 and tops_have >= 1:
            ops.append(Operation(
                piece_type=piece_type,
                action="ASSEMBLE",
                tool=profile["join_tool"],
                duration_s=profile["join_time"],
                target_id=_final_piece_id(piece_type),
                req_top_id=profile["top_id"],
                req_leg_id=profile["leg_id"],
                req_join_tool=int(profile["join_tool"].replace("T", "")),
            ))

        return ops if ops else None


def _final_piece_id(piece_type):
    return {
        "RWW": 9,
        "SWW": 10,
        "RWM": 11,
        "SWM": 12,
        "RMM": 13,
        "SMM": 14,
    }[piece_type]
