import sys
from loguru import logger

LOG_LEVELS = {
    "TRACE",
    "DEBUG",
    "INFO",
    "SUCCESS",
    "WARNING",
    "ERROR",
    "CRITICAL",
}


def configure_logging(log_level: str = "INFO"):
    log_level = log_level.upper()

    if log_level not in LOG_LEVELS:
        raise ValueError(f"Invalid log level: {log_level}")

    logger.remove()  # remove default handler

    logger.add(
        sys.stderr,
        level=log_level,
        format=(
            #            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level:8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        backtrace=(log_level == "TRACE"),
        diagnose=(log_level == "TRACE"),
    )
