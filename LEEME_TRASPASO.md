# SUPER FICHA LABORAL · Traspaso del proyecto

Despacho Abogado Rafael Serrano · Ficha C «Empleada de hogar sin papeles» · Estado a 30/10/2026

## 1. Qué es y qué hace

Es una ficha de entrevista para el asesor (ubicado en Colombia, sin especialización en derecho laboral español). Hace tres cosas:

- Guía la entrevista paso a paso.
- Detecta lo que falta, las contradicciones y los plazos urgentes.
- Al terminar genera:
  - la **papeleta de conciliación** (borrador para el abogado), en Word y como texto;
  - la **ficha en Word**, con todas las preguntas y respuestas en orden, más un resumen para el abogado.

Es un **prototipo con datos ficticios**:

- No tiene usuarios, contraseñas ni almacenamiento seguro.
- Olvida todo al cerrarse; existe una «Copia de seguridad» en texto.
- No hay que usar datos reales hasta tener la infraestructura del punto 9.

- **Ficha publicada (enlace para probar):** https://claude.ai/artifact/L1wg7C1pD9tfKRyrJKELVZ
- **Archivo único con todo el código:** `super_ficha_laboral.html`. Se abre en cualquier navegador.

## 2. Contenido del paquete

| Carpeta / archivo | Qué es |
|---|---|
| `super_ficha_laboral.html` | La ficha completa, lista para usar (≈1,3 MB). |
| `fuente/head.html` | Estilos (CSS) y contenedores de la página. |
| `fuente/v5_original.js` | La ficha original v5 de la abogada. Se conserva entera; el abogado la abre desde el paso 9. |
| `fuente/app.js` | Pantalla de inicio, fichas A y B, utilidades comunes (`SF`). |
| `fuente/territorio.js` | Datos del Excel/CSV del mapa: 8.132 municipios con partido judicial, juzgado de lo social y sede MN. |
| `fuente/orgt.js` | Tabla de organismos de conciliación por provincia (del PDF del despacho). |
| `fuente/fc.js` | **Motor de la ficha C**: modelo de datos, cálculos, evaluación, plazos, papeleta y pruebas automáticas. |
| `fuente/fc_docx.js` | Generación de Word (papeleta y ficha) sin librerías externas. |
| `fuente/fc_ui.js` | Pantallas y botones de la ficha C. |
| `fuente/fc_import.js` | «Rellenar desde una ficha en Word»: lee el .docx, Claude lo interpreta (capacidad `sample` de la página publicada) y rellena solo las preguntas vacías; lista lo que falta. |
| `herramientas/construir.py` | Une `fuente/` en `super_ficha_laboral.html`. |
| `herramientas/csv_a_territorio.py` | Regenera `territorio.js` desde el CSV del mapa. |
| `herramientas/pdf_a_organismos.py` | Regenera `orgt.js` desde la tabla de organismos (PDF). |
| `pruebas/prueba_navegador_simulado.js` | Prueba de punta a punta sin navegador (Node + jsdom). |
| `datos/` | CSV del mapa, PDF de organismos y la papeleta de ejemplo (Word) que sirve de modelo de redacción. |

**Cómo modificar:**

1. Editar el archivo de `fuente/`.
2. Ejecutar `python3 herramientas/construir.py`.
3. Abrir el HTML.

**Pruebas automáticas:**

- Hay 119 y deben pasar todas.
- Para ejecutarlas, abrir la consola del navegador y escribir `SF.runTests()`, o ejecutar `node pruebas/prueba_navegador_simulado.js`, que necesita `npm i jsdom`.

## 3. Pasos de la ficha (orden actual)

0. **Filtro:**
   - ¿Otro abogado lleva el caso? Si dice que sí y no quiere que lo estudiemos, solo se guardan los datos de contacto.
   - Papeleta o demanda previas.
   - Qué quiere reclamar y cómo nos conoció.
1. **Cliente:**
   - D.ª o D.
   - Nombre y apellidos por separado.
   - Documento. Si es DNI o NIE, se comprueban el formato y la letra de control (también en las personas de la casa). Si es NIE o pasaporte, «¿qué país se lo dio?»; por defecto, el NIE lo emite España y el pasaporte su país.
   - País de nacionalidad. El gentilicio sale **siempre en femenino** («de nacionalidad peruana»).
   - Nacimiento con día, mes y año (1920 al año actual).
   - Teléfono: solo números, con prefijo y bandera, +34 por defecto.
   - Correo: obliga a la @ y quita los espacios; tiene un botón que abre el correo del asesor con un mensaje de comprobación.
   - Padrón, con el botón «Vive en la misma dirección del padrón».
   - Domicilio y dirección postal.
   - Cargo sindical.
