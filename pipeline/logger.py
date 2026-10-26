import json
import logging
import os
import sys

from pipeline import config


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "step": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "data"):
            log.update(record.data)
        return json.dumps(log)


def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        os.makedirs(config.LOG_DIR, exist_ok=True)
        for handler in (logging.StreamHandler(sys.stdout),
                        logging.FileHandler(os.path.join(config.LOG_DIR, "pipeline.log"))):
            handler.setFormatter(JsonFormatter())
            logger.addHandler(handler)
        logger.setLevel(config.LOG_LEVEL)
        logger.propagate = False
    return logger
