import asyncio
import logging
from asyncua import Client, ua

from mes_logger import setup_logger

logger = setup_logger("PLC")

OPC_URL = "opc.tcp://127.0.0.1:4840"

_client = None
_client_lock = None


async def _get_client():
    global _client, _client_lock
    loop = asyncio.get_running_loop()
    if _client_lock is None or getattr(_client_lock, '_loop', None) is not loop:
        _client_lock = asyncio.Lock()

    async with _client_lock:
        if _client is not None:
            try:
                status_node = _client.get_node("ns=0;i=2258")
                await status_node.read_value()
                return _client
            except Exception as e:
                logger.info(f"[PLC] Health check failed: {e}. Forcing reconnect.")
                try:
                    await _client.disconnect()
                except Exception:
                    pass
                _client = None

        _client = Client(url=OPC_URL)
        await asyncio.wait_for(_client.connect(), timeout=5.0)
        return _client


async def close_client():
    global _client
    if _client is not None:
        try:
            await _client.disconnect()
        except Exception:
            pass
        _client = None


NAMESPACE_CANDIDATES = [4, 3, 2]
NODE_PATH_ROOTS = [
    "|var|CODESYS Control Win V3 x64.Application.PLC_PRG",
    "|var|CODESYS Control Win V3.Application.PLC_PRG",
    "|var|CODESYS Control Win V3 x64.Application.GVL",
    "|var|CODESYS Control Win V3.Application.GVL",
    "|var|CODESYS Control Win V3 x64.Application",
    "|var|CODESYS Control Win V3.Application",
]

MACHINE_TO_INPUT = {
    "M1a": "I1",
    "M1b": "I1",
    "M1c": "I1",
    "M2a": "I2",
    "M2b": "I2",
    "M2c": "I2",
    "M3a": "I3",
    "M3b": "I3",
    "M3c": "I3",
    "M4a": "I4",
    "M4b": "I4",
    "M4c": "I4",
}

TOOL_TO_MATERIAL = {
    "T1": 1,
    "T2": 1,
    "T3": 1,
    "T4": 2,
    "T5": 2,
    "T6": 2,
    "T10": 1,
    "T11": 2,
}

MACHINE_TO_CONVEYOR = {
    "M1a": "C6",
    "M1b": "C8",
    "M1c": "C10",
    "M2a": "C11",
    "M2b": "C13",
    "M2c": "C15",
    "M3a": "C16",
    "M3b": "C18",
    "M3c": "C20",
    "M4a": "C21",
    "M4b": "C23",
    "M4c": "C25",
}


