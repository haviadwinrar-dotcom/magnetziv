@echo off
chcp 65001 >nul
python -m pip install -r requirements.txt --quiet
python app.py
