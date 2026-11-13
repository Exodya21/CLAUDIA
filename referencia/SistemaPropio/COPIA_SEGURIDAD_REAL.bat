@echo off
setlocal
title SISTEMA PROPIO REAL - copia de seguridad
cd /d "%~dp0"
echo.
echo  COPIA DE SEGURIDAD con restauracion comprobada
echo  ===============================================
echo.
docker compose -p sistemapropio_real --env-file .env.real exec -T db true >nul 2>nul
if errorlevel 1 goto :parado
if not exist copias_real mkdir copias_real

echo  1/2  Copiando la base de datos y restaurandola en una base de comprobacion...
set ARCHIVO=
for /f "delims=" %%F in ('docker compose -p sistemapropio_real --env-file .env.real exec -T db sh /ops/copia.sh') do set ARCHIVO=%%F
if "%ARCHIVO%"=="" goto :error

echo  2/2  Comprobando la copia restaurada (esquema y cadena de auditoria)...
docker compose -p sistemapropio_real --env-file .env.real exec -T api python -m app.ops.backup verificar --archivo %ARCHIVO%
if errorlevel 1 goto :invalida

echo.
echo  Copia VALIDA guardada en la carpeta "copias_real": %ARCHIVO%
echo  Se conservan las 14 mas recientes. Queda registrada en Administracion - Copias de seguridad.
echo  IMPORTANTE: guarde la carpeta copias_real Y el archivo .env.real fuera de este ordenador (disco cifrado).
echo.
pause
exit /b 0

:parado
echo  El sistema no esta en marcha. Ejecute primero INICIAR_REAL.bat.
pause
exit /b 1

:invalida
echo.
echo  ATENCION: la copia NO ha superado la comprobacion. No confie en ella.
echo  Envie a Claude el texto de esta ventana.
pause
exit /b 1

:error
echo.
echo  No se pudo hacer la copia. Envie a Claude el texto de esta ventana.
pause
exit /b 1