class PLCSymbolMap:
    """Maps CODESYS GVL variables exposed in Symbol Configuration."""

    def __init__(self, client):
        self.client = client
        self._node_cache = {}
        self._preferred_prefix = None

    @staticmethod
    def _all_prefixes():
        prefixes = []
        for ns in NAMESPACE_CANDIDATES:
            for root in NODE_PATH_ROOTS:
                prefixes.append(f"ns={ns};s={root}")
        return prefixes

    async def _resolve_node(self, symbol):
        if symbol in self._node_cache:
            return self._node_cache[symbol]

        prefixes = self._all_prefixes()
        if self._preferred_prefix and self._preferred_prefix in prefixes:
            prefixes = [self._preferred_prefix] + [p for p in prefixes if p != self._preferred_prefix]

        last_error = None
        for prefix in prefixes:
            root_suffix = prefix.split(".")[-1]
            candidates = [symbol]
            if root_suffix != "GVL" and not symbol.startswith("GVL."):
                candidates.append(f"GVL.{symbol}")
            if root_suffix != "PLC_PRG" and not symbol.startswith("PLC_PRG."):
                candidates.append(f"PLC_PRG.{symbol}")

            for candidate in candidates:
                node_id = f"{prefix}.{candidate}"
                node = self.client.get_node(node_id)
                try:
                    await node.read_data_value()
                    self._node_cache[symbol] = node
                    self._preferred_prefix = prefix
                    return node
                except Exception as exc:
                    last_error = exc

        raise RuntimeError(
            f"Unable to resolve OPC-UA symbol '{symbol}'. Last error: {last_error}"
        )

    @staticmethod
    async def _write_with_variants(node, variants):
        last_error = None
        for variant in variants:
            try:
                await node.write_value(variant)
                return True
            except Exception as exc:
                last_error = exc
        raise last_error

    async def pulse_create_piece(self, input_line, material_id):
        if not input_line.startswith("I"):
            raise ValueError(f"Unknown input line: {input_line}")

        create_piece_node = await self._resolve_node(f"Create_Piece_{input_line}")
        piece_material_node = await self._resolve_node(f"piece_material_{input_line}")

        await piece_material_node.write_value(
            ua.Variant(int(material_id), ua.VariantType.UInt16)
        )
        await create_piece_node.write_value(
            ua.Variant(True, ua.VariantType.Boolean)
        )
        await asyncio.sleep(0.05)
        await create_piece_node.write_value(
            ua.Variant(False, ua.VariantType.Boolean)
        )

    async def write_tool_configuration(self, tool_map, tool_times):
        for machine_id, tools in tool_map.items():
            if not isinstance(tools, (list, tuple)):
                continue
            if len(tools) < 3:
                tools = list(tools) + [0] * (3 - len(tools))
            else:
                tools = list(tools)[:3]

            for index, tool_id in enumerate(tools):
                tool_node = await self._resolve_node(
                    f"Tool_{machine_id}[{index}]"
                )
                await self._write_with_variants(
                    tool_node,
                    [
                        ua.Variant(int(tool_id), ua.VariantType.Int16),
                        ua.Variant(int(tool_id), ua.VariantType.Int32),
                    ],
                )

        for tool_id, seconds in tool_times.items():
            time_node = await self._resolve_node(
                f"Tool_Time[{int(tool_id)}]"
            )
            await self._write_with_variants(
                time_node,
                [
                    ua.Variant(int(seconds * 1000), ua.VariantType.UInt32),
                    ua.Variant(int(seconds * 1000), ua.VariantType.Int64),
                    ua.Variant(int(seconds), ua.VariantType.UInt32),
                ],
            )

    async def write_machine_command(self, conveyor_id, command):
        action_node = await self._resolve_node(f"{conveyor_id}.Action_Type")
        process_node = await self._resolve_node(f"{conveyor_id}.Process_Time")
        target_node = await self._resolve_node(f"{conveyor_id}.Target_ID")
        needed_tool_node = await self._resolve_node(f"{conveyor_id}.Needed_Tool")
        req_top_node = await self._resolve_node(f"{conveyor_id}.Req_Top_ID")
        req_leg_node = await self._resolve_node(f"{conveyor_id}.Req_Leg_ID")
        req_join_node = await self._resolve_node(f"{conveyor_id}.Req_Join_Tool")

        await self._write_with_variants(
            action_node,
            [
                ua.Variant(int(command["action_type"]), ua.VariantType.UInt16),
                ua.Variant(int(command["action_type"]), ua.VariantType.Int32),
            ],
        )
        await self._write_with_variants(
            process_node,
            [
                ua.Variant(int(command["process_ms"]), ua.VariantType.UInt32),
                ua.Variant(int(command["process_ms"]), ua.VariantType.Int64),
                ua.Variant(int(command["process_ms"] / 1000), ua.VariantType.UInt32),
            ],
        )
        await self._write_with_variants(
            target_node,
            [
                ua.Variant(int(command["target_id"]), ua.VariantType.UInt16),
                ua.Variant(int(command["target_id"]), ua.VariantType.Int32),
            ],
        )
        await self._write_with_variants(
            needed_tool_node,
            [
                ua.Variant(int(command["needed_tool_slot"]), ua.VariantType.Int16),
                ua.Variant(int(command["needed_tool_slot"]), ua.VariantType.Int32),
            ],
        )
        await self._write_with_variants(
            req_top_node,
            [
                ua.Variant(int(command.get("req_top_id", 0)), ua.VariantType.UInt16),
                ua.Variant(int(command.get("req_top_id", 0)), ua.VariantType.Int32),
            ],
        )
        await self._write_with_variants(
            req_leg_node,
            [
                ua.Variant(int(command.get("req_leg_id", 0)), ua.VariantType.UInt16),
                ua.Variant(int(command.get("req_leg_id", 0)), ua.VariantType.Int32),
            ],
        )
        await self._write_with_variants(
            req_join_node,
            [
                ua.Variant(int(command.get("req_join_tool", 0)), ua.VariantType.Int16),
                ua.Variant(int(command.get("req_join_tool", 0)), ua.VariantType.Int32),
            ],
        )

    async def read_machine_command(self, conveyor_id):
        """Read back the current command values from the PLC for a conveyor."""
        action_node = await self._resolve_node(f"{conveyor_id}.Action_Type")
        process_node = await self._resolve_node(f"{conveyor_id}.Process_Time")
        target_node = await self._resolve_node(f"{conveyor_id}.Target_ID")
        needed_tool_node = await self._resolve_node(f"{conveyor_id}.Needed_Tool")
        action_val = int(await action_node.read_value())
        process_val = int(await process_node.read_value())
        target_val = int(await target_node.read_value())
        tool_val = int(await needed_tool_node.read_value())
        return {
            "action_type": action_val,
            "process_ms": process_val,
            "target_id": target_val,
            "needed_tool_slot": tool_val,
        }

    async def read_unload_requested(self, unload_key):
        if not unload_key.startswith("U"):
            raise ValueError(f"Unknown unload key: {unload_key}")

        unload_req_node = await self._resolve_node(f"Unload_Req_{unload_key}")
        req_value = await unload_req_node.read_value()
        return bool(req_value), 0

    async def pulse_unload_request(self, unload_key, material_id=0):
        if not unload_key.startswith("U"):
            raise ValueError(f"Unknown unload key: {unload_key}")

        unload_req_node = await self._resolve_node(f"Unload_Req_{unload_key}")
        unload_type_node = await self._resolve_node(f"Unload_Type_{unload_key}")
        # Give the PLC scan a better chance to observe the pulse.
        await unload_type_node.write_value(
            ua.Variant(int(material_id), ua.VariantType.UInt16)
        )
        await asyncio.sleep(0.05)
        await unload_req_node.write_value(
            ua.Variant(True, ua.VariantType.Boolean)
        )
        read_back = await unload_req_node.read_value()
        logger.info(
            f"[PLC] pulse_unload_request({unload_key}, material={material_id}): "
            f"wrote True, read_back={read_back}"
        )
        await asyncio.sleep(0.20)
        await unload_req_node.write_value(
            ua.Variant(False, ua.VariantType.Boolean)
        )
        read_back2 = await unload_req_node.read_value()
        logger.info(
            f"[PLC] pulse_unload_request({unload_key}, material={material_id}): "
            f"wrote False, read_back={read_back2}"
        )

    async def read_warehouse_snapshot(self):
        w1_node = await self._resolve_node("W1_Count")
        w2_node = await self._resolve_node("W2_Count")
        top_node = await self._resolve_node("WareHouseTop")
        bottom_node = await self._resolve_node("WareHouseBottom")

        w1_count = int(await w1_node.read_value())
        w2_count = int(await w2_node.read_value())
        top_values = await top_node.read_value()
        bottom_values = await bottom_node.read_value()
        return w1_count, w2_count, top_values, bottom_values


