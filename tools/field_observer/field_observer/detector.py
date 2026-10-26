"""Small, explicit adapter around pinned RF-DETR and ByteTrack APIs."""

from importlib.metadata import version
import os
from pathlib import Path

from .core import require, sha256

# RF-DETR's official COCO checkpoint uses sparse category IDs, not YOLO IDs.
COCO_TRAFFIC = {1: "person", 2: "bicycle", 3: "car", 4: "motorcycle", 6: "bus", 8: "truck"}


def configure_cache() -> None:
    cache = Path(__file__).resolve().parents[1] / ".cache"
    os.environ.setdefault("HF_HOME", str(cache / "huggingface"))
    os.environ.setdefault("TORCH_HOME", str(cache / "torch"))


def resolve_device(requested: str = "auto") -> str:
    """'auto' uses an NVIDIA GPU when this environment's PyTorch can reach one, else the CPU.
    FIELD_OBSERVER_DEVICE (cpu or cuda) overrides 'auto', for example to force the CPU."""
    require(requested in {"auto", "cpu", "cuda"}, "Device must be auto, cpu or cuda.")
    if requested == "auto":
        requested = os.environ.get("FIELD_OBSERVER_DEVICE", "auto").strip().lower() or "auto"
        require(requested in {"auto", "cpu", "cuda"}, "FIELD_OBSERVER_DEVICE must be auto, cpu or cuda.")
    if requested != "auto":
        return requested
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


class TrafficDetector:
    def __init__(self, weights: Path, confidence: float, device: str):
        require(weights.is_file(), "Local RF-DETR Small weights are missing; run prepare-model first.")
        require(weights.name == "rf-detr-small.pth", "This adapter supports the official RF-DETR Small COCO checkpoint only.")
        require(0.1 <= confidence <= 0.9, "Confidence must be between 0.1 and 0.9.")
        device = resolve_device(device)
        configure_cache()
        try:
            import numpy as np
            from rfdetr import RFDETRSmall
            from trackers import ByteTrackTracker
            from rfdetr.assets.model_weights import validate_pretrain_weights
        except ImportError as exc:
            raise ValueError("Install requirements-cv.txt in the separate field observer environment.") from exc
        self.np = np
        self.confidence = confidence
        validate_pretrain_weights(str(weights.resolve()), strict=True)
        self.model = RFDETRSmall(pretrain_weights=str(weights.resolve()), device=device)
        # Separate families prevent matching a pedestrian to a vehicle. Keep all
        # original class IDs; line/location IDs are never written into class_id.
        settings = dict(track_activation_threshold=confidence, high_conf_det_threshold=confidence,
                        minimum_consecutive_frames=2, lost_track_buffer=30)
        self.trackers = {key: ByteTrackTracker(**settings) for key in ("P", "V")}
        self.provenance = {"model": "RFDETRSmall", "weights_sha256": sha256(weights),
                           "weights_path": str(weights.resolve()), "device": device,
                           "confidence": confidence, "tracker": "ByteTrackTracker", "tracker_settings": settings,
                           "class_map": COCO_TRAFFIC, "timestamp_mode": "source_pts_seconds",
                           "packages": {name: version(name) for name in
                                        ("rfdetr", "supervision", "trackers", "torch", "torchvision", "av", "numpy", "Pillow")}}

    def update(self, image, time_s: float) -> list[dict]:
        predictions = self.model.predict(image, threshold=self.confidence, include_source_image=False)
        if predictions.class_id is None:
            raise ValueError("Detector did not return category IDs.")
        rows = []
        for family, tracker in self.trackers.items():
            ids = [1] if family == "P" else [2, 3, 4, 6, 8]
            subset = predictions[self.np.isin(predictions.class_id, ids)]
            tracked = tracker.update(subset, timestamp=time_s)
            for index in range(len(tracked)):
                category = int(tracked.class_id[index])
                track_id = int(tracked.tracker_id[index])
                rows.append({"track_id": f"{family}{track_id}" if track_id >= 0 else "",
                             "detected_class_id": category, "detected_class": COCO_TRAFFIC[category],
                             "confidence": float(tracked.confidence[index]),
                             **dict(zip(("x1", "y1", "x2", "y2"), map(float, tracked.xyxy[index])))})
        return rows


def prepare_model(directory: Path) -> dict:
    """Explicit download step; analysis subsequently requires these local weights."""
    configure_cache()
    from rfdetr.assets.model_weights import download_pretrain_weights, validate_pretrain_weights
    directory.mkdir(parents=True, exist_ok=True)
    path = directory.resolve() / "rf-detr-small.pth"
    download_pretrain_weights(str(path))
    validate_pretrain_weights(str(path), strict=True)
    return {"model": "RFDETRSmall", "path": str(path), "sha256": sha256(path)}
