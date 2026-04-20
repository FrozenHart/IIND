import asyncio

from mes_service import run_mes_loop


def start_mes_server():
    print("[MES] Database-only execution mode enabled.")
    print("[MES] Communication path: ERP database -> MES service -> PLC.")
    asyncio.run(run_mes_loop())


if __name__ == "__main__":
    start_mes_server()
