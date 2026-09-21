import logging
import sys

def setup_logging():
    """Configure logging to stdout at INFO level.

    Uses a timestamped format and raises ``uvicorn.access`` to WARNING so
    individual requests are not logged.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """Return the logger for a module.

    Args:
        name: Logger name, usually the module's ``__name__``.

    Returns:
        The stdlib logger registered under that name.
    """
    return logging.getLogger(name)
