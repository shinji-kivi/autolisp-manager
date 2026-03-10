@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ==============================
echo  AutoLISP管理ツール ビルド
echo ==============================
echo.

pyinstaller "AutoLISP管理ツール.spec" --clean

if %errorlevel% neq 0 (
    echo.
    echo [エラー] ビルドに失敗しました。
    pause
    exit /b 1
)

echo.
echo [完了] dist\AutoLISP管理ツール.exe が生成されました。
pause
