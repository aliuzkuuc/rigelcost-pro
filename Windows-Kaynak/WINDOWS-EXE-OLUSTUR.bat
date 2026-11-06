@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Rigel Cost Pro - Windows EXE Olusturucu

set "BUILD_SCRIPT=%~dp0build\windows\build_windows.ps1"
set "RELEASE_DIR=%~dp0release"
set "PORTABLE_ZIP=%RELEASE_DIR%\RigelCost-Pro-v4.0.0-Portable.zip"

echo.
echo Rigel Cost Pro v4.0.0 Windows paketi hazirlaniyor.
echo Ilk calistirma internet hizina gore birkac dakika surebilir.
echo.

if not exist "%BUILD_SCRIPT%" (
    echo.
    echo HATA: Windows derleme betigi bulunamadi.
    echo Beklenen dosya:
    echo   %BUILD_SCRIPT%
    echo.
    echo Bu ZIP/klasor eksik. Guncel RigelCost-Pro-TEST paketini
    echo yeniden indirip tamamen cikarin; icinde build\windows
    echo klasoru olmalidir.
    echo.
    echo ISLEM BASARISIZ. release klasoru acilmayacak.
    echo.
    pause
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%BUILD_SCRIPT%"
set "BUILD_EXIT=%ERRORLEVEL%"
if not "%BUILD_EXIT%"=="0" (
    echo.
    echo DERLEME TAMAMLANAMADI. ^(cikis kodu: %BUILD_EXIT%^)
    echo Yukaridaki hata mesajinin ekran goruntusunu alin.
    echo.
    echo ISLEM BASARISIZ. release klasoru acilmayacak.
    echo.
    pause
    exit /b 1
)

if not exist "%PORTABLE_ZIP%" (
    echo.
    echo HATA: Derleme bitti gibi gorundu ama cikti olusmadi.
    echo Beklenen dosya:
    echo   %PORTABLE_ZIP%
    echo.
    echo ISLEM BASARISIZ. release klasoru acilmayacak.
    echo.
    pause
    exit /b 1
)

echo.
echo ISLEM TAMAMLANDI.
echo Kurulum ve tasinabilir paket "release" klasorundedir.
echo.
echo HIZLI TEST:
echo   1. release\RigelCost-Pro-v4.0.0-Portable.zip dosyasini C:\RigelTest gibi
echo      OneDrive DISINDA bir klasore cikarin.
echo   2. RIGEL-COST-PRO-BASLAT.bat dosyasina cift tiklayin.
echo.
echo Setup.exe "setup files are corrupted" derse portable ZIP ile devam edin
echo ve projeyi OneDrive disina tasiyip WINDOWS-EXE-OLUSTUR.bat'i yeniden calistirin.
echo.
start "" "%RELEASE_DIR%"
pause
exit /b 0
