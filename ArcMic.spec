# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


root = Path(SPECPATH).resolve()

a = Analysis(
    [str(root / "run_arcmic.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[
        (str(root / "vendor" / "engine" / name), "vendor/engine")
        for name in (
            "EqualizerAPO.dll",
            "fftw3f.dll",
            "sndfile.dll",
            "msvcp140.dll",
            "msvcp140_1.dll",
            "msvcp140_2.dll",
            "vcruntime140.dll",
            "vcruntime140_1.dll",
        )
    ] + [
        (str(root / "vendor" / "rnnoise" / "rnnoise_mono.dll"), "vendor/rnnoise"),
        (str(root / "vendor" / "licenses"), "licenses"),
        (str(root / "assets" / "app.ico"), "assets"),
    ],
    hiddenimports=["pystray._win32"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "pytest", "IPython", "matplotlib", "pandas"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ArcMic",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(root / "assets" / "app.ico")],
    version=str(root / "version_info.txt"),
)
