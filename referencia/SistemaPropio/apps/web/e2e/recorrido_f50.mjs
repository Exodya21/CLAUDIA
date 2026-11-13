// Recorrido F5.0 (gastos con justificante, cobros, caja, devoluciones) contra web + API + BD reales.
// Uso: TICKET=ticket.jpg EXTRACTO=extracto.csv node e2e/recorrido_f50.mjs <carpeta_capturas>
// El ticket debe ser una imagen FICTICIA de 14,00 € con fecha de hoy (ver docs/pruebas/evidencias_F5.0.md).
import { chromium } from "playwright-core";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const TICKET = process.env.TICKET;
const EXTRACTO = process.env.EXTRACTO;
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const log = (m) => console.log("OK  " + m);

async function as(name) {
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 950 }, locale: "es-ES", timezoneId: "Europe/Madrid" });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => { throw e; });
  await page.goto(`${W}/login`);
  await page.getByRole("listitem").filter({ hasText: name }).click();
  await page.waitForURL(`${W}/`);
  return { ctx, page };
}

// 1) Asesor sube un ticket: el sistema propone los datos y la persona confirma
let expenseUrl;
{
  const { ctx, page } = await as("Asesor Laboral Barcelona");
  await page.getByRole("link", { name: "Gastos" }).click();
  await page.getByLabel("Justificante").setInputFiles(TICKET);
  await page.waitForURL(/\/gastos\/[0-9a-f-]+\?nuevo=1/);
  expenseUrl = page.url().split("?")[0];
  await page.getByText("Justificante leído").waitFor();
  const total = await page.getByLabel("Total pagado").inputValue();
  if (total !== "14,00") throw new Error(`total propuesto ${total}`);
  const iva = await page.getByLabel(/IVA \(cuota del ticket\)/).inputValue();
  if (iva !== "2,43") throw new Error(`IVA propuesto ${iva}`);
  await page.screenshot({ path: `${OUT}/f50_01_ticket_leido.png`, fullPage: true });
  log("Ticket leído en el servidor: total 14,00 € e IVA 2,43 € propuestos (confianza visible)");
  await page.getByLabel("Concepto").selectOption("desplazamiento");
  await page.getByLabel("Forma de pago").selectOption("tarjeta_empresa");
  await page.getByLabel(/^Tarjeta/).selectOption({ index: 1 });
  await page.getByLabel(/^Descripción/).fill("Aparcamiento vista oral (ficticio)");
  await page.getByRole("button", { name: "Confirmar y enviar a Contabilidad" }).click();
  await page.getByText("Gasto enviado a Contabilidad.").waitFor();
  log("La persona revisa, completa y envía a Contabilidad");
  await ctx.close();
}

// 2) Recepción cobra en efectivo un expediente y hace el arqueo de su caja
{
  const { ctx, page } = await as("Recepción Barcelona");
  await page.getByRole("link", { name: "Economía" }).click();
  await page.getByLabel("Código de expediente").fill("LAB-2026-0001");
  await page.getByRole("button", { name: "Buscar" }).click();
  await page.getByRole("button", { name: "Registrar cobro" }).click();
  await page.getByLabel("Importe recibido").fill("50,00");
  await page.getByRole("button", { name: "Registrar cobro" }).last().click();
  await page.getByText(/Cobro de 50,00.€ registrado/).waitFor();
  log("Recepción registra un cobro en efectivo sin ver la economía del expediente");
  await page.getByRole("tab", { name: "Caja" }).click();
  const box = page.getByLabel("Caja Barcelona");
  await box.getByRole("button", { name: "Arqueo" }).click();
  await box.getByLabel("Efectivo contado").fill("1,00");
  await box.getByRole("button", { name: "Guardar" }).click();
  await box.getByText(/explique el motivo/).waitFor();
  await box.getByLabel(/Observaciones/).fill("Recuento de prueba ficticio");
  await box.getByRole("button", { name: "Guardar" }).click();
  await box.getByText(/Arqueo registrado con una diferencia/).waitFor();
  await page.screenshot({ path: `${OUT}/f50_02_caja_recepcion.png`, fullPage: true });
  log("Arqueo: si no cuadra exige motivo y deja el ajuste registrado");
  await ctx.close();
}

