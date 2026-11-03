"""Construye el Excel de preguntas y respuestas de la Superficha: una hoja por bloque.
Uso: python3 -I excel.py preguntas.json salida.xlsx"""
import json, re, sys
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.table import Table, TableStyleInfo

src, out = sys.argv[1], sys.argv[2]
pasos = json.load(open(src, encoding='utf-8'))

# preguntas que solo aparecen al escribir un valor (el recorrido automático no escribe) y ajustes de grupo
def it(label, tipo, ops=(), grupo='', aparece='Según otra respuesta', req=False, help='', sec=''):
    return dict(sec=sec, grupo=grupo, label=label, tipo=tipo, ops=list(ops), min='', max='', req=req, ns=False, help=help, aparece=aparece)
FORMAS = ['Efectivo', 'Transferencia', 'Bizum', 'Con nómina', 'Otra']
EXTRA = {
    4: [('Periodo de jornada|Lugar de trabajo', it('Días de la semana del turno', 'Varias opciones', ['L', 'M', 'X', 'J', 'V', 'S', 'D'], 'Turno', 'Al añadir: Turno'))],
    5: [('|Otros conceptos (euros)', it('¿Qué otros conceptos?', 'Texto', aparece='Si se pone un importe en «Otros conceptos»')),
        ('|Al terminar el trabajo, ¿cómo le pagaron el último salario?', [
            it('Importe bruto (euros)', 'Número', grupo='Mes en que la dieron de alta', aparece='Si la fecha de alta es posterior al inicio del trabajo', help='Antes trabajaba sin alta. Pregunte cuánto le pagaron ese mes, en bruto y en neto, y de qué fecha a qué fecha era ese pago.'),
            it('Importe neto (euros)', 'Número', grupo='Mes en que la dieron de alta', aparece='Si la fecha de alta es posterior al inicio del trabajo'),
            it('El pago era desde', 'Fecha (día, mes y año)', grupo='Mes en que la dieron de alta', aparece='Si la fecha de alta es posterior al inicio del trabajo'),
            it('Hasta', 'Fecha (día, mes y año)', grupo='Mes en que la dieron de alta', aparece='Si la fecha de alta es posterior al inicio del trabajo'),
            it('¿Qué día se lo pagaron?', 'Fecha (día, mes y año)', grupo='Mes en que la dieron de alta', aparece='Si la fecha de alta es posterior al inicio del trabajo'),
            it('¿Cómo se lo pagaron?', 'Desplegable', FORMAS, grupo='Mes en que la dieron de alta', aparece='Si la fecha de alta es posterior al inicio del trabajo'),
            it('Observaciones del pago (si cambió algo al darla de alta)', 'Texto', grupo='Mes en que la dieron de alta', aparece='Si la fecha de alta es posterior al inicio del trabajo')])],
    6: [('Periodo de vacaciones|¿Se las pagaron?', it('¿Cuánto le pagaron? (€)', 'Número', grupo='Periodo de vacaciones', aparece='Si «¿Se las pagaron?» = Sí')),
        ('|¿Quién podía darle o cambiarle los descansos y las vacaciones?', it('¿Cuál se usa en la tabla de vacaciones?', 'Una opción', ['Restar los días disfrutados (con su total)', 'Restar el dinero pagado (con su total)'], aparece='Si hay a la vez días disfrutados y dinero pagado por vacaciones', help='Muestra el total de las dos formas y marca la mayor. Mientras no se elija, se usa la que da más.'))],
    9: [('|¿Se acumula la reclamación de cantidad?', [
            it('Otras personas como empleadoras: citar también a cada una', 'Casillas (una por persona)', ['(las otras personas empleadoras apuntadas en la ficha)'], aparece='Solo en modo abogado, si hay otras personas empleadoras'),
            it('Sede judicial (resultado A, según el mapa)', 'Una opción', ['(los lugares de trabajo y domicilios de los empleadores con municipio del mapa)'], aparece='Solo en modo abogado'),
            it('Organismo de conciliación (resultado B): corrección del abogado', 'Texto (dos líneas del encabezamiento)', aparece='Solo en modo abogado'),
            it('Salario mínimo por año: «Lo he comprobado en el BOE»', 'Casilla (una por año sin verificar)', aparece='Solo en modo abogado')]),
        ('|Horas base de las vacaciones (vacío = las reales, con topes)', [
            it('Incluir meses y años de más de un año', 'Casilla', aparece='Solo en modo abogado'),
            it('Contar el segundo salario del mismo empleador', 'Casilla', aparece='Solo en modo abogado'),
            it('Datos del despacho para notificaciones: domicilio', 'Texto', aparece='Solo en modo abogado'),
            it('Datos del despacho para notificaciones: teléfono', 'Texto', aparece='Solo en modo abogado'),
            it('Datos del despacho para notificaciones: correo', 'Texto', aparece='Solo en modo abogado')])],
}
TURNO = {'Entrada', 'Salida', 'Tipo de horas', 'Descanso en minutos', 'Tareas especiales'}
for pq in pasos:
    for x in pq['items']:
        if pq['paso'] == 4 and not x['grupo'] and x['label'] in TURNO:
            x['grupo'], x['aparece'] = 'Turno', 'Al añadir: Turno'
        if pq['paso'] == 4 and not x['grupo'] and x['label'] in ('Descanso desde', 'Descanso hasta'):
            x['grupo'], x['aparece'] = 'Descanso del turno', 'Al añadir: Descanso del turno'
        if pq['paso'] == 4 and x['label'] in ('¿A qué hora terminaba realmente sus tareas habituales?', '¿Dónde dormía dentro de la vivienda?', 'Después de acostarse, ¿tenía que estar disponible por si la necesitaban?'):
            x['aparece'] = 'Solo si la modalidad es «Interna»'
    for after, new in EXTRA.get(pq['paso'], []):
        g, lab = after.split('|')
        pos = next((i for i, x in enumerate(pq['items']) if x['label'] == lab and (not g or x['grupo'] == g)), None)
        assert pos is not None, (pq['paso'], after)
        pq['items'][pos + 1:pos + 1] = new if isinstance(new, list) else [new]

