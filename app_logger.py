"""Application logging helpers."""

import logging
import os
from datetime import datetime
from sys import stdout

from azure.core.pipeline.policies import HttpLoggingPolicy


def setup_logger(name="my-app", log_dir="./logs", log_level=logging.DEBUG):
    """Create a file and console logger with Azure SDK request logging disabled."""
    os.makedirs(log_dir, exist_ok=True)
    log_filename = datetime.now().strftime(f"{name}_%Y-%m-%d_%H-%M-%S.log")
    log_path = os.path.join(log_dir, log_filename)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    logger.handlers = []

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    if file_handler not in logger.handlers:
        logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(stdout)
    console_handler.setFormatter(formatter)
    if console_handler not in logger.handlers:
        logger.addHandler(console_handler)

    for logger_name in (
        "llama_index",
        "llama_index.agent",
        "llama_index.tools.retriever",
        "llama_index.agent.function_calling",
    ):
        logging.getLogger(logger_name).setLevel(logging.INFO)
    for logger_name in (
        "llama_index.vector_stores",
        "llama_index.storage",
        "openai",
        "httpx",
        "azure",
        "azure.core.pipeline.policies.http_logging_policy",
    ):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    http_logging_policy = HttpLoggingPolicy()
    http_logging_policy.allowed_header_names = set()
    http_logging_policy.allowed_query_params = set()

    return logger, log_filename


def filter_error_logs(input_file, output_file_name="Error_log", logger=None):
    """Copy ERROR lines from a log file into a timestamped output file."""
    logger = logger or logging.getLogger()
    search_keyword = "ERROR"
    output_file = datetime.now().strftime(f"{output_file_name}_%Y-%m-%d_%H-%M-%S.log")
    try:
        with open(f"../logs/{input_file}", encoding="utf-8", errors="ignore") as infile, open(
            f"../logs/{output_file}", "w"
        ) as outfile:
            for line in infile:
                if search_keyword in line.upper():
                    outfile.write(line)
        logger.info(f"Filtering complete. Errors saved to {output_file}")
    except FileNotFoundError:
        logger.error("The source log file was not found.")
    except Exception as exc:
        logger.error(f"An error occurred: {exc}")
