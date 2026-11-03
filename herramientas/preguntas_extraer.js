// Recorre la ficha C en el navegador y saca todas las preguntas con sus respuestas posibles.
// Uso: node herramientas/preguntas_extraer.js "$PWD/super_ficha_laboral.html" preguntas.json   (luego: python3 herramientas/preguntas_excel.py preguntas.json salida.xlsx)
const {chromium}=require('playwright');
const fs=require('fs');
const [,,HTML,OUT]=process.argv;

// en la página: lista de preguntas visibles del paso actual, en orden
function recoger(){
  const root=document.getElementById('vC');
  const main=root.querySelector('.x-main')||root;
  const T=s=>(s||'').replace(/\s+/g,' ').trim();
  const norm=p=>(p||'').replace(/\.\d+(?=\.|$)/g,'.n');
  const esPer=v=>/^[PELRKJS]\d+$/.test(v);const QUE={P:'(las personas apuntadas en la ficha)',E:'(los empleadores apuntados en la ficha)',L:'(los lugares de trabajo apuntados en la ficha)',R:'(las pruebas apuntadas en la ficha)',K:'(las personas cuidadas apuntadas en la ficha)',J:'(los periodos apuntados en la ficha)',S:'(las altas apuntadas en la ficha)'};const queDe=v=>QUE[v[0]]||'(elementos apuntados en la ficha)';
  const GR={empleadores:'Empleador',lugares:'Lugar de trabajo',altas:'Alta en la Seguridad Social',autorizacion:'Periodo de autorización de trabajo',personas:'Persona de la casa',cuidados:'Persona cuidada',periodos:'Periodo de jornada',meses:'Mes',incidencias:'Otra cantidad (pagada o debida)',vacaciones:'Periodo de vacaciones',cronologia:'Hecho de la cronología',pruebas:'Prueba'};
  const items=[];const vistos=new Set();
  const grupoDe=el=>{const ep=el.closest('.fc-emp-p');if(ep){const t=T((ep.querySelector('.fc-ct')||{}).textContent);return /^También/.test(t)?'Otra persona empleadora':'Empleador';}
    const cd=el.closest('[data-card]');if(!cd)return '';const cp=cd.dataset.card;if(/\.desc\./.test(cp))return 'Descanso del turno';if(/\.turnos\./.test(cp))return 'Turno';if(/\.semanas\./.test(cp))return 'Semana modelo';return GR[cp.split('.')[0]]||T((cd.querySelector(':scope > .fc-ct')||{}).textContent).replace(/\s+\d+$/,'');};
  const secDe=el=>{const s=el.closest('.x-sec');return s?T((s.querySelector(':scope > h2')||{}).textContent):'';};
  const opcionesBotones=(el,sel)=>{const bs=[...el.querySelectorAll(sel)].filter(b=>!b.classList.contains('ns'));if(!bs.length)return null;
    const per=bs.every(b=>esPer(b.dataset.v||''));return {multi:bs.some(b=>b.dataset.multi==='1')||bs[0].classList.contains('x-chip'),ops:per?[queDe(bs[0].dataset.v)]:bs.map(b=>T(b.textContent))};};
  const tipoControl=el=>{
    const tb=el.querySelector('table');if(tb&&tb.querySelector('[data-p]'))return {tipo:'Tabla (una fila por mes)',ops:['Columnas: '+[...tb.querySelectorAll('th')].map(h=>T(h.textContent)).filter(Boolean).join(' · ')]};
    if(el.querySelector('.x-addr'))return {tipo:'Dirección',ops:['Tipo de vía, nombre de la vía, número, portal o bloque, escalera, piso, puerta, código postal, provincia, municipio (de la lista), indicaciones; comprobación en Google Maps']};
    const ob=opcionesBotones(el,'[data-op]');if(ob)return {tipo:(ob.multi?'Varias opciones':'Una opción')+(el.querySelector('input[data-p]:not([type=number]):not([type=date])')?' + texto libre':''),ops:ob.ops};
    const tg=opcionesBotones(el,'[data-tog]');if(tg)return {tipo:'Casillas (marcar las que correspondan)',ops:tg.ops};
    if(el.querySelector('[data-dpart]'))return {tipo:'Fecha (día, mes y año)',ops:[]};
    const telPref=el.querySelector('select[data-p$=".telPref"]');if(telPref)return {tipo:'Teléfono (prefijo del país + número)',ops:[]};
    const s=el.querySelector('select[data-p]');if(s){const o=[...s.options].filter(o=>o.value);return {tipo:'Desplegable',ops:o.every(x=>esPer(x.value))&&o.length?[queDe(o[0].value)]:o.map(x=>T(x.textContent))};}
    const ta=el.querySelector('textarea[data-p]');if(ta)return {tipo:'Texto largo',ops:[]};
    const f=el.querySelector('input[type=file]');if(f)return {tipo:'Archivos',ops:[]};
    const i=el.querySelector('input[data-p]');if(i){const t=i.type;return {tipo:t==='number'?'Número':t==='email'?'Correo electrónico':t==='date'?'Fecha':'Texto',ops:[],min:i.min,max:i.max};}
    return null;};
  const clave=(el,label)=>{const c=['[data-p]:not([data-p$=".telPref"])','[data-dpart]','[data-op]','[data-tog]'].map(q=>el.querySelector(q)).find(Boolean);const p=c?(c.dataset.p||c.dataset.op||c.dataset.dpart||c.dataset.tog||''):'';return norm(p.replace(/\.(telPref|via|calle)$/,''))+'|'+label;};
  const push=(el,label,extra)=>{label=T(label).replace(/\s*·\s*obligatoria$/,'');if(!label)return;const tc=tipoControl(el);if(!tc)return;const k=grupoDe(el)+'|'+clave(el,label);if(vistos.has(k))return;vistos.add(k);
    const help=[...el.querySelectorAll(':scope > .x-help, :scope > div > .x-help')].map(h=>T(h.textContent)).filter(Boolean).join(' ');
    items.push(Object.assign({k,sec:secDe(el),grupo:grupoDe(el),label,tipo:tc.tipo,ops:tc.ops,min:tc.min||'',max:tc.max||'',req:el.classList.contains('req'),ns:!!el.querySelector(':scope [data-ns]'),help},extra||{}));};
  const nodos=[...main.querySelectorAll('.x-q, .x-fld, .roles, textarea[data-p], input[data-p], select[data-p]')];
  for(const el of nodos){
    if(el.closest('.fc-imp'))continue;
    if(el.matches('.x-q')){const lab=el.querySelector(':scope > .x-qt');if(!lab)continue;push(el,lab.textContent);continue;}
    if(el.matches('.x-fld')){if(el.closest('.x-q')&&el.closest('.x-q').querySelector('.x-addr'))continue;if(el.closest('.x-q')&&el.closest('.x-q').querySelector('.x-fld')===null)continue;
      const lab=el.querySelector(':scope > label, :scope > .x-lead');if(!lab)continue;if(el.closest('.x-q')&&!el.querySelector('[data-p],[data-op],[data-dpart]'))continue;push(el,lab.textContent);continue;}
    if(el.matches('.roles')){if(el.closest('.x-q'))continue;if(!el.querySelector('[data-tog],[data-op]'))continue;const lab=el.querySelector(':scope > .x-lead');if(!lab)continue;push(el,lab.textContent);continue;}
    if(el.closest('.x-q,.x-fld,.roles'))continue;const lab=el.getAttribute('aria-label');if(lab){const w=document.createElement('div');w.appendChild(el.cloneNode(true));w.className=el.className;push(w,lab);}
  }
  return items;}

