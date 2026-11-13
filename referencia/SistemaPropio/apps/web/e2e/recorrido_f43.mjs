// Recorrido F4.3: subir contrato, padrón, tasa y TIE FICTICIOS → la lectura propone → la persona valida →
// los datos (también los del empleador) llegan a la ficha como propuestas con su origen → la persona guarda.
// Uso: node e2e/recorrido_f43.mjs <carpeta_capturas>   (muestras en docs/pruebas/muestras, scripts/muestras_f43.py)
import { chromium } from "playwright-core";
import { resolve } from "node:path";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const M = resolve(new URL("../../../docs/pruebas/muestras", import.meta.url).pathname);
const CASE = process.env.CASO ?? "EXT-2026-0001";
const log = (m) => console.log("OK  " + m);

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const ctx = await browser.newContext({ viewport: { width: 1360, height: 950 }, locale: "es-ES", timezoneId: "Europe/Madrid" });
const page = await ctx.newPage();
page.on("pageerror", (e) => { throw e; });
await page.goto(`${W}/login`);
await page.getByRole("listitem").filter({ hasText: "Asesora Extranjería Madrid" }).click();
await page.waitForURL(`${W}/`);
await page.getByRole("link", { name: "Extranjería" }).click();
await page.getByRole("link", { name: CASE }).click();
await page.getByRole("heading", { name: /^Extranjería · / }).waitFor();

// 1) Subida de cuatro documentos a la vez: la lectura propone tipo y datos
await page.getByLabel(/Subir documentos/).setInputFiles(["FICTICIO_contrato_trabajo.pdf", "FICTICIO_empadronamiento.pdf",
  "FICTICIO_tasa_790_052.pdf", "FICTICIO_TIE.png"].map((f) => `${M}/${f}`));
const rowOf = (name) => page.getByRole("row").filter({ hasText: name });
await rowOf("FICTICIO_TIE.png").getByText(/MRZ correcta/).waitFor({ timeout: 90000 });
for (const [f, t] of [["FICTICIO_contrato_trabajo.pdf", "Contrato de trabajo"], ["FICTICIO_empadronamiento.pdf", "Certificado de empadronamiento"],
  ["FICTICIO_tasa_790_052.pdf", "Justificante de la tasa"], ["FICTICIO_TIE.png", "TIE / NIE"]]) {
  await rowOf(f).getByText(new RegExp(`Parece ${t}`)).waitFor();
}
if (await rowOf("FICTICIO_TIE.png").getByText(/no coincide/).count()) throw new Error("la TIE ficticia debería ser de la clienta");
log("Cuatro documentos leídos: tipo propuesto para cada uno (contrato, padrón, tasa, TIE con MRZ)");
const contrato = rowOf("FICTICIO_contrato_trabajo.pdf");
await contrato.getByText(/datos leídos para la ficha \(pasan a la ficha al marcarlo válido\)/).click();
await contrato.getByText("Construcciones Ficticias Demo SL").waitFor();
await contrato.getByText("B12345674").waitFor();
await rowOf("FICTICIO_tasa_790_052.pdf").getByText("Datos leídos").click();
await rowOf("FICTICIO_tasa_790_052.pdf").getByText("0520000000000000000ABCD1").waitFor();
await contrato.scrollIntoViewIfNeeded();
await page.screenshot({ path: `${OUT}/f43_01_datos_leidos.png`, fullPage: true });
log("Se ve qué se ha leído de cada documento (empresa, CIF, cuenta de cotización… y el NRC de la tasa)");

// 2) Antes de validar, nada del contrato llega a la ficha
const card = page.getByLabel("Datos para el formulario");
await card.getByRole("tab", { name: "Empleador/a o actividad" }).click();
if (await card.getByLabel("Nombre o razón social").first().inputValue() !== "") throw new Error("la ficha usó un documento sin validar");
log("Mientras el documento no esté validado, la ficha no lo usa");

// 3) La persona valida contrato, padrón y TIE
for (const f of ["FICTICIO_contrato_trabajo.pdf", "FICTICIO_empadronamiento.pdf", "FICTICIO_TIE.png"]) {
  await rowOf(f).getByRole("button", { name: "Revisar" }).click();
  const form = page.getByLabel(new RegExp(`^Revisión de ${f.replace(".", "\\.")}`));
  await form.getByRole("button", { name: "Confirmar como válido" }).click();
  await rowOf(f).getByRole("button", { name: "Corregir" }).waitFor();
}
log("La persona confirma los tres documentos como válidos");

