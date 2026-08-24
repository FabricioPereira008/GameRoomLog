@echo off
echo =========================================================
echo  GameRoomLog - Build Windows Executable (.exe)
echo =========================================================

set PYTHON_CMD=python
if exist venv\Scripts\python.exe (
    set PYTHON_CMD=venv\Scripts\python.exe
)

echo 1. Instalando / Verificando PyInstaller...
%PYTHON_CMD% -m pip install --upgrade pip pyinstaller

echo 2. Compilando o executavel com PyInstaller...
%PYTHON_CMD% -m PyInstaller --clean gameroomlog.spec

echo 3. Compactando executavel em arquivo ZIP...
powershell -Command "Compress-Archive -Path dist\gameroomlog.exe, resources -DestinationPath dist\GameRoomLog-Windows-x64.zip -Force"

echo =========================================================
echo  Build concluido com sucesso!
echo  Arquivo gerado: dist\GameRoomLog-Windows-x64.zip
echo =========================================================
pause
