# MQTT Implementation Plan — ThingsBoard Cloud Dashboard

## Overview

This document describes how to integrate the CODESYS `MQTT Library.library` (Rossmann-Engineering) into the existing PLC project and connect it to a ThingsBoard cloud dashboard. The PLC publishes telemetry directly via MQTT, eliminating the need for an external Python bridge for PLC I/O data.

---

## Target Architecture

```
CODESYS PLC (with MQTT Library)
   │
   │  FB_MQTTClient — publishes GVL variables as JSON telemetry
   │  FB_MQTTClient — subscribes to ThingsBoard RPC commands
   │
   ▼
ThingsBoard Cloud (port 1883, access token auth)
   ├── Device: PLC_Gateway   ← PLC I/O signals
   ├── Device: MES_Monitor   ← Machine/tool stats from PostgreSQL
   └── Device: ERP_Monitor   ← Order KPIs from PostgreSQL
   │
   ▼
ThingsBoard Dashboard: "IIND Factory Floor"

Python (lightweight — MES/ERP PostgreSQL stats only)
   └── mqtt_publisher.py  →  MES_Monitor + ERP_Monitor devices
```

---

## Library Reference — FB_MQTTClient

The library exposes a single function block (`FB_MQTTClient`) that handles TCP connect, MQTT handshake, publish, and subscribe in one state machine.

### Inputs

| Input | Type | Default | Purpose |
|---|---|---|---|
| `i_xEnable` | `BOOL` | `TRUE` | Rising edge connects to broker |
| `i_sBrokerAddress` | `STRING` | `'www.mqtt-dashboard.com'` | Broker IP or hostname |
| `i_uiPort` | `UINT` | `1883` | Broker port |
| `i_sUsername` | `STRING` | `''` | ThingsBoard **Access Token** goes here |
| `i_sPassword` | `STRING` | `''` | Leave empty for ThingsBoard |
| `i_sClientID` | `STRING` | `'12345678'` | Unique MQTT client ID |
| `i_sPayload` | `STRING(255)` | — | JSON payload to publish (max 255 chars) |
| `i_sTopicPublish` | `STRING` | `'CoDeSys'` | Topic to publish to |
| `i_sTopicSubscribe` | `STRING` | `'CoDeSys'` | Topic to subscribe to |
| `i_xPublish` | `BOOL` | `FALSE` | Rising edge triggers a publish |
| `i_xSubscribe` | `BOOL` | `FALSE` | Rising edge registers subscription |
| `i_xRetain` | `BOOL` | `TRUE` | MQTT retain flag on publish |
| `i_xAutoReconnect` | `BOOL` | `TRUE` | Reconnect automatically on error |
| `i_sWillTopic` | `STRING` | `''` | Last Will topic (optional) |
| `i_sWillMessage` | `STRING` | `''` | Last Will message (optional) |

### Outputs

| Output | Type | Purpose |
|---|---|---|
| `q_xError` | `BOOL` | Error flag |
| `q_sDiagMsg` | `STRING` | Human-readable state description |
| `q_udiState` | `UDINT` | Internal state machine number |
| `q_xReceivedMessageNotification` | `BOOL` | TRUE when new message arrives |
| `q_sLastReceivedMessage` | `STRING(1024)` | Most recent received payload |
| `q_arsLastReceivedMessages` | `ARRAY[0..24] OF STRING(1024)` | Last 25 received messages |
| `q_arsLastReceivedMessageTopics` | `ARRAY[0..24] OF STRING` | Last 25 received topics |

### JSON Helper Functions

| Function | Signature | Purpose |
|---|---|---|
| `FC_AddKeyValueToJSON` | `(i_sKeyToAdd: STRING(255), i_sValueToAdd: STRING(255)) : BOOL` | Queues a key-value pair into internal buffer (`GVL_thingsboard`) |
| `FC_CreateJSON` | `() : STRING(255)` | Flushes buffer into a JSON string and resets the counter |

The internal `GVL_thingsboard` buffer holds up to 1000 key-value pairs (`ars_key[]`, `ars_value[]`).

---

## Constraints

