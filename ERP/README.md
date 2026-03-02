# ERP Module

## Purpose
The ERP is a **headless C++ backend service** that receives client production orders and generates production/purchasing plans.

## Role in Architecture
- Listens on **TCP port 6666** for JSON client orders.
- Parses and validates incoming order payloads.
- Calculates production and purchasing plans.
- Writes plans and order state directly to PostgreSQL for persistence.

## Tech Stack
- Language: **C++**
- Communication: **TCP socket server (port 6666)**, JSON messages
- Data store: **PostgreSQL**

## Inputs and Outputs
- Input: JSON order requests from clients.
- Output: Planned orders, purchasing decisions, and related records in PostgreSQL.

## Dependencies
- PostgreSQL availability and schema consistency.
- Stable contract for JSON message format.

## Notes
- Keep this service stateless beyond runtime memory; persistence is handled by PostgreSQL.
- Any protocol/schema change should be reflected in MES data consumption logic.
