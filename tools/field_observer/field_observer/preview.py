"""Human-facing annotated derivatives; original footage/timestamps stay authoritative."""

import io
import math
from fractions import Fraction
from pathlib import Path


def annotate(picture, detections, config, seconds, demo=False):
    from PIL import ImageDraw
    ratio = min(1, 960 / picture.width)
    size = (max(2, int(picture.width * ratio) // 2 * 2), max(2, int(picture.height * ratio) // 2 * 2))
    image = picture.resize(size)
    sx, sy = size[0] / picture.width, size[1] / picture.height
    draw = ImageDraw.Draw(image)
    for line in config.get("lines", []):
        a, b = [(point[0] * sx, point[1] * sy) for point in (line["a"], line["b"])]
        draw.line((a, b), fill="#4af0b5", width=3)
        draw.text((a[0], max(22, a[1] - 16)), line["id"], fill="#4af0b5")
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length:
            sign = -1 if line["direction"] == "positive_to_negative" else 1
            nx, ny = -dy / length * sign, dx / length * sign
            x, y = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            end = (x + nx * 16, y + ny * 16)
            draw.line(((x - nx * 16, y - ny * 16), end), fill="#4af0b5", width=3)
            draw.line(((end[0] - nx * 8 - ny * 6, end[1] - ny * 8 + nx * 6), end,
                       (end[0] - nx * 8 + ny * 6, end[1] - ny * 8 - nx * 6)), fill="#4af0b5", width=3)
    for item in detections:
        box = (item["x1"] * sx, item["y1"] * sy, item["x2"] * sx, item["y2"] * sy)
        color = "#ffc760" if item["detected_class"] == "person" else "#7dc8ff"
        draw.rectangle(box, outline=color, width=2)
        label = f"{item['detected_class']} {item['confidence']:.0%} {item['track_id'] or 'untracked'}"
        y = max(23, box[1] - 15)
        draw.rectangle((box[0], y, min(size[0], box[0] + len(label) * 7), y + 14), fill="#12242e")
        draw.text((box[0] + 2, y), label, fill=color)
    draw.rectangle((0, 0, size[0], 21), fill="#12242e")
    label = "SCRIPTED DEMO - NOT AI / FIELD DATA" if demo else "AUTOMATIC PROPOSALS - REVIEW REQUIRED"
    draw.text((8, 4), f"{seconds:.2f}s | {label}", fill="white")
    return image


def jpeg_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82)
    return buffer.getvalue()


class PreviewWriter:
    def __init__(self, path: Path):
        import av
        self.av = av
        self.container = av.open(str(path), "w", options={"movflags": "+faststart"})
        self.stream = None

    def append(self, image, seconds):
        if self.stream is None:
            self.stream = self.container.add_stream("libx264", rate=25)
            self.stream.width, self.stream.height = image.size
            self.stream.pix_fmt = "yuv420p"
            self.stream.options = {"preset": "ultrafast", "crf": "24"}
            self.stream.time_base = self.stream.codec_context.time_base = Fraction(1, 1000000)
        frame = self.av.VideoFrame.from_image(image)
        frame.pts, frame.time_base = round(seconds * 1000000), Fraction(1, 1000000)
        for packet in self.stream.encode(frame):
            self.container.mux(packet)

    def close(self):
        try:
            if self.stream is not None:
                for packet in self.stream.encode():
                    self.container.mux(packet)
        finally:
            self.container.close()
