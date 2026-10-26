"""Run from tools/field_observer: python -m field_observer --help."""

import argparse
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

from .core import create_take, export_revision, nearest_frame, validate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline single-phone observation preparation and reviewed counting proposals.")
    commands = parser.add_subparsers(dest="command", required=True)
    gui = commands.add_parser("gui", help="Open the local graphical recording workspace.")
    gui.add_argument("--port", type=int, default=0)
    gui.add_argument("--no-browser", action="store_true")
    gui.add_argument("--data-dir", type=Path)
    create = commands.add_parser("register", help="Decode/hash one fixed take and create empty observation tables.")
    create.add_argument("video", type=Path)
    create.add_argument("destination", type=Path, help="New, nonexistent take directory.")
    for name in ("survey-id", "intersection-id", "take-id", "collector", "clock-note"):
        create.add_argument("--" + name, required=True)
    create.add_argument("--start", help="Wall-clock time of first decoded video frame, with UTC offset. Omit if unknown.")
    create.add_argument("--source-kind", choices=("observed", "synthetic"), required=True)
    frame = commands.add_parser("frame", help="Find nearest real frame timestamp for a manually observed event.")
    frame.add_argument("take", type=Path)
    frame.add_argument("--time", type=float, required=True)
    setup = commands.add_parser("setup", help="Create a local HTML counting-line editor from a source frame.")
    setup.add_argument("take", type=Path)
    setup.add_argument("destination", type=Path, help="New HTML filename.")
    setup.add_argument("--time", type=float, default=0)
    setup.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=0, help="Clockwise display rotation.")
    model = commands.add_parser("prepare-model", help="Download and verify the official RF-DETR Small checkpoint.")
    model.add_argument("--directory", type=Path, default=Path(".cache/models"))
    analyze_parser = commands.add_parser("analyze", help="Analyze every source frame; output unreviewed proposals only.")
    analyze_parser.add_argument("take", type=Path)
    analyze_parser.add_argument("lines", type=Path)
    analyze_parser.add_argument("destination", type=Path, help="New analysis directory.")
    analyze_parser.add_argument("--weights", type=Path, default=Path(".cache/models/rf-detr-small.pth"))
    analyze_parser.add_argument("--confidence", type=float, default=.35)
    analyze_parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto",
                                help="auto uses an NVIDIA GPU when available (override with FIELD_OBSERVER_DEVICE).")
    proposals = commands.add_parser("use-proposals", help="Copy a complete analysis into an EMPTY events draft for manual review.")
    proposals.add_argument("take", type=Path)
    proposals.add_argument("analysis", type=Path)
    check = commands.add_parser("check", help="Validate source identity and editable observation tables.")
    check.add_argument("take", type=Path)
    export = commands.add_parser("export", help="Save a new provisional revision and coverage-aware count bins.")
    export.add_argument("take", type=Path)
    export.add_argument("--reviewer", required=True)
    export.add_argument("--note", required=True)
    export.add_argument("--bin-seconds", type=float, default=900)
    args = parser.parse_args(argv)
    try:
        if args.command == "gui":
            from .gui import serve
            serve(args.data_dir, args.port, not args.no_browser)
            return 0
        elif args.command == "register":
            result = create_take(args.video, args.destination, survey_id=args.survey_id,
                                 intersection_id=args.intersection_id, take_id=args.take_id,
                                 start=args.start, collector=args.collector, clock_note=args.clock_note,
                                 source_kind=args.source_kind)
        elif args.command == "frame":
            result = nearest_frame(args.take, args.time)
        elif args.command == "setup":
            from .setup import create_setup
            result = create_setup(args.take, args.destination, args.time, args.rotation)
        elif args.command == "prepare-model":
            from .detector import prepare_model
            with redirect_stdout(sys.stderr):
                result = prepare_model(args.directory)
        elif args.command == "analyze":
            from .analysis import analyze
            with redirect_stdout(sys.stderr):
                result = analyze(args.take, args.lines, args.destination, args.weights,
                                 confidence=args.confidence, device=args.device,
                                 progress=lambda frames, seconds, events: print(
                                     f"Processed {frames} frames / {seconds:.1f}s; {events} proposals", file=sys.stderr))
        elif args.command == "use-proposals":
            from .analysis import use_proposals
            result = use_proposals(args.take, args.analysis)
        elif args.command == "check":
            result = validate(args.take)[2]
        else:
            result = {"revision_path": str(export_revision(args.take, args.reviewer, args.note, args.bin_seconds).resolve()),
                      "publication_status": "provisional"}
    except (OSError, ValueError, KeyError, ImportError, RuntimeError) as exc:
        print(f"Field observer: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Field observer: interrupted; an incomplete analysis cannot seed reviewed data.", file=sys.stderr)
        return 130
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
