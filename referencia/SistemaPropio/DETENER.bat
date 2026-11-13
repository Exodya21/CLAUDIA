@echo off
cd /d "%~dp0"
echo  Deteniendo SISTEMA PROPIO (los datos ficticios se conservan)...
docker compose down
echo  Detenido.
pause
