@echo off
title AI Power Farm Dashboard
cd /d "%~dp0"
echo Installing dependencies...
pip install -r requirements.txt --quiet 2>nul
echo.
echo Starting AI Power Farm Dashboard...
echo Open http://localhost:5000 in your browser
echo Default login: admin / admin123
echo.
python server.py
