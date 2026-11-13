// Pide la ficha a SISTEMA PROPIO con el código temporal y la guarda solo en memoria de la sesión del navegador
// (chrome.storage.session: se borra al cerrar Chrome) hasta que caduca el código.
const DEFAULT_SERVER = "http://localhost:3000";

async function server() {
  const { server } = await chrome.storage.local.get("server");
  return (server || DEFAULT_SERVER).replace(/\/+$/, "");
}

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  (async () => {
    if (msg.type === "sp-fetch") {
      const code = String(msg.code || "").toUpperCase().replace(/[^A-Z0-9-]/g, "");
      if (code.replace(/-/g, "").length !== 12) return reply({ ok: false, error: "El código tiene 12 letras o números (XXXX-XXXX-XXXX)." });
      let res;
      try {
        res = await fetch(`${await server()}/api/v1/immigration/fill/${code}`, { credentials: "omit", cache: "no-store" });
      } catch {
        return reply({ ok: false, error: "No se puede conectar con SISTEMA PROPIO. ¿Está arrancado? Revise la dirección en Ajustes." });
      }
      const body = await res.json().catch(() => null);
      if (!res.ok) return reply({ ok: false, error: body?.error?.message || `Error ${res.status}` });
      await chrome.storage.session.set({ ficha: body });
      return reply({ ok: true, data: body });
    }
    if (msg.type === "sp-get") {
      const { ficha } = await chrome.storage.session.get("ficha");
      if (ficha && new Date(ficha.expires_at) < new Date()) {
        await chrome.storage.session.remove("ficha");
        return reply({ ok: true, data: null, expired: true });
      }
      return reply({ ok: true, data: ficha || null });
    }
    if (msg.type === "sp-forget") {
      await chrome.storage.session.remove("ficha");
      return reply({ ok: true });
    }
    if (msg.type === "sp-server") {
      if (msg.value !== undefined) await chrome.storage.local.set({ server: msg.value || DEFAULT_SERVER });
      return reply({ ok: true, server: await server() });
    }
    reply({ ok: false, error: "Mensaje desconocido" });
  })();
  return true;
});