2. **Empleadores y lugares** (orden pedido):
   1. Fechas de la relación.
   2. **Empleadores a demandar**, con todos sus datos, domicilio y fechas. Los coempleadores se añaden dentro del mismo empleador.
   3. Centros de trabajo.
   4. ¿Quién de los empleadores vivía en la casa?
   5. Relación laboral:
      - contrato;
      - autorización de trabajo, que es distinta del alta;
      - altas en la Seguridad Social, con el pago del mes del alta, marcado como importante.
3. **Tareas y cuidados:**
   - Otras personas de la casa: no empleadores, testigos, visitas.
   - Tareas.
   - Personas cuidadas, con:
     - dependencia y grado;
     - Alzheimer o demencia;
     - discapacidad reconocida;
     - movilidad y tarjeta sanitaria o DNI.
   - Los menores salen solo con su edad en la papeleta.
4. **Jornada:**
   - Periodos.
   - Semanas modelo con **turnos estilo calculadora**: días L–D, entrada, salida, efectivo o presencia, y descansos con horario o en minutos.
   - Bloque «solo internas»: hora real de fin, dónde dormía y si estaba disponible de noche.
5. **Salarios:**
   - Fijo o mes a mes.
   - Botón «Crear los meses del año de reclamación».
   - Por horas y precio de la hora.
   - Pagas extra.
   - Quién le entregaba el dinero, dónde y quién estaba delante.
   - Forma del último pago.
6. **Vacaciones:** periodos, y quién autorizaba descansos y vacaciones.
7. **¿Qué pasó con su trabajo?:**
   - despido, renuncia, fallecimiento, otro o sigue trabajando;
   - quién decidió y comunicó;
   - las 12 preguntas del despido;
   - «Describa lo que pasó el día del despido»;
   - burofax;
   - cronología.
8. **Pruebas:**
   - llaves y acceso a la casa (sin contraseñas);
   - audios;
   - si conserva el teléfono;
   - conversaciones con quien mandaba o pagaba;
   - una ficha por prueba, con varios archivos.
9. **Revisión:** pendientes, contradicciones, cálculos y tablas. En modo abogado incluye:
   - calificación y acumulación;
   - coempleadores;
   - sede y organismo;
   - comprobación del salario mínimo;
   - la ficha v5.
10. **Papeleta:**
    - borrador;
    - Word con el formato del despacho;
    - copia con formato y texto plano.

En cada pregunta hay «No lo sabe», «Añadir explicación libre» y marca de obligatoria.

## 4. Reglas de cálculo (no cambiar sin validar con el abogado)

- **Horas que se pagan (escrito de ejemplo):** 40 h de trabajo efectivo más hasta 20 h de presencia, y lo que pasa de 40 h efectivas cuenta como presencia. Tope de 60 h, que con el SMI de 2026 dan **2.136,75 €** (1.424,50 × 60 / 40). Función `FC.horasPag`.
- **SMI con prorrata:** mensual × 14 / 12.

  | Año | SMI | Estado |
  |---|---|---|
  | 2024 | 1.134 € | Verificado |
  | 2025 | 1.184 € | Verificado |
  | 2026 | 1.221 € | Verificado |
  | 2023 | 1.080 € | **Sin verificar**: el abogado debe confirmarlo; mientras tanto ese año no se calcula |

- **Tabla 1 · diferencias salariales:**
  - Mes a mes, con lo que debía percibir y lo que percibió.
  - Un mes incompleto va en proporción y con sus días («Septiembre 2026 (15 días)»), **siempre dividiendo entre 30** (18 días de agosto = salario × 18 / 30), también en lo percibido con salario fijo y en el mes del alta.
  - Un mes sin datos **no** cuenta como impagado; solo cuenta si se marca «No cobró».
- **Año de reclamación:**
  - Empieza el mismo mes del año anterior a hoy, o en el inicio de la relación si es más reciente.
  - Termina siempre en el fin de la relación.
  - Los meses anteriores quedan fuera salvo que el abogado los incluya.
  - Función `FC.ventana`.
