@echo off
title FieldTool
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao iniciar. Verifique se as dependencias estao instaladas.
    echo Execute: install.bat
    pause
)
