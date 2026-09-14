@echo off
setlocal
start "" "%~dp0WebeeBlocksLauncher.exe"
if errorlevel 1 (
  echo.
  echo WebeeBlocks n'a pas pu demarrer. Consultez README-WINDOWS.md.
  pause
)