// 3) ATC investiga la devolución pero no puede aprobarla
{
  const { ctx, page } = await as("Atención al cliente");
  await page.getByRole("link", { name: "Economía" }).click();
  await page.getByRole("tab", { name: "Devoluciones" }).click();
  await page.locator("tr.clickable").first().click();
  await page.getByRole("button", { name: "Pasar a revisión" }).click();
  await page.getByRole("button", { name: "Confirmar" }).click();
  await page.getByRole("button", { name: "Escalar a letrado" }).waitFor();
  if (await page.getByRole("button", { name: "Aprobar" }).count()) throw new Error("ATC puede aprobar");
  log("ATC registra y revisa la devolución; no tiene botón de aprobar (A-09)");
  await ctx.close();
}

// 4) Contabilidad: confirma cobros, decide la devolución, revisa el gasto y concilia la tarjeta
{
  const { ctx, page } = await as("Contabilidad");
  await page.getByRole("link", { name: "Economía" }).click();
  await page.getByRole("tab", { name: "Cobros por confirmar" }).click();
  const row = page.getByRole("row", { name: /LAB-2026-0001.*50,00/ }).first();
  await row.getByRole("textbox").fill("F-2026-0007");
  await row.getByRole("button", { name: "Confirmar" }).click();
  await page.getByRole("row", { name: /LAB-2026-0001.*50,00/ }).first().waitFor({ state: "detached" }).catch(() => undefined);
  log("Contabilidad confirma el cobro y anota el nº de factura del programa homologado");
  await page.getByRole("tab", { name: "Devoluciones" }).click();
  await page.locator("tr.clickable").first().click();
  await page.getByRole("button", { name: "Aprobar" }).click();
  await page.getByLabel("Motivo").fill("Cobro duplicado comprobado en el banco (ficticio)");
  await page.getByRole("button", { name: "Confirmar" }).click();
  await page.getByRole("button", { name: "Registrar pago" }).click();
  await page.getByLabel("Referencia del pago").fill("TRF-DEV-0001");
  await page.getByRole("button", { name: "Confirmar" }).click();
  await page.locator(".badge", { hasText: "Pagada" }).first().waitFor();
  await page.screenshot({ path: `${OUT}/f50_03_devolucion_contabilidad.png`, fullPage: true });
  log("Contabilidad aprueba con motivo y registra el pago de la devolución");

  await page.goto(expenseUrl);
  await page.getByRole("heading", { name: "Revisión de Contabilidad" }).waitFor();
  await page.getByRole("button", { name: "Aprobar" }).click();
  await page.getByText("Gasto aprobado.").waitFor();
  log("Contabilidad ve el justificante y aprueba el gasto");
  await page.goto(`${W}/gastos`);
  await page.getByRole("tab", { name: "Tarjetas y extractos" }).click();
  await page.getByLabel("Extracto CSV").setInputFiles(EXTRACTO);
  await page.getByText(/Extracto importado/).waitFor();
  await page.getByRole("row", { name: /APARCAMIENTO FICTICIO/ }).getByRole("button", { name: "Conciliar" }).click();
  await page.getByText("Gasto conciliado con el extracto.").waitFor();
  await page.getByRole("row", { name: /RESTAURANTE SIN TICKET/ }).getByText("Sin justificante").waitFor();
  await page.screenshot({ path: `${OUT}/f50_04_tarjetas.png`, fullPage: true });
  log("Extracto importado: el cargo con ticket se concilia y el que no tiene justificante queda señalado");
  await page.getByRole("tab", { name: "Resumen mensual" }).click();
  await page.getByText("Total del mes").waitFor();
  await page.screenshot({ path: `${OUT}/f50_05_resumen_gastos.png`, fullPage: true });
  log("Resumen mensual por persona, sede, concepto y forma de pago (descargable)");
  await ctx.close();
}

// 5) El asesor ve la economía en la ficha del expediente; Marketing no ve nada económico
{
  const { ctx, page } = await as("Asesor Laboral Barcelona");
  await page.goto(`${W}/expedientes`);
  await page.getByRole("link", { name: /^LAB-2026-\d{4}$/ }).first().click();
  await page.getByRole("heading", { name: "Economía" }).waitFor();
  await page.getByText("Pendiente de cobro").waitFor();
  await page.screenshot({ path: `${OUT}/f50_06_expediente_economia.png`, fullPage: true });
  log("Ficha del expediente: pactado, cobrado y pendiente");
  await ctx.close();
  const mk = await as("Marketing");
  if (await mk.page.getByRole("link", { name: "Economía" }).count()) throw new Error("Marketing ve Economía");
  log("Marketing no ve el módulo de Economía");
  await mk.ctx.close();
}

await browser.close();
console.log("RECORRIDO F5.0 COMPLETO");
