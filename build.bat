@echo off
echo Cleaning previous build and dist directories...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building Tunevia with PyInstaller...
if exist "venv\Scripts\pyinstaller.exe" (
    "venv\Scripts\pyinstaller.exe" --clean Tunevia.spec --noconfirm
) else (
    pyinstaller --clean Tunevia.spec --noconfirm
)

if %ERRORLEVEL% equ 0 (
    echo.
    echo ========================================================
    echo Build succeeded! The output is located at:
    echo dist\Tunevia\Tunevia.exe
    echo ========================================================
) else (
    echo.
    echo ========================================================
    echo Build failed with error code %ERRORLEVEL%.
    echo ========================================================
)
