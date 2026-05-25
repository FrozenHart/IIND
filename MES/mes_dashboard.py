import asyncio
import sys
import streamlit as st

sys.path.insert(0, "Code")

from iind.MES.plc_client import read_warehouse_snapshot, read_conveyor_state

CELL_LAYOUT = {
    "Cell 1": {"lane": "U2", "conveyors": ["C6", "C8", "C10"]},
    "Cell 2": {"lane": "U3", "conveyors": ["C11", "C13", "C15"]},
    "Cell 3": {"lane": "U4", "conveyors": ["C16", "C18", "C20"]},
    "Cell 4": {"lane": "U5", "conveyors": ["C21", "C23", "C25"]},
}


def _extract_type_id(piece):
    if piece is None:
        return 0
    type_id = getattr(piece, "Type_ID", None)
    if type_id is not None:
        try:
            return int(type_id)
        except Exception:
            return 0
    if isinstance(piece, dict):
        try:
            return int(piece.get("Type_ID", 0))
        except Exception:
            return 0
    if isinstance(piece, (list, tuple)) and piece:
        try:
            return int(piece[0])
        except Exception:
            return 0
    piece_dict = getattr(piece, "__dict__", None)
    if piece_dict:
        try:
            return int(piece_dict.get("Type_ID", 0))
        except Exception:
            return 0
    body = getattr(piece, "Body", None)
    if isinstance(body, (bytes, bytearray)) and body:
        le_uint16 = int.from_bytes(body[:2], "little") if len(body) >= 2 else int(body[0])
        return le_uint16
    return 0


TYPE_LABELS = {
    1: "Raw Wood",
    2: "Raw Metal",
    3: "R_top_W",
    4: "S_top_W",
    5: "Leg_W",
    6: "R_top_M",
    7: "S_top_M",
    8: "Leg_M",
    9: "RWW",
    10: "SWW",
    11: "RWM",
    12: "SWM",
    13: "RMM",
    14: "SMM",
}


async def load_data():
    snapshot = await read_warehouse_snapshot()
    conveyors = {}
    for cell in CELL_LAYOUT.values():
        for cid in cell["conveyors"]:
            state = await read_conveyor_state(cid)
            conveyors[cid] = state
    return snapshot, conveyors


def render():
    st.set_page_config(page_title="MES Debug Dashboard", layout="wide")
    st.title("🔧 MES Debug Dashboard")

    snapshot, conveyors = asyncio.run(load_data())

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📦 W1 (Top)")
        if snapshot is not None:
            w1_count, _, top_vals, _ = snapshot
            st.caption(f"Count: **{w1_count}**")
            table = []
            limit = min(w1_count, len(top_vals))
            for i in range(limit):
                tid = _extract_type_id(top_vals[i])
                label = TYPE_LABELS.get(tid, f"Unknown ({tid})")
                table.append({"Slot": i, "Type_ID": tid, "Label": label})
            if table:
                st.dataframe(table, width="stretch")
            else:
                st.info("Empty")
        else:
            st.error("Cannot read W1 snapshot")

    with col2:
        st.subheader("📦 W2 (Bottom)")
        if snapshot is not None:
            _, w2_count, _, bot_vals = snapshot
            st.caption(f"Count: **{w2_count}**")
            table = []
            limit = min(w2_count, len(bot_vals))
            for i in range(limit):
                tid = _extract_type_id(bot_vals[i])
                label = TYPE_LABELS.get(tid, f"Unknown ({tid})")
                table.append({"Slot": i, "Type_ID": tid, "Label": label})
            if table:
                st.dataframe(table, width="stretch")
            else:
                st.info("Empty")
        else:
            st.error("Cannot read W2 snapshot")

    st.divider()
    st.subheader("🏭 Cell Status")

    cell_table = []
    for cell_name, info in CELL_LAYOUT.items():
        lane = info["lane"]
        convs = info["conveyors"]
        busy = any(
            conveyors.get(c) is not None and conveyors[c]["action_type"] != 0
            for c in convs
        )
        status_icon = "🔴 BUSY" if busy else "🟢 FREE"
        details = []
        for c in convs:
            s = conveyors.get(c)
            if s is None:
                details.append(f"{c}: ?")
            elif s["action_type"] == 0 and s["free"]:
                details.append(f"{c}: free")
            else:
                act = ["pass", "transform", "swallow", "assemble"]
                a = s["action_type"] if s["action_type"] < len(act) else "?"
                details.append(f"{c}: {a}")
        cell_table.append({
            "Cell": cell_name,
            "Lane": lane,
            "Conveyors": " ".join(convs),
            "Status": status_icon,
            "Details": ", ".join(details),
        })

    st.dataframe(cell_table, width="stretch")

    st.caption(f"Last refresh: {asyncio.get_event_loop().time():.0f}s since epoch")


if __name__ == "__main__":
    render()
