import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    for logger_name in ("httpx", "httpcore", "postgrest", "supabase"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)