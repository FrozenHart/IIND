import asyncio

from mes_logger import setup_logger
from mes_service import run_mes_loop

logger = setup_logger("MES")


def start_mes_server():
    logger.info("Communication path: ERP database -> MES service -> PLC.")
    try:
        asyncio.run(run_mes_loop())
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutdown requested by user.")


if __name__ == "__main__":
    start_mes_server()
