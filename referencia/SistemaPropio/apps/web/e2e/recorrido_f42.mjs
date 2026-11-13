// Recorrido F4.2: ficha del modelo EX en la web → código → extensión de Chrome que rellena una página de PRUEBA
// servida en la dirección de Mercurio (interceptada: no sale nada a Internet). Comprueba que no pulsa ningún botón.
// Uso: node e2e/recorrido_f42.mjs <carpeta_capturas>
import { chromium } from "playwright-core";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const CHROME = process.env.CHROME_PATH ?? "/usr/bin/google-chrome";
const EXT = resolve(new URL("../../extension-mercurio", import.meta.url).pathname);
const TEST_PAGE = readFileSync(join(EXT, "pruebas/formulario_prueba.html"), "utf8");
const MERCURIO = "https://mercurio.delegaciondelgobierno.gob.es/mercurio/prueba-extension.html";
const log = (m) => console.log("OK  " + m);

// 1) La asesora revisa y guarda la ficha del EX-10 y genera el código
const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
const ctx = await browser.newContext({ viewport: { width: 1360, height: 950 }, locale: "es-ES", timezoneId: "Europe/Madrid", acceptDownloads: true });
const page = await ctx.newPage();
page.on("pageerror", (e) => { throw e; });
await page.goto(`${W}/login`);
await page.getByRole("listitem").filter({ hasText: "Asesora Extranjería Madrid" }).click();
await page.waitForURL(`${W}/`);
await page.getByRole("link", { name: "Extranjería" }).click();
await page.getByRole("link", { name: "EXT-2026-0002" }).click();
const card = page.getByLabel("Datos para el formulario");
await card.getByRole("heading", { name: /Datos para el formulario EX-10/ }).waitFor();
await card.getByText(/datos propuestos pendientes de confirmar/).waitFor();
await card.scrollIntoViewIfNeeded();
await page.screenshot({ path: `${OUT}/f42_01_ficha_propuesta.png`, fullPage: true });
log("La ficha del EX-10 llega con propuestas (cliente, pasaporte leído, despacho) pendientes de confirmar");
await card.getByLabel("NIE (X-1234567-L)").fill("Y-7654321-Z");
await card.getByLabel("Estado civil").selectOption("S");
await card.getByLabel(/^Tipo de vía/).fill("Calle");
await card.getByLabel(/^Domicilio \(nombre de la vía\)/).fill("Ficticia");
await card.getByLabel("Número", { exact: true }).fill("14");
await card.getByLabel("Piso", { exact: true }).fill("8");
await card.getByRole("tab", { name: "Tipo de solicitud" }).click();
await card.getByLabel(/^Arraigo social/).check();
await card.getByRole("button", { name: "Guardar ficha" }).click();
await card.getByText("Ficha guardada.").waitFor();
log("La persona confirma la ficha y marca el supuesto (el sistema no lo elige)");
const dl = page.waitForEvent("download");
await card.getByRole("link", { name: /Vista previa del EX-10/ }).click();
if (!(await dl).suggestedFilename().startsWith("VISTA_PREVIA_EX-10")) throw new Error("nombre de la vista previa");
log("Vista previa interna del EX-10 rellenado (no sustituye al que emite Mercurio)");
await card.getByRole("button", { name: "Rellenar en Mercurio" }).click();
const code = (await card.getByLabel("Código para la extensión").locator(".mono").innerText()).trim();
if (!/^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(code)) throw new Error(`código ${code}`);
await page.screenshot({ path: `${OUT}/f42_02_codigo.png`, fullPage: true });
log(`Código temporal generado (${code.slice(0, 4)}-…), caduca a los 15 minutos`);
await browser.close();

