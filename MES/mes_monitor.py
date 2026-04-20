from collections import defaultdict

import psycopg2
import streamlit as st

from mes_scheduler import MACHINE_TOOLS

DB_HOST = "localhost"
DB_PORT = "5000"
DB_NAME = "erp_db"
DB_USER = "iind_user"
DB_PASS = "IIND20266"
SHIFT_SECONDS = 8 * 3600

PIECE_EST_SECONDS = {
    "RWW": 50,
    "SWW": 40,
    "RWM": 90,
    "SWM": 80,
    "RMM": 95,
    "SMM": 85,
}

ALL_MACHINE_IDS = sorted(MACHINE_TOOLS.keys())


def db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )


def as_int(value):
    if value is None:
        return 0
    return int(value)


def seconds_to_hms(total_seconds):
    total_seconds = max(0, as_int(total_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def normalize_status(status):
    label = str(status).strip().lower()
    if label in {"completed", "done"}:
        return "completed"
    if label in {"in progress", "in_progress", "running", "active"}:
        return "in_progress"
    return "pending"


def ensure_mes_schema():
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS production_orders (
                id SERIAL PRIMARY KEY,
                orderid VARCHAR(50) NOT NULL,
                piece_type VARCHAR(10) NOT NULL,
                quantity_ordered INT NOT NULL,
                production_day INT DEFAULT 1,
                quantity_produced INT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'Pending'
            )
            """
        )
        cur.execute(
            """
            ALTER TABLE production_orders
            ADD COLUMN IF NOT EXISTS production_day INT DEFAULT 1
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS machine_stats (
                machine_id VARCHAR(10) PRIMARY KEY,
                total_operating_sec INT DEFAULT 0,
                tool_changes INT DEFAULT 0,
                pieces_processed INT DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_stats (
                id SERIAL PRIMARY KEY,
                machine_id VARCHAR(10) REFERENCES machine_stats(machine_id),
                tool_id VARCHAR(10) NOT NULL,
                operating_sec INT DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS machine_piece_stats (
                id SERIAL PRIMARY KEY,
                machine_id VARCHAR(10) REFERENCES machine_stats(machine_id),
                piece_type VARCHAR(10) NOT NULL,
                pieces_processed INT DEFAULT 0,
                UNIQUE(machine_id, piece_type)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS unloading_stats (
                id SERIAL PRIMARY KEY,
                dock_id INT NOT NULL,
                piece_type VARCHAR(10) NOT NULL,
                quantity_unloaded INT DEFAULT 0
            )
            """
        )
        conn.commit()


def fetch_order_overview():
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, orderid, piece_type, status,
                   quantity_ordered, quantity_produced,
                   COALESCE(production_day, 1) AS production_day
            FROM production_orders
            ORDER BY id DESC
            """
        )
        rows = cur.fetchall()
        data = [
            {
                "id": row[0],
                "order_id": row[1],
                "piece_type": row[2],
                "status": row[3],
                "quantity_ordered": row[4],
                "quantity_produced": row[5],
                "production_day": row[6],
                "quantity_pending": max(0, row[4] - row[5]),
                "production_time_sec": row[5] * PIECE_EST_SECONDS.get(str(row[2]).upper(), 60),
            }
            for row in rows
        ]
        return data


def fetch_current_day():
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT current_day FROM simulation_state WHERE id = 1")
        row = cur.fetchone()
        return int(row[0]) if row else 0


def fetch_status_summary(overview):
    counts = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
    }
    for row in overview:
        counts[normalize_status(row["status"])] += 1
    return counts


def fetch_priority_status(overview, current_day):
    executable = [
        row
        for row in overview
        if normalize_status(row["status"]) != "completed"
        and as_int(row.get("production_day", 1)) <= as_int(current_day)
    ]

    ranked = sorted(
        executable,
        key=lambda row: (row["quantity_pending"], row["quantity_produced"]),
        reverse=True,
    )
    result = []
    for idx, row in enumerate(ranked, start=1):
        piece = str(row["piece_type"]).upper()
        step = "LEGS" if row["quantity_pending"] > 0 else "TOPS"
        result.append(
            {
                "priority_rank": idx,
                "order_id": row["order_id"],
                "piece_type": row["piece_type"],
                "pending": row["quantity_pending"],
                "production_day": row["production_day"],
                "algorithm_step": step,
                "reason": f"Higher pending quantity gets higher priority ({piece}).",
            }
        )
    return result


def fetch_machine_stats():
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT machine_id, total_operating_sec, tool_changes, pieces_processed
            FROM machine_stats
            ORDER BY machine_id
            """
        )
        rows = cur.fetchall()

    stats = []
    for row in rows:
        occupation = 0.0
        if SHIFT_SECONDS > 0:
            occupation = min(100.0, (float(row[1]) / float(SHIFT_SECONDS)) * 100.0)
        stats.append(
            {
                "machine_id": row[0],
                "total_operating_sec": row[1],
                "occupation_pct_of_shift": round(occupation, 2),
                "tool_changes": row[2],
                "pieces_processed": row[3],
            }
        )
    return stats


def fetch_machine_tool_stats():
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT machine_id, tool_id, SUM(operating_sec) AS total_operating_sec
            FROM tool_stats
            GROUP BY machine_id, tool_id
            ORDER BY machine_id, tool_id
            """
        )
        rows = cur.fetchall()

    return [
        {
            "machine_id": row[0],
            "tool_id": row[1],
            "total_operating_sec": row[2],
        }
        for row in rows
    ]


def fetch_operated_pieces_by_type(overview):
    grouped = {}
    for row in overview:
        p_type = str(row["piece_type"])
        grouped[p_type] = grouped.get(p_type, 0) + int(row["quantity_produced"])
    return [{"piece_type": k, "produced_total": v} for k, v in sorted(grouped.items())]


def fetch_machine_piece_stats():
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT machine_id, piece_type, pieces_processed
            FROM machine_piece_stats
            ORDER BY machine_id, piece_type
            """
        )
        rows = cur.fetchall()

    return [
        {
            "machine_id": row[0],
            "piece_type": row[1],
            "pieces_processed": row[2],
        }
        for row in rows
    ]


def fetch_unloading_total_by_dock():
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT dock_id, SUM(quantity_unloaded) AS total_unloaded
            FROM unloading_stats
            GROUP BY dock_id
            ORDER BY dock_id
            """
        )
        rows = cur.fetchall()

    return [{"dock_id": row[0], "total_unloaded": row[1]} for row in rows]


def fetch_unloading_by_type():
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT dock_id, piece_type, quantity_unloaded
            FROM unloading_stats
            ORDER BY dock_id, piece_type
            """
        )
        rows = cur.fetchall()

    return [
        {
            "dock_id": row[0],
            "piece_type": row[1],
            "quantity_unloaded": row[2],
        }
        for row in rows
    ]


def split_orders_by_status(overview):
    grouped = {
        "pending": [],
        "in_progress": [],
        "completed": [],
    }
    for row in overview:
        grouped[normalize_status(row["status"])].append(row)

    grouped["pending"].sort(key=lambda r: (r["quantity_pending"], -r["id"]), reverse=True)
    grouped["in_progress"].sort(key=lambda r: (r["quantity_pending"], -r["id"]), reverse=True)
    grouped["completed"].sort(key=lambda r: r["id"], reverse=True)
    return grouped


def render_order_card(order, current_day):
    ordered = max(1, as_int(order["quantity_ordered"]))
    produced = as_int(order["quantity_produced"])
    pending = as_int(order["quantity_pending"])
    production_day = as_int(order.get("production_day", 1))
    day_ready = production_day <= as_int(current_day)
    progress_value = min(1.0, max(0.0, produced / float(ordered)))

    with st.container(border=True):
        st.markdown(f"**{order['order_id']} - {order['piece_type']}**")
        st.progress(progress_value)
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Produced", produced)
        col_b.metric("Pending", pending)
        col_c.metric("Target", ordered)
        if day_ready:
            st.caption(f"Production day: {production_day} (ready)")
        else:
            st.caption(f"Production day: {production_day} (waiting for day {production_day})")
        st.caption(f"Produced-time estimate: {seconds_to_hms(order['production_time_sec'])}")


def render_order_lane(title, orders, empty_label, current_day):
    st.markdown(f"### {title} ({len(orders)})")
    if not orders:
        st.info(empty_label)
        return

    for order in orders[:12]:
        render_order_card(order, current_day)

    overflow = len(orders) - 12
    if overflow > 0:
        st.caption(f"+ {overflow} additional orders not shown in this lane")


def render_machine_stats(machine_stats, machine_tool_stats, machine_piece_stats):
    st.subheader("Machine Statistics")
    st.caption(
        "Requirement 4.3: total operating time, occupation percentage, tool changes, "
        "total operated pieces, and operated pieces by type."
    )

    stats_map = {row["machine_id"]: row for row in machine_stats}
    tools_by_machine = defaultdict(list)
    for row in machine_tool_stats:
        tools_by_machine[row["machine_id"]].append(row)

    pieces_by_machine = defaultdict(list)
    for row in machine_piece_stats:
        pieces_by_machine[row["machine_id"]].append(row)

    for machine_id in ALL_MACHINE_IDS:
        base = stats_map.get(
            machine_id,
            {
                "machine_id": machine_id,
                "total_operating_sec": 0,
                "occupation_pct_of_shift": 0.0,
                "tool_changes": 0,
                "pieces_processed": 0,
            },
        )

        with st.expander(
            f"{machine_id} | operating {seconds_to_hms(base['total_operating_sec'])} | "
            f"occupation {float(base['occupation_pct_of_shift']):.2f}%",
            expanded=False,
        ):
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Total operating time", seconds_to_hms(base["total_operating_sec"]))
            m_col2.metric("Occupation", f"{float(base['occupation_pct_of_shift']):.2f}%")
            m_col3.metric("Tool changes", as_int(base["tool_changes"]))
            m_col4.metric("Operated work-pieces", as_int(base["pieces_processed"]))

            st.markdown("**Operating Time by Tool**")
            tool_rows = sorted(tools_by_machine.get(machine_id, []), key=lambda r: str(r["tool_id"]))
            if not tool_rows:
                st.caption("No tool activity recorded yet.")
            else:
                max_tool_sec = max(as_int(r["total_operating_sec"]) for r in tool_rows) or 1
                for row in tool_rows:
                    operating_sec = as_int(row["total_operating_sec"])
                    st.write(f"{row['tool_id']}: {seconds_to_hms(operating_sec)}")
                    st.progress(min(1.0, operating_sec / float(max_tool_sec)))

            st.markdown("**Operated Work-Pieces by Type**")
            piece_rows = sorted(pieces_by_machine.get(machine_id, []), key=lambda r: str(r["piece_type"]))
            if not piece_rows:
                st.caption("No piece-type activity recorded yet.")
            else:
                total_piece_count = sum(as_int(r["pieces_processed"]) for r in piece_rows) or 1
                for row in piece_rows:
                    qty = as_int(row["pieces_processed"])
                    piece_share = qty / float(total_piece_count)
                    st.write(f"{row['piece_type']}: {qty}")
                    st.progress(min(1.0, piece_share))


def render_unloading_stats(unloading_total, unloading_by_type):
    st.subheader("Unloaded Work-Pieces")
    st.caption("Requirement 4.3: totals by unloading dock and by piece type for each dock.")

    totals_by_dock = {as_int(row["dock_id"]): as_int(row["total_unloaded"]) for row in unloading_total}
    by_type = defaultdict(list)
    for row in unloading_by_type:
        by_type[as_int(row["dock_id"])].append(
            {
                "piece_type": str(row["piece_type"]),
                "quantity_unloaded": as_int(row["quantity_unloaded"]),
            }
        )

    dock_ids = sorted(set(totals_by_dock.keys()) | set(by_type.keys()) | {1, 2, 3, 4, 5})
    columns = st.columns(3)
    for index, dock_id in enumerate(dock_ids):
        with columns[index % 3]:
            with st.container(border=True):
                total = totals_by_dock.get(dock_id, 0)
                st.markdown(f"**Dock {dock_id}**")
                st.metric("Total unloaded", total)

                piece_rows = sorted(by_type.get(dock_id, []), key=lambda r: r["piece_type"])
                if not piece_rows:
                    st.caption("No unloaded pieces recorded yet.")
                else:
                    denominator = max(1, sum(r["quantity_unloaded"] for r in piece_rows))
                    for row in piece_rows:
                        qty = row["quantity_unloaded"]
                        st.write(f"{row['piece_type']}: {qty}")
                        st.progress(min(1.0, qty / float(denominator)))


def render_priority_status(priority_status):
    st.subheader("Execution Priority and Algorithm Status")
    st.caption(
        "Priority rule: orders with more pending pieces are executed first; ties are broken by "
        "higher produced quantity."
    )

    if not priority_status:
        st.info("No queued orders to prioritize right now.")
        return

    top_rows = priority_status[:10]
    max_pending = max(as_int(row["pending"]) for row in top_rows) or 1
    for row in top_rows:
        with st.container(border=True):
            p_col1, p_col2, p_col3 = st.columns([1, 3, 2])
            p_col1.metric("Rank", as_int(row["priority_rank"]))
            p_col2.markdown(f"**{row['order_id']} - {row['piece_type']}**")
            p_col3.metric("Pending pieces", as_int(row["pending"]))
            p_col3.caption(f"Next step: {row['algorithm_step']} | Prod day: {row['production_day']}")
            st.progress(min(1.0, as_int(row["pending"]) / float(max_pending)))
            st.caption(row["reason"])


def load_dashboard_snapshot():
    ensure_mes_schema()
    overview = fetch_order_overview()
    current_day = fetch_current_day()
    return {
        "current_day": current_day,
        "overview": overview,
        "status_summary": fetch_status_summary(overview),
        "priority_status": fetch_priority_status(overview, current_day),
        "machine_stats": fetch_machine_stats(),
        "machine_tool_stats": fetch_machine_tool_stats(),
        "machine_piece_stats": fetch_machine_piece_stats(),
        "unloading_total": fetch_unloading_total_by_dock(),
        "unloading_by_type": fetch_unloading_by_type(),
        "global_piece_mix": fetch_operated_pieces_by_type(overview),
    }


def render_database_error(exc):
    st.error("MES monitor could not read the shared database tables.")
    st.code("psql -p 5000 -U postgres -d erp_db -f Database/shared_schema.sql")
    st.caption(f"Database error: {exc}")


def render_kpis(snapshot):
    overview = snapshot["overview"]
    status_summary = snapshot["status_summary"]
    current_day = snapshot["current_day"]
    future_waiting = sum(
        1
        for row in overview
        if normalize_status(row["status"]) == "pending"
        and as_int(row.get("production_day", 1)) > as_int(current_day)
    )

    total_ordered = sum(as_int(row["quantity_ordered"]) for row in overview)
    total_produced = sum(as_int(row["quantity_produced"]) for row in overview)
    total_pending = sum(as_int(row["quantity_pending"]) for row in overview)
    total_production_time = sum(as_int(row["production_time_sec"]) for row in overview)

    k_col1, k_col2, k_col3, k_col4, k_col5 = st.columns(5)
    k_col1.metric("Simulation Day", current_day)
    k_col2.metric("To Do", status_summary["pending"])
    k_col3.metric("In Progress", status_summary["in_progress"])
    k_col4.metric("Completed", status_summary["completed"])
    k_col5.metric("Future Queue", future_waiting)

    k2_col1, k2_col2, k2_col3 = st.columns(3)
    k2_col1.metric("Total Orders", len(overview))
    k2_col2.metric("Produced Pieces", total_produced)
    k2_col3.metric("Pending Pieces", total_pending)

    st.caption(f"Estimated Produced Time: {seconds_to_hms(total_production_time)}")


def render_orders_page(snapshot):
    overview = snapshot["overview"]
    current_day = snapshot["current_day"]
    st.subheader("Order Flow")
    st.caption(
        "Orders grouped by status. Future orders are queued immediately and executed when "
        "simulation day reaches their production day."
    )
    grouped_orders = split_orders_by_status(overview)
    lane1, lane2, lane3 = st.columns(3)
    with lane1:
        render_order_lane("To Do", grouped_orders["pending"], "No pending orders.", current_day)
    with lane2:
        render_order_lane(
            "In Progress",
            grouped_orders["in_progress"],
            "No orders currently in progress.",
            current_day,
        )
    with lane3:
        render_order_lane("Done", grouped_orders["completed"], "No completed orders yet.", current_day)

    with st.expander("All Orders (table view)", expanded=False):
        st.dataframe(overview, width="stretch", hide_index=True)


def render_algorithm_page(snapshot):
    render_priority_status(snapshot["priority_status"])


def render_machine_page(snapshot):
    render_machine_stats(
        snapshot["machine_stats"],
        snapshot["machine_tool_stats"],
        snapshot["machine_piece_stats"],
    )

    st.subheader("Global Operated Work-Pieces by Type")
    global_piece_mix = snapshot["global_piece_mix"]
    if not global_piece_mix:
        st.caption("No operated pieces recorded yet.")
    else:
        total_mix = sum(as_int(row["produced_total"]) for row in global_piece_mix) or 1
        for row in global_piece_mix:
            produced_total = as_int(row["produced_total"])
            st.write(f"{row['piece_type']}: {produced_total}")
            st.progress(min(1.0, produced_total / float(total_mix)))


def render_unloading_page(snapshot):
    render_unloading_stats(snapshot["unloading_total"], snapshot["unloading_by_type"])


def render_debug_page(snapshot):
    st.caption("Detailed raw data for debugging and validation.")
    st.write("production_orders")
    st.dataframe(snapshot["overview"], width="stretch", hide_index=True)
    st.write("machine_stats")
    st.dataframe(snapshot["machine_stats"], width="stretch", hide_index=True)
    st.write("tool_stats (aggregated by machine/tool)")
    st.dataframe(snapshot["machine_tool_stats"], width="stretch", hide_index=True)
    st.write("machine_piece_stats")
    st.dataframe(snapshot["machine_piece_stats"], width="stretch", hide_index=True)
    st.write("unloading_stats by dock")
    st.dataframe(snapshot["unloading_total"], width="stretch", hide_index=True)
    st.write("unloading_stats by dock and type")
    st.dataframe(snapshot["unloading_by_type"], width="stretch", hide_index=True)


def render_all_pages(snapshot):
    render_kpis(snapshot)

    tab_orders, tab_algorithm, tab_machines, tab_unloading, tab_debug = st.tabs(
        [
            "Orders",
            "Algorithm",
            "Machine Statistics",
            "Unloading",
            "Raw Data",
        ]
    )

    with tab_orders:
        render_orders_page(snapshot)
    with tab_algorithm:
        render_algorithm_page(snapshot)
    with tab_machines:
        render_machine_page(snapshot)
    with tab_unloading:
        render_unloading_page(snapshot)
    with tab_debug:
        render_debug_page(snapshot)


def render_static_all_pages():
    try:
        snapshot = load_dashboard_snapshot()
    except Exception as exc:
        render_database_error(exc)
        return

    render_all_pages(snapshot)


def main():
    st.set_page_config(page_title="MES Monitor", layout="wide")
    st.title("MES Monitor")

    header_col, refresh_col = st.columns([5, 1])
    with refresh_col:
        if st.button("Refresh", width="stretch"):
            st.rerun()

    render_static_all_pages()


if __name__ == "__main__":
    main()