async def send_to_plc(machine_id, tool_id, action, operations_count=1, input_line=None):
    try:
        client = await _get_client()
        symbol_map = PLCSymbolMap(client)
        if input_line is None:
            input_line = MACHINE_TO_INPUT.get(machine_id)
        material_id = TOOL_TO_MATERIAL.get(tool_id)

        if action == "CREATE":
            if not input_line:
                logger.info(f"[PLC] No input-line mapping found for machine {machine_id}.")
                return False
            if material_id is None:
                logger.info(
                    f"[PLC] Tool {tool_id} is not a raw transformation tool. "
                    "Skipping create-piece pulse."
                )
                return False

            for _ in range(max(1, int(operations_count))):
                await symbol_map.pulse_create_piece(input_line, material_id)

            logger.info(
                "[PLC] Dispatch completed via mapped variables: "
                f"Create_Piece_{input_line}, piece_material_{input_line}={material_id}, "
                f"operations={max(1, int(operations_count))}."
            )
            return True

        logger.info(f"[PLC] Unsupported action for create-piece flow: {action}.")
        return False
    except Exception as exc:
        logger.info(f"[PLC] Failed to write to OPC-UA node: {exc}")
        return False


async def read_unloading_snapshot():
    """Reads unload request/material nodes U1..U10 for MES statistics."""
    try:
        client = await _get_client()
        symbol_map = PLCSymbolMap(client)
        snapshot = {}
        for i in range(1, 11):
            key = f"U{i}"
            req_value, material_value = await symbol_map.read_unload_requested(key)
            snapshot[key] = {
                "requested": req_value,
                "material": material_value,
            }
        return snapshot
    except Exception as exc:
        logger.info(f"[PLC] Unable to read unloading snapshot: {exc}")
        return {}


