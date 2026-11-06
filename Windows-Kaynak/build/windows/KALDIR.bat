@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title Rigel Cost Pro - Kaldir

set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

set "LOCAL_DATA=%LOCALAPPDATA%\Rigel Alüminyum\Rigel Cost Pro"
set "ROAM_DATA=%APPDATA%\Rigel Alüminyum\Rigel Cost Pro"
set "LOCAL_ORG=%LOCALAPPDATA%\Rigel Alüminyum"
set "ROAM_ORG=%APPDATA%\Rigel Alüminyum"
set "LEGACY_LOCAL=%LOCALAPPDATA%\RigelCostPro"
set "LEGACY_ROAM=%APPDATA%\RigelCostPro"
set "LEGACY_LOCAL2=%LOCALAPPDATA%\Rigel Cost Pro"
set "LEGACY_ROAM2=%APPDATA%\Rigel Cost Pro"
set "DOT_RIGEL=%USERPROFILE%\.rigelcost"
set "DOCS=%USERPROFILE%\Documents"

echo.
echo  ============================================
echo   Rigel Cost Pro - Kaldirma
echo  ============================================
echo.
echo  Program klasoru:
echo    %APP_DIR%
echo.
echo  [1] Normal kaldir
echo      Yalniz bu program klasorunu siler.
echo      Veritabani / ayarlar / ekler KALIR.
echo.
echo  [2] Temiz kaldir / Tum dosyalari kaldir
echo      Program klasoru + tum kullanici verileri:
echo      veritabani, ayarlar, ekler, onbellek,
echo      Documents\RigelCost_* dosyalari.
echo.
echo  [0] Vazgec
echo.
set /p "CHOICE=Seciminiz (0/1/2): "

if "%CHOICE%"=="0" goto :cancel
if "%CHOICE%"=="1" goto :normal
if "%CHOICE%"=="2" goto :clean
echo Gecersiz secim.
pause
exit /b 1

:normal
echo.
echo Normal kaldirma: yalniz program klasoru silinecek.
set /p "CONFIRM=Devam? (E/H): "
if /I not "%CONFIRM%"=="E" goto :cancel
call :close_app
call :delete_program_folder
echo.
echo Normal kaldirma tamamlandi. Kullanici verileri korundu.
goto :done

:clean
echo.
echo UYARI: Temiz kaldirma GERI ALINAMAZ.
echo Silinecek ornek yollar:
echo   %LOCAL_DATA%
echo   %ROAM_DATA%
echo   %DOT_RIGEL%
echo   %DOCS%\RigelCost_*
echo.
set /p "CONFIRM=Tum dosyalari silmek istediginize emin misiniz? (E/H): "
if /I not "%CONFIRM%"=="E" goto :cancel
set /p "CONFIRM2=Son onay - TEMIZ KALDIR? (E/H): "
if /I not "%CONFIRM2%"=="E" goto :cancel
call :close_app
call :wipe_user_data
call :delete_program_folder
echo.
echo Temiz kaldirma tamamlandi.
goto :done

:cancel
echo.
echo Islem iptal edildi.
pause
exit /b 0

:done
echo.
pause
exit /b 0

:close_app
taskkill /F /IM RigelCostPro.exe >nul 2>&1
timeout /t 1 /nobreak >nul
exit /b 0

:wipe_user_data
call :rmdir_if_exists "%LOCAL_DATA%"
call :rmdir_if_exists "%ROAM_DATA%"
call :rmdir_if_exists "%LOCAL_ORG%"
call :rmdir_if_exists "%ROAM_ORG%"
call :rmdir_if_exists "%LEGACY_LOCAL%"
call :rmdir_if_exists "%LEGACY_ROAM%"
call :rmdir_if_exists "%LEGACY_LOCAL2%"
call :rmdir_if_exists "%LEGACY_ROAM2%"
call :rmdir_if_exists "%DOT_RIGEL%"

if exist "%DOCS%" (
  for %%F in ("%DOCS%\RigelCost_*") do (
    if exist "%%~fF\" (
      echo Siliniyor klasor: %%~fF
      rmdir /S /Q "%%~fF" >nul 2>&1
    ) else if exist "%%~fF" (
      echo Siliniyor dosya: %%~fF
      del /F /Q "%%~fF" >nul 2>&1
    )
  )
)

reg delete "HKCU\Software\RigelCost" /f >nul 2>&1
reg delete "HKCU\Software\Rigel Alüminyum" /f >nul 2>&1
exit /b 0

:delete_program_folder
echo Program klasoru siliniyor: %APP_DIR%
cd /d "%TEMP%"
start "" cmd /c "timeout /t 1 /nobreak >nul & rmdir /S /Q \"%APP_DIR%\""
exit /b 0

:rmdir_if_exists
if exist "%~1\" (
  echo Siliniyor: %~1
  rmdir /S /Q "%~1" >nul 2>&1
) else if exist "%~1" (
  echo Siliniyor: %~1
  del /F /Q "%~1" >nul 2>&1
)
exit /b 0
