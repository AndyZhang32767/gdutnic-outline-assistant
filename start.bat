@echo off
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
py -3 -m uvicorn server.app:app --host 0.0.0.0 --port 8787
