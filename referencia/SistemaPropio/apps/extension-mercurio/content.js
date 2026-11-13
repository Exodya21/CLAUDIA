// Se ejecuta SOLO en mercurio.delegaciondelgobierno.gob.es. Rellena cuando la persona lo pide desde la ventanita
// de la extensión. No pulsa ningún botón (Concluir, Presentación electrónica, Firmar y registrar…) ni envía nada.
chrome.runtime.onMessage.addListener(function (msg, _sender, reply) {
  if (window.top !== window && !document.querySelector("input,select,textarea")) return false;
  if (msg && msg.type === "sp-fill") {
    window.SPMatcher.fill(document, msg.data, { overwrite: !!msg.overwrite })
      .then(function (report) { reply({ ok: true, frame: location.pathname, report: report }); })
      .catch(function (e) { reply({ ok: false, error: String(e && e.message || e) }); });
    return true; // respuesta asíncrona
  } else if (msg && msg.type === "sp-diagnose") {
    reply({ ok: true, diagnosis: window.SPMatcher.diagnose(document) });
  }
  return false;
});
