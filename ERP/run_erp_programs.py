import argparse
import json
import logging
import socket
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("ERP-LAUNCHER")


LOGGER = _setup_logger()


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
    subprocess.run([sys.executable, str(BASE_DIR / "erp_server.py")], check=False)


def run_dispatcher():
    subprocess.run([sys.executable, str(BASE_DIR / "erp_dispatcher.py")], check=False)


def run_dashboard():
    LOGGER.info("ERP dashboard available at: http://localhost:8501")
    subprocess.run(_streamlit_cmd(BASE_DIR / "erp_gui.py", 8501), check=False)


def _send_demo_payload(payload):
    raw = json.dumps(payload).encode("utf-8")
    for attempt in range(1, 11):
        try:
            with socket.create_connection(("127.0.0.1", 6666), timeout=2.0) as conn:
                conn.sendall(raw)
            LOGGER.info("Demo payload sent (OrderID=%s).", payload.get("OrderID"))
            return True
        except OSError as exc:
            LOGGER.warning(
                "ERP order socket not ready yet (attempt %d/10): %s",
                attempt,
                exc,
            )
            time.sleep(1)
    return False


def run_demo_payloads():
    demo_payloads = [
        {
            "name": "Demo Client A",
            "NIF": 123456789,
            "OrderID": 9001,
            "orders": [
                {"type": "RWM", "quantity": 3, "DDate": 4, "Penalty": 2.5},
                {"type": "SMM", "quantity": 2, "DDate": 6, "Penalty": 3.0},
            ],
        },
        {
            "name": "Demo Client B",
            "NIF": 987654321,
            "OrderID": 9002,
            "orders": [
                {"type": "RWW", "quantity": 5, "DDate": 5, "Penalty": 1.5},
            ],
        },
    ]

    LOGGER.info("Sending ERP demo payload set for testing...")
    for payload in demo_payloads:
        if not _send_demo_payload(payload):
            LOGGER.error("Failed to deliver demo payload (OrderID=%s).", payload.get("OrderID"))


def run_all(with_demo=False):
    processes = [
        _spawn([sys.executable, str(BASE_DIR / "erp_server.py")], "ERP Server"),
        _spawn([sys.executable, str(BASE_DIR / "erp_dispatcher.py")], "ERP Dispatcher"),
        _spawn(_streamlit_cmd(BASE_DIR / "erp_gui.py", 8501), "ERP Dashboard"),
    ]

    LOGGER.info("ERP full component started (server + dispatcher + dashboard).")
    LOGGER.info("ERP<->MES path is database-only. Client intake stays on TCP 6666.")

    if with_demo:
        run_demo_payloads()

    LOGGER.info("Press Ctrl+C to stop all ERP processes.")
    LOGGER.info("Open ERP dashboard manually at: http://localhost:8501")
    try:
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        LOGGER.warning("Shutdown signal received. Terminating ERP processes...")
        for proc in processes:
            proc.terminate()
        for proc in processes:
            proc.wait()
        LOGGER.info("ERP processes stopped cleanly.")


def main():
    parser = argparse.ArgumentParser(description="Run ERP programs")
    parser.add_argument(
        "--mode",
        choices=["server", "dispatcher", "dashboard", "all", "demo"],
        default="all",
        help="ERP component to run (demo starts full stack + test payloads)",
    )
    args = parser.parse_args()

    if args.mode == "server":
        run_server()
    elif args.mode == "dispatcher":
        run_dispatcher()
    elif args.mode == "dashboard":
        run_dashboard()
    elif args.mode == "demo":
        run_all(with_demo=True)
    else:
        run_all(with_demo=False)


if __name__ == "__main__":
    main()
