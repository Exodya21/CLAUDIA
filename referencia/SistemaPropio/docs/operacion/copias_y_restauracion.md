# Copias de seguridad y restauración (AT-29)

## Qué hace una copia
1. `pg_dump` en formato personalizado a la carpeta `copias/` (archivo `sp_AAAAMMDDTHHMMSSZ.dump`).
2. **Restaura** esa copia completa en una base aparte (`<base>_comprobacion`), nunca en la base en uso.
3. La API comprueba en la base restaurada: que existe el esquema (versión de migraciones), que la **cadena de
   auditoría** se verifica entera y que su último evento **coincide** con el de la base en uso.
4. Registra el resultado en `backup_run` (tabla de solo inserción) y en la auditoría (`backup.verify`).
5. Conserva las 14 copias más recientes.

Una copia que no supera los tres controles aparece como **No válida** en Administración → Copias de seguridad.

## Windows (Docker Desktop)
- Con el sistema en marcha, doble clic en **`COPIA_SEGURIDAD.bat`**.
- Programarla a diario: Programador de tareas de Windows → Crear tarea básica → Diariamente → Iniciar un programa →
  `COPIA_SEGURIDAD.bat` (en «Iniciar en» ponga la carpeta del sistema). El ordenador y Docker Desktop deben estar
  encendidos a esa hora.
- **Copia externa**: la carpeta `copias/` está en el mismo ordenador. Con datos reales debe copiarse además a un
  destino cifrado fuera de él (decisión T-17).

## Linux / servidor
```bash
docker compose exec -T db sh /ops/copia.sh          # imprime el nombre del archivo
docker compose exec -T api python -m app.ops.backup verificar --archivo <nombre>
# Sin Docker (pg_dump/pg_restore instalados y RESTORE_DATABASE_URL definida):
python -m app.ops.backup completa
```
En Linux, la carpeta `copias/` debe ser escribible por el usuario `postgres` del contenedor (`chmod 777 copias` en
desarrollo, o propietario uid 999).

## Restaurar de verdad (desastre)
Solo con autorización de Dirección y anotándolo en la auditoría posteriormente.
1. `DETENER.bat` (o `docker compose stop api web`).
2. `docker compose up -d db`
3. `docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'`
4. `docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" --no-owner --exit-on-error -d "$POSTGRES_DB" /copias/<archivo>'`
5. `INICIAR.bat` y, en Ajustes → Auditoría, **Verificar integridad**.

## Primera instalación sin datos ficticios
```bash
python -m app.ops.primer_admin --usuario nombre.apellido --nombre "Nombre Apellidos" \
  --correo persona@despacho.es --entidad "Razón social" --crear-entidad
```
Imprime una contraseña provisional (una sola vez). Se niega si la entidad ya tiene administración.
