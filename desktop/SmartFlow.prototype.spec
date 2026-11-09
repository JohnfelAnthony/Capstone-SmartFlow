# Disposable source-revision prototype only: not an installer or release.
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
import sys
sys.path.insert(0, str(root))
from desktop.paths import STUDY_MAPPING_NAMES, network_resource_names

icon = root / "desktop" / "smartflow.ico"
files = [(str(p), "simulation") for p in sorted((root / "simulation").glob("*.py"))]
files += [(str(root / "simulation" / "metric_definitions.json"), "simulation"), (os.environ["SMARTFLOW_PROTOTYPE_FRONTEND"], "dist")]
files += [(os.environ["SMARTFLOW_PROTOTYPE_MANIFEST"], "."), (str(icon), "desktop")]
if os.environ.get("SMARTFLOW_PROTOTYPE_FULL_ML") == "1":
    files += collect_data_files("stable_baselines3")
files += [(str(root / "data" / "networks" / name), "data/networks") for name in
          network_resource_names(root / "data" / "networks")]
# The shared scenario code uses these templates to recognize the two study sites.
files += [(str(root / "data" / "sites" / name), "data/sites") for name in STUDY_MAPPING_NAMES]
if os.environ.get("SMARTFLOW_DESKTOP_STARTER"):
    files.append((os.environ["SMARTFLOW_DESKTOP_STARTER"], "desktop-starter-content"))

a = Analysis([str(root / "desktop" / "frozen_shell.py"), str(root / "desktop" / "worker_entry.py")],
             pathex=[str(root)], binaries=[], datas=files,
             hiddenimports=["desktop.serve", "desktop.bootstrap", "desktop.recover", "tools.train_ql", "tools.train_dql", "tools.train_ppo", "tools.evaluate_controllers"],
             excludes=[] if os.environ.get("SMARTFLOW_PROTOTYPE_FULL_ML") == "1" else ["torch", "stable_baselines3"], hookspath=[], runtime_hooks=[])
pyz = PYZ(a.pure)
shell_scripts = [item for item in a.scripts if item[0] != "worker_entry"]
worker_scripts = [item for item in a.scripts if item[0] != "frozen_shell"]
shell = EXE(pyz, shell_scripts, [], exclude_binaries=True, name="SmartFlow", console=False, upx=False, icon=str(icon))
worker = EXE(pyz, worker_scripts, [], exclude_binaries=True, name="SmartFlowWorker", console=True, upx=False)
bundle = COLLECT(shell, worker, a.binaries, a.datas, strip=False, upx=False, name="SmartFlowPrototype")
