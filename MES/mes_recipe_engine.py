from dataclasses import dataclass


@dataclass
class Operation:
    piece_type: str
    step: str
    tool: str
    quantity: int


class RecipeEngine:
    """Computes next MES operations with legs-before-tops policy."""

    # Per final product unit: legs required and tops required.
    REQUIRED_PARTS = {
        "RWW": {"legs": 2, "tops": 1, "leg_tool": "T3", "top_tool": "T1"},
        "SWW": {"legs": 2, "tops": 1, "leg_tool": "T3", "top_tool": "T2"},
        "RWM": {"legs": 2, "tops": 1, "leg_tool": "T5", "top_tool": "T1"},
        "SWM": {"legs": 2, "tops": 1, "leg_tool": "T5", "top_tool": "T2"},
        "RMM": {"legs": 2, "tops": 1, "leg_tool": "T5", "top_tool": "T4"},
        "SMM": {"legs": 2, "tops": 1, "leg_tool": "T5", "top_tool": "T6"},
    }

    def next_operation(self, piece_type, ordered_qty, completed_qty):
        piece_type = piece_type.upper()
        if piece_type not in self.REQUIRED_PARTS:
            return None

        remaining_final = max(0, ordered_qty - completed_qty)
        if remaining_final == 0:
            return None

        profile = self.REQUIRED_PARTS[piece_type]
        legs_needed = remaining_final * profile["legs"]
        tops_needed = remaining_final * profile["tops"]

        # Hard rule from simulation behavior: produce all legs first.
        if legs_needed > 0:
            return Operation(
                piece_type=piece_type,
                step="LEGS",
                tool=profile["leg_tool"],
                quantity=legs_needed,
            )

        return Operation(
            piece_type=piece_type,
            step="TOPS",
            tool=profile["top_tool"],
            quantity=tops_needed,
        )


def main():
    engine = RecipeEngine()
    sample = engine.next_operation("RWW", ordered_qty=2, completed_qty=0)
    print("[MES] Recipe engine ready.")
    print(f"[MES] Sample operation: {sample}")


if __name__ == "__main__":
    main()
