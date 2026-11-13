// Recorrido F5.4: Contabilidad completa. Factura recibida leída (propone, no calcula IVA) con alta rápida del
// proveedor, validación, remesa con doble firma de Dirección (nunca quien la propone), fichero SEPA, previsión de
// tesorería, cierre del mes preparado → revisado → aprobado (inmutable) y exportación. Datos FICTICIOS de la semilla.
// Uso: FACTURA=factura_ficticia.pdf node e2e/recorrido_f54.mjs <carpeta_capturas>   (semilla recién cargada)
import { chromium } from "playwright-core";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const FACTURA = process.env.FACTURA;
if (!FACTURA) throw new Error("Falta FACTURA (factura ficticia generada con app.accounting.invoices.invoice_pdf)");
const log = (m) => console.log("OK  " + m);

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: "es-ES", timezoneId: "Europe/Madrid", acceptDownloads: true });
const page = await ctx.newPage();
page.on("pageerror", (e) => { throw e; });

async function login(name) {
  await ctx.clearCookies();
  await page.goto(`${W}/login`);
  await page.getByRole("listitem").filter({ hasText: name }).click();
  await page.waitForURL(`${W}/`);
}
const tab = (name) => page.getByRole("tab", { name }).click();

// 1) Contabilidad sube una factura: la lectura propone los datos y detecta que el proveedor no existe
await login("Contabilidad (demo)");
await page.goto(`${W}/contabilidad?tab=facturas`);
await page.getByRole("heading", { name: "Registrar factura recibida" }).waitFor();
await page.getByLabel("Factura (PDF o imagen)").setInputFiles(FACTURA);
await page.getByRole("button", { name: "Leer factura" }).click();
const quick = page.getByLabel("Alta rápida de proveedor");
await quick.waitFor();
await quick.getByLabel("Nombre del proveedor").fill("Limpiezas Ficticias SL");
await quick.getByLabel("Categoría del proveedor").selectOption("limpieza");
await quick.getByRole("button", { name: "Crear proveedor" }).click();
const form = page.getByLabel("Datos de la factura");
await quick.waitFor({ state: "detached" });
if (!(await form.getByLabel("Proveedor *").locator("option:checked").innerText()).includes("Limpiezas Ficticias")) throw new Error("proveedor no elegido");
await form.getByText("Base + IVA − retención = total").waitFor();
if ((await form.getByLabel("Número *").inputValue()) !== "LF-2026-118") throw new Error("número no leído");
await page.screenshot({ path: `${OUT}/f54_01_lectura_factura.png`, fullPage: true });
log("Lectura de factura: propone número, fechas, base, IVA de la factura y total; alta rápida del proveedor con su IBAN");

// 2) Comprobación: si las cifras no cuadran no se puede registrar; se registra sin validar (lo valida otra persona)
await form.getByLabel("Total *").fill("250,00");
await form.getByText(/Las cifras no cuadran/).waitFor();
if (!(await form.getByRole("button", { name: "Registrar factura" }).isDisabled())) throw new Error("debe bloquearse si no cuadra");
await form.getByLabel("Total *").fill("242,00");
await form.getByLabel(/He comprobado los datos/).uncheck();
await form.getByRole("button", { name: "Registrar factura" }).click();
await page.getByText(/Factura LF-2026-118 de Limpiezas Ficticias SL registrada \(por validar\)/).waitFor().catch(async (e) => { await page.screenshot({ path: `${OUT}/f54_fallo.png`, fullPage: true }); throw e; });
log("Base + IVA − retención debe dar el total para registrar; el sistema nunca calcula el IVA");

// 3) La misma factura otra vez: archivo ya registrado y aviso de duplicado
await page.getByLabel("Factura (PDF o imagen)").setInputFiles(FACTURA);
await page.getByRole("button", { name: "Leer factura" }).click();
await page.getByText(/Este archivo ya está registrado: factura LF-2026-118/).waitFor();
await page.screenshot({ path: `${OUT}/f54_02_duplicado.png`, fullPage: true });
log("Subir el mismo archivo otra vez: aviso de factura ya registrada");