// 4) La ficha trae las propuestas con su origen, incluido el empleador
await card.getByRole("tab", { name: "Empleador/a o actividad" }).click();
const nombre = card.getByLabel("Nombre o razón social").first();
await nombre.waitFor();
if (await nombre.inputValue() !== "Construcciones Ficticias Demo SL") throw new Error("empresa no propuesta");
if (await card.getByLabel("NIF/NIE/DNI").first().inputValue() !== "B12345674") throw new Error("CIF no propuesto");
await card.getByText("Propuesto: documento leído: Contrato de trabajo").first().waitFor();
await card.scrollIntoViewIfNeeded();
await page.screenshot({ path: `${OUT}/f43_02_ficha_empleador.png`, fullPage: true });
log("Pestaña Empleador: empresa, CIF, domicilio y representante propuestos desde el contrato");
await card.getByRole("tab", { name: "Contrato de trabajo" }).click();
if (await card.getByLabel("Código de cuenta de cotización").inputValue() !== "28123456789") throw new Error("CCC");
if (await card.getByLabel("Denominación del puesto").inputValue() !== "Peón de la construcción") throw new Error("puesto");
log("Pestaña Contrato: cuenta de cotización, puesto, código de contrato y centro de trabajo");
await card.getByRole("tab", { name: "Persona extranjera solicitante" }).click();
if (await card.getByLabel("NIE (X-1234567-L)").inputValue() !== "Y7654321G") throw new Error("NIE de la TIE");
if (await card.getByLabel("Código postal").first().inputValue() !== "28901") throw new Error("CP del padrón");
await card.getByText("Propuesto: documento leído: Certificado de empadronamiento").first().waitFor();
await page.screenshot({ path: `${OUT}/f43_03_ficha_extranjero.png`, fullPage: true });
log("Pestaña Extranjero/a: N.I.E. de la TIE y domicilio del padrón, cada uno con su origen");

// 4 bis) Herramientas: volver a leer y diagnóstico sin datos
await rowOf("FICTICIO_contrato_trabajo.pdf").getByRole("button", { name: "Corregir" }).click();
const tools = page.getByLabel("Herramientas de lectura de FICTICIO_contrato_trabajo.pdf");
await tools.getByRole("button", { name: "Diagnóstico de la lectura (sin datos)" }).click();
const diag = await tools.getByLabel("Diagnóstico sin datos").inputValue();
if (!/cotización/.test(diag) || /B12345674|Construcciones|Y7654321G/.test(diag)) throw new Error("diagnóstico con datos");
await tools.scrollIntoViewIfNeeded();
await page.screenshot({ path: `${OUT}/f43_04_diagnostico_sin_datos.png`, fullPage: true });
await tools.getByRole("button", { name: "Volver a leer" }).click();
await page.getByText("Documento leído de nuevo.").waitFor({ timeout: 90000 });
log("Diagnóstico de la lectura sin datos (etiquetas visibles, valores como XXX/999) y «Volver a leer»");
// Subir otra vez el mismo archivo no lo duplica
await page.getByLabel(/Subir documentos/).setInputFiles(`${M}/FICTICIO_tasa_790_052.pdf`);
await page.getByText(/Ya estaba subido en este expediente/).waitFor({ timeout: 60000 });
log("El mismo archivo subido dos veces no se duplica");

// 4 ter) Revisión automática: el sistema dice qué falla sin que nadie lo busque
const rev = page.getByLabel("Revisión automática de la lectura");
await rev.getByRole("heading", { name: "Revisión automática de la lectura" }).waitFor();
await rev.getByText("Ver el informe que se copia").click();
const informe = await rev.getByLabel("Informe de lectura sin datos").inputValue();
if (!/INFORME DE LECTURA/.test(informe) || !/Justificante de la tasa/.test(informe) || !/Leídos: .*Código de cuenta de cotización/.test(informe) || /B12345674|Construcciones|Y7654321G|Ferrer|Carla/.test(informe)) throw new Error("informe con datos");
await rev.scrollIntoViewIfNeeded();
await page.screenshot({ path: `${OUT}/f43_05_revision_automatica.png`, fullPage: true });
log("Revisión automática: por cada documento qué se ha leído, qué falta o se ha descartado; informe para Claude sin datos");

// 5) Solo al guardar queda confirmado
await card.getByRole("button", { name: "Guardar ficha" }).click();
await card.getByText("Ficha guardada.").waitFor();
log("La persona guarda la ficha: ya puede generar el código para la extensión de Mercurio");
await browser.close();
