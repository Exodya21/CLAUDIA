(function(){
'use strict';
/* =====================================================================
   RELLENAR LA FICHA C DESDE UN WORD
   Lee el .docx en el navegador, pide a Claude que lo interprete (capacidad
   «sample» de la página publicada) y rellena solo las preguntas vacías.
   Lo que no aparece en el Word se lista para responderlo a mano.
   ===================================================================== */
const SF=window.SF,FC=window.FC,esc=SF.esc,$=id=>document.getElementById(id);
const getP=FC.getP,setP=FC.setP;
const has=v=>!(v===undefined||v===null||v===''||v===false||(Array.isArray(v)&&!v.length));
const norm=s=>String(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9ñ ]/g,' ').replace(/\s+/g,' ').trim();
const fecha=s=>/^\d{4}-\d{2}-\d{2}$/.test(String(s||''))&&!isNaN(Date.parse(s))?s:'';
const hora=s=>{const m=/^(\d{1,2})[:.h](\d{2})$/.exec(String(s||'').trim());return m&&+m[1]<=24&&+m[2]<60?String(+m[1]).padStart(2,'0')+':'+m[2]:'';};
const numTxt=x=>{if(x==null||x==='')return '';const n=Number(String(x).replace(/[^\d,.-]/g,'').replace(/\.(?=\d{3}(\D|$))/g,'').replace(',','.'));return isFinite(n)&&n>=0?String(Math.round(n*100)/100):'';};
const uno=(v,ok)=>ok.includes(v)?v:'';
const varios=(v,ok)=>Array.isArray(v)?[...new Set(v.filter(x=>ok.includes(x)))]:[];

/* ---------------- 1. texto del .docx (zip + XML) ---------------- */
async function inflar(bytes){const ds=new DecompressionStream('deflate-raw');const out=new Response(new Blob([bytes]).stream().pipeThrough(ds));return new Uint8Array(await out.arrayBuffer());}
async function leerZip(buf,nombre){const u=new Uint8Array(buf),dv=new DataView(buf);let e=-1;for(let i=u.length-22;i>=Math.max(0,u.length-66000);i--){if(dv.getUint32(i,true)===0x06054b50){e=i;break;}}if(e<0)throw new Error('zip');
 const n=dv.getUint16(e+10,true);let p=dv.getUint32(e+16,true);const dec=new TextDecoder();
 for(let k=0;k<n;k++){const met=dv.getUint16(p+10,true),cs=dv.getUint32(p+20,true),fl=dv.getUint16(p+28,true),xl=dv.getUint16(p+30,true),cl=dv.getUint16(p+32,true),off=dv.getUint32(p+42,true);const name=dec.decode(u.subarray(p+46,p+46+fl));
  if(name===nombre){const lf=dv.getUint16(off+26,true),lx=dv.getUint16(off+28,true);const data=u.subarray(off+30+lf+lx,off+30+lf+lx+cs);return dec.decode(met===0?data:await inflar(data));}
  p+=46+fl+xl+cl;}
 return null;}
FC.docxTexto=async file=>{const xml=await leerZip(await file.arrayBuffer(),'word/document.xml');if(!xml)throw new Error('sin document.xml');
 const doc=new DOMParser().parseFromString(xml,'application/xml');const W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';const L=[];
 const txt=n=>{let s='';const w=x=>{for(const ch of x.childNodes){if(ch.namespaceURI!==W){continue;}const t=ch.localName;if(t==='t')s+=ch.textContent;else if(t==='tab')s+='\t';else if(t==='br'||t==='cr')s+='\n';else if(t==='sym')s+='☒';else if(t==='checkBox'||t==='checkbox'){const v=[...ch.getElementsByTagNameNS(W,'checked'),...ch.getElementsByTagNameNS(W,'default')][0];s+=v&&v.getAttributeNS(W,'val')!=='0'&&v.getAttributeNS(W,'val')!=='false'?'☒ ':'☐ ';}else w(ch);}};w(n);return s.trim();};
 const walk=n=>{for(const ch of n.childNodes){if(ch.namespaceURI!==W)continue;if(ch.localName==='p'){const t=txt(ch);if(t)L.push(t);}else if(ch.localName==='tbl'){for(const tr of ch.childNodes){if(tr.localName!=='tr')continue;const cells=[...tr.childNodes].filter(x=>x.localName==='tc').map(tc=>[...tc.childNodes].filter(x=>x.localName==='p'||x.localName==='tbl').map(x=>x.localName==='p'?txt(x):'[tabla]').filter(Boolean).join(' / '));if(cells.some(Boolean))L.push(cells.join(' | '));}}else walk(ch);}};
 walk(doc.documentElement);return L.join('\n');};

/* ---------------- 2. lo que se le pide a Claude ---------------- */
const DIR='{"via":"Calle|Avenida|Plaza|Paseo|Carretera|Camino|Ronda|Travesía|Glorieta|Urbanización|Polígono|Otro","calle":"","numero":"","bloque":"","escalera":"","piso":"","puerta":"","cp":"5 cifras","municipio":"","provincia":""}';
const ESQUEMA=`{
 "cliente":{"trato":"da (mujer) | d (hombre)","nombre":"","apellidos":"","documento":"DNI | NIE | Pasaporte | ninguno","numDocumento":"","paisNacionalidad":"nombre del país","fechaNacimiento":"AAAA-MM-DD","telefono":"con prefijo si lo tiene","email":"","empadronada":"si | no","padron":${DIR},"domicilio":${DIR},"cargoSindical":"si | no"},
 "filtro":{"otroAbogado":"no | si | cambiar","reclamar":["despido|salarios|vacaciones|horas|alta|finiquito|otro"],"motivo":"qué quiere conseguir, con sus palabras","conocio":["tiktok|facebook|instagram|vozavoz|amiga|excliente|despacho|otro"],"conocioOtro":"","hechaPor":"quién hizo la entrevista o la ficha"},
 "relacion":{"inicio":"AAAA-MM-DD","fin":"AAAA-MM-DD","contrato":"verbal | escrito","alta":"si | no","altas":[{"alta":"AAAA-MM-DD","baja":"AAAA-MM-DD"}],"autorizacion":"nunca | siempre | parte"},
 "empleadores":[{"trato":"da | d","nombre":"","apellidos":"","papel":"señora de la casa, hijo…","edad":0,"documento":"DNI | NIE | Pasaporte","numDocumento":"","telefono":"","email":"","domicilio":${DIR},"viviaEnLaCasa":true}],
 "otrasPersonas":[{"trato":"da | d","nombre":"","apellidos":"","papel":"persona cuidada, nieta, portero…","edad":0,"viviaEnLaCasa":true,"cuidada":true}],
 "lugaresDeTrabajo":[${DIR}],
 "tareas":["limpiar_casa|limpiar_banos|limpiar_cocina|lavar|planchar|cocinar|compras|ninos|mayores|dependientes|citas|mascotas|pasear|otras"],"tareasOtras":"",
 "jornada":{"modalidad":"interna | externa | horas | mixta","turnos":[{"dias":[0,1,2,3,4],"entrada":"HH:MM","salida":"HH:MM"}],"descansoMinutos":0,"explicacion":"la jornada tal como la cuenta"},
 "salario":{"fijo":"si | no","importeMensual":0,"forma":["efectivo|transferencia|bizum|otra"],"dia":"qué día cobraba","pagasExtra":"si | no","porHoras":"si | no","precioHora":0,"ultimoMes":{"pagado":"si | no","salarioDias":0,"vacaciones":0,"pagasExtra":0,"indemnizacion":0,"otros":0}},
 "vacaciones":{"tuvo":"si | no"},
 "fin":{"tipo":"despido | renuncia | fallecimiento | otro | continua","fechaFin":"AAAA-MM-DD","fechaComunicacion":"AAAA-MM-DD","quePaso":"lo que pasó el día del despido","queLeDijeron":""},
 "observaciones":"datos útiles del Word que no encajan en ningún campo"
}`;
const PROMPT=t=>`Eres asistente de un despacho de abogados laboralistas en España. Te paso el texto de la ficha de entrevista de una clienta (empleada de hogar), escrita a mano por un asesor en Word. Extrae los datos para rellenar una ficha estructurada.

Reglas:
- Responde solo con un objeto JSON con exactamente esta forma (los textos entre comillas indican el formato o los valores permitidos separados por |):
${ESQUEMA}
- Usa null en todo dato que el Word no diga claramente. No inventes, no deduzcas fechas ni importes que no estén escritos y no rellenes con valores de ejemplo.
- Fechas en formato AAAA-MM-DD; si solo aparece mes y año, null. Horas en HH:MM. Importes en euros como número.
- En listas con valores permitidos usa solo esos códigos. En "dias" de los turnos: 0=lunes … 6=domingo.
- Las casillas marcadas pueden aparecer como ☒, X o ✓ y las vacías como ☐.
- "empleadores" son quienes la contrataban, le pagaban o le daban órdenes; "otrasPersonas" son el resto de personas de la casa (persona cuidada si no es la empleadora, familiares, testigos).
- Copia los textos tal como están, sin corregir nombres.

TEXTO DEL WORD:
"""
${t}
"""`;

/* ---------------- 3. pasar la respuesta a la ficha (solo lo vacío) ---------------- */
FC.aplicarImport=(c,d)=>{const R={ok:[],falta:[]};d=d&&typeof d==='object'?d:{};
 const put=(path,v,label)=>{if(!has(v)){R.falta.push(label);return;}if(has(getP(c,path))){return;}setP(c,path,v);R.ok.push(label);};
 const prov=(cp,nombre)=>{if(/^\d{5}$/.test(cp||'')&&window.TERR.prov[cp.slice(0,2)])return cp.slice(0,2);const k=norm(nombre);if(!k)return '';const f=FC.provList().find(([,n])=>norm(n)===k||norm(n).includes(k)||k.includes(norm(n)));return f?f[0]:'';};
 const dir=(x,path,label)=>{if(!x||typeof x!=='object'){R.falta.push(label);return false;}const cur=getP(c,path);if(cur&&!FC.dirVacia(cur))return true;const D=FC.newDir();
  D.via=FC.VIAS.includes(x.via)?x.via:'';D.calle=String(x.calle||'').trim();D.num=String(x.numero||'').trim();D.bloque=String(x.bloque||'').trim();D.esc=String(x.escalera||'').trim();D.piso=String(x.piso||'').trim();D.puerta=String(x.puerta||'').trim();
  D.cp=/^\d{5}$/.test(String(x.cp||'').trim())?String(x.cp).trim():'';D.prov=prov(D.cp,x.provincia);if(D.prov&&x.municipio){const m=FC.munSearch(D.prov,String(x.municipio))[0];if(m){D.codm=m.codm;D.munq=m.name;}else D.munq=String(x.municipio);}
  if(FC.dirVacia(D)){R.falta.push(label);return false;}setP(c,path,D);R.ok.push(label);return true;};
 const doc=v=>({dni:'DNI',nie:'NIE',pasaporte:'Pasaporte',ninguno:'ninguno'})[norm(v)]||'';
 const tel=(base,v)=>{const s=String(v||'').trim();if(!s)return false;let d=s.replace(/\D/g,'');let pref='ES';if(/^(\+|00)/.test(s)){d=d.replace(/^00/,'');const p=FC.PREF.slice().sort((a,b)=>b[2].length-a[2].length).find(p=>d.startsWith(p[2].slice(1)));if(p){pref=p[0];d=d.slice(p[2].length-1);}}if(has(getP(c,base+'.tel')))return true;setP(c,base+'.telPref',pref);setP(c,base+'.tel',d);return true;};
 const k=d.cliente||{},cl='Cliente: ';
 put('cli.trato',uno(k.trato,['da','d']),cl+'D.ª o D.');put('cli.nombre',k.nombre&&String(k.nombre).trim(),cl+'nombre');put('cli.apellidos',k.apellidos&&String(k.apellidos).trim(),cl+'apellidos');
 put('cli.doc',doc(k.documento),cl+'documento');put('cli.docnum',k.numDocumento&&String(k.numDocumento).trim(),cl+'número de documento');
 {const p=FC.PAISES.find(x=>norm(x[1])===norm(k.paisNacionalidad));put('cli.pais',p?p[0]:'',cl+'país de nacionalidad');}
 put('cli.nac',fecha(k.fechaNacimiento),cl+'fecha de nacimiento');if(!tel('cli',k.telefono))R.falta.push(cl+'teléfono');else if(!R.ok.includes(cl+'teléfono'))R.ok.push(cl+'teléfono');
 put('cli.email',k.email&&String(k.email).replace(/\s/g,''),cl+'correo electrónico');put('cli.empadronada',uno(k.empadronada,['si','no']),cl+'¿está empadronada?');
 if(k.empadronada==='si')dir(k.padron,'cli.padronDir',cl+'dirección del padrón');dir(k.domicilio,'cli.dom',cl+'dirección donde vive');put('cli.sindical',uno(k.cargoSindical,['si','no']),cl+'cargo sindical');
 const f=d.filtro||{};put('filtro.abogado',uno(f.otroAbogado,['no','si','cambiar']),'Filtro: ¿otro abogado lleva el caso?');put('filtro.reclamar',varios(f.reclamar,['despido','salarios','vacaciones','horas','alta','finiquito','otro']),'Filtro: qué quiere reclamar');
 put('filtro.motivo',f.motivo,'Filtro: qué le gustaría conseguir');put('filtro.conocio',varios(f.conocio,['tiktok','facebook','instagram','vozavoz','amiga','excliente','despacho','otro']),'Filtro: cómo nos conoció');if(f.conocioOtro)put('filtro.conocioOtro',f.conocioOtro,'Filtro: cómo nos conoció (otro)');put('filtro.hechaPor',f.hechaPor,'Filtro: ficha hecha por');
 const r=d.relacion||{};put('rel.inicio',fecha(r.inicio),'Relación: fecha de inicio');if(fecha(r.fin))put('rel.fin',fecha(r.fin),'Relación: fecha de fin');put('rel.contrato',uno(r.contrato,['verbal','escrito']),'Relación: ¿contrato por escrito?');
 put('rel.alta',uno(r.alta,['si','no']),'Relación: ¿alta en la Seguridad Social?');put('rel.autGlobal',uno(r.autorizacion,['nunca','siempre','parte']),'Relación: ¿autorización de trabajo?');
 if(r.alta==='si'&&!c.altas.length){const A=(Array.isArray(r.altas)?r.altas:[]).filter(a=>a&&fecha(a.alta));A.forEach(a=>{const x=FC.T.altas(c);x.alta=fecha(a.alta);x.baja=fecha(a.baja);c.altas.push(x);});if(A.length)R.ok.push('Relación: fechas de alta');else R.falta.push('Relación: fechas de alta');}
 const persona=(x,rol)=>{const p=FC.T.personas(c);p.trato=uno(x.trato,['da','d'])||'da';p.nombre=String(x.nombre||'').trim();p.apellidos=String(x.apellidos||'').trim();p.papel=String(x.papel||'').trim();const e=Number(x.edad);if(e>0&&e<=140)p.edad=String(e);
  if(rol==='emp'){const dt=doc(x.documento);if(dt&&dt!=='ninguno')p.docTipo=dt;p.docNum=String(x.numDocumento||'').trim();p.email=String(x.email||'').replace(/\s/g,'');const t=String(x.telefono||'').replace(/\D/g,'');if(t)p.tel=t;p.m={titular:true};}else p.m={};
  if(x.viviaEnLaCasa===true)p.m.vive=true;c.personas.push(p);return p;};
 const E=(Array.isArray(d.empleadores)?d.empleadores:[]).filter(x=>x&&(x.nombre||x.apellidos));
 if(!c.empleadores.length&&E.length){E.forEach((x,i)=>{const p=persona(x,'emp');const e=FC.T.empleadores(c);e.titular=p.id;c.empleadores.push(e);dir(x.domicilio,`empleadores.${c.empleadores.length-1}.dom`,`Empleador ${i+1}: domicilio`);});R.ok.push('Empleadores ('+E.length+')');}
 else if(!E.length&&!c.empleadores.length)R.falta.push('Empleadores: nombre y datos');
 const O=(Array.isArray(d.otrasPersonas)?d.otrasPersonas:[]).filter(x=>x&&x.nombre);const yaNom=new Set(c.personas.map(p=>norm(FC.full(p))));
 O.forEach(x=>{if(yaNom.has(norm([x.nombre,x.apellidos].filter(Boolean).join(' '))))return;const p=persona(x,'otra');if(x.cuidada===true){const k2=FC.T.cuidados(c);k2.persona=p.id;c.cuidados.push(k2);}});if(O.length)R.ok.push('Otras personas de la casa ('+O.length+')');
 const LG=(Array.isArray(d.lugaresDeTrabajo)?d.lugaresDeTrabajo:[]).filter(x=>x&&typeof x==='object');
 if(!c.lugares.length&&LG.length){LG.forEach((x,i)=>{const l=FC.T.lugares(c);c.lugares.push(l);if(c.empleadores[0])l.quienes=[c.empleadores[0].titular];if(!dir(x,`lugares.${c.lugares.length-1}.dir`,`Lugar de trabajo ${i+1}: dirección`))c.lugares.pop();});}
 else if(!c.lugares.length)R.falta.push('Lugar de trabajo: dirección');
 put('tareas',varios(d.tareas,FC.TAREAS.map(x=>x[0])),'Tareas: qué tareas hacía');if(d.tareasOtras)put('tareasOtras',d.tareasOtras,'Tareas: otras tareas');
 const j=d.jornada||{};const T=(Array.isArray(j.turnos)?j.turnos:[]).map(t=>({dias:varios(t&&t.dias,[0,1,2,3,4,5,6]),e:hora(t&&t.entrada),s:hora(t&&t.salida)})).filter(t=>t.dias.length&&t.e&&t.s);
 if(!c.periodos.length&&(T.length||j.modalidad)){const P=FC.T.periodos(c);P.modalidad=uno(j.modalidad,['interna','externa','horas','mixta']);P.desde=c.rel.inicio||'';P.hasta=c.rel.fin||'';const dm=Number(j.descansoMinutos)>0?String(Math.round(Number(j.descansoMinutos))):'';
  T.forEach(t=>{const u=FC.newTurno(c,t.dias);u.e=t.e;u.s=t.s;u.descMin=dm;P.semanas[0].turnos.push(u);});c.periodos.push(P);
  if(T.length)R.ok.push('Jornada: horario');else R.falta.push('Jornada: horario (entrada, salida y días)');if(P.modalidad)R.ok.push('Jornada: interna o externa');else R.falta.push('Jornada: interna o externa');}
 else if(!c.periodos.length)R.falta.push('Jornada: horario (entrada, salida y días)');
 if(j.explicacion&&String(j.explicacion).trim())c.nota['periodos']=c.nota['periodos']||('Del Word: '+String(j.explicacion).trim());
 const s=d.salario||{};put('sal.fijo',uno(s.fijo,['si','no']),'Salario: ¿siempre la misma cantidad?');put('sal.importe',numTxt(s.importeMensual),'Salario: importe mensual');put('sal.forma',varios(s.forma,['efectivo','transferencia','bizum','otra']),'Salario: cómo le pagaban');
 if(s.dia)put('sal.dia',s.dia,'Salario: día de pago');put('sal.pagas',uno(s.pagasExtra,['si','no']),'Salario: pagas extra');if(s.porHoras)put('sal.porHoras',uno(s.porHoras,['si','no']),'Salario: ¿por horas?');if(s.porHoras==='si')put('sal.precioHora',numTxt(s.precioHora),'Salario: precio de la hora');
 const um=s.ultimoMes||{};if(c.fin&&(fecha(r.fin)||fecha((d.fin||{}).fechaFin)||c.rel.fin||c.fin.fechaFin)){put('sal.ultimoMes',uno(um.pagado,['si','no']),'Salarios: ¿le pagaron algo el último mes?');if(um.pagado==='si'){[['ultimoMesImporte',um.salarioDias,'salario de los días'],['finVac',um.vacaciones,'vacaciones'],['finPagas',um.pagasExtra,'pagas extra'],['finIndem',um.indemnizacion,'indemnización'],['finOtros',um.otros,'otros conceptos']].forEach(([k3,v,l])=>{if(numTxt(v))put('sal.'+k3,numTxt(v),'Último mes: '+l);});}}
 put('vac.tuvo',uno((d.vacaciones||{}).tuvo,['si','no']),'Vacaciones: ¿tuvo vacaciones?');
 const fi=d.fin||{};put('fin.tipo',uno(fi.tipo,['despido','renuncia','fallecimiento','otro','continua']),'Fin: qué pasó con su trabajo');if(fi.tipo&&fi.tipo!=='continua'){put('fin.fechaFin',fecha(fi.fechaFin)||fecha(r.fin),'Fin: qué día dejó de trabajar');if(!c.rel.fin&&c.fin.fechaFin)c.rel.fin=c.fin.fechaFin;}
 if(fi.tipo==='despido'){put('fin.fechaCom',fecha(fi.fechaComunicacion),'Despido: qué día se lo comunicaron');put('fin.dia',fi.quePaso,'Despido: qué pasó ese día');put('fin.dicho',fi.queLeDijeron,'Despido: qué le dijeron');}
 if(d.observaciones&&String(d.observaciones).trim()){c.obs=(c.obs?c.obs+'\n\n':'')+'Del Word (sin casilla propia): '+String(d.observaciones).trim();R.ok.push('Observaciones generales');}
 return R;};

/* ---------------- 4. pantalla ---------------- */
FC.smp=undefined;FC.impBusy=null;
(async()=>{try{FC.smp=(window.claude&&window.claude.use)?await window.claude.use('sample'):null;}catch(e){FC.smp=null;}if(FC.st&&FC.step===0&&$('vC')&&!$('vC').hidden)FC.render();})();
const ERR={not_granted:'No se ha dado permiso a esta página para usar Claude.',sampling_disabled:'Claude no está disponible para esta cuenta.',rate_limited:'Demasiadas peticiones o límite de uso alcanzado. Pruebe más tarde.',session_expired:'La sesión ha caducado: vuelva a entrar en claude.ai.',prompt_too_large:'El Word es demasiado largo para leerlo de una vez.',invalid_json:'Claude no devolvió una respuesta legible. Pruebe otra vez.',refused:'Claude no ha podido procesar este documento.'};
FC.impCard=()=>{const c=FC.st.c,I=c.imp;const E=FC.evaluate(FC.st);
 let h=`<div class="x-card x-stack fc-imp"><h3 class="x-h3">Rellenar desde una ficha en Word</h3>`;
 if(FC.smp===null)h+=`<p class="x-help">Esta opción solo funciona con la ficha abierta en claude.ai: allí Claude lee el Word y rellena las preguntas.</p>`;
 else if(FC.smp===undefined)h+=`<p class="x-help">Comprobando si Claude está disponible…</p>`;
 else if(FC.impBusy)h+=`<p><b>${esc(FC.impBusy)}</b></p><div class="x-row"><button class="x-btn sm" type="button" id="fcImpStop">Detener</button></div>`;
 else h+=`<p class="x-help">Suba la ficha del cliente en Word (.docx). Claude la lee y responde todas las preguntas que pueda; solo rellena las que estén vacías. Después se listan las que no se han podido responder. Revise siempre lo rellenado. Prototipo: use solo fichas con datos inventados.</p><div class="x-row"><label class="x-btn pri" for="fcImpFile" style="cursor:pointer">Subir ficha en Word</label><input type="file" id="fcImpFile" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" hidden></div>`;
 if(I){h+=`<p class="x-lead">Rellenada desde «${esc(I.archivo)}» el ${esc(I.fecha)}: ${I.ok.length} respuestas.</p>`;
  const pasos=[...new Set(E.inc.map(i=>i.s))].sort((a,b)=>a-b);
  h+=`<h3 class="x-h3">Preguntas obligatorias sin responder (${E.inc.length})</h3>${E.inc.length?pasos.map(s=>`<div><button class="x-link" type="button" data-step="${s}"><b>${esc(FC.STEPS[s])}</b></button><ul class="x-mini">${E.inc.filter(i=>i.s===s).map(i=>`<li class="w">${esc(i.l)}</li>`).join('')}</ul></div>`).join(''):'<p class="x-empty">Ninguna.</p>'}`;
  const fal=I.falta.filter((x,i,a)=>a.indexOf(x)===i);h+=`<h3 class="x-h3">Datos que no estaban en el Word (${fal.length})</h3>${fal.length?`<ul class="x-mini">${fal.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'<p class="x-empty">Ninguno.</p>'}<div class="x-row"><button class="x-btn sm" type="button" id="fcImpClose">Ocultar este resumen</button></div>`;}
 return h+'</div>';};
let ctl=null;
async function importar(file){const c=FC.st.c;if(!/\.docx$/i.test(file.name)){SF.toast('Suba un archivo Word .docx (los .doc antiguos no se pueden leer: ábralo en Word y guárdelo como .docx)',1);return;}
 FC.impBusy='Leyendo el Word…';FC.render();let texto;
 try{texto=await FC.docxTexto(file);}catch(e){FC.impBusy=null;FC.render();SF.toast('No se ha podido leer el Word',1);return;}
 if(!texto.trim()){FC.impBusy=null;FC.render();SF.toast('El Word no tiene texto',1);return;}
 FC.impBusy='Claude está leyendo la ficha… puede tardar uno o dos minutos';FC.render();ctl=new AbortController();
 try{const d=await FC.smp.json(PROMPT(texto.slice(0,150000)),{signal:ctl.signal,modelTier:'default'});const R=FC.aplicarImport(c,d);
  c.imp={archivo:file.name,fecha:new Date().toLocaleString('es-ES'),ok:R.ok,falta:R.falta};FC.impBusy=null;FC.step=0;FC.render();SF.toast(`Ficha rellenada: ${R.ok.length} respuestas. Revise lo que falta.`);}
 catch(e){FC.impBusy=null;FC.render();if(e&&e.code==='cancelled')return;SF.toast(ERR[e&&e.code]||'No se ha podido completar. Pruebe otra vez más tarde.',1);}
 finally{ctl=null;}}
document.addEventListener('change',e=>{if(e.target&&e.target.id==='fcImpFile'&&e.target.files&&e.target.files[0])importar(e.target.files[0]);});
document.addEventListener('click',e=>{const t=e.target;if(!t||!t.id)return;if(t.id==='fcImpStop'&&ctl)ctl.abort();if(t.id==='fcImpClose'){delete FC.st.c.imp;FC.render();}});
})();
