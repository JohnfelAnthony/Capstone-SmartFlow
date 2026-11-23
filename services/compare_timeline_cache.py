"""Bounded, disposable random-access copies of compressed Compare Runs timelines.

Gzip seeking restarts decompression from the beginning on every new request.
Keep decoded bytes on disk, not Python frame objects in memory. Originals remain
authoritative, and changed files invalidate their copy. Large files and hosts
without temporary space retain the ordinary gzip reader.
"""
from __future__ import annotations

import atexit
import gzip
import shutil
import tempfile
import threading
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import BinaryIO


# Same reserve recordings keep free, so a copy never takes the last of the disk from the database.
FREE_SPACE_RESERVE = 256 * 1024 * 1024


def _declared_size(path: Path) -> int:
    """Decoded size from the gzip trailer (modulo 4 GiB), or 0 for a non-gzip file so the reader reports it."""
    with path.open("rb") as stream:
        if stream.read(2) != b"\x1f\x8b":
            return 0
        stream.seek(-4, 2)
        return int.from_bytes(stream.read(4), "little")


class CompareTimelineCache:
    def __init__(self, *, max_bytes: int = 1024 * 1024 * 1024, max_entries: int = 4):
        self.max_bytes = max_bytes
        self.max_entries = max_entries
        self._entries: OrderedDict[tuple[Path, int, int], tuple[BinaryIO | None, int]] = OrderedDict()
        self._bytes = 0
        # A cached file has one cursor. Serialize readers and eviction so a
        # prefetch, chart or seek cannot move/close another request's cursor.
        self._lock = threading.RLock()

    def _remove(self, key: tuple[Path, int, int]) -> None:
        stream, size = self._entries.pop(key)
        self._bytes -= size
        if stream is not None:
            stream.close()

    def clear(self) -> None:
        with self._lock:
            for key in list(self._entries):
                self._remove(key)

    def _decode(self, path: Path) -> tuple[BinaryIO | None, int]:
        expected = _declared_size(path)
        if expected > self.max_bytes // 2 or shutil.disk_usage(tempfile.gettempdir()).free < expected + FREE_SPACE_RESERVE:
            return None, 0
        try:
            copy = tempfile.TemporaryFile(prefix="smartflow-compare-", mode="w+b")
        except OSError:
            return None, 0
        retained = False
        try:
            size = 0
            with gzip.open(path, "rb") as source:
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    # Reserve room for both sides of a comparison. Remember
                    # oversize misses too, instead of trying to cache each tick.
                    if size > self.max_bytes // 2:
                        return None, 0
                    while self._entries and self._bytes + size > self.max_bytes:
                        self._remove(next(iter(self._entries)))
                    try:
                        copy.write(chunk)
                    except OSError:
                        return None, 0
            try:
                copy.seek(0)  # also flushes buffered writes before retaining it
            except OSError:
                return None, 0
            retained = True
            return copy, size
        finally:
            if not retained:
                # A failed buffered write can fail again while closing. The
                # cache is optional, so still let the original reader run.
                with suppress(OSError):
                    copy.close()

    @contextmanager
    def open(self, path: Path) -> Iterator[BinaryIO]:
        if path.suffix != ".gz":
            with path.open("rb") as stream:
                yield stream
            return
        path = path.resolve()
        stat = path.stat()
        key = (path, stat.st_mtime_ns, stat.st_size)
        with self._lock:
            for old_key in list(self._entries):
                if old_key[0] == path and old_key != key:
                    self._remove(old_key)
            if key not in self._entries:
                while self._entries and len(self._entries) >= self.max_entries:
                    self._remove(next(iter(self._entries)))
                self._entries[key] = self._decode(path)
                self._bytes += self._entries[key][1]
            self._entries.move_to_end(key)
            stream, _ = self._entries[key]
            if stream is not None:
                stream.seek(0)
                yield stream
                return
        with gzip.open(path, "rb") as stream:
            yield stream


compare_timeline_cache = CompareTimelineCache()
atexit.register(compare_timeline_cache.clear)
