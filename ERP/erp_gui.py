import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import socket
import json
import pandas as pd
import psycopg2
import erp_mps

DB_CONFIG = dict(host="localhost", port="5000", database="erp_db", user="iind_user", password="IIND20266")
PIECE_TYPES = ["RWW", "SWW", "RWM", "SWM", "RMM", "SMM"]
PIECE_TYPE_LABELS = {
    "RWW": "Round Wood-Wood",
    "SWW": "Square Wood-Wood",
    "RWM": "Round Wood-Metal",
    "SWM": "Square Wood-Metal",
    "RMM": "Round Metal-Metal",
    "SMM": "Square Metal-Metal",
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)


def format_piece_type(piece_code):
    code = str(piece_code).upper()
    label = PIECE_TYPE_LABELS.get(code)
    if label:
        return f"{label} ({code})"
    return str(piece_code)


def apply_piece_labels(df, column_name):
    if column_name not in df.columns:
        return df

    out = df.copy()
    out[column_name] = out[column_name].apply(format_piece_type)
    return out


def query_dataframe(sql, params=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params or ())
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    cur.close()
    conn.close()
    return pd.DataFrame(rows, columns=columns)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="ERP System", page_icon="🏭", layout="wide")
st.title("🏭 ERP - Enterprise Resource Planning")

st_autorefresh = getattr(st, "autorefresh", None)

tab1, tab2, tab3 = st.tabs(["📋 Submit Order", "📅 Production Plans", "🏭 MES Feedback"])

# ---------------------------------------------------------------------------
# Tab 1 - Submit Order
# ---------------------------------------------------------------------------
def validate_order(client_name, nif_raw, order_id_raw, order_lines):
    """Returns a list of error strings. Empty list means valid."""
    errors = []

    if not client_name.strip():
        errors.append("Client Name is required.")

    # NIF: Portuguese tax number - exactly 9 digits
    nif_clean = nif_raw.strip()
    if not nif_clean:
        errors.append("NIF is required.")
    elif not nif_clean.isdigit():
        errors.append("NIF must contain digits only.")
    elif len(nif_clean) != 9:
        errors.append(f"NIF must be exactly 9 digits (you entered {len(nif_clean)}).")

    # Order ID: positive integer
    order_id_clean = order_id_raw.strip()
    if not order_id_clean:
        errors.append("Order ID is required.")
    elif not order_id_clean.isdigit() or int(order_id_clean) < 1:
        errors.append("Order ID must be a positive whole number.")

    # Order lines
    if not order_lines:
        errors.append("At least one order line is required.")
    for i, line in enumerate(order_lines, start=1):
        if line["quantity"] < 1:
            errors.append(f"Line {i}: Quantity must be at least 1.")
        if line["DDate"] < 1:
            errors.append(f"Line {i}: Delivery date must be at least 1 day.")
        if line["Penalty"] < 0:
            errors.append(f"Line {i}: Penalty cannot be negative.")

    return errors


