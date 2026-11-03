"""Read PNG/JPEG image dimensions without decoding untrusted pixel data."""
from __future__ import annotations

import struct


def image_dimensions(data: bytes, mime: str) -> tuple[int, int]:
    if mime == "data:image/png;base64":
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[8:16] != b"\x00\x00\x00\rIHDR":
            raise ValueError("Reference PNG has an invalid or missing image header")
        width, height = struct.unpack(">II", data[16:24])
    elif mime == "data:image/jpeg;base64":
        if not data.startswith(b"\xff\xd8"):
            raise ValueError("Reference JPEG has an invalid signature")
        index = 2
        width = height = 0
        while index < len(data):
            if data[index] != 0xFF:
                break
            while index < len(data) and data[index] == 0xFF:
                index += 1
            if index >= len(data):
                break
            marker = data[index]
            index += 1
            if marker in (0xD8, 0xD9, 0xDA) or marker == 0x00:
                break
            if marker == 0x01 or 0xD0 <= marker <= 0xD7:
                continue
            if index + 2 > len(data):
                break
            length = int.from_bytes(data[index:index + 2], "big")
            if length < 2 or index + length > len(data):
                break
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                if length < 8:
                    break
                height, width = struct.unpack(">HH", data[index + 3:index + 7])
                break
            index += length
    else:
        raise ValueError("Reference image must be a PNG or JPEG")
    if not width or not height:
        raise ValueError("Reference image has invalid or missing dimensions")
    if width * height > 40_000_000:
        raise ValueError("Reference image exceeds 40 million pixels")
    return width, height
