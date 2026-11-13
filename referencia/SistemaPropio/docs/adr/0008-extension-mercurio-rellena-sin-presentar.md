# ADR-0008 · Extensión de navegador que rellena Mercurio sin presentar

Fecha: 05/11/2026 · Estado: aceptada (Dirección aprueba T-24 el 05/11/2026)

## Contexto
Mercurio (presentación telemática de extranjería) no ofrece interfaz de programación. Los datos se escriben en
pestañas web; al final Mercurio genera el modelo EX, se adjuntan documentos y el profesional firma con AutoFirma y
su certificado. A-11 y D-09 prohíben envíos automáticos a portales oficiales.

## Decisión
1. **Ficha de datos por expediente** (`immig_form`): las claves (ext.apellido1, rep.email…) se derivan de los 16
   modelos EX oficiales editables (mapa generado por `scripts/ex_forms_build.py`, EX-10 revisado a mano) más los
   campos que Mercurio pide aparte (tipo de vía, municipio, escalera…). Se proponen desde el cliente, el pasaporte
   leído y los datos del despacho; **solo se usan los valores que una persona guarda**.
2. **Código temporal** de 12 caracteres (hash SHA-256 en BD, 15 minutos, 10 lecturas, un expediente) para que la
   extensión lea la ficha **sin sesión ni contraseña**. Cada lectura se audita.
3. **Extensión Chrome MV3** limitada a `mercurio.delegaciondelgobierno.gob.es`, con permiso solo de almacenamiento.
   Reconoce campos por etiqueta y apartado; rellena la pestaña visible; espera listas dependientes; no sobrescribe.
   **Nunca** pulsa botones, envía formularios, marca «NO CONSIENTO» ni elige el supuesto de autorización (prueba
   estática en `apps/web/tests/extension_mercurio.test.ts` y recorrido e2e).
4. El PDF EX que genera SISTEMA PROPIO es una **vista previa interna**; el oficial lo genera Mercurio.

## Consecuencias
- El reconocimiento depende del HTML de Mercurio, que puede cambiar: la extensión trae un **diagnóstico** que copia
  la estructura (sin valores) para ajustarlo. Validación sobre Mercurio real pendiente (T-27).
- Distribución: carga descomprimida en los equipos de quienes presentan; publicar en Chrome Web Store (privada) o
  por política de Google Workspace/Intune queda para cuando se use en producción (T-28).