async def read_warehouse_counts():
    try:
        client = await _get_client()
        symbol_map = PLCSymbolMap(client)
        w1_node = await symbol_map._resolve_node("W1_Count")
        w2_node = await symbol_map._resolve_node("W2_Count")
        w1_value = await w1_node.read_value()
        w2_value = await w2_node.read_value()
        return int(w1_value), int(w2_value)
    except Exception as exc:
        logger.info(f"[PLC] Unable to read warehouse counts: {exc}")
        return None


async def read_warehouse_snapshot():
    try:
        client = await _get_client()
        symbol_map = PLCSymbolMap(client)
        return await symbol_map.read_warehouse_snapshot()
    except asyncio.CancelledError:
        return None
    except Exception as exc:
        logger.info(f"[PLC] Unable to read warehouse snapshot: {exc}")
        return None


async def pulse_unload_request(unload_key, material_id=0, pulses=1):
    try:
        client = await _get_client()
        symbol_map = PLCSymbolMap(client)
        for _ in range(max(1, int(pulses))):
            await symbol_map.pulse_unload_request(unload_key, material_id)
        return True
    except Exception as exc:
        logger.info(f"[PLC] Unable to pulse unload request {unload_key}: {exc}")
        return False


async def write_tool_configuration(tool_map, tool_times):
    try:
        client = await _get_client()
        symbol_map = PLCSymbolMap(client)
        await symbol_map.write_tool_configuration(tool_map, tool_times)
        return True
    except Exception as exc:
        logger.info(f"[PLC] Unable to write tool configuration: {exc}")
        return False


async def send_machine_command(machine_id, command):
    conveyor_id = MACHINE_TO_CONVEYOR.get(machine_id)
    if not conveyor_id:
        logger.info(f"[PLC] No conveyor mapping found for machine {machine_id}.")
        return False

    try:
        client = await _get_client()
        symbol_map = PLCSymbolMap(client)
        await symbol_map.write_machine_command(conveyor_id, command)
        logger.info(
            f"[PLC] Command sent to {conveyor_id}: action={command['action_type']}, "
            f"tool_slot={command['needed_tool_slot']}, target={command['target_id']}, "
            f"time_ms={command['process_ms']}."
        )
        return True
    except Exception as exc:
        logger.info(f"[PLC] Unable to send machine command: {exc}")
        return False


