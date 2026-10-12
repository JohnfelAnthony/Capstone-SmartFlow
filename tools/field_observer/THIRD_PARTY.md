# Third-party components

The field observer uses installed public APIs; no upstream repository or example source has been vendored into SmartFlow. Preserve upstream package licenses when distributing an environment. `requirements-cv-lock.txt` records the Windows/Python 3.13 wheel versions and hashes used for this tool; those dependencies are separate from the SmartFlow backend.

| Component | Use | Upstream |
| --- | --- | --- |
| RF-DETR 1.11.1, RF-DETR Small COCO weights | General object detections; Apache-2.0 family selected in the project plan | [RF-DETR](https://github.com/roboflow/rf-detr), [versioned package](https://pypi.org/project/rfdetr/1.11.1/) |
| Supervision 0.30.6 | Detection containers and filtering | [Supervision](https://github.com/roboflow/supervision), [versioned package](https://pypi.org/project/supervision/0.30.6/) |
| trackers 2.6.1 | ByteTrack association with source timestamps | [Trackers](https://github.com/roboflow/trackers), [versioned package](https://pypi.org/project/trackers/2.6.1/) |
| PyAV 19.0.1 | Decode the original presentation timestamps and frames | [PyAV](https://github.com/PyAV-Org/PyAV), [time API](https://pyav.org/docs/stable/api/time.html) |
| Pillow 12.3.0 | Consistent RGB frame rotation and reference PNG | [Pillow](https://github.com/python-pillow/Pillow) |
| OpenCV Python 5.0.0.93 | Upstream tracker dependency; the first editor itself uses local HTML | [OpenCV Python](https://github.com/opencv/opencv-python) |

The integration keeps original detector category IDs separate from track IDs and counting-line IDs. It uses RF-DETR's sparse COCO IDs (person 1, bicycle 2, car 3, motorcycle 4, bus 6, truck 8). No local tricycle, jeepney or emergency classification has been trained. Changing the checkpoint or class mapping requires an explicit adapter change and new validation.

The prepared official Small checkpoint is `rf-detr-small.pth`, SHA-256 `d81979a9213a2109345158ce9232668df4c1ae52e9b8db3f2ec0a8cbad959b33`. Preparation verifies the upstream registry checksum; each analysis records the local SHA-256. Weights are ignored cache artifacts, not SmartFlow RL models. RF-DETR Plus models are not selected by this tool.