- **Tabla 2 · vacaciones:**
  - 30 días al año en proporción a lo trabajado (**días trabajados × 30 / 360**, con un máximo de 30 por año y **redondeado a 2 decimales** antes de multiplicar), menos los disfrutados.
  - Base = SMI con prorrata × horas semanales / 40, con un **máximo de 40 horas** (el abogado puede cambiar las horas base).
  - **Suma todos los años.**
  - **Dos formas de descontar:** restar los días disfrutados, o restar el dinero pagado por vacaciones (sin restar días). Si hay de las dos, se calculan ambas, se muestran juntas (en Vacaciones y en la revisión) y se usa la que da más, salvo que se elija otra. La tabla de la papeleta muestra «Días disfrutados» o «Pagado» según la forma usada.
- **Meses de interés (cada uno con su propia tabla y su párrafo en la papeleta, y su tabla en la revisión):**
  - **Último mes trabajado:** se pregunta en Salarios, concepto por concepto (salario de los días trabajados, vacaciones pendientes, pagas extra, indemnización y otros). Solo el salario de los días entra como «percibido» del mes; vacaciones, pagas extra y otros se descuentan como «abonado al finalizar»; la indemnización no se descuenta. «No le pagaron» = 0 €.
  - **Mes del alta** (si antes trabajaba sin alta): bruto, neto y fechas que cubría el pago. Percibido = bruto (o neto si no hay bruto); debía percibir = el del periodo. Si el periodo no cubre meses completos, sale una contradicción para revisarlo.
  - Sus diferencias se suman en los totales en líneas propias.
- **Tabla 1 de la papeleta:** no incluye los meses cobrados correctamente (diferencia 0 o negativa); van en el párrafo «En los devengos correspondientes de salario base más el complemento a salario base del año … de … la demandante percibió lo correspondiente al convenio aplicable.», agrupados por año.
- **Totales:**
  - Diferencias + vacaciones (+ otras deudas − lo abonado al finalizar) = total principal.
  - Mora del 10 %.
  - Total pendiente, con el importe en letra (`FC.letras`).
- **Jornada:**
  - Los turnos pueden cruzar medianoche.
  - Los descansos con horario se descuentan, también los de madrugada.
  - Las horas nocturnas van de 22 a 6.
  - Avisos del RD 1620/2011: más de 40 h efectivas, más de 20 h de presencia, menos de 12 h entre jornadas (10 h si es interna) y menos de 36 h de descanso semanal.
- **Plazos del despido:**
  - 20 días hábiles, contados de lunes a viernes y sin festivos, como estimación prudente. **Nunca** se da una fecha de caducidad definitiva.
  - La papeleta suspende el plazo.
  - La alerta urgente sale aunque falten otros datos.
- **Autorización de trabajo:**
  - Se calculan los días con y sin autorización.
  - Es distinta del alta en la Seguridad Social y nunca se confunden.

## 5. Territorio (juzgado y organismo)

- **Dirección:** se elige provincia y luego municipio en un desplegable con los municipios del CSV. El código postal rellena la provincia, y el **juzgado de lo social** (columna SOCIAL) se muestra solo.
- **Google Maps:**
  - El botón abre la búsqueda con vía, número, portal, código postal, municipio y provincia; no usa escalera, piso ni puerta.
  - El asesor marca «comprobada».
  - Si luego cambia algún dato que entra en la búsqueda, la marca se quita sola.
  - **No es automático:** necesita una clave de la API de Google y un servidor.
- **Organismo de conciliación:**
  - Sale automáticamente de la tabla del despacho, según la **provincia del lugar de trabajo**.
  - Si el abogado elige el domicilio del empleador (art. 10.1 LRJS), cambia al organismo de esa provincia.
  - Ceuta y Melilla no tienen organismo en la tabla: la papeleta sale con «PENDIENTE DE VALIDACIÓN TERRITORIAL».
- **Posibles erratas de la tabla, a confirmar por el despacho:**
  - Canarias: «CONOCIMIENTO YEMPLEO».
  - País Vasco: «SECCIÓN DE CONCILACIONES».

## 6. Papeleta: reglas de redacción

- **Párrafos:**
  - Se usan los del **escrito de ejemplo** (`datos/`).
  - Las frases nuevas salen marcadas «Variante nueva: pendiente de aprobación».
  - **No inventar redacción general.**
  - No incluir súplica ni firma: van en el «otro sí».
