"""Reorganiza la plantilla «Ficha de entrevista inicial» sin cambiar el texto de ninguna celda.
Uso: python3 -I reorganizar.py document.xml"""
import sys,re,copy,unicodedata
from lxml import etree
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';N={'w':W};q=lambda t:'{%s}%s'%(W,t)
def norm(s):
    s=unicodedata.normalize('NFD',s or '');s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower()
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9ñ ]',' ',s)).strip()
path=sys.argv[1];tree=etree.parse(path);body=tree.getroot().find('w:body',N);E=list(body)
import os
_st=etree.parse(os.path.join(os.path.dirname(path),'styles.xml')).getroot()
H1S,H2S=set(),set()
for st in _st.findall('w:style',N):
    nm=norm((st.find('w:name',N).get(q('val')) if st.find('w:name',N) is not None else ''))
    if nm in('heading 1','titulo 1'):H1S.add(st.get(q('styleId')))
    if nm in('heading 2','titulo 2'):H2S.add(st.get(q('styleId')))
tx=lambda e:''.join(x.text or '' for x in e.iter(q('t'))).strip()
def sty(p):
    s=p.find('w:pPr/w:pStyle',N);return s.get(q('val')) if s is not None else ''
# localizar por texto (no por posición) los títulos y tablas de la plantilla
H1={};cur=None;secs={}
for el in E:
    if etree.QName(el).localname=='p' and sty(el) in H1S:
        cur=tx(el);secs[cur]=[];continue
    if cur is not None:secs[cur].append(el)
def h1k(pref):
    k=[x for x in secs if norm(x).startswith(norm(pref))];assert len(k)==1,(pref,k);return k[0]
def grupo(sec,h2):
    """elementos bajo un título 2 dentro de una sección (hasta el siguiente título 2)"""
    out=[];on=False
    for el in secs[h1k(sec)]:
        if etree.QName(el).localname=='p' and sty(el) in H2S:on=norm(tx(el))==norm(h2);continue
        if on:out.append(el)
    return out
def tabla(sec,h2=None):
    els=grupo(sec,h2) if h2 else secs[h1k(sec)]
    t=[e for e in els if etree.QName(e).localname=='tbl'];assert t,(sec,h2);return t[0]
P1=next(e for e in E if etree.QName(e).localname=='p' and sty(e) in H1S and tx(e).startswith('2.'))
P2=next(e for e in E if etree.QName(e).localname=='p' and sty(e) in H2S)
def titulo(t,tpl):
    p=copy.deepcopy(tpl);rs=p.findall('w:r',N)
    for r in rs[1:]:p.remove(r)
    ts=rs[0].findall('w:t',N)
    for x in ts[1:]:rs[0].remove(x)
    ts[0].text=t;return p
lab=lambda tr:norm(tx(tr.findall('w:tc',N)[0])) if tr.findall('w:tc',N) else ''
def filas(tbl,pred,cabecera=True):
    """copia de la tabla con la cabecera y las filas cuya primera celda cumple pred"""
    t=copy.deepcopy(tbl);rows=t.findall('w:tr',N)
    for i,r in enumerate(rows):
        if i==0 and cabecera and lab(r)=='pregunta':continue
        if not pred(lab(r)):t.remove(r)
    return t
empieza=lambda *ks:(lambda l:any(l.startswith(norm(k)) for k in ks))
no=lambda f:(lambda l:not f(l))
usados=set()
# --- tabla de datos del cliente (4 columnas) -> tablas de 2 columnas con la misma cabecera que las demás
cli=tabla('1. DATOS DEL CLIENTE');trat=tabla('3. TRATAMIENTO')
def tabla2(pares):
    t=copy.deepcopy(trat);rows=t.findall('w:tr',N);tplr=rows[1]
    for r in rows[1:]:t.remove(r)
    for lc,vc in pares:
        r=copy.deepcopy(tplr);cs=r.findall('w:tc',N)
        for c,src in zip(cs,(lc,vc)):
            for p in c.findall('w:p',N):c.remove(p)
            for p in src.findall('w:p',N):c.append(copy.deepcopy(p))
        t.append(r)
    return t
pares=[]
for r in cli.findall('w:tr',N):
    cs=r.findall('w:tc',N);i=0
    while i<len(cs):
        if tx(cs[i]):pares.append((cs[i],cs[i+1] if i+1<len(cs) else cs[i]))
        i+=2
P=lambda k:[x for x in pares if norm(tx(x[0])).startswith(norm(k))]
out=[]
add=out.extend
# ---------------- ENCABEZADO ----------------
out.append(titulo('ENCABEZADO',P1))
for n in range(1,6):
    out.append(titulo(f'Centro de trabajo {n}',P2));out.append(filas(tabla('7. LUGARES',f'Centro de trabajo {n}'),empieza('dirección')))
