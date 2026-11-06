# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path


# PyInstaller's module graph can traverse deeply through Qt, openpyxl and
# reportlab. Windows builds need a higher analysis limit than Python's
# default recursion limit.
sys.setrecursionlimit(max(sys.getrecursionlimit(), 10_000))

project_root = Path(SPECPATH).resolve().parents[1]
icon_path = project_root / "assets" / "rigel.ico"
version_path = project_root / "build" / "windows" / "version_info.txt"

analysis = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "assets" / "logo.jpg"), "assets"),
        (str(project_root / "assets" / "rigel.ico"), "assets"),
        (str(project_root / "data" / "settings.json"), "data"),
        (str(project_root / "database" / "sqlserver"), "database/sqlserver"),
        (str(project_root / "database" / "sqlite"), "database/sqlite"),
    ],
    hiddenimports=["pyodbc"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest", "tkinter"],
    noarchive=False,
    optimize=1,
)

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="RigelCostPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path),
    version=str(version_path),
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RigelCost-Pro",
    contents_directory="_internal",
)
