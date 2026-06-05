import argparse
import subprocess
import sys
from pathlib import Path

from mes_logger import setup_logger

BASE_DIR = Path(__file__).resolve().parent

LOGGER = setup_logger("MES-LAUNCHER", console_only=True)


def _spawn(cmd, name):
    LOGGER.info("Starting %s: %s", name, " ".join(str(c) for c in cmd))
    return subprocess.Popen(cmd)


def _streamlit_cmd(script_path, port):
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(script_path),
        "--server.port",
        str(port),
    ]


def run_server():
    subprocess.run([sys.executable, str(BASE_DIR / "mes_server.py")], check=False)


def run_service():
    subprocess.run([sys.executable, str(BASE_DIR / "mes_service.py")], check=False)


def run_monitor():
    LOGGER.info("MES dashboard available at: http://localhost:8502")
    subprocess.run(_streamlit_cmd(BASE_DIR / "mes_monitor.py", 8502), check=False)


def run_all():
    processes = [
        _spawn([sys.executable, str(BASE_DIR / "mes_server.py")], "MES Server"),
        _spawn(_streamlit_cmd(BASE_DIR / "mes_monitor.py", 8502), "MES Dashboard"),
    ]
    LOGGER.info("MES full component started (server + dashboard).")
    LOGGER.info("Press Ctrl+C to stop all MES processes.")
    LOGGER.info("Open MES dashboard manually at: http://localhost:8502")
    try:
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        LOGGER.warning("Shutdown signal received. Terminating MES processes...")
        for proc in processes:
            proc.terminate()
        for proc in processes:
            proc.wait()
        LOGGER.info("MES processes stopped cleanly.")


def main():
    parser = argparse.ArgumentParser(description="Run MES programs")
    parser.add_argument(
        "--mode",
        choices=["server", "service", "monitor", "all"],
        default="all",
        help="MES component to run (all starts server + dashboard)",
    )
    args = parser.parse_args()

    if args.mode == "server":
        run_server()
    elif args.mode == "service":
        run_service()
    elif args.mode == "monitor":
        run_monitor()
    else:
        run_all()


if __name__ == "__main__":
    main()
