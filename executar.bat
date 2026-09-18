@echo off
title Monitor SEI - Inicializador
cd /d "%~dp0"
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocorreu um erro ao executar o Monitor SEI.
    pause
)