| Constraint | Impact |
|---|---|
| Payload max **255 chars** | Split GVL data across multiple publish calls grouped by topic |
| **No TLS** (plain TCP only) | Use ThingsBoard port **1883**; do not use 8883 |
| **QoS 0 only** (at-most-once) | Acceptable for real-time telemetry; no guaranteed delivery |
| **Edge-triggered** publish | Pulse `i_xPublish := TRUE` for one scan, then set to FALSE |
| **One subscribe topic** per FB instance | Use separate `FB_MQTTClient` instances for publish and subscribe |

---

## Phase 1 — ThingsBoard Cloud Setup

### 1.1 Create Account

Sign up at `thingsboard.cloud`. The Community (free) tier supports up to 30 devices and MQTT access on port 1883.

### 1.2 Create Devices

| Device Name | Device ID | Access Token |
|---|---|---|
| `PLC_Gateway` | `10264160-4d24-11f1-8db5-c3197a5d8b3d` | `5FT2jeSK3hla6ZWBnrQU` |
| `MES_Monitor` | `10eee890-4d24-11f1-aa03-0f0d95b4aecc` | `k46vqnDJEI3ZFKRcABhU` |
| `ERP_Monitor` | `128a2200-4d24-11f1-aa03-0f0d95b4aecc` | `dUJyNXoIX3UXQGN4QAtM` |

The Access Token for each device is used as `i_sUsername` in `FB_MQTTClient` (password left empty).

### 1.3 ThingsBoard MQTT Topics

| Direction | Topic | Used by |
|---|---|---|
| PLC → ThingsBoard | `v1/devices/me/telemetry` | `FB_MQTTClient` publish |
| PLC → ThingsBoard | `v1/devices/me/attributes` | Optional static attributes |
| ThingsBoard → PLC | `v1/devices/me/rpc/request/+` | `FB_MQTTClient` subscribe |
| PLC → ThingsBoard (RPC reply) | `v1/devices/me/rpc/response/<id>` | Optional acknowledgement |

---

## Phase 2 — CODESYS PLC Implementation

### 2.1 Add Library to Project

1. Open `PLC/PLC.project` in CODESYS IDE
2. Navigate to **Library Manager** in the project tree
3. Click **Add Library → Browse** and select `~/Downloads/MQTT Library.library`
4. Confirm it appears in the library list alongside `Standard` and `SysSocket`

The ready-to-paste code for steps 2.2 and 2.3 is in:
- `PLC/GVL_MQTT.iecst` — paste into a new GVL named `GVL_MQTT`
- `PLC/PRG_MQTT.iecst` — paste into a new Program named `PRG_MQTT`

### 2.2 Global Variable List — GVL_MQTT

Create a new GVL named `GVL_MQTT`:

```iecst
VAR_GLOBAL
    // Publisher — sends PLC I/O telemetry to ThingsBoard
    fbMQTT_Pub          : FB_MQTTClient;

    // Subscriber — receives RPC commands from ThingsBoard
    fbMQTT_Sub          : FB_MQTTClient;

    // Publish timer
    tPublishTimer       : TON;

    // Payload groups (255-char limit per publish)
    sPayload_Inputs     : STRING(255);
    sPayload_UnloadReq  : STRING(255);
    sPayload_UnloadMat  : STRING(255);

    // RPC command handling
    sRPCMessage         : STRING(1024);
    bNewRPC             : BOOL;
END_VAR
```

### 2.3 Program — PRG_MQTT

Add a new program `PRG_MQTT` and call it from the main task (same task as `PRG_Main`):

