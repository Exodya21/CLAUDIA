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
wb.save(out)
print('OK', out)
