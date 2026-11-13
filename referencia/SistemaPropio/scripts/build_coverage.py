"""Genera el mapa de cobertura de las 208 referencias a partir de la matriz maestra.

Uso:
    python scripts/build_coverage.py [ruta_xlsx]

Salidas (en docs/producto/):
    requisitos_208.json   inventario completo con campos originales + clasificación
    mapa_cobertura.csv    una fila por ID (filtrable en Excel)
    mapa_cobertura.md     tabla legible agrupada por fuente

Reglas de clasificación (propuesta de producto, a validar por Dirección):
    precedencia: contradictorio > sin_definicion > equivalente > complementario > nuevo
    - contradictorio: el ID aparece en una decisión que señala una afirmación jurídica,
      fiscal u operativa posiblemente incorrecta o en conflicto con política vigente.
    - sin_definicion: el ID depende de una decisión estructural abierta (interfaz oficial
      autorizada, proveedor fiscal, migración desde MNP, etc.).
    - equivalente: relación recíproca con otra fuente y mismo módulo.
    - complementario: relacionado con otra fuente, pero aporta un alcance distinto.
    - nuevo: aportación exclusiva de su fuente, sin relación cruzada.
El script NO elimina ningún ID: falla si el recuento no es 208 o hay IDs duplicados.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XLSX = ROOT / "docs" / "fuentes" / "02_Matriz_Maestra_208_Requisitos.xlsx"
OUT = ROOT / "docs" / "producto"

# Decisiones que señalan contradicción con la norma o con la política vigente.
CONTRADICTORIAS = {
    "D-01", "D-02", "D-03", "D-04", "D-05", "D-06", "D-07",
    "D-08", "D-10", "D-11", "D-13", "D-18", "D-21", "D-22",
}
# Decisiones estructurales sin las que el requisito no se puede especificar.
SIN_DEFINICION = {"D-09", "D-16", "D-17", "D-20", "D-24", "D-25"}

# Relaciones de los acuerdos U-* que la matriz deja vacías (derivadas del detalle funcional).
RELACIONES_ACUERDOS = {
    "U-01": ["Q-2.9", "Q-6.1", "I-004"], "U-02": ["I-002", "I-079", "Q-5.5"],
    "U-03": ["I-004", "Q-6.1"], "U-04": ["I-004", "Q-6.1"], "U-05": ["I-004"],
    "U-06": ["I-004"], "U-07": ["I-004"], "U-08": ["I-004"], "U-09": ["I-004", "I-015"],
    "U-10": ["I-004", "Q-6.1"], "U-11": ["I-004", "Q-6.1"], "U-12": ["I-004", "Q-6.1"],
    "U-13": ["Q-3.8", "Q-3.9"], "U-14": ["Q-3.7"], "U-15": ["Q-6.3", "I-091"],
    "U-16": ["I-089", "Q-6.20B"], "U-17": [], "U-18": ["Q-1.1"],
}
# Decisiones adicionales que afectan a acuerdos U-* (la matriz no las enlaza).
DECISIONES_EXTRA = {"U-14": ["D-11"], "U-13": ["D-13"]}

# Ajustes manuales documentados (requisitos atados a un sistema que se va a sustituir).
OVERRIDES = {
    "I-060": ("sin_definicion", "Incorporar a MN Program contradice la sustitución progresiva; depende del plan de convivencia D-15."),
    "I-111": ("sin_definicion", "Integración con MN Program: depende de D-15 (migración y convivencia)."),
    "I-113": ("sin_definicion", "Plantillas MN Program: inventariar y migrar a plantillas propias; depende de D-15."),
}

ID_RE = re.compile(r"\b([IQU])-(\d+(?:\.\d+)?B?)(?:-(\d+(?:\.\d+)?))?")


def expand_refs(text: str) -> list[str]:
    """Convierte 'Q-4.1-4.16; I-047-066' en una lista de IDs individuales."""
    ids: list[str] = []
    if not text:
        return ids
    for pref, start, end in ID_RE.findall(str(text)):
        if not end:
            ids.append(f"{pref}-{start}")
            continue
        if pref == "I":
            ids += [f"I-{n:03d}" for n in range(int(start), int(end) + 1)]
        elif "." in start and "." in end:
            blk, a = start.split(".")
            _, b = end.split(".")
            ids += [f"Q-{blk}.{n}" for n in range(int(a), int(b) + 1)]
    return ids


def sheet_rows(ws, header_row: int = 4):
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h).strip() if h else "" for h in rows[header_row - 1]]
    for r in rows[header_row:]:
        if r and r[0]:
            yield {header[i]: (r[i] if i < len(r) else None) for i in range(len(header)) if header[i]}


def main() -> None:
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)

    reqs: dict[str, dict] = {}
    for r in sheet_rows(wb["INFORME_120"]):
        reqs[r["ID"]] = {
            "id": r["ID"], "fuente": "Informe 120", "titulo": r["Necesidad literal"],
            "referencia_origen": r.get("Referencia de origen"), "bloque": r["Bloque"],
            "modulo": r["Módulo"], "prioridad": r["Prioridad"], "fase": r["Fase"],
            "estado_matriz": r["Estado"], "nota": r.get("Nota de implementacion"),
            "relaciones": expand_refs(r.get("Relación con Qubiq") or ""),
            "valida": r.get("Responsable a validar"),
        }
    for r in sheet_rows(wb["QUBIQ_70"]):
        reqs[r["ID"]] = {
            "id": r["ID"], "fuente": "Qubiq 70", "titulo": r["Necesidad / titulo"],
            "referencia_origen": f"Project Charter p.{r.get('Página en PDF')}", "bloque": r["Bloque"],
            "modulo": r["Módulo"], "prioridad": r["Prioridad"], "fase": r["Fase"],
            "estado_matriz": r["Estado"], "nota": r.get("Observacion o discrepancia"),
            "relaciones": expand_refs(r.get("Relación con Informe 120") or ""),
            "valida": r.get("Responsable a validar"),
        }
    for r in sheet_rows(wb["ACUERDOS_18"]):
        reqs[r["ID"]] = {
            "id": r["ID"], "fuente": "Acuerdos 18", "titulo": r["Necesidad"],
            "referencia_origen": r.get("Origen / acuerdo"), "bloque": "U",
            "modulo": r["Módulo"], "prioridad": r["Prioridad"], "fase": r["Fase"],
            "estado_matriz": r["Estado"], "nota": r.get("Detalle funcional"),
            "relaciones": RELACIONES_ACUERDOS.get(r["ID"], []),
            "valida": None,
        }

    counts = Counter(v["fuente"] for v in reqs.values())
    assert counts == {"Informe 120": 120, "Qubiq 70": 70, "Acuerdos 18": 18}, counts
    assert len(reqs) == 208, len(reqs)

    decisiones = []
    dec_by_id: dict[str, list[str]] = defaultdict(list)
    for r in sheet_rows(wb["DECISIONES_CRITICAS"]):
        refs = expand_refs(r.get("Referencia") or "")
        decisiones.append({
            "id": r["ID"], "tema": r["Tema"], "referencia": r["Referencia"], "riesgo": r["Texto / riesgo"],
            "propuesta": r["Decisión técnica propuesta"], "valida": r["Valida"], "situacion": r["Situacion"],
            "fuente_oficial": r.get("Fuente oficial (cuando procede)"), "ids": refs,
        })
        for i in refs:
            if i in reqs:
                dec_by_id[i].append(r["ID"])
    for i, ds in DECISIONES_EXTRA.items():
        dec_by_id[i] += ds
    assert len(decisiones) == 25, len(decisiones)

    for rid, req in reqs.items():
        decs = sorted(set(dec_by_id.get(rid, [])))
        req["decisiones"] = decs
        rels = [x for x in req["relaciones"] if x in reqs]
        req["relaciones"] = rels
        reciprocal = [x for x in rels if rid in reqs[x]["relaciones"] and reqs[x]["modulo"] == req["modulo"]]
        if rid in OVERRIDES:
            estado, motivo = OVERRIDES[rid]
        elif set(decs) & CONTRADICTORIAS:
            estado, motivo = "contradictorio", "Afectado por " + ", ".join(sorted(set(decs) & CONTRADICTORIAS)) + "; no programar como regla hasta resolver."
        elif set(decs) & SIN_DEFINICION:
            estado, motivo = "sin_definicion", "Bloqueado por " + ", ".join(sorted(set(decs) & SIN_DEFINICION)) + "."
        elif reciprocal:
            estado, motivo = "equivalente", "Misma necesidad que " + ", ".join(reciprocal) + "; se implementa una vez y se enlazan ambos IDs."
        elif rels:
            estado, motivo = "complementario", "Relacionado con " + ", ".join(rels) + "; aporta alcance propio."
        else:
            estado, motivo = "nuevo", "Aportación exclusiva de su fuente."
        req["cobertura"] = estado
        req["motivo_cobertura"] = motivo
        req["implementado_en"] = []  # se rellena en docs/producto/trazabilidad_codigo.md

    OUT.mkdir(parents=True, exist_ok=True)
    order = sorted(reqs.values(), key=lambda x: ("IQU".index(x["id"][0]), x["id"]))
    (OUT / "requisitos_208.json").write_text(
        json.dumps({"total": 208, "requisitos": order, "decisiones": decisiones}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    cols = ["id", "fuente", "titulo", "modulo", "fase", "prioridad", "cobertura", "motivo_cobertura", "relaciones", "decisiones"]
    with open(OUT / "mapa_cobertura.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cols)
        for r in order:
            w.writerow([", ".join(r[c]) if isinstance(r[c], list) else r[c] for c in cols])

    by_state = Counter(r["cobertura"] for r in order)
    by_src_state = Counter((r["fuente"], r["cobertura"]) for r in order)
    states = ["equivalente", "complementario", "nuevo", "contradictorio", "sin_definicion"]
    lines = [
        "# Mapa de cobertura — 208 referencias",
        "",
        "> Generado por `scripts/build_coverage.py` desde `docs/fuentes/02_Matriz_Maestra_208_Requisitos.xlsx`. "
        "No editar a mano: modificar las reglas del script y regenerar. Ningún ID se elimina; la clasificación es una "
        "propuesta de producto pendiente de validación por Dirección.",
        "",
        "## Recuento",
        "",
        "| Fuente | " + " | ".join(states) + " | Total |",
        "|---|" + "---|" * (len(states) + 1),
    ]
    for src in ["Informe 120", "Qubiq 70", "Acuerdos 18"]:
        row = [str(by_src_state[(src, s)]) for s in states]
        lines.append(f"| {src} | " + " | ".join(row) + f" | {counts[src]} |")
    lines.append("| **Total** | " + " | ".join(f"**{by_state[s]}**" for s in states) + " | **208** |")
    lines += [
        "",
        "Significado: **equivalente** = misma necesidad en dos fuentes (se construye una vez, se enlazan los IDs); "
        "**complementario** = relacionado pero con alcance propio; **nuevo** = solo aparece en su fuente; "
        "**contradictorio** = contiene una afirmación jurídica/fiscal/operativa a corregir antes de programar; "
        "**sin definición** = depende de una decisión estructural abierta.",
        "",
    ]
    for src in ["Informe 120", "Qubiq 70", "Acuerdos 18"]:
        lines += [f"## {src}", "", "| ID | Necesidad | Mód. | Fase | Cobertura | Relaciones | Decisiones |", "|---|---|---|---|---|---|---|"]
        for r in order:
            if r["fuente"] != src:
                continue
            t = str(r["titulo"]).replace("|", "/")
            lines.append(
                f"| {r['id']} | {t} | {r['modulo']} | {r['fase']} | {r['cobertura']} | "
                f"{', '.join(r['relaciones']) or '—'} | {', '.join(r['decisiones']) or '—'} |"
            )
        lines.append("")
    (OUT / "mapa_cobertura.md").write_text("\n".join(lines), encoding="utf-8")

    # Registro de decisiones D-01..D-25 con los IDs afectados (generado, no transcrito).
    dl = [
        "# Registro de decisiones de la matriz (D-01 … D-25)",
        "",
        "> Generado por `scripts/build_coverage.py`. Situación tal como consta en la matriz; ninguna decisión jurídica, "
        "fiscal o de privacidad se considera aprobada por el hecho de figurar aquí. El sistema NO programa como regla "
        "ningún requisito marcado `contradictorio` mientras su decisión siga abierta.",
        "",
        "| ID | Tema | Situación | Valida | Riesgo detectado | Propuesta técnica | IDs afectados |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in decisiones:
        afect = [i for i in d["ids"] if i in reqs] + [k for k, v in DECISIONES_EXTRA.items() if d["id"] in v]
        dl.append(
            f"| {d['id']} | {d['tema']} | {d['situacion']} | {d['valida']} | {str(d['riesgo']).replace('|', '/')} | "
            f"{str(d['propuesta']).replace('|', '/')} | {', '.join(afect) or '—'} |"
        )
    (OUT / "registro_decisiones_matriz.md").write_text("\n".join(dl) + "\n", encoding="utf-8")
    print("OK 208 IDs:", dict(counts), dict(by_state))


if __name__ == "__main__":
    main()
