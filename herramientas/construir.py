# Une las piezas de /fuente en un único HTML: python3 herramientas/construir.py
import os
B=os.path.join(os.path.dirname(__file__),'..','fuente')
r=lambda f:open(os.path.join(B,f),encoding='utf-8').read()
parts=[r('head.html').rstrip('\n'),'<script>\n'+r('v5_original.js')+'</script>']
for f in ['app.js','territorio.js','orgt.js','fc.js','fc_docx.js','fc_ui.js','fc_import.js','fc_plantilla.js']:
    parts.append('<script>\n'+r(f)+'\n</script>')
# catálogo de convenios: cada convenios/<carpeta>/resumen.json (formato de la skill convenio-a-markdown)
import glob,json
CV=os.path.join(os.path.dirname(__file__),'..','convenios')
cat=[]
for f in sorted(glob.glob(os.path.join(CV,'*','resumen.json'))):
    d=json.load(open(f,encoding='utf-8'));cv=d.get('convenio',{})
    cat.append({'id':os.path.basename(os.path.dirname(f)),'nombre':cv.get('nombre',''),'codigo':cv.get('codigo',''),'ambito':cv.get('ambito',''),'resumen':d})
parts.insert(len(parts)-1,'<script>\n// catálogo de convenios generado por construir.py (un resumen.json por carpeta de convenios)\nwindow.CONVENIOS='+json.dumps(cat,ensure_ascii=False).replace('</','<\\/')+';\n</script>')
out=os.path.join(os.path.dirname(__file__),'..','super_ficha_laboral.html')
open(out,'w',encoding='utf-8').write('\n'.join(parts)+'\n');print('OK ->',os.path.abspath(out))