F = 'Arial'
fh = Font(name=F, bold=True, color='FFFFFF', size=10)
fb = Font(name=F, size=10)
ft = Font(name=F, bold=True, size=14)
fs = Font(name=F, italic=True, size=9, color='595959')
fill_h = PatternFill('solid', fgColor='0B5D4B')
wrap = Alignment(wrap_text=True, vertical='top')
COLS = [('Nº', 6), ('Apartado', 24), ('Grupo (repetible)', 20), ('Pregunta', 46), ('Tipo de respuesta', 22),
        ('Respuestas posibles', 52), ('Obligatoria', 11), ('Admite «No lo sabe»', 13), ('Cuándo aparece', 26), ('Ayuda que ve el asesor', 50)]


def nombre_hoja(i, n):
    n = re.sub(r'[\\/*?:\[\]¿]', '', n).strip()
    return f'{i} {n}'[:31]


wb = Workbook()
wb.remove(wb.active)
idx = wb.create_sheet('Índice')
idx['A1'] = 'Superficha laboral · Ficha C · Preguntas y respuestas'
idx['A1'].font = ft
idx['A2'] = ('Una hoja por bloque (paso de la ficha), en el orden en que aparecen. '
             '«Cuándo aparece»: «Siempre» = se ve con la ficha vacía; «Según otra respuesta» = depende de lo contestado antes; '
             '«Al añadir: …» = está dentro de un elemento que se añade (empleador, lugar, periodo…); «Solo en modo abogado».')
idx['A2'].font = fs
idx['A2'].alignment = wrap
idx.merge_cells('A2:C2')
idx.row_dimensions[2].height = 48
for c, (h, w) in enumerate([('Paso', 8), ('Bloque', 34), ('Nº de preguntas', 16)], 1):
    cell = idx.cell(row=4, column=c, value=h)
    cell.font, cell.fill = fh, fill_h
    idx.column_dimensions[cell.column_letter].width = w
r0 = 5
for p in pasos:
    if not p['items']:
        continue
    ws = wb.create_sheet(nombre_hoja(p['paso'], p['nombre']))
    ws['A1'] = f"Paso {p['paso']} · {p['nombre']}"
    ws['A1'].font = ft
    for c, (h, w) in enumerate(COLS, 1):
        cell = ws.cell(row=3, column=c, value=h)
        cell.font, cell.fill, cell.alignment = fh, fill_h, Alignment(wrap_text=True, vertical='center')
        ws.column_dimensions[cell.column_letter].width = w
    for n, it in enumerate(p['items'], 1):
        tipo = it['tipo']
        if it.get('max'):
            tipo += f" (de {it.get('min') or '…'} a {it.get('max') or '…'})"
        vals = [n, it['sec'], it['grupo'], it['label'], tipo, '\n'.join(it['ops']), 'Sí' if it['req'] else 'No',
                'Sí' if it['ns'] else 'No', it['aparece'], it['help']]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(row=3 + n, column=c, value=v)
            cell.font, cell.alignment = fb, wrap
    last = 3 + len(p['items'])
    t = Table(displayName=f"Paso{p['paso']}", ref=f"A3:J{last}")
    t.tableStyleInfo = TableStyleInfo(name='TableStyleLight9', showRowStripes=True)
    ws.add_table(t)
    ws.freeze_panes = 'E4'
    idx.cell(row=r0, column=1, value=p['paso']).font = fb
    link = idx.cell(row=r0, column=2, value=p['nombre'])
    link.hyperlink = f"#'{ws.title}'!A1"
    link.font = Font(name=F, size=10, color='0563C1', underline='single')
    idx.cell(row=r0, column=3, value=f"=COUNTA('{ws.title}'!D4:D{last})").font = fb
    r0 += 1
