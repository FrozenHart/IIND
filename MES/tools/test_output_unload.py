import asyncio
import logging

from asyncua import Client, ua

PLC_URL = "opc.tcp://127.0.0.1:4840"

NAMESPACE_CANDIDATES = [4, 3, 2]
NODE_PATH_ROOTS = [
    "|var|CODESYS Control Win V3 x64.Application.PLC_PRG",
    "|var|CODESYS Control Win V3.Application.PLC_PRG",
    "|var|CODESYS Control Win V3 x64.Application.GVL",
    "|var|CODESYS Control Win V3.Application.GVL",
]

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


async def resolve_node(client, symbol):
    for root in NODE_PATH_ROOTS:
        for ns in NAMESPACE_CANDIDATES:
            node_id = f"ns={ns};s={root}.{symbol}"
            node = client.get_node(node_id)
            try:
                await node.read_data_value()
                log.info(f"Resolved via: {node_id}")
                return node
            except Exception:
                pass
    raise RuntimeError(f"Could not resolve symbol '{symbol}'")


async def main():
    async with Client(PLC_URL) as client:
        node = await resolve_node(client, "Output_Unload_O5")

        log.info(f"Current value: {await node.read_value()}")

        log.info("Writing True ...")
        await node.write_value(ua.Variant(True, ua.VariantType.Boolean))
        log.info(f"Read back: {await node.read_value()}")

        await asyncio.sleep(2)

        log.info("Writing False ...")
        await node.write_value(ua.Variant(False, ua.VariantType.Boolean))
        log.info(f"Read back: {await node.read_value()}")

        log.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
