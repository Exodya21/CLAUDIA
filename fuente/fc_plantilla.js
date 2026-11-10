(function(){
'use strict';
/* =====================================================================
   RELLENAR DESDE LA PLANTILLA NUEVA («Ficha de entrevista inicial» en Word)
   La plantilla tiene siempre los mismos títulos y las mismas tablas
   «Pregunta | Respuesta»: se lee directamente, SIN Claude (sin coste y
   siempre igual). Solo rellena lo que esté vacío en la ficha abierta.
   El importador antiguo (Word libre interpretado por Claude) sigue en fc_import.js.
   ===================================================================== */
const SF=window.SF,FC=window.FC,W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const norm=s=>String(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9ñ ]/g,' ').replace(/\s+/g,' ').trim();
const has=v=>!(v===undefined||v===null||v===''||v===false||(Array.isArray(v)&&!v.length));
const limpio=s=>String(s||'').replace(/[ \t]+/g,' ').replace(/\s*\n\s*/g,'\n').trim();
const MESES=['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
const trato=v=>{const s=String(v||'').trim();return /^(d\.?\s*[ªºa](?![a-z])|doña|sra)/i.test(s)?'da':/^(d\.?|don|sr\.?)(\s|$)/i.test(s)?'d':'';};
const DIAS=['lunes','martes','miercoles','jueves','viernes','sabado','domingo'];

/* ---------------- valores ---------------- */
const siNo=v=>{const k=norm(v);return /^(si|sí|s|yes|x)\b/.test(k)?'si':/^no\b/.test(k)?'no':'';};
const iso=(d,m,y)=>{y=+y;if(y<100)y+=y>50?1900:2000;const s=`${y}-${String(+m).padStart(2,'0')}-${String(+d).padStart(2,'0')}`;const t=new Date(s+'T00:00:00Z');return !isNaN(t)&&t.getUTCDate()===+d&&+m>=1&&+m<=12?s:'';};
/* todas las fechas de un texto, en orden: 06/11/2026, 6-11-26, 2026-11-06, «6 de noviembre de 2026» */
const fechas=v=>{const s=String(v||''),out=[];const re=/(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{2,4})|(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(?:de(?:l)?\s+)?(\d{4})/gi;let m;
 while((m=re.exec(s))){let f='';if(m[1])f=iso(m[3],m[2],m[1]);else if(m[4])f=iso(m[4],m[5],m[6]);else{const k=MESES.indexOf(norm(m[8]));if(k>=0)f=iso(m[7],k+1,m[9]);}if(f)out.push(f);}return out;};
const fecha=v=>fechas(v)[0]||'';
const num=v=>{const m=String(v||'').match(/\d[\d.]*(?:,\d+)?|\d+(?:\.\d+)?/);if(!m)return '';let t=m[0];t=/,\d+$/.test(t)?t.replace(/\./g,'').replace(',','.'):(/\.\d{3}(\.|$)/.test(t)?t.replace(/\./g,''):t);const n=Number(t);return isFinite(n)?String(Math.round(n*100)/100):'';};
const importes=v=>(String(v||'').match(/\d[\d.]*(?:,\d{1,2})?\s*(?:€|eur)/gi)||[]).map(num).filter(Boolean);
/* hora: «8:30», «8.30», «8h», «8», «8,5» (= 8:30) */
const hora=v=>{const s=String(v||'').trim().toLowerCase();let m=/^(\d{1,2})\s*[:h.]\s*(\d{2})\s*h?$/.exec(s);if(m)return +m[1]<=24&&+m[2]<60?String(+m[1]).padStart(2,'0')+':'+m[2]:'';
 m=/^(\d{1,2})(?:,(\d+))?\s*h?(?:oras)?$/.exec(s);if(!m)return '';const h=+m[1],min=m[2]?Math.round(Number('0.'+m[2])*60):0;return h<=24&&min<60?String(h).padStart(2,'0')+':'+String(min).padStart(2,'0'):'';};
const minutos=v=>{const k=norm(v);if(!k)return '';let m=/(\d+(?:[.,]\d+)?)\s*h(?:ora)?s?/.exec(k);if(m&&!/min/.test(k.slice(m.index,m.index+12)))return String(Math.round(Number(m[1].replace(',','.'))*60));
 if(/media hora/.test(k))return '30';if(/\buna hora\b/.test(k))return '60';if(/\bdos horas\b/.test(k))return '120';if(/\btres horas\b/.test(k))return '180';m=/(\d+)/.exec(k);return m?m[1]:'';};
const tc=s=>s===s.toUpperCase()&&/[A-ZÁÉÍÓÚÑ]/.test(s)?s.toLowerCase().replace(/(^|[\s\-'’])([a-záéíóúñü])/g,(a,b,c)=>b+c.toUpperCase()).replace(/\b(De|Del|La|Las|Los|Y)\b/g,x=>x.toLowerCase()).replace(/^./,x=>x.toUpperCase()):s;
/* nombre completo -> [nombre, apellidos]: 2 palabras 1+1, 3 palabras 1+2, 4 o más: los dos últimos son apellidos (con partículas «de la…») */
const partir=v=>{const s=tc(limpio(v));if(!s)return ['',''];const w=s.split(/\s+/),g=[];let pend=[];for(const x of w){if(/^(de|del|la|las|los|y|san|da|dos|van|von)$/i.test(x)){pend.push(x);continue;}g.push([...pend,x].join(' '));pend=[];}if(pend.length)g.push(pend.join(' '));
 const n=g.length;if(n<=1)return [g[0]||'',''];const k=n===2?1:n===3?1:n-2;return [g.slice(0,k).join(' '),g.slice(k).join(' ')];};
const docTipo=(v,numero)=>{const k=norm(v),n=String(numero||'').toUpperCase().replace(/[\s.\-]/g,'');if(/nie|tie/.test(k))return 'NIE';if(/dni|nif/.test(k)&&!/cif/.test(k))return /^[XYZ]/.test(n)?'NIE':'DNI';if(/pasap/.test(k))return 'Pasaporte';if(/cif/.test(k))return 'CIF';if(/ningun|no tiene/.test(k))return 'ninguno';
 if(/^[XYZ]\d{7}[A-Z]$/.test(n))return 'NIE';if(/^\d{8}[A-Z]$/.test(n))return 'DNI';if(/^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$/.test(n))return 'CIF';return '';};
const esEmpresa=(nombre,numero)=>/\b(s\.?\s?l\.?(u\.?)?|s\.?\s?a\.?(u\.?)?|s\.?\s?l\.?\s?l\.?|s\.?\s?coop\.?|sociedad|c\.?\s?b\.?|asociaci[oó]n|fundaci[oó]n)\s*$/i.test(String(nombre||'').trim())||docTipo('',numero)==='CIF';
const pais=v=>{const k=norm(v);if(!k)return '';if(/^espan/.test(k))return 'ES';const p=FC.PAISES.find(x=>[x[1],x[2],x[3]].some(n=>norm(n)===k)||k.startsWith(norm(x[1])));return p?p[0]:'';};
const paisUE=v=>{const k=norm(v);const p=FC.PAISES_UE.find(x=>norm(x[1])===k||k.includes(norm(x[1])));return p?p[0]:'';};

/* dirección escrita en una línea -> dirección de la ficha (se marca para revisar) */
const VIA=[[/^(c\/|c\.|cl\.?|calle|carrer|kalea)\s*/i,'Calle'],[/^(av\.?|avda\.?|avenida|avinguda|avgda\.?|venguda)\s*/i,'Avenida'],[/^(pl\.?|pza\.?|plaza|plaça|placa)\s*/i,'Plaza'],[/^(p[ºo°]\.?|pg\.?|paseo|passeig)\s*/i,'Paseo'],[/^(ctra\.?|carretera|carr\.)\s*/i,'Carretera'],[/^(cno\.?|camino|cami)\s*/i,'Camino'],[/^(rda\.?|ronda)\s*/i,'Ronda'],[/^(trav\.?|travesia|travesía)\s*/i,'Travesía'],[/^(glorieta)\s*/i,'Glorieta'],[/^(urb\.?|urbanizaci[oó]n)\s*/i,'Urbanización'],[/^(pol\.?|pol[ií]gono)\s*/i,'Polígono']];
FC.plaDir=(texto,extra)=>{extra=extra||{};let s=limpio(texto).replace(/\n/g,', ').replace(/[.\s]+$/,'');const D=FC.newDir();if(!s&&!extra.cp&&!extra.mun)return null;
 const cp=(/\b(\d{5})\b/.exec(s)||[])[1]||(/^\d{5}$/.test(String(extra.cp||'').trim())?String(extra.cp).trim():'');if(cp)s=s.replace(cp,' ');
 for(const [re,v] of VIA)if(re.test(s)){D.via=v;s=s.replace(re,'');break;}
 const take=(re)=>{const m=re.exec(s);if(!m)return '';s=s.slice(0,m.index)+(/^\s*,/.test(m[0])?', ':' ')+s.slice(m.index+m[0].length);return m[1];};
 D.puerta=take(/,?\s*\b(?:puerta|pta\.?|pt\.?)\s*([\w\d]+)/i);D.piso=take(/,?\s*\b(?:piso|planta|p\.)\s*([\w\dºª]+)/i);if(!D.piso){const m=/,?\s*\b(\d{1,2})\s*[ºª°]\s*(?:([a-z]|\d{1,2})(?![a-z0-9]))?/i.exec(s);if(m){D.piso=m[1];if(m[2]&&!D.puerta)D.puerta=m[2].toUpperCase();s=s.slice(0,m.index)+(/^\s*,/.test(m[0])?', ':' ')+s.slice(m.index+m[0].length);}}
 D.esc=take(/,?\s*\b(?:escalera|esc\.?)\s*([\w\d]+)/i);D.bloque=take(/,?\s*\b(?:bloque|blq\.?)\s*([\w\d]+)/i);
 D.num=take(/,?\s*\b(?:n[ºo°]\.?|n\.|num\.?|número|numero)\s*(\d+\s*[a-z]?)\b/i)||take(/,\s*(\d+\s*[a-z]?)\b/i)||take(/\s(\d+[a-z]?)\b(?=\s*(,|$))/i);
 const partes=s.split(',').map(x=>x.replace(/\s+/g,' ').trim()).filter(Boolean);D.calle=tc(partes.shift()||'');
 if(cp){D.cp=cp;FC.cpAplicar(D,cp);}
 const provTxt=extra.prov||'';if(!D.prov&&provTxt){const k=norm(provTxt);const f=FC.provList().find(([,n])=>norm(n)===k||norm(n).includes(k)||k.includes(norm(n)));if(f)D.prov=f[0];}
 if(!D.prov)for(let i=0;i<partes.length;i++){const k=norm(partes[i]);const f=FC.provList().find(([,n])=>k===norm(n)||k.endsWith(' '+norm(n)));if(f){D.prov=f[0];partes[i]=partes[i].slice(0,partes[i].length-f[1].length).replace(/[\s,]+$/,'');if(!partes[i])partes.splice(i,1);break;}}
 const munTxt=[extra.mun,...partes].filter(Boolean);if(D.prov&&!D.codm)for(const x of munTxt){const m=FC.munSearch(D.prov,String(x))[0];if(m){D.codm=m.codm;D.munq=m.name;break;}}
 if(!D.codm&&!D.munq&&munTxt.length)D.munq=tc(String(munTxt[munTxt.length>1&&!extra.mun?munTxt.length-1:0]));
 return FC.dirVacia(D)?null:D;};

/* ---------------- 1. leer el Word ---------------- */
FC.plaLeer=xml=>{const doc=new DOMParser().parseFromString(xml,'application/xml');const body=doc.getElementsByTagNameNS(W,'body')[0];const P={t:[],p:[]};if(!body)return P;
 const txt=n=>{let s='';const w=x=>{for(const ch of x.childNodes){if(ch.namespaceURI!==W)continue;const t=ch.localName;if(t==='t')s+=ch.textContent;else if(t==='tab')s+=' ';else if(t==='br'||t==='cr')s+='\n';else if(t==='instrText'||t==='delText')continue;else w(ch);}};w(n);return s;};
 const estilo=p=>{const s=p.getElementsByTagNameNS(W,'pStyle')[0];return s?s.getAttributeNS(W,'val'):'';};
 const cel=tc=>[...tc.childNodes].filter(x=>x.namespaceURI===W&&x.localName==='p').map(x=>txt(x).trim()).filter(Boolean).join('\n');
 let h1='',h2='';const walk=n=>{for(const ch of n.childNodes){if(ch.namespaceURI!==W)continue;
  if(ch.localName==='p'){const st=estilo(ch),t=limpio(txt(ch));if(!t)continue;if(/^(t[ií]?tulo|ttulo|heading)\s?1$/i.test(st)){h1=t;h2='';continue;}if(/^(t[ií]?tulo|ttulo|heading)\s?2$/i.test(st)){h2=t;continue;}if(/^(tdc|toc)/i.test(st))continue;P.p.push({h1,h2,t});}
  else if(ch.localName==='tbl'){P.t.push({h1,h2,rows:[...ch.childNodes].filter(x=>x.localName==='tr').map(tr=>[...tr.childNodes].filter(x=>x.localName==='tc').map(cel))});}
  else if(ch.localName==='sdt'||ch.localName==='sdtContent')walk(ch);}};
 walk(body);return P;};
FC.plaEs=P=>P.p.some(x=>/ficha de entrevista inicial/i.test(x.t))&&P.t.some(T=>T.rows.some(r=>norm(r[0])==='pregunta'&&norm(r[1])==='respuesta'));
const sec=h=>{const m=/^\s*(\d+)\s*\./.exec(h||'');return m?+m[1]:/datos de la entrevista/i.test(h||'')?99:0;};
const mapa=T=>{const M={};T.rows.forEach(r=>{for(let i=0;i+1<r.length;i+=2){const k=norm(r[i]);if(k&&k!=='pregunta'&&!(k in M))M[k]=limpio(r[i+1]);}});return M;};
const de=(M,preg)=>{const k=norm(preg);for(const x in M)if(x.startsWith(k))return M[x];for(const x in M)if(x.includes(k))return M[x];return '';};

/* ---------------- 2. pasar las respuestas a la ficha ---------------- */
FC.plaAplicar=(st,P)=>{const c=st.c,B=FC.esB&&FC.esB(c);const R={ok:[],falta:[],rev:[],aviso:[]};const obs=[];
 const put=(path,v,label)=>{if(!has(v)){R.falta.push(label);return false;}if(has(FC.getP(c,path)))return false;FC.setP(c,path,v);R.ok.push(label);return true;};
 const putSi=(path,v,label)=>{if(has(v))put(path,v,label);};
 const tablas=(n,h2)=>P.t.filter(T=>sec(T.h1)===n&&(h2==null||norm(T.h2).startsWith(norm(h2))));
 const Q=(n,h2,preg)=>{for(const T of tablas(n,h2)){const v=de(mapa(T),preg);if(v)return v;}return '';};
 const nota=(path,t)=>{if(t)c.nota[path]=(c.nota[path]?c.nota[path]+'\n':'')+'De la plantilla: '+t;};
 /* 1. datos del cliente (tabla de 4 columnas) */
 const C1=tablas(1)[0]?mapa(tablas(1)[0]):{};const cl='Cliente: ';
 {const [n,a]=partir(de(C1,'nombre completo'));if(put('cli.nombre',n,cl+'nombre')&&a.split(' ').length+n.split(' ').length>2)R.rev.push(cl+'reparto entre nombre y apellidos');put('cli.apellidos',a,cl+'apellidos');}
 put('cli.email',de(C1,'correo').replace(/\s/g,''),cl+'correo electrónico');
 const nd=de(C1,'nif').toUpperCase().replace(/\s/g,'');const tipoDoc=docTipo(Q(4,'Regular / Irregular','qué documentación'),nd)||docTipo('',nd);
 put('cli.doc',tipoDoc==='CIF'?'':tipoDoc,cl+'documento');put('cli.docnum',nd,cl+'número de documento');
 put('cli.nac',fecha(de(C1,'fecha de nacimiento')),cl+'fecha de nacimiento');
 {const t=de(C1,'telefono').replace(/[^\d+]/g,'');if(t&&!c.cli.tel){c.cli.telPref='ES';c.cli.tel=t.replace(/^(\+|00)34/,'');R.ok.push(cl+'teléfono');}else if(!t)R.falta.push(cl+'teléfono');const t2=de(C1,'telefono 2');if(t2)nota('cli.tel','teléfono 2: '+t2);}
 {const vive=Q(4,'Domicilio','dirección donde vive');const D=FC.plaDir(de(C1,'direccion')||vive,{cp:de(C1,'codigo postal'),mun:de(C1,'poblacion'),prov:de(C1,'provincia')});if(D&&FC.dirVacia(c.cli.dom)){c.cli.dom=D;R.ok.push(cl+'dirección donde vive');R.rev.push(cl+'dirección (leída de una línea de texto)');}else if(!D)R.falta.push(cl+'dirección donde vive');}
 /* 3. tratamiento */
 {const t2=norm(Q(3,null,'el cliente'))+' '+norm(Q(3,null,'el trabajador'));const tr=trato(Q(3,null,'d d'))||(/^la\b/.test(t2)?'da':/^el\b/.test(t2)?'d':'');put('cli.trato',tr,cl+'D. o D.ª');}
 /* 4. información del cliente */
 {const pa=Q(4,'Regular / Irregular','nacionalidad');put('cli.pais',pais(pa),cl+'nacionalidad');if(pa&&!pais(pa))R.rev.push(cl+'nacionalidad «'+pa+'» no reconocida');
  const ue=Q(4,'Regular / Irregular','país (ue)');if(ue)putSi('cli.emisorPais',paisUE(ue),cl+'país que expidió el NIE');const pp=Q(4,'Regular / Irregular','país que expidió el pasaporte');if(pp)putSi('cli.emisorPais',pais(pp),cl+'país que expidió el pasaporte');
  const pap=Q(4,'Regular / Irregular','¿tiene papeles');if(pap)obs.push('¿Tiene papeles?: '+pap);const cad=Q(4,'Regular / Irregular','caducidad');if(cad)nota('cli.docnum','caducidad del NIE: '+cad);
  put('cli.empadronada',siNo(Q(4,'Domicilio','¿está empadronad')),cl+'¿está empadronado/a?');
  const pd=Q(4,'Domicilio','dirección del padrón');if(pd&&/^(la misma|el mismo|misma|igual)/.test(norm(pd))&&!FC.dirVacia(c.cli.dom)&&FC.dirVacia(c.cli.padronDir)){c.cli.padronDir=JSON.parse(JSON.stringify(c.cli.dom));R.ok.push(cl+'dirección del padrón (la misma)');}else if(pd){const D=FC.plaDir(pd);if(D&&FC.dirVacia(c.cli.padronDir)){c.cli.padronDir=D;R.ok.push(cl+'dirección del padrón');R.rev.push(cl+'dirección del padrón');}}
  const po=Q(4,'Domicilio','dirección postal');if(po&&!c.cli.postalIgual&&/^(la misma|el mismo|misma|igual|idem|la de arriba)/.test(norm(po))){c.cli.postalIgual='si';R.ok.push(cl+'dirección postal (la misma)');}else if(po&&!c.cli.postalIgual){const D=FC.plaDir(po);if(D){c.cli.postalIgual='no';c.cli.postal=D;R.ok.push(cl+'dirección postal');R.rev.push(cl+'dirección postal');}}
  const ec=Q(4,'Otros','estado civil');if(ec)obs.push('Estado civil: '+ec);const dep=Q(4,'Otros','¿personas que dependan');if(dep)obs.push('Personas que dependen de él/ella: '+dep);
  put('cli.sindical',siNo(Q(4,'Otros','en el último año')),cl+'cargo sindical');}
 /* 2. antes de empezar */
 {const f='Filtro: ';const ab=Q(2,'Trámites previos','¿otro abogado');put('filtro.abogado',/cambiar/.test(norm(ab))?'cambiar':siNo(ab),f+'¿otro abogado lleva el caso?');
  const ac=norm(Q(2,'Trámites previos','¿ya se presentó'));put('filtro.actuado',!ac?'':/ambas|las dos|ambos/.test(ac)?'ambas':/papeleta/.test(ac)?'papeleta':/demanda/.test(ac)?'demanda':/^no|ningun/.test(ac)?'ninguna':'',f+'¿ya se presentó papeleta o demanda?');
  putSi('filtro.papFecha',fecha(Q(2,'Trámites previos','si ya presentó una papeleta')),f+'fecha de la papeleta');putSi('filtro.demFecha',fecha(Q(2,'Trámites previos','si ya presentó una demanda')),f+'fecha de la demanda');
  put('filtro.estudiar',siNo(Q(2,'Motivos de la consulta','¿quiere que el despacho')),f+'¿quiere que estudiemos el caso?');
  const pq=Q(2,'Motivos de la consulta','¿por qué viene'),k=norm(pq);const rc=[];if(/despid|desped|echar/.test(k))rc.push('despido');if(/salari|diferenc|deben|deuda|cantidad|sueldo/.test(k))rc.push('salarios');if(/vacacion/.test(k))rc.push('vacaciones');if(/horas/.test(k))rc.push('horas');if(/\balta\b|seguridad social/.test(k))rc.push('alta');if(/finiquito/.test(k))rc.push('finiquito');if(k&&!rc.length)rc.push('otro');
  put('filtro.reclamar',rc,f+'qué quiere reclamar');put('filtro.motivo',Q(2,'Motivos de la consulta','con sus palabras')||pq,f+'qué le gustaría conseguir');
  const co=norm(Q(2,'Otros','¿cómo nos conoció'));const cn=[];[['tiktok',/tik ?tok/],['facebook',/facebook/],['instagram',/instagram/],['vozavoz',/boca|voz a voz/],['amiga',/amig|famil|conocid/],['excliente',/exclient|cliente/],['despacho',/despacho|pas[oó] por/]].forEach(([v,re])=>{if(re.test(co))cn.push(v);});if(co&&!cn.length){cn.push('otro');putSi('filtro.conocioOtro',Q(2,'Otros','¿cómo nos conoció'),'');}
  put('filtro.conocio',cn,f+'cómo nos conoció');put('filtro.hechaPor',Q(2,'Otros','ficha hecha por')||Q(99,null,'entrevista realizada por'),f+'ficha hecha por');}
 /* 6. fechas, permiso y alta */
 const ini=fecha(Q(6,'Vida laboral','¿cuándo empezó')),finT=fecha(Q(6,'Vida laboral','¿cuándo terminó'))||fecha(Q(13,'Lo que dice el cliente','¿qué día terminó'));
 put('rel.inicio',ini,'Relación: fecha de inicio');if(finT){putSi('rel.fin',finT,'Relación: fecha de fin');}
 {const s=norm(Q(6,'Permiso de trabajo','situación'));const ag=!s?'':/parte|solo una|algun/.test(s)?'parte':/siempre|todo/.test(s)?'siempre':/nunca|^no/.test(s)?'nunca':'';put('rel.autGlobal',ag,'Relación: ¿autorización de trabajo?');
  const pd=fecha(Q(6,'Permiso de trabajo','permiso desde')),ph=fecha(Q(6,'Permiso de trabajo','permiso hasta')),pt=Q(6,'Permiso de trabajo','tipo de permiso');
  if(!c.autorizacion.length&&c.rel.autGlobal==='parte'&&pd){if(c.rel.inicio&&c.rel.inicio<pd)c.autorizacion.push(Object.assign(FC.T.autorizacion(c),{tipo:'sin',desde:c.rel.inicio,hasta:SF.addDays(pd,-1)}));c.autorizacion.push(Object.assign(FC.T.autorizacion(c),{tipo:'con',desde:pd,hasta:ph,permiso:pt}));R.ok.push('Relación: periodos con y sin autorización');}
  else if(pt)obs.push('Tipo de permiso: '+pt+(pd?` (desde ${pd}${ph?' hasta '+ph:''})`:''));}
 /* 5. empleadores / partes contrarias */
 const CON=tablas(5).filter(T=>/contrario/i.test(T.h2)).map(mapa).filter(M=>Object.values(M).some(Boolean));const per=[];
 CON.forEach((M,i)=>{const nom=de(M,'nombre completo'),nd2=de(M,'n º de identidad')||de(M,'n de identidad')||de(M,'nº de identidad');const roles=norm(de(M,'marque todo')+' '+de(M,'relación laboral'));
  const [d1,d2]=fechas(de(M,'¿desde y hasta'));const dir=FC.plaDir(de(M,'dirección de notificación'));
  const emp=esEmpresa(nom,nd2)||/empresa|sociedad|mercantil/.test(norm(de(M,'documentación')+' '+de(M,'¿qué es del cliente')));
  const m={};if(/contrat/.test(roles))m.contrato=true;if(/pag/.test(roles))m.pago=true;if(/orden|mand|jefe/.test(roles))m.ordenes=true;if(/despid|desped/.test(roles))m.despidio=true;if(/titular/.test(roles))m.titular=true;if(/vive|vivia|casa/.test(roles))m.vive=true;if(/visit/.test(roles))m.visita=true;
  per.push({i,M,nom,nd2,emp,m,d1,d2,dir,roles,trato:trato(de(M,'d d')),cuidada:/cuid|atend/.test(roles),testigo:/testig|compañer/.test(roles)});});
 const mkP=x=>{const p=FC.T.personas(c);const [n,a]=partir(x.nom);Object.assign(p,{trato:x.trato||'',nombre:n,apellidos:a,papel:de(x.M,'¿qué es del cliente'),edad:num(de(x.M,'edad')),tel:de(x.M,'teléfono').replace(/[^\d+]/g,''),email:de(x.M,'email').replace(/\s/g,''),m:x.m});
  const dt=docTipo(de(x.M,'documentación'),x.nd2);if(dt&&dt!=='CIF'&&dt!=='ninguno')p.docTipo=dt;p.docNum=String(x.nd2||'').trim();if(x.dir)p.dom=x.dir;if(x.d1)p.empDesde=x.d1;if(x.d2)p.empHasta=x.d2;c.personas.push(p);x.p=p;if(n&&(a||'').split(' ').length+n.split(' ').length>2)R.rev.push(`Contrario ${x.i+1}: reparto entre nombre y apellidos`);if(x.dir)R.rev.push(`Contrario ${x.i+1}: dirección (leída de una línea de texto)`);return p;};
 if(!c.empleadores.length&&per.length){
  const gente=per.filter(x=>!x.emp),empresas=per.filter(x=>x.emp);
  if(B&&empresas.length){const ps=gente.filter(x=>!x.testigo).map(mkP);gente.filter(x=>x.testigo).forEach(mkP);
   empresas.forEach((x,k)=>{const e=FC.T.empleadores(c);Object.assign(e,{tipoEmp:'juridica',razon:limpio(x.nom),cif:String(x.nd2||'').toUpperCase().replace(/\s/g,''),desde:x.d1||c.rel.inicio||'',hasta:x.d2||c.rel.fin||''});if(x.dir)e.dom=x.dir;if(k===0&&ps[0]){e.titular=ps[0].id;e.otros=ps.slice(1).map(p=>p.id);}c.empleadores.push(e);});}
  else{const cand=gente.filter(x=>!x.testigo&&(!x.cuidada||x.m.titular||x.m.contrato||x.m.pago||x.m.ordenes||x.m.despidio));empresas.forEach(x=>obs.push(`Contrario ${x.i+1} (empresa): ${x.nom}${x.nd2?' · '+x.nd2:''}`));
   gente.forEach(mkP);const tit=cand.find(x=>x.m.titular)||cand.find(x=>x.m.contrato||x.m.pago)||cand[0];
   if(tit){const e=FC.T.empleadores(c);e.titular=tit.p.id;tit.p.m.titular=true;e.otros=cand.filter(x=>x!==tit).map(x=>x.p.id);e.desde=tit.d1||c.rel.inicio||'';e.hasta=tit.d2||c.rel.fin||'';if(tit.dir)e.dom=JSON.parse(JSON.stringify(tit.dir));
    if(B){e.tipoEmp='fisica';e.cif=String(tit.nd2||'').toUpperCase().replace(/\s/g,'');}c.empleadores.push(e);}
   gente.filter(x=>x.cuidada).forEach(x=>{if(!B){const k=FC.T.cuidados(c);k.persona=x.p.id;c.cuidados.push(k);}});}
  R.ok.push(`Empleadores y partes contrarias (${per.length})`);}
 else if(!per.length&&!c.empleadores.length)R.falta.push('Empleadores: nombre y datos');
 const quien=t=>{const k=norm(t);if(!k)return [];return c.personas.filter(p=>{const n=norm(p.nombre).split(' ')[0];return n&&k.includes(n);}).map(p=>p.id);};
 const titulares=()=>c.empleadores.map(e=>e.titular).filter(Boolean);
 /* alta */
 {const al=siNo(Q(6,'Alta en la Seguridad Social','¿le dieron de alta'));put('rel.alta',al,'Relación: ¿alta en la Seguridad Social?');
  const fa=fecha(Q(6,'Alta en la Seguridad Social','fecha de alta')),fb=fecha(Q(6,'Alta en la Seguridad Social','fecha de baja'));
  if(al==='si'&&!c.altas.length){if(fa){const ids=quien(Q(6,'Alta en la Seguridad Social','¿qué empleador'));const fu=norm(Q(6,'Alta en la Seguridad Social','datos sacados'));c.altas.push(Object.assign(FC.T.altas(c),{alta:fa,baja:fb,emps:ids.length?ids:titulares().slice(0,1),fuente:/vida/.test(fu)?'vida':fu?'cliente':''}));R.ok.push('Relación: fechas de alta');}else R.falta.push('Relación: fechas de alta');}}
 /* 7. lugares de trabajo */
 {const L=tablas(7).filter(T=>/centro/i.test(T.h2)).map(mapa).filter(M=>de(M,'dirección'));
  if(!c.lugares.length&&L.length){L.forEach((M,i)=>{const D=FC.plaDir(de(M,'dirección'));if(!D)return;const l=FC.T.lugares(c);l.dir=D;const [a,b]=fechas(de(M,'¿desde cuándo'));l.desde=a||c.rel.inicio||'';l.hasta=b||c.rel.fin||'';const ids=quien(de(M,'¿qué empleadores'));l.quienes=ids.length?ids:titulares();c.lugares.push(l);
    const h=de(M,'¿qué horario');if(h)nota(`lugares.${c.lugares.length-1}.dir`,'horario en este lugar: '+h);R.rev.push(`Centro de trabajo ${i+1}: dirección (leída de una línea de texto)`);});if(c.lugares.length)R.ok.push(`Lugares de trabajo (${c.lugares.length})`);}
  else if(!c.lugares.length){const e=c.empleadores[0];if(e&&!FC.dirVacia(e.dom)&&!B){R.falta.push('Lugar de trabajo: dirección (puede ser la misma que la del empleador)');}else R.falta.push('Lugar de trabajo: dirección');}}
 /* 8. información contractual */
 const cm=norm(Q(8,'Contratación','indique la modalidad'));put('rel.contrato',/escrit/.test(cm)?'escrito':/verbal|sin contrato|^no/.test(cm)?'verbal':'','Relación: ¿contrato por escrito?');
 {const fi=Q(8,'Contratación','fecha de inicio contractual');if(fi)obs.push('Fecha de inicio del contrato: '+fi);const pr=Q(8,'Contratación','¿cumplió el periodo');if(pr)obs.push('¿Cumplió el periodo de prueba?: '+pr);}
 const oficio=Q(8,'Funciones pactadas','¿de qué trabaja'),funciones=Q(8,'Funciones pactadas','explique qué funciones');
 if(B){put('puesto.categoria',tc(Q(8,'Convenio colectivo','grupo profesional')||oficio),'Puesto: categoría');put('puesto.funciones',funciones,'Puesto: funciones');}
 else{const k=norm(oficio+' '+funciones);const T=[];[['limpiar_casa',/limpi|barr|freg|aseo/],['limpiar_banos',/bano/],['limpiar_cocina',/cocina/],['lavar',/lav/],['planchar',/planch/],['cocinar',/cocin|comida/],['compras',/compra/],['ninos',/nin|menor|bebe|guarderia|colegio/],['mayores',/mayor|abuel|ancian/],['dependientes',/dependien|discapac|silla de ruedas|encamad/],['citas',/medic|cita/],['mascotas',/mascota|perro|gato/],['pasear',/pase/]].forEach(([v,re])=>{if(re.test(k))T.push(v);});
  put('tareas',T,'Tareas: qué tareas hacía');if(funciones)putSi('tareasOtras',funciones,'Tareas: explicación');}
 {const hogar=/hogar|domestic|intern|cuidad|limpieza de (la )?casa|niñer|nin(o|a)s|mayores/.test(norm(oficio+' '+funciones));if(!B&&oficio&&!hogar)R.aviso.push(`«${oficio}» no parece empleo de hogar: si es régimen general, use la ficha B.`);if(B&&hogar)R.aviso.push(`«${oficio||funciones}» parece empleo de hogar: si lo es, use la ficha C.`);}
 const jp=Q(8,'Jornada pactada','explique la jornada');if(B){const h=/(\d+(?:[.,]\d+)?)\s*h(?:oras)?\s*(semanal|a la semana|por semana)/.exec(norm(jp));if(h)putSi('rel.horasContrato',h[1].replace(',','.'),'Contrato: horas semanales');}
 /* 9. jornada (tabla por días; si está vacía, se lee el texto de la jornada pactada) */
 {const T=tablas(9,'Tabla de jornada')[0]||tablas(9).find(T=>T.rows.some(r=>norm(r[0])==='lunes'));const filas=[];
  if(T)T.rows.forEach(r=>{const d=DIAS.indexOf(norm(r[0]));if(d<0)return;const e=hora(r[2]),s=hora(r[3]);if(e&&s)filas.push({d,e,s,m:minutos(r[4])});});
  let leida='';if(!filas.length&&jp){const k=norm(jp);let ds=[];const rg=/(lunes|martes|miercoles|jueves|viernes|sabado|domingo)s? (?:a|al|hasta) (?:el )?(lunes|martes|miercoles|jueves|viernes|sabado|domingo)/.exec(k);
   if(rg){let a=DIAS.indexOf(rg[1]),b=DIAS.indexOf(rg[2]);for(let x=a;;x=(x+1)%7){ds.push(x);if(x===b)break;}}else DIAS.forEach((n,x)=>{if(new RegExp('\\b'+n).test(k))ds.push(x);});
   const hh=[...String(jp).matchAll(/(\d{1,2}(?:[:.h]\d{2})?)\s*(?:h|horas)?\s*(?:a|-|–|hasta)\s*(?:las\s*)?(\d{1,2}(?:[:.h]\d{2})?)/gi)].map(m=>[hora(m[1]),hora(m[2])]).filter(x=>x[0]&&x[1]);
   if(ds.length&&hh.length){let m='';const dm=/(\d+\s*min\w*|media hora|una hora|dos horas|tres horas|\d+(?:[.,]\d+)?\s*horas?)\s*(?:de|para)?\s*(?:descanso|almuerzo|comida|comer)|(?:descanso|almuerzo|comida|comer)\w*\s*(?:de)?\s*(\d+\s*min\w*|media hora|una hora|dos horas|\d+(?:[.,]\d+)?\s*horas?)|con (una hora|media hora|\d+\s*min\w*)/.exec(k);if(dm)m=minutos(dm[1]||dm[2]||dm[3]);
    if(hh.length>=2){const toM=h=>+h.slice(0,2)*60+ +h.slice(3);const gap=toM(hh[1][0])-toM(hh[0][1]);if(gap>0)m=String(gap);hh.splice(0,2,[hh[0][0],hh[1][1]]);}
    ds.forEach(d=>filas.push({d,e:hh[0][0],s:hh[0][1],m}));leida='texto';}}
  if(filas.length&&!c.periodos.length){const Pj=FC.T.periodos(c);Pj.desde=c.rel.inicio||'';Pj.hasta=c.rel.fin||'';if(c.lugares[0])Pj.lugar=c.lugares[0].id;const all=norm(jp+' '+oficio+' '+funciones+' '+Q(9,'Comentarios','¿tiene varios'));Pj.modalidad=/\binterna\b/.test(all)?'interna':/\bexterna\b/.test(all)?'externa':/por horas/.test(all)?'horas':'';
   const g={};filas.forEach(f=>{const k=f.e+'|'+f.s+'|'+f.m;(g[k]=g[k]||[]).push(f.d);});Object.entries(g).forEach(([k,ds])=>{const [e,s,m]=k.split('|');const u=FC.newTurno(c,ds.sort());u.e=e;u.s=s;u.descMin=m;Pj.semanas[0].turnos.push(u);});c.periodos.push(Pj);
   R.ok.push('Jornada: horario'+(leida?' (leído del texto de la jornada pactada)':''));if(leida)R.rev.push('Jornada: horario leído del texto «'+jp.replace(/\s+/g,' ')+'»');if(!B){if(Pj.modalidad)R.ok.push('Jornada: interna o externa');else R.falta.push('Jornada: interna o externa');}}
  else if(!c.periodos.length)R.falta.push('Jornada: horario (entrada, salida y días)');
  if(jp)nota('periodos','jornada pactada: '+jp.replace(/\s+/g,' '));const cm2=Q(9,'Comentarios','¿tiene varios');if(cm2)obs.push('Turnos y horas extra: '+cm2);}
 /* 10. lo percibido */
 {const T=tablas(10).find(T=>T.rows.some(r=>norm(r[0])==='mes'));const M=[];
  if(T)T.rows.forEach(r=>{const k=norm(r[0]);let mi=MESES.indexOf(k);if(mi<0&&/^\d{1,2}$/.test(k))mi=+k-1;const y=num(r[1]),v=num(r[2]);if(mi>=0&&mi<12&&/^\d{4}$/.test(y)&&v)M.push({mes:`${y}-${String(mi+1).padStart(2,'0')}`,v,neto:/x|si/i.test(r[3]||'')});});
  const igual=siNo(Q(10,'Comentarios','explicar si siempre'));const sc=num(Q(8,'Salario pactado','salario contractual'));
  if(M.length&&!c.meses.length){const vs=new Set(M.map(x=>x.v));if(vs.size===1&&igual!=='no'){put('sal.fijo','si','Salario: ¿siempre la misma cantidad?');put('sal.importe',M[0].v,'Salario: importe mensual');}
    else{put('sal.fijo','no','Salario: ¿siempre la misma cantidad?');M.forEach(x=>c.meses.push(Object.assign(FC.T.meses(c),{mes:x.mes,salario:x.v,obs:x.neto?'importe neto':''})));R.ok.push(`Salario mes a mes (${M.length} meses)`);}
    if(M.some(x=>x.neto))R.rev.push('Lo percibido: hay importes marcados como netos');}
  else if(!M.length){if(igual)put('sal.fijo',igual,'Salario: ¿siempre la misma cantidad?');if(sc&&igual!=='no'){if(put('sal.importe',sc,'Salario: importe mensual'))R.rev.push('Salario: se ha tomado el salario del contrato como lo que cobraba');}else R.falta.push('Salario: lo que cobraba cada mes');}
  const ex=Q(10,'Comentarios','explicar si siempre');if(ex)nota('sal.fijo',ex);
  const tr=norm(Q(8,'Salario pactado','tipo de retribución'));if(tr)putSi('sal.porHoras',/hora/.test(tr)?'si':'no','Salario: ¿por horas?');
  const ma=Q(10,'Mes de alta','explicar cómo');if(ma){if(c.altas[0]){c.altas[0].pagoMesObs=c.altas[0].pagoMesObs||ma;const v=importes(ma);if(v[0]&&!c.altas[0].pagoNeto)c.altas[0].pagoNeto=v[0];}else obs.push('Mes del alta: '+ma);R.rev.push('Pago del mes del alta: completar fechas y forma de pago');}
  const fq=Q(10,'Finiquito','explicar cuánto');if(fq){const k=norm(fq);if(/^(nada|no\b|ninguno|0\b)/.test(k)||/no le (pagaron|dieron)/.test(k))put('sal.ultimoMes','no','Salarios: ¿le pagaron algo el último mes?');else{const v=importes(fq)[0]||num(fq);put('sal.ultimoMes','si','Salarios: ¿le pagaron algo el último mes?');if(v)putSi('sal.ultimoMesImporte',v,'Último mes: importe');}nota('sal.ultimoMes',fq);R.rev.push('Finiquito: repartir el importe por conceptos si hace falta');}
  else if(c.rel.fin)R.falta.push('Salarios: ¿le pagaron algo el último mes?');}
 /* 12. pagas extra */
 {const pr=siNo(Q(12,null,'¿están prorrateadas'))||siNo(Q(8,'Salario pactado','¿hay prorrateo')),rec=siNo(Q(12,null,'¿recibió alguna'));const np=num(Q(8,'Pagas','¿cuántas pagas'));
  if(pr==='si'){put('sal.pagas','si','Salario: pagas extra');putSi('sal.pagasTxt','prorrateadas en el salario'+(np?` (${np} pagas)`:''),'');}else if(rec){put('sal.pagas',rec,'Salario: pagas extra');if(np)putSi('sal.pagasTxt',np+' pagas al año','');}else R.falta.push('Salario: pagas extra');}
 /* 11. vacaciones, bajas y permisos */
 {const t=siNo(Q(11,'Vacaciones','¿disfrutó'));put('vac.tuvo',t,'Vacaciones: ¿tuvo vacaciones?');const dv=Q(11,'Vacaciones','introduzca los días');const F=fechas(dv);
  if(t==='si'&&!c.vacaciones.length&&F.length>=2){for(let i=0;i+1<F.length;i+=2)c.vacaciones.push(Object.assign(FC.T.vacaciones(c),{desde:F[i],hasta:F[i+1],pagadas:'si',disfruto:'si'}));R.ok.push(`Vacaciones: periodos (${c.vacaciones.length})`);R.rev.push('Vacaciones: comprobar si cada periodo se pagó');}
  else if(dv)obs.push('Vacaciones disfrutadas: '+dv);const pn=Q(11,'Vacaciones','¿le pagaron por no disfrutar');if(pn&&!/^no\b/.test(norm(pn)))obs.push('Vacaciones pagadas sin disfrutar: '+pn);
  const bj=siNo(Q(11,'Bajas','¿estuvo de baja'));if(bj==='si')obs.push('Bajas en el último año: '+[Q(11,'Bajas','¿qué tipo'),Q(11,'Bajas','introduzca las fechas')].filter(Boolean).join(' · '));
  const pe=siNo(Q(11,'Permisos retribuidos','¿en el último año'));if(pe==='si')obs.push('Permisos retribuidos: '+(Q(11,'Permisos retribuidos','introduzca las fechas')||'sí'));}
 /* 13. fin de la relación */
 {const qp=Q(13,'Lo que dice el cliente','¿qué pasó'),k=norm(qp);const tipo=!k?'':/falleci|muri/.test(k)?'fallecimiento':/renunci|dimit|baja voluntaria|me fui|se fue/.test(k)?'renuncia':/despid|desped|echar|ech[oó]/.test(k)?'despido':/sigue|continu|todavia/.test(k)?'continua':'otro';
  const tipo2=tipo||(Q(13,'Renuncia','¿cómo renunció')?'renuncia':Q(13,'Por fallecimiento','¿quién falleció')?'fallecimiento':Q(13,'Despido','¿cómo le comunicaron')?'despido':'');
  put('fin.tipo',tipo2,'Fin: qué pasó con su trabajo');if(tipo2!=='continua')put('fin.fechaFin',finT,'Fin: qué día dejó de trabajar');
  if(tipo2==='despido'){const qn=Q(13,'Despido','¿quién decidió');const ids=quien(qn);if(ids.length)put('fin.quien',ids,'Despido: quién lo decidió');else if(qn)nota('fin.quien',qn);
   const md=norm(Q(13,'Despido','¿cómo le comunicaron'));put('fin.medio',!md?'':/whats|wasap|wsp/.test(md)?'whatsapp':/carta/.test(md)?'carta':/burofax/.test(md)?'burofax':/correo|email|mail/.test(md)?'email':/telef|llamad/.test(md)?'telefono':/verbal|palabra|persona|dijo/.test(md)?'verbal':'otro','Despido: cómo se lo comunicaron');
   put('fin.fechaCom',fecha(Q(13,'Despido','¿qué día le comunicaron'))||finT,'Despido: qué día se lo comunicaron');put('fin.dicho',Q(13,'Despido','¿qué le dijeron'),'Despido: qué le dijeron');put('fin.motivo',siNo(Q(13,'Despido','¿le explicaron')),'Despido: ¿le explicaron un motivo?');}
  if(tipo2==='renuncia'){const rm=norm(Q(13,'Renuncia','¿cómo renunció'));put('fin.renMedio',/escrit|carta|burofax|correo|email/.test(rm)?'escrito':rm?'verbal':'','Renuncia: cómo renunció');put('fin.renMotivo',Q(13,'Renuncia','¿por qué renunció'),'Renuncia: por qué');putSi('fin.fechaCom',finT,'');}
  if(tipo2==='fallecimiento'){const ids=quien(Q(13,'Por fallecimiento','¿quién falleció'));putSi('fin.fallQuien',ids[0]||'','Fallecimiento: quién');put('fin.fallFecha',fecha(Q(13,'Por fallecimiento','fecha del fallecimiento')),'Fallecimiento: fecha');}
  const ds=Q(13,'Despido','describa');if(ds)put('fin.dia',ds,'Fin: qué pasó ese día');else if(qp)putSi('fin.dia',qp,'Fin: qué pasó');
  put('fin.docEntregado',siNo(Q(13,'Documentos recibidos','¿le entregaron')),'Fin: ¿le entregaron algún documento?');putSi('fin.pidieronFirmar',siNo(Q(13,'Documentos recibidos','¿le pidieron firmar')),'Fin: ¿le pidieron firmar?');putSi('fin.firmo',siNo(Q(13,'Documentos recibidos','¿firmó')),'Fin: ¿firmó algo?');
  const bu=siNo(Q(13,'Burofax','¿se envió'));put('fin.burofax',bu,'Burofax: ¿se envió?');if(bu==='si'){putSi('fin.burFecha',fecha(Q(13,'Burofax','fecha del burofax')),'Burofax: fecha');putSi('fin.burDest',quien(Q(13,'Burofax','¿a quién'))[0]||'','Burofax: a quién');const br=norm(Q(13,'Burofax','¿qué pasó'));putSi('fin.burRes',!br?'':/rechaz|rehus/.test(br)?'rehusado':/recog|retir/.test(br)?'noretirado':/no respond|sin respuesta|nada/.test(br)?'sinresp':/respond|contest/.test(br)?'respondio':'','Burofax: qué pasó');}}
 /* 14. cronología (texto libre: una entrada por párrafo, con su fecha si la lleva) */
 {const L=P.p.filter(x=>sec(x.h1)===14&&!/^campo de texto libre/i.test(x.t)).map(x=>x.t);if(L.length&&!c.cronologia.length){L.forEach(t=>c.cronologia.push(Object.assign(FC.T.cronologia(c),{fecha:fecha(t),desc:t})));R.ok.push(`Cronología (${L.length})`);}}
 /* convenio (ficha B): si el texto coincide con un único convenio del catálogo, se carga */
 if(B){const cv=Q(8,'Convenio colectivo','convenio colectivo'),act=Q(8,'Convenio colectivo','¿sabe a qué se dedica');if(act&&c.empleadores[0])putSi('empleadores.0.actividad',act,'Empresa: actividad');
  if(cv&&!c.conv.nombre){const L=FC.convFiltra?FC.convFiltra(cv):[];if(L.length===1&&FC.convAplicar){FC.convAplicar(c,L[0].resumen,'plantilla');R.ok.push('Convenio: '+L[0].nombre);}else{c.conv.nombre=cv;R.rev.push('Convenio: elegirlo de la lista o importarlo');}}}
 if(obs.length){c.obs=(c.obs?c.obs+'\n\n':'')+'De la plantilla (sin casilla propia):\n'+obs.join('\n');R.ok.push('Observaciones');}
 [c.cli.dom,c.cli.padronDir,...c.lugares.map(l=>l.dir),...c.empleadores.map(e=>e.dom)].forEach(d=>{if(d&&!FC.dirVacia(d))d.gmaps='';});
 R.falta=[...new Set(R.falta.filter(Boolean))];R.ok=R.ok.filter(Boolean);return R;};

/* ---------------- 3. leer el archivo y aplicar ---------------- */
FC.plaImportar=async file=>{const st=FC.st,c=st.c;if(!/\.docx$/i.test(file.name)){SF.toast('Suba la plantilla en Word .docx',1);return;}
 let xml;try{xml=await FC.docxXml(file);}catch(e){SF.toast('No se ha podido leer el Word',1);return;}
 const P=FC.plaLeer(xml||'');if(!FC.plaEs(P)){SF.toast('Este Word no es la plantilla nueva de entrevista: use «Ficha antigua» (con Claude)',1);return;}
 const R=FC.plaAplicar(st,P);c.imp={archivo:file.name,fecha:new Date().toLocaleString('es-ES'),ok:R.ok,falta:R.falta,rev:R.rev,aviso:R.aviso,modo:'plantilla'};FC.step=0;FC.render();SF.toast(`Plantilla leída: ${R.ok.length} respuestas. Revise lo marcado.`);};
document.addEventListener('change',e=>{if(e.target&&e.target.id==='fcPlaFile'&&e.target.files&&e.target.files[0]){FC.plaImportar(e.target.files[0]);e.target.value='';}});
})();
