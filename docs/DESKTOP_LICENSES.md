# Desktop package dependency licences (D1 review, 2026-11-04)

Source: package metadata from `.venv-desktop` (exact versions in `desktop/requirements-desktop-lock.txt`) and `package.json` production dependencies. This is an engineering inventory, not legal advice; the owner or adviser should confirm before any distribution.

## Python runtime packages

The comparison PDF also uses ReportLab 4.4.9 (BSD) and charset-normalizer 3.5.2 (MIT).

| Licence | Packages |
| --- | --- |
| MIT / MIT-0 / MIT-CMU | altgraph, annotated-types, anyio, bottle, cffi, fastapi, filelock, fonttools, gymnasium, h11, pefile, pillow, proxy_tools, pydantic, pydantic_core, pyparsing, pythonnet, stable_baselines3, typing-inspection, Farama-Notifications |
| BSD (2/3-clause) | click, cloudpickle, contourpy, fsspec, idna, Jinja2, MarkupSafe, mpmath, networkx, numpy (bundles 0BSD, MIT, Zlib, CC0 parts), pandas, pycparser, pywebview, pywin32-ctypes, python-dateutil, starlette, sympy, torch (CPU build), uvicorn, websockets, Werkzeug |
| Apache-2.0 / dual | packaging (Apache-2.0 OR BSD-2-Clause), tzdata, python-dateutil (dual BSD/Apache) |
| PSF-style | typing_extensions, matplotlib (PSF-based licence), cycler/kiwisolver (BSD, matplotlib project) |
| Not stated in metadata | clr_loader (upstream is MIT; confirm from its source before release) |

Build-time only (not shipped inside the application folder): PyInstaller 6.22.3 (GPLv2-or-later with an exception that permits bundling non-GPL programs) and pyinstaller-hooks-contrib (Apache-2.0 / GPLv2 hook files). PyInstaller's bootloader exception allows distributing the frozen output under any licence; keep the notice text with the build.

## Frontend and assets

MIT: React stack, @base-ui, @dnd-kit and other production dependencies (17); Apache-2.0: class-variance-authority; ISC: lucide-react; BSD-2-Clause: leaflet 1.9.4; OFL-1.1: Geist variable font (@fontsource). Kenney 3D asset kits were removed with the 3D renderer.

## Network use to disclose

Map view uses OpenStreetMap tiles, which need internet access and carry OpenStreetMap attribution requirements; the simulator itself is offline. Junction images are enhanced images, not field photographs.

## Installer tooling

Inno Setup is free to use, including commercially, under its own licence; confirm the current terms at jrsoftware.org before building (D10). The Microsoft WebView2 runtime is redistributable under Microsoft's terms; the standalone offline installer must come from Microsoft.

## Open items

- Ship a third-party notices file inside the installer containing the licence texts of the packages above (not yet generated).
- Hash-pinned lock (pip-compile or uv) is not produced; versions are recorded only.
