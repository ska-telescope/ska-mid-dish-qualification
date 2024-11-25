# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ["src/ska_mid_disq/mvcmain.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("src/ska_mid_disq/ui/dishstructure_mvc.ui", "ska_mid_disq/ui"),
        ("src/ska_mid_disq/default_logging_config.yaml", "ska_mid_disq"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DiSQ",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    [("skao.ico", "src/ska_mid_disq/ui/icons/skao.ico", "DATA")],
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DiSQ",
)
