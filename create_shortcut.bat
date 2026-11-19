@echo off
REM Creates a Desktop shortcut that launches START.bat
set "TARGET=%~dp0START.bat"
set "LNK=%USERPROFILE%\Desktop\Credit Nexus.lnk"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%');$s.TargetPath='%TARGET%';$s.WorkingDirectory='%~dp0';$s.Description='Credit Nexus';$s.Save()" >nul 2>&1
if exist "%LNK%" (echo   [OK] Desktop shortcut created) else (echo   [i] Shortcut not created - use START.bat directly)