```iecst
// ── Publisher configuration (set every scan) ──────────────────────────
fbMQTT_Pub.i_xEnable        := TRUE;
fbMQTT_Pub.i_sBrokerAddress := 'thingsboard.cloud';
fbMQTT_Pub.i_uiPort         := 1883;
fbMQTT_Pub.i_sUsername      := '5FT2jeSK3hla6ZWBnrQU';
fbMQTT_Pub.i_sPassword      := '';
fbMQTT_Pub.i_sClientID      := 'codesys-plc-pub';
fbMQTT_Pub.i_sTopicPublish  := 'v1/devices/me/telemetry';
fbMQTT_Pub.i_xRetain        := FALSE;
fbMQTT_Pub.i_xAutoReconnect := TRUE;

// ── Subscriber configuration ──────────────────────────────────────────
fbMQTT_Sub.i_xEnable         := TRUE;
fbMQTT_Sub.i_sBrokerAddress  := 'thingsboard.cloud';
fbMQTT_Sub.i_uiPort          := 1883;
fbMQTT_Sub.i_sUsername       := '5FT2jeSK3hla6ZWBnrQU';
fbMQTT_Sub.i_sPassword       := '';
fbMQTT_Sub.i_sClientID       := 'codesys-plc-sub';
fbMQTT_Sub.i_sTopicSubscribe := 'v1/devices/me/rpc/request/+';
fbMQTT_Sub.i_xSubscribe      := TRUE;
fbMQTT_Sub.i_xAutoReconnect  := TRUE;

// ── Publish telemetry on 2-second timer ───────────────────────────────
tPublishTimer(IN := TRUE, PT := T#2S);

IF tPublishTimer.Q THEN
    tPublishTimer(IN := FALSE); // reset

    // Group 1: Input line signals
    FC_AddKeyValueToJSON('create_piece_I1', BOOL_TO_STRING(GVL.Create_Piece_I1));
    FC_AddKeyValueToJSON('create_piece_I2', BOOL_TO_STRING(GVL.Create_Piece_I2));
    FC_AddKeyValueToJSON('create_piece_I3', BOOL_TO_STRING(GVL.Create_Piece_I3));
    FC_AddKeyValueToJSON('create_piece_I4', BOOL_TO_STRING(GVL.Create_Piece_I4));
    FC_AddKeyValueToJSON('piece_material_I1', INT_TO_STRING(GVL.piece_material_I1));
    FC_AddKeyValueToJSON('piece_material_I2', INT_TO_STRING(GVL.piece_material_I2));
    FC_AddKeyValueToJSON('piece_material_I3', INT_TO_STRING(GVL.piece_material_I3));
    FC_AddKeyValueToJSON('piece_material_I4', INT_TO_STRING(GVL.piece_material_I4));
    fbMQTT_Pub.i_sPayload  := FC_CreateJSON();
    fbMQTT_Pub.i_xPublish  := TRUE;
    fbMQTT_Pub();
    fbMQTT_Pub.i_xPublish  := FALSE;

    // Group 2: Unload request signals (U1–U10)
    FC_AddKeyValueToJSON('unload_req_U1',  BOOL_TO_STRING(GVL.Unload_Req_U1));
    FC_AddKeyValueToJSON('unload_req_U2',  BOOL_TO_STRING(GVL.Unload_Req_U2));
    FC_AddKeyValueToJSON('unload_req_U3',  BOOL_TO_STRING(GVL.Unload_Req_U3));
    FC_AddKeyValueToJSON('unload_req_U4',  BOOL_TO_STRING(GVL.Unload_Req_U4));
    FC_AddKeyValueToJSON('unload_req_U5',  BOOL_TO_STRING(GVL.Unload_Req_U5));
    FC_AddKeyValueToJSON('unload_req_U6',  BOOL_TO_STRING(GVL.Unload_Req_U6));
    FC_AddKeyValueToJSON('unload_req_U7',  BOOL_TO_STRING(GVL.Unload_Req_U7));
    FC_AddKeyValueToJSON('unload_req_U8',  BOOL_TO_STRING(GVL.Unload_Req_U8));
    FC_AddKeyValueToJSON('unload_req_U9',  BOOL_TO_STRING(GVL.Unload_Req_U9));
    FC_AddKeyValueToJSON('unload_req_U10', BOOL_TO_STRING(GVL.Unload_Req_U10));
    fbMQTT_Pub.i_sPayload  := FC_CreateJSON();
    fbMQTT_Pub.i_xPublish  := TRUE;
    fbMQTT_Pub();
    fbMQTT_Pub.i_xPublish  := FALSE;

    // Group 3: Unload material type per dock (U1–U10) — correct variable: Unload_Type_U*
    FC_AddKeyValueToJSON('unload_type_U1',  UINT_TO_STRING(GVL.Unload_Type_U1));
    FC_AddKeyValueToJSON('unload_type_U2',  UINT_TO_STRING(GVL.Unload_Type_U2));
    FC_AddKeyValueToJSON('unload_type_U3',  UINT_TO_STRING(GVL.Unload_Type_U3));
    FC_AddKeyValueToJSON('unload_type_U4',  UINT_TO_STRING(GVL.Unload_Type_U4));
    FC_AddKeyValueToJSON('unload_type_U5',  UINT_TO_STRING(GVL.Unload_Type_U5));
    FC_AddKeyValueToJSON('unload_type_U6',  UINT_TO_STRING(GVL.Unload_Type_U6));
    FC_AddKeyValueToJSON('unload_type_U7',  UINT_TO_STRING(GVL.Unload_Type_U7));
    FC_AddKeyValueToJSON('unload_type_U8',  UINT_TO_STRING(GVL.Unload_Type_U8));
    FC_AddKeyValueToJSON('unload_type_U9',  UINT_TO_STRING(GVL.Unload_Type_U9));
    FC_AddKeyValueToJSON('unload_type_U10', UINT_TO_STRING(GVL.Unload_Type_U10));
    fbMQTT_Pub.i_sPayload  := FC_CreateJSON();
    fbMQTT_Pub.i_xPublish  := TRUE;
    fbMQTT_Pub();
    fbMQTT_Pub.i_xPublish  := FALSE;

    // Group 4: Warehouse counts
    FC_AddKeyValueToJSON('W1_count', UINT_TO_STRING(GVL.W1_Count));
    FC_AddKeyValueToJSON('W2_count', UINT_TO_STRING(GVL.W2_Count));
    fbMQTT_Pub.i_sPayload  := FC_CreateJSON();
    fbMQTT_Pub.i_xPublish  := TRUE;
    fbMQTT_Pub();
    fbMQTT_Pub.i_xPublish  := FALSE;
END_IF

// ── Call subscriber FB every scan ─────────────────────────────────────
fbMQTT_Sub();

// ── Handle incoming RPC commands ──────────────────────────────────────
IF fbMQTT_Sub.q_xReceivedMessageNotification THEN
    sRPCMessage := fbMQTT_Sub.q_sLastReceivedMessage;
    bNewRPC     := TRUE;
    // Parse sRPCMessage (JSON) and act:
    // e.g. {"method":"create_piece","params":{"line":1,"material":2}}
    // → pulse GVL.Create_Piece_I1 := TRUE for one scan cycle
END_IF
```

