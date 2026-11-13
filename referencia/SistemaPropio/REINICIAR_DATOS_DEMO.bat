@echo off
setlocal
title SISTEMA PROPIO - reiniciar datos de demostracion
cd /d "%~dp0"
echo.
echo  ATENCION: esto borra la base de datos local de demostracion y la recrea con los datos ficticios iniciales.
echo  Solo afecta a este ordenador. Pulse Ctrl+C para cancelar o cualquier tecla para continuar.
pause >nul

docker info >nul 2>nul
if errorlevel 1 goto :docker_parado

rem Para apagar y borrar no hacen falta las claves reales: si falta .env se usan valores provisionales.
if not exist .env (
  set POSTGRES_PASSWORD=borrado
  set SESSION_SECRET=borrado-borrado-borrado-borrado-borrado
)
docker compose -p sistemapropio down -v --remove-orphans
rem Por si la base es de una instalacion en otra carpeta: se borra tambien por su nombre.
docker volume inspect sistemapropio_pgdata >nul 2>nul
if errorlevel 1 goto :hecho
docker volume rm sistemapropio_pgdata >nul 2>nul
if errorlevel 1 goto :en_uso

:hecho
echo.
echo  Base de datos local borrada. Ahora ejecute INICIAR.bat para empezar de cero.
echo.
pause
exit /b 0

:en_uso
echo.
echo  No se pudo borrar la base de datos porque la esta usando otra instalacion del sistema.
echo  Abra Docker Desktop, en "Containers" elimine los de "sistemapropio" y vuelva a ejecutar este archivo.
pause
exit /b 1

:docker_parado
echo  Docker Desktop no esta en marcha. Abralo, espere a "Engine running" y vuelva a ejecutar este archivo.
pause
exit /b 1
