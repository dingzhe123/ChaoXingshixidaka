# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — 静默（后台）构建目标
输出: dist/后台打卡.exe（无控制台，仅依赖 requests）

【关键】本 spec 必须不引用任何 GUI 模块。
如果 main.py 顶部 import 了 PyQt5，PyInstaller 会把它一并打包进来
（即使函数内延迟 import 也会被静态分析捕获），
导致每次定时打卡都解包 80MB 的 Qt。

因此静默入口是独立的 silent_main.py，不是 main.py --silent。

构建命令:
    pyinstaller build/silent.spec --distpath dist --workpath build/work
"""

block_cipher = None

a = Analysis(
    ['../silent_main.py'],                  # 独立静默入口
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['core'],                  # 只打包 core/，不碰 gui/
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 明确排除 GUI 相关模块，防止意外引入
    excludes=[
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
        'tkinter', 'matplotlib', 'numpy', 'scipy',
        'IPython', 'jupyter', 'pytest',
    ],
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
    name='后台打卡',                         # 输出名：后台打卡.exe
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                           # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                               # TODO: 替换为实际 .ico 路径
    version=None,
)
