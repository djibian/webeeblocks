@echo off
setlocal EnableExtensions DisableDelayedExpansion

if not defined LOCALAPPDATA goto :local_profile_unavailable
set "WB_LOCAL_ROOT=%LOCALAPPDATA%\WebeeBlocks"
set "WEBEEBLOCKS_CHROME_PROFILE=%WB_LOCAL_ROOT%\Chrome-R2025a"

if not exist "%WB_LOCAL_ROOT%" mkdir "%WB_LOCAL_ROOT%" >nul 2>&1
if not exist "%WB_LOCAL_ROOT%" goto :local_profile_unavailable

call :webots_running
if not errorlevel 1 goto :concurrent_webots

set "WEBEEBLOCKS_CHROME_EXE="
if defined ProgramFiles if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "WEBEEBLOCKS_CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined WEBEEBLOCKS_CHROME_EXE if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "WEBEEBLOCKS_CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if not defined WEBEEBLOCKS_CHROME_EXE if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "WEBEEBLOCKS_CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined WEBEEBLOCKS_CHROME_EXE goto :chrome_unavailable

powershell.exe -NoLogo -NoProfile -Command ^
  "$ErrorActionPreference='Stop'; try { $p=[IO.Path]::GetFullPath($env:WEBEEBLOCKS_CHROME_PROFILE); $root=[IO.Path]::GetPathRoot($p); if ([string]::IsNullOrWhiteSpace($root) -or $root.StartsWith('\\')) { exit 2 }; $drive=[IO.DriveInfo]::new($root); if ($drive.DriveType -eq [IO.DriveType]::Network) { exit 3 }; [IO.Directory]::CreateDirectory($p) | Out-Null; $probe=Join-Path $p ('.webeeblocks-write-' + [Guid]::NewGuid().ToString('N') + '.tmp'); [IO.File]::WriteAllText($probe,'probe'); Remove-Item -LiteralPath $probe -Force; exit 0 } catch { exit 4 }"
if errorlevel 1 goto :local_profile_unavailable

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-WebeeBlocks.ps1"
set "WB_LAUNCH_EXIT=%ERRORLEVEL%"
if not "%WB_LAUNCH_EXIT%"=="0" (
  echo.
  echo WebeeBlocks n'a pas pu demarrer. Consultez README-WINDOWS.md.
  pause
)
exit /b %WB_LAUNCH_EXIT%

:webots_running
tasklist.exe /FI "IMAGENAME eq webots.exe" /NH 2>nul | find.exe /I "webots.exe" >nul
if not errorlevel 1 exit /b 0
tasklist.exe /FI "IMAGENAME eq webotsw.exe" /NH 2>nul | find.exe /I "webotsw.exe" >nul
if not errorlevel 1 exit /b 0
tasklist.exe /FI "IMAGENAME eq webots-bin.exe" /NH 2>nul | find.exe /I "webots-bin.exe" >nul
if not errorlevel 1 exit /b 0
exit /b 1

:concurrent_webots
echo.
echo Une instance Webots est deja ouverte. Fermez-la avant de lancer WebeeBlocks.
goto :fail

:chrome_unavailable
echo.
echo Google Chrome est introuvable sur ce poste. Installez Chrome localement puis relancez WebeeBlocks.
goto :fail

:local_profile_unavailable
echo.
echo WebeeBlocks ne peut pas creer un profil Chrome local et accessible hors ligne dans %%LOCALAPPDATA%%.
goto :fail

:fail
pause
exit /b 1
