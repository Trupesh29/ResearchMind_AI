import logging
import sys


class StructuredFormatter(logging.Formatter):
    """
    Format logs with timestamp, level, logger name, message, and optional request_id.
    """

    def format(self, record: logging.LogRecord) -> str:
        base = f"[{self.formatTime(record, '%Y-%m-%d %H:%M:%S')}] [{record.levelname}] [{record.name}]"
        request_id = getattr(record, "request_id", None)
        if request_id:
            base += f" [req:{request_id}]"
        base += f" {record.getMessage()}"
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"
        return base


def setup_logging(log_level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(log_level)

    # Avoid duplicate handlers
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        root.addHandler(handler)
    else:
        for handler in root.handlers:
            handler.setFormatter(StructuredFormatter())
