# MES Module

## Purpose
The MES is a **Python orchestration layer** that executes prioritization logic and controls production flow through the PLC.

## Role in Architecture
- Reads ERP-generated orders from PostgreSQL.
- Applies prioritization and scheduling logic.
- Sends commands to PLC using **OPC-UA**.
- Hosts the main graphical interface for monitoring:
  - order status
  - machine statistics

## Tech Stack
- Language: **Python**
- Data source: **PostgreSQL**
- Control protocol: **OPC-UA**
- UI: Local MES GUI

## Inputs and Outputs
- Input: Orders and plans persisted by ERP in PostgreSQL.
- Output: Control commands to PLC and status visualization for operators.

## Dependencies
- PostgreSQL connectivity.
- OPC-UA endpoint exposed by PLC/CODESYS runtime.

## Notes
- Prioritization policy changes should be versioned and documented.
- UI state should reflect database truth whenever possible.
