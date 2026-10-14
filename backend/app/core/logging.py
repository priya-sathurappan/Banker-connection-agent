"""Structured JSON logging with correlation ID, datacenter and PII masking."""

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")

_datacenter = "local"


def mask(value: object, visible: int = 4) -> str:
    """Mask an account, routing or check number, keeping the last few characters."""
    text = "" if value is None else str(value)
    if len(text) <= visible:
        return "*" * len(text)
    return "*" * (len(text) - visible) + text[-visible:]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "dc": _datacenter,
            "correlation_id": correlation_id_var.get(),
        }
        extra = getattr(record, "fields", None)
        if extra:
            entry.update(extra)
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str, datacenter: str) -> None:
    global _datacenter
    _datacenter = datacenter
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def log(logger: logging.Logger, msg: str, **fields: object) -> None:
    logger.info(msg, extra={"fields": fields})
