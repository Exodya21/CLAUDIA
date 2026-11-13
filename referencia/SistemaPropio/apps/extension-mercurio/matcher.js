// Reconoce los campos de un formulario por su etiqueta y su apartado y los rellena con la ficha confirmada.
// REGLAS FIJAS: nunca pulsa botones, nunca envía formularios, nunca toca contraseñas, archivos ni campos ocultos,
// y no sobrescribe lo que ya tiene valor salvo que se pida expresamente.
(function (root) {
  "use strict";

  function norm(s) {
    return String(s || "")
      .normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/\(\s*\d+\s*\)/g, " ")
      .replace(/[º°]/g, "o")
      .replace(/[*:]/g, " ")
      .replace(/\s+/g, " ")
      .trim().toLowerCase();
  }

  // Apartado (pestaña, fieldset, título) → papel en la ficha
  var ROLE_RULES = [
    ["rep", /presentador|representante a efectos|datos del representante/],
    ["notif", /notificaci/],
    ["con", /contrato/],
    ["fam", /reagrupante|familiar|titular de los recursos/],
    ["emp", /empleador|empresa|datos de la actividad|cuenta propia/],
    ["ent", /entidad|centro de (estudios|formacion)|institucion/],
    ["ext", /extranjer|solicitante|reagrupad|interesad|persona/],
  ];
  function roleOf(text) {
    var t = norm(text);
    for (var i = 0; i < ROLE_RULES.length; i++) if (ROLE_RULES[i][1].test(t)) return ROLE_RULES[i][0];
    return null;
  }

  // Etiqueta → campo de la ficha (el orden importa: lo más concreto primero)
  var FIELD_RULES = [
    ["_ignorar", /^no consiento|persona tutelada|^km$/],
    ["hijos_escolarizacion", /hijas?\/?os a cargo|escolarizacion/],
    ["consiento_dehu", /^(si )?consiento.*(dehu|direccion electronica habilitada)/],
    ["padre", /nombre del padre|^padre$/], ["madre", /nombre de la madre|^madre$/],
    ["rl_nombre", /representante legal/], ["apellido1", /primer apellido|1er apellido|^apellido 1$|^1o apellido$/],
    ["apellido2", /segundo apellido|2o apellido|^apellido 2$/], ["pasaporte", /pasaporte$|^pasaporte/],
    ["nie", /^n\.?i\.?e\.?$|numero de identidad de extranjero|^nie\b/], ["fecha_nacimiento", /fecha de nacimiento/],
    ["lugar_nacimiento", /lugar de nacimiento|^lugar$|localidad de nacimiento/],
    ["pais_nacimiento", /pais de nacimiento|^pais$/], ["nacionalidad", /nacionalidad/],
    ["sexo", /^sexo$/], ["estado_civil", /estado civil/],
    ["nombre", /^nombre$|nombre\s*\/\s*razon social|razon social|^denominacion$/],
    ["doc", /^dni|nif|^documento/],
    ["tipo_via", /tipo de via/], ["domicilio", /domicilio|direccion|nombre de la via|^calle|^via$/],
    ["numero", /^(numero|no|n|num\.?)$/], ["piso", /^piso|planta/], ["letra", /^letra|^puerta/],
    ["escalera", /^escalera/], ["bloque", /^bloque/], ["municipio", /municipio/],
    ["localidad", /localidad|poblacion/], ["cp", /codigo postal|^c\.?p\.?$/], ["provincia", /provincia/],
    ["telefono", /telefono movil|^movil/], ["telefono_fijo", /^telefono( fijo)?$/], ["email", /e-?mail|correo/],
    ["actividad", /^actividad/], ["cnae", /cnae/], ["cno", /\bcno\b/], ["puesto", /puesto/],
    ["retribucion", /retribucion|salario/], ["vinculo", /vinculo|parentesco/],
    ["titulo", /^titulo/],
  ];
  function fieldOf(label) {
    var t = norm(label);
    if (!t) return null;
    for (var i = 0; i < FIELD_RULES.length; i++) if (FIELD_RULES[i][1].test(t)) return FIELD_RULES[i][0];
    return null;
  }

  var CHOICE_WORDS = {
    sexo: { H: ["hombre", "varon", "masculino", "h"], M: ["mujer", "femenino", "m"], X: ["x", "no binario", "otro"] },
    rl_doc_tipo: { DNI: ["dni"], NIE: ["nie"], PAS: ["pasaporte", "pas"] },
    doc_tipo: { DNI: ["dni"], NIE: ["nie"], PAS: ["pasaporte", "pas"] },
    estado_civil: { S: ["soltero", "soltera", "s"], C: ["casado", "casada", "c"], V: ["viudo", "viuda", "v"],
                    D: ["divorciado", "divorciada", "d"], Sp: ["separado", "separada", "sp"] },
  };

  function isFillable(el) {
    if (!el || el.disabled || el.readOnly) return false;
    var tag = el.tagName;
    if (tag === "SELECT" || tag === "TEXTAREA") return true;
    if (tag !== "INPUT") return false;
    var type = (el.type || "text").toLowerCase();
    return ["text", "email", "tel", "date", "number", "search", "radio", "checkbox", ""].indexOf(type) >= 0;
  }

  function textOf(node) {
    if (!node) return "";
    var clone = node.cloneNode(true);
    var drop = clone.querySelectorAll ? clone.querySelectorAll("input,select,textarea,button,script,style,option") : [];
    for (var i = 0; i < drop.length; i++) drop[i].remove();
    return (clone.textContent || "").replace(/\s+/g, " ").trim();
  }

  function labelOf(el) {
    var doc = el.ownerDocument;
    if (el.labels && el.labels.length) return textOf(el.labels[0]);
    if (el.getAttribute("aria-label")) return el.getAttribute("aria-label");
    var lb = el.getAttribute("aria-labelledby");
    if (lb) return lb.split(/\s+/).map(function (id) { return textOf(doc.getElementById(id)); }).join(" ");
    // celda anterior de la misma fila de tabla
    var cell = el.closest("td,th");
    if (cell && cell.previousElementSibling) {
      var t = textOf(cell.previousElementSibling);
      if (t) return t;
    }
    // texto inmediatamente anterior dentro del mismo contenedor
    var prev = el.previousSibling, guard = 0;
    while (prev && guard++ < 6) {
      var tt = prev.nodeType === 3 ? prev.textContent.trim() : (prev.matches && prev.matches("input,select,textarea") ? "" : textOf(prev));
      if (tt) return tt;
      prev = prev.previousSibling;
    }
    var parent = el.parentElement;
    if (parent && parent.querySelectorAll("input,select,textarea").length === 1) {
      var pt = textOf(parent);
      if (pt) return pt;
    }
    // rejilla de dos columnas: <div><label>* Pasaporte:</label></div><div><input></div>
    var up = el.parentElement, depth = 0;
    while (up && depth++ < 3) {
      var sib = up.previousElementSibling;
      if (sib && !sib.querySelector("input,select,textarea")) {
        var st = textOf(sib);
        if (st && st.length < 80) return st;
      }
      if (up.querySelectorAll("input,select,textarea").length > 1) break;
      up = up.parentElement;
    }
    return el.getAttribute("placeholder") || el.getAttribute("title") || "";
  }

  // Títulos de apartado en orden del documento (excluye las pestañas): «DATOS DEL EXTRANJERO/A»,
  // «DOMICILIO EN ESPAÑA», «REPRESENTANTE LEGAL, EN SU CASO»…
  // Pestañas de Mercurio: grupo de ≥3 enlaces o elementos de lista hermanos con textos de apartado. La activa se
  // reconoce por aria-selected, por su clase o, si no, por tener un fondo distinto al de las demás.
  function tabsOf(doc) {
    var cands = Array.prototype.slice.call(doc.querySelectorAll("a, li, [role=tab], button"))
      .filter(function (n) {
        var t = textOf(n);
        return t && t.length < 60 && (roleOf(t) || /tipo de autorizaci|datos de/.test(norm(t))) && !n.querySelector("input,select,textarea");
      });
    var groups = new Map();
    cands.forEach(function (n) {
      var key = n.tagName === "A" && n.parentElement && n.parentElement.tagName === "LI" ? n.parentElement.parentElement : n.parentElement;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(n);
    });
    var best = null;
    groups.forEach(function (list, parent) { if (list.length >= 3 && (!best || list.length > best.items.length)) best = { bar: parent, items: list }; });
    if (!best) return null;
    var win = doc.defaultView;
    var active = best.items.filter(function (n) {
      var li = n.closest("li") || n;
      return n.getAttribute("aria-selected") === "true" || /(^|\s|-)(active|activ[ao]|selected|current|ui-tabs-active|ui-state-active)(\s|$)/i.test((li.className || "") + " " + (n.className || ""));
    })[0];
    if (!active && win) {
      var bg = best.items.map(function (n) { var e = n; var c = win.getComputedStyle(e).backgroundColor;
        if (c === "rgba(0, 0, 0, 0)" && e.parentElement) c = win.getComputedStyle(e.parentElement).backgroundColor; return c; });
      var count = {};
      bg.forEach(function (c) { count[c] = (count[c] || 0) + 1; });
      var uniq = bg.map(function (c, i) { return count[c] === 1 ? i : -1; }).filter(function (i) { return i >= 0; });
      if (uniq.length === 1) active = best.items[uniq[0]];
    }
    return { bar: best.bar, items: best.items, active: active || null, activeText: active ? textOf(active) : "" };
  }

  function headingsOf(doc, tabs) {
    var out = [];
    var all = doc.body ? doc.body.querySelectorAll("*") : [];
    for (var i = 0; i < all.length; i++) {
      var n = all[i];
      if (/^(SCRIPT|STYLE|OPTION|SELECT|BUTTON|INPUT|TEXTAREA|LABEL)$/.test(n.tagName)) continue;
      if (n.closest("[role=tablist], .nav, .nav-tabs, .tabs, ul.pestanas, a, li, nav")) continue;
      if (tabs && tabs.bar && tabs.bar.contains(n)) continue;
      if (n.querySelector("input,select,textarea,button")) continue;
      var own = "";
      for (var c = n.firstChild; c; c = c.nextSibling) if (c.nodeType === 3) own += c.textContent;
      own = own.replace(/\s+/g, " ").trim();
      if (own.length < 6 || own.length > 80) continue;
      var letters = own.replace(/[^A-Za-zÁÉÍÓÚÑáéíóúñ]/g, "");
      if (letters.length < 5 || letters !== letters.toUpperCase()) continue;
      out.push({ node: n, text: own });
    }
    return out;
  }
  function precedingHeadings(el, heads) {
    var before = [];
    for (var i = 0; i < heads.length; i++) {
      if (heads[i].node.compareDocumentPosition(el) & 4) before.push(heads[i]); // 4 = el va después
    }
    return before;
  }

  function contextOf(el) {
    // apartado: legend del fieldset, título anterior o pestaña activa
    var n = el;
    while (n && n !== el.ownerDocument.body) {
      if (n.tagName === "FIELDSET") {
        var lg = n.querySelector("legend");
        if (lg && roleOf(lg.textContent)) return lg.textContent;
      }
      if (n.getAttribute && n.getAttribute("data-apartado")) return n.getAttribute("data-apartado");
      var h = n.previousElementSibling, g = 0;
      while (h && g++ < 20) {
        if (/^H[1-6]$/.test(h.tagName) || (h.className && /titulo|title|cabecera|header/i.test(h.className))) {
          if (roleOf(h.textContent)) return h.textContent;
        }
        h = h.previousElementSibling;
      }
      if (n.getAttribute && n.getAttribute("role") === "tabpanel" && n.getAttribute("aria-labelledby")) {
        var tab = el.ownerDocument.getElementById(n.getAttribute("aria-labelledby"));
        if (tab) return tab.textContent;
      }
      n = n.parentElement;
    }
    var active = el.ownerDocument.querySelector("[role=tab][aria-selected=true], .tab.active, li.active > a, .nav-link.active");
    return active ? active.textContent : "";
  }

  function groupLabelOf(el) {
    // Para botones de opción: la etiqueta del grupo (Sexo, Estado civil), no la de cada opción
    var g = el.closest("[role=radiogroup]");
    if (g && (g.getAttribute("aria-label") || g.getAttribute("aria-labelledby"))) return labelOf(g);
    var fs = el.closest("fieldset");
    if (fs && fs.querySelector("legend")) return textOf(fs.querySelector("legend"));
    var cell = el.closest("td,th");
    if (cell && cell.previousElementSibling) return textOf(cell.previousElementSibling);
    return labelOf(el);
  }

  function clean(l) { return String(l || "").replace(/^\s*\*\s*/, "").replace(/\s*:\s*$/, "").trim(); }

  // Identificadores REALES de Mercurio (diagnóstico del 05/11/2026, modelo EX-10): prefijo = apartado,
  // parte central = dato, sufijo opcional = bloque. Es la vía principal; las etiquetas quedan de respaldo.
  var ID_ROLE = { ext: "ext", rea: "fam", emp: "emp", pre: "rep", not: "notif" };
  var ID_FIELD = {
    Pasaporte: "pasaporte", Nie: "nie", Apellido1: "apellido1", Apellido2: "apellido2", Nombre: "nombre", Sexo: "sexo",
    FechaNacimiento: "fecha_nacimiento", EstadoCivil: "estado_civil", LugarNacimiento: "lugar_nacimiento",
    CodigoPaisNacimiento: "pais_nacimiento", CodigoNacionalidad: "nacionalidad", Padre: "padre", Madre: "madre",
    TipoVia: "tipo_via", Domicilio: "domicilio", Numero: "numero", Piso: "piso", Letra: "letra", Escalera: "escalera",
    Bloque: "bloque", CodigoProvincia: "provincia", CodigoMunicipio: "municipio", CodigoLocalidad: "localidad",
    CodigoPostal: "cp", Telefono: "telefono_fijo", TelefonoMovil: "telefono", Email: "email",
    NombreRepresentante: "rl_nombre", TipodocumentoRepresentante: "rl_doc_tipo", NieRepresentante: "rl_doc",
    TituloRepresentante: "rl_titulo", Tipodocumento: "doc_tipo", TipoDocumento: "doc_tipo", Documento: "doc",
    Parentesco: "vinculo",
  };
  function fromId(el) {
    var id = el.id || el.name || "";
    if (/(-ts-control|Aux|AuxSup)$/.test(id)) return null;           // controles auxiliares de búsqueda/copia
    if (id === "chkConsentimientoNotificacion") return { role: "notif", field: "consiento_dehu" };
    var m = /^(ext|rea|emp|pre|not)([A-Z][A-Za-z0-9]*?)(Reagrupante|Empresa2|Empresa|Presentador|Notificacion)?$/.exec(id);
    if (!m) return null;
    var role = ID_ROLE[m[1]], mid = m[2];
    if (m[3] === "Empresa2") role = "ent";
    var field = ID_FIELD[mid];
    if (!field) return null;
    if (field === "nie" && role !== "ext") field = role === "fam" ? "nie" : "doc";   // preNie…, notNie…, empNie… = documento
    if (field === "doc" && role === "fam") field = "nie";
    if (role === "emp" && field === "telefono_fijo") field = "telefono";
    return { role: role, field: field };
  }

  var PERSON_ONLY = ["pasaporte", "nie", "apellido1", "apellido2", "sexo", "fecha_nacimiento", "estado_civil",
                     "lugar_nacimiento", "pais_nacimiento", "nacionalidad", "padre", "madre"];

  function describe(el, heads, tabs) {
    var label = (el.type || "").toLowerCase() === "radio" ? groupLabelOf(el) : labelOf(el);
    var byId = fromId(el);
    if (byId) return { el: el, label: clean(label), context: byId.role, role: byId.role, field: byId.field,
                       key: byId.role + "." + byId.field, byId: true };
    var ctx = "", sub = "";
    if (heads) {
      var prev = precedingHeadings(el, heads);
      // con pestañas, solo valen los títulos que están DESPUÉS de la barra de pestañas (dentro del panel)
      if (tabs && tabs.bar) prev = prev.filter(function (h) { return tabs.bar.compareDocumentPosition(h.node) & 4; });
      for (var i = prev.length - 1; i >= 0; i--) { if (roleOf(prev[i].text)) { ctx = prev[i].text; break; } }
      if (prev.length) sub = prev[prev.length - 1].text;
    }
    if (!ctx && tabs && tabs.activeText) ctx = tabs.activeText;
    if (!ctx) ctx = contextOf(el);
    var field = fieldOf(label);
    label = clean(label);
    if (field === "_ignorar") return { el: el, label: label, context: ctx, role: null, field: null, key: null, ignore: true };
    if (field === "doc" && el.tagName === "SELECT") field = "doc_tipo";
    if (/representante legal/.test(norm(sub))) {
      if (field === "doc" || field === "doc_tipo") field = "rl_doc_tipo";
      else if (field === "numero") field = "rl_doc";
      else if (field === "titulo") field = "rl_titulo";
    } else if (field === "titulo") {
      field = "rl_titulo";
    }
    var role = roleOf(ctx) || "ext";
    if (field === "nombre" && /razon social|denominacion/.test(norm(label)) && role === "ext") role = "rep";
    return { el: el, label: label, context: ctx, role: role, field: field, key: field ? role + "." + field : null };
  }

  function setValue(el, v) {
    var proto = el.tagName === "SELECT" ? root.HTMLSelectElement.prototype
      : el.tagName === "TEXTAREA" ? root.HTMLTextAreaElement.prototype : root.HTMLInputElement.prototype;
    var desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (desc && desc.set) desc.set.call(el, v); else el.value = v;
    ["input", "change", "blur"].forEach(function (t) { el.dispatchEvent(new root.Event(t, { bubbles: true })); });
  }

  function words(key, value, data) {
    var f = key.split(".")[1];
    var out = [norm(value)];
    if (CHOICE_WORDS[f] && CHOICE_WORDS[f][value]) out = CHOICE_WORDS[f][value].slice();
    var lab = data.choices && data.choices[key] && data.choices[key][value];
    if (lab) out.push(norm(lab));
    if (/^\d{1,2}$/.test(String(value))) { out.push(norm(value) + "o"); out.push(("0" + value).slice(-2)); }
    return out;
  }

  function pickOption(sel, cands) {
    var opts = Array.prototype.slice.call(sel.options);
    for (var pass = 0; pass < 3; pass++) {
      for (var i = 0; i < opts.length; i++) {
        var t = norm(opts[i].textContent), v = norm(opts[i].value);
        for (var j = 0; j < cands.length; j++) {
          var c = cands[j];
          if (!c) continue;
          if ((pass === 0 && (t === c || v === c)) || (pass === 1 && c.length > 2 && t.indexOf(c) === 0) ||
              (pass === 2 && c.length > 3 && t.indexOf(c) >= 0)) return opts[i];
        }
      }
    }
    return null;
  }

  function fmtDate(iso, el) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    if (!m) return iso;
    if (el.type === "date") return iso;
    return m[3] + "/" + m[2] + "/" + m[1];
  }

  function splitNie(v) {
    var m = /^([XYZ])\W?(\d{7})\W?([A-Z])$/.exec(String(v || "").toUpperCase());
    return m ? [m[1], m[2], m[3]] : null;
  }

  function visible(el) {
    if (!el.ownerDocument.defaultView) return true;
    var st = el.ownerDocument.defaultView.getComputedStyle(el);
    return st.display !== "none" && st.visibility !== "hidden" && (el.offsetParent !== null || st.position === "fixed");
  }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  // Rellena la página. Asíncrono porque Mercurio carga «Municipio» y «Localidad» después de elegir la provincia.
  async function fill(doc, data, opts) {
    opts = opts || {};
    var values = data.values || {};
    var report = { filled: [], skipped_existing: [], no_data: [], not_found: [], unknown_fields: 0 };
    var used = {};
    var tabs = tabsOf(doc);
    var heads = headingsOf(doc, tabs);
    var els = Array.prototype.slice.call(doc.querySelectorAll("input,select,textarea")).filter(isFillable);
    // Campos reconocidos por su identificador de Mercurio: se rellenan en todas las pestañas a la vez.
    // Los reconocidos solo por la etiqueta: únicamente en la pestaña visible.
    var described = els.map(function (e) { return describe(e, heads, tabs); })
      .filter(function (d) { return d.byId || opts.allTabs || visible(d.el); });
    // «DNI/NIE/PAS: [lista] Numero: [casilla]»: el número que sigue a la lista es el del documento
    for (var q = 1; q < described.length; q++) {
      var pv = described[q - 1].field, cur = described[q];
      if (cur.field === "numero" && (pv === "doc_tipo" || pv === "rl_doc_tipo")) {
        cur.field = pv === "doc_tipo" ? "doc" : "rl_doc";
        cur.key = cur.role + "." + cur.field;
      }
    }
    var groups = {};
    described.forEach(function (d) { if (d.key) (groups[d.key] = groups[d.key] || []).push(d); });
    var radiosDone = {};
    for (var n = 0; n < described.length; n++) {
      var d = described[n], el = d.el;
      if (d.ignore) continue;
      if (!d.key) { report.unknown_fields++; continue; }
      var v = values[d.key];
      // Un dato que solo puede ser de la persona extranjera (pasaporte, apellidos…) se toma de ella si el apartado
      // detectado no lo tiene: la pestaña del presentador o de notificaciones nunca pide estos datos.
      if ((v === undefined || v === "") && PERSON_ONLY.indexOf(d.field) >= 0 && d.role !== "fam" && values["ext." + d.field]) {
        v = values["ext." + d.field]; d.key = "ext." + d.field;
      }
      if ((d.field === "rl_doc_tipo" || d.field === "doc_tipo") && !v && values[d.role + "." + d.field.replace("_tipo", "")]) {
        var doc_ = String(values[d.role + "." + d.field.replace("_tipo", "")]).toUpperCase();
        v = /^[XYZ]/.test(doc_) ? "NIE" : /^\d{8}[A-Z]$/.test(doc_) ? "DNI" : "PAS";
      }
      if (v === undefined || v === "") { report.no_data.push(d.label || d.key); mark(el, "#f2c94c"); continue; }
      var grp = groups[d.key], idx = grp.indexOf(d), val = v;
      if (d.field === "nie" && grp.length === 3) { var p = splitNie(v); val = p ? p[idx] : (idx === 1 ? v : ""); }
      else if (d.field === "nie") { val = String(v).replace(/\W/g, ""); }
      if (d.field === "fecha_nacimiento" && grp.length === 3) {
        var mm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v); val = mm ? [mm[3], mm[2], mm[1]][idx] : "";
      } else if (d.field === "fecha_nacimiento") { val = fmtDate(v, el); }
      if (d.field === "telefono" || d.field === "telefono_fijo") {
        val = String(v).replace(/\D/g, "");
        if (val.length === 11 && val.indexOf("34") === 0) val = val.slice(2);
        if (val.length === 13 && val.indexOf("0034") === 0) val = val.slice(4);
      }
      var type = (el.type || "").toLowerCase();
      if (type === "radio") {
        if (radiosDone[el.name]) continue;
        var cands = words(d.key, v, data);
        var radios = Array.prototype.slice.call(doc.querySelectorAll('input[type=radio][name="' + el.name + '"]'));
        var hit = radios.filter(function (r) { var t = norm(labelOf(r) + " " + r.value); return cands.some(function (c) { return c && (t === c || t.split(" ").indexOf(c) >= 0); }); })[0];
        radiosDone[el.name] = true;
        if (hit) { hit.checked = true; hit.dispatchEvent(new root.Event("change", { bubbles: true })); report.filled.push(d.label); used[d.key] = 1; mark(hit, "#27ae60"); }
        else report.not_found.push(d.label + " → " + v);
        continue;
      }
      if (type === "checkbox") {
        // Solo dos casillas: «SÍ hijas/os a cargo…» y el consentimiento DEHú, y solo si la ficha dice «sí».
        if ((d.field === "consiento_dehu" || d.field === "hijos_escolarizacion") && v === "si" && !el.checked) {
          el.checked = true; el.dispatchEvent(new root.Event("change", { bubbles: true }));
          report.filled.push(d.label); used[d.key] = 1; mark(el, "#27ae60");
        } else if (v) used[d.key] = 1;
        continue;
      }
      if (el.tagName === "SELECT") {
        var want = words(d.key, v, data), opt = pickOption(el, want), waited = 0;
        // lista dependiente (municipio, localidad): esperar a que Mercurio la cargue
        while (!opt && el.options.length <= 2 && waited < (opts.waitMs || 6000)) {
          await sleep(300); waited += 300; opt = pickOption(el, want);
        }
        if (!opt) { report.not_found.push((d.label || d.key) + " → " + v); mark(el, "#eb5757"); continue; }
        if (el.value && el.selectedIndex > 0 && !opts.overwrite && el.value !== opt.value) { report.skipped_existing.push(d.label); continue; }
        setValue(el, opt.value); report.filled.push(d.label); used[d.key] = 1; mark(el, "#27ae60");
        await sleep(50);
        continue;
      }
      if (el.value && !opts.overwrite) { if (el.value !== val) report.skipped_existing.push(d.label); else used[d.key] = 1; continue; }
      if (el.maxLength > 0 && String(val).length > el.maxLength) { report.not_found.push(d.label + " (demasiado largo)"); mark(el, "#eb5757"); continue; }
      setValue(el, val); report.filled.push(d.label); used[d.key] = 1; mark(el, "#27ae60");
    }
    report.unused = Object.keys(values).filter(function (k) { return !used[k]; });
    return report;
  }

  function mark(el, color) {
    try { el.style.outline = "3px solid " + color; el.style.outlineOffset = "1px"; } catch (e) { /* sin estilo */ }
  }

  function diagnose(doc) {
    var tabs = tabsOf(doc);
    var heads = headingsOf(doc, tabs);
    var els = Array.prototype.slice.call(doc.querySelectorAll("input,select,textarea,button"));
    return {
      page: (doc.location && doc.location.pathname) || "", title: doc.title,
      // sin datos personales: se descartan títulos con un DNI/NIE o el nombre del profesional conectado
      apartados: heads.map(function (h) { return h.text; }).filter(function (t) {
        return !/\d{7,8}\s*[A-Z]|[XYZ]\d{7}[A-Z]|ABOGAD[OA]\s*-|^[A-ZÁÉÍÓÚÑ ]+ - [A-ZÁÉÍÓÚÑ ]+/.test(t); }),
      pestanas: tabs ? tabs.items.map(function (t) { return textOf(t).slice(0, 40); }) : [],
      pestana_activa: tabs ? tabs.activeText : null,
      tabs: Array.prototype.slice.call(doc.querySelectorAll("[role=tab], .nav-link, .tab")).map(function (t) { return textOf(t).slice(0, 60); }),
      fields: els.map(function (el) {
        var d = el.tagName === "BUTTON" ? { label: textOf(el), context: "", key: null } : describe(el, heads, tabs);
        // SIN valores: solo la estructura, para poder ajustar el reconocimiento
        return { tag: el.tagName.toLowerCase(), type: el.type || "", name: el.name || "", id: el.id || "",
                 label: String(d.label || "").slice(0, 80), apartado: String(d.context || "").replace(/\s+/g, " ").slice(0, 60),
                 clave: d.key, opciones: el.tagName === "SELECT" ? el.options.length : undefined,
                 maxlength: el.maxLength > 0 ? el.maxLength : undefined, visible: visible(el) };
      }),
    };
  }

  root.SPMatcher = { norm: norm, roleOf: roleOf, fieldOf: fieldOf, fromId: fromId, describe: describe, fill: fill, diagnose: diagnose };
})(typeof window !== "undefined" ? window : globalThis);
