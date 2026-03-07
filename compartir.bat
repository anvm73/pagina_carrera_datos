@echo off
setlocal EnableExtensions
set "STATE_FILE=%~dp0.runtime\share-link\state.json"
if exist "%STATE_FILE%" del /q "%STATE_FILE%" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\share-link.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if exist "%STATE_FILE%" exit /b 0
if not "%EXIT_CODE%"=="0" (
  echo.
  echo [ERROR] Fallo el proceso de compartir (codigo %EXIT_CODE%).
  pause
)
exit /b %EXIT_CODE%
