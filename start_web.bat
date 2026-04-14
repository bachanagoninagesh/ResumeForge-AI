@echo off
title ResumeForge AI
echo.
echo  ============================================================
echo    ResumeForge AI  --  Starting Web Application
echo  ============================================================
echo.

REM Install / upgrade dependencies
pip install -r requirements.txt --quiet

echo  Open your browser at:  http://localhost:5000
echo.
python app.py
pause
