// Recorrido F1.2 + F2 (CRM → expediente → tareas → validación letrada) contra web + API + BD reales.
// Uso: node e2e/recorrido_f2.mjs <carpeta_capturas>   (WEB_URL y CHROME_PATH opcionales)
import { chromium } from "playwright-core";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const log = (m) => console.log("OK  " + m);
const stamp = Date.now().toString().slice(-5);

async function session(name) {
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: "es-ES", timezoneId: "Europe/Madrid" });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => { throw e; });
  await page.goto(`${W}/login`);
  await page.getByRole("listitem").filter({ hasText: name }).click();
  await page.waitForURL(`${W}/`);
  await page.getByText("Mi agenda de hoy").waitFor();
  return { ctx, page };
}

// 1) Recepción registra un lead: sin campaña no se puede para TikTok Live
{
  const { ctx, page } = await session("Recepción Barcelona");
  await page.screenshot({ path: `${OUT}/f2_01_inicio_recepcion.png` });
  await page.goto(`${W}/crm`);
  await page.getByRole("button", { name: "+ Nuevo lead" }).click();
  await page.getByLabel("Buscar persona").fill("Lucia Ferrer");
  await page.getByRole("button", { name: "Buscar" }).click();
  await page.getByRole("button", { name: /Lucía Ferrer Demo/ }).click();
  await page.getByLabel("Origen *").selectOption("tiktok_live");
  await page.getByRole("button", { name: "Registrar lead" }).click();
  await page.getByText(/exige indicar la campaña/).waitFor();
  log("Lead de TikTok Live sin campaña: rechazado (AT-05)");
  await page.getByLabel(/Campaña/).fill(`Directo laboral ${stamp}`);
  await page.getByRole("button", { name: "Registrar lead" }).click();
  await page.waitForURL(/\/crm\/[0-9a-f-]+$/);
  await page.getByRole("button", { name: "Marcar contactado" }).click();
  await page.getByText(/Estado cambiado a «Contactado»/).waitFor();
  await page.screenshot({ path: `${OUT}/f2_02_lead_recepcion.png` });
  log("Lead registrado con origen y campaña, y marcado como contactado");
  await page.goto(`${W}/crm`);
  await page.getByRole("tab", { name: "Pendientes de seguimiento" }).click();
  await page.getByText(/Más de 24 h|Más de 72 h|Más de 7 días/).first().waitFor();
  await page.screenshot({ path: `${OUT}/f2_03_seguimiento.png` });
  log("Bandeja de seguimiento 24 h / 72 h / 7 días");
  await ctx.close();
}

