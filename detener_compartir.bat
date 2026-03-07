@echo off
setlocal EnableExtensions
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-share-link.ps1"
exit /b %ERRORLEVEL%
