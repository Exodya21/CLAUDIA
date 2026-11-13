// Recorrido F0.2 (alta de usuario → primer acceso con doble verificación → sesiones → bloqueo → copias)
// contra web + API + BD reales. Uso: node e2e/recorrido_f02.mjs <carpeta_capturas>
import { createHmac } from "node:crypto";
import { chromium } from "playwright-core";

const W = process.env.WEB_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? ".";
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const log = (m) => console.log("OK  " + m);
const stamp = Date.now().toString(36).slice(-5);

// TOTP RFC 6238 (lo que hace la app del móvil), para poder automatizar el recorrido.
function totp(secretB32, offset = 0) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of secretB32.replace(/\s|=/g, "").toUpperCase()) bits += alphabet.indexOf(c).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const counter = Math.floor(Date.now() / 30000) + offset;
  const msg = Buffer.alloc(8);
  msg.writeBigUInt64BE(BigInt(counter));
  const h = createHmac("sha1", key).update(msg).digest();
  const o = h[h.length - 1] & 0xf;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1e6).padStart(6, "0");
}

async function ctxPage() {
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, locale: "es-ES", timezoneId: "Europe/Madrid" });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => { throw e; });
  return { ctx, page };
}

async function demo(name) {
  const { ctx, page } = await ctxPage();
  await page.goto(`${W}/login`);
  await page.getByRole("listitem").filter({ hasText: name }).click();
  await page.waitForURL(`${W}/`);
  return { ctx, page };
}

// 1) Dirección da de alta a una persona de Recepción
const username = `recepcion.f02${stamp}`;
let temp;
const dir = await demo("Dirección (demo)");
{
  const { page } = dir;
  await page.getByRole("link", { name: "Administración" }).click();
  await page.getByRole("button", { name: "+ Nuevo usuario" }).click();
  await page.getByLabel("Nombre y apellidos").fill("Recepción Ficticia F02");
  await page.getByLabel(/^Usuario/).fill(username);
  await page.getByLabel("Correo corporativo").fill(`${username}@demo.invalid`);
  await page.getByLabel("Entidad").selectOption({ label: "Despacho Demo España S.L. (ficticia)" });
  await page.getByLabel("Rol").selectOption({ label: "Recepción" });
  await page.getByLabel(/^Sede/).selectOption({ label: "Barcelona" });
  await page.getByLabel("Motivo del alta").fill("incorporación ficticia a Recepción Barcelona");
  await page.getByRole("button", { name: "Crear usuario" }).click();
  await page.getByText(/Contraseña provisional de/).waitFor();
  temp = (await page.locator(".secret-box div.mono").innerText()).trim();
  await page.screenshot({ path: `${OUT}/f02_01_alta_usuario.png` });
  log(`Alta de usuario con contraseña provisional mostrada una sola vez (${username})`);
  await page.getByRole("button", { name: "Ya la he entregado" }).click();
}

// 2) Primer acceso: contraseña provisional → QR → contraseña definitiva + código
const user = await ctxPage();
let secret;
let password = `Recepcion-Ficticia-${stamp}`;
{
  const { page } = user;
  await page.goto(`${W}/login`);
  await page.getByLabel("Usuario", { exact: true }).fill(username);
  await page.getByLabel("Contraseña", { exact: true }).fill(temp);
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByRole("heading", { name: "Primer acceso" }).waitFor();
  secret = (await page.locator("form[aria-label='Primer acceso'] .mono[style]").innerText()).replace(/\s/g, "");
  await page.screenshot({ path: `${OUT}/f02_02_primer_acceso_qr.png` });
  await page.getByLabel(/^Nueva contraseña/).fill(password);
  await page.getByLabel("Repita la contraseña").fill(password);
  await page.getByLabel(/Código de 6 cifras que muestra/).fill("000000");
  await page.getByRole("button", { name: "Activar y entrar" }).click();
  await page.getByText(/El código no coincide/).waitFor();
  log("Código incorrecto al activar la doble verificación: rechazado");
  await page.getByLabel(/Código de 6 cifras que muestra/).fill(totp(secret));
  await page.getByRole("button", { name: "Activar y entrar" }).click();
  await page.waitForURL(`${W}/`);
  await page.getByText("Recepción Ficticia F02").first().waitFor();
  log("Primer acceso completado: contraseña definitiva + doble verificación");
  await page.goto(`${W}/ajustes`);
  await page.getByRole("heading", { name: "Seguridad" }).waitFor();
  await page.getByText("Contraseña + código del móvil").first().waitFor();
  await page.screenshot({ path: `${OUT}/f02_03_ajustes_seguridad.png` });
  log("Ajustes → Seguridad muestra la sesión y el método de acceso");
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await page.waitForURL(/\/login/);
}

// 3) Acceso normal: contraseña + código (el siguiente, el anterior ya se usó)
{
  const { page } = user;
  await page.getByLabel("Usuario", { exact: true }).fill(username);
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByRole("heading", { name: "Código de verificación" }).waitFor();
  await page.screenshot({ path: `${OUT}/f02_04_codigo.png` });
  await page.getByLabel("Código de 6 cifras").fill(totp(secret, 1));
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL(`${W}/`);
  log("Acceso con contraseña + código del móvil");
}

