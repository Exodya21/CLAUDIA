// Recorrido F5.2 + F5.3: Recepción (cobro con justificante no fiscal, cobro repetido, cierre de caja validado por otra
// persona, informe por sede) y RRHH (plantilla, nómina leída y confirmada, avisos de vencimientos, vacaciones con su
// responsable, resumen de nóminas). Datos FICTICIOS de la semilla.
// Uso: NOMINA=nomina_ficticia.pdf node e2e/recorrido_f52_f53.mjs <carpeta_capturas>   (semilla recién cargada)
import { chromium } from "playwright-core";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const NOMINA = process.env.NOMINA;
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
const go = async (href) => { await page.locator(`a[href="${href}"]`).first().click(); };

// 0) Si otro recorrido ya cerró hoy la caja de Barcelona, un responsable rechaza ese cierre para volver a contar
await login("Dirección (demo)");
for (const c of await (await page.request.get(`${W}/api/v1/reception/closings`)).json()) {
  if (c.branch === "Barcelona" && c.can_decide) {
    await page.request.post(`${W}/api/v1/reception/closings/${c.id}/decide`, { headers: { ...H, "Content-Type": "application/json" },
      data: { approve: false, note: "Recontar para el recorrido" } });
  }
}

// 1) Recepción Barcelona cobra una consulta en efectivo y emite el justificante (no es factura)
await login("Recepción Barcelona (demo)");
await go("/recepcion");
await page.getByRole("heading", { name: "Recepción" }).waitFor();
await page.getByLabel("Buscar cliente").fill("Lucía Ferrer");
await page.getByRole("button", { name: "Buscar" }).click();
await page.getByRole("button", { name: /Lucía Ferrer Demo/ }).first().click();
const form = page.getByLabel("Registrar cobro");
await form.getByText(/Pendiente .*€|Sin pendiente/).first().waitFor();
await form.getByLabel("Consulta (sin expediente)").check();
await form.getByLabel("Importe recibido").fill("60,00");
await form.getByRole("button", { name: "Registrar cobro y emitir justificante" }).click();
await page.getByText(/Cobro registrado · justificante REC-BCN-\d{4}-\d{6}/).waitFor();
const href = await page.getByRole("link", { name: "Ver e imprimir el justificante" }).getAttribute("href");
const pdf = await page.request.get(`${W}${href}`);
if (!(await pdf.body()).includes("NO ES UNA FACTURA")) throw new Error("el justificante debe decir que no es factura");
await page.screenshot({ path: `${OUT}/f52_01_cobro_justificante.png`, fullPage: true });
log("Cobro de consulta sin expediente con justificante numerado por sede (documento interno, no es factura)");

// 2) El mismo cobro otra vez: el sistema avisa y solo lo guarda con una explicación
await page.getByRole("button", { name: "Cobrar otro" }).click();
await page.getByLabel("Buscar cliente").fill("Lucía Ferrer");
await page.getByRole("button", { name: "Buscar" }).click();
await page.getByRole("button", { name: /Lucía Ferrer Demo/ }).first().click();
await form.getByLabel("Consulta (sin expediente)").check();
await form.getByLabel("Importe recibido").fill("60,00");
await form.getByRole("button", { name: "Registrar cobro y emitir justificante" }).click();
await page.getByText("Parece que este cobro ya está registrado").waitFor();
await page.screenshot({ path: `${OUT}/f52_02_posible_duplicado.png`, fullPage: true });
await form.getByLabel(/Si es un cobro distinto/).fill("Paga también la consulta de su hermano (ficticio)");
await form.getByRole("button", { name: "Registrar de todos modos" }).click();
await page.getByText(/Cobro registrado · justificante/).waitFor();
log("Cobro que parece repetido: aviso con los anteriores y solo se guarda con explicación (va a Contabilidad)");

