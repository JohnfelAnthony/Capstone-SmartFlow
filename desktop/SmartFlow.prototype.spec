# Disposable source-revision prototype only: not an installer or release.
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
files = [(str(p), "simulation") for p in sorted((root / "simulation").glob("*.py"))]
files += [(str(root / "simulation" / "metric_definitions.json"), "simulation"), (os.environ["SMARTFLOW_PROTOTYPE_FRONTEND"], "dist")]
files += [(os.environ["SMARTFLOW_PROTOTYPE_MANIFEST"], ".")]
if os.environ.get("SMARTFLOW_PROTOTYPE_FULL_ML") == "1":
    files += collect_data_files("stable_baselines3")
files += [(str(root / "data" / "networks" / name), "data/networks") for name in
          ("registry.json", "tagum_network.json", "tagum_site_a.json", "tagum_site_b.json")]

a = Analysis([str(root / "desktop" / "frozen_shell.py"), str(root / "desktop" / "worker_entry.py")],
             pathex=[str(root)], binaries=[], datas=files,
             hiddenimports=["desktop.serve", "desktop.bootstrap", "desktop.recover", "tools.train_ql", "tools.train_dql", "tools.train_ppo", "tools.evaluate_controllers"],
             excludes=[] if os.environ.get("SMARTFLOW_PROTOTYPE_FULL_ML") == "1" else ["torch", "stable_baselines3"], hookspath=[], runtime_hooks=[])
pyz = PYZ(a.pure)
shell_scripts = [item for item in a.scripts if item[0] != "worker_entry"]
worker_scripts = [item for item in a.scripts if item[0] != "frozen_shell"]
shell = EXE(pyz, shell_scripts, [], exclude_binaries=True, name="SmartFlow", console=False, upx=False)
worker = EXE(pyz, worker_scripts, [], exclude_binaries=True, name="SmartFlowWorker", console=True, upx=False)
bundle = COLLECT(shell, worker, a.binaries, a.datas, strip=False, upx=False, name="SmartFlowPrototype")
