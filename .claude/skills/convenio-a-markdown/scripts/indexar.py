"""Indexa un convenio en Markdown por capítulos, artículos, disposiciones y anexos.
Uso: python3 indexar.py convenio.md [--limpiar]
Genera indice.md (y convenio_limpio.md con --limpiar) en la misma carpeta."""
import os
import re
import sys

ruta = sys.argv[1]
limpiar = '--limpiar' in sys.argv
texto = open(ruta, encoding='utf-8', errors='replace').read()
carpeta = os.path.dirname(os.path.abspath(ruta))

RUIDO = [r'^\s*BOLET[IÍ]N OFICIAL DEL ESTADO\s*$', r'^\s*N[uú]m\.\s*\d+\s+.*\d{4}\s+Sec\.\s*[IVX]+\.?.*P[aá]g\.\s*\d+\s*$',
         r'^\s*Sec\.\s*[IVX]+\.?\s*P[aá]g\.\s*\d+\s*$', r'^\s*cve:\s*BOE-\S+\s*$', r'^\s*Verificable en https?://\S+\s*$',
         r'^\s*D\.\s*L\.:?\s*M-\d+/\d+.*$', r'^\s*ISSN:?\s*\d{4}-\d{3}[\dX]\s*$', r'^\s*P[aá]gina\s+\d+(\s+de\s+\d+)?\s*$', r'^\s*\d{1,4}\s*$']
if limpiar:
    pat = re.compile('|'.join(RUIDO), re.I)
    lineas = [l for l in texto.splitlines() if not pat.match(l)]
    texto = re.sub(r'\n{3,}', '\n\n', '\n'.join(lineas))
    ruta = os.path.join(carpeta, 'convenio_limpio.md')
    open(ruta, 'w', encoding='utf-8').write(texto)

lineas = texto.splitlines()
CAB = re.compile(r'^\s*(#+\s*)?((CAP[IÍ]TULO|T[IÍ]TULO)\s+[IVXLC\d]+.*|Art[ií]culo\s+\d+[\w.º°]*.*|ART[IÍ]CULO\s+\d+.*|Disposici[oó]n\s+(adicional|transitoria|final|derogatoria).*|DISPOSICI[OÓ]N\s+.*|ANEXO\s*[IVX\d]*.*|Anexo\s+[IVX\d]+.*)$')
CLAVE = {'salario': r'salari|retribuci', 'tablas': r'tabla', 'plus': r'\bplus|complement', 'jornada': r'jornada|horas? extra',
         'vacaciones': r'vacacion', 'pagas': r'paga[s]? extra|gratificaci', 'IT': r'incapacidad temporal|\bI\.?T\.?\b|enfermedad|accidente',
         'preaviso': r'preaviso', 'categoría': r'categor[ií]a|grupo profesional|clasificaci', 'antigüedad': r'antig[uü]edad'}
marcas = [i for i, l in enumerate(lineas) if CAB.match(l) and len(l) < 220]
fil = ['| Línea inicio | Línea fin | Apartado | Temas |', '|---:|---:|---|---|']
for n, i in enumerate(marcas):
    fin = (marcas[n + 1] if n + 1 < len(marcas) else len(lineas))
    cuerpo = '\n'.join(lineas[i:fin]).lower()
    temas = ', '.join(k for k, rx in CLAVE.items() if re.search(rx, cuerpo))
    titulo = re.sub(r'^#+\s*', '', lineas[i].strip()).replace('|', '/')[:120]
    fil.append(f'| {i + 1} | {fin} | {titulo} | {temas} |')
cab = f'# Índice de {os.path.basename(ruta)}\n\n{len(lineas)} líneas, {len(marcas)} apartados. Lee cada apartado con: sed -n \'INICIO,FINp\' {os.path.basename(ruta)}\n\n'
open(os.path.join(carpeta, 'indice.md'), 'w', encoding='utf-8').write(cab + '\n'.join(fil) + '\n')
print(f'OK: {len(marcas)} apartados -> {os.path.join(carpeta, "indice.md")}' + (f' (texto limpio: {ruta})' if limpiar else ''))
if len(marcas) < 5:
    print('AVISO: casi no se han encontrado artículos. ¿El PDF es escaneado o el texto salió desordenado?')
