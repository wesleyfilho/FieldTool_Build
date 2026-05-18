@echo off
title FieldTool - Build PyInstaller
echo.
echo  ================================================
echo   FieldTool - Gerando Executavel
echo  ================================================
echo.

pip install pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Falha ao instalar PyInstaller.
    pause & exit /b 1
)

:: Limpa builds anteriores
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist "FieldTool.spec" del /q "FieldTool.spec"

pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "FieldTool" ^
    --add-data "app\templates\mikrotik_ap.json;app\templates" ^
    --add-data "app\templates\mikrotik_cliente.json;app\templates" ^
    --add-data "app\templates\ubnt_ap.json;app\templates" ^
    --hidden-import "PySide6.QtWidgets" ^
    --hidden-import "PySide6.QtCore" ^
    --hidden-import "PySide6.QtGui" ^
    --hidden-import "PySide6.QtNetwork" ^
    --hidden-import "cryptography.fernet" ^
    --hidden-import "cryptography.hazmat.primitives.hashes" ^
    --hidden-import "cryptography.hazmat.primitives.kdf.pbkdf2" ^
    --hidden-import "librouteros" ^
    --hidden-import "paramiko" ^
    --hidden-import "paramiko.transport" ^
    --hidden-import "paramiko.auth_handler" ^
    --hidden-import "paramiko.packet" ^
    --collect-all "PySide6" ^
    --collect-all "cryptography" ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERRO] Build falhou. Verifique os erros acima.
    pause & exit /b 1
)

:: Cria pastas de dados ao lado do exe
mkdir "dist\config" 2>nul
mkdir "dist\logs" 2>nul
mkdir "dist\config\backups" 2>nul

echo.
echo  ================================================
echo   Build concluido com sucesso!
echo  ================================================
echo.
echo  Executavel: dist\FieldTool.exe
echo  Copie a pasta dist\ inteira para qualquer PC Windows.
echo  (o exe precisa das pastas config\ e logs\ ao lado dele)
echo  Nao precisa de Python instalado.
echo.
echo  IMPORTANTE: Execute como Administrador para que
echo  o scan de rede funcione corretamente.
echo.
pause
