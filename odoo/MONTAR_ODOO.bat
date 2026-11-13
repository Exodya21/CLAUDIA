@echo off
setlocal
title Odoo 20 del despacho - entorno de PRUEBAS (datos ficticios)
cd /d "%~dp0"
echo.
echo  ODOO 20 COMMUNITY DEL DESPACHO - entorno de pruebas con DATOS FICTICIOS
echo  ======================================================================
echo.
where docker >nul 2>nul
if errorlevel 1 goto :sin_docker
docker info >nul 2>nul
if errorlevel 1 goto :docker_parado

echo  1/4 Construyendo y arrancando Odoo 20 (la primera vez tarda varios minutos)...
docker compose up -d --build
if errorlevel 1 goto :error

echo  2/4 Esperando a la base de datos...
:espera
docker compose exec -T db pg_isready -U odoo >nul 2>nul
if errorlevel 1 ( timeout /t 2 /nobreak >nul & goto :espera )

docker compose exec -T db psql -U odoo -lqt | findstr /c:"sp_contable" >nul
if not errorlevel 1 goto :ya_existe

echo  3/4 Creando la base sp_contable con Contabilidad, Espana, Colombia y Verifactu...
docker compose exec -T odoo odoo -d sp_contable -i account,l10n_es,l10n_co,l10n_es_edi_verifactu --load-language=es_ES --stop-after-init --no-http --db_host=db -r odoo -w odoo
if errorlevel 1 goto :error
docker compose exec -T odoo odoo shell -d sp_contable --db_host=db -r odoo -w odoo --no-http < configuracion\base_contable.py
docker compose restart odoo
echo      Instalando los modulos del despacho (Recepcion, Contabilidad y Gastos)...
docker compose exec -T odoo odoo -d sp_contable -i sp_recepcion,sp_contabilidad,sp_gastos --stop-after-init --no-http --db_host=db -r odoo -w odoo
if errorlevel 1 goto :error
docker compose exec -T odoo odoo shell -d sp_contable --db_host=db -r odoo -w odoo --no-http < configuracion\recepcion.py
docker compose exec -T odoo odoo shell -d sp_contable --db_host=db -r odoo -w odoo --no-http < configuracion\gastos.py
goto :abrir

:ya_existe
echo  3/4 La base sp_contable ya existe: se actualizan los modulos del despacho...
docker compose exec -T odoo odoo -d sp_contable -u sp_recepcion,sp_contabilidad,sp_gastos --stop-after-init --no-http --db_host=db -r odoo -w odoo

:abrir
echo  4/4 Reiniciando Odoo...
docker compose restart odoo
timeout /t 10 /nobreak >nul
start "" "http://localhost:8069"
echo.
echo  Listo: http://localhost:8069
echo   - Administrador: admin / admin  (cambie la contrasena)
echo   - Usuarios de demostracion (contrasena = usuario): recepcion.bcn, recepcion.mad, recepcion.vlc,
echo     contabilidad.1, contabilidad.2, atc.demo, letrado.demo
echo  Para empezar de cero: docker compose down -v   y vuelva a ejecutar este archivo.
echo.
pause
exit /b 0

:sin_docker
echo  No se encuentra Docker. Instale Docker Desktop y vuelva a ejecutar este archivo.
pause
exit /b 1
:docker_parado
echo  Docker Desktop no esta en marcha. Abralo, espere a "Engine running" y vuelva a ejecutar este archivo.
pause
exit /b 1
:error
echo.
echo  Algo ha fallado. Copie el texto de esta ventana y envieselo a Claude.
pause
exit /b 1
