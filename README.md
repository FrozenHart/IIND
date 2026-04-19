# Industrial Informatics: MES & ERP Backend Architecture

This repository contains the backend architecture for an automated production line project, including the ERP order management system, MRP planning engine, MPS scheduler, MES production dispatcher, and OPC-UA physical hardware client.

## Architecture Overview

```
Client (GUI / test_client.py)
        |  JSON over TCP (port 6666)
        v
   ERP Server  ──────────────────────────────> MES Feedback (port 6668)
        |                                            ^
   ERP Dispatcher (ticks every 60s = 1 sim day)     | production cost
        |  JSON over TCP (port 7777)                 |
        v                                            |
   MES Server ──> Scheduler ──> PLC Client (OPC-UA) ─┘
        |
   PostgreSQL (erp_db / mes_db)
```

---

## Prerequisites

Before running this project, install the following:

1. **Python 3.10+** (Homebrew recommended on macOS: `brew install python`)
2. **PostgreSQL 16** on **port 5433**
3. **Codesys** (only required for live PLC/OPC-UA commands — optional for ERP/MES testing)

### Install PostgreSQL (macOS)

```bash
brew install postgresql@16
brew services start postgresql@16
```

Then set PostgreSQL to run on port 5433 (to match the project config):

```bash
# Edit postgresql.conf
sed -i '' 's/#port = 5432/port = 5433/' /opt/homebrew/var/postgresql@16/postgresql.conf
brew services restart postgresql@16
```

---

## Setup Instructions

### 1. Clone and create a virtual environment

```bash
cd /path/to/iind
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create the PostgreSQL databases

```bash
/opt/homebrew/opt/postgresql@16/bin/psql -p 5433 -U $(whoami) -d postgres -c "CREATE DATABASE erp_db;"
/opt/homebrew/opt/postgresql@16/bin/psql -p 5433 -U $(whoami) -d postgres -c "CREATE DATABASE mes_db;"
```

### 4. Create a postgres user

```bash
/opt/homebrew/opt/postgresql@16/bin/psql -p 5433 -U $(whoami) -d postgres -c "CREATE ROLE postgres WITH SUPERUSER LOGIN PASSWORD 'IIND20266';"
```

### 5. Run the database schemas

```bash
/opt/homebrew/opt/postgresql@16/bin/psql -p 5433 -U postgres -d erp_db -f Database/erp_schema.sql
/opt/homebrew/opt/postgresql@16/bin/psql -p 5433 -U postgres -d mes_db -f Database/mes_schema.sql
```

### 6. Configure passwords (if using a different PostgreSQL password)

Open the following files and update `DB_PASS` at the top of each:

- `ERP/erp_server.py`
- `ERP/erp_dispatcher.py`
- `ERP/erp_engine.py`
- `ERP/erp_mps.py`
- `ERP/erp_gui.py`
- `MES/mes_server.py`

---

## Running the System

Open **4 terminal windows**, activate the virtual environment in each:

```bash
source /path/to/iind/.venv/bin/activate
```

### Terminal 1 — MES Server (start first)
```bash
cd /path/to/iind/MES && python mes_server.py
```
Listens for production orders from ERP on **port 7777**.

### Terminal 2 — ERP Server
```bash
cd /path/to/iind/ERP && python erp_server.py
```
Listens for:
- Client orders on **port 6666** (JSON over TCP)
- MES production feedback on **port 6668** (JSON over TCP)

### Terminal 3 — ERP Dispatcher
```bash
cd /path/to/iind/ERP && python erp_dispatcher.py
```
Ticks every **60 seconds** (= 1 simulation day). On each tick it:
1. Advances the simulation clock
2. Prints the Master Production Schedule (MPS)
3. Prints purchasing recommendations
4. Dispatches any orders due today to the MES

### Terminal 4 — ERP GUI
```bash
cd /path/to/iind/ERP && streamlit run erp_gui.py
```
Opens a browser at `http://localhost:8501` with three tabs:

| Tab | Description |
|-----|-------------|
| Submit Order | Form to submit client orders (sent over TCP to port 6666) |
| Production Plans | Live MPS table, purchasing recommendations, all orders view |
| MES Feedback | Displays production cost data received back from MES |

---

## Sending a Test Order (without the GUI)

With the ERP server running, send a test order from the command line:

```bash
source /path/to/iind/.venv/bin/activate
cd /path/to/iind/MES_ERP_Tests && python test_client.py
```

---

## Simulation Time Model

| Simulation | Real time |
|---|---|
| 1 day | 60 seconds |
| DDate = 3 | order due after 3 × 60s = 180s |

The dispatcher schedules each order for production on `DDate - 1` to meet the deadline. Orders are dispatched to the MES on their scheduled production day.

---

## MES Integration Contract

The MES must send a JSON callback to **TCP port 6668** on the ERP machine when an order is completed:

```json
{
  "OrderID": "101-RWM",
  "Pieces_Produced": 5,
  "Production_Cost": 125.50
}
```

The ERP will automatically update `Quantity_Done`, `Total_Cost`, and mark the order as `Completed`.

---

## Resetting the Simulation

To wipe all data and restart from Day 1:

```bash
/opt/homebrew/opt/postgresql@16/bin/psql -p 5433 -U postgres -d erp_db \
  -c "DROP TABLE IF EXISTS Production_Feedback, Order_Items, Orders, Clients, Simulation_State CASCADE;" \
  && /opt/homebrew/opt/postgresql@16/bin/psql -p 5433 -U postgres -d erp_db \
  -f /path/to/iind/Database/erp_schema.sql
```

---

## Project Structure

```
iind/
├── ERP/
│   ├── erp_server.py       # TCP listener (port 6666 orders, port 6668 MES feedback)
│   ├── erp_dispatcher.py   # Simulation clock + daily MPS dispatch loop
│   ├── erp_mps.py          # MPS engine (scheduling + purchasing plan)
│   ├── erp_engine.py       # MRP purchasing calculator
│   └── erp_gui.py          # Streamlit web GUI
├── MES/
│   ├── mes_server.py       # TCP listener (port 7777), receives ERP dispatch
│   ├── mes_scheduler.py    # Production optimisation algorithm
│   └── plc_client.py       # OPC-UA client → Codesys PLC
├── Database/
│   ├── erp_schema.sql      # ERP database schema
│   └── mes_schema.sql      # MES database schema
├── MES_ERP_Tests/
│   └── test_client.py      # Simulates a client sending an order to the ERP
└── requirements.txt
```
