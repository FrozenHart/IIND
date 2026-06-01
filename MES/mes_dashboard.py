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
    body = getattr(piece, "Body", None)
    if isinstance(body, (bytes, bytearray)) and body:
        le_uint16 = int.from_bytes(body[:2], "little") if len(body) >= 2 else int(body[0])
        return le_uint16
    piece_dict = getattr(piece, "__dict__", None)
    if piece_dict:
        try:
            tid = piece_dict.get("Type_ID") or piece_dict.get("TypeId")
            if tid is not None:
                return int(tid)
        except Exception:
            return 0
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


def _build_warehouse_table(warehouse_count, warehouse_values, label):
    if warehouse_values is None:
        st.error(f"Cannot read {label} snapshot")
        return
    limit = min(warehouse_count, len(warehouse_values))
    st.caption(f"Count: **{warehouse_count}**")
    rows = []
    for i in range(limit):
        tid = _extract_type_id(warehouse_values[i])
        rows.append({"Slot": i, "Type_ID": tid, "Label": TYPE_LABELS.get(tid, f"Unknown ({tid})")})
    if rows:
        st.dataframe(rows, width="stretch")
    else:
        st.info("Empty")


@st.fragment(run_every=5)
def _render_warehouse_fragment():
    snap = asyncio.run(read_warehouse_snapshot())
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("W1 (Top)")
        if snap is not None:
            w1c, _, tv, _ = snap
            _build_warehouse_table(w1c, tv, "W1")
        else:
            st.error("Cannot read W1 snapshot")
    with col2:
        st.subheader("W2 (Bottom)")
        if snap is not None:
            _, w2c, _, bv = snap
            _build_warehouse_table(w2c, bv, "W2")
        else:
            st.error("Cannot read W2 snapshot")


@st.fragment(run_every=4)
def _render_cell_status_fragment():
    st.subheader("Cell Status")

    async def load_conveyors():
        convs = {}
        for cell in CELL_LAYOUT.values():
            for cid in cell["conveyors"]:
                convs[cid] = await read_conveyor_state(cid)
        return convs

    conveyors = asyncio.run(load_conveyors())

    table = []
    for cell_name, info in CELL_LAYOUT.items():
        convs = info["conveyors"]
        busy = any(
            conveyors.get(c) is not None and conveyors[c]["action_type"] != 0
            for c in convs
        )
        status_icon = "BUSY" if busy else "FREE"
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
        table.append({
            "Cell": cell_name,
            "Lane": info["lane"],
            "Conveyors": " ".join(convs),
            "Status": status_icon,
            "Details": ", ".join(details),
        })

    st.dataframe(table, width="stretch")


def render():
    st.set_page_config(page_title="MES Debug Dashboard", layout="wide")
    st.title("MES Debug Dashboard")

    _render_warehouse_fragment()
    st.divider()
    _render_cell_status_fragment()


if __name__ == "__main__":
    render()