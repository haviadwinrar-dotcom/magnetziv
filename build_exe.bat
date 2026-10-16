@echo off
chcp 65001 >nul
echo מתקין תלויות...
python -m pip install -r requirements.txt --quiet
echo בונה קובץ EXE...
python -m PyInstaller --noconfirm --onefile --windowed --name Magnetoti app.py
echo.
echo הסתיים! הקובץ נמצא בתיקייה dist\Magnetoti.exe
pause
