#!/usr/bin/env python3
"""Regenera los Word (.docx) de docs/entrega/word a partir de los Markdown de docs/entrega.

El Markdown es la fuente; el Word se genera. Usa pandoc y toma los estilos de
herramientas/plantilla_docs.docx (copia de uno de los Word originales del paquete).

Uso:
    python3 herramientas/docs_a_word.py            # todos los documentos
    python3 herramientas/docs_a_word.py 11 12      # solo los que empiezan por 11 y 12
"""
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs" / "entrega"
SALIDA = DOCS / "word"
PLANTILLA = RAIZ / "herramientas" / "plantilla_docs.docx"


def main(prefijos):
    if not shutil.which("pandoc"):
        sys.exit("Falta pandoc. Instálelo (https://pandoc.org) y vuelva a ejecutar.")
    SALIDA.mkdir(parents=True, exist_ok=True)
    md = sorted(DOCS.glob("[0-9][0-9]_*.md"))
    if prefijos:
        md = [p for p in md if any(p.name.startswith(x) for x in prefijos)]
    if not md:
        sys.exit("No hay documentos que coincidan.")
    for p in md:
        destino = SALIDA / (p.stem + ".docx")
        cmd = ["pandoc", str(p), "-f", "gfm", "-o", str(destino)]
        if PLANTILLA.exists():
            cmd += ["--reference-doc", str(PLANTILLA)]
        subprocess.run(cmd, check=True, cwd=DOCS)
        bordes_tablas(destino)
        print("OK", destino.relative_to(RAIZ))


def bordes_tablas(ruta):
    """Pone bordes finos a todas las tablas, como en los Word originales del paquete."""
    try:
        import docx
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
    except ImportError:
        print("  (sin python-docx: las tablas quedan sin bordes)")
        return
    d = docx.Document(str(ruta))
    for t in d.tables:
        tblPr = t._tbl.tblPr
        for viejo in tblPr.findall(qn("w:tblBorders")):
            tblPr.remove(viejo)
        bordes = OxmlElement("w:tblBorders")
        for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
            b = OxmlElement(f"w:{lado}")
            b.set(qn("w:val"), "single")
            b.set(qn("w:sz"), "4")
            b.set(qn("w:color"), "808080")
            bordes.append(b)
        tblPr.append(bordes)
    d.save(str(ruta))


if __name__ == "__main__":
    main(sys.argv[1:])
