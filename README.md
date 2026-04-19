# Industrial Informatics: MES & ERP Backend Architecture

This repository contains the backend architecture for our automated production line project, including the ERP network listener, the MRP planning engine, the MES scheduler, and the OPC-UA physical hardware client.

## 🛠️ Prerequisites
Before running this project, you must have the following installed on your machine:
1. **Python 3.x**
2. **PostgreSQL** (Port 5433 or 5432) & **pgAdmin 4**
3. **Codesys** (For the PLC OPC-UA Server simulation)

## 🚀 Setup Instructions

### 1. Install Dependencies
Open your terminal in the root of this project and run:
`pip install -r requirements.txt`

### 2. Database Setup (Crucial)
You cannot run the servers without the persistent databases.
1. Open **pgAdmin 4**.
2. Create two new databases: `erp_db` and `mes_db`.
3. Open the Query Tool for `erp_db` and run the script located in `database/erp_schema.sql`.
4. Open the Query Tool for `mes_db` and run the script located in `database/mes_schema.sql`.

### 3. Configure Passwords
Open `erp/erp_server.py`, `erp/erp_dispatcher.py`, `erp/mrp_engine.py`, and `mes/mes_server.py`. 
Look at the top of each file and change `DB_PASS = "YOUR_PASSWORD_HERE"` to match your local PostgreSQL master password. (Also verify your `DB_PORT` matches your local install!).

## 🏭 How to Run the Factory

To simulate the full lights-out manufacturing pipeline, open three separate terminal windows:

1. **Start the Factory Brain:** Run `python mes/mes_server.py` (Listens on Port 7777).
2. **Start the Financial Brain:** Run `python erp/erp_server.py` (Listens on Port 6666).
3. **Receive an Order:** Run `python Tests/test_client.py` to simulate a client sending a JSON order to the ERP.
4. **Calculate Purchasing:** Run `python erp/mrp_engine.py` to generate the raw material purchasing plan.
5. **Dispatch to Factory:** Run `python erp/erp_dispatcher.py` to push the scheduled orders down to the MES.

The MES will automatically catch the dispatch, save it to the database, run the optimization algorithm to minimize tool-change times, and fire OPC-UA commands to Codesys.