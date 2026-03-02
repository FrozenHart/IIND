# Cloud Dashboard Module

## Purpose
The Cloud Dashboard module publishes tool/machine usage metrics from the shop floor to cloud services.

## Role in Architecture
- Collects usage/statistical data relevant for remote visibility.
- Pushes telemetry to cloud endpoint using:
  - **MQTT**, or
  - **HTTP REST**

## Tech Stack
- Language: **Python**
- Protocols: **MQTT**, **HTTP REST**

## Inputs and Outputs
- Input: Usage statistics from local systems (MES/SCADA/DB integration as defined by implementation).
- Output: Cloud-published telemetry for dashboards and analytics.

## Dependencies
- Network connectivity to broker/API.
- Authentication/authorization setup for cloud endpoint.

## Notes
- Ensure retry/backoff and buffering for transient connectivity issues.
- Keep payload schema stable for downstream dashboards.