// 4) Validar la factura y comprobar la lista
await page.getByLabel("Estado de las facturas").selectOption("recibida");
const row = page.getByRole("row").filter({ hasText: "LF-2026-118" });
await row.getByRole("button", { name: "Revisar" }).click();
await page.getByLabel("Revisar factura LF-2026-118").getByRole("button", { name: "Validar" }).click();
await page.getByText("Factura LF-2026-118 validada.").waitFor();
await page.getByLabel("Estado de las facturas").selectOption("validada");
await page.getByRole("row").filter({ hasText: "LF-2026-118" }).getByText("Validada").waitFor();
await page.screenshot({ path: `${OUT}/f54_03_facturas.png`, fullPage: true });
log("Factura validada con actividad y oficina (centro de coste)");

// 5) Tesorería: saldos, previsión y remesa propuesta con la nueva factura y la vencida de la gestoría
await tab("Tesorería y remesas");
await page.getByLabel("Previsión de pagos").getByText("Vencido").waitFor();
const nb = page.getByLabel("Nueva remesa");
await nb.getByText(/Limpiezas Ficticias SL/).waitFor();
await nb.getByRole("checkbox").first().waitFor();
for (const cb of await nb.getByRole("checkbox").all()) await cb.check();
await nb.getByRole("button", { name: "Proponer remesa" }).click();
await page.getByText(/Remesa REM-\d{4}-0002 propuesta por .*pendiente de dos firmas/).waitFor();
const code = (await page.getByText(/Remesa REM-\d{4}-0002 propuesta/).innerText()).match(/REM-\d{4}-0002/)[0];
if (await page.getByLabel(`Remesa ${code}`).getByRole("button", { name: "Autorizar", exact: true }).count()) throw new Error("quien propone no puede firmar");
await page.screenshot({ path: `${OUT}/f54_04_tesoreria_remesa.png`, fullPage: true });
log(`Previsión de pagos (vencido, 7, 30, 60, 90 días) y remesa ${code} propuesta; quien la propone no puede firmarla`);

// 6) Firma 1: Dirección desde sus pendientes de Contabilidad
await login("Dirección (demo)");
await page.goto(`${W}/contabilidad?tab=pendientes`);
const sig1 = page.locator(".card, .notice").filter({ hasText: `Firma 1 de 2` }).filter({ hasText: code }).first();
await sig1.waitFor();
await page.screenshot({ path: `${OUT}/f54_05_firma_pendiente.png`, fullPage: true });
await sig1.getByRole("button", { name: "Autorizar (mi firma)" }).click();
await page.locator(".card, .notice").filter({ hasText: "Firma 2 de 2" }).filter({ hasText: code }).first().waitFor({ state: "attached" }).catch(() => {});
log("Primera firma de Dirección desde «Pendientes de decidir»");

// La misma persona no puede firmar dos veces
await page.goto(`${W}/contabilidad?tab=tesoreria`);
const card = page.getByLabel(`Remesa ${code}`);
await card.getByText("Pendiente de firmas").waitFor();
if (await card.getByRole("button", { name: "Autorizar", exact: true }).count()) throw new Error("no puede firmar dos veces");
log("Quien ya firmó no puede dar la segunda firma");

// 7) Firma 2: el socio director autoriza; se descarga el SEPA y se marca como subida al banco
await login("Socio Director (demo)");
await page.goto(`${W}/contabilidad?tab=tesoreria`);
const card2 = page.getByLabel(`Remesa ${code}`);
await card2.getByLabel(`Nota de firma ${code}`).fill("Conforme con la previsión (ficticio)");
await card2.getByRole("button", { name: "Autorizar", exact: true }).click();
await page.getByText(`Ha firmado la remesa ${code}.`).waitFor();
await card2.getByText("Autorizada").waitFor();
if (await card2.getByRole("link", { name: "Descargar fichero SEPA" }).count()) throw new Error("Dirección autoriza; el fichero lo prepara Contabilidad");
log("Segunda firma de otra persona de Dirección: remesa autorizada");

