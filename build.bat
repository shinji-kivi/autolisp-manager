@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ==============================
echo  AutoLISP管理ツール ビルド
echo ==============================
echo.

:: --- 1. Python EXE ---
echo [1/3] Python EXE をビルド中...
pyinstaller "AutoLISP管理ツール.spec" --clean
if %errorlevel% neq 0 (
    echo [エラー] Python ビルドに失敗しました。
    pause
    exit /b 1
)

:: --- 2. AutoCAD パネル DLL ---
echo.
echo [2/3] AutoCAD パネル DLL をビルド中...
dotnet build panel\AutoLispPanel.sln -c Release
if %errorlevel% neq 0 (
    echo [エラー] パネル DLL のビルドに失敗しました。
    pause
    exit /b 1
)

:: --- 3. バンドルを ApplicationPlugins に配置 ---
echo.
echo [3/3] バンドルを ApplicationPlugins に配置中...
set BUNDLE_DST=%APPDATA%\Autodesk\ApplicationPlugins\AutoLispPanel.bundle

xcopy /E /I /Y "panel\bundle" "%BUNDLE_DST%" > nul
copy /Y "panel\AutoLispPanel\bin\Release\net8.0-windows\AutoLispPanel.dll"  "%BUNDLE_DST%\Contents\2026\" > nul
copy /Y "panel\AutoLispPanel\bin\Release\net10.0-windows\AutoLispPanel.dll" "%BUNDLE_DST%\Contents\2027\" > nul
copy /Y "assets\logo.png" "%BUNDLE_DST%\" > nul

echo.
echo ==============================
echo  ビルド完了
echo   dist\AutoLISP管理ツール.exe
echo   %BUNDLE_DST%
echo ==============================
pause