// 4) Dirección cierra la sesión de esa persona desde Administración → efecto inmediato
{
  const { page } = dir;
  await page.goto(`${W}/administracion`);
  await page.getByLabel("Buscar usuarios").fill(username);
  await page.getByRole("button", { name: "Buscar" }).click();
  await page.getByRole("row", { name: new RegExp(username.replace(".", "\\.")) }).getByRole("link").click();
  await page.getByRole("heading", { name: "Sesiones" }).waitFor();
  await page.screenshot({ path: `${OUT}/f02_05_ficha_usuario.png` });
  await page.locator("table").last().getByRole("button", { name: "Cerrar" }).first().click();
  await page.getByLabel("Motivo").fill("dispositivo extraviado (ficticio)");
  await page.getByRole("button", { name: "Confirmar cierre" }).click();
  await page.getByText("dispositivo extraviado (ficticio)").first().waitFor();
  log("Dirección cierra la sesión con motivo");
}
{
  const { page } = user;
  await page.goto(`${W}/clientes`);
  await page.waitForURL(/\/login\?error=sesion_revocada/);
  await page.getByText(/se cerró desde la administración/).waitFor();
  await page.screenshot({ path: `${OUT}/f02_06_sesion_revocada.png` });
  log("La persona pierde el acceso al instante y ve el motivo");
}

// 5) Fuerza bruta: 5 contraseñas erróneas bloquean el acceso, incluso con la correcta
{
  const { page } = user;
  await page.goto(`${W}/login`);
  for (let i = 0; i < 5; i++) {
    await page.getByLabel("Usuario", { exact: true }).fill(username);
    await page.getByLabel("Contraseña", { exact: true }).fill(`incorrecta-${i}`);
    await page.getByRole("button", { name: "Continuar" }).click();
    await page.getByText("Usuario o contraseña incorrectos.").waitFor();
  }
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Continuar" }).click();
  await page.getByText(/Demasiados intentos fallidos/).waitFor();
  await page.screenshot({ path: `${OUT}/f02_07_bloqueo.png` });
  log("Bloqueo tras 5 intentos fallidos (también con la contraseña correcta)");
}

// 6) Cambio de rol con efecto inmediato y restablecimiento de credenciales
{
  const { page } = dir;
  await page.reload();
  await page.getByRole("button", { name: "+ Añadir rol" }).click();
  await page.getByLabel("Rol").selectOption({ label: "Atención al cliente" });
  await page.getByLabel("Motivo").fill("pasa a Atención al cliente (ficticio)");
  await page.getByRole("button", { name: "Añadir rol" }).click();
  await page.getByRole("cell", { name: "Atención al cliente" }).waitFor();
  await page.getByRole("row", { name: /Recepción/ }).getByRole("button", { name: "Retirar" }).click();
  await page.getByLabel("Motivo").fill("deja Recepción (ficticio)");
  await page.getByRole("button", { name: "Retirar rol" }).click();
  await page.getByText("Retirado").waitFor();
  log("Cambio de rol: se añade el nuevo y se retira el anterior; el historial se conserva");
  await page.getByRole("button", { name: "Restablecer contraseña y móvil" }).click();
  await page.getByLabel("Motivo").fill("cambio de móvil (ficticio)");
  await page.getByRole("button", { name: "Restablecer", exact: true }).click();
  await page.getByText(/Contraseña provisional de/).waitFor();
  await page.screenshot({ path: `${OUT}/f02_08_restablecer.png` });
  log("Restablecimiento: nueva contraseña provisional y doble verificación a configurar de nuevo");
}

// 7) Autorización puntual desde la pantalla y registro de copias de seguridad
{
  const { page } = dir;
  await page.goto(`${W}/ajustes`);
  await page.getByLabel("Código de expediente").fill("LAB-2026-0001");
  await page.getByRole("button", { name: "Buscar" }).click();
  await page.getByLabel("Persona").selectOption({ index: 1 });
  await page.getByLabel(/^Motivo/).fill("sustitución por vacaciones del responsable (ficticio)");
  await page.getByRole("button", { name: "Conceder acceso" }).click();
  await page.getByRole("cell", { name: "sustitución por vacaciones del responsable (ficticio)" }).first().waitFor();
  log("Autorización puntual concedida desde Ajustes, con motivo y caducidad");
  await page.goto(`${W}/administracion`);
  await page.getByRole("heading", { name: "Copias de seguridad" }).waitFor();
  await page.getByText(/Última copia válida/).waitFor();
  await page.getByRole("heading", { name: "Copias de seguridad" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${OUT}/f02_09_copias.png`, fullPage: true });
  log("Administración muestra la última copia comprobada (AT-29)");
}

// 8) Un perfil sin permiso no ve Administración y la API lo rechaza
{
  const { ctx, page } = await demo("Líder Laboral");
  if (await page.getByRole("link", { name: "Administración" }).count()) throw new Error("Líder ve Administración");
  await page.goto(`${W}/administracion`);
  await page.getByText(/Solo Dirección administra usuarios/).waitFor();
  const st = await page.evaluate(() => fetch("/api/v1/admin/users").then((r) => r.status));
  if (st !== 403) throw new Error(`esperado 403, recibido ${st}`);
  log("Líder Laboral: sin menú de Administración y 403 en la API");
  await ctx.close();
}

await browser.close();
console.log("RECORRIDO F0.2 COMPLETO");
