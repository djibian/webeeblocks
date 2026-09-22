@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "WB_REG_KEY=HKCU\Software\Cyberbotics\Webots-R2025a\RobotWindow"
set "WB_BROWSER_PROGRAM=WebeeBlocks-Chrome.cmd"

if not defined LOCALAPPDATA goto :local_profile_unavailable
set "WB_LOCAL_ROOT=%LOCALAPPDATA%\WebeeBlocks"
set "WEBEEBLOCKS_CHROME_PROFILE=%WB_LOCAL_ROOT%\Chrome-R2025a"
set "WB_BROWSER_HELPER=%WB_LOCAL_ROOT%\%WB_BROWSER_PROGRAM%"
set "WB_REG_SNAPSHOT=%WB_LOCAL_ROOT%\webots-robot-window-registry.reg"
set "WB_REG_STATE=%WB_LOCAL_ROOT%\webots-robot-window-registry.state"

if not exist "%WB_LOCAL_ROOT%" mkdir "%WB_LOCAL_ROOT%" >nul 2>&1
if not exist "%WB_LOCAL_ROOT%" goto :local_profile_unavailable

if exist "%WB_REG_STATE%" (
  call :webots_running
  if not errorlevel 1 goto :concurrent_webots
  call :recover_previous_override
  if errorlevel 1 goto :registry_recovery_failed
)

call :is_chrome_target
if errorlevel 1 goto :launch

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

call :write_browser_helper
if errorlevel 1 goto :local_profile_unavailable

set "WB_REG_EXISTED=0"
reg.exe query "%WB_REG_KEY%" >nul 2>&1
if not errorlevel 1 (
  reg.exe export "%WB_REG_KEY%" "%WB_REG_SNAPSHOT%" /y >nul 2>&1
  if errorlevel 1 goto :registry_snapshot_failed
  set "WB_REG_EXISTED=1"
) else (
  if exist "%WB_REG_SNAPSHOT%" del /q "%WB_REG_SNAPSHOT%" >nul 2>&1
)

> "%WB_REG_STATE%" echo %WB_REG_EXISTED% || goto :registry_snapshot_failed

set "WB_REG_MUTATED=1"
reg.exe add "%WB_REG_KEY%" /v browser /t REG_SZ /d "%WB_BROWSER_PROGRAM%" /f >nul 2>&1
if errorlevel 1 goto :registry_override_failed
reg.exe add "%WB_REG_KEY%" /v newBrowserWindow /t REG_DWORD /d 0 /f >nul 2>&1
if errorlevel 1 goto :registry_override_failed

set "PATH=%WB_LOCAL_ROOT%;%PATH%"

:launch
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-WebeeBlocks.ps1"
set "WB_LAUNCH_EXIT=%ERRORLEVEL%"

call :restore_current_override
if errorlevel 1 goto :registry_recovery_failed

if not "%WB_LAUNCH_EXIT%"=="0" (
  echo.
  echo WebeeBlocks n'a pas pu demarrer. Consultez README-WINDOWS.md.
  pause
)
exit /b %WB_LAUNCH_EXIT%

:is_chrome_target
powershell.exe -NoLogo -NoProfile -Command ^
  "$ErrorActionPreference='SilentlyContinue'; $webots=(Get-ItemProperty -LiteralPath 'Registry::HKEY_CURRENT_USER\Software\Cyberbotics\Webots-R2025a\RobotWindow' -Name browser).browser; if (-not [string]::IsNullOrWhiteSpace([string]$webots)) { if ([string]$webots -match '(?i)chrome') { exit 0 }; exit 1 }; $choice=(Get-ItemProperty -LiteralPath 'Registry::HKEY_CURRENT_USER\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice' -Name ProgId).ProgId; if ([string]::IsNullOrWhiteSpace([string]$choice)) { exit 1 }; if ([string]$choice -match '(?i)chrome') { exit 0 }; $command=(Get-ItemProperty -LiteralPath ('Registry::HKEY_CLASSES_ROOT\' + $choice + '\shell\open\command')).'(default)'; if ([string]$command -match '(?i)chrome(?:\.exe)?') { exit 0 }; exit 1"
exit /b %ERRORLEVEL%

