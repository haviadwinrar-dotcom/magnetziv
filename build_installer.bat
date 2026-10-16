@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo [1/3] Building Magnetoti.exe ...
python -m pip install -r requirements.txt --quiet || goto :err
python -m PyInstaller --noconfirm --onefile --windowed --name Magnetoti app.py || goto :err

echo [2/3] Looking for Inno Setup ...
set "ISCC="
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set "ISCC=%%~P"
if not defined ISCC (
    echo Installing Inno Setup via winget ...
    winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
    for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set "ISCC=%%~P"
)
if not defined ISCC (
    echo Could not find Inno Setup. Install it from https://jrsoftware.org/isdl.php and run this file again.
    goto :err
)

echo [3/3] Building installer ...
"%ISCC%" installer.iss || goto :err

echo.
echo Done! Installer: installer_output\Magnetoti_Setup.exe
pause
exit /b 0

:err
echo.
echo Build failed. See the messages above.
pause
exit /b 1
