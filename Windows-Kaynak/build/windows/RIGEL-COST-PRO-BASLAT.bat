@echo off
setlocal
cd /d "%~dp0"
title Rigel Cost Pro
if not exist "%~dp0RigelCostPro.exe" (
    echo RigelCostPro.exe bulunamadi.
    echo Once ZIP dosyasini tamamen cikardiniz mi?
    pause
    exit /b 1
)
start "" "%~dp0RigelCostPro.exe"