// Contabilidad descarga el fichero SEPA y, tras subirlo a la banca electrónica, lo marca
await login("Contabilidad (demo)");
await page.goto(`${W}/contabilidad?tab=tesoreria`);
await card2.getByText("Autorizada").waitFor();
const [dl] = await Promise.all([page.waitForEvent("download"), card2.getByRole("link", { name: "Descargar fichero SEPA" }).click()]);
const xml = await (await import("node:fs/promises")).readFile(await dl.path(), "utf8");
if (!xml.includes("pain.001.001.03") || !xml.includes("ES9399990007110000000066")) throw new Error("SEPA incorrecto");
await card2.getByRole("button", { name: "Ya la he subido al banco" }).click();
await card2.getByText("Subida al banco").waitFor();
await page.screenshot({ path: `${OUT}/f54_06_remesa_autorizada.png`, fullPage: true });
log("Contabilidad descarga el fichero SEPA pain.001 y lo marca como subido al banco (lo sube una persona, nunca el sistema)");

// 8) Cierre del mes: Contabilidad prepara y revisa; Dirección aprueba y queda congelado
await page.goto(`${W}/contabilidad?tab=cierre`);
await page.getByLabel("Cuadro de mando").getByRole("cell", { name: "Resultado provisional" }).waitFor();
await page.getByRole("button", { name: /Preparar el cierre de/ }).click();
await page.getByText(/Cierre de .* preparado \(revisión 1\)/).waitFor();
await page.getByRole("button", { name: "Recalcular (nueva revisión)" }).click();
await page.getByText(/preparado \(revisión 2\)/).waitFor();
await page.getByText(/Revisión 1 · Sustituido/).waitFor();
await page.getByLabel("Nota del cierre").fill("Pendientes revisados con la gestoría; cifras provisionales (ficticio)");
await page.getByRole("button", { name: "Dar por revisado" }).click();
await page.getByText("Cierre revisado: pendiente de aprobación de Dirección.").waitFor();
await page.screenshot({ path: `${OUT}/f54_07_cierre_revisado.png`, fullPage: true });
log("Cierre preparado, recalculado (la revisión anterior queda sustituida, nunca se borra) y revisado con nota");

await login("Dirección (demo)");
await page.goto(`${W}/contabilidad?tab=cierre`);
await page.getByRole("button", { name: "Aprobar cierre" }).click();
await page.getByText("Cierre aprobado y congelado.").waitFor();
await page.getByText("Aprobado por Dirección").first().waitFor();
if (await page.getByRole("button", { name: /Recalcular/ }).count()) throw new Error("un cierre aprobado no se recalcula");
const csvHref = await page.getByRole("link", { name: "Exportar CSV" }).getAttribute("href");
const csv = await (await page.request.get(`${W}${csvHref}`)).text();
if (!csv.includes("Resultado")) throw new Error("CSV sin resultado");
await page.getByText("Propuesta de asientos: no disponible aún").waitFor();
await page.screenshot({ path: `${OUT}/f54_08_cierre_aprobado.png`, fullPage: true });
log("Dirección aprueba el cierre: cifras congeladas con huella, exportación CSV; asientos «No disponible aún» (T-40)");

// 9) Una persona sin permiso de contabilidad no ve tesorería y la API lo deniega
await login("Recepción Barcelona (demo)");
const r = await page.request.get(`${W}/api/v1/accounting/treasury?organization_id=00000000-0000-0000-0000-000000000000`);
if (![403, 404].includes(r.status())) throw new Error(`esperaba 403/404 y fue ${r.status()}`);
await page.goto(`${W}/contabilidad`);
await page.getByText("Su rol no tiene acceso a Contabilidad.").waitFor();
log("Sin permiso: Contabilidad no aparece y la API deniega (registrado en auditoría)");

await browser.close();
console.log("Recorrido F5.4 completado.");
