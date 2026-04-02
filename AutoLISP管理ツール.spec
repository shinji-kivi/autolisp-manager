# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AutoLISP管理ツール
ビルド方法: pyinstaller "AutoLISP管理ツール.spec"

onedir モード: インストーラーで配布するため _MEI* 一時ディレクトリ問題を回避。
"""
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# CustomTkinter のテーマ・アセットを収集
ctk_datas = collect_data_files("customtkinter")

# tkinterdnd2 の DLL を収集（インストール済みの場合のみ）
try:
    tkdnd_datas = collect_data_files("tkinterdnd2")
except Exception:
    tkdnd_datas = []

a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=[],
    datas=ctk_datas + tkdnd_datas + [("assets", "assets")],
    hiddenimports=[
        "win32api",
        "win32con",
        "win32com.client",
        "win32com.server.util",
        "pywintypes",
        "PIL._tkinter_finder",
        "tkinterdnd2",
        "windnd",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoLISP管理ツール",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/logo.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="AutoLISP管理ツール",
)
