"""Generate a local, self-contained counting-line editor on an actual frame."""

import base64
import io
import json

from pathlib import Path
from .core import nearest_frame, read_take, require
from .media import display_frames


def create_setup(take: Path, destination: Path, seconds: float, rotation: int) -> dict:
    require(not destination.exists(), "Setup destination already exists; choose a new HTML filename.")
    require(rotation in (0, 90, 180, 270), "Unsupported rotation.")
    manifest, _ = read_take(take)
    target = nearest_frame(take, seconds)
    for pts, _, picture in display_frames(Path(manifest["source_path"]), rotation):
        if pts == target["frame_pts"]:
            break
    else:
        raise ValueError("Registered frame was not decoded.")
    width, height = picture.size
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG")
    config = {"schema_version": 1, "take_id": manifest["take_id"], "source_sha256": manifest["source_sha256"],
              "coordinate_space": "display_pixels", "rotation_clockwise": rotation,
              "width": width, "height": height, "reference_frame_pts": target["frame_pts"],
              "reference_time_s": target["time_s"], "deadband_px": min(4, min(width, height) / 10),
              "max_gap_s": 0.5, "lines": []}
    template = Path(__file__).with_name("setup.html").read_text(encoding="utf-8")
    html = template.replace("__CONFIG__", json.dumps(config).replace("<", "\\u003c"))
    html = html.replace("__IMAGE__", base64.b64encode(buffer.getvalue()).decode("ascii"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(html)
    return {"setup_html": str(destination.resolve()), "reference": target,
            "instructions": "Open the HTML locally, draw lines, then save the downloaded lines.json beside this take."}
