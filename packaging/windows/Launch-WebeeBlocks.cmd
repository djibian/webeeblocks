@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-WebeeBlocks.ps1"
if errorlevel 1 (
  echo.
  echo WebeeBlocks n'a pas pu demarrer. Consultez README-WINDOWS.md.
  pause
)
