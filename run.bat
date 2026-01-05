@echo off
:: Restored run.bat
start cmd /k "python -m backend.app"
timeout /t 5
python main.py
pause
