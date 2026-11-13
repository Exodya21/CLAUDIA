// Recorrido F5.4b: rutina de trabajo de Contabilidad (pasos que el sistema comprueba, tareas en la Agenda, «no aplica»
// con motivo, responsables) e informes semanales/quincenales/mensuales (generados por la rutina, PDF, revisión de
// Dirección). Datos FICTICIOS de la semilla.   Uso: node e2e/recorrido_f54b.mjs <carpeta_capturas>   (semilla recién cargada)
import { chromium } from "playwright-core";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const log = (m) => console.log("OK  " + m);
const H = { "X-Requested-With": "sistema-propio" };

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: "es-ES", timezoneId: "Europe/Madrid" });
const page = await ctx.newPage();
page.on("pageerror", (e) => { throw e; });

async function login(name) {
  await ctx.clearCookies();
  await page.goto(`${W}/login`);
  await page.getByRole("listitem").filter({ hasText: name }).click();
  await page.waitForURL(`${W}/`);
}
const tab = (name) => page.getByRole("tab", { name, exact: true }).click();
const step = (title) => page.getByLabel(`Paso ${title}`);

// 1) Contabilidad entra y lo primero que ve es su rutina: lo de hoy, la semana y el cierre del mes, con lo comprobado.
//    (Funciona sobre la semilla recién cargada o después de los demás recorridos: el estado de cada paso depende de los datos.)
await login("Contabilidad (demo)");
await page.locator('a[href="/contabilidad"]').first().click();
await page.getByRole("tab", { name: "Rutina de trabajo", selected: true }).waitFor();
await page.getByLabel("Cumplimiento del mes").waitFor();
await page.getByText(/Comprobación: /).first().waitFor();
await page.screenshot({ path: `${OUT}/f54b_01_rutina.png`, fullPage: true });
log("La rutina abre Contabilidad: pasos de hoy, de la semana y del cierre (días 1–5) con responsable y lo que el sistema ha comprobado");

// 2) La rutina no se tacha: al validar las facturas pendientes, el paso pasa solo a «Hecho» y su tarea de la Agenda se cierra
await page.goto(`${W}/contabilidad?tab=facturas`);
await page.getByLabel("Estado de las facturas").selectOption("recibida");
await page.getByRole("table").first().locator("tbody tr").first().waitFor();
for (let i = 0; i < 10; i++) {
  const btn = page.getByRole("button", { name: "Revisar" }).first();
  if (!(await btn.count())) break;
  await btn.click();
  await page.getByLabel(/Revisar factura/).getByRole("button", { name: "Validar" }).click();
  await page.getByText(/validada\./).waitFor();
  await page.waitForTimeout(300);
}
await tab("Rutina de trabajo");
await page.getByRole("button", { name: /Ver lo hecho/ }).click();
await page.getByRole("row").filter({ hasText: "Validar las facturas recibidas" }).getByText("Hecho").first().waitFor();
await page.screenshot({ path: `${OUT}/f54b_02_paso_comprobado.png`, fullPage: true });
log("Validar la factura basta: el sistema comprueba y da el paso por hecho (con evidencia); no se marca a mano");

// 3) «No aplica» exige motivo
const daily = step("Importar los extractos del día anterior");
if (await daily.count()) {
  await daily.getByRole("button", { name: "No aplica…" }).click();
  await daily.getByLabel(/Motivo no aplica/).fill("corto");
  if (!(await daily.getByRole("button", { name: "Confirmar" }).isDisabled())) throw new Error("debe exigir motivo");
  await daily.getByLabel(/Motivo no aplica/).fill("Banco sin servicio de extractos hoy (ficticio)");
  await daily.getByRole("button", { name: "Confirmar" }).click();
  await page.getByRole("row").filter({ hasText: "Importar los extractos del día anterior" }).getByText("No aplica").waitFor();
  log("«No aplica» solo con motivo (queda quién y por qué)");
} else {
  log("Fin de semana: sin pasos diarios (se comprueba «no aplica» en las pruebas de la API)");
}

// 3b) Extracto del banco en Excel (muestra ficticia del repositorio): se lee aunque tenga filas de título
const EXCEL = process.env.EXCEL ?? new URL("../../../docs/pruebas/muestras/FICTICIO_extracto_cuenta_A_octubre.xlsx", import.meta.url).pathname;
await tab("Banco y conciliación");
await page.getByRole("tab", { name: /Cuenta A · Laboral/ }).click();
await page.getByLabel("Extracto bancario").setInputFiles(EXCEL);
await page.getByRole("button", { name: "Importar extracto", exact: true }).click();
await page.getByText(/Extracto importado: 4 movimiento\(s\) nuevo\(s\)/).waitFor();
await page.screenshot({ path: `${OUT}/f54b_06_extracto_excel.png`, fullPage: true });
log("Extracto en Excel (.xlsx con titular, cuenta y periodo antes de la cabecera) importado y comprobado");

