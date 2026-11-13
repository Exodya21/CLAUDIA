import { describe, expect, it } from "vitest";
import { ApiError, backupValid, fieldErrors, hasPerm, parseError, type BackupRun, type Me } from "@/lib/api";
import { deviceLabel, fmtDate, fmtDateTime } from "@/lib/format";
import { MODULES } from "@/lib/modules";
import { checkIdentifier, checkPhone, normalizeDoc } from "@/lib/validation";

describe("formato horario Europe/Madrid", () => {
  it("convierte UTC a hora local de Madrid (invierno, UTC+1)", () => {
    expect(fmtDateTime("2026-11-02T12:30:00Z")).toBe("02/11/2026, 13:30");
  });
  it("convierte UTC a hora local de Madrid (verano, UTC+2)", () => {
    expect(fmtDateTime("2026-07-15T22:15:00Z")).toBe("16/07/2026, 00:15");
  });
  it("las fechas civiles no se desplazan", () => {
    expect(fmtDate("1990-01-01")).toBe("01/01/1990");
    expect(fmtDate(null)).toBe("—");
  });
});

describe("validación de documentos en el navegador (espejo del servidor)", () => {
  it("DNI y NIE con letra de control", () => {
    expect(checkIdentifier("DNI", "12345678Z")).toBeNull();
    expect(checkIdentifier("DNI", "12345678A")).toMatch(/letra/);
    expect(checkIdentifier("NIE", "X1234567L")).toBeNull();
    expect(checkIdentifier("NIE", "X1234567A")).toMatch(/letra/);
  });
  it("normaliza separadores", () => {
    expect(normalizeDoc("12.345.678-z")).toBe("12345678Z");
  });
  it("teléfono", () => {
    expect(checkPhone("+34 611 000 999")).toBeNull();
    expect(checkPhone("123")).not.toBeNull();
  });
});

describe("cliente de API", () => {
  it("interpreta el JSON de error uniforme", () => {
    const e = parseError(422, { error: { code: "validacion", message: "Revise", details: [{ field: "phone", message: "mal" }] } });
    expect(e).toBeInstanceOf(ApiError);
    expect(e.body.code).toBe("validacion");
    expect(fieldErrors(e)).toEqual({ phone: "mal" });
  });
  it("respuesta no estándar produce un mensaje genérico", () => {
    expect(parseError(500, "<html>").message).toMatch(/No se ha podido/);
  });
  it("hasPerm recorre todas las entidades", () => {
    const me = { permissions: { a: ["contact.search"], b: ["audit.read"] } } as unknown as Me;
    expect(hasPerm(me, "audit.read")).toBe(true);
    expect(hasPerm(me, "grant.manage")).toBe(false);
  });
});

describe("módulos", () => {
  it("los módulos futuros están marcados como pendientes y enlazan requisitos", () => {
    const pend = MODULES.filter((m) => m.status === "pendiente");
    expect(pend.map((m) => m.slug)).toEqual(
      ["citas", "fichas-laborales", "documentos", "facturacion", "direccion"]);
    for (const m of pend) expect(m.requisitos.length).toBeGreaterThan(0);
  });
});

describe("F0.2 seguridad", () => {
  it("una copia solo es válida con restauración y auditoría íntegra", () => {
    const base = { restore_ok: true, audit_chain_ok: true, matches_live_chain: true } as BackupRun;
    expect(backupValid(base)).toBe(true);
    expect(backupValid({ ...base, audit_chain_ok: false })).toBe(false);
    expect(backupValid({ ...base, matches_live_chain: false })).toBe(false);
    expect(backupValid({ ...base, restore_ok: false })).toBe(false);
  });
  it("describe el dispositivo de una sesión", () => {
    expect(deviceLabel("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36")).toBe("Chrome · Windows");
    expect(deviceLabel("Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36 Edg/130.0")).toBe("Edge · Windows");
    expect(deviceLabel(null)).toBe("Dispositivo desconocido");
  });
  it("Administración solo aparece con su permiso", () => {
    const m = MODULES.find((x) => x.slug === "administracion");
    // Usuarios y copias (admin.users.manage) o configuración de agentes (agents.manage, F5.1); sin permiso, oculto
    expect(m?.perm ?? null).toBeNull();
    expect(m?.anyPerm).toEqual(["admin.users.manage", "agents.manage"]);
  });
  it("Contabilidad (F5.4) se ve con banco, tesorería o cierre, nunca sin permiso", () => {
    const m = MODULES.find((x) => x.slug === "contabilidad");
    expect(m?.status).toBe("operativo");
    expect(m?.anyPerm).toEqual(["bank.read", "treasury.read", "accounting.read"]);
    for (const r of ["DR-CON-1", "DR-CON-4", "DR-CON-5", "DR-CON-7", "DR-CON-8"]) expect(m?.requisitos).toContain(r);
  });
});

describe("F5.0 importes", () => {
  it("interpreta importes en formato español y rechaza los mal escritos", async () => {
    const { parseMoney, centsToInput } = await import("@/lib/format");
    expect(parseMoney("45,50")).toBe(4550);
    expect(parseMoney("1.234,56")).toBe(123456);
    expect(parseMoney("12.5")).toBe(1250);
    expect(parseMoney("12,555")).toBeNull();
    expect(parseMoney("abc")).toBeNull();
    expect(centsToInput(1800)).toBe("18,00");
  });
  it("Economía y Gastos están en el menú solo con sus permisos", () => {
    expect(MODULES.find((m) => m.slug === "gastos")?.perm).toBe("expense.submit");
    expect(MODULES.find((m) => m.slug === "economia")?.anyPerm).toContain("refund.decide");
    expect(MODULES.find((m) => m.slug === "facturacion")?.status).toBe("pendiente");
  });
});
