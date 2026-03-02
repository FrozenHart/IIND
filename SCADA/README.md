# SCADA Module

## Purpose
The SCADA module provides a **separate Python operator interface** for cell-level supervision and operating mode management.

## Role in Architecture
- Connects to PLC via **Modbus/TCP**.
- Monitors one selected cell at a time (**C1 to C6**).
- Allows operator mode switching:
  - automatic
  - manual
  - maintenance

## Tech Stack
- Language: **Python**
- Protocol: **Modbus/TCP**
- UI: Dedicated SCADA GUI

## Inputs and Outputs
- Input: Real-time PLC data points for selected cell.
- Output: Operator commands and mode changes written to PLC.

## Dependencies
- Reliable Modbus/TCP communication with PLC.
- Shared tag/register mapping between PLC and SCADA.

## Notes
- Keep SCADA responsibilities focused on supervision and manual intervention.
- Avoid duplicating MES planning logic in this module.