- **Formato Word:**
  - Arial 12, justificado, sangría de primera línea de 1,24 cm, 8 pt después e interlineado 1,5.
  - Fechas en formato 01.01.2026; meses en texto («ENERO DEL 2026»).
  - Medianoche como «24:00h».
- **Tratamiento:** D.ª o D.
- **Varios empleadores:** todo en plural («los empleadores despidieron»).
- **DICE (cuatro fórmulas):**
  - DESPIDO IMPROCEDENTE CON ACUMULACIÓN DE RECLAMACIÓN DE CANTIDAD.
  - DESPIDO NULO POR VULNERACIÓN DE DERECHOS FUNDAMENTALES Y SUBSIDIARIAMENTE IMPROCEDENTE, CON ACUMULACIÓN DE ACCIÓN DE RECLAMACIÓN DE CANTIDAD.
  - RECLAMACIÓN DE CANTIDAD.
  - DESPIDO IMPROCEDENTE.
  - Si el abogado no elige: despido improcedente, con acumulación si hay cantidades.
- **Coempleadores:** los familiares marcados por el asesor entran por defecto (párrafo «Cabe señalar…»), y el abogado puede quitarlos.
- **Jornada:**
  - Sin día libre: «sin disfrutar de ningún día de descanso semanal».
  - Contrato verbal con autorización y sin alta: «…, sin haberse procedido a la correspondiente alta…».
- **Salario variable:** los meses iguales se agrupan; si todos son iguales, se usa la frase fija del ejemplo.
- **Tablas:**
  - Tabla 1 con título y periodo, cabecera gris y fila «Total diferencia salarial».
  - Tabla 2 con el mismo estilo.
  - Tabla de totales con mora.
- **Envío:** la papeleta **nunca se envía automáticamente**. La validación jurídica es solo del abogado.

## 7. Modelo de datos (preparado para MNProgram)

- **Estructura:**
  - Cada ficha es un objeto con `id` estable (`F-AAAAMMDD-XXXX`), `v:2` y `c` (contenido).
  - Las personas tienen id propio y el resto de la ficha las referencia; un nombre no se escribe dos veces.
  - Las capas están separadas: lo que declara el cliente, los cálculos (`FC.calcT1`, `FC.calcT2`, `FC.calcJ`) y las decisiones del abogado (`c.abg`).
- **Integración con MNProgram:**
  - Está prevista: sede MN del municipio y abreviatura del CSV.
  - **No existe todavía ninguna conexión**, y no hay endpoints comprobados.

## 8. Pendiente o a validar por el abogado

- **Textos:** aprobar las variantes nuevas que salen marcadas, sobre todo la jornada con horarios distintos según el día, la modalidad por horas y el despido por WhatsApp.
- **Reglas de cálculo:**
  - Confirmar el SMI de 2023.
  - Indemnización del hogar: 33 días por año con tope de 24 mensualidades (tras el RDL 16/2022).
  - Fallecimiento: un mes.
  - Compensación entre meses pagados por encima del mínimo.
  - Descontar lo abonado al finalizar en los totales.
- **Erratas de la tabla de organismos:** las dos citadas en el punto 5.
- **«Otras personas de la casa»:** confirmar si se quedan en el paso 3.

## 9. Lo que necesita infraestructura de producción

- **Acceso y seguridad:**
  - Usuarios con contraseña y roles (asesor, abogado). Solo el abogado valida y edita lo jurídico.
  - Almacenamiento seguro de las fichas, con historial de cambios: autor, fecha y valor anterior.
  - Gestión documental protegida: archivos de pruebas guardados y vinculados de verdad. Ahora solo existen en la memoria del navegador.
- **Servicios externos:**
  - Envío real del correo de comprobación (servidor de correo).
  - Validación automática de direcciones (API de Google Maps con clave).
  - Integración con MNProgram (identificador de cliente y de expediente).
- **Calendario:** festivos por comunidad para afinar los plazos.

## 10. Criterios que se han seguido (para no romperlos)

- No convertir lo que declara el cliente en hechos probados.
- No calcular plazos definitivos con fórmulas simplificadas.
- No inventar municipios, competencias ni denominaciones de organismos.
- No poner botones que no funcionen.
- No pedir contraseñas reales.
- No enviar escritos automáticamente.
- Las horas de los turnos y los meses de la tabla de salarios se dejan como están: el despacho lo pidió expresamente.
