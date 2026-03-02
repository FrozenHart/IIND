# Automation of a Production Line

## Course Context
- **MB – Industrial Informatics**
- **Master's in Electrical and Computer Engineering**
- **Academic Year:** 2025/2026
- **Specification Version:** 1.0 (2026-02-27)
- **Specification Author:** Mário de Sousa

## Warning
The customer may update the project specifications up to **21 days before the delivery deadline**.

## Project Overview
This repository implements an Industrial Informatics project for a **flexible production line** simulation. The system is split into layered components that cover:

1. PLC-level control of equipment;
2. SCADA supervision and operator actions;
3. Cloud dashboard for machine/tool monitoring;
4. MES management and execution of production;
5. ERP order intake and production scheduling.

The production line is simulated with **SFS (Shop Floor Simulator)** and integrated through industrial protocols (Modbus/TCP and OPC-UA), with persistence in PostgreSQL.

## High-Level Architecture

### ERP (C++)
Headless backend listening on TCP port `6666` for JSON client orders. Computes production/purchasing plans and writes to PostgreSQL.

### Database (PostgreSQL)
Central persistent storage for orders, plans, and statistics so system restarts do not lose state.

### MES (Python)
Reads ERP orders from PostgreSQL, applies prioritization logic, sends control commands to PLC via OPC-UA, and provides a production monitoring interface.

### SCADA (Python)
Separate supervisory UI connected to PLC via Modbus/TCP. Monitors one selected cell (C1 to C6) and supports automatic/manual/maintenance modes.

### Cloud Dashboard (Python)
Publishes tool usage and machine statistics to cloud services via MQTT or HTTP REST.

### PLC (CODESYS / IEC 61131)
Implements low-level deterministic control and interfaces with the Shop Floor Simulator through Modbus/TCP.

## Repository Structure
- [CloudDashBoard](CloudDashBoard/README.md) – Cloud telemetry and dashboard integration.
- [ERP](ERP/README.md) – Order intake and planning backend.
- [MES](MES/README.md) – Production execution and monitoring.
- [PLC](PLC/README.md) – Low-level plant control logic.
- [SCADA](SCADA/README.md) – Supervisory and operator interface.
- [ShopFloor](ShopFloor/README.md) – Simulator assets, mappings, and plant configuration.

## Core Requirements Covered
- Flexible production line automation and equipment control.
- Supervisory interface with operator modes and alarms.
- Cloud-based machine/tool usage dashboard.
- MES order execution, prioritization, and statistics.
- ERP client order reception over TCP/JSON and planning.
- Persistent data storage for ERP/MES continuity.

## Change Log
| Version | Date       | Changes                   |
|---------|------------|---------------------------|
| 1.0     | 2026-02-27 | Initial published version |