### 2.4 Payload Groups and 255-char Budget

Each `FC_CreateJSON()` call produces at most:
- 8 bool/int key-value pairs → approx. 200 chars including keys and JSON syntax
- Stay within budget by keeping each group to 8–10 short keys

| Group | Keys published | Approx. chars |
|---|---|---|
| Input lines | `create_piece_I1..I4`, `piece_material_I1..I4` | ~150 |
| Unload requests | `unload_req_U1..U10` | ~180 |
| Unload types | `unload_type_U1..U10` | ~190 |
| Warehouse | `W1_count`, `W2_count` | ~50 |

### 2.5 Diagnostic Monitoring

Monitor `fbMQTT_Pub.q_sDiagMsg` and `fbMQTT_Pub.q_udiState` in the CODESYS watch window during commissioning. Key state numbers:

| `q_udiState` | Meaning |
|---|---|
| `0` | Waiting for enable |
| `5` | Creating TCP socket |
| `10` | Connecting to TCP server |
| `15–30` | MQTT CONNECT handshake |
| `40` | Waiting for CONNACK |
| `60` | Connected — ready to publish/subscribe |
| `65–67` | Subscribe flow (SUBSCRIBE → SUBACK) |
| `70–80` | Publish flow |
| `90` | Disconnecting / closing socket |

---

## Phase 3 — Python MQTT Publisher (MES/ERP Stats)

The PLC handles its own I/O data. Python only needs to publish PostgreSQL statistics for `MES_Monitor` and `ERP_Monitor`.

### File: `mqtt_bridge/mqtt_publisher.py`