:write_browser_helper
> "%WB_BROWSER_HELPER%" echo @echo off || exit /b 1
>> "%WB_BROWSER_HELPER%" echo if not defined WEBEEBLOCKS_CHROME_EXE exit 2 || exit /b 1
>> "%WB_BROWSER_HELPER%" echo if not defined WEBEEBLOCKS_CHROME_PROFILE exit 2 || exit /b 1
>> "%WB_BROWSER_HELPER%" echo start "" "%%WEBEEBLOCKS_CHROME_EXE%%" --user-data-dir="%%WEBEEBLOCKS_CHROME_PROFILE%%" --no-first-run --no-default-browser-check "%%~1" || exit /b 1
>> "%WB_BROWSER_HELPER%" echo exit || exit /b 1
exit /b 0

:recover_previous_override
set "WB_RECOVERY_STATE="
set /p WB_RECOVERY_STATE=<"%WB_REG_STATE%"
if "%WB_RECOVERY_STATE%"=="1" (
  if not exist "%WB_REG_SNAPSHOT%" exit /b 1
  reg.exe query "%WB_REG_KEY%" >nul 2>&1
  if not errorlevel 1 (
    reg.exe delete "%WB_REG_KEY%" /f >nul 2>&1
    if errorlevel 1 exit /b 1
  )
  reg.exe import "%WB_REG_SNAPSHOT%" >nul 2>&1
  if errorlevel 1 exit /b 1
) else if "%WB_RECOVERY_STATE%"=="0" (
  reg.exe delete "%WB_REG_KEY%" /f >nul 2>&1
  reg.exe query "%WB_REG_KEY%" >nul 2>&1
  if not errorlevel 1 exit /b 1
) else (
  exit /b 1
)
if exist "%WB_REG_SNAPSHOT%" del /q "%WB_REG_SNAPSHOT%" >nul 2>&1
del /q "%WB_REG_STATE%" >nul 2>&1
if exist "%WB_REG_STATE%" exit /b 1
exit /b 0

:restore_current_override
if not defined WB_REG_MUTATED exit /b 0
if "%WB_REG_EXISTED%"=="1" (
  if not exist "%WB_REG_SNAPSHOT%" exit /b 1
  reg.exe query "%WB_REG_KEY%" >nul 2>&1
  if not errorlevel 1 (
    reg.exe delete "%WB_REG_KEY%" /f >nul 2>&1
    if errorlevel 1 exit /b 1
  )
  reg.exe import "%WB_REG_SNAPSHOT%" >nul 2>&1
  if errorlevel 1 exit /b 1
) else (
  reg.exe delete "%WB_REG_KEY%" /f >nul 2>&1
  reg.exe query "%WB_REG_KEY%" >nul 2>&1
  if not errorlevel 1 exit /b 1
)
if exist "%WB_REG_SNAPSHOT%" del /q "%WB_REG_SNAPSHOT%" >nul 2>&1
del /q "%WB_REG_STATE%" >nul 2>&1
if exist "%WB_REG_STATE%" exit /b 1
set "WB_REG_MUTATED="
exit /b 0

:webots_running
tasklist.exe /FI "IMAGENAME eq webots.exe" /NH 2>nul | find.exe /I "webots.exe" >nul
if not errorlevel 1 exit /b 0
tasklist.exe /FI "IMAGENAME eq webotsw.exe" /NH 2>nul | find.exe /I "webotsw.exe" >nul
if not errorlevel 1 exit /b 0
tasklist.exe /FI "IMAGENAME eq webots-bin.exe" /NH 2>nul | find.exe /I "webots-bin.exe" >nul
if not errorlevel 1 exit /b 0
exit /b 1

:registry_override_failed
call :restore_current_override
if errorlevel 1 goto :registry_recovery_failed
echo.
echo WebeeBlocks n'a pas pu preparer Chrome sans modifier durablement les preferences Webots.
goto :fail

:registry_snapshot_failed
if exist "%WB_REG_STATE%" del /q "%WB_REG_STATE%" >nul 2>&1
if exist "%WB_REG_SNAPSHOT%" del /q "%WB_REG_SNAPSHOT%" >nul 2>&1
echo.
echo WebeeBlocks n'a pas pu sauvegarder les preferences Webots avant le lancement.
goto :fail

:registry_recovery_failed
echo.
echo WebeeBlocks a conserve une sauvegarde locale des preferences Webots mais n'a pas pu les restaurer automatiquement.
echo Fermez Webots puis relancez WebeeBlocks pour retenter la restauration.
goto :fail

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
