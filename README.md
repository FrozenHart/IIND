# IIND — Industrial Automation Project

ERP, MES, PLC, SCADA, Cloud Dashboard, and Shop Floor simulation for a flexible production line.

## Architecture Overview

```
Clients ──TCP 6666──► ERP (Python) ──┐
                                      ├──► PostgreSQL (erp_db) ◄── MES (Python) ──OPC-UA──► PLC (CODESYS)
                                      │                              │
                                      ▼                              ▼
                              ThingsBoard Cloud              ThingsBoard Cloud
                              (ERP_Monitor device)           (MES_Monitor device)
                                                                       ▲
                                                              mqtt_publisher.py
                                                                       │
                                                              PLC ──MQTT──► ThingsBoard Cloud
                                                                           (PLC_Gateway device)
```

## Prerequisites

- Python 3.10+
- PostgreSQL running on port `5000`
- Java Runtime (for Shop Floor Simulator `sfs.jar`)
- CODESYS Development System (for PLC project)
- ThingsBoard Cloud account (`thingsboard.cloud`)
- Installed Python dependencies:

```powershell
pip install -r requirements.txt
```

**Requirements:** `psycopg2-binary`, `asyncua`, `streamlit`, `paho-mqtt>=2.0`

---

## Quick Start — Complete Run Order

Run each step in this exact order from the project root (`iind/`):

### 1. PostgreSQL

Start PostgreSQL on port `5000`.

#### First run only — create the database:

```powershell
psql -p 5000 -U postgres -d postgres -c "CREATE DATABASE erp_db;"
```

#### Load the shared schema (first run and after full resets):

```powershell
psql -p 5000 -U postgres -d erp_db -f Database/shared_schema.sql
```

### 2. Shop Floor Simulator

```powershell
java -jar ShopFloor/sfs.jar ShopFloor/plant.properties
```

The simulator communicates with the PLC via Modbus/TCP on port `5502`.

### 3. CODESYS PLC

1. Open `PLC/PLC.project` in CODESYS.
2. Ensure the Modbus TCP slave is configured (see `Modbus_TCP_Slave.csv` for register mapping).
3. Log in to the PLC runtime and start the application.
4. Verify MQTT connection: `PRG_MQTT` publishes I/O signals to ThingsBoard `PLC_Gateway` every 2 seconds.

### 4. ERP — Full Stack

```powershell
python ERP/run_erp_programs.py --mode all
```

Starts:
- `erp_server.py` — TCP server (port 6666) listening for JSON client orders
- `erp_dispatcher.py` — dispatches orders into the planning pipeline
- `erp_gui.py` — Streamlit dashboard at **http://localhost:8501**

To auto-insert demo orders instead:
```powershell
python ERP/run_erp_programs.py --mode demo
```

### 5. MES — Full Stack

```powershell
python MES/run_mes_programs.py --mode all
```

Starts:
- `mes_service.py` — main orchestration loop
- `mes_scheduler.py` — priority scheduler
- `mes_dashboard.py` — Streamlit dashboard at **http://localhost:8502**

### 6. MQTT Bridge — Cloud Dashboards

```powershell
python mqtt_bridge/mqtt_publisher.py
```

Reads machine stats and order data from PostgreSQL and publishes to ThingsBoard:
- `MES_Monitor` device — machine occupation, tool changes, pieces processed, dock output
- `ERP_Monitor` device — simulation day, order counts, order statuses

### 7. ThingsBoard Dashboards

ThingBoard dashboards are accessed via the cloud at `thingsboard.cloud`.

#### Import the MES Dashboard (one-time)

1. Log in to `thingsboard.cloud`.
2. Go to **Dashboards** → **Import dashboard**.
3. Upload `mqtt_bridge/thingsboard_mes_dashboard.json`.
4. Verify the `MES_Monitor` entity alias resolves to the correct device.

#### Devices

| Device | Access Token | Data Source |
|--------|-------------|-------------|
| `PLC_Gateway` | In `mqtt_bridge/thingsboard_tokens.json` | PLC `PRG_MQTT` (CODESYS) |
| `MES_Monitor` | In `mqtt_bridge/thingsboard_tokens.json` | `mqtt_publisher.py` (from PostgreSQL) |
| `ERP_Monitor` | In `mqtt_bridge/thingsboard_tokens.json` | `mqtt_publisher.py` (from PostgreSQL) |

---

## Dashboards Reference

| Dashboard | URL / Location | Module |
|-----------|---------------|--------|
| ERP (Streamlit) | `http://localhost:8501` | `ERP/erp_gui.py` |
| MES (Streamlit) | `http://localhost:8502` | `MES/mes_dashboard.py` |
| ERP Cloud | thingsboard.cloud → ERP_Monitor device | `mqtt_publisher.py` |
| MES Cloud | thingsboard.cloud → MES_Monitor device | `mqtt_publisher.py` |
| PLC Cloud | thingsboard.cloud → PLC_Gateway device | PLC `PRG_MQTT` |

---

## Optional ERP Demo Mode

```powershell
python ERP/run_erp_programs.py --mode demo
```

Auto-inserts sample orders to test the planning pipeline.

---

## Database Reset

Full reset (drops all data and recreates tables):

```powershell
psql -p 5000 -U postgres -d erp_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
psql -p 5000 -U postgres -d erp_db -f Database/shared_schema.sql
```

---

## Notes

- ERP and MES share one database: `erp_db`.
- Dedicated project DB role: `iind_user`.
- Project DB password: `IIND20266`.
- Terminal output is launcher/service logging; the user-facing interfaces are browser dashboards.
- ThingsBoard tokens in `thingsboard_tokens.json` — do not commit this file to version control.
- The SCADA module is packaged as `SCADA/SCADA.zip` — extract and run separately if needed.