```python
import time
import json
import paho.mqtt.client as mqtt
import psycopg2

TB_HOST   = "thingsboard.cloud"
TB_PORT   = 1883
MES_TOKEN = "k46vqnDJEI3ZFKRcABhU"
ERP_TOKEN = "dUJyNXoIX3UXQGN4QAtM"
DB_DSN    = "postgresql://iind_user:IIND20266@localhost:5000/erp_db"
INTERVAL  = 5  # seconds

def fetch_mes_stats(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT machine_id,
                   total_operating_sec,
                   tool_changes,
                   pieces_processed
            FROM machine_stats
        """)
        rows = cur.fetchall()
    payload = {}
    for machine_id, op_sec, tool_changes, pieces in rows:
        key = machine_id.lower().replace(" ", "_")
        payload[f"{key}_operating_sec"]   = op_sec
        payload[f"{key}_occupation_pct"]  = round(op_sec / 28800 * 100, 1)
        payload[f"{key}_tool_changes"]    = tool_changes
        payload[f"{key}_pieces_processed"] = pieces
    return payload

def fetch_erp_stats(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT current_day FROM simulation_state LIMIT 1")
        day = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'Done'")
        done = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM orders WHERE status = 'In Progress'")
        in_prog = cur.fetchone()[0]
    return {
        "simulation_day":      day,
        "orders_total":        total,
        "orders_done":         done,
        "orders_in_progress":  in_prog,
        "orders_pending":      total - done - in_prog,
    }

def publish(token, payload):
    client = mqtt.Client()
    client.username_pw_set(token, "")
    client.connect(TB_HOST, TB_PORT, keepalive=60)
    client.publish("v1/devices/me/telemetry", json.dumps(payload))
    client.disconnect()

def main():
    conn = psycopg2.connect(DB_DSN)
    while True:
        try:
            publish(MES_TOKEN, fetch_mes_stats(conn))
            publish(ERP_TOKEN, fetch_erp_stats(conn))
        except Exception as e:
            print(f"[MQTT Publisher] Error: {e}")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
```

### Dependencies

Add to `requirements.txt`:
```
paho-mqtt>=2.0
```

---

## Phase 4 — ThingsBoard Dashboard Configuration

Create a dashboard named **"IIND Factory Floor"** in the ThingsBoard UI using drag-and-drop widgets.

### Suggested Widgets

| Widget Type | Data Source | Keys | Label |
|---|---|---|---|
| Value card | `ERP_Monitor` | `simulation_day` | Simulation Day |
| Value cards row | `ERP_Monitor` | `orders_total`, `orders_done`, `orders_in_progress` | Order KPIs |
| Bar chart | `MES_Monitor` | `*_occupation_pct` | Machine Occupation % |
| Table | `MES_Monitor` | `*_tool_changes`, `*_pieces_processed` | Machine Statistics |
| Bar chart | `MES_Monitor` | `dock_U*_pieces` | Unloading Dock Output |
| Boolean indicator grid | `PLC_Gateway` | `unload_req_U1..U10` | Unload Requests Live |
| Boolean indicator grid | `PLC_Gateway` | `create_piece_I1..I4` | Input Lines Live |
| RPC button | `PLC_Gateway` | method: `create_piece` | Manual Piece Trigger |

---

## Phase 5 — Startup Order

```
1. PostgreSQL (already running on port 5000)
2. CODESYS + Shop Floor Simulator (sfs.jar, Modbus TCP on port 5502)
3. python ERP/erp_server.py + ERP/erp_dispatcher.py
4. python MES/mes_service.py
5. python mqtt_bridge/mqtt_publisher.py       ← new
6. (Optional) Streamlit dashboards on :8501 / :8502
```

---

## Data Flow Summary

```
GVL.Unload_Req_U1..U10     ──┐
GVL.piece_material_U1..U10 ──┤  FB_MQTTClient (PRG_MQTT)
GVL.Create_Piece_I1..I4    ──┘       │
                                      │  MQTT telemetry (port 1883)
PostgreSQL machine_stats    ──┐       ▼
PostgreSQL orders           ──┤  mqtt_publisher.py
PostgreSQL simulation_state ──┘       │
                                      │  MQTT telemetry (port 1883)
                                      ▼
                              ThingsBoard Cloud
                                      │
                                      ▼
                           "IIND Factory Floor" Dashboard
                                      │
                              RPC commands (optional)
                                      │
                                      ▼
                              FB_MQTTClient (PRG_MQTT)
                                      │
                                      ▼
                          GVL.Create_Piece_I1 (pulse)
```

---

## Open Items

- [x] Copy `PLC_Gateway`, `MES_Monitor`, `ERP_Monitor` access tokens from ThingsBoard and substitute placeholders above
- [ ] Verify PLC network allows outbound TCP to `thingsboard.cloud:1883`
- [x] Confirm exact GVL variable names match what is declared in `PLC.project`
- [ ] Decide whether RPC command handling (cloud → PLC write) is in scope
- [ ] Test payload length for each group stays under 255 chars with real variable names