def parse_uploaded_client_orders(raw_text):
    """Parses one or many client-order payloads from uploaded JSON text."""
    payload = json.loads(raw_text)
    payload_list = payload if isinstance(payload, list) else [payload]

    normalized = []
    for idx, item in enumerate(payload_list, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Entry {idx} must be a JSON object.")

        for key in ("name", "NIF", "OrderID", "orders"):
            if key not in item:
                raise ValueError(f"Entry {idx} is missing required key: {key}")

        if not isinstance(item["orders"], list) or not item["orders"]:
            raise ValueError(f"Entry {idx} must include a non-empty 'orders' list.")

        normalized.append(item)

    return normalized


def send_payload_to_erp(payload):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(('127.0.0.1', 6666))
    sock.send(json.dumps(payload).encode('utf-8'))
    sock.close()

with tab1:
    st.subheader("New Client Order")
    st.caption("Order will be sent as JSON over TCP to the ERP server on port 6666.")

    col1, col2, col3 = st.columns(3)
    client_name  = col1.text_input("Client Name", placeholder="e.g. FEUP Furniture Co.")
    client_nif   = col2.text_input("NIF", placeholder="9-digit Portuguese tax number", max_chars=9)
    order_id_raw = col3.text_input("Order ID", placeholder="e.g. 101")

    st.divider()
    st.markdown("**Order Lines**")

    # Initialise session state for dynamic items list
    if "order_lines" not in st.session_state:
        st.session_state.order_lines = [{"type": "RWM", "quantity": 1, "DDate": 3, "Penalty": 2.0}]

    # Render each item row
    for i, item in enumerate(st.session_state.order_lines):
        c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 0.4])
        item["type"]     = c1.selectbox(
            "Piece Type",
            PIECE_TYPES,
            index=PIECE_TYPES.index(item["type"]),
            key=f"type_{i}",
            format_func=format_piece_type,
        )
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
        errors = validate_order(client_name, client_nif, order_id_raw, st.session_state.order_lines)
        if errors:
            for err in errors:
                st.error(err)
        else:
            payload = {
                "name":    client_name.strip(),
                "NIF":     int(client_nif.strip()),
                "OrderID": int(order_id_raw.strip()),
                "orders":  [
                    {"type": it["type"], "quantity": it["quantity"],
                     "DDate": it["DDate"], "Penalty": it["Penalty"]}
                    for it in st.session_state.order_lines
                ]
            }
            try:
                send_payload_to_erp(payload)
                st.success(f"✅ Order {order_id_raw.strip()} submitted successfully for {client_name.strip()}!")
                st.session_state.order_lines = [{"type": "RWM", "quantity": 1, "DDate": 3, "Penalty": 2.0}]
                st.rerun()
            except ConnectionRefusedError:
                st.error("❌ Could not connect to ERP server. Is erp_server.py running on port 6666?")
            except TimeoutError:
                st.error("❌ Connection to ERP server timed out. Please try again.")

    st.divider()
    st.subheader("Upload Orders JSON")
    st.caption("Upload one JSON file containing one Client Order object or a list of Client Order objects.")

    uploaded_file = st.file_uploader("Choose JSON file", type=["json"])
    if uploaded_file is not None:
        try:
            raw_text = uploaded_file.getvalue().decode("utf-8")
            parsed_orders = parse_uploaded_client_orders(raw_text)
            st.success(f"Parsed {len(parsed_orders)} client-order payload(s).")
            st.json(parsed_orders)

            if st.button("📤 Submit Uploaded JSON"):
                sent = 0
                for payload in parsed_orders:
                    send_payload_to_erp(payload)
                    sent += 1
                st.success(f"✅ Sent {sent} payload(s) to ERP server on port 6666.")
        except json.JSONDecodeError:
            st.error("❌ Uploaded file is not valid JSON.")
        except Exception as exc:
            st.error(f"❌ Failed to parse uploaded file: {exc}")