out.append(titulo('Tratamiento',P2));out.append(filas(trat,empieza('d d')))
out.append(titulo('Datos del cliente',P2));out.append(tabla2(P('nombre completo')+P('nif cif')))
# ---------------- DICE ----------------
out.append(titulo('DICE',P1))
DICE=empieza('d d','nombre completo','documentación de identificación','n º de identidad','n de identidad','dirección de notificación')
for n in range(1,6):
    out.append(titulo(f'Contrario {n}',P2));out.append(filas(tabla('5. EMPLEADORES',f'Contrario {n}'),DICE))
# ---------------- HECHOS ----------------
out.append(titulo('PRIMER HECHO',P1))
out.append(titulo('Vida laboral',P2));out.append(filas(tabla('6. FECHAS','Vida laboral'),empieza('¿cuándo empezó')))
out.append(titulo('Funciones pactadas',P2));out.append(copy.deepcopy(tabla('8. INFORMACIÓN','Funciones pactadas')))
out.append(titulo('SEGUNDO HECHO',P1))
out.append(titulo('Vida laboral',P2));out.append(filas(tabla('6. FECHAS','Vida laboral'),empieza('¿cuándo terminó')))
for h in ('Permiso de trabajo','Alta en la Seguridad Social'):out.append(titulo(h,P2));out.append(copy.deepcopy(tabla('6. FECHAS',h)))
out.append(titulo('TERCER HECHO',P1))
out.append(titulo('Tabla de jornada',P2));out.append(copy.deepcopy(tabla('9. JORNADA','Tabla de jornada')))
out.append(titulo('Comentarios',P2));out.append(copy.deepcopy(tabla('9. JORNADA','Comentarios')))
out.append(titulo('Jornada pactada',P2));out.append(copy.deepcopy(tabla('8. INFORMACIÓN','Jornada pactada')))
for n in range(1,6):
    out.append(titulo(f'Centro de trabajo {n}',P2));out.append(filas(tabla('7. LUGARES',f'Centro de trabajo {n}'),no(empieza('dirección'))))
out.append(titulo('CUARTO HECHO',P1))
for el in secs[h1k('10. LO PERCIBIDO')]:out.append(copy.deepcopy(el))
out.append(titulo('QUINTO HECHO',P1))
for h in ('Lo que dice el cliente','Despido','Por fallecimiento','Renuncia','Documentos recibidos'):out.append(titulo(h,P2));out.append(copy.deepcopy(tabla('13. FIN',h)))
out.append(titulo('SEXTO HECHO',P1))
out.append(titulo('Burofax',P2));out.append(copy.deepcopy(tabla('13. FIN','Burofax')))
# ---------------- RESTO (con sus títulos de siempre) ----------------
def resto_cli():
    o=[e for e in secs[h1k('1. DATOS')] if False];r=[x for x in pares if not norm(tx(x[0])).startswith(('nombre completo','nif cif'))]
    return [titulo('DATOS DEL CLIENTE',P1),tabla2(r)]
add(resto_cli())
for k in ('2. ANTES DE EMPEZAR',):
    out.append(titulo(re.sub(r'^\d+\.\s*','',k),P1));add(copy.deepcopy(e) for e in secs[h1k(k)])
out.append(titulo('TRATAMIENTO',P1));out.append(filas(trat,no(empieza('d d'))))
out.append(titulo('INFORMACIÓN DEL CLIENTE',P1));add(copy.deepcopy(e) for e in secs[h1k('4. INFORMACIÓN')])
out.append(titulo('EMPLEADORES / PARTES CONTRARIAS',P1))
for el in secs[h1k('5. EMPLEADORES')]:
    if etree.QName(el).localname=='p' and sty(el) not in H2S:out.append(copy.deepcopy(el))
for n in range(1,6):
    out.append(titulo(f'Contrario {n}',P2));out.append(filas(tabla('5. EMPLEADORES',f'Contrario {n}'),no(DICE)))
out.append(titulo('INFORMACIÓN CONTRACTUAL LABORAL',P1))
for h in ('Contratación','Salario pactado','Convenio colectivo','Pagas'):out.append(titulo(h,P2));out.append(copy.deepcopy(tabla('8. INFORMACIÓN',h)))
for k in ('11. VACACIONES','12. PAGAS','14. CRONOLOGÍA','DATOS DE LA ENTREVISTA'):
    out.append(titulo(re.sub(r'^\d+\.\s*','',next(x for x in secs if norm(x).startswith(norm(k)))),P1));add(copy.deepcopy(e) for e in secs[h1k(k)] if etree.QName(e).localname!='sectPr')
# montar el cuerpo: lo de antes del primer título 1 (cabecera del documento), lo nuevo y el sectPr
first=E.index(next(e for e in E if etree.QName(e).localname=='p' and sty(e) in H1S))
cab=E[:first];sect=body.find('w:sectPr',N)
for el in list(body):body.remove(el)
for el in out:
    if etree.QName(el).localname=='tbl':
        rows=el.findall('w:tr',N)
        if rows:
            for k in rows[-1].iter(q('keepNext')):k.getparent().remove(k)
for el in cab+out:body.append(el)
body.append(sect)
tree.write(path,xml_declaration=True,encoding='UTF-8',standalone=True)
# comprobación: mismas preguntas (primera celda de cada fila) antes y después
print('OK',len(out),'elementos')
