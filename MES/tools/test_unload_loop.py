import asyncio
import logging
import sys

sys.path.insert(0, r"C:\Users\Bruno Esteves\Desktop\IIND\project\Code\iind\MES")

from plc_client import (
    send_to_plc,
    pulse_unload_request,
    read_warehouse_counts,
    read_conveyor_recv,
    read_output_conveyor_empty,
    write_output_unload,
    send_machine_command,
    confirm_machine_command,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

MACHINES_U2 = ["M1a", "M1b", "M1c"]
INPUT_LINES = ["I1", "I2", "I3", "I4", "I5"]
TOOL_WOOD = "T3"

PASS_THRU_CMD = {
    "action_type": 0,
    "process_ms": 0,
    "target_id": 0,
    "needed_tool_slot": 0,
}


async def wait_recv(conv_id, target, timeout_s=30.0, poll_s=0.2):
    start = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start) < timeout_s:
        val = await read_conveyor_recv(conv_id)
        if val == target:
            return True
        await asyncio.sleep(poll_s)
    log.error(f"Timeout waiting for {conv_id}.recv_i == {target}")
    return False


async def run_cycle():
    log.info("=== CYCLE START ===")

    # ---- Phase 1: create 5 raw wood pieces ----
    for i, inp in enumerate(INPUT_LINES):
        log.info(f"Creating piece {i+1}/5 on {inp} ...")
        ok = await send_to_plc("M1a", TOOL_WOOD, "CREATE", input_line=inp)
        if not ok:
            log.error(f"CREATE failed on {inp}")
            return
        loading_conv = f"L{i + 6}"
        log.info(f"  Waiting for {loading_conv}.recv_i ...")
        arrived = await wait_recv(loading_conv, True)
        if not arrived:
            log.error(f"Piece never arrived on {loading_conv}")
            return
        log.info(f"  Piece confirmed on {loading_conv}")

    log.info("All 5 pieces created. Processing through U2 ...")

    # ---- Phase 2: pass each piece through cell U2 to W2 ----
    for i in range(5):
        log.info(f"Processing piece {i+1}/5 through U2 ...")

        free = await wait_recv("L2", False)
        if not free:
            log.error("L2 not free")
            return

        for mach in MACHINES_U2:
            await send_machine_command(mach, PASS_THRU_CMD)
            ok = await confirm_machine_command(mach, PASS_THRU_CMD)
            if not ok:
                log.error(f"Machine command failed for {mach}")
                return

        arrived = await wait_recv("L2", True)
        if not arrived:
            log.error("Piece never arrived on L2")
            return

        unload_ok = await pulse_unload_request("U2", 1)
        if not unload_ok:
            log.error("Unload pulse failed")
            return

        log.info(f"  Piece {i+1} sent to W2")

    # ---- Phase 3: ship from W2 to O5 ----
    log.info("=== SHIPPING TO O5 ===")
    for i in range(5):
        log.info(f"Shipping piece {i+1}/5 to O5 ...")
        ok = await pulse_unload_request("U10", 1)
        if not ok:
            log.error(f"Ship pulse failed for piece {i+1}")
            return
        log.info(f"  Piece {i+1} shipped")

    log.info("=== CYCLE DONE ===")


async def main():
    while True:
        cmd = input("\n[R]un cycle  [S]et Output_Unload_O5  [Q]uit\n> ").strip().upper()
        if cmd == "Q":
            break
        elif cmd == "R":
            await run_cycle()
        elif cmd == "S":
            val = input("Toggle O5 unload to (T)rue or (F)alse? ").strip().upper()
            if val == "T":
                await write_output_unload(5, True)
            elif val == "F":
                await write_output_unload(5, False)
            else:
                log.info("Invalid, write True/False by pulse")
                await write_output_unload(5, True)
                await asyncio.sleep(0.5)
                await write_output_unload(5, False)
            empty = await read_output_conveyor_empty(5)
            log.info(f"O5.EMPTY = {empty}")
        else:
            log.info("Unknown command")


if __name__ == "__main__":
    asyncio.run(main())
