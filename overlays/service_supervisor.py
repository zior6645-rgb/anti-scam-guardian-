#!/usr/bin/env python3
"""Run the FastAPI service and Telegram long-polling bot as one container service."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s service-supervisor: %(message)s",
)
logger = logging.getLogger("service-supervisor")
_shutdown_requested = False


def _request_shutdown(signum, _frame) -> None:
    global _shutdown_requested
    logger.info("Received signal %s; stopping child services", signum)
    _shutdown_requested = True


def _wait_for_api(process: subprocess.Popen, port: str, timeout_seconds: int = 60) -> bool:
    health_url = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline and not _shutdown_requested:
        if process.poll() is not None:
            logger.error("API process exited during startup with code %s", process.returncode)
            return False
        try:
            with urlopen(health_url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (OSError, URLError):
            time.sleep(1)
    logger.error("API did not become healthy within %s seconds", timeout_seconds)
    return False


def _stop_processes(processes: list[subprocess.Popen]) -> None:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()

    deadline = time.monotonic() + 10
    for process in reversed(processes):
        remaining = max(0.1, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def main() -> int:
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    port = os.getenv("PORT", "8080")
    env = os.environ.copy()
    processes: list[subprocess.Popen] = []

    api_command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        port,
    ]
    bot_command = [sys.executable, "-m", "app.bot_launcher"]

    try:
        logger.info("Starting API service on port %s", port)
        api = subprocess.Popen(api_command, env=env)
        processes.append(api)

        if not _wait_for_api(api, port):
            return 1

        logger.info("API health check passed; starting Telegram bot polling")
        bot = subprocess.Popen(bot_command, env=env)
        processes.append(bot)

        while not _shutdown_requested:
            for name, process in (("API", api), ("Telegram bot", bot)):
                exit_code = process.poll()
                if exit_code is not None:
                    logger.error("%s process exited unexpectedly with code %s", name, exit_code)
                    return 1
            time.sleep(0.5)

        return 0
    except OSError:
        logger.exception("Could not start a child service")
        return 1
    finally:
        _stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
