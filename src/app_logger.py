"""Package-safe logging helpers used by the application runtime."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def setup_logger(
    name: str = "agentic-rag",
    log_dir: str | os.PathLike[str] = "./logs",
    log_level: int = logging.INFO,
):
    """Configure an application logger without logging credentials or payloads."""
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    filename = f"{name}_{datetime.now(timezone.utc):%Y-%m-%d_%H-%M-%S}.log"
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler = logging.FileHandler(path / filename, encoding="utf-8")
        console_handler = logging.StreamHandler(sys.stdout)
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger, filename


def filter_error_logs(input_file: str, output_file_name: str = "Error_log") -> None:
    """Write ERROR-level lines from a log file to a sibling output file."""
    source = Path(input_file)
    output = source.with_name(
        f"{output_file_name}_{datetime.now(timezone.utc):%Y-%m-%d_%H-%M-%S}.log"
    )
    with source.open("r", encoding="utf-8", errors="ignore") as infile, output.open(
        "w", encoding="utf-8"
    ) as outfile:
        for line in infile:
            if "ERROR" in line.upper():
                outfile.write(line)
