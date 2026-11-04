---
name: convenio-a-markdown
description: Convierte el PDF (o Word) de un convenio colectivo a Markdown con markitdown, lo trocea por artículos con un índice y extrae los datos que necesita la ficha B (salario por categoría con el SMI como mínimo, pluses, jornada máxima, pagas extra, vacaciones y su base, clasificación profesional, mejoras de la incapacidad temporal, preaviso y su penalización), citando el artículo de cada dato. Úsala cuando suban un convenio en PDF o Word, o pidan analizar un convenio ya convertido.
---

# Convenio colectivo: PDF → Markdown → datos para la ficha

Los convenios tienen muchas páginas: no se leen enteros de una vez. Se convierten a Markdown, se indexan por artículos y se lee solo lo necesario.

Es orientación para el abogado, no un dictamen: cada dato lleva su artículo para que lo compruebe. No inventes cifras ni artículos; si algo no aparece, dilo.

## Paso 1 — Convertir

1. Cada convenio en su carpeta: `convenios/<codigo-o-nombre-corto>/`. Copia allí el PDF original sin tocarlo.
2. Convierte con markitdown (preinstalado; si falta: `pip install 'markitdown[pdf,docx]'`):
   ```bash
   markitdown "convenios/<carpeta>/original.pdf" -o "convenios/<carpeta>/convenio.md"
   ```
3. Comprueba el resultado: `wc -c` y mira el principio. Si sale casi vacío o con texto ilegible, el PDF es una imagen escaneada: dilo y, si hay OCR disponible (skill de PDF / `tesseract`), úsalo; si no, pide el texto publicado en el BOE o boletín (versión HTML).
4. Los PDF del BOE suelen traer cabeceras y pies repetidos («BOLETÍN OFICIAL DEL ESTADO», «Núm. …», «Sec. III. Pág. …», «cve: BOE-…», «Verificable en…»). Quítalos con el script del paso 2 (opción `--limpiar`).

## Paso 2 — Indexar por artículos

```bash
python3 .claude/skills/convenio-a-markdown/scripts/indexar.py "convenios/<carpeta>/convenio.md" --limpiar
```

Genera junto al Markdown:
- `convenio_limpio.md`: sin cabeceras ni pies de página del boletín.
- `indice.md`: cada capítulo, artículo, disposición y anexo con su línea de inicio y fin, y si contiene palabras clave (salario, plus, jornada, vacaciones, paga, incapacidad, preaviso, categoría, grupo profesional, tablas).

Usa el índice para leer solo los artículos que hacen falta (Read con `offset` y `limit`, o `sed -n 'inicio,finp'`).

## Paso 3 — Extraer los datos para la ficha

Busca y anota, con **artículo (o anexo) y cita literal breve** de cada dato:

| Dato | Qué buscar |
|---|---|
| Identificación | nombre oficial, código REGCON, ámbito funcional, territorial y personal, vigencia, ultraactividad, boletín y fecha |
| Clasificación profesional | grupos, niveles y categorías con sus funciones; qué datos deciden el encaje (funciones, titulación, autonomía) |
| Salario | tablas salariales por categoría y **año** (busca también revisiones salariales publicadas aparte); salario base mensual o anual y nº de pagas. Compara siempre con el **SMI** del año: lo que debía percibir es lo mayor de los dos |
| Pluses y complementos | antigüedad, transporte, nocturnidad, festivos, turnicidad, toxicidad, idiomas, manutención…: cuantía, si son salariales o extrasalariales, si se cobran en vacaciones y pagas |
| Jornada | jornada máxima anual y semanal, distribución irregular, descansos, horas extra (precio o compensación) |
| Pagas extraordinarias | cuántas, cuantía (salario base, base + antigüedad…), fechas de devengo y pago, si se pueden prorratear |
| Vacaciones | días al año (naturales o laborables), periodo, y **cómo se calcula su retribución** (qué conceptos entran) |
| Incapacidad temporal | complementos sobre la prestación (por ejemplo, hasta el 100 % desde el día X) por enfermedad y por accidente |
| Preaviso | días de preaviso de la persona trabajadora al dimitir según grupo y **penalización** si no se cumple (descuento en la liquidación); también el preaviso de la empresa si lo regula |
| Otros | indemnizaciones propias, ropa de trabajo, dietas, permisos retribuidos que mejoren el ET |

Si el salario está fijado **por días** (por ejemplo, en construcción: salario base por día natural, pluses por día trabajado), pásalo a cifras mensuales sin contar dos veces las vacaciones ni las pagas: `base_mensual` = salario base anual / 12; `pluses_mensuales` = todos los pluses fijos anuales (salariales y extrasalariales) / 12, para que la papeleta muestre «Salario base» y «Pluses» con su nombre; `paga_importe` = importe de cada paga extra de la tabla; `vacaciones_importe` = importe anual de las vacaciones de la tabla. Comprueba que base_mensual × 12 + pluses_mensuales × 12 + pagas × paga_importe + vacaciones_importe = total anual de la tabla.

Escribe dos archivos en la carpeta del convenio:
- `resumen.md`: los datos de la tabla anterior en lenguaje claro, con su artículo, y una lista de lo que **no aparece** o está **por verificar** (por ejemplo, tablas del año en curso no publicadas).
- `resumen.json`: los mismos datos en este formato, para cargarlos después en la ficha B:
  ```json
  {"convenio":{"nombre":"","codigo":"","ambito":"","vigencia":"","publicacion":"","enlace":""},
   "categorias":[{"grupo":"","categoria":"","funciones":"","salario":{"2026":{"base_mensual":0,"pluses_mensuales":0,"pagas":14,"paga_importe":0,"vacaciones_importe":0,"anual":0}},"articulo":""}],
   "pluses":[{"nombre":"","cuantia":"","tipo":"salarial|extrasalarial","en_vacaciones":true,"en_pagas":false,"articulo":""}],
   "jornada":{"anual_horas":0,"semanal_horas":0,"horas_extra":"","articulo":""},
   "pagas_extra":{"numero":0,"cuantia":"","devengo":"","prorrateables":true,"articulo":""},
   "vacaciones":{"dias":0,"tipo":"naturales|laborables","base_calculo":"","articulo":""},
   "incapacidad_temporal":{"enfermedad":"","accidente":"","articulo":""},
   "preaviso":{"dias_por_grupo":"","penalizacion":"","articulo":""},
   "otros":[],"no_encontrado":[],"por_verificar":[]}
  ```

## Reglas

- Los importes, con su año y su fuente (artículo o anexo, o resolución de revisión salarial con su boletín y fecha).
- Si el convenio remite a otro (por ejemplo, a uno estatal para la clasificación profesional), dilo y no lo completes de memoria.
- El SMI es el mínimo: si las tablas del convenio quedan por debajo para la jornada completa, manda el SMI (en cómputo anual).
- Para identificar qué convenio corresponde a una empresa, usa la skill `convenio-colectivo-aplicable`; esta solo procesa un convenio ya elegido.
- No guardes en el repositorio datos personales de clientes; los convenios son públicos y sí pueden guardarse.
