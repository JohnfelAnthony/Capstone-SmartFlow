"""Read actual presentation timestamps without changing the original recording."""

from fractions import Fraction
from pathlib import Path


def display_frames(path: Path, rotation: int = 0):
    """Yield source PTS and RGB PIL frames; apply only the operator's rotation.

    Phone display metadata is deliberately not guessed. Setup and inference use
    the same explicit transform, including recordings stored sideways.
    """
    import av
    from PIL import Image
    rotations = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
                 270: Image.Transpose.ROTATE_90}
    with av.open(str(path)) as container:
        for frame in container.decode(video=0):
            if frame.pts is None or frame.time_base is None:
                raise ValueError("Decoded frame has no timestamp.")
            picture = frame.to_image()
            if rotation:
                picture = picture.transpose(rotations[rotation])
            yield frame.pts, Fraction(frame.pts) * frame.time_base, picture


def probe_video(path: Path) -> dict:
    try:
        import av
    except ImportError as exc:
        raise ValueError("Install the field observer's requirements in its separate environment.") from exc

    timestamps = []
    issues = []
    previous = None
    first_pts = None
    first_time = None
    durations = []
    try:
        with av.open(str(path)) as container:
            if not container.streams.video:
                raise ValueError("The source has no video stream.")
            stream = container.streams.video[0]
            metadata = dict(stream.metadata)
            width, height = stream.width, stream.height
            stream_duration = float(stream.duration * stream.time_base) if stream.duration else None
            for index, frame in enumerate(container.decode(stream)):
                if frame.pts is None or frame.time_base is None:
                    issues.append(f"Frame {index} has no presentation timestamp.")
                    continue
                absolute = Fraction(frame.pts) * frame.time_base
                if first_time is None:
                    first_pts, first_time = frame.pts, absolute
                if previous is not None and absolute <= previous:
                    issues.append(f"Frame {index} has a repeated/backward timestamp.")
                previous = absolute
                seconds = float(absolute - first_time)
                duration = float(frame.duration * frame.time_base) if frame.duration else 0.0
                durations.append(duration)
                timestamps.append({"frame_index": index, "frame_pts": frame.pts,
                                   "time_base": str(frame.time_base), "time_s": seconds})
    except (ValueError, OSError) as exc:
        raise ValueError(f"Cannot decode source video: {exc}") from exc
    if not timestamps:
        raise ValueError("No video frames with usable timestamps were decoded.")
    # The last frame onset is the latest safely supported event time; do not
    # manufacture its exposure duration from the advertised frame rate.
    last_time = timestamps[-1]["time_s"]
    return {"decoder": f"PyAV {av.__version__}", "width": width, "height": height,
            "stream_metadata": metadata, "first_pts": first_pts,
            "first_pts_seconds": float(first_time), "last_frame_time_s": last_time,
            "decoded_duration_s": last_time + durations[-1],
            "reported_stream_duration_s": stream_duration,
            "timestamp_issues": issues, "frames": timestamps}
