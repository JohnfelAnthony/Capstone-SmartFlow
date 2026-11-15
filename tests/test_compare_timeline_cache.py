"""The disposable playback cache preserves bytes, bounds disk use and owns its cursors."""
import gzip
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from services.compare_timeline_cache import CompareTimelineCache


@pytest.fixture
def cache():
    instance = CompareTimelineCache(max_bytes=200, max_entries=2)
    yield instance
    instance.clear()


def compressed(tmp_path, name, content):
    path = tmp_path / f"{name}.jsonl.gz"
    path.write_bytes(gzip.compress(content))
    return path


def test_cache_preserves_bytes_and_reuses_them_for_random_seeks(tmp_path, cache):
    content = 'first\n{"street":"Dalisay Gante – road"}\nlast\n'.encode()
    path = compressed(tmp_path, "run", content)
    with patch("gzip.open", wraps=gzip.open) as decoder:
        for offset in (20, 0, 12, 0):
            with cache.open(path) as stream:
                stream.seek(offset)
                assert stream.read() == content[offset:]
    assert decoder.call_count == 1


def test_eviction_and_clear_close_temporary_files(tmp_path, cache):
    streams = []
    for name in ("first", "second", "third"):
        with cache.open(compressed(tmp_path, name, b"x" * 40)) as stream:
            streams.append(stream)
    assert streams[0].closed
    assert not streams[1].closed
    cache.clear()
    assert all(stream.closed for stream in streams)


def test_total_disk_budget_evicts_even_below_the_entry_limit(tmp_path):
    cache = CompareTimelineCache(max_bytes=100, max_entries=4)
    try:
        streams = []
        for name in ("first", "second", "third"):
            with cache.open(compressed(tmp_path, name, b"x" * 40)) as stream:
                streams.append(stream)
        assert streams[0].closed
        assert not streams[1].closed
        assert cache._bytes == 80
    finally:
        cache.clear()


def test_changed_artifact_invalidates_the_copy_and_deleted_artifact_is_not_served(tmp_path, cache):
    path = compressed(tmp_path, "run", b"old")
    with cache.open(path) as old:
        assert old.read() == b"old"
    previous = path.stat()
    path.write_bytes(gzip.compress(b"new"))
    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000))
    with cache.open(path) as new:
        assert new.read() == b"new"
    assert old.closed
    path.unlink()
    with pytest.raises(FileNotFoundError), cache.open(path):
        pass


def test_oversize_recording_falls_back_without_repeated_cache_attempts(tmp_path, cache):
    content = b"x" * 101
    path = compressed(tmp_path, "large", content)
    with patch.object(cache, "_decode", wraps=cache._decode) as prepare:
        for _ in range(2):
            with cache.open(path) as stream:
                assert stream.read() == content
    assert prepare.call_count == 1
    assert cache._bytes == 0


def test_unavailable_temp_space_keeps_recording_readable(tmp_path, cache):
    path = compressed(tmp_path, "run", b"recorded")
    with patch("services.compare_timeline_cache.tempfile.TemporaryFile", side_effect=OSError("no space")):
        with cache.open(path) as stream:
            assert stream.read() == b"recorded"


def test_disk_filling_during_a_copy_still_falls_back_and_closes_it(tmp_path, cache):
    path = compressed(tmp_path, "run", b"recorded")
    temporary = tempfile.TemporaryFile()
    class FullDisk:
        def write(self, _chunk):
            raise OSError("disk filled during write")
        def close(self):
            temporary.close()
            raise OSError("buffer flush failed during close")
    with patch("services.compare_timeline_cache.tempfile.TemporaryFile", return_value=FullDisk()):
        with cache.open(path) as stream:
            assert stream.read() == b"recorded"
    assert temporary.closed
    assert cache._bytes == 0


def test_corrupt_gzip_is_not_retained(tmp_path, cache):
    path = tmp_path / "bad.jsonl.gz"
    path.write_bytes(b"invalid gzip")
    with pytest.raises(gzip.BadGzipFile), cache.open(path):
        pass
    assert not cache._entries


def test_parallel_readers_do_not_share_a_moving_cursor(tmp_path, cache):
    content = bytes(range(80))
    path = compressed(tmp_path, "run", content)
    def read_at(offset):
        with cache.open(path) as stream:
            stream.seek(offset)
            return stream.read(5)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(read_at, range(70))) == [content[i:i+5] for i in range(70)]


def test_plain_timeline_reads_directly_without_temporary_copy(tmp_path, cache):
    path = tmp_path / "run.jsonl"
    path.write_bytes(b"plain\n")
    with patch.object(cache, "_decode", side_effect=AssertionError("plain file needs no copy")):
        with cache.open(path) as stream:
            assert stream.read() == b"plain\n"
    assert stream.closed
