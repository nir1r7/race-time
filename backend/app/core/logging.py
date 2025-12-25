import logging
import json
from datetime import datetime, UTC

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "level": record.levelname,
            "message": record.getMessage(),
            "time": datetime.now(UTC).isoformat()
        }

        if hasattr(record, "extra"):
            log.update(record.extra)

        return json.dumps(log)
    
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    if not logger.handlers:
        logger.addHandler(handler)

    return logger;