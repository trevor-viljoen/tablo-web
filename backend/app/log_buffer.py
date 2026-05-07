"""In-memory ring buffer for recent log lines used by the debug report."""

import logging
from collections import deque

recent_logs: deque[str] = deque(maxlen=200)


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            recent_logs.append(self.format(record))
        except Exception:
            pass


def install() -> None:
    handler = _BufferHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