// 2) Chrome con la extensión instalada; la «página de Mercurio» es la página de PRUEBA interceptada
const profile = mkdtempSync(join(tmpdir(), "sp-ext-"));
const ectx = await chromium.launchPersistentContext(profile, {
  executablePath: CHROME, headless: false, viewport: { width: 1200, height: 900 }, locale: "es-ES",
  args: ["--headless=new", "--no-sandbox", `--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`],
});
await ectx.route("https://mercurio.delegaciondelgobierno.gob.es/**", (r) => r.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: TEST_PAGE }));
let sw = ectx.serviceWorkers()[0] ?? await ectx.waitForEvent("serviceworker");
const extId = new URL(sw.url()).host;
const merc = await ectx.newPage();
await merc.goto(MERCURIO);
await merc.getByText("PÁGINA DE PRUEBA INVENTADA").waitFor();
const popup = await ectx.newPage();
await popup.goto(`chrome-extension://${extId}/popup.html`);
await popup.getByLabel("Código del expediente").fill(code);
await popup.getByRole("button", { name: "Traer datos" }).click();
await popup.getByText(/datos confirmados el/).waitFor();
await popup.getByText(/Marque en Mercurio: Arraigo social/).waitFor();
await popup.screenshot({ path: `${OUT}/f42_03_extension_datos.png` });
log("La extensión trae la ficha con el código (sin sesión ni contraseña)");
const v = (id) => merc.locator(`#${id}`).inputValue();
const txt = (id) => merc.locator(`#${id} option:checked`).innerText();
async function pestana(name) {  // la PERSONA cambia de pestaña (en Mercurio, con «Continuar»)
  await merc.bringToFront();
  await merc.getByRole("link", { name }).click();
}
// Un solo clic: los campos con identificador de Mercurio se rellenan en TODAS las pestañas
await popup.bringToFront();
await popup.getByRole("button", { name: "Rellenar esta página" }).click();
await popup.getByText(/Rellenados \d+ campos/).waitFor({ timeout: 15000 });
await popup.screenshot({ path: `${OUT}/f42_04_extension_informe.png` });
const checks = {
  pasaporte: (await v("extPasaporte")).startsWith("ZZ"), nie: (await v("extNie")) === "Y7654321Z",
  apellido1: (await v("extApellido1")).length > 0, segundo_no_tocado: (await v("extApellido2")) === "YA ESCRITO",
  sexo: (await v("extSexo")) !== "", fecha: /^\d{2}\/\d{2}\/\d{4}$/.test(await v("extFechaNacimiento")),
  estado_civil: (await v("extEstadoCivil")) === "S", tipo_via: (await v("extTipoVia")) === "CL",
  numero: (await v("extNumero")) === "14", piso: (await v("extPiso")) === "8",
  movil_9_cifras: /^\d{9}$/.test(await v("extTelefonoMovil")), contrasena_intacta: (await v("pwd")) === "",
  tutelada_intacta: !(await merc.locator("#tutelada").isChecked()), rep_legal_vacio: (await v("extNieRepresentante")) === "",
  presentador: (await v("preNombrePresentador")).includes("Despacho"), presentador_tipo: (await v("preTipodocumentoPresentador")) === "D",
  presentador_doc: (await v("preNiePresentador")) === "12345678Z",
  notif_nombre: (await v("notNombreNotificacion")).includes("Despacho"), notif_provincia: (await v("notCodigoProvinciaNotificacion")) === "28",
  notif_municipio: (await txt("notCodigoMunicipioNotificacion")) === "MADRID", notif_localidad: (await txt("notCodigoLocalidadNotificacion")) === "MADRID",
  notif_cp: (await v("notCodigoPostalNotificacion")) === "28001",
  dehu_sin_dato_no_marcado: !(await merc.locator("#chkConsentimientoNotificacion").isChecked()),
};
await merc.bringToFront();
await merc.screenshot({ path: `${OUT}/f42_05_pestana_extranjero.png`, fullPage: true });
await pestana("DOMICILIO DE NOTIFICACIÓN");
await merc.screenshot({ path: `${OUT}/f42_06_pestana_notificacion.png`, fullPage: true });
const bad = Object.entries(checks).filter(([, ok]) => !ok).map(([k]) => k);
if (bad.length) throw new Error("Campos mal rellenados: " + bad.join(", "));
log("Reconocimiento por los identificadores reales de Mercurio: un clic rellena extranjero/a, presentador y notificación");
log("Formatos de Mercurio: N.I.E. sin guiones, fecha dd/mm/aaaa, móvil de 9 cifras; no sobrescribe ni toca contraseña ni «Persona tutelada»");
log("Domicilio de notificación: espera a que se carguen municipio y localidad tras la provincia");
await pestana("TIPO DE AUTORIZACIÓN");
if (await merc.locator("#chkConsientoConsultaDocumentos").isChecked()) throw new Error("Ha marcado NO CONSIENTO");
if (await merc.locator("input[name=datosForAut]:checked").count()) throw new Error("Ha elegido el tipo de autorización");
const pressed = await merc.evaluate(() => window.__pulsado ?? null);
if (pressed) throw new Error("La extensión ha pulsado " + pressed);
log("No marca «NO CONSIENTO» ni elige el supuesto; ningún botón pulsado (Continuar, Concluir, Firmar y registrar, Presentación electrónica)");
await popup.getByRole("button", { name: "Olvidar datos" }).click();
await popup.getByLabel("Código del expediente").waitFor();
log("«Olvidar datos» borra la ficha de la extensión");
await ectx.close();
console.log("RECORRIDO F4.2 COMPLETO");
