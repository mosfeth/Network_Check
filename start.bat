@echo off
REM start.bat - Launcher para start.ps1 (evita problemas de encoding)
powershell.exe -ExecutionPolicy Bypass -File "%~dp0start.ps1"