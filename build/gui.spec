# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — GUI 构建目标
输出: dist/打卡助手.exe（--noconsole，带 PyQt5）

构建命令:
    pyinstaller build/gui.spec --distpath dist --workpath build/work
"""

import sys
import os

block_cipher = None

a = Analysis(
    ['../main.py'],                          # GUI 入口
    pathex=[],
    binaries=[],
    datas=[],                                # config/ 不打包，放在 exe 旁
    hiddenimports=['core', 'gui'],           # 确保 core/ 与 gui/ 被打包
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],                             # 不排除 PyQt5，GUI 需要它
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='打卡助手',                         # 输出名：打卡助手.exe
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                           # --noconsole：不弹出黑框
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                               # TODO: 替换为实际 .ico 路径
    version=None,                            # TODO: 替换为 version.txt 路径
    # uac_admin=False,
)
