// Recorrido F4.1 (expediente de extranjería) contra web + API + BD reales, sobre una base recién sembrada.
// Uso: PASAPORTE=pasaporte_ficticio.png node e2e/recorrido_f41.mjs <carpeta_capturas>
// El pasaporte debe ser una imagen FICTICIA (país UTO de la OACI) generada con app.seed_immigration.passport_image.
import { chromium } from "playwright-core";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const PASAPORTE = process.env.PASAPORTE;
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const log = (m) => console.log("OK  " + m);

async function as(name) {
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 950 }, locale: "es-ES", timezoneId: "Europe/Madrid", acceptDownloads: true });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => { throw e; });
  await page.goto(`${W}/login`);
  await page.getByRole("listitem").filter({ hasText: name }).click();
  await page.waitForURL(`${W}/`);
  return { ctx, page };
}
async function openCase(page, code) {
  await page.getByRole("link", { name: "Extranjería" }).click();
  await page.getByRole("link", { name: code }).click();
  await page.getByRole("heading", { name: /^Extranjería · / }).waitFor();
}

// 1) Asesora: bandeja, subida de un pasaporte, lectura MRZ y confirmación
{
  const { ctx, page } = await as("Asesora Extranjería Madrid");
  await page.getByRole("link", { name: "Extranjería" }).click();
  await page.getByRole("heading", { name: "Extranjería", exact: true }).waitFor();
  await page.getByRole("row", { name: /EXT-2026-0001/ }).waitFor();
  await page.screenshot({ path: `${OUT}/f41_01_bandeja.png`, fullPage: true });
  log("Bandeja de trámites por fase, con documentos por revisar y caducidades");

  await openCase(page, "EXT-2026-0001");
  await page.getByLabel(/Subir documentos/).setInputFiles(PASAPORTE);
  await page.getByText(/parece Pasaporte.*\(confianza alta\)/).waitFor({ timeout: 60000 });
  log("Pasaporte leído en el servidor: MRZ correcta, tipo propuesto con confianza alta");
  const row = page.getByRole("row").filter({ hasText: /MRZ correcta: PRUEBA,? RECORRIDO/ });
  await row.waitFor();
  await row.getByRole("button", { name: "Revisar" }).click();
  if (await page.getByLabel(/^Revisión de /).getByLabel("Tipo de documento").inputValue() !== "pasaporte") throw new Error("tipo no propuesto");
  await page.screenshot({ path: `${OUT}/f41_02_lectura_pasaporte.png`, fullPage: true });
  await page.getByRole("button", { name: "Confirmar como válido" }).click();
  await page.getByText("Documento confirmado.").waitFor();
  await page.getByRole("heading", { name: "Documentación exigida" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${OUT}/f41_03_lista_documentos.png`, fullPage: true });
  log("La persona confirma; la lista de documentación exigida se actualiza");
  await ctx.close();
}

// 2) Paquete para Mercurio: comprobación, problemas que bloquean y descarga
{
  const { ctx, page } = await as("Asesora Extranjería Madrid");
  await openCase(page, "EXT-2026-0003");
  await page.getByRole("alert", { name: "Avisos del expediente" }).getByText(/pasaporte caduca/).waitFor();
  log("Aviso de pasaporte que caduca en menos de 90 días");
  await page.getByRole("button", { name: "Comprobar paquete" }).click();
  await page.getByText("No está listo para presentar").waitFor();
  const dl = page.waitForEvent("download");
  await page.getByRole("link", { name: /Descargar igualmente/ }).click();
  const file = await dl;
  if (!file.suggestedFilename().startsWith("mercurio_EXT-2026-0003")) throw new Error(file.suggestedFilename());
  await page.screenshot({ path: `${OUT}/f41_04_paquete_mercurio.png`, fullPage: true });
  log("Paquete: indica lo que falta y permite un borrador registrado (.zip con índice y ficha de datos)");

  // Fase «Presentado» exige motivo si faltan documentos
  await page.getByLabel("Siguiente fase").selectOption("presentado");
  await page.getByRole("button", { name: "Registrar fase" }).click();
  await page.getByText(/Faltan documentos obligatorios/).waitFor();
  await page.getByLabel("Número de registro (resguardo)").fill("REGAGE-E2E-0001");
  await page.getByLabel(/^Nota/).fill("Se presenta por urgencia; el resto se aporta en plazo (ficticio)");
  await page.getByRole("button", { name: "Registrar fase" }).click();
  await page.getByText("Fase cambiada a «Presentado».").waitFor();
  log("Presentado con número de registro; si faltan documentos se exige y guarda el motivo");
  await ctx.close();
}

// 3) Requerimiento: crea una tarea para el letrado SIN calcular el plazo legal
{
  const { ctx, page } = await as("Asesora Extranjería Madrid");
  await openCase(page, "EXT-2026-0004");
  await page.getByLabel("Siguiente fase").selectOption("requerimiento");
  await page.getByLabel(/^Nota/).fill("Piden contrato de alquiler actualizado (ficticio)");
  await page.getByRole("button", { name: "Registrar fase" }).click();
  await page.getByText(/Se ha creado una tarea para que el letrado fije el plazo legal/).waitFor();
  await page.getByText(/Requerimiento EXT-2026-0004: fijar plazo legal/).first().waitFor();
  await page.screenshot({ path: `${OUT}/f41_05_requerimiento.png`, fullPage: true });
  log("Requerimiento registrado: tarea de plazo para el letrado, sin fecha legal inventada");
  if (await page.getByRole("option", { name: /Resolución favorable/ }).count()) throw new Error("asesora puede resolver");
  await ctx.close();
}

// 4) Líder de Extranjería: valida la lista de un trámite y registra la resolución favorable
{
  const { ctx, page } = await as("Líder Extranjería");
  await page.getByRole("link", { name: "Extranjería" }).click();
  await page.getByRole("tab", { name: "Catálogo de trámites" }).click();
  const r = page.getByRole("row", { name: /Arraigo sociolaboral/ }).first();
  await r.getByRole("button", { name: "Validar lista" }).click();
  await page.getByText(/validada\. Queda registrado/).waitFor();
  await page.screenshot({ path: `${OUT}/f41_06_catalogo.png`, fullPage: true });
  log("Legal Extranjería valida la lista de documentos del trámite (con fuente oficial)");
  await page.getByRole("tab", { name: "Bandeja de trámites" }).click();
  await page.getByRole("link", { name: "EXT-2026-0005" }).click();
  await page.getByLabel("Siguiente fase").selectOption("requerimiento_respondido");
  await page.getByRole("button", { name: "Registrar fase" }).click();
  await page.getByText(/Fase cambiada a «Requerimiento respondido»/).waitFor();
  await page.getByLabel("Siguiente fase").selectOption("resolucion_favorable");
  await page.getByLabel(/Fecha de la resolución/).fill(new Date().toISOString().slice(0, 10));
  await page.getByRole("button", { name: "Registrar fase" }).click();
  await page.getByText("Fase cambiada a «Resolución favorable».").waitFor();
  await page.screenshot({ path: `${OUT}/f41_07_resolucion.png`, fullPage: true });
  log("Resolución favorable registrada por el letrado, con fecha");
  await ctx.close();
}

// 5) Laboral no ve Extranjería ni sus expedientes
{
  const { ctx, page } = await as("Asesor Laboral Barcelona");
  if (await page.getByRole("link", { name: "Extranjería" }).count()) throw new Error("Laboral ve Extranjería");
  const res = await page.request.get(`${W}/api/v1/immigration/inbox`);
  if ((await res.json()).cases.length !== 0) throw new Error("Laboral ve trámites");
  log("Laboral no ve el módulo ni ningún trámite de extranjería (comprobado en el servidor)");
  await ctx.close();
}

await browser.close();
console.log("RECORRIDO F4.1 COMPLETO");
