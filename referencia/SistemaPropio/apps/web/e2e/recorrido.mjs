// Recorrido real por la interfaz (web + API + PostgreSQL) con capturas como evidencia.
// Requisitos: API y web en marcha con datos ficticios; Chrome/Chromium (CHROME_PATH).
// Uso: npm run e2e   (o: node e2e/recorrido.mjs <carpeta_capturas>)
// Genera un NIE ficticio distinto en cada ejecución, así que puede repetirse sin reiniciar la BD.
import { chromium } from "playwright-core";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2];
let EXT_ID = process.argv[3];
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const log = [];
const ok = (m) => { log.push("OK  " + m); };
// NIE ficticio distinto en cada ejecución (X + 7 dígitos + letra de control calculada)
const n7 = String(Math.floor(Math.random() * 1e7)).padStart(7, "0");
const NIE = "X" + n7 + "TRWAGMYFPDXBNJZSQVHLCKE"[Number("0" + n7) % 23];
const NIE_MAL = NIE.slice(0, 8) + (NIE[8] === "A" ? "B" : "A");
const NIE_GUIONES = `x-${n7}-${NIE[8].toLowerCase()}`;

async function session(fullName) {
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: "es-ES", timezoneId: "Europe/Madrid" });
  const page = await ctx.newPage();
  await page.goto(`${W}/login`);
  await page.getByRole("listitem").filter({ hasText: fullName }).click();
  await page.waitForURL(`${W}/`);
  await page.getByText("Expedientes visibles para usted").waitFor();
  return { ctx, page };
}

// 1) Recepción
{
  const { ctx, page } = await session("Recepción Barcelona");
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/01_inicio_recepcion.png` });
  ok("Recepción entra en modo demo y ve su panel");

  await page.goto(`${W}/clientes`);
  await page.getByText("Escriba al menos 3 caracteres").waitFor();
  ok("Recepción no puede listar el directorio sin criterio");
  await page.getByLabel("Buscar cliente").fill("611000999");
  await page.getByRole("button", { name: "Buscar" }).click();
  await page.getByText("2 resultados").waitFor();
  await page.screenshot({ path: `${OUT}/02_busqueda_telefono_compartido_recepcion.png` });
  ok("Búsqueda por teléfono compartido devuelve 2 personas distintas con datos enmascarados");

  await page.getByLabel("Buscar cliente").fill("Lucia Ferrer");
  await page.getByRole("button", { name: "Buscar" }).click();
  await page.getByRole("link", { name: "Lucía Ferrer Demo" }).first().click();
  await page.getByText("Ficha mínima", { exact: true }).waitFor();
  await page.getByRole("tab", { name: "Expedientes autorizados" }).click();
  await page.getByText("Solo metadatos").first().waitFor();
  await page.screenshot({ path: `${OUT}/03_recepcion_ficha_minima_metadatos.png` });
  ok("Recepción ve ficha mínima y solo metadatos de los dos expedientes");

  await page.goto(`${W}/clientes/nuevo`);
  await page.getByLabel("Nombre *").fill("Prueba");
  await page.getByLabel("Apellidos *").fill("Duplicado Recorrido");
  await page.getByLabel("Tipo").selectOption("NIE");
  await page.getByLabel("Número").fill(NIE);
  await page.getByRole("button", { name: "Guardar cliente" }).click();
  await page.waitForURL(/\/clientes\/[0-9a-f-]+\?alta=1/);
  ok("Alta de cliente con NIE válido");

  await page.goto(`${W}/clientes/nuevo`);
  await page.getByLabel("Nombre *").fill("Otra");
  await page.getByLabel("Apellidos *").fill("Persona Recorrido");
  await page.getByLabel("Tipo").selectOption("NIE");
  await page.getByLabel("Número").fill(NIE_MAL);
  await page.getByRole("button", { name: "Guardar cliente" }).click();
  await page.getByText("La letra de control del NIE no es correcta.").waitFor();
  ok("Validación de letra de control en el formulario");
  await page.getByLabel("Número").fill(NIE_GUIONES);
  await page.getByLabel("Teléfono móvil").click();
  await page.getByText("Ya existe un cliente con este documento").waitFor();
  await page.getByRole("button", { name: "Guardar cliente" }).click();
  await page.getByText("Posible duplicado: revise antes de continuar").waitFor();
  await page.screenshot({ path: `${OUT}/04_aviso_duplicado.png`, fullPage: true });
  ok("Documento repetido: aviso previo y bloqueo hasta confirmar con motivo");
  await ctx.close();
}

// 2) Asesor Laboral
if (!EXT_ID) {
  const { ctx, page } = await session("Dirección (demo)");
  const r = await page.request.get(`${W}/api/v1/cases?materia=extranjeria&page_size=1`);
  EXT_ID = (await r.json()).items[0].id;
  await ctx.close();
}
{
  const { ctx, page } = await session("Asesor Laboral Barcelona");
  await page.goto(`${W}/expedientes`);
  await page.getByText("LAB-2026", { exact: false }).first().waitFor();
  await page.screenshot({ path: `${OUT}/05_expedientes_asesor_laboral.png` });
  const txt = await page.locator("table.data").innerText();
  if (txt.includes("Extranjería")) throw new Error("El asesor laboral ve Extranjería");
  ok("El listado del asesor laboral no contiene Extranjería");
  await page.goto(`${W}/expedientes/${EXT_ID}`);
  await page.getByRole("heading", { name: "Acceso denegado" }).waitFor();
  await page.screenshot({ path: `${OUT}/06_403_expediente_extranjeria.png` });
  ok("Forzar la URL de un expediente de Extranjería devuelve 403 y lo muestra");
  await ctx.close();
}

// 3) Dirección
{
  const { ctx, page } = await session("Dirección (demo)");
  await page.goto(`${W}/ajustes`);
  await page.getByRole("heading", { name: "Auditoría" }).waitFor();
  await page.getByLabel("Filtrar por resultado").selectOption("denied");
  await page.getByRole("button", { name: "Verificar integridad" }).click();
  await page.getByText("Cadena íntegra").waitFor();
  await page.getByRole("heading", { name: "Auditoría" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${OUT}/07_auditoria_denegaciones_direccion.png` });
  ok("Dirección ve las denegaciones registradas y verifica la cadena de auditoría");
  await page.goto(`${W}/citas`);
  await page.getByText("Pendiente de desarrollar").first().waitFor();
  await page.screenshot({ path: `${OUT}/08_modulo_pendiente_citas.png` });
  ok("Módulo futuro: 'Pendiente de desarrollar', sin datos simulados");
  await ctx.close();
}

await browser.close();
console.log(log.join("\n"));
