// Garantías de la extensión de Mercurio que se comprueban en el código (el relleno real se prueba en e2e/recorrido_f42.mjs).
import { readFileSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { describe, expect, it } from "vitest";

const DIR = path.resolve(__dirname, "../../extension-mercurio");
const read = (f: string) => readFileSync(path.join(DIR, f), "utf8");

describe("extensión Mercurio", () => {
  it("nunca pulsa botones ni envía formularios", () => {
    for (const f of ["matcher.js", "content.js", "background.js"]) {
      const src = read(f);
      expect(src).not.toMatch(/\.click\s*\(/);
      expect(src).not.toMatch(/\.submit\s*\(|requestSubmit/);
      expect(src).not.toMatch(/dispatchEvent\(new [^)]*("|')(click|submit)/);
    }
  });

  it("solo actúa en Mercurio y solo pide permiso de almacenamiento", () => {
    const m = JSON.parse(read("manifest.json"));
    expect(m.manifest_version).toBe(3);
    expect(m.permissions).toEqual(["storage"]);
    expect(m.content_scripts[0].matches).toEqual(["https://mercurio.delegaciondelgobierno.gob.es/*"]);
  });

  it("reconoce etiquetas y apartados habituales", () => {
    const ctx: { SPMatcher?: { fieldOf: (s: string) => string | null; roleOf: (s: string) => string | null;
      fromId: (el: { id: string; name?: string }) => { role: string; field: string } | null } } = {};
    vm.runInNewContext(read("matcher.js"), { window: ctx, globalThis: ctx });
    const m = ctx.SPMatcher!;
    expect(m.fieldOf("Primer apellido")).toBe("apellido1");
    expect(m.fieldOf("2º Apellido")).toBe("apellido2");
    expect(m.fieldOf("Nombre del padre")).toBe("padre");
    expect(m.fieldOf("N.I.E.")).toBe("nie");
    expect(m.fieldOf("Fecha de nacimiento (2)")).toBe("fecha_nacimiento");
    expect(m.fieldOf("Código postal")).toBe("cp");
    expect(m.fieldOf("Nombre/Razón Social")).toBe("nombre");
    expect(m.roleOf("Datos del presentador")).toBe("rep");
    expect(m.roleOf("Domicilio de notificación")).toBe("notif");
    expect(m.roleOf("Datos del reagrupante")).toBe("fam");
    expect(m.roleOf("Datos del reagrupado:")).toBe("ext");
    expect(m.roleOf("Datos del extranjero/a")).toBe("ext");
    // Identificadores reales de Mercurio (diagnóstico del 05/11/2026)
    const id = (x: string) => m.fromId({ id: x });
    expect(id("extPasaporte")).toEqual({ role: "ext", field: "pasaporte" });
    expect(id("extNie")).toEqual({ role: "ext", field: "nie" });
    expect(id("extCodigoNacionalidad")).toEqual({ role: "ext", field: "nacionalidad" });
    expect(id("extTelefonoMovil")).toEqual({ role: "ext", field: "telefono" });
    expect(id("extNieRepresentante")).toEqual({ role: "ext", field: "rl_doc" });
    expect(id("preNiePresentador")).toEqual({ role: "rep", field: "doc" });
    expect(id("notNombreNotificacion")).toEqual({ role: "notif", field: "nombre" });
    expect(id("reaApellido1Reagrupante")).toEqual({ role: "fam", field: "apellido1" });
    expect(id("empNombreEmpresa2")).toEqual({ role: "ent", field: "nombre" });
    expect(id("empNieEmpresa")).toEqual({ role: "emp", field: "doc" });
    expect(id("chkConsentimientoNotificacion")).toEqual({ role: "notif", field: "consiento_dehu" });
    expect(id("chkConsientoConsultaDocumentos")).toBeNull();   // «NO CONSIENTO»: jamás
    expect(id("empActividadEmpresaCNAE-ts-control")).toBeNull();
    expect(id("notEmailNotificacionAux")).toBeNull();
  });
});
