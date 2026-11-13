"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useMe } from "@/components/session";
import { api, ApiError, fieldErrors, hasPerm, type ContactFull, type ContactMinimal, type Organization } from "@/lib/api";
import { checkIdentifier, checkPhone } from "@/lib/validation";

interface DupCheck { identifier_matches: ContactMinimal[]; hidden_identifier_matches: number; shared_phone_contacts: number }

const EMPTY = {
  organization_id: "", primary_branch_id: "", given_name: "", family_names: "", birth_date: "", nationality: "",
  preferred_language: "es", origin: "presencial", doc_kind: "DNI", doc_number: "", doc_country: "ES",
  phone: "", email: "", line1: "", postal_code: "", municipality: "", consent: true, consent_source: "presencial",
};

export default function NuevoCliente() {
  const me = useMe();
  const router = useRouter();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [f, setF] = useState(EMPTY);
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [general, setGeneral] = useState<string | null>(null);
  const [dup, setDup] = useState<DupCheck | null>(null);
  const [conflict, setConflict] = useState<ContactMinimal[] | null>(null);
  const [justification, setJustification] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api<Organization[]>("/organizations").then((all) => {
      const allowed = all.filter((o) => o.can_create_contacts);
      setOrgs(allowed);
      if (allowed.length) setF((s) => ({ ...s, organization_id: allowed[0].id }));
    });
  }, []);

  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const v = e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value;
    setF((s) => ({ ...s, [k]: v }));
    setErrs((x) => ({ ...x, [k]: "" }));
  };

  async function checkDuplicates() {
    if (!f.organization_id || (!f.doc_number && !f.phone)) return setDup(null);
    if (f.doc_number && checkIdentifier(f.doc_kind, f.doc_number)) return;
    try {
      setDup(await api<DupCheck>("/contacts/duplicate-check", {
        method: "POST",
        body: JSON.stringify({
          organization_id: f.organization_id,
          identifiers: f.doc_number ? [{ kind: f.doc_kind, number: f.doc_number, country: f.doc_country }] : [],
          phones: f.phone && !checkPhone(f.phone) ? [f.phone] : [],
        }),
      }));
    } catch { setDup(null); }
  }

  function localValidate(): boolean {
    const e: Record<string, string> = {};
    if (!f.given_name.trim()) e.given_name = "Indique el nombre.";
    if (!f.family_names.trim()) e.family_names = "Indique los apellidos.";
    const docErr = f.doc_number ? checkIdentifier(f.doc_kind, f.doc_number) : null;
    if (docErr) e.doc_number = docErr;
    const phErr = checkPhone(f.phone);
    if (phErr) e.phone = phErr;
    if ((f.line1 || f.municipality) && !(f.line1 && f.municipality)) e.line1 = "Complete dirección y municipio.";
    setErrs(e);
    return Object.keys(e).length === 0;
  }

  async function submit(confirm = false) {
    setGeneral(null);
    if (!localValidate()) return;
    setSaving(true);
    const body = {
      organization_id: f.organization_id,
      primary_branch_id: f.primary_branch_id || null,
      given_name: f.given_name, family_names: f.family_names,
      birth_date: f.birth_date || null, nationality: f.nationality ? f.nationality.toUpperCase() : null,
      preferred_language: f.preferred_language, origin: f.origin,
      identifiers: f.doc_number ? [{ kind: f.doc_kind, number: f.doc_number, country: f.doc_country.toUpperCase() }] : [],
      phones: f.phone ? [{ number: f.phone, label: "movil", is_primary: true }] : [],
      emails: f.email ? [{ email: f.email, is_primary: true }] : [],
      addresses: f.line1 ? [{ kind: "postal", line1: f.line1, postal_code: f.postal_code || null, municipality: f.municipality, country: "ES" }] : [],
      consents: f.consent ? [{ purpose: "gestion_expediente", granted: true, source: f.consent_source }] : [],
      confirm_possible_duplicate: confirm,
      duplicate_justification: confirm ? justification : null,
    };
    try {
      const created = await api<ContactFull>("/contacts", { method: "POST", body: JSON.stringify(body) });
      router.push(`/clientes/${created.id}?alta=1`);
    } catch (e) {
      if (e instanceof ApiError && e.body.code === "posible_duplicado") {
        setConflict((e.body.details as { candidates: ContactMinimal[] }).candidates);
      } else if (e instanceof ApiError) {
        setGeneral(e.message);
        const fe = fieldErrors(e);
        const mapped: Record<string, string> = {};
        for (const [k, v] of Object.entries(fe)) {
          if (k.includes("number") || k === "kind" || k === "country") mapped.doc_number = v;
          else if (k.includes("phone") || k.startsWith("phones")) mapped.phone = v;
          else if (k.startsWith("emails")) mapped.email = v;
          else if (k === "duplicate_justification") mapped.justification = v;
          else mapped[k] = v;
        }
        setErrs(mapped);
      } else setGeneral("No se pudo guardar.");
    } finally { setSaving(false); }
  }

  if (!hasPerm(me, "contact.create")) {
    return <div className="notice notice-warn"><strong>Sin permiso</strong>Su rol no permite dar de alta clientes.</div>;
  }
  const org = orgs.find((o) => o.id === f.organization_id);
  const err = (k: string) => errs[k] ? <span className="error-text" role="alert">{errs[k]}</span> : null;

  return (
    <div className="stack">
      <div className="topline">
        <div>
          <h1>Nuevo cliente</h1>
          <p className="subtitle">Antes de guardar, el sistema comprueba si el documento ya existe. Un teléfono compartido no une fichas.</p>
        </div>
        <Link className="btn" href="/clientes">Cancelar</Link>
      </div>
      {general && <div className="notice notice-danger" role="alert">{general}</div>}

      <form className="stack" onSubmit={(e) => { e.preventDefault(); submit(false); }} noValidate>
        <fieldset>
          <legend>Identidad</legend>
          <div className="form-grid">
            <label className="field">Entidad
              <select value={f.organization_id} onChange={set("organization_id")}>
                {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
            </label>
            <label className="field">Sede principal
              <select value={f.primary_branch_id} onChange={set("primary_branch_id")}>
                <option value="">Sin asignar</option>
                {org?.branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </label>
            <label className="field">Nombre *
              <input value={f.given_name} onChange={set("given_name")} className={errs.given_name ? "invalid" : ""} autoComplete="off" />
              {err("given_name")}
            </label>
            <label className="field">Apellidos *
              <input value={f.family_names} onChange={set("family_names")} className={errs.family_names ? "invalid" : ""} autoComplete="off" />
              {err("family_names")}
            </label>
            <label className="field">Fecha de nacimiento
              <input type="date" value={f.birth_date} onChange={set("birth_date")} />
              {err("birth_date")}
            </label>
            <label className="field">Nacionalidad <span className="hint">Código de 2 letras (ES, CO, MA…)</span>
              <input value={f.nationality} onChange={set("nationality")} maxLength={2} />
            </label>
            <label className="field">Idioma de comunicación
              <select value={f.preferred_language} onChange={set("preferred_language")}>
                <option value="es">Español</option><option value="ca">Catalán</option><option value="en">Inglés</option>
                <option value="fr">Francés</option><option value="ar">Árabe</option><option value="ro">Rumano</option><option value="pt">Portugués</option>
              </select>
            </label>
            <label className="field">Canal de entrada
              <select value={f.origin} onChange={set("origin")}>
                <option value="presencial">Presencial</option><option value="telefono">Teléfono</option>
                <option value="web">Web</option><option value="redes_sociales">Redes sociales</option><option value="recomendacion">Recomendación</option>
              </select>
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Documento</legend>
          <div className="form-grid">
            <label className="field">Tipo
              <select value={f.doc_kind} onChange={(e) => { set("doc_kind")(e); setF((s) => ({ ...s, doc_kind: e.target.value, doc_country: ["DNI", "NIE"].includes(e.target.value) ? "ES" : s.doc_country })); }}>
                <option value="DNI">DNI</option><option value="NIE">NIE</option><option value="PASAPORTE">Pasaporte</option><option value="OTRO">Otro</option>
              </select>
            </label>
            <label className="field">País emisor <span className="hint">2 letras</span>
              <input value={f.doc_country} onChange={set("doc_country")} maxLength={2} disabled={["DNI", "NIE"].includes(f.doc_kind)} />
            </label>
            <label className="field full">Número
              <input value={f.doc_number} onChange={set("doc_number")} onBlur={checkDuplicates} className={errs.doc_number ? "invalid" : ""} autoComplete="off" />
              {err("doc_number")}
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Contacto y domicilio</legend>
          <div className="form-grid">
            <label className="field">Teléfono móvil
              <input value={f.phone} onChange={set("phone")} onBlur={checkDuplicates} inputMode="tel" placeholder="+34 6.. ... ..." className={errs.phone ? "invalid" : ""} />
              {err("phone")}
            </label>
            <label className="field">Correo electrónico
              <input type="email" value={f.email} onChange={set("email")} className={errs.email ? "invalid" : ""} />
              {err("email")}
            </label>
            <label className="field full">Dirección postal
              <input value={f.line1} onChange={set("line1")} className={errs.line1 ? "invalid" : ""} />
              {err("line1")}
            </label>
            <label className="field">Código postal<input value={f.postal_code} onChange={set("postal_code")} maxLength={12} /></label>
            <label className="field">Municipio<input value={f.municipality} onChange={set("municipality")} /></label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Protección de datos</legend>
          <label className="row"><input type="checkbox" style={{ width: "auto" }} checked={f.consent} onChange={set("consent")} />
            <span>Se ha informado al cliente y consta su autorización para gestionar su consulta o expediente.</span></label>
          <label className="field" style={{ marginTop: 10, maxWidth: 320 }}>Cómo se obtuvo
            <select value={f.consent_source} onChange={set("consent_source")}>
              <option value="presencial">Presencial</option><option value="telefono">Teléfono</option>
              <option value="formulario_web">Formulario web</option><option value="documento_firmado">Documento firmado</option>
            </select>
          </label>
          <p className="small muted" style={{ marginTop: 8 }}>Catálogo de finalidades y bases jurídicas pendiente de validación por el DPO.</p>
        </fieldset>

        {dup && dup.identifier_matches.length > 0 && !conflict && (
          <div className="notice notice-warn" role="status">
            <strong>Ya existe un cliente con este documento</strong>
            {dup.identifier_matches.map((m) => <div key={m.id}><Link href={`/clientes/${m.id}`}>{m.display_name}</Link> · {m.primary_branch ?? "sin sede"}</div>)}
            Abra la ficha existente en lugar de crear otra, salvo que sea una persona distinta.
          </div>
        )}
        {dup && dup.shared_phone_contacts > 0 && (
          <div className="notice notice-info" role="status">
            Este teléfono ya figura en {dup.shared_phone_contacts} ficha{dup.shared_phone_contacts > 1 ? "s" : ""}. Es normal en familias: no se unirán.
          </div>
        )}

        {conflict && (
          <div className="notice notice-warn" role="alert">
            <strong>Posible duplicado: revise antes de continuar</strong>
            <ul>{conflict.map((c) => <li key={c.id}><Link href={`/clientes/${c.id}`}>{c.display_name}</Link> · {c.identifiers_masked.join(", ")}</li>)}</ul>
            <p>Si confirma que es una persona distinta, explique el motivo. Ambas fichas quedarán marcadas para revisión; nunca se fusionan automáticamente.</p>
            <label className="field">Motivo (mín. 10 caracteres)
              <textarea rows={2} value={justification} onChange={(e) => setJustification(e.target.value)} className={errs.justification ? "invalid" : ""} />
              {err("justification")}
            </label>
            <div className="row" style={{ marginTop: 10 }}>
              <button type="button" className="btn btn-warn" disabled={saving || justification.trim().length < 10} onClick={() => submit(true)}>Confirmar alta como persona distinta</button>
              <button type="button" className="btn" onClick={() => setConflict(null)}>Volver a revisar</button>
            </div>
          </div>
        )}

        {!conflict && (
          <div className="row">
            <button className="btn btn-primary" type="submit" disabled={saving}>{saving ? "Guardando…" : "Guardar cliente"}</button>
            <span className="small muted">Los campos con * son obligatorios.</span>
          </div>
        )}
      </form>
    </div>
  );
}