// 3) Caja del día y cierre con diferencia (motivo obligatorio); queda pendiente de validar
await page.getByRole("tab", { name: "Caja del día" }).click();
await page.getByText("parecía repetido").waitFor();
const balanceText = await page.getByLabel("Resumen de caja").locator(".card").nth(3).locator(".stat").innerText();
const balance = Math.round(parseFloat(balanceText.replace(/[^\d,]/g, "").replace(",", ".")) * 100);
const counted = ((balance - 500) / 100).toFixed(2).replace(".", ",");
const closeForm = page.getByLabel("Cerrar caja");
await closeForm.getByLabel("Efectivo contado").fill(counted);
await closeForm.getByLabel("Diferencia").getByText(/Diferencia -5,00/).waitFor();
await closeForm.getByLabel(/Motivo de la diferencia/).fill("Faltan 5 € de cambio (ficticio)");
await closeForm.getByRole("button", { name: "Cerrar la caja de hoy" }).click();
await page.getByText("Caja cerrada. Queda pendiente de que un responsable la valide.").waitFor();
await page.getByText("Pendiente de validar", { exact: true }).first().waitFor();
await page.screenshot({ path: `${OUT}/f52_03_cierre_caja.png`, fullPage: true });
log("Caja del día: cobros, saldo según registros y cierre con diferencia explicada, pendiente de validar");

// 4) Recepción de Madrid solo ve su sede
await login("Recepción Madrid (demo)");
await go("/recepcion");
await page.getByRole("heading", { name: "Recepción" }).waitFor();
if (await page.getByLabel("Sede").count()) throw new Error("Recepción Madrid no debe elegir otras sedes");
await page.getByRole("tab", { name: "Caja del día" }).click();
await page.getByText("Madrid", { exact: true }).first().waitFor();
log("Recepción de Madrid trabaja solo con su sede (la caja de Barcelona no le aparece)");

// 5) Contabilidad valida el cierre (con nota por la diferencia) y anula el cobro repetido
await login("Contabilidad (demo)");
await go("/recepcion");
await page.getByRole("tab", { name: /Pendientes/ }).click();
const closeCard = page.getByLabel(/Validar cierre de caja · Barcelona/);
await closeCard.getByRole("button", { name: "Validar cierre" }).click();
await closeCard.getByText(/indique qué ha comprobado/).waitFor();
await closeCard.getByLabel("Nota de la decisión").fill("Revisado con el arqueo (ficticio)");
await closeCard.getByRole("button", { name: "Validar cierre" }).click();
await closeCard.waitFor({ state: "detached" });
const dup = page.getByLabel(/¿Cobro repetido\?/);
await dup.getByText("Paga también la consulta de su hermano").waitFor();
await page.screenshot({ path: `${OUT}/f52_04_pendientes_contabilidad.png`, fullPage: true });
await dup.getByLabel("Nota de la decisión").fill("Cobrado dos veces por error (ficticio)");
await dup.getByRole("button", { name: "Es repetido: anular" }).click();
await dup.waitFor({ state: "detached" });
log("Contabilidad valida el cierre (nunca quien contó) y anula el cobro repetido con motivo");

// 6) Informe del día por sede
await page.getByRole("tab", { name: "Informe" }).click();
await page.getByRole("heading", { name: "Barcelona" }).waitFor();
await page.getByText(/1 anulado\(s\)/).first().waitFor();
await page.getByText("Validado").first().waitFor();
await page.screenshot({ path: `${OUT}/f52_05_informe.png`, fullPage: true });
log("Informe diario por sede: cobros por concepto y forma de pago, anulados, repetidos y estado del cierre");

