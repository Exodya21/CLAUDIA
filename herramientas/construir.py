# Une las piezas de /fuente en un único HTML: python3 herramientas/construir.py
import os
B=os.path.join(os.path.dirname(__file__),'..','fuente')
r=lambda f:open(os.path.join(B,f),encoding='utf-8').read()
parts=[r('head.html').rstrip('\n'),'<script>\n'+r('v5_original.js')+'</script>']
for f in ['app.js','territorio.js','orgt.js','fc.js','fc_docx.js','fc_ui.js','fc_import.js']:
    parts.append('<script>\n'+r(f)+'\n</script>')
out=os.path.join(os.path.dirname(__file__),'..','super_ficha_laboral.html')
open(out,'w',encoding='utf-8').write('\n'.join(parts)+'\n');print('OK ->',os.path.abspath(out))