(async()=>{const T0=Date.now();const b=await chromium.launch();const p=await b.newPage({viewport:{width:1200,height:1000}});
 await p.goto('file://'+HTML);await p.evaluate(()=>{window.scrollTo=()=>{};SF.toast=()=>{};});
 const pasos=await p.evaluate(()=>FC.STEPS);
 const master={};// paso -> {orden:[k], items:{k:item}}
 const fuente={};// k -> conjunto de condiciones en que apareció
 const recoge=async(paso,cond)=>{const L=await p.evaluate(recoger);const M=master[paso]||(master[paso]={orden:[],items:{}});let prev=null;
   for(const it of L){if(M.items[it.k]&&it.ops.length>M.items[it.k].ops.length){M.items[it.k].ops=it.ops;M.items[it.k].tipo=it.tipo;}if(!M.items[it.k]){M.items[it.k]=it;const at=prev?M.orden.indexOf(prev)+1:0;M.orden.splice(at,0,it.k);}
     (fuente[paso+'§'+it.k]=fuente[paso+'§'+it.k]||new Set()).add(cond);prev=it.k;}
   return L.length;};
 const ir=async paso=>{await p.evaluate(s=>{FC.step=s;FC.render();},paso);};
 const explorar=async(paso,cond)=>{await ir(paso);await recoge(paso,cond);const hecho=new Set(),añadidos=new Set();
   for(let ronda=0;ronda<2;ronda++){
     // botones de opción y desplegables que cambian la pantalla
     const ctr=await p.evaluate(()=>{const m=document.querySelector('#vC .x-main')||document.getElementById('vC');const o=[];
       m.querySelectorAll('[data-op]').forEach(b=>{if(!b.closest('.fc-imp'))o.push(['op',b.dataset.op,b.dataset.v]);});
       m.querySelectorAll('select[data-p][data-rr]').forEach(s=>[...s.options].forEach(x=>{if(x.value&&!/telPref$/.test(s.dataset.p))o.push(['sel',s.dataset.p,x.value]);}));
       return o;});
     for(const [t,path,v] of ctr){const kk=t+path.replace(/\.\d+/g,'.n')+'='+v;if(hecho.has(kk))continue;hecho.add(kk);
       await p.evaluate(([t,path,v])=>{const m=document.querySelector('#vC .x-main')||document.getElementById('vC');
         if(t==='op'){const b=[...m.querySelectorAll('[data-op]')].find(x=>x.dataset.op===path&&x.dataset.v===v);if(b&&b.getAttribute('aria-pressed')!=='true')b.click();}
         else{const s=[...m.querySelectorAll('select[data-p]')].find(x=>x.dataset.p===path);if(s){s.value=v;s.dispatchEvent(new Event('change',{bubbles:true}));}}},[t,path,v]);
       await recoge(paso,cond);
       const nuevos=(await p.evaluate(()=>[...document.querySelectorAll('#vC [data-add]')].map(b=>b.dataset.add))).filter(a=>!añadidos.has(a.replace(/\.\d+/g,'.n')));
       for(const a of nuevos){añadidos.add(a.replace(/\.\d+/g,'.n'));await p.evaluate(a=>{const b=[...document.querySelectorAll('#vC [data-add]')].find(x=>x.dataset.add===a);if(b)b.click();},a);await recoge(paso,cond);}}
     // añadir un elemento de cada lista
     {const adds=(await p.evaluate(()=>[...(document.querySelector('#vC .x-main')||document.getElementById('vC')).querySelectorAll('[data-add]')].map(b=>b.dataset.add))).filter(a=>!añadidos.has(a.replace(/\.\d+/g,'.n')));adds.forEach(a=>añadidos.add(a.replace(/\.\d+/g,'.n')));
       for(const a of adds){await p.evaluate(a=>{const b=[...document.querySelectorAll('#vC [data-add]')].find(x=>x.dataset.add===a);if(b)b.click();},a);await p.waitForTimeout(5);await recoge(paso,cond);}}
   }};
 for(const modo of ['asesor','abogado']){console.log('modo',modo);
   // ficha vacía: lo que se ve siempre
   await p.evaluate(m=>{document.querySelector('[data-new="C"]')?document.querySelector('[data-new="C"]').click():null;SF.mode=m;},modo);
   await p.waitForTimeout(50);await p.evaluate(m=>{SF.mode=m;},modo);
   for(let s=0;s<pasos.length;s++){await ir(s);await recoge(s,modo+':base');}
   // explorar con la ficha vacía y con la de ejemplo
   for(const base of ['vacia','ejemplo']){
     for(let s=0;s<pasos.length;s++){
       await p.evaluate(([base,m])=>{FC.render&&0;const ini=document.getElementById('vInicio');if(ini)ini.hidden=false;},[base,modo]);
       await p.evaluate(([base,m])=>{if(base==='vacia')document.querySelector('[data-new="C"]').click();else document.querySelector('[data-demo="C"]').click();SF.mode=m;const s=document.getElementById('fcMode');if(s)s.value=m;},[base,modo]);
       if(modo==='abogado'&&s!==9)continue;await p.waitForTimeout(30);await explorar(s,modo+':'+base);console.log(modo,base,s,Date.now()-T0);
       await p.evaluate(()=>{const v=document.getElementById('fcSave');if(v)v.click();});await p.waitForTimeout(20);
     }}
 }
 const out=pasos.map((nombre,s)=>{const M=master[s]||{orden:[],items:{}};return {paso:s,nombre,items:M.orden.map(k=>{const it=M.items[k];const f=fuente[s+'§'+k]||new Set();
   const ap=f.has('asesor:base')?'Siempre':[...f].some(x=>x.startsWith('asesor'))?(it.grupo?'Al añadir: '+it.grupo:'Según otra respuesta'):'Solo en modo abogado';return Object.assign({},it,{aparece:ap});})};});
 fs.writeFileSync(OUT,JSON.stringify(out,null,1));console.log(out.map(x=>x.nombre+': '+x.items.length).join('\n'));await b.close();})();
