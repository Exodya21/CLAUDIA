import csv,sys,json
rows=list(csv.reader(open(sys.argv[1],encoding='latin-1',newline='')))
hdr=[h.replace('\n',' ').strip() for h in rows[1]]
ix={h:i for i,h in enumerate(hdr)}
need=['CODM','LOCALIDAD','LOCALIDAD SIN ACENTOS','ANTIGUO NOMBRE','CPRO','PROVINCIA','CCAA','CP','PARTIDO','CODM SOCIAL','SOCIAL','SEDE ABR MN']
for n in need: assert n in ix,(n,hdr)
prov={};m=[]
for r in rows[2:]:
    g=lambda k:r[ix[k]].strip()
    cpro=g('CPRO').zfill(2)
    prov.setdefault(cpro,{'n':g('PROVINCIA'),'c':g('CCAA')})
    m.append([g('CODM'),g('LOCALIDAD'),g('LOCALIDAD SIN ACENTOS'),g('ANTIGUO NOMBRE'),cpro,g('CP'),g('PARTIDO'),g('SOCIAL'),g('SEDE ABR MN')])
out={'src':'MAPA - COMPETENCIAS TERRITORRIALES 8(DATOS_ORIGEN).csv','rows':len(m),'prov':prov,'m':m}
s='window.TERR='+json.dumps(out,ensure_ascii=False,separators=(',',':'))+';'
open(sys.argv[2],'w',encoding='utf-8').write(s)
print(len(m),len(prov),len(s))
