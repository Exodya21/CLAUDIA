@echo off
setlocal
title SISTEMA PROPIO - instalacion REAL del despacho
cd /d "%~dp0"
echo.
echo  SISTEMA PROPIO - instalacion REAL (datos de la empresa)
echo  ========================================================
echo  Base de datos y documentos SEPARADOS de la demostracion. Sin datos ficticios.
echo  Acceso con usuario, contrasena y codigo del movil (app de autenticacion).
echo.

where docker >nul 2>nul
if errorlevel 1 goto :sin_docker
docker info >nul 2>nul
if errorlevel 1 goto :docker_parado

set PRIMERA=0
docker volume inspect sistemapropio_real_pgdata >nul 2>nul
if errorlevel 1 goto :sin_datos
rem Ya hay datos reales: hace falta su .env.real valido (sus claves de cifrado)
if not exist .env.real goto :falta_env
call :env_valido
if errorlevel 1 goto :env_danado
goto :arrancar

:sin_datos
rem Aun no hay base de datos real: si el .env.real no es valido (p. ej. un intento anterior fallido), se rehace
set PRIMERA=1
if not exist .env.real goto :crear_env
call :env_valido
if errorlevel 1 (
  echo  El archivo .env.real esta incompleto ^(intento anterior^). Se vuelve a crear; aun no hay datos.
  del /q .env.real
  goto :crear_env
)
goto :arrancar

:falta_env
echo  Existe la base de datos REAL pero falta el archivo .env.real (contiene sus claves de cifrado).
echo  Copie el .env.real que guardo al instalar a esta carpeta y vuelva a ejecutar. Sin el no se pueden leer los documentos.
pause
exit /b 1

:env_danado
echo  El archivo .env.real esta incompleto y ya existen datos reales. NO lo borre.
echo  Recupere el .env.real que guardo fuera del ordenador y vuelva a ejecutar.
pause
exit /b 1

:env_valido
rem Cada clave debe existir y no estar vacia
for %%K in (SESSION_SECRET POSTGRES_PASSWORD FIELD_ENCRYPTION_KEY) do (
  findstr /b /c:"%%K=" .env.real >nul 2>nul || exit /b 1
  findstr /x /c:"%%K=" .env.real >nul 2>nul && exit /b 1
)
exit /b 0

:crear_env
echo  Creando claves aleatorias de esta instalacion (archivo .env.real)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ops\crear_env_real.ps1" "%~dp0.env.real"
call :env_valido
if not errorlevel 1 goto :env_creado
rem Si PowerShell esta limitado en este equipo, las claves se generan con Docker (solo la primera vez)
echo  Generando las claves con Docker...
if exist .env.real del /q .env.real
docker run --rm alpine:3.20 sh -c "h(){ head -c $1 /dev/urandom | od -An -tx1 | tr -d ' \n'; }; echo POSTGRES_USER=sistema; echo POSTGRES_PASSWORD=$(h 24); echo POSTGRES_DB=sistema_propio; echo APP_ENV=production; echo AUTH_MODE=local; echo SESSION_SECRET=$(h 32); echo FIELD_ENCRYPTION_KEY=$(head -c 32 /dev/urandom | base64 | tr '+/' '-_'); echo COOKIE_SECURE=true; echo COPIAS_DIR=./copias_real; echo OWN_TAX_IDS=" > .env.real
call :env_valido
if errorlevel 1 goto :error
:env_creado
set PRIMERA=1
echo.
echo  IMPORTANTE: guarde una copia de .env.real fuera de este ordenador (por ejemplo en un USB cifrado).
echo  Sin ese archivo NO se pueden recuperar los documentos cifrados ni restaurar las copias.
echo.

:arrancar
if not exist copias_real mkdir copias_real
echo  Deteniendo la demostracion si estaba en marcha (usa los mismos puertos)...
docker compose -p sistemapropio down >nul 2>nul
echo  Construyendo y arrancando. La PRIMERA vez tarda varios minutos...
docker compose -p sistemapropio_real --env-file .env.real up -d --build
if errorlevel 1 goto :error

echo  Esperando a que el sistema responda...
powershell -NoProfile -ExecutionPolicy Bypass -Command "for ($i = 0; $i -lt 150; $i++) { try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://localhost:3000/api/v1/health'; if ($r.StatusCode -eq 200) { exit 0 } } catch { }; Start-Sleep -Seconds 2 }; exit 1"
if errorlevel 1 goto :lento

if "%PRIMERA%"=="1" goto :primer_admin
goto :abrir

:primer_admin
echo.
echo  Alta de la PRIMERA persona administradora (Direccion). El resto de usuarios se crean despues
echo  desde Administracion dentro del programa.
echo.
set /p ENTIDAD=  Nombre de la sociedad (tal como figura en las facturas): 
set /p SEDES=  Sedes separadas por comas (ej. Barcelona,Madrid,Valencia): 
set /p USUARIO=  Usuario para entrar (sin espacios, ej. rserrano): 
set /p NOMBRE=  Nombre y apellidos: 
set /p CORREO=  Correo electronico: 
docker compose -p sistemapropio_real --env-file .env.real exec -T api python -m app.ops.primer_admin --crear-entidad --entidad "%ENTIDAD%" --sedes "%SEDES%" --usuario "%USUARIO%" --nombre "%NOMBRE%" --correo "%CORREO%"
if errorlevel 1 goto :error
echo.
echo  Apunte la contrasena provisional de arriba. Al entrar le pedira cambiarla y activar el codigo del movil
echo  (Google Authenticator, Microsoft Authenticator o similar).
echo  Recomendado: anada el CIF del despacho al final del archivo .env.real en la linea OWN_TAX_IDS=
echo  y vuelva a ejecutar este archivo, para que la lectura de facturas no lo confunda con el del proveedor.
echo.
pause

:abrir
start "" "http://localhost:3000"
echo.
echo  Listo: instalacion REAL en http://localhost:3000
echo  Para apagarla: DETENER_REAL.bat.  Copia de seguridad: COPIA_SEGURIDAD_REAL.bat (hagala a diario).
echo.
pause
exit /b 0

:sin_docker
echo  No se encuentra Docker. Instale Docker Desktop y vuelva a ejecutar este archivo.
pause
exit /b 1
:docker_parado
echo  Docker Desktop no esta en marcha. Abralo, espere a "Engine running" y vuelva a ejecutar.
pause
exit /b 1
:lento
echo  Esta tardando mas de lo normal. Pruebe a abrir http://localhost:3000 en un minuto.
echo  Si no carga, envie a Claude el resultado de:  docker compose -p sistemapropio_real logs api
pause
exit /b 1
:error
echo.
echo  Algo ha fallado. Copie el texto de esta ventana y envieselo a Claude (no contiene sus datos).
pause
exit /b 1
