"""Genera los documentos FICTICIOS de muestra de F4.3 en docs/pruebas/muestras/ (para probar la lectura a mano).

Uso: cd apps/api && python ../../scripts/muestras_f43.py
"""
from __future__ import annotations

import io
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from PIL import Image  # noqa: E402

from app.immigration import samples  # noqa: E402
from app.seed_immigration import passport_image  # noqa: E402

out = Path(__file__).resolve().parents[1] / "docs" / "pruebas" / "muestras"
out.mkdir(parents=True, exist_ok=True)
files = {
    "FICTICIO_contrato_trabajo.pdf": samples.contrato(),
    "FICTICIO_contrato_escaneado.pdf": samples.contrato(scanned=True),
    "FICTICIO_empadronamiento.pdf": samples.padron(),
    "FICTICIO_tasa_790_052.pdf": samples.tasa(),
    "FICTICIO_TIE.png": samples.tie_image(),
}
png, _ = passport_image("Ferrer Demo", "Carla", "ZZ1234567", date(1990, 3, 14), date(2031, 1, 1), "F")
pages = [Image.new("RGB", (1654, 2339), "white"), Image.open(io.BytesIO(png)).convert("RGB")]
buf = io.BytesIO()
pages[0].save(buf, "PDF", save_all=True, append_images=pages[1:], resolution=200)
files["FICTICIO_pasaporte_2_paginas.pdf"] = buf.getvalue()
for name, data in files.items():
    (out / name).write_bytes(data)
    print(name, len(data))
