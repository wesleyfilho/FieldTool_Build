@echo off
title FieldTool - Instalacao
echo.
echo  ================================================
echo   FieldTool - Instalador
echo  ================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Python nao encontrado. Instale Python 3.13+
    pause
    exit /b 1
)

echo  [OK] Python encontrado
python --version

echo.
echo  [INFO] Instalando dependencias...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo  [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo  ================================================
echo   Instalacao concluida com sucesso!
echo  ================================================
echo.
echo  Para iniciar: python main.py
echo  OU execute: run.bat
echo.
pause
