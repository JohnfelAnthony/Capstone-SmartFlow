"""Explicitly scripted visual demo for trying the GUI before field collection."""

from fractions import Fraction
import time


def boxes(index):
    rows = []
    for track_id, category, category_id, x, offset in (("V1", "car", 3, 180, 0), ("V2", "truck", 8, 370, -70),
                                                     ("P1", "person", 1, 560, -30)):
        y = 55 + index * 3 + offset
        if 0 < y < 450:
            rows.append(dict(track_id=track_id, detected_class=category, detected_class_id=category_id,
                             confidence=1., x1=x, x2=x + (25 if category == "person" else 65), y1=y - 45, y2=y))
    return rows


def create_demo(path):
    import av
    from PIL import Image, ImageDraw
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=25)
        stream.width, stream.height, stream.pix_fmt = 800, 450, "yuv420p"
        stream.time_base = stream.codec_context.time_base = Fraction(1, 1000)
        for i in range(100):
            picture = Image.new("RGB", (800, 450), "#d6e2da")
            draw = ImageDraw.Draw(picture)
            draw.rectangle((130, 0, 500, 450), fill="#4a5963")
            draw.line((310, 0, 310, 450), fill="#e6e8d9", width=3)
            draw.text((16, 15), "SYNTHETIC VISUAL DEMO", fill="#18352d")
            for item in boxes(i):
                draw.rectangle((item["x1"], item["y1"], item["x2"], item["y2"]), fill="#4d9ac0" if item["detected_class"] != "person" else "#e8ac57")
            frame = av.VideoFrame.from_image(picture)
            frame.pts, frame.time_base = i * 40, Fraction(1, 1000)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)


class DemoDetector:
    provenance = {"model": "SCRIPTED DEMO - not AI inference", "field_accuracy_verified": False}

    def __init__(self, *_):
        pass

    def update(self, image, seconds):
        time.sleep(.025)
        return boxes(round(seconds * 25))
