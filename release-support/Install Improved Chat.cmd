@echo off
setlocal
title Improved Chat beta installer
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
set "install_result=%ERRORLEVEL%"
echo.
if not "%install_result%"=="0" echo Installation did not complete. Read the message above.
pause
exit /b %install_result%
