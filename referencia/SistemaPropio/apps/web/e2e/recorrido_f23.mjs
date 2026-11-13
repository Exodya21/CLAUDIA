// Recorrido F2.3: portal del cliente y conversaciones por expediente (portal propio, sin WhatsApp — T-31).
// Equipo y cliente en dos navegadores distintos (sesiones separadas). Datos FICTICIOS de la semilla.
// Uso: node e2e/recorrido_f23.mjs <carpeta_capturas>
import { chromium } from "playwright-core";
import { resolve } from "node:path";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const M = resolve(new URL("../../../docs/pruebas/muestras", import.meta.url).pathname);
const CASE = "EXT-2026-0001";
const log = (m) => console.log("OK  " + m);

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const staffCtx = await browser.newContext({ viewport: { width: 1360, height: 950 }, locale: "es-ES", timezoneId: "Europe/Madrid" });
const clientCtx = await browser.newContext({ viewport: { width: 420, height: 900 }, locale: "es-ES", timezoneId: "Europe/Madrid", isMobile: true, hasTouch: true });
const staff = await staffCtx.newPage();
const client = await clientCtx.newPage();
for (const p of [staff, client]) p.on("pageerror", (e) => { throw e; });

async function staffLogin(name) {
  await staff.goto(`${W}/login`);
  await staff.getByRole("listitem").filter({ hasText: name }).click();
  await staff.waitForURL(`${W}/`);
}

// 1) Equipo: el expediente tiene su conversación; la asesora ve el estado del portal y la nota interna de la semilla
await staffLogin("Asesora Extranjería Madrid");
await staff.getByRole("link", { name: "Comunicaciones" }).click();
await staff.getByRole("heading", { name: "Comunicaciones" }).waitFor();
await staff.getByLabel("Bandeja de conversaciones").getByText(CASE).click();
const panel = staff.getByLabel("Conversación con el cliente");
await panel.getByText("Invitado/a, aún no ha entrado").waitFor();
await panel.getByText("la clienta prefiere que la llamemos por la tarde").waitFor();
log("Bandeja del equipo: conversación del expediente, estado del portal y nota interna visible solo para el equipo");

// 2) La asesora pide los documentos con la plantilla (lista sacada del trámite) y deja una nota interna
await panel.getByLabel("Plantilla").selectOption("solicitud_documentos");
await panel.getByRole("button", { name: "Enviar" }).click();
await panel.getByText(/necesitamos que nos envíe la siguiente documentación: Impreso EX-10 firmado/).waitFor();
await panel.getByRole("radio", { name: "Nota interna" }).click();
await panel.getByLabel("Nota interna").fill("Revisar si el contrato cumple el salario mínimo (nota ficticia).");
await panel.getByRole("button", { name: "Guardar nota" }).click();
await panel.getByText("Revisar si el contrato cumple el salario mínimo").waitFor();
await staff.screenshot({ path: `${OUT}/f23_01_bandeja_equipo.png`, fullPage: true });
log("Solicitud de documentos con plantilla (trato de usted, lista del trámite) y nota interna");

// 3) Cliente: entra con su correo y un código de un solo uso (en pruebas se muestra porque no hay correo configurado)
await client.goto(`${W}/portal`);
await client.getByLabel("Correo electrónico").fill("carla.13@ejemplo.invalid");
await client.getByRole("button", { name: "Recibir código" }).click();
const devCode = (await client.locator(".notice-warn .mono").innerText()).trim();
await client.getByLabel("Código de 6 cifras").fill(devCode);
await client.getByRole("button", { name: "Entrar" }).click();
await client.getByRole("heading", { name: /Bienvenido\/a, Carla/ }).waitFor();
await client.screenshot({ path: `${OUT}/f23_02_portal_condiciones.png`, fullPage: true });
await client.getByRole("checkbox").check();
await client.getByRole("button", { name: "Continuar" }).click();
await client.getByRole("heading", { name: "Hola, Carla" }).waitFor();
await client.getByText(/Nos faltan \d+ documento/).waitFor();
await client.screenshot({ path: `${OUT}/f23_03_portal_asuntos.png`, fullPage: true });
log("Cliente: acceso con código de un solo uso, condiciones aceptadas, sus asuntos con mensajes nuevos y documentos que faltan");

// 4) Cliente: ve los mensajes (sin la nota interna), envía el empadronamiento para la lista y escribe
await client.getByRole("link", { name: /Arraigo sociolaboral/ }).click();
await client.getByText("Situación: Reuniendo la documentación").waitFor();
const msgs = client.getByRole("log", { name: "Mensajes" });
await msgs.getByText(/necesitamos que nos envíe/).waitFor();
if (await msgs.getByText(/salario mínimo|llamemos por la tarde/).count()) throw new Error("el cliente ve una nota interna");
const missing = client.getByLabel("Documentos que faltan");
const target = missing.getByRole("listitem").filter({ hasText: "Pendiente de enviar" }).first();
await target.locator('input[type="file"]').setInputFiles(`${M}/FICTICIO_contrato_escaneado.pdf`);
await msgs.getByText(/Le envío: /).waitFor({ timeout: 60000 });
await client.getByLabel("Escriba su mensaje").fill("Buenos días. Les envío el contrato. ¿Necesitan algo más? (mensaje ficticio)");
await client.getByRole("button", { name: "Enviar", exact: true }).click();
await msgs.getByText(/Les envío el contrato/).waitFor();
await client.screenshot({ path: `${OUT}/f23_04_portal_conversacion.png`, fullPage: true });
log("Cliente: no ve notas internas; envía el contrato pedido en la lista y un mensaje");

