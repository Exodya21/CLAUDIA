# Odoo 20 Community del despacho · carpeta `odoo/`

Aquí está lo que se construye sobre **Odoo 20 Community** (decisión del 13/11/2026, documento 18):

| Carpeta / archivo | Qué es |
|---|---|
| `docker-compose.yml` | Odoo 20 + PostgreSQL 16 para pruebas en un ordenador con Docker Desktop |
| `configuracion/base_contable.py` | Monta la **base contable** (compañías, plan contable, diarios y series, bancos, cajas, analítica, cuentas propias, productos base, Verifactu en pruebas). Se puede repetir sin duplicar nada |
| `pruebas/prueba_base_contable.py` | Prueba con **datos ficticios**: facturas CIT y EXP, IVA, retención de IRPF, suplido, cobro parcial, rectificativa y Verifactu |
| `addons/sp_recepcion/` | **Recepción y cajas**: cobros con justificante por sede, aviso de repetidos, confirmación por Contabilidad, anulación con motivo y cierre de caja validado por otra persona |
| `configuracion/recepcion.py` | Crea las sedes (Barcelona, Madrid, Valencia) y usuarios de **demostración** para probar Recepción |
| `pruebas/prueba_recepcion.py` | Escenario de Recepción con datos ficticios (una vez, sobre una base recién montada) |
| `addons/` | Módulos propios `sp_*` (ver documento 19 §5) |

Todo usa **datos ficticios**. En la instalación real se cambian los valores del bloque CONFIGURACIÓN de
`base_contable.py` en el servidor, sin subirlos al repositorio.

## Montarlo en Windows (Docker Desktop)
En PowerShell, dentro de la carpeta `odoo` del repositorio. Un comando cada vez.

1. Arrancar Odoo 20:
   ```
   docker compose up -d
   ```
2. Crear la base de datos `sp_contable` con Contabilidad, la localización española y la colombiana y Verifactu
   (tarda unos minutos):
   ```
   docker compose exec odoo odoo -d sp_contable -i account,l10n_es,l10n_co,l10n_es_edi_verifactu --load-language=es_ES --stop-after-init --db_host=db -r odoo -w odoo
   ```
3. Montar la base contable:
   ```
   docker compose exec -T odoo odoo shell -d sp_contable --db_host=db -r odoo -w odoo --no-http < configuracion/base_contable.py
   ```
4. (Opcional) Pasar la prueba con datos ficticios:
   ```
   docker compose exec -T odoo odoo shell -d sp_contable --db_host=db -r odoo -w odoo --no-http < pruebas/prueba_base_contable.py
   ```
5. Abrir http://localhost:8069. Usuario `admin`, contraseña `admin` (**cámbiela** en Ajustes → Usuarios).
   Arriba a la derecha se elige la compañía: «Despacho S.L. (demo)» o «Filial Colombia (demo)».
   El autónomo del titular **queda fuera de Odoo** (AL-06, decidido provisionalmente el 13/11/2026): el script lo
   tiene desactivado (`"incluir": False` en `configuracion/base_contable.py`) y no lo crea.

### Recepción y cajas (módulo `sp_recepcion`)
6. Reiniciar Odoo para que vea los módulos nuevos de `addons/`:
   ```
   docker compose restart odoo
   ```
7. Instalar el módulo y pasar sus pruebas automáticas:
   ```
   docker compose exec odoo odoo -d sp_contable -i sp_recepcion --test-enable --test-tags /sp_recepcion --stop-after-init --no-http --db_host=db -r odoo -w odoo
   ```
8. Crear las sedes y los usuarios de demostración:
   ```
   docker compose exec -T odoo odoo shell -d sp_contable --db_host=db -r odoo -w odoo --no-http < configuracion/recepcion.py
   ```
9. (Opcional) Escenario completo con datos ficticios:
   ```
   docker compose exec -T odoo odoo shell -d sp_contable --db_host=db -r odoo -w odoo --no-http < pruebas/prueba_recepcion.py
   ```
En Facturación aparece el menú **Recepción** (Cobros, Cierres de caja, Sedes). Usuarios de demostración (contraseña =
usuario): `recepcion.bcn`, `recepcion.mad`, `recepcion.vlc` (Recepción) y `contabilidad.1`, `contabilidad.2`
(responsables). Son solo para la base de pruebas.

En Linux (entorno de Claude): `bash herramientas/odoo_dev.sh sp_recepcion` arranca todo y actualiza el módulo.

Para empezar de cero: `docker compose down -v` (borra la base de datos de pruebas) y repetir desde el paso 1.

## Qué monta la base contable
| Elemento | Despacho S.L. | Filial Colombia |
|---|---|---|
| Plan contable y moneda | PGC pymes · EUR | Plan colombiano · COP |
| Series de factura (sin saltos, rectificativas aparte) | `CIT/2026/…` citas web · `EXP/2026/…` expedientes | — |
| Bancos | Banco A · Laboral, Banco B · Extranjería, Banco C · Tesorería | Del plan |
| Cajas | Barcelona, Madrid, Valencia | — |
| Cuentas propias (provisionales, T-40) | 555001 suplidos · 555002 fondos de clientes en mediación (80 % cuota litis) | — |
| Verifactu | Activado en **entorno de pruebas** | — |

El autónomo del titular no es compañía en Odoo (AL-06): sus facturas a la S.L. se registran en la S.L. como facturas
de proveedor.

Analítica compartida: plan **Actividad** (Laboral, Extranjería, Compartida) y plan **Sede** (Barcelona, Madrid,
Valencia, Colombia). Productos base de ejemplo: consultas de 50 € y 40 €, honorarios, cuota litis y suplido sin IVA.

## Verifactu
- Está activado en el **entorno de pruebas de la AEAT**: no tiene efectos fiscales.
- La prueba carga el **certificado de pruebas público de la AEAT** que trae el propio Odoo (entidad ficticia).
  **Nunca** se usa ni se sube aquí un certificado real: el real lo carga en Odoo la persona autorizada del despacho,
  en Ajustes → Contabilidad → Veri*Factu.
- Para pasar a producción hay que seguir el plan del documento 19 §3.8 (validación con la gestoría incluida).
