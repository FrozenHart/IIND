import asyncio
from asyncua import Client, ua

BASE_NODE_PATH = "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL"

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

        self.create_piece = {
            f"I{i}": self._node(f"Create_Piece_I{i}")
            for i in range(1, 6)
        }
        self.piece_material_input = {
            f"I{i}": self._node(f"piece_material_I{i}")
            for i in range(1, 6)
        }
        self.unload_req = {
            f"U{i}": self._node(f"Unload_Req_U{i}")
            for i in range(1, 11)
        }
        self.piece_material_unload = {
            f"U{i}": self._node(f"piece_material_U{i}")
            for i in range(1, 11)
        }

    def _node(self, symbol):
        return self.client.get_node(f"{BASE_NODE_PATH}.{symbol}")

    async def pulse_create_piece(self, input_line, material_id):
        if input_line not in self.create_piece or input_line not in self.piece_material_input:
            raise ValueError(f"Unknown input line: {input_line}")

        await self.piece_material_input[input_line].write_value(
            ua.Variant(int(material_id), ua.VariantType.UInt16)
        )
        await self.create_piece[input_line].write_value(
            ua.Variant(True, ua.VariantType.Boolean)
        )
        await asyncio.sleep(0.05)
        await self.create_piece[input_line].write_value(
            ua.Variant(False, ua.VariantType.Boolean)
        )


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
                req_value = await symbol_map.unload_req[key].read_value()
                material_value = await symbol_map.piece_material_unload[key].read_value()
                snapshot[key] = {
                    "requested": bool(req_value),
                    "material": int(material_value),
                }
    except Exception as exc:
        print(f"[PLC] Unable to read unloading snapshot: {exc}")

    return snapshot


if __name__ == "__main__":
    asyncio.run(send_to_plc("M1a", "T1", "START", operations_count=1))
