
@echo off
title NETPULSE BUILD
color 0B

echo ======================================
echo          NETPULSE BUILD
echo ======================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Install Python from https://www.python.org/downloads/
    echo Make sure to enable "Add Python to PATH".
    pause
    exit /b 1
)

echo Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install psutil pyinstaller

if errorlevel 1 goto failed

echo.
echo Compiling NETPULSE...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name NETPULSE --icon=netpulse.ico --add-data "netpulse.ico;." NETPULSE.pyw

if errorlevel 1 goto failed

echo.
echo ======================================
echo BUILD SUCCESSFUL!
echo ======================================
echo Your application is in:
echo dist\NETPULSE.exe
pause
exit /b 0

:failed
echo.
echo BUILD FAILED. Check the errors above.
pause
exit /b 1
