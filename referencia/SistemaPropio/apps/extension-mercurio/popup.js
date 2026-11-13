const $ = (id) => document.getElementById(id);
const MERCURIO = "https://mercurio.delegaciondelgobierno.gob.es/*";
const send = (msg) => chrome.runtime.sendMessage(msg);

function show(text, ok = true, list = null) {
  const m = $("msg");
  m.hidden = false;
  m.className = "box " + (ok ? "ok" : "bad");
  m.textContent = text;
  if (list && list.length) {
    const ul = document.createElement("ul");
    list.slice(0, 15).forEach((x) => { const li = document.createElement("li"); li.textContent = x; ul.appendChild(li); });
    m.appendChild(ul);
  }
}

async function mercurioTab() {
  const tabs = await chrome.tabs.query({ url: MERCURIO });
  if (!tabs.length) return null;
  return tabs.find((t) => t.active) || tabs.sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0))[0];
}

function render(data) {
  $("sin-datos").hidden = !!data;
  $("con-datos").hidden = !data;
  if (!data) return;
  const s = $("summary");
  s.textContent = "";
  const t = document.createElement("strong");
  t.textContent = `${data.case_code} · ${data.model}`;
  s.appendChild(t);
  const lines = [
    `Cliente: ${data.client}`,
    `${Object.keys(data.values).length} datos confirmados el ${new Date(data.confirmed_at).toLocaleString("es-ES")}`,
    `Válido hasta las ${new Date(data.expires_at).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}`,
  ];
  if (data.options.length) lines.push(`Marque en Mercurio: ${data.options.join("; ")}`);
  lines.forEach((l) => { const d = document.createElement("div"); d.className = "muted"; d.textContent = l; s.appendChild(d); });
}

$("fetch").addEventListener("click", async () => {
  $("fetch").disabled = true;
  const r = await send({ type: "sp-fetch", code: $("code").value });
  $("fetch").disabled = false;
  if (!r.ok) return show(r.error, false);
  render(r.data);
  show("Datos cargados. Abra la pestaña de Mercurio que quiera rellenar y pulse «Rellenar esta página».");
});

$("fill").addEventListener("click", async () => {
  const { data } = await send({ type: "sp-get" });
  if (!data) { render(null); return show("El código ha caducado. Genere otro en SISTEMA PROPIO.", false); }
  const tab = await mercurioTab();
  if (!tab) return show("Abra Mercurio (mercurio.delegaciondelgobierno.gob.es) en una pestaña de Chrome.", false);
  let res;
  try {
    res = await chrome.tabs.sendMessage(tab.id, { type: "sp-fill", data, overwrite: $("overwrite").checked });
  } catch {
    return show("No se pudo leer la página de Mercurio. Recárguela (F5) y vuelva a intentarlo.", false);
  }
  if (!res || !res.ok) return show("No se pudo rellenar: " + (res && res.error || "sin respuesta de la página"), false);
  const rep = res.report;
  const extra = [];
  if (rep.not_found.length) extra.push(...rep.not_found.map((x) => `No encontrado en la lista: ${x}`));
  if (rep.skipped_existing.length) extra.push(`Ya tenían otro valor (no se tocan): ${rep.skipped_existing.join(", ")}`);
  if (rep.no_data.length) extra.push(`Sin dato en la ficha (en amarillo): ${rep.no_data.slice(0, 8).join(", ")}`);
  show(`Rellenados ${rep.filled.length} campos (en verde). Revíselos uno a uno antes de continuar.`, rep.filled.length > 0, extra);
});

$("forget").addEventListener("click", async () => { await send({ type: "sp-forget" }); render(null); show("Datos borrados de la extensión."); });

$("save-server").addEventListener("click", async () => {
  let v = $("server").value.trim().replace(/\/+$/, "");
  if (v && !/^https?:\/\//.test(v)) return show("Escriba la dirección completa, p. ej. https://sistema.despacho.es", false);
  if (v && !/^http:\/\/(localhost|127\.0\.0\.1):3000$/.test(v)) {
    const granted = await chrome.permissions.request({ origins: [`${v}/*`] });
    if (!granted) return show("Sin permiso para esa dirección.", false);
  }
  const r = await send({ type: "sp-server", value: v });
  $("server").value = r.server;
  show("Dirección guardada.");
});

$("diagnose").addEventListener("click", async () => {
  const tab = await mercurioTab();
  if (!tab) return show("Abra la página de Mercurio que quiere analizar.", false);
  try {
    const r = await chrome.tabs.sendMessage(tab.id, { type: "sp-diagnose" });
    await navigator.clipboard.writeText(JSON.stringify(r.diagnosis, null, 1));
    show(`Estructura copiada (${r.diagnosis.fields.length} campos, sin datos). Péguela en un mensaje al equipo.`);
  } catch {
    show("No se pudo analizar la página. Recárguela y vuelva a intentarlo.", false);
  }
});

(async () => {
  const s = await send({ type: "sp-server" });
  $("server").value = s.server;
  const r = await send({ type: "sp-get" });
  render(r.data);
  if (r.expired) show("El código anterior ha caducado.", false);
})();
