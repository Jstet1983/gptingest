from logging.handlers import RotatingFileHandler
import logging

from config import LOG_FILE

logger = logging.getLogger("github_to_gptingester")
logger.setLevel(logging.INFO)

_formatter = logging.Formatter(
    "%(asctime)s %(levelname)-8s %(message)s"
)

fh = RotatingFileHandler(
    LOG_FILE,
    maxBytes=10_000_000,
    backupCount=10
)

fh.setFormatter(_formatter)

sh = logging.StreamHandler()
sh.setFormatter(_formatter)

logger.addHandler(fh)
logger.addHandler(sh)
