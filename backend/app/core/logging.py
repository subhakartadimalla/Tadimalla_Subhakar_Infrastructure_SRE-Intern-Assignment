from __future__ import annotations

import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger


class ServiceFilter(logging.Filter):
    def __init__(self, service: str):
        super().__init__()
        self._service = service

    def filter(self, record: logging.LogRecord) -> bool:
        # Inject `service` into every structured log line.
        setattr(record, "service", self._service)
        return True


def configure_logging(level: str, *, service: str = "ims-backend") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ServiceFilter(service))
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(service)s %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