// 4) Informes: Contabilidad genera el semanal de la semana pasada y lo descarga en PDF
await tab("Informes");
const lastWeek = new Date(Date.now() - 7 * 864e5).toLocaleDateString("sv-SE", { timeZone: "Europe/Madrid" });
await page.getByLabel("Tipo a generar").selectOption("semanal");
await page.getByLabel("Un día del periodo").fill(lastWeek);
await page.getByRole("button", { name: "Generar ahora" }).click();
await page.getByText(/Informe semanal semana del .* generado \(versión 1\)/).waitFor();
const view = page.getByLabel(/Informe semana del/);
await view.getByText("Rutina de trabajo").waitFor();
const pdfHref = await view.getByRole("link", { name: "PDF" }).getAttribute("href");
const pdf = await page.request.get(`${W}${pdfHref}`);
if (!(await pdf.body()).subarray(0, 4).equals(Buffer.from("%PDF"))) throw new Error("PDF");
if (await view.getByRole("button", { name: "Marcar como revisado" }).count()) throw new Error("Contabilidad no revisa");
await page.screenshot({ path: `${OUT}/f54b_03_informe_semanal.png`, fullPage: true });
log("Informe semanal: cifras por oficina y actividad, comparación, pendientes, pagos y cumplimiento de la rutina; PDF y CSV");

// 4b) Los pasos semanales y mensuales están en la Agenda de su responsable (aquí, Dirección)
await login("Dirección (demo)");
await page.goto(`${W}/agenda`);
await page.getByText(/Rutina Contabilidad · Revisar el informe semanal/).first().waitFor();
log("Los pasos semanales y mensuales están en la Agenda de su responsable");

// 5) La rutina automática genera los informes que tocan y pide a Dirección que los revise (correo sin cifras)
const orgs = await (await page.request.get(`${W}/api/v1/organizations`)).json();
const es = orgs.find((o) => o.name.startsWith("Despacho Demo España"));
const run = await page.request.post(`${W}/api/v1/agents/contabilidad/run?organization_id=${es.id}`, { headers: H });
if (!run.ok()) throw new Error(`run ${run.status()}`);
await page.goto(`${W}/contabilidad?tab=pendientes`);
const card = page.locator(".card, .notice").filter({ hasText: /Informe quincenal listo/ }).first();
await card.waitFor();
await page.screenshot({ path: `${OUT}/f54b_04_informe_pendiente.png`, fullPage: true });
await card.getByRole("button", { name: "Marcar como revisado" }).click();
await page.locator(".card, .notice").filter({ hasText: /Informe quincenal listo/ }).filter({ has: page.getByRole("button", { name: "Marcar como revisado" }) }).waitFor({ state: "detached" });
await page.getByRole("tab", { name: "Informes" }).click();
await page.getByRole("row").filter({ hasText: /Quincenal/ }).getByText("Revisado").first().waitFor();
log("La rutina genera el quincenal (y el semanal y mensual que tocan); Dirección lo revisa desde sus pendientes de Contabilidad");

// 6) Dirección asigna responsables
await tab("Rutina de trabajo");
await page.getByRole("button", { name: "Responsables de cada paso" }).click();
await page.getByLabel("Responsable de Revisar el informe semanal").selectOption({ label: "Socio Director (demo)" });
await page.waitForTimeout(500);
if ((await page.getByLabel("Responsable de Revisar el informe semanal").locator("option:checked").innerText()) !== "Socio Director (demo)") throw new Error("responsable");
await page.screenshot({ path: `${OUT}/f54b_05_responsables.png`, fullPage: true });
log("Dirección asigna el responsable de cada paso (solo personas con permiso para ese paso)");

// 7) Sin permiso no hay rutina ni informes
await login("Recepción Barcelona (demo)");
const r = await page.request.get(`${W}/api/v1/accounting/reports?organization_id=${es.id}`);
if (r.status() !== 403) throw new Error(`esperaba 403 y fue ${r.status()}`);
log("Recepción no ve la rutina ni los informes (403 auditado)");

await browser.close();
console.log("Recorrido F5.4b completado.");