idx.cell(row=r0, column=2, value='Total').font = Font(name=F, bold=True, size=10)
idx.cell(row=r0, column=3, value=f'=SUM(C5:C{r0-1})').font = Font(name=F, bold=True, size=10)
# ---- hoja «Respuestas clave»: las preguntas elegidas por el despacho, para ver las respuestas de un vistazo ----
SEL = {0: [6, 8, 10], 1: list(range(1, 9)) + list(range(10, 19)), 2: [1, 2] + list(range(16, 33)) + list(range(34, 38)),
       3: list(range(1, 15)) + list(range(18, 37))}
CALC = {4: [('Total de horas a la semana de la jornada laboral', 'Horas efectivas y de presencia por semana, según los turnos de la jornada')],
        5: [('Diferencias salariales de los meses', 'Total de la tabla 1'), ('Diferencia del mes del alta en la Seguridad Social', 'Tabla propia del mes del alta'),
            ('Diferencia del último mes trabajado', 'Tabla propia del último mes'), ('Pagas extra', 'Pagas extra pendientes'),
            ('Vacaciones', 'Total de la tabla 2'), ('Otros', 'Otras cantidades adeudadas (− lo abonado al finalizar)'),
            ('Total', 'Total principal'), ('Total + mora', 'Total pendiente con la mora del 10 %')],
        6: [('Días disfrutados o pagados sin disfrutar', 'Según la forma de descontar elegida (días o dinero)')],
        7: [('Descripción del fin de la relación laboral', 'Qué pasó, fecha y cómo se lo comunicaron')]}
TIPOS_PRUEBA = next(x['ops'] for x in pasos[8]['items'] if x['label'] == 'Tipo')
rk = wb.create_sheet('Respuestas clave', 1)
rk['A1'] = 'Respuestas clave de la ficha'
rk['A1'].font = ft
rk['A2'] = ('Las preguntas que el despacho quiere ver de un vistazo. Rellene la columna amarilla «Respuesta». '
            '«Nº» es el número de la pregunta en la hoja de su bloque. Las filas «Dato calculado» las calcula la ficha.')
rk['A2'].font, rk['A2'].alignment = fs, wrap
rk.merge_cells('A2:G2')
rk.row_dimensions[2].height = 30
HK = [('Bloque', 22), ('Nº', 6), ('Grupo (repetible)', 22), ('Pregunta o dato', 46), ('Tipo', 22), ('Respuestas posibles / de dónde sale', 44), ('Respuesta', 40)]
for c, (h, w) in enumerate(HK, 1):
    cell = rk.cell(row=4, column=c, value=h)
    cell.font, cell.fill, cell.alignment = fh, fill_h, Alignment(wrap_text=True, vertical='center')
    rk.column_dimensions[cell.column_letter].width = w
fill_in = PatternFill('solid', fgColor='FFF2CC')
r = 5
def fila(vals):
    global r
    for c, v in enumerate(vals, 1):
        cell = rk.cell(row=r, column=c, value=v)
        cell.font, cell.alignment = fb, wrap
    rk.cell(row=r, column=7).fill = fill_in
    r += 1
for pq in pasos:
    blo = f"{pq['paso']} {pq['nombre']}"
    for n in SEL.get(pq['paso'], []):
        x = pq['items'][n - 1]
        fila([blo, n, x['grupo'], x['label'], x['tipo'], '\n'.join(x['ops']), None])
    for lab, de in CALC.get(pq['paso'], []):
        fila([blo, None, None, lab, 'Dato calculado', de, None])
    if pq['paso'] == 8:
        for t in TIPOS_PRUEBA:
            fila([blo, None, 'Checklist de tipo de pruebas', t, 'Sí / No', '¿Hay alguna prueba de este tipo?', None])
tk = Table(displayName='RespuestasClave', ref=f'A4:G{r-1}')
tk.tableStyleInfo = TableStyleInfo(name='TableStyleLight9', showRowStripes=False)
rk.add_table(tk)
rk.freeze_panes = 'E5'
from openpyxl.worksheet.datavalidation import DataValidation
dv = DataValidation(type='list', formula1='"Sí,No"', allow_blank=True)
rk.add_data_validation(dv)
for rr in range(5, r):
    if rk.cell(row=rr, column=5).value == 'Sí / No':
        dv.add(rk.cell(row=rr, column=7))
idx.cell(row=4, column=4, value='Respuestas clave').font = fh
idx.cell(row=4, column=4).fill = fill_h
idx.column_dimensions['D'].width = 22
lk = idx.cell(row=5, column=4, value='Ver la hoja')
lk.hyperlink = "#'Respuestas clave'!A1"
lk.font = Font(name=F, size=10, color='0563C1', underline='single')
wb.save(out)
print('OK', out)
