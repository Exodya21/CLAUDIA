// Recorrido F5.1: conciliación bancaria de una cuenta (lo que pidió Dirección en su «Instrucción final»), bandeja
// única de propuestas y agente de mensajes al cliente por el portal propio. Datos y extractos FICTICIOS.
// Uso: node e2e/recorrido_f51.mjs <carpeta_capturas>   (necesita la semilla recién cargada)
import { chromium } from "playwright-core";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const log = (m) => console.log("OK  " + m);
const H = { "X-Requested-With": "sistema-propio", "Content-Type": "application/json" };

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
const detail = () => page.getByLabel("Detalle del movimiento");
async function openMovement(text) {
  await page.getByRole("button", { name: text }).first().click();
  await detail().waitFor();
}

// 1) Contabilidad importa el extracto (Norma 43 ficticio) de la cuenta A y ve importados/conciliados/pendientes/errores
await login("Contabilidad (demo)");
await page.locator('a[href="/contabilidad"]').first().click();
await page.getByRole("heading", { name: "Contabilidad" }).waitFor();
await page.getByRole("tab", { name: "Banco y conciliación" }).click();  // desde F5.4b la primera pestaña es la rutina
await page.getByRole("tab", { name: /Cuenta A · Laboral/ }).waitFor();
await page.getByRole("button", { name: "Importar extracto FICTICIO de prueba" }).click();
await page.getByText(/Extracto importado: \d+ movimiento\(s\) nuevo\(s\)/).waitFor();
await page.getByText(/Cuadra: saldo inicial/).waitFor();
await page.getByLabel(/^Importados: [1-9]/).waitFor();
await page.getByLabel(/^Pendientes: [1-9]/).waitFor();
await page.screenshot({ path: `${OUT}/f51_01_importacion_cuadra.png`, fullPage: true });
log("Extracto importado: saldo inicial + movimientos = saldo final; resumen importados / conciliados / pendientes / errores");

// 2) Reimportar el mismo extracto no duplica nada
await page.getByRole("button", { name: "Importar extracto FICTICIO de prueba" }).click();
await page.getByText(/ya se importó.*No se duplica nada/).waitFor();
log("El mismo extracto otra vez se rechaza: no se duplican movimientos");

// 3) Transferencia con referencia del expediente: el agente lo explica y Contabilidad valida (el cobro queda confirmado)
await openMovement(/TRANSF DEMO CLIENTE REF LAB-/);
await detail().getByText("Propuesta del agente · Referencia del expediente").waitFor();
await detail().getByText(/trae la referencia LAB-2026-\d{4}/).waitFor();
await page.screenshot({ path: `${OUT}/f51_02_propuesta_referencia.png`, fullPage: true });
await detail().getByRole("button", { name: "Validar propuesta" }).click();
await page.getByText("Emparejamiento validado: el cobro queda confirmado.").waitFor();
await detail().getByText("Conciliado", { exact: true }).waitFor();
log("Referencia del expediente: propuesta explicada, validada por Contabilidad y cobro confirmado");

// 4) Liquidación de TPV: bruto − comisión = neto; al validar, la comisión también queda conciliada
await openMovement(/LIQUIDACION TPV/);
await detail().getByText(/bruto .* − comisión .* = neto/).waitFor();
await detail().getByRole("button", { name: "Validar propuesta" }).click();
await detail().getByText("Conciliado", { exact: true }).waitFor();
await detail().getByText(/COMISION TPV/).waitFor();
log("TPV con comisión: la liquidación neta cuadra con los cobros con tarjeta y la comisión se concilia a la vez");

// 5) Ingreso sin identificar: no se concilia solo; a mano solo si cuadra exactamente
await openMovement(/TRANSFERENCIA DE J\. FICTICIO/);
await detail().getByText(/no hay cobro registrado que lo justifique/).waitFor();
await detail().getByRole("button", { name: "Conciliar a mano" }).click();
await detail().getByText(/debe cuadrar exactamente/).waitFor();
await page.screenshot({ path: `${OUT}/f51_03_ingreso_sin_identificar.png`, fullPage: true });
await detail().getByRole("button", { name: "Cancelar" }).click();
log("Ingreso sin identificar: excepción para Contabilidad; la conciliación manual exige cuadre exacto");

// 6) Pendientes de Contabilidad (dentro de su propio módulo): la cuota de la Seguridad Social se justifica
await page.getByRole("tab", { name: /Pendientes de decidir/ }).click();
const tgss = page.getByLabel(/Revisar .*Cuenta A/).filter({ hasText: "parece seguridad social" });
await tgss.waitFor();
await page.screenshot({ path: `${OUT}/f51_04_bandeja_contabilidad.png`, fullPage: true });
await tgss.getByRole("button", { name: "Aprobar" }).click();
await tgss.waitFor({ state: "detached" });
log("Pendientes de Contabilidad: excepción del banco (TGSS) aprobada y justificada con su categoría");

