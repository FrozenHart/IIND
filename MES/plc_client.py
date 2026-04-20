import asyncio
from asyncua import Client, ua

NAMESPACE_CANDIDATES = [4, 3, 2]
NODE_PATH_ROOTS = [
    "|var|CODESYS Control Win V3 x64.Application.PLC_PRG",
    "|var|CODESYS Control Win V3.Application.PLC_PRG",
    "|var|CODESYS Control Win V3 x64.Application.GVL",
    "|var|CODESYS Control Win V3.Application.GVL",
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
            node_id = f"{prefix}.{symbol}"
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

    async def read_unload_requested(self, unload_key):
        if not unload_key.startswith("U"):
            raise ValueError(f"Unknown unload key: {unload_key}")

        unload_req_node = await self._resolve_node(f"Unload_Req_{unload_key}")
        piece_material_node = await self._resolve_node(f"piece_material_{unload_key}")
        req_value = await unload_req_node.read_value()
        material_value = await piece_material_node.read_value()
        return bool(req_value), int(material_value)


async def send_to_plc(machine_id, tool_id, action, operations_count=1):
    url = "opc.tcp://127.0.0.1:4840"
    print(f"[PLC] Attempting connection to OPC-UA server at {url}.")

    try:
        async with Client(url=url) as client:
            print("[PLC] Connection established successfully.")

            try:
                symbol_map = PLCSymbolMap(client)
                input_line = MACHINE_TO_INPUT.get(machine_id)
                material_id = TOOL_TO_MATERIAL.get(tool_id)

                if action != "START":
                    print(f"[PLC] Unsupported action for mapped PLC flow: {action}.")
                    return False
                if not input_line:
                    print(f"[PLC] No input-line mapping found for machine {machine_id}.")
                    return False
                if material_id is None:
                    print(f"[PLC] Tool {tool_id} is not a raw transformation tool. Skipping create-piece pulse.")
                    return False

                for _ in range(max(1, int(operations_count))):
                    await symbol_map.pulse_create_piece(input_line, material_id)

                print(
                    "[PLC] Dispatch completed via mapped variables: "
                    f"Create_Piece_{input_line}, piece_material_{input_line}={material_id}, "
                    f"operations={max(1, int(operations_count))}."
                )
                return True

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


if __name__ == "__main__":
    asyncio.run(send_to_plc("M1a", "T1", "START", operations_count=1))
