"""Build an isolated two-executable Windows prototype; never a release installer."""
import os
import json
import subprocess
import sys
import uuid
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build a disposable desktop experiment")
    parser.add_argument("--with-ml", action="store_true", help="Include the checked CPU-only ML stack")
    parser.add_argument("--frontend", type=Path, help="Built desktop frontend directory (defaults to dist)")
    args = parser.parse_args()
    if os.name != "nt":
        raise SystemExit("Build this Windows prototype on Windows")
    root = Path(__file__).resolve().parents[1]
    frontend = (args.frontend or root / "dist").resolve()
    if not (frontend / "index.html").is_file():
        raise SystemExit("Build the desktop frontend first with VITE_SMARTFLOW_DESKTOP=1")
    if args.with_ml:
        from desktop.packaging_checks import require_cpu_ml
        require_cpu_ml()
    output = root / "tmp" / ("desktop-shell-experiment-" + uuid.uuid4().hex[:12])
    output.mkdir(parents=True, exist_ok=False)
    from desktop.engine_manifest import create_manifest
    manifest = output / "engine-manifest.json"
    manifest.write_text(json.dumps(create_manifest(root), indent=2), encoding="utf-8")
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["SMARTFLOW_PROTOTYPE_MANIFEST"] = str(manifest)
    env["SMARTFLOW_PROTOTYPE_FRONTEND"] = str(frontend)
    env["SMARTFLOW_PROTOTYPE_FULL_ML"] = "1" if args.with_ml else "0"
    print(f"Building disposable shell experiment in {output}", flush=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(output / "dist"),
                    "--workpath", str(output / "work"), str(root / "desktop" / "SmartFlow.prototype.spec")],
                   cwd=root, env=env, check=True)
    from desktop.build_inventory import inventory
    record = inventory(output / "dist" / "SmartFlowPrototype")
    with (output / "build-inventory.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    print(f"Prototype: {output / 'dist' / 'SmartFlowPrototype'}", flush=True)
    print(f"Unsigned build inventory: {output / 'build-inventory.json'}", flush=True)


if __name__ == "__main__":
    main()