# ---------------------------------------------------------------------------
# Tab 2 - Production Plans (MPS)
# ---------------------------------------------------------------------------
with tab2:
    if st_autorefresh is not None:
        st_autorefresh(interval=5000, key="erp_refresh")

    st.divider()
    current_day = erp_mps.get_current_day()
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
                    "Piece":          format_piece_type(o["Piece"]),
                    "Qty":            o["Qty"],
                    "Due Day":        o["DDate"],
                    "Penalty €/day":  o["Penalty_Per_Day"],
                    "Status":         "⚠️ Overdue" if prod_day < current_day else "🟢 On Schedule"
                })

        df = pd.DataFrame(rows)
        st.subheader("Master Production Schedule")
        st.dataframe(df, width="stretch", hide_index=True)

        st.subheader("🛒 Purchasing Recommendations - Day " + str(current_day))
        recs = erp_mps.generate_purchasing_plan(current_day, mps)
        if recs:
            for r in recs:
                st.markdown(r)
        else:
            st.info("No purchasing actions required today.")

    # Pending orders summary from DB
    st.divider()
    st.subheader("📦 All Orders")
    orders_placeholder = st.empty()
    try:
        orders_signature = query_dataframe(
            """
            SELECT
                (SELECT COUNT(*) FROM Orders) as order_count,
                (SELECT COALESCE(MAX(OrderID), '') FROM Orders) as max_order_id,
                (SELECT COUNT(*) FROM Order_Items) as item_count,
                (SELECT COALESCE(MAX(ItemID), 0) FROM Order_Items) as max_item_id
            """
        )
        signature_key = "orders_signature"
        signature_value = tuple(orders_signature.iloc[0].tolist())
        previous_signature = st.session_state.get(signature_key)
        st.session_state[signature_key] = signature_value

        if previous_signature != signature_value or "orders_cache" not in st.session_state:
            df_orders = query_dataframe("""
                SELECT o.OrderID, c.Name as Client, o.DDate, o.Penalty_Per_Day,
                       o.Status, o.Total_Cost, o.Estimated_Completion_Day,
                       oi.Piece_Type, oi.Quantity_Ordered, oi.Quantity_Done
                FROM Orders o
                JOIN Clients c ON o.Client_NIF = c.NIF
                JOIN Order_Items oi ON o.OrderID = oi.OrderID
                ORDER BY o.DDate ASC;
            """)
            df_orders = apply_piece_labels(df_orders, "piece_type")
            st.session_state["orders_cache"] = df_orders

        orders_placeholder.dataframe(
            st.session_state["orders_cache"],
            width="stretch",
            hide_index=True,
        )
    except Exception as e:
        orders_placeholder.error(f"Could not load orders: {e}")

    st.divider()
    st.subheader("🛠️ Maintenance")
    st.caption("Use these tools to reset the simulation state.")
    confirm_wipe = st.checkbox("I understand this deletes all ERP + MES data", key="confirm_wipe")
    if st.button("🧹 Clean Database", type="primary"):
        if not confirm_wipe:
            st.error("Please confirm the data wipe before continuing.")
        else:
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("DELETE FROM Production_Feedback;")
                cur.execute("DELETE FROM Unloading_Stats;")
                cur.execute("DELETE FROM Machine_Piece_Stats;")
                cur.execute("DELETE FROM Tool_Stats;")
                cur.execute("DELETE FROM Machine_Stats;")
                cur.execute("DELETE FROM Production_Orders;")
                cur.execute("DELETE FROM Order_Items;")
                cur.execute("DELETE FROM Orders;")
                cur.execute("DELETE FROM Clients;")
                cur.execute("UPDATE Simulation_State SET current_day = 0 WHERE id = 1;")
                conn.commit()
                cur.close()
                conn.close()
                st.success("Database cleaned and day reset to 0.")
                st.session_state.pop("orders_cache", None)
                st.session_state.pop("orders_signature", None)
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to clean database: {exc}")

# ---------------------------------------------------------------------------
# Tab 3 - MES Feedback
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("🏭 Production Feedback from MES")

    st.info(
        "**MES Integration Contract (Database-Only)**\n\n"
        "MES updates ERP feedback through database writes (no ERP↔MES TCP callback).\n\n"
        "Expected updates in `erp_db`:\n"
        "- insert records into `Production_Feedback`\n"
        "- update `Order_Items.Quantity_Done`\n"
        "- update `Orders.Total_Cost` and `Orders.Status`"
    )

    feedback_placeholder = st.empty()
    try:
        feedback_signature = query_dataframe(
            """
            SELECT
                (SELECT COUNT(*) FROM Production_Feedback) as feedback_count,
                (SELECT COALESCE(MAX(ID), 0) FROM Production_Feedback) as max_feedback_id
            """
        )
        signature_key = "feedback_signature"
        signature_value = tuple(feedback_signature.iloc[0].tolist())
        previous_signature = st.session_state.get(signature_key)
        st.session_state[signature_key] = signature_value

        if previous_signature != signature_value or "feedback_cache" not in st.session_state:
            df_feedback = query_dataframe("""
                SELECT pf.ID, pf.OrderID, pf.Pieces_Produced,
                       pf.Production_Cost, pf.Received_At,
                       o.Status as Order_Status
                FROM Production_Feedback pf
                JOIN Orders o ON pf.OrderID = o.OrderID
                ORDER BY pf.Received_At DESC;
            """)
            st.session_state["feedback_cache"] = df_feedback

        cached = st.session_state["feedback_cache"]
        if cached.empty:
            feedback_placeholder.warning("No feedback received from MES yet.")
        else:
            feedback_placeholder.dataframe(cached, width="stretch", hide_index=True)
            total_cost = cached["Production_Cost"].sum()
            st.metric("💰 Total Production Cost Reported", f"€{total_cost:.2f}")
    except Exception as e:
        feedback_placeholder.error(f"Could not load MES feedback: {e}")


def main():
    # Streamlit executes this script directly; this entrypoint keeps the
    # runnable-section layout consistent with other project modules.
    return None


if __name__ == "__main__":
    main()
