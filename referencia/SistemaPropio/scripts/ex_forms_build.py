"""Genera el mapa de campos de los modelos oficiales EX (PDF editables) a la ficha de datos del expediente.

    python scripts/ex_forms_build.py            # escribe apps/api/app/immigration/ex_forms/EXnn.json

Para cada campo del PDF localiza su apartado («1) DATOS DE LA PERSONA EXTRANJERA»…) y la etiqueta impresa a su
izquierda, y lo asigna a una clave de la ficha (p. ej. ext.apellido1). Las casillas que no son sexo, estado civil ni
consentimiento quedan como «opciones» del modelo con su texto, para que la persona marque las que correspondan.
Los modelos sin capa de texto (escaneados, p. ej. EX-10) usan un mapa revisado a mano en MANUAL.
Requiere pypdf y pdfplumber (dependencias de desarrollo). El resultado se revisa visualmente con --preview.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import pdfplumber
import pypdf

ROOT = Path(__file__).resolve().parents[1]
FORMS = ROOT / "apps/api/app/immigration/ex_forms"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(\s*\d+\s*\)", " ", s)          # llamadas a notas (1), (13)
    s = re.sub(r"[…\.]{3,}", " ", s)
    return re.sub(r"\s+", " ", s).strip(" :*-")


def role(section: str) -> str | None:
    s = norm(section)
    if not s:
        return None
    if "representante a efectos" in s:
        return "rep"
    if "notificacion" in s:
        return "notif"
    if "contrato" in s:
        return "con"
    if any(k in s for k in ("tipo de autorizacion", "relativos a la solicitud", "situacion en espana", "tipo de estancia")):
        return "sol"
    if "empleador" in s or "datos de la actividad" in s:
        return "emp"
    if any(k in s for k in ("entidad", "institucion", "centro de estudios")):
        return "ent"
    if any(k in s for k in ("familiar", "reagrupante", "titular de los recursos")):
        return "fam"
    if any(k in s for k in ("persona extranjera", "persona solicitante", "trabajadora extranjera")):
        return "ext"
    return "otro"


HEAD = re.compile(r"^(\d{1,2}\)\s*)?(DATOS|DOMICILIO|TIPO|SITUACI)", re.I)


def page_words(pp):
    words = pp.extract_words(use_text_flow=True)
    lines = [(ln["top"], re.sub(r"\s+", " ", ln["text"]).strip()) for ln in pp.extract_text_lines()]
    heads = [(t, x) for t, x in lines if HEAD.match(x) and (x[:1].isdigit() or x.isupper())]
    return words, heads


def analyze(pdf: Path) -> list[dict]:
    r, pl = pypdf.PdfReader(str(pdf)), pdfplumber.open(str(pdf))
    out: list[dict] = []
    for pi, (p, pp) in enumerate(zip(r.pages, pl.pages, strict=True)):
        h = float(p.mediabox.height)
        words, heads = page_words(pp)
        widgets = []
        for a in p.get("/Annots") or []:
            a = a.get_object()
            if a.get("/Subtype") != "/Widget":
                continue
            par = a["/Parent"].get_object() if a.get("/Parent") else None
            name = str(a.get("/T") or par.get("/T"))
            ft = a.get("/FT") or (par.get("/FT") if par else None)
            states = [str(k) for k in (a.get("/AP", {}).get("/N", {}) or {}).keys()] if a.get("/AP") else []
            x0, y0, x1, y1 = (float(v) for v in a["/Rect"])
            widgets.append((h - y1, x0, name, ft, states, (x0, y0, x1, y1)))
        # filas por centro vertical (tolerancia 5 pt) y, dentro de cada fila, de izquierda a derecha
        widgets.sort(key=lambda w: h - (w[5][1] + w[5][3]) / 2)
        rows: list[list] = []
        for w in widgets:
            cyw = h - (w[5][1] + w[5][3]) / 2
            if rows and abs(cyw - rows[-1][0]) <= 5:
                rows[-1][1].append(w)
            else:
                rows.append([cyw, [w]])
        widgets = [w for _, ws in rows for w in sorted(ws, key=lambda w: w[1])]
        for top, _, name, ft, states, (x0, y0, x1, y1) in widgets:
            bot = h - y0
            cy = (top + bot) / 2
            sec = [x for t, x in heads if t < top + 2]
            section = sec[-1] if sec else (out[-1]["section"] if out and out[-1]["page"] == pi else "")
            row = [w for w in words if abs((w["top"] + w["bottom"]) / 2 - cy) < max(6, (bot - top) / 2)]
            left = sorted([w for w in row if w["x1"] <= x0 + 3], key=lambda w: w["x0"])
            lab, prev = [], x0
            for w in reversed(left):
                if prev - w["x1"] > 40:
                    break
                lab.insert(0, w["text"])
                prev = w["x0"]
            right = sorted([w for w in row if w["x0"] >= x1 - 2], key=lambda w: w["x0"])
            rtxt, last = [], x1
            for w in right:
                if w["x0"] - last > 40:
                    break
                rtxt.append(w["text"])
                last = w["x1"]
            out.append({"name": name, "type": "text" if ft == "/Tx" else "check", "page": pi,
                        "rect": [round(x0), round(y0), round(x1), round(y1)], "section": section,
                        "label": " ".join(lab), "right": " ".join(rtxt[:40]),
                        "on": next((s.lstrip("/") for s in states if s != "/Off"), "Yes")})
    return out


ADDR = [("domicilio en espana", "domicilio"), ("domicilio de residencia", "domicilio"), ("domicilio social", "domicilio"), ("domicilio", "domicilio"),
        ("no", "numero"), ("n", "numero"), ("piso", "piso"), ("localidad", "localidad"), ("c.p.", "cp"), ("c.p", "cp"),
        ("provincia", "provincia"), ("telefono movil", "telefono"), ("telefono", "telefono"), ("e-mail", "email")]
PERSON = [("pasaporte", "pasaporte"), ("1er apellido", "apellido1"), ("2o apellido", "apellido2"),
          ("2 apellido", "apellido2"), ("nombre del padre", "padre"), ("nombre de la madre", "madre"),
          ("nombre/razon social", "nombre"), ("razon social/nombre", "nombre"), ("denominacion", "nombre"),
          ("nombre", "nombre"), ("domicilio cl/pl", "domicilio"), ("trabajo por cuenta propia", "actividad"), ("lugar", "lugar_nacimiento"),
          ("pais", "pais_nacimiento"), ("nacionalidad", "nacionalidad"), ("nif/nie", "doc"), ("nif", "doc"), ("direccion", "domicilio"),
          ("actividad", "actividad"), ("cnae", "cnae"), ("autorizacion de la que es titular", "autorizacion_titular"),
          ("vinculo", "vinculo"), ("parentesco", "vinculo")]
CONTRACT = [("denominacion puesto", "puesto"), ("grupo cotizacion", "grupo_cotizacion"), ("cno sepe 2011", "cno"),
            ("codigo convenio", "convenio_codigo"), ("denominacion convenio", "convenio_nombre"),
            ("codigo contrato", "contrato_codigo"), ("denominacion", "contrato_nombre"),
            ("codigo de cuenta cotizacion", "ccc"), ("retribucion total bruta en euros", "retribucion"),
            ("direccion centro de trabajo", "centro_domicilio")]


def assign(fields: list[dict]) -> dict:
    mapping: dict[str, dict] = {}
    options, unmapped = [], []
    state: dict = {}
    for f in fields:
        rl = role(f["section"])
        lab = norm(f["label"])
        right = norm(f["right"])
        key = part = None
        if rl is None:
            rl = "fam"  # bloque sin título al principio (reagrupante en EX-02)
        if f["type"] == "check":
            if rl in ("ext", "fam"):
                for suf, val in (("x", "X"), ("h", "H"), ("m", "M")):
                    if re.search(rf"(^|\s){suf}$", lab) and ("sexo" in lab or re.search(r"x\s*h?\s*m?$", lab) or val == "X"):
                        key, part = f"{rl}.sexo", val
                        break
                if key is None:
                    for suf, val in (("sp", "Sp"), ("s", "S"), ("c", "C"), ("v", "V"), ("d", "D")):
                        if "estado civil" in lab and re.search(rf"(^|\s){suf}$", lab):
                            key, part = f"{rl}.estado_civil", val
                            break
                if key is None and lab.endswith("si") and "no" not in lab.split()[-1:]:
                    key, part = f"{rl}.hijos_escolarizacion", "si"
                if key is None and re.search(r"(^|\s)(si\s+)?no$", lab):
                    key, part = f"{rl}.hijos_escolarizacion", "no"
            if key is None and rl == "notif" and right.startswith("consiento"):
                key, part = "notif.consiento_dehu", "si"
            if key is None and right.startswith("consiento"):
                key, part = "notif.consiento_dehu", "si"
            if key is None:
                options.append({"field": f["name"], "label": f["right"].strip() or f["label"].strip(),
                                "section": f["section"], "page": f["page"] + 1})
                continue
            mapping[f["name"]] = {"key": key, "part": part, "on": f["on"]}
            continue
        # campos de texto
        prev = state.get("last")
        if rl == "sol":
            if lab.endswith("dirigida a"):
                key = "sol.dirigida_a"
            elif ("dir3" in lab or lab.endswith("codigo")) and "provincia" not in lab:
                key = "sol.dir3"
            elif lab.endswith("provincia") or prev == "sol.dir3":
                key = "sol.dirigida_provincia"
            elif lab.endswith(", a") or lab.endswith(" a"):
                key = "sol.firma_dia"
            elif prev == "sol.firma_dia":
                key = "sol.firma_mes"
            elif prev == "sol.firma_mes":
                key = "sol.firma_anio"
            elif right.startswith("a ") or right.startswith(", a"):
                key = "sol.firma_lugar"
        if key is None and rl in ("ext", "fam"):
            raw = f["label"].strip()
            if (lab.endswith("n.i.e.") or lab.endswith("n.i.e") or lab == "nie") and not raw.endswith("-"):
                key, part = f"{rl}.nie", "1"
            elif prev == f"{rl}.nie" and state.get("part") in ("1", "2"):
                key, part = f"{rl}.nie", str(int(state["part"]) + 1)
            elif "fecha de nacimiento" in lab and prev != f"{rl}.fecha_nacimiento":
                key, part = f"{rl}.fecha_nacimiento", "d"
            elif prev == f"{rl}.fecha_nacimiento" and state.get("part") in ("d", "m"):
                key, part = f"{rl}.fecha_nacimiento", "m" if state["part"] == "d" else "y"
        if key is None and rl == "con":
            for pat, k in CONTRACT:
                if lab.endswith(pat):
                    key = f"con.{k}"
                    break
            if key is None:
                for pat, k in ADDR:
                    if lab.endswith(pat) or lab.split()[-1:] == [pat]:
                        key = f"con.centro_{k}"
                        break
        if key is None and rl in ("ext", "fam", "emp", "ent", "rep", "notif"):
            if "representante legal" in lab:
                key = f"{rl}.rl_nombre"
            elif lab.endswith("dni/nie/pas") or lab.endswith("dni/nie"):
                key = f"{rl}.rl_doc" if prev == f"{rl}.rl_nombre" or prev == f"{rl}.autorizacion_titular" and False else f"{rl}.doc"
                if prev == f"{rl}.rl_nombre":
                    key = f"{rl}.rl_doc"
                elif prev == f"{rl}.autorizacion_titular":
                    key = f"{rl}.autorizacion_doc"
            elif lab.endswith("titulo"):
                key = f"{rl}.autorizacion_titulo" if prev == f"{rl}.autorizacion_doc" else f"{rl}.rl_titulo"
            if key is None:
                for pat, k in PERSON:
                    if lab.endswith(pat):
                        key = f"{rl}.{k}"
                        break
            if key is None:
                for pat, k in ADDR:
                    if lab.endswith(" " + pat) or lab == pat:
                        key = f"{rl}.{k}"
                        break
        if key is None:
            unmapped.append({"field": f["name"], "section": f["section"][:60], "label": f["label"][-60:], "right": f["right"][:60]})
            state = {"last": None}
            continue
        if key in [m["key"] for m in mapping.values()] and part is None:
            # segunda aparición en el mismo apartado (p. ej. dos «Nombre»): se informa, no se pisa
            unmapped.append({"field": f["name"], "section": f["section"][:60], "label": f["label"][-60:], "right": "repetido: " + key})
            continue
        mapping[f["name"]] = {"key": key, **({"part": part} if part else {})}
        state = {"last": key, "part": part}
    return {"fields": mapping, "options": options, "unmapped": unmapped}


def title(pdf: Path) -> str:
    with pdfplumber.open(str(pdf)) as p:
        txt = p.pages[0].extract_text() or ""
    m = re.search(r"Solicitud de[^\n]*(?:\n[^\n(]*)*?\(LO", txt)
    return re.sub(r"\s+", " ", m.group(0)[:-3]).strip() if m else ""


def main(argv: list[str]) -> int:
    only = {a.upper() for a in argv if a.upper().startswith("EX")}
    manual = json.loads((FORMS / "manual.json").read_text(encoding="utf-8")) if (FORMS / "manual.json").exists() else {}
    for pdf in sorted((FORMS / "pdf").glob("EX*.pdf")):
        code = pdf.stem
        if only and code not in only:
            continue
        if code in manual:
            data = manual[code]
        else:
            data = assign(analyze(pdf))
            data["title"] = title(pdf)
        data["model"] = f"EX-{code[2:]}"
        data["source"] = "Modelo oficial editable (Ministerio de Inclusión, Seguridad Social y Migraciones), aportado por el despacho"
        (FORMS / f"{code}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{code}: {len(data['fields'])} campos asignados, {len(data['options'])} opciones, {len(data['unmapped'])} sin asignar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
