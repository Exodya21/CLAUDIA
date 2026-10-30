# Genera fuente/orgt.js a partir de la tabla de organismos (PDF del despacho). Requiere pdftotext.
# Uso: python3 herramientas/pdf_a_organismos.py "datos/Tabla de organismos de conciliacion.pdf"
import re,subprocess,json,unicodedata,sys,os
B=os.path.join(os.path.dirname(__file__),'..','fuente')
T=json.loads(open(os.path.join(B,'territorio.js'),encoding='utf-8').read()[len('window.TERR='):-1])
def n(x):x=unicodedata.normalize('NFD',x.upper().strip());return ''.join(c for c in x if unicodedata.category(c)!='Mn')
txt=subprocess.run(['pdftotext','-layout',sys.argv[1],'-'],capture_output=True,text=True).stdout
provn={n(v['n']):k for k,v in T['prov'].items()}
CC=['Comunidad Valenciana','Comunidad de Madrid','Castilla-La Mancha','Castilla y León','Región de Murcia','País Vasco','Andalucía','Asturias','Extremadura','Cataluña','Cantabria','Galicia','La Rioja','Canarias','Navarra','Aragón','BALEARES','Ceuta','Melilla']
org={}
for l in txt.split('\n'):
    l=l.strip()
    if not l or l.startswith('Nombre'):continue
    for c in CC:
        m=re.match(r'(.+?)\s+('+re.escape(c)+r')(?:\s+(.*))?$',l)
        if m:break
    name,cc,rest=m.group(1).strip(),m.group(2),(m.group(3) or '').strip()
    if n(name) in ('IBIZA','MALLORCA','MENORCA'):continue
    ps=re.split(r'\s{2,}',rest) if rest else []
    org[provn[n(name)]]={'nombre':name,'ccaa':cc,'enc':ps[0] if ps else '','secc':ps[1] if len(ps)>1 else ''}
open(os.path.join(B,'orgt.js'),'w',encoding='utf-8').write('window.ORGT={src:"MAPA - COMPETENCIAS TERRITORRIALES 8 (tabla de organismos del despacho)",p:'+json.dumps(org,ensure_ascii=False,separators=(',',':'))+'};')
print(len(org),'provincias')