// 7) Traspaso A → C: al importar la cuenta C aparece la pareja; nunca cuenta como ingreso
await page.getByRole("tab", { name: "Banco y conciliación" }).click();
await page.getByRole("tab", { name: /Cuenta C · Tesorería/ }).click();
await page.getByRole("button", { name: "Importar extracto FICTICIO de prueba" }).click();
await page.getByText(/Extracto importado/).waitFor();
await openMovement(/TRASPASO DESDE CUENTA A/);
await detail().getByText(/No es un ingreso/).waitFor();
await detail().getByRole("button", { name: "Validar propuesta" }).click();
await detail().getByText("Traspaso entre cuentas", { exact: true }).waitFor();
await page.getByRole("tab", { name: "Errores" }).click();
await page.getByText("Sin errores: todas las líneas se leyeron y los saldos cuadran.").waitFor();
await page.getByRole("tab", { name: "Conciliados" }).click();
await page.screenshot({ path: `${OUT}/f51_05_traspaso_y_errores.png`, fullPage: true });
log("Traspaso entre cuentas propias conciliado en las dos cuentas; pestaña de errores vacía");

// 8) Agente de mensajes: al abrir un expediente prepara la bienvenida; la asesora la aprueba y llega al portal
await login("Asesor Laboral Barcelona (demo)");
const orgs = await (await page.request.get(`${W}/api/v1/organizations`)).json();
const org = orgs[0];
const branch = org.branches.find((b) => b.name === "Barcelona");
const contact = (await (await page.request.get(`${W}/api/v1/contacts?q=${encodeURIComponent("Lucía Ferrer")}`)).json()).items[0];
const caseResp = await page.request.post(`${W}/api/v1/cases`, { headers: H, data: {
  organization_id: org.id, materia: "laboral", branch_id: branch.id,
  contact_id: contact.id, title: "Recorrido F5.1 (ficticio)", summary: "[FICTICIO]" } });
if (!caseResp.ok()) throw new Error(`alta de expediente: ${await caseResp.text()}`);
const cf = await caseResp.json();
const tr = await page.request.post(`${W}/api/v1/cases/${cf.id}/transition`, { headers: H, data: { to: "abierto", engagement_confirmed: true } });
if (!tr.ok()) throw new Error(`apertura: ${await tr.text()}`);
// El mensaje por aprobar aparece en el propio expediente y en Comunicaciones → «Mensajes por aprobar»
await page.locator('a[href="/comunicaciones"]').first().click();
await page.getByRole("tab", { name: /Mensajes por aprobar/ }).click();
const card = page.getByLabel(`Bienvenida al abrir el expediente · ${cf.code}`);
await card.getByText(/^Buenos días, Lucía Ferrer Demo\. Le confirmamos que hemos abierto su expediente/).waitFor();
await page.screenshot({ path: `${OUT}/f51_06_bienvenida_propuesta.png`, fullPage: true });
await card.getByRole("button", { name: "Aprobar y enviar" }).click();
await card.waitFor({ state: "detached" });
await page.goto(`${W}/expedientes/${cf.id}`);
await page.getByText(/Le confirmamos que hemos abierto su expediente/).first().waitFor();
log("Bienvenida (DR-PLT-1) propuesta al abrir el expediente, aprobada por la asesora y publicada en su conversación");

// 9) Dirección: configuración de agentes en Administración; ve el banco pero no concilia
await login("Dirección (demo)");
await page.locator('a[href="/administracion"]').first().click();
await page.getByRole("tab", { name: "Agentes automáticos" }).click();
await page.getByRole("heading", { name: "Conciliación bancaria" }).waitFor();
await page.getByRole("heading", { name: "Mensajes al cliente" }).waitFor();
await page.getByText("No valida ni concilia nada por su cuenta: propone y explica.").waitFor();
await page.getByLabel("Medición de los últimos 7 días").waitFor();
await page.screenshot({ path: `${OUT}/f51_07_agentes.png`, fullPage: true });
await page.locator('a[href="/contabilidad"]').first().click();
await page.getByRole("heading", { name: "Contabilidad" }).waitFor();
await page.getByRole("tab", { name: "Banco y conciliación" }).click();
await page.getByRole("tab", { name: /Cuenta A · Laboral/ }).waitFor();
if (await page.getByRole("button", { name: "Revisar ahora" }).count()) throw new Error("Dirección no debe conciliar");
log("Dirección: agentes (en Administración) con sus límites y medición semanal; ve el banco sin poder conciliar (separación de funciones)");

await browser.close();
