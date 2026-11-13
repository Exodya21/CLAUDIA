# Odoo 20 Community del despacho · carpeta `odoo/`

Aquí está lo que se construye sobre **Odoo 20 Community** (decisión del 13/11/2026, documento 18):

| Carpeta / archivo | Qué es |
|---|---|
| `docker-compose.yml` | Odoo 20 + PostgreSQL 16 para pruebas en un ordenador con Docker Desktop |
| `configuracion/base_contable.py` | Monta la **base contable** (compañías, plan contable, diarios y series, bancos, cajas, analítica, cuentas propias, productos base, Verifactu en pruebas). Se puede repetir sin duplicar nada |
| `pruebas/prueba_base_contable.py` | Prueba con **datos ficticios**: facturas CIT y EXP, IVA, retención de IRPF, suplido, cobro parcial, rectificativa y Verifactu |
| `addons/` | Módulos propios `sp_*` (se irán añadiendo; ver documento 19 §5) |

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
   Arriba a la derecha se elige la compañía: «Despacho S.L. (demo)», «Autónomo del titular (demo)» o «Filial
   Colombia (demo)».

Para empezar de cero: `docker compose down -v` (borra la base de datos de pruebas) y repetir desde el paso 1.

## Qué monta la base contable
| Elemento | Despacho S.L. | Autónomo (AL-06 abierto) | Filial Colombia |
|---|---|---|---|
| Plan contable y moneda | PGC pymes · EUR | PGC pymes · EUR | Plan colombiano · COP |
| Series de factura (sin saltos, rectificativas aparte) | `CIT/2026/…` citas web · `EXP/2026/…` expedientes | Igual | — |
| Bancos | Banco A · Laboral, Banco B · Extranjería, Banco C · Tesorería | Banco A | Del plan |
| Cajas | Barcelona, Madrid, Valencia | Barcelona | — |
| Cuentas propias (provisionales, T-40) | 555001 suplidos · 555002 fondos de clientes en mediación (80 % cuota litis) | Igual | — |
| Verifactu | Activado en **entorno de pruebas** | Igual | — |

Analítica compartida: plan **Actividad** (Laboral, Extranjería, Compartida) y plan **Sede** (Barcelona, Madrid,
Valencia, Colombia). Productos base de ejemplo: consultas de 50 € y 40 €, honorarios, cuota litis y suplido sin IVA.

## Verifactu
- Está activado en el **entorno de pruebas de la AEAT**: no tiene efectos fiscales.
- La prueba carga el **certificado de pruebas público de la AEAT** que trae el propio Odoo (entidad ficticia).
  **Nunca** se usa ni se sube aquí un certificado real: el real lo carga en Odoo la persona autorizada del despacho,
  en Ajustes → Contabilidad → Veri*Factu.
- Para pasar a producción hay que seguir el plan del documento 19 §3.8 (validación con la gestoría incluida).
