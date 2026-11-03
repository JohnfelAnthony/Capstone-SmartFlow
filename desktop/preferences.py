"""Bounded, non-sensitive desktop presentation preferences."""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path

KEY = re.compile(r"^(smartflow-theme|smartflow-random-count|smartflow-random-palette|smartflow-view-[0-9]{1,12})$")


class DesktopPreferences:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()

    def _read(self):
        if not self.path.exists():
            return {}
        if self.path.stat().st_size > 65536:
            raise ValueError("Desktop preferences file is too large")
        result = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(result, dict) or any(not isinstance(k, str) or not KEY.fullmatch(k) or not isinstance(v, str) or len(v) > 8192 for k, v in result.items()):
            raise ValueError("Desktop preferences file is invalid")
        return result

    def read(self):
        with self.lock:
            return self._read()

    def update(self, key, value):
        if not isinstance(key, str) or not KEY.fullmatch(key) or (value is not None and (not isinstance(value, str) or len(value) > 8192)):
            raise ValueError("Unsupported desktop preference")
        with self.lock:
            values = self._read()
            if value is None:
                values.pop(key, None)
            else:
                values[key] = value
            encoded = json.dumps(values, ensure_ascii=False).encode("utf-8")
            if len(encoded) > 65536:
                raise ValueError("Desktop preferences exceed storage limit")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.parent / (".preferences-" + uuid.uuid4().hex + ".tmp")
            try:
                with temporary.open("xb") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            finally:
                temporary.unlink(missing_ok=True)
