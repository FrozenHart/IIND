# Shop Floor Module

## Purpose
The Shop Floor folder contains simulator assets, plant configuration files, and I/O/address mappings used by the PLC and integration layers.

## Role in Architecture
- Hosts files supporting the simulated production environment.
- Provides addressing and I/O mapping artifacts consumed by control software.
- Supports PLC integration and runtime behavior validation.

## Current Contents
- `plant.properties`, `plant.properties.sh`
- `enderecos.csv`, `enderecos.txt`
- `io.csv`
- simulator assets/jars and related resources

## Tech Stack
- Configuration assets and simulator resources
- Interfaces mainly through **Modbus/TCP** mappings and plant configuration

## Inputs and Outputs
- Input: Configuration edits and simulator setup changes.
- Output: Runtime plant behavior for PLC/MES/SCADA integration testing.

## Dependencies
- Consistency between address mapping files and PLC program variables.
- Compatible simulator and runtime environment.

## Notes
- Treat mapping/config files as source-of-truth artifacts.
- Validate changes with end-to-end communication checks.
