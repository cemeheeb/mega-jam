@echo off
rem Packages the game for Windows (Shipping). Result: Out\Windows next to this file.
setlocal
set "UE=C:\Program Files\Epic Games\UE_5.8"
if not exist "%UE%\Engine\Build\BatchFiles\RunUAT.bat" (
  echo Unreal Engine 5.8 was not found in "%UE%".
  echo Open this file in Notepad and fix the line:  set "UE=..."
  pause
  exit /b 1
)
echo Packaging... the first run takes 20-40 minutes. Full log: package_windows.log
call "%UE%\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="%~dp0MegaJam.uproject" -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -archive -archivedirectory="%~dp0Out" -prereqs -nop4 -utf8output -unattended > "%~dp0package_windows.log" 2>&1
if errorlevel 1 (
  echo.
  echo PACKAGING FAILED. Last errors:
  findstr /i /c:"error" "%~dp0package_windows.log" | more
  echo Send package_windows.log to the assistant.
) else (
  echo.
  echo DONE. The game is in "%~dp0Out\Windows". Run MegaJam.exe from there.
)
pause