// 2) Asesor laboral convierte su lead en expediente, confirma encargo y crea tareas
let caseUrl;
{
  const { ctx, page } = await session("Asesor Laboral Barcelona");
  await page.goto(`${W}/crm`);
  // Primer lead abierto del asesor (en una segunda ejecución el de «cita solicitada» ya estará convertido)
  let row = null;
  for (const st of ["cita_solicitada", "contactado", "en_seguimiento", "nuevo"]) {
    await page.getByLabel("Estado").selectOption(st);
    await page.waitForTimeout(700);
    const rows = page.locator("tr.clickable");
    if (await rows.count()) { row = rows.first(); break; }
  }
  if (!row) throw new Error("El asesor no tiene leads abiertos");
  await row.click();
  await page.waitForURL(/\/crm\/[0-9a-f-]+$/);
  await page.getByRole("link", { name: "Abrir expediente" }).click();
  await page.waitForURL(/\/expedientes\/nuevo/);
  await page.getByLabel("Título *").fill(`Despido disciplinario (prueba ${stamp})`);
  await page.getByRole("button", { name: "Abrir expediente" }).click();
  await page.waitForURL(/\/expedientes\/[0-9a-f-]+\?nuevo=1/);
  caseUrl = page.url().split("?")[0];
  await page.getByText("Expediente abierto en preapertura").waitFor();
  log("Lead → expediente en preapertura con código consecutivo (AT-06)");
  await page.getByRole("button", { name: "Pasar a «Abierto»" }).click();
  await page.getByText(/confirme que consta el encargo/).waitFor();
  await page.getByLabel("Consta el encargo firmado por el cliente").check();
  await page.getByRole("button", { name: "Pasar a «Abierto»" }).click();
  await page.getByText(/Fase cambiada a «Abierto»/).waitFor();
  if (await page.getByRole("button", { name: "Pasar a «Resuelto»" }).count()) throw new Error("El asesor no debería poder resolver");
  log("Apertura exige encargo confirmado; el asesor no ve fases jurídicas (AT-16)");
  await page.getByRole("button", { name: "+ Tarea" }).click();
  await page.getByLabel("Qué hay que hacer *").fill("Presentar escrito de prueba");
  await page.getByLabel(/^Tipo(?! de relación)/).selectOption("plazo");
  const d = new Date(Date.now() + 10 * 864e5);
  await page.getByLabel(/Plazo legal \(opcional\)/).fill(d.toISOString().slice(0, 10));
  await page.getByLabel("Fuente del plazo *").fill("Diligencia ficticia de prueba");
  await page.getByRole("button", { name: "Crear tarea" }).click();
  await page.getByText(/Plazo legal \d{2}\/\d{2}\/\d{4} · SIN VALIDAR/).first().waitFor();
  await page.screenshot({ path: `${OUT}/f2_04_expediente_asesor.png`, fullPage: true });
  log("Tarea con plazo legal propuesto: queda SIN VALIDAR (AT-19)");
  await page.getByRole("button", { name: "Gestionar" }).first().click();
  await page.getByRole("button", { name: "Aplazar" }).click();
  await page.getByRole("button", { name: "Aplazar" }).last().click();
  await page.getByText(/Para aplazar indique motivo y nueva fecha/).waitFor();
  await page.getByLabel("Motivo del aplazamiento *").fill("El cliente aporta documentación la semana próxima");
  await page.getByRole("button", { name: "Aplazar" }).last().click();
  await page.getByText(/La fecha anterior queda en el historial/).waitFor();
  log("Aplazar exige motivo; la fecha anterior queda en el historial (AT-20)");
  await page.goto(`${W}/agenda`);
  // Las citas ficticias que se solapan están a 3 días vista: de jueves a domingo caen en la semana siguiente.
  await page.getByText(/Semana del/).waitFor();
  // Decide por el día de hoy (no por lo que haya cargado ya la página, que puede llegar tarde)
  const dow = new Date(new Date().toLocaleString("en-US", { timeZone: "Europe/Madrid" })).getDay();
  if (dow === 0 || dow >= 5) await page.getByRole("button", { name: "Semana siguiente →" }).click();
  await page.getByText("Solapa con otra cita").first().waitFor();
  await page.screenshot({ path: `${OUT}/f2_05_agenda_asesor.png` });
  log("Agenda semanal con solapamientos y vencidas");
  await ctx.close();
}

// 3) El líder laboral valida el plazo y resuelve el expediente
{
  const { ctx, page } = await session("Líder Laboral");
  await page.goto(`${W}/agenda`);
  await page.getByText(/pendientes? de su validación/).waitFor();
  await page.screenshot({ path: `${OUT}/f2_06_validacion_lider.png` });
  await page.goto(caseUrl);
  await page.getByRole("button", { name: "Gestionar" }).first().click();
  await page.getByRole("button", { name: "Validar plazo" }).click();
  await page.getByText("Plazo legal validado.").waitFor();
  log("Otro letrado valida el plazo legal propuesto (doble control)");
  await page.getByRole("button", { name: "Pasar a «En trámite»" }).click();
  await page.getByText(/Fase cambiada a «En trámite»/).waitFor();
  await page.getByLabel(/Motivo o resultado/).fill("Sentencia estimatoria (ficticia)");
  await page.getByRole("button", { name: "Pasar a «Resuelto»" }).click();
  await page.getByText(/Fase cambiada a «Resuelto»/).waitFor();
  await page.screenshot({ path: `${OUT}/f2_07_expediente_resuelto.png`, fullPage: true });
  log("Fase jurídica «Resuelto» solo por perfil autorizado y con motivo");
  await ctx.close();
}

// 4) Marketing: embudo, sin acceso a expedientes
{
  const { ctx, page } = await session("Marketing");
  await page.goto(`${W}/crm`);
  await page.getByRole("tab", { name: "Embudo" }).click();
  await page.getByText("Conversión", { exact: true }).waitFor();
  await page.screenshot({ path: `${OUT}/f2_08_embudo_marketing.png`, fullPage: true });
  await page.goto(caseUrl);
  await page.getByRole("heading", { name: "Acceso denegado" }).waitFor();
  log("Marketing ve el embudo y recibe 403 en expedientes");
  await ctx.close();
}
await browser.close();