// 5) Equipo: lo ve sin leer, pasa el archivo al expediente (se lee como cualquier documento)
await staff.reload();
await staff.getByLabel("Bandeja de conversaciones").getByRole("button", { name: new RegExp(CASE) }).getByLabel(/sin leer/).waitFor();
await staff.getByLabel("Bandeja de conversaciones").getByText(CASE).click();
const p2 = staff.getByLabel("Conversación con el cliente");
await p2.getByText(/Les envío el contrato/).waitFor();
await p2.getByRole("button", { name: "Pasar al expediente" }).first().click();
await p2.getByText("En el expediente").first().waitFor({ timeout: 60000 });
log("Equipo: mensaje del cliente sin leer en la bandeja; el adjunto pasa al expediente con su lectura automática");

// 6) Líder de Extranjería: aviso urgente con plantilla. Sin plazo validado no se puede; con señalamiento sí.
await staffCtx.clearCookies();
await staffLogin("Líder Extranjería");
await staff.goto(`${W}/comunicaciones`);
await staff.getByLabel("Bandeja de conversaciones").getByText(CASE).click();
const p3 = staff.getByLabel("Conversación con el cliente");
await p3.getByLabel("Plantilla").selectOption("requerimiento");
const opts = await p3.getByLabel("Tarea con la fecha").locator("option").count();
if (opts > 1) {
  await p3.getByLabel("Tarea con la fecha").selectOption({ index: 1 });
  await p3.getByRole("button", { name: "Enviar" }).click();
  await p3.getByText(/no está validado|validado/).first().waitFor();
}
log("Avisos urgentes solo con plantilla y fecha de una tarea; un plazo legal sin validar no se comunica");

// La líder crea en la agenda un señalamiento ficticio y lo comunica
await staff.evaluate(async (code) => {
  const H = { "Content-Type": "application/json", "X-Requested-With": "sistema-propio" };
  const inbox = await (await fetch("/api/v1/comm/inbox")).json();
  const th = await (await fetch(`/api/v1/comm/threads/${inbox.threads.find((t) => t.case_code === code).id}`)).json();
  const cf = await (await fetch(`/api/v1/cases/${th.case.id}`)).json();
  const me = await (await fetch("/api/v1/me")).json();
  const start = new Date(Date.now() + 9 * 86400000); start.setUTCHours(9, 0, 0, 0);
  const end = new Date(start.getTime() + 3600000);
  const r = await fetch("/api/v1/tasks", { method: "POST", headers: H, body: JSON.stringify({
    organization_id: cf.organization_id, case_id: th.case.id, title: "Juicio (ficticio)", kind: "senalamiento",
    assignee_id: me.id, due_at: start.toISOString(), start_at: start.toISOString(), end_at: end.toISOString(),
    location: "Juzgado de lo Social n.º 0 (ficticio)" }) });
  if (!r.ok) throw new Error("tarea " + r.status + " " + (await r.text()));
}, CASE);
await staff.reload();
await staff.getByLabel("Bandeja de conversaciones").getByText(CASE).click();
const p4 = staff.getByLabel("Conversación con el cliente");
await p4.getByLabel("Plantilla").selectOption("senalamiento_juicio");
const juicio = await p4.getByLabel("Tarea con la fecha").locator("option", { hasText: "Juicio (ficticio)" }).getAttribute("value");
await p4.getByLabel("Tarea con la fecha").selectOption(juicio);
await p4.getByRole("button", { name: "Enviar" }).click();
await p4.getByText(/el juicio de su expediente EXT-2026-0001 está señalado/).waitFor();
await p4.getByText("Pendiente de confirmar").last().waitFor();
await staff.screenshot({ path: `${OUT}/f23_05_aviso_urgente_equipo.png`, fullPage: true });
log("Aviso urgente de señalamiento enviado con la fecha y el lugar de la agenda; queda pendiente de confirmar");

// 7) Cliente: ve el aviso urgente y lo confirma
await client.reload();
await client.getByText(/aviso urgente pendiente de confirmar/).waitFor();
await client.getByRole("button", { name: "He leído este aviso" }).click();
await client.getByText(/✓ Confirmado el/).waitFor();
await client.screenshot({ path: `${OUT}/f23_06_portal_confirmacion.png`, fullPage: true });
await staff.reload();
await staff.getByLabel("Bandeja de conversaciones").getByText(CASE).click();
await staff.getByLabel("Conversación con el cliente").getByText(/Confirmado \d/).waitFor();
log("Cliente confirma el aviso urgente; el equipo ve la confirmación con fecha y hora");

// 8) Exportación con huella y ficha del cliente (acceso al portal y correos sin contenido)
const [dl] = await Promise.all([staff.waitForEvent("download"), staff.getByRole("link", { name: "Exportar PDF" }).click()]);
const path = await dl.path();
if (!path || !dl.suggestedFilename().startsWith("conversacion_EXT-2026-0001")) throw new Error("exportación");
await staff.getByLabel("Conversación con el cliente").getByRole("link", { name: "ficha" }).click();
await staff.getByRole("tab", { name: "Portal y mensajes" }).click();
const acc = staff.getByLabel("Acceso al portal");
await acc.getByText("Usa el portal").waitFor();
await acc.getByText("Últimos correos enviados al cliente").click();
await acc.getByText(/falta configurar el correo/).first().waitFor();
await staff.screenshot({ path: `${OUT}/f23_07_ficha_portal.png`, fullPage: true });
log("Exportación PDF con huella; en la ficha, el acceso al portal y los correos (sin contenido; aquí sin servidor de correo)");

// 9) Sesiones separadas: la cookie del cliente no abre el sistema del equipo
const r = await client.evaluate(async () => (await fetch("/api/v1/comm/inbox")).status);
if (r !== 401) throw new Error("la sesión del cliente abre la bandeja del equipo");
log("La sesión del cliente no da acceso a nada del equipo");
await browser.close();
