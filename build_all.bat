@echo off
chcp 65001 >nul 2>&1
setlocal

echo ============================================
echo   学习通实习打卡助手 — 构建脚本
echo ============================================
echo.

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 pyinstaller。请先执行:
    echo        pip install pyinstaller
    exit /b 1
)

echo [1/2] 构建 后台打卡.exe ...
pyinstaller build\silent.spec --distpath dist --workpath build\work
if errorlevel 1 (
    echo [失败] 后台打卡.exe 构建出错，详见上方日志。
    exit /b 1
)
echo        完成 → dist\后台打卡.exe
echo.

echo [2/2] 构建 打卡助手.exe ...
pyinstaller build\gui.spec --distpath dist --workpath build\work
if errorlevel 1 (
    echo [失败] 打卡助手.exe 构建出错，详见上方日志。
    exit /b 1
)
echo        完成 → dist\打卡助手.exe
echo.

echo ============================================
echo   构建完成！发布包内容（dist\ 目录）：
echo ============================================
dir /b dist\
echo.
echo 将 dist\ 整个文件夹复制给用户即可。
pause