async def confirm_machine_command(machine_id, command, max_retries=3):
    """Read back key nodes and verify they match the command. Retries on mismatch."""
    conveyor_id = MACHINE_TO_CONVEYOR.get(machine_id)
    if not conveyor_id:
        logger.info(f"[PLC] No conveyor mapping for {machine_id}.")
        return False

    try:
        client = await _get_client()
        symbol_map = PLCSymbolMap(client)
        wanted = {
            "action_type": int(command["action_type"]),
            "process_ms": int(command["process_ms"]),
            "target_id": int(command["target_id"]),
            "needed_tool_slot": int(command["needed_tool_slot"]),
        }

        for attempt in range(1, max_retries + 1):
            await asyncio.sleep(0.1)
            actual = await symbol_map.read_machine_command(conveyor_id)
            ok = (
                actual["action_type"] == wanted["action_type"]
                and actual["target_id"] == wanted["target_id"]
                and actual["needed_tool_slot"] == wanted["needed_tool_slot"]
            )
            logger.info(
                f"[PLC] Confirm {conveyor_id} (attempt {attempt}/{max_retries}): "
                f"Action={actual['action_type']} (wanted={wanted['action_type']}), "
                f"Process={actual['process_ms']}ms (wanted={wanted['process_ms']}), "
                f"Target={actual['target_id']} (wanted={wanted['target_id']}), "
                f"Tool={actual['needed_tool_slot']} (wanted={wanted['needed_tool_slot']}) "
                f"{'OK' if ok else 'MISMATCH'}"
            )
            if ok:
                return True
            logger.info(f"[PLC]   Mismatch on {conveyor_id}, rewriting command (attempt {attempt}/{max_retries})...")
            await symbol_map.write_machine_command(conveyor_id, command)

        return False
    except Exception as exc:
        logger.info(f"[PLC] Unable to confirm {conveyor_id}: {exc}")
        return False


async def read_conveyor_state(conveyor_id):
    try:
        client = await _get_client()
        sm = PLCSymbolMap(client)
        action_node = await sm._resolve_node(f"{conveyor_id}.Action_Type")
        free_node = await sm._resolve_node(f"{conveyor_id}.free_O")
        action_val = int(await action_node.read_value())
        free_val = bool(await free_node.read_value())
        return {"action_type": action_val, "free": free_val}
    except asyncio.CancelledError:
        return None
    except Exception:
        return None


async def read_conveyor_piece_in(conveyor_id):
    try:
        client = await _get_client()
        sm = PLCSymbolMap(client)
        node = await sm._resolve_node(f"{conveyor_id}.Piece_In")
        return int(await node.read_value())
    except asyncio.CancelledError:
        return None
    except Exception:
        return None


async def read_conveyor_recv(conveyor_id):
    """Reads recv_i from a loading conveyor. True when receiving a piece."""
    try:
        client = await _get_client()
        sm = PLCSymbolMap(client)
        node = await sm._resolve_node(f"{conveyor_id}.recv_i")
        return bool(await node.read_value())
    except asyncio.CancelledError:
        return None
    except Exception:
        return None


async def read_conveyor_saved_leg(conveyor_id):
    """Returns (saved_leg1, saved_leg2) UINT values for a conveyor."""
    try:
        client = await _get_client()
        sm = PLCSymbolMap(client)
        leg1_node = await sm._resolve_node(f"{conveyor_id}.Saved_Leg1")
        leg2_node = await sm._resolve_node(f"{conveyor_id}.Saved_Leg2")
        leg1 = int(await leg1_node.read_value())
        leg2 = int(await leg2_node.read_value())
        return leg1, leg2
    except Exception as exc:
        logger.info(f"[PLC] Unable to read {conveyor_id}.Saved_Leg: {exc}")
        return None


async def read_output_conveyor_empty(lane: int):
    """Reads O{lane}.EMPTY via OPC-UA. Returns True when conveyor is empty."""
    try:
        client = await _get_client()
        sm = PLCSymbolMap(client)
        node = await sm._resolve_node(f"O{lane}.EMPTY")
        val = bool(await node.read_value())
        logger.info(f"[PLC] read O{lane}.EMPTY = {val}")
        return val
    except Exception as exc:
        logger.info(f"[PLC] read O{lane}.EMPTY failed: {exc}")
        return None


async def write_output_unload(lane: int, value: bool):
    """Writes Output_Unload_O{lane} = value (level, not pulse)."""
    try:
        client = await _get_client()
        sm = PLCSymbolMap(client)
        node = await sm._resolve_node(f"Output_Unload_O{lane}")
        await node.write_value(ua.Variant(bool(value), ua.VariantType.Boolean))
        read_back = bool(await node.read_value())
        logger.info(f"[PLC] wrote Output_Unload_O{lane}={value}, read_back={read_back}")
        return True
    except Exception as exc:
        logger.info(f"[PLC] write_output_unload(O{lane}) failed: {exc}")
        return False


if __name__ == "__main__":
    asyncio.run(send_to_plc("M1a", "T1", "CREATE", operations_count=1))