// 7) RRHH: Dirección pasa el agente de plantilla (en producción lo hace solo cada hora)
await login("Dirección (demo)");
for (const o of await (await page.request.get(`${W}/api/v1/organizations`)).json()) {
  await page.request.post(`${W}/api/v1/agents/rrhh/run?organization_id=${o.id}`, { headers: H });
}
await login("Recursos Humanos (demo)");
await go("/rrhh");
await page.getByRole("heading", { name: "Recursos Humanos" }).waitFor();
await page.getByRole("button", { name: "Laura Gómez Demo" }).waitFor();
await page.getByRole("row", { name: /Laura Gómez Demo/ }).getByText("Vence contrato").waitFor();
await page.getByRole("button", { name: "Daniel Ortiz Prueba" }).click();
const ficha = page.getByLabel("Ficha de Daniel Ortiz Prueba");
await ficha.getByText("Salario bruto anual").waitFor();
await ficha.getByLabel("Tipo de documento").selectOption("nomina");
await ficha.getByLabel("Archivo").setInputFiles(NOMINA);
await ficha.getByRole("button", { name: "Subir" }).click();
const rev = page.getByLabel("Revisión del documento");
await rev.getByText("Devengado − deducciones = líquido").waitFor();
await page.screenshot({ path: `${OUT}/f53_01_nomina_leida.png`, fullPage: true });
await rev.getByRole("button", { name: "Confirmar" }).click();
await ficha.getByText(/Líquido .*€/).first().waitFor();
log("Plantilla con avisos; nómina leída (periodo, devengado, deducciones, líquido que cuadran) y confirmada por RRHH");

// 8) Avisos de plantilla: el contrato que vence se convierte en tarea
await page.getByRole("tab", { name: /Avisos/ }).click();
const aviso = page.getByLabel(/Vence el contrato · Laura Gómez Demo/);
await aviso.waitFor();
await page.getByLabel(/Termina el periodo de prueba · Daniel Ortiz Prueba/).waitFor();
await page.getByLabel(/Diferencia de nómina .* · Laura Gómez Demo/).waitFor();
await page.screenshot({ path: `${OUT}/f53_02_avisos.png`, fullPage: true });
await aviso.getByRole("button", { name: "Crear tarea en mi agenda" }).click();
await aviso.waitFor({ state: "detached" });
log("Avisos: vencimiento de contrato, fin del periodo de prueba y diferencia de nómina; uno pasa a tarea en la agenda");

// 9) Nóminas para la gestoría: diferencia señalada y nómina por revisar
await page.getByRole("tab", { name: "Nóminas" }).click();
await page.getByRole("row", { name: /Laura Gómez Demo/ }).getByText("+18 %").waitFor();
await page.getByRole("row", { name: /Andrés Ruiz Demo/ }).getByText("Por revisar").waitFor();
await page.screenshot({ path: `${OUT}/f53_03_nominas.png`, fullPage: true });
log("Resumen de nóminas: confirmadas, por revisar y variación del +18 % señalada (sin calcular nóminas)");

// 10) Un asesor pide vacaciones desde su ficha; su líder las decide (nadie aprueba lo suyo)
await login("Asesor Laboral Barcelona (demo)");
await go("/rrhh");
await page.getByLabel("Ficha de Marcos Vidal Ficticio").waitFor();
const monday = new Date(); monday.setDate(monday.getDate() + ((8 - monday.getDay()) % 7 || 7) + 35);
const friday = new Date(monday); friday.setDate(monday.getDate() + 4);
const iso = (d) => d.toLocaleDateString("sv-SE");
const lf = page.getByLabel("Pedir ausencia");
await lf.getByLabel("Desde").fill(iso(monday));
await lf.getByLabel("Hasta").fill(iso(friday));
await lf.getByRole("button", { name: "Pedir" }).click();
await page.getByText(/5 pendientes de aprobar/).waitFor();
await page.screenshot({ path: `${OUT}/f53_04_mis_vacaciones.png`, fullPage: true });
await login("Líder Laboral (demo)");
await go("/rrhh");
await page.getByRole("tab", { name: "Ausencias" }).click();
const row = page.getByRole("row", { name: /Marcos Vidal Ficticio/ }).filter({ hasText: "solicitada" });
await row.getByRole("button", { name: "Aprobar" }).click();
await row.waitFor({ state: "detached" });
log("Vacaciones: el asesor las pide con su saldo a la vista y su líder las aprueba");

await browser.close();
