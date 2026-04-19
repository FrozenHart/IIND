import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import socket
import json
import pandas as pd
import psycopg2
import erp_mps

DB_CONFIG = dict(host="localhost", port="5433", database="erp_db", user="postgres", password="IIND20266")
PIECE_TYPES = ["RWW", "SWW", "RWM", "SWM", "RMM", "SMM"]

def get_db():
    return psycopg2.connect(**DB_CONFIG)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="ERP System", page_icon="🏭", layout="wide")
st.title("🏭 ERP — Enterprise Resource Planning")

tab1, tab2, tab3 = st.tabs(["📋 Submit Order", "📅 Production Plans", "🏭 MES Feedback"])

# ---------------------------------------------------------------------------
# Tab 1 — Submit Order
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("New Client Order")
    st.caption("Order will be sent as JSON over TCP to the ERP server on port 6666.")

    col1, col2, col3 = st.columns(3)
    client_name = col1.text_input("Client Name", placeholder="e.g. FEUP Furniture Co.")
    client_nif  = col2.number_input("NIF", min_value=1, step=1, value=987654321)
    order_id    = col3.number_input("Order ID", min_value=1, step=1, value=101)

    st.divider()
    st.markdown("**Order Lines**")

    # Initialise session state for dynamic items list
    if "order_lines" not in st.session_state:
        st.session_state.order_lines = [{"type": "RWM", "quantity": 1, "DDate": 3, "Penalty": 2.0}]

    # Render each item row
    for i, item in enumerate(st.session_state.order_lines):
        c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 0.4])
        item["type"]     = c1.selectbox("Piece Type", PIECE_TYPES, index=PIECE_TYPES.index(item["type"]), key=f"type_{i}")
        item["quantity"] = c2.number_input("Quantity", min_value=1, value=item["quantity"], key=f"qty_{i}")
        item["DDate"]    = c3.number_input("DDate (days)", min_value=1, value=item["DDate"], key=f"ddate_{i}")
        item["Penalty"]  = c4.number_input("Penalty (€/day)", min_value=0.0, step=0.5, value=item["Penalty"], key=f"pen_{i}", format="%.2f")
        if c5.button("✖", key=f"rm_{i}", help="Remove line") and len(st.session_state.order_lines) > 1:
            st.session_state.order_lines.pop(i)
            st.rerun()

    if st.button("➕ Add Order Line"):
        st.session_state.order_lines.append({"type": "RWM", "quantity": 1, "DDate": 3, "Penalty": 1.0})
        st.rerun()

    st.divider()

    if st.button("📤 Submit Order", type="primary"):
        if not client_name.strip():
            st.error("Client name is required.")
        else:
            payload = {
                "name":    client_name.strip(),
                "NIF":     int(client_nif),
                "OrderID": int(order_id),
                "orders":  [
                    {"type": it["type"], "quantity": it["quantity"],
                     "DDate": it["DDate"], "Penalty": it["Penalty"]}
                    for it in st.session_state.order_lines
                ]
            }
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(('127.0.0.1', 6666))
                sock.send(json.dumps(payload).encode('utf-8'))
                sock.close()
                st.success(f"✅ Order {order_id} submitted successfully!")
                # Reset items for next order
                st.session_state.order_lines = [{"type": "RWM", "quantity": 1, "DDate": 3, "Penalty": 2.0}]
                st.rerun()
            except ConnectionRefusedError:
                st.error("❌ Could not connect to ERP server. Is erp_server.py running on port 6666?")

# ---------------------------------------------------------------------------
# Tab 2 — Production Plans (MPS)
# ---------------------------------------------------------------------------
with tab2:
    col_day, col_refresh = st.columns([3, 1])

    current_day = erp_mps.get_current_day()
    col_day.metric("📅 Current Simulation Day", current_day, help="1 day = 60 seconds")

    if col_refresh.button("🔄 Refresh", use_container_width=True):
        st.rerun()

    st.divider()
    mps = erp_mps.generate_mps()

    if not mps:
        st.info("No pending orders in the MPS.")
    else:
        # Build MPS dataframe
        rows = []
        for prod_day in sorted(mps.keys()):
            for o in mps[prod_day]:
                rows.append({
                    "Production Day": prod_day,
                    "Order ID":       o["OrderID"],
                    "Piece":          o["Piece"],
                    "Qty":            o["Qty"],
                    "Due Day":        o["DDate"],
                    "Penalty €/day":  o["Penalty_Per_Day"],
                    "Status":         "⚠️ Overdue" if prod_day < current_day else "🟢 On Schedule"
                })

        df = pd.DataFrame(rows)
        st.subheader("Master Production Schedule")
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("🛒 Purchasing Recommendations — Day " + str(current_day))
        recs = erp_mps.generate_purchasing_plan(current_day, mps)
        if recs:
            for r in recs:
                st.markdown(r)
        else:
            st.info("No purchasing actions required today.")

    # Pending orders summary from DB
    st.divider()
    st.subheader("📦 All Orders")
    try:
        conn = get_db()
        df_orders = pd.read_sql("""
            SELECT o.OrderID, c.Name as Client, o.DDate, o.Penalty_Per_Day,
                   o.Status, o.Total_Cost,
                   oi.Piece_Type, oi.Quantity_Ordered, oi.Quantity_Done
            FROM Orders o
            JOIN Clients c ON o.Client_NIF = c.NIF
            JOIN Order_Items oi ON o.OrderID = oi.OrderID
            ORDER BY o.DDate ASC;
        """, conn)
        conn.close()
        st.dataframe(df_orders, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Could not load orders: {e}")

# ---------------------------------------------------------------------------
# Tab 3 — MES Feedback
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("🏭 Production Feedback from MES")

    st.info(
        "**MES Integration Contract**\n\n"
        "When MES completes an order, it must send the following JSON to **TCP port 6668** on this machine:\n\n"
        "```json\n"
        "{\n"
        '  "OrderID": "101-RWM",\n'
        '  "Pieces_Produced": 5,\n'
        '  "Production_Cost": 125.50\n'
        "}\n"
        "```\n\n"
        "The ERP will automatically update `Quantity_Done`, `Total_Cost`, and mark the order as `Completed`."
    )

    if st.button("🔄 Refresh Feedback", use_container_width=False):
        st.rerun()

    try:
        conn = get_db()
        df_feedback = pd.read_sql("""
            SELECT pf.ID, pf.OrderID, pf.Pieces_Produced,
                   pf.Production_Cost, pf.Received_At,
                   o.Status as Order_Status
            FROM Production_Feedback pf
            JOIN Orders o ON pf.OrderID = o.OrderID
            ORDER BY pf.Received_At DESC;
        """, conn)
        conn.close()

        if df_feedback.empty:
            st.warning("No feedback received from MES yet.")
        else:
            st.dataframe(df_feedback, use_container_width=True, hide_index=True)

            total_cost = df_feedback["Production_Cost"].sum()
            st.metric("💰 Total Production Cost Reported", f"€{total_cost:.2f}")

    except Exception as e:
        st.error(f"Could not load MES feedback: {e}")
