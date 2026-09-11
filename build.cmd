@echo off
echo ====================================================
echo        Building Codex Account Manager...
echo ====================================================

pyinstaller --noconfirm --distpath ./lastapp codex_switcher.spec

echo.
echo ====================================================
echo Build completed! Output is in the 'lastapp' folder.
echo ====================================================
pause
