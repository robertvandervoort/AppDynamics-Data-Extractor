"""
Lightweight live logger to mirror messages to console and Streamlit UI.

Usage:
    logger = Logger(debug=True, ui_writers=[status.write, ui_append])
    logger.info("Fetching applications...")
"""

from __future__ import annotations

import datetime as _dt
from typing import Callable, List, Optional


class Logger:
    def __init__(self, debug: bool = False, ui_writers: Optional[List[Callable[[str], None]]] = None):
        self.debug_enabled = debug
        self.ui_writers: List[Callable[[str], None]] = ui_writers or []

    def attach_ui_writer(self, writer: Callable[[str], None]) -> None:
        if writer not in self.ui_writers:
            self.ui_writers.append(writer)

    def _emit(self, level: str, message: str) -> None:
        ts = _dt.datetime.now().strftime('%H:%M:%S')
        line = f"[{ts}] {level}: {message}"
        # Console
        print(line)
        # UI sinks
        for writer in self.ui_writers:
            try:
                writer(line)
            except Exception:
                # Avoid breaking main flow due to UI issues
                pass

    def info(self, message: str) -> None:
        self._emit("INFO", message)

    def warn(self, message: str) -> None:
        self._emit("WARN", message)

    def error(self, message: str) -> None:
        self._emit("ERROR", message)

    def debug(self, message: str) -> None:
        if self.debug_enabled:
            self._emit("DEBUG", message)


