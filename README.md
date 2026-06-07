# IIND ERP + MES

## Overview

This project runs ERP and MES on a shared PostgreSQL database (`erp_db`) with browser-based graphical dashboards.

## Prerequisites

- Python 3.10+
- PostgreSQL running on port `5000`
- Installed dependencies:

```powershell
pip install -r requirements.txt
```

## Quick Start (Run Order)

Run in this order from the project root:

- Start PostgreSQL on port `5000`.

#### Create the database (first run only):

```powershell
psql -p 5000 -U postgres -d postgres -c "CREATE DATABASE erp_db;"
```

#### Load the shared schema (first run and after full resets):

```powershell
psql -p 5000 -U postgres -d erp_db -f Database/shared_schema.sql
```

#### Start ERP full stack:

```powershell
python ERP/run_erp_programs.py --mode all
```

ERP dashboard URL: `http://localhost:8501`

#### Start MES full stack:

```powershell
python MES/run_mes_programs.py --mode all
```

MES dashboard URL: `http://localhost:8502`


## Optional ERP Demo Mode

Use this to start ERP and auto-insert demo orders:

```powershell
python ERP/run_erp_programs.py --mode demo
```

## Database Reset

Full reset (drop schema + recreate all tables and grants):

```powershell
psql -p 5000 -U postgres -d erp_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
psql -p 5000 -U postgres -d erp_db -f Database/shared_schema.sql
```

## Notes

- ERP and MES share one database: `erp_db`.
- Dedicated project DB role: `iind_user`.
- Project DB password: `IIND20266`.
- Terminal output is launcher/service logging; the user-facing interfaces are browser dashboards.
