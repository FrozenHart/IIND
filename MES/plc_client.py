import asyncio
from asyncua import Client, ua

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
        await unload_type_node.write_value(
            ua.Variant(int(material_id), ua.VariantType.UInt16)
        )
        await unload_req_node.write_value(
            ua.Variant(True, ua.VariantType.Boolean)
        )
        await asyncio.sleep(0.05)
        await unload_req_node.write_value(
            ua.Variant(False, ua.VariantType.Boolean)
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
    url = "opc.tcp://127.0.0.1:4840"

    try:
        async with Client(url=url) as client:
            try:
                symbol_map = PLCSymbolMap(client)
                if input_line is None:
                    input_line = MACHINE_TO_INPUT.get(machine_id)
                material_id = TOOL_TO_MATERIAL.get(tool_id)

                if action == "CREATE":
                    if not input_line:
                        print(f"[PLC] No input-line mapping found for machine {machine_id}.")
                        return False
                    if material_id is None:
                        print(
                            f"[PLC] Tool {tool_id} is not a raw transformation tool. "
                            "Skipping create-piece pulse."
                        )
                        return False

                    for _ in range(max(1, int(operations_count))):
                        await symbol_map.pulse_create_piece(input_line, material_id)

                    print(
                        "[PLC] Dispatch completed via mapped variables: "
                        f"Create_Piece_{input_line}, piece_material_{input_line}={material_id}, "
                        f"operations={max(1, int(operations_count))}."
                    )
                    return True

                print(f"[PLC] Unsupported action for create-piece flow: {action}.")
                return False

            except Exception as exc:
                print(f"[PLC] Failed to write to OPC-UA node: {exc}")
                return False

    except Exception as exc:
        print(f"[PLC] Connection failed. Verify Codesys OPC-UA server status. Error: {exc}")
        return False


async def read_unloading_snapshot():
    """Reads unload request/material nodes U1..U10 for MES statistics."""
    url = "opc.tcp://127.0.0.1:4840"
    snapshot = {}

    try:
        async with Client(url=url) as client:
            symbol_map = PLCSymbolMap(client)
            for i in range(1, 11):
                key = f"U{i}"
                req_value, material_value = await symbol_map.read_unload_requested(key)
                snapshot[key] = {
                    "requested": req_value,
                    "material": material_value,
                }
    except Exception as exc:
        print(f"[PLC] Unable to read unloading snapshot: {exc}")

    return snapshot


async def read_warehouse_counts():
    url = "opc.tcp://127.0.0.1:4840"
    try:
        async with Client(url=url) as client:
            symbol_map = PLCSymbolMap(client)
            w1_node = await symbol_map._resolve_node("W1_Count")
            w2_node = await symbol_map._resolve_node("W2_Count")
            w1_value = await w1_node.read_value()
            w2_value = await w2_node.read_value()
            return int(w1_value), int(w2_value)
    except Exception as exc:
        print(f"[PLC] Unable to read warehouse counts: {exc}")
        return None


async def read_warehouse_snapshot():
    url = "opc.tcp://127.0.0.1:4840"
    try:
        async with Client(url=url) as client:
            symbol_map = PLCSymbolMap(client)
            return await symbol_map.read_warehouse_snapshot()
    except Exception as exc:
        print(f"[PLC] Unable to read warehouse snapshot: {exc}")
        return None


async def pulse_unload_request(unload_key, material_id=0, pulses=1):
    url = "opc.tcp://127.0.0.1:4840"
    try:
        async with Client(url=url) as client:
            symbol_map = PLCSymbolMap(client)
            for _ in range(max(1, int(pulses))):
                await symbol_map.pulse_unload_request(unload_key, material_id)
            return True
    except Exception as exc:
        print(f"[PLC] Unable to pulse unload request {unload_key}: {exc}")
        return False


async def write_tool_configuration(tool_map, tool_times):
    url = "opc.tcp://127.0.0.1:4840"
    try:
        async with Client(url=url) as client:
            symbol_map = PLCSymbolMap(client)
            await symbol_map.write_tool_configuration(tool_map, tool_times)
            return True
    except Exception as exc:
        print(f"[PLC] Unable to write tool configuration: {exc}")
        return False


async def send_machine_command(machine_id, command):
    url = "opc.tcp://127.0.0.1:4840"
    conveyor_id = MACHINE_TO_CONVEYOR.get(machine_id)
    if not conveyor_id:
        print(f"[PLC] No conveyor mapping found for machine {machine_id}.")
        return False

    try:
        async with Client(url=url) as client:
            symbol_map = PLCSymbolMap(client)
            await symbol_map.write_machine_command(conveyor_id, command)
            print(
                f"[PLC] Command sent to {conveyor_id}: action={command['action_type']}, "
                f"tool_slot={command['needed_tool_slot']}, target={command['target_id']}, "
                f"time_ms={command['process_ms']}."
            )
            return True
    except Exception as exc:
        print(f"[PLC] Unable to send machine command: {exc}")
        return False


if __name__ == "__main__":
    asyncio.run(send_to_plc("M1a", "T1", "CREATE", operations_count=1))
