import asyncio

from mes_service import run_mes_loop


def start_mes_server():
    print("[MES] Communication path: ERP database -> MES service -> PLC.")
    try:
        asyncio.run(run_mes_loop())
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("[MES] Shutdown requested by user.")


if __name__ == "__main__":
    start_mes_server()
