@echo off
setlocal
title SISTEMA PROPIO - entorno de demostracion
cd /d "%~dp0"
echo.
echo  SISTEMA PROPIO - entorno local con DATOS FICTICIOS
echo  ===================================================
echo.

where docker >nul 2>nul
if errorlevel 1 goto :sin_docker
docker info >nul 2>nul
if errorlevel 1 goto :docker_parado

if exist .env goto :arrancar
docker volume inspect sistemapropio_pgdata >nul 2>nul
if errorlevel 1 goto :crear_env
echo  Ya existe una base de datos de una instalacion anterior, pero esta carpeta no tiene su archivo .env
echo  (contiene la clave de esa base de datos).
echo   - Para conservar sus datos: copie el archivo .env de la carpeta anterior a esta y vuelva a ejecutar.
echo   - Para empezar de cero con los datos ficticios: ejecute REINICIAR_DATOS_DEMO.bat y despues este archivo.
pause
exit /b 1
:crear_env
echo  Creando configuracion local con claves aleatorias...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = -join (1..24 | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) }); $s = -join (1..32 | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) }); Set-Content -Path '.env' -Encoding ascii -Value @('POSTGRES_USER=sistema', ('POSTGRES_PASSWORD=' + $p), 'POSTGRES_DB=sistema_propio', 'APP_ENV=development', 'AUTH_MODE=demo,local', ('SESSION_SECRET=' + $s), 'COOKIE_SECURE=false')"
if not exist .env goto :error

:arrancar
rem Actualizacion F0.2: ademas del acceso de demostracion, habilita usuario + contrasena + codigo del movil.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$c = Get-Content '.env'; if ($c -contains 'AUTH_MODE=demo') { ($c -replace '^AUTH_MODE=demo$', 'AUTH_MODE=demo,local') | Set-Content -Encoding ascii '.env' }"
if not exist copias mkdir copias
echo  Construyendo y arrancando. La PRIMERA vez tarda varios minutos...
echo.
docker compose up -d --build
if errorlevel 1 goto :error

echo.
echo  Esperando a que el sistema responda...
powershell -NoProfile -ExecutionPolicy Bypass -Command "for ($i = 0; $i -lt 120; $i++) { try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://localhost:3000/api/v1/health'; if ($r.StatusCode -eq 200) { exit 0 } } catch { }; Start-Sleep -Seconds 2 }; exit 1"
if errorlevel 1 goto :lento

start "" "http://localhost:3000"
echo.
echo  Listo. Se ha abierto http://localhost:3000 en su navegador.
echo  Para apagarlo, haga doble clic en DETENER.bat
echo.
pause
exit /b 0

:sin_docker
echo  No se encuentra Docker. Instale Docker Desktop desde
echo  https://www.docker.com/products/docker-desktop/  y vuelva a ejecutar este archivo.
pause
exit /b 1

:docker_parado
echo  Docker Desktop esta instalado pero no esta en marcha.
echo  Abralo desde el menu Inicio, espere a que diga "Engine running" y vuelva a ejecutar este archivo.
pause
exit /b 1

:lento
echo  El sistema esta tardando mas de lo normal. Pruebe a abrir http://localhost:3000 dentro de un minuto.
echo  Si no carga, envie a Claude el resultado de:  docker compose logs api
pause
exit /b 1

:error
echo.
echo  Algo ha fallado. Copie el texto de esta ventana y envieselo a Claude.
pause
exit /b 1
