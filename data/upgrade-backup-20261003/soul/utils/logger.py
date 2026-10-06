from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler

class JSONFormatter(logging.Formatter):
    def format(self, record):
        value = {"time": self.formatTime(record), "level": record.levelname,
                 "event": record.getMessage()}
        if record.exc_info:
            value["exception"] = self.formatException(record.exc_info)
        return json.dumps(value)

class RedactingFormatter(JSONFormatter):
    def __init__(self, secret: str):
        super().__init__()
        self.secret = secret

    def format(self, record):
        result = super().format(record)
        return result.replace(self.secret, "[REDACTED]") if self.secret else result

def setup_logging(directory, debug=False, secret=""):
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("soul")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    handler = RotatingFileHandler(directory / "soul.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(RedactingFormatter(secret))
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger
