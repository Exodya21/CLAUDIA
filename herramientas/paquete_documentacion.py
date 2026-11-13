#!/usr/bin/env python3
"""Prepara la documentación del proyecto para entregarla.

Genera, en documentacion/entregas/:
  - Documentacion_proyecto_<fecha>.zip   → Markdown + Word de docs/entrega y openapi.json
  - Documentacion_proyecto_<fecha>.docx  → un solo Word con todos los documentos en orden (índice incluido)

Antes regenera los Word de todos los documentos (herramientas/docs_a_word.py).

Uso:
    python3 herramientas/paquete_documentacion.py            # todo
    python3 herramientas/paquete_documentacion.py 05 19      # solo esos documentos (zip y Word combinado)
"""
import datetime as dt
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs" / "entrega"
SALIDA = RAIZ / "documentacion" / "entregas"
PLANTILLA = RAIZ / "herramientas" / "plantilla_docs.docx"


def main(prefijos):
    subprocess.run([sys.executable, str(RAIZ / "herramientas" / "docs_a_word.py"), *prefijos], check=True)
    md = sorted(DOCS.glob("[0-9][0-9]_*.md"))
    if prefijos:
        md = [p for p in md if any(p.name.startswith(x) for x in prefijos)]
    if not md:
        sys.exit("No hay documentos que coincidan.")
    SALIDA.mkdir(parents=True, exist_ok=True)
    fecha = dt.date.today().strftime("%Y-%m-%d")
    sufijo = "" if not prefijos else "_" + "-".join(prefijos)
    base = SALIDA / f"Documentacion_proyecto_{fecha}{sufijo}"

    # Zip con Markdown, Word y la especificación de la API
    with zipfile.ZipFile(f"{base}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in md:
            z.write(p, f"Markdown/{p.name}")
            w = DOCS / "word" / f"{p.stem}.docx"
            if w.exists():
                z.write(w, f"Word/{w.name}")
        if not prefijos and (DOCS / "openapi.json").exists():
            z.write(DOCS / "openapi.json", "openapi.json")
    print("OK", Path(f"{base}.zip").relative_to(RAIZ))

    # Un solo Word con todos los documentos
    if shutil.which("pandoc"):
        cmd = ["pandoc", *[str(p) for p in md], "-f", "gfm", "--toc", "--toc-depth=1",
               "-M", f"title=Documentación del proyecto · {fecha}", "-o", f"{base}.docx"]
        if PLANTILLA.exists():
            cmd += ["--reference-doc", str(PLANTILLA)]
        subprocess.run(cmd, check=True, cwd=DOCS)
        sys.dont_write_bytecode = True  # no dejar herramientas/__pycache__ en el repositorio
        sys.path.insert(0, str(RAIZ / "herramientas"))
        from docs_a_word import bordes_tablas
        bordes_tablas(Path(f"{base}.docx"))
        print("OK", Path(f"{base}.docx").relative_to(RAIZ))


if __name__ == "__main__":
    main(sys.argv[1:])
