@echo off
cd /d "%~dp0"
echo  Deteniendo la instalacion REAL (sus datos se conservan)...
docker compose -p sistemapropio_real --env-file .env.real down
echo  Detenido.
pause
