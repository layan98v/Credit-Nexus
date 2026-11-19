@echo off
REM Builds dist\CreditNexus.exe on THIS Windows PC (needs Python once, only here).
REM Give the resulting .exe to anyone: they just double-click it, no Python needed.
cd /d "%~dp0"
python -m pip install --quiet -r backend\requirements.txt pyinstaller || goto :fail
python -m PyInstaller --noconfirm --clean packaging\credit-nexus.spec || goto :fail
echo.
echo   Built: %~dp0dist\CreditNexus.exe
pause
exit /b 0
:fail
echo   Build failed - see messages above.
pause
exit /b 1
