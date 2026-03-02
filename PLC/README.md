# PLC Module

## Purpose
The PLC module contains the low-level automation logic for physical process control.

## Role in Architecture
- Implements control logic in **CODESYS** using **IEC 61131**.
- Executes deterministic machine control and sequencing.
- Connects to Shop Floor Simulator via **Modbus/TCP**.
- Receives high-level commands from MES and mode/control interactions from SCADA.

## Tech Stack
- Platform: **CODESYS PLC runtime**
- Standard: **IEC 61131**
- Protocol: **Modbus/TCP**

## Inputs and Outputs
- Input: Commands from MES (OPC-UA path), supervision actions from SCADA (Modbus/TCP path).
- Output: Actuator/control states and process variables exposed to higher layers.

## Dependencies
- Correct simulator mapping and PLC variable/register mapping.
- Stable protocol contracts with MES and SCADA.

## Notes
- Prioritize fail-safe behavior and predictable state transitions.
- Keep I/O maps synchronized with Shop Floor configuration.
