@echo off
REM ============================================================
REM  HITL annotation experiment - server launcher (double-click)
REM  Runs run_server.ps1 in the same folder.
REM  Set the password by editing $Pass in run_server.ps1.
REM ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_server.ps1"
echo.
echo === Server / tunnel stopped ===
pause
