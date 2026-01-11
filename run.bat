@echo off
:: Unified Startup
start cmd /k "call .venv\Scripts\activate.bat && python -m backend.app"
timeout /t 2
echo System Started. Access at http://127.0.0.1:5001
