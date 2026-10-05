@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "vk03_app.py"
) else (
  start "" pyw -3 "vk03_app.py"
)
