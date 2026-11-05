(function(){
'use strict';
/* =====================================================================
   FICHA C v2 — Empleada de hogar sin papeles
   Modelo con módulos repetibles, jornada por periodos y semanas modelo,
   salarios mes a mes, vacaciones, pruebas con archivos, búsqueda
   territorial (CSV) y papeleta basada en el escrito de ejemplo.
   ===================================================================== */
const SF=window.SF,esc=SF.esc,$=id=>document.getElementById(id);
const FC=window.FC={};
const DAY=864e5;
const pd=SF.pd,iso=SF.iso,fmt=SF.fmt;
const eur=SF.eur,eurN=x=>SF.eur(x).replace(' €','');
const n2=x=>(Math.round(x*100)/100).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2});
const n1=x=>{const r=Math.round(x*10)/10;return (Number.isInteger(r)?String(r):r.toFixed(1)).replace('.',',');};
const dmy=s=>{const t=pd(s);if(t==null)return null;const d=new Date(t);return `${String(d.getUTCDate()).padStart(2,'0')}.${String(d.getUTCMonth()+1).padStart(2,'0')}.${d.getUTCFullYear()}`;};
const today=()=>FC._hoy||SF.today();
const P=t=>'⟦'+t+'⟧';
const num=x=>{if(x===''||x==null)return null;const n=Number(String(x).replace(/\./g,'').replace(',','.'));return isFinite(n)?n:null;};
const numS=x=>{if(x===''||x==null)return null;const n=Number(String(x).replace(',','.'));return isFinite(n)?n:null;};
const has=v=>!(v===undefined||v===null||v===''||v===false||(Array.isArray(v)&&!v.length));
const uid=(c,p)=>{c.seq=(c.seq||0)+1;return p+c.seq;};
const getP=(o,p)=>p.split('.').reduce((a,k)=>a==null?undefined:a[k],o);
const setP=(o,p,v)=>{const ks=p.split('.');let a=o;for(let i=0;i<ks.length-1;i++){if(a[ks[i]]==null)a[ks[i]]=/^\d+$/.test(ks[i+1])?[]:{};a=a[ks[i]];}a[ks[ks.length-1]]=v;};
const pid=p=>'f_'+p.replace(/\./g,'_');
const listY=a=>a.length>1?a.slice(0,-1).join(', ')+' y '+a[a.length-1]:(a[0]||'');
const DOWN=['lunes','martes','miércoles','jueves','viernes','sábado','domingo'];
const DOWP=['lunes','martes','miércoles','jueves','viernes','sábados','domingos'];
FC.getP=getP;FC.setP=setP;

/* ---------------- importes legales ---------------- */
FC.SMI={
 2023:{m:1080,h:null,rd:'RD 99/2023',ver:false,src:''},
 2024:{m:1134,h:8.87,rd:'RD 145/2024',ver:true,src:'https://www.laboral-social.com/publicado-real-decreto-salario-minimo-interprofesional-2024'},
 2025:{m:1184,h:9.26,rd:'RD 87/2025',ver:true,src:'https://www.cuestioneslaborales.es/cuantia-diaria-mensual-y-anual-del-smi-en-2025/'},
 2026:{m:1221,h:9.55,rd:'RD 126/2026',ver:true,src:'https://www.boe.es/eli/es/rd/2026/02/18/126/con'}
};
FC.smiP=(st,y)=>{const r=FC.SMI[y];if(!r)return null;if(!r.ver&&!((st.c.abg.smiVer||{})[y]))return null;return r.m*14/12;};

/* ---------------- configuración del despacho (sesión) ---------------- */
SF.cfg=SF.cfg||{despacho:{dom:'Calle Llobregat, nº 62, local, 08904 Hospitalet de Llobregat, Barcelona',tel:'627 58 16 04',email:'laboral.general@abogadorafaelserrano.com'},org:{}};
FC.orgOk=o=>!!(o&&o.enc1);
/* organismo de conciliación por provincia: tabla del despacho (window.ORGT); el abogado puede corregirlo para la sesión en SF.cfg.org[cpro] */
FC.orgTabla=cpro=>{const r=((window.ORGT||{}).p||{})[cpro];return r&&r.enc?{enc1:r.enc,enc2:r.secc,ccaa:r.ccaa,nombre:r.nombre,fuente:'tabla'}:null;};
FC.orgDe=cpro=>{const o=SF.cfg.org[cpro];if(o&&o.enc1)return Object.assign({fuente:'abogado'},o);return FC.orgTabla(cpro);};

/* ---------------- territorio (CSV) ---------------- */
const norm=s=>String(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[’`]/g,"'").replace(/[^a-z0-9' ]+/g,' ').replace(/\s+/g,' ').trim();
const ART=/^(el|la|los|las|l'|els|les|o|a|os|as|es|sa|ses) ?/;
const LOWW=new Set(['de','del','la','las','los','el','y','i','e','en','d','da','do','dos','das','les','els']);
const tc=s=>String(s||'').toLowerCase().split(/(\s+|\/|-)/).map((w,i,arr)=>{if(!w||/^\s+$|^\/$|^-$/.test(w))return w;const first=i===0||arr[i-1]==='/'||arr[i-1]==='-';if(!first&&LOWW.has(w))return w;const m=w.match(/^([dl]['’])(.+)$/);if(m)return (first?m[1].charAt(0).toUpperCase()+m[1].slice(1):m[1])+m[2].charAt(0).toUpperCase()+m[2].slice(1);return w.charAt(0).toUpperCase()+w.slice(1);}).join('');
const unInv=x=>{const m=String(x).match(/^(.*),\s*(EL|LA|LOS|LAS|ELS|LES|L'|O|A|OS|AS|ES|SA|SES)$/i);return m?m[2]+(m[2].endsWith("'")?'':' ')+m[1]:x;};
FC.tc=tc;
FC.buildIdx=()=>{const T=window.TERR;const byP={},byC={};T.m.forEach(r=>{const vs=new Set();[r[1],r[2],r[3]].forEach(n=>{if(!n)return;n.split('/').forEach(x=>{const k=norm(unInv(x.trim()));if(!k)return;vs.add(k);vs.add(k.replace(ART,''));});});const o={codm:r[0],name:tc(unInv(r[1])),cpro:r[4],cp:r[5],partido:r[6],social:r[7],sedeMN:r[8]||'',ant:r[3],v:[...vs]};(byP[r[4]]=byP[r[4]]||[]).push(o);byC[r[0]]=o;});FC.idx={byP,byC};};
FC.munSearch=(cpro,q)=>{if(!FC.idx)FC.buildIdx();const L=FC.idx.byP[cpro]||[];const k=norm(q);if(!k)return [];const k2=k.replace(ART,'');const sc=o=>{let b=99;o.v.forEach(v=>{if(v===k||v===k2)b=Math.min(b,0);else if(v.startsWith(k)||v.startsWith(k2))b=Math.min(b,1);else if((' '+v).includes(' '+k2))b=Math.min(b,2);});return b;};return L.map(o=>[sc(o),o]).filter(x=>x[0]<99).sort((a,b)=>a[0]-b[0]||a[1].name.localeCompare(b[1].name,'es')).slice(0,8).map(x=>x[1]);};
FC.munAll=q=>{if(!FC.idx)FC.buildIdx();const k=norm(q);if(!k)return [];return Object.values(FC.idx.byC).filter(o=>o.v.includes(k)||o.v.includes(k.replace(ART,'')));};
FC.munList=cpro=>{if(!FC.idx)FC.buildIdx();const L=FC.idx.byP[cpro]||[];if(!L._s){L.sort((a,b)=>a.name.localeCompare(b.name,'es'));L._s=1;}return L;};
FC.mun=codm=>{if(!codm)return null;if(!FC.idx)FC.buildIdx();return FC.idx.byC[codm]||null;};
FC.provName=cpro=>{const p=((window.TERR||{}).prov||{})[cpro];return p?tc(p.n):'';};
FC.ccaa=cpro=>{const p=((window.TERR||{}).prov||{})[cpro];return p?p.c:'';};
FC.provList=()=>Object.entries(window.TERR.prov).map(([k,v])=>[k,tc(v.n)]).sort((a,b)=>a[1].localeCompare(b[1],'es'));
FC.ccaaList=()=>[...new Set(Object.values(window.TERR.prov).map(v=>v.c))].sort((a,b)=>a.localeCompare(b,'es'));

/* ---------------- direcciones ---------------- */
FC.VIAS=['Calle','Avenida','Plaza','Paseo','Carretera','Camino','Ronda','Travesía','Glorieta','Urbanización','Polígono','Otro'];
FC.newDir=()=>({via:'',calle:'',num:'',bloque:'',esc:'',piso:'',puerta:'',cp:'',prov:'',codm:'',munq:'',ind:''});
/* comprobación en Google Maps: cuenta todo menos escalera, piso y puerta */
FC.dirSig=d=>d?[d.via,d.calle,d.num,d.bloque,d.cp,d.codm,d.prov].map(x=>String(x||'').trim().toLowerCase()).join('|'):'';
FC.dirQuery=d=>{const m=FC.mun(d.codm);return [`${d.via||''} ${d.calle||''} ${d.num||''}`.replace(/\s+/g,' ').trim()+(d.bloque?`, portal ${d.bloque}`:''),`${d.cp||''} ${m?m.name:(d.munq||'')}`.trim(),FC.provName(d.prov)||'','España'].filter(Boolean).join(', ');};
FC.gmapsUrl=d=>'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(FC.dirQuery(d));
FC.dirComprobada=d=>!!(d&&d.gmaps&&d.gmaps===FC.dirSig(d));
FC.dirVacia=d=>!d||!['calle','num','cp','prov','codm','munq'].some(k=>d[k]);
FC.fmtDir=(d,ph)=>{const m=x=>ph?P(x):'['+x+']';if(FC.dirVacia(d))return m('dirección completa');const mu=FC.mun(d.codm);const via=d.via&&d.via!=='Otro'?d.via+' ':'';const parts=[d.calle?via+d.calle:m('nombre de la vía'),d.num?(/^s\/?n$/i.test(d.num)?'s/n':'nº '+d.num):m('número')];const pi=[d.bloque?'portal '+d.bloque:'',d.esc?'esc. '+d.esc:'',d.piso?(/^\d+$/.test(d.piso)?d.piso+'º':d.piso):'',d.puerta||''].filter(Boolean).join(' ');if(pi)parts.push(pi);parts.push(`${/^\d{5}$/.test(d.cp||'')?d.cp:m('código postal')} ${mu?mu.name:m('municipio')}`);return parts.join(', ')+', '+(d.prov?FC.provName(d.prov):m('provincia'));};
FC.dirFalta=d=>{if(FC.dirVacia(d))return ['dirección'];const f=[];if(!d.calle)f.push('vía');if(!d.num)f.push('número');if(!/^\d{5}$/.test(d.cp||''))f.push('código postal');if(!d.prov)f.push('provincia');if(!d.codm)f.push('municipio elegido de la lista');return f;};
/* DNI/NIE: formato y letra de control (módulo 23). Devuelve '' si es válido o no aplica. */
FC.docCheck=(tipo,num)=>{tipo=String(tipo||'').toUpperCase();if(tipo!=='DNI'&&tipo!=='NIE')return '';const n=String(num||'').replace(/\(.*?\)/g,'').toUpperCase().replace(/[\s.\-]/g,'');if(!n)return '';const L='TRWAGMYFPDXBNJZSQVHLCKE';
 if(tipo==='DNI'){if(!/^\d{8}[A-Z]$/.test(n))return 'El DNI tiene 8 números y una letra (ejemplo: 12345678Z).';const ok=L[+n.slice(0,8)%23];return ok===n[8]?'':'La letra del DNI no corresponde a los números. Revise el número y la letra con el documento delante.';}
 if(!/^[XYZ]\d{7}[A-Z]$/.test(n))return 'El NIE empieza por X, Y o Z, sigue con 7 números y acaba en una letra (ejemplo: X1234567L).';const ok=L[+('XYZ'.indexOf(n[0])+n.slice(1,8))%23];return ok===n[8]?'':'La letra del NIE no corresponde a los números. Revise el número y la letra con el documento delante.';};
FC.dirsUsadas=(c,salvo)=>{const L=[],vis=new Set([FC.dirSig(getP(c,salvo))]);const add=(p,l)=>{const d=getP(c,p);if(!d||FC.dirFalta(d).length)return;const k=FC.dirSig(d);if(vis.has(k))return;vis.add(k);L.push({p,l,d});};
 add('cli.dom','Domicilio de la clienta');if(c.cli.empadronada==='si')add('cli.padronDir','Padrón de la clienta');if(c.cli.postalIgual==='no')add('cli.postal','Dirección postal de la clienta');
 c.empleadores.forEach((e,i)=>{add(`empleadores.${i}.dom`,'Domicilio de '+(FC.full(FC.per(c,e.titular))||'empleador '+(i+1)));(e.otros||[]).forEach(id=>{const k=c.personas.findIndex(q=>q.id===id);if(k>=0)add(`personas.${k}.dom`,'Domicilio de '+(FC.full(c.personas[k])||'otra persona empleadora'));});});
 c.lugares.forEach((l,i)=>add(`lugares.${i}.dir`,'Lugar de trabajo '+(i+1)));return L.filter(x=>x.p!==salvo);};
FC.dirCPmal=d=>d&&/^\d{5}$/.test(d.cp||'')&&d.prov&&d.cp.slice(0,2)!==d.prov;

/* ---------------- plantillas de registros ---------------- */
FC.newSemana=(c,nombre)=>({id:uid(c,'W'),nombre:nombre||'A',turnos:[],dias:[0,1,2,3,4,5,6].map(()=>({libre:false,tramos:[]}))});
/* turno (como en la calculadora): días de la semana + entrada + salida + tipo + descansos con horario o en minutos */
FC.newTurno=(c,dias)=>({id:uid(c,'U'),dias:dias||[],e:'',s:'',tipo:'efectivo',desc:[],descMin:'',nota:''});
FC.newDesc=c=>({id:uid(c,'D'),e:'',s:''});
FC.turnos2dias=s=>{const D=[0,1,2,3,4,5,6].map(()=>({libre:false,tramos:[]}));(s.turnos||[]).forEach(t=>{const rng=(t.desc||[]).filter(x=>x.e&&x.s);(t.dias||[]).forEach(i=>{if(!D[i])return;D[i].tramos.push({e:t.e,s:t.s,tipo:t.tipo||'efectivo',menos:rng.length?0:(numS(t.descMin)||0),tid:t.id});rng.forEach(x=>D[i].tramos.push({e:x.e,s:x.s,tipo:'descanso',tid:t.id}));});});D.forEach(d=>{if(!d.tramos.length)d.libre=true;});return D;};
FC.diasDe=s=>(s.turnos&&s.turnos.length)?FC.turnos2dias(s):s.dias;
/* convierte una semana guardada por días (versión anterior) a turnos */
FC.dias2turnos=(c,s)=>{if(s.turnos&&s.turnos.length)return;const map={};const out=[];
 (s.dias||[]).forEach((d,i)=>{if(d.libre)return;const T=(d.tramos||[]).filter(t=>t.e&&t.s);const W=T.filter(t=>t.tipo!=='descanso'),Ds=T.filter(t=>t.tipo==='descanso');
  W.forEach(w=>{const x=FC.tramo(w);const mine=Ds.filter(y=>{const z=FC.tramo(y);return x&&z&&[0,1440].some(k=>Math.min(x.e,z.e+k)>Math.max(x.a,z.a+k));});
   const key=[w.e,w.s,w.tipo,mine.map(y=>y.e+'-'+y.s).join(','),w.nota||''].join('|');if(map[key]){map[key].dias.push(i);return;}
   const t=FC.newTurno(c,[i]);Object.assign(t,{e:w.e,s:w.s,tipo:w.tipo||'efectivo',nota:w.nota||'',desc:mine.map(y=>Object.assign(FC.newDesc(c),{e:y.e,s:y.s}))});map[key]=t;out.push(t);});});
 s.turnos=out;s.dias=[0,1,2,3,4,5,6].map(()=>({libre:false,tramos:[]}));};
FC.normalize=st=>{const c=st.c;(c.periodos||[]).forEach(p=>p.semanas.forEach(w=>{if(!w.turnos||!w.turnos.length)FC.dias2turnos(c,w);}));};
FC.newTramo=(c,tipo,e,s)=>({id:uid(c,'T'),e:e||'',s:s||'',tipo:tipo||'efectivo',nota:''});
FC.T={
 personas:c=>({id:uid(c,'P'),trato:'',nombre:'',apellidos:'',papel:'',edad:'',tel:'',email:'',docTipo:'',docNum:'',trabajo:'',m:{},frec:'',dias:'',vio:'',testigo:''}),
 empleadores:c=>({id:uid(c,'E'),titular:'',otros:[],dom:FC.newDir(),desde:'',hasta:''}),
 lugares:c=>({id:uid(c,'L'),dir:FC.newDir(),desde:'',hasta:'',quienes:[]}),
 autorizacion:c=>({id:uid(c,'A'),tipo:'',desde:'',hasta:'',permiso:''}),
 altas:c=>({id:uid(c,'S'),alta:'',baja:'',emps:[],fuente:'',pagoMes:'',pagoMesForma:''}),
 cuidados:c=>({id:uid(c,'K'),persona:'',autonomia:'',grado:'',diag:[],diagOtro:'',ayudas:'',medicacion:'',noche:'',centro:'',sanitarios:'',colegio:'',extra:'',rutina:'',cu:[],obs:''}),
 periodos:c=>({id:uid(c,'J'),desde:'',hasta:'',modalidad:'',lugar:'',semanas:[FC.newSemana(c,'A')]}),
 meses:c=>({id:uid(c,'M'),mes:'',salario:'',extra:'',segundo:'',segConcepto:'',segOrigen:'',forma:'',fechaPago:'',nocobro:false,especie:'',obs:''}),
 incidencias:c=>({id:uid(c,'I'),fecha:'',concepto:'',importe:'',tipo:'',prueba:''}),
 vacaciones:c=>({id:uid(c,'V'),desde:'',hasta:'',pagadas:'',importe:'',disfruto:''}),
 cronologia:c=>({id:uid(c,'H'),fecha:'',desc:'',personas:[],pruebas:[]}),
 pruebas:c=>({id:uid(c,'R'),nombre:'',tipo:'',desc:'',fecha:'',hecho:'',archivos:[]}),
 tablas:c=>({id:uid(c,'Y'),anio:'',base:'',pluses:'',pagasNum:'',pagaImporte:'',anual:'',vacImporte:''})
};
FC.newC=()=>{const st=SF.newFicha('C');st.v=2;st.c={seq:0,ns:{},nota:{},
 filtro:{abogado:'',estudiar:'',actuado:'',papFecha:'',demFecha:'',conocio:[],conocioOtro:'',reclamar:[],motivo:''},int:{finReal:'',dormia:'',dormiaOtro:'',disponible:'',disponibleTxt:''},
 cli:{trato:'',nombre:'',apellidos:'',pais:'',doc:'',docnum:'',emisor:'',emisorPais:'',telPref:'ES',nacionalidad:'',nac:'',tel:'',email:'',empadronada:'',padronDir:FC.newDir(),padronFecha:'',dom:FC.newDir(),postalIgual:'',postal:FC.newDir(),sindical:''},
 personas:[],empleadores:[],lugares:[],
 rel:{inicio:'',aprox:false,fin:'',contrato:'',alta:'',autGlobal:''},autorizacion:[],altas:[],
 tareas:[],tareasOtras:'',mascotas:'',cuidados:[],relDia:'',
 periodos:[],
 sal:{fijo:'',importe:'',forma:[],dia:'',porHoras:'',precioHora:'',pagas:'',pagasTxt:'',entrega:[],entregaDonde:'',entregaPresentes:'',entregaPresentesP:[],formaFinal:'',ultimoMes:'',ultimoMesImporte:''},meses:[],incidencias:[],
 vac:{tuvo:'',autoriza:[]},vacaciones:[],
 fin:{tipo:'',fechaCom:'',fechaFin:'',medio:'',dicho:'',motivo:'',docEntregado:'',pidieronFirmar:'',firmo:'',copia:'',pago:'',pagoImporte:'',pagoConcepto:'',dia:'',fallQuien:'',fallFecha:'',fallRel:'',renMedio:'',renMotivo:'',burofax:'',burFecha:'',burDest:'',burRes:''},
 cronologia:[],pru:{llaves:'',acceso:'',audios:'',telefono:'',conversaciones:'',convCon:[]},pruebas:[],obs:'',
 abg:{calif:'',acum:'',coemp:{},sede:'',smiVer:{},horasBaseVac:'',incluirSegundo:true,incluirPrescritos:false}};
 st.c.pruebas.push(FC.T.pruebas(st.c));return st;};

/* ---------------- personas ---------------- */
FC.per=(c,id)=>c.personas.find(p=>p.id===id)||null;
FC.trato=p=>p&&p.trato==='d'?'D.':'D.ª';
FC.full=p=>p?[p.nombre,p.apellidos].map(x=>(x||'').trim()).filter(Boolean).join(' '):'';
FC.perNom=p=>p?`${FC.trato(p)} ${(p.nombre||'').trim()||P('nombre')} ${(p.apellidos||'').trim()||P('apellidos')}`:P('persona');
FC.perLabel=p=>p.nombre?(FC.full(p)+(p.papel?' ('+p.papel+')':'')):'Persona sin nombre';
/* nacionalidad: país -> gentilicio (f, m) y nombre oficial para «emitido por» */
FC.PAISES=[['PE','Perú','peruana','peruano','la República del Perú'],['CO','Colombia','colombiana','colombiano','la República de Colombia'],['HN','Honduras','hondureña','hondureño','la República de Honduras'],['NI','Nicaragua','nicaragüense','nicaragüense','la República de Nicaragua'],['VE','Venezuela','venezolana','venezolano','la República Bolivariana de Venezuela'],['EC','Ecuador','ecuatoriana','ecuatoriano','la República del Ecuador'],['BO','Bolivia','boliviana','boliviano','el Estado Plurinacional de Bolivia'],['PY','Paraguay','paraguaya','paraguayo','la República del Paraguay'],['GT','Guatemala','guatemalteca','guatemalteco','la República de Guatemala'],['SV','El Salvador','salvadoreña','salvadoreño','la República de El Salvador'],['DO','República Dominicana','dominicana','dominicano','la República Dominicana'],['CU','Cuba','cubana','cubano','la República de Cuba'],['MX','México','mexicana','mexicano','los Estados Unidos Mexicanos'],['AR','Argentina','argentina','argentino','la República Argentina'],['CL','Chile','chilena','chileno','la República de Chile'],['UY','Uruguay','uruguaya','uruguayo','la República Oriental del Uruguay'],['BR','Brasil','brasileña','brasileño','la República Federativa del Brasil'],['CR','Costa Rica','costarricense','costarricense','la República de Costa Rica'],['PA','Panamá','panameña','panameño','la República de Panamá'],['MA','Marruecos','marroquí','marroquí','el Reino de Marruecos'],['DZ','Argelia','argelina','argelino','la República Argelina Democrática y Popular'],['SN','Senegal','senegalesa','senegalés','la República de Senegal'],['NG','Nigeria','nigeriana','nigeriano','la República Federal de Nigeria'],['GQ','Guinea Ecuatorial','ecuatoguineana','ecuatoguineano','la República de Guinea Ecuatorial'],['PH','Filipinas','filipina','filipino','la República de Filipinas'],['CN','China','china','chino','la República Popular China'],['IN','India','india','indio','la República de la India'],['PK','Pakistán','pakistaní','pakistaní','la República Islámica de Pakistán'],['RO','Rumanía','rumana','rumano','Rumanía'],['UA','Ucrania','ucraniana','ucraniano','Ucrania'],['GE','Georgia','georgiana','georgiano','Georgia'],['RU','Rusia','rusa','ruso','la Federación de Rusia']];
FC.pais=k=>FC.PAISES.find(x=>x[0]===k)||null;
FC.ES=['ES','España','española','español','el Reino de España'];
/* países de la Unión Europea (27), con su nombre oficial para «emitido por …» */
FC.PAISES_UE=[['ES','España','el Reino de España'],['DE','Alemania','la República Federal de Alemania'],['AT','Austria','la República de Austria'],['BE','Bélgica','el Reino de Bélgica'],['BG','Bulgaria','la República de Bulgaria'],['CY','Chipre','la República de Chipre'],['HR','Croacia','la República de Croacia'],['DK','Dinamarca','el Reino de Dinamarca'],['SK','Eslovaquia','la República Eslovaca'],['SI','Eslovenia','la República de Eslovenia'],['EE','Estonia','la República de Estonia'],['FI','Finlandia','la República de Finlandia'],['FR','Francia','la República Francesa'],['GR','Grecia','la República Helénica'],['HU','Hungría','Hungría'],['IE','Irlanda','Irlanda'],['IT','Italia','la República Italiana'],['LV','Letonia','la República de Letonia'],['LT','Lituania','la República de Lituania'],['LU','Luxemburgo','el Gran Ducado de Luxemburgo'],['MT','Malta','la República de Malta'],['NL','Países Bajos','el Reino de los Países Bajos'],['PL','Polonia','la República de Polonia'],['PT','Portugal','la República Portuguesa'],['CZ','Chequia','la República Checa'],['RO','Rumanía','Rumanía'],['SE','Suecia','el Reino de Suecia']];
FC.paisEmisor=k=>{if(k==='ES')return FC.ES;const p=FC.pais(k);if(p)return p;const u=FC.PAISES_UE.find(x=>x[0]===k);return u?[u[0],u[1],'','',u[2]]:null;};
/* quién emitió el documento: país elegido; por defecto, el pasaporte lo emite su país y el NIE, España */
FC.emisorDe=c=>{const k=Object.assign({},c.cli);if(k.doc!=='Pasaporte'&&k.doc!=='NIE')return null;if(k.doc==='NIE'&&k.emisorPais&&!FC.PAISES_UE.some(x=>x[0]===k.emisorPais))k.emisorPais='';if(k.emisorPais==='otro')return (k.emisor||'').trim()||P('quién emitió el documento');const x=FC.paisEmisor(k.emisorPais||(k.doc==='NIE'?'ES':k.pais));return x?x[4]:((k.emisor||'').trim()||P('quién emitió el documento'));};
/* prefijos telefónicos */
FC.PREF=[['ES','España','+34'],['PE','Perú','+51'],['CO','Colombia','+57'],['HN','Honduras','+504'],['NI','Nicaragua','+505'],['VE','Venezuela','+58'],['EC','Ecuador','+593'],['BO','Bolivia','+591'],['PY','Paraguay','+595'],['GT','Guatemala','+502'],['SV','El Salvador','+503'],['DO','República Dominicana','+1'],['CU','Cuba','+53'],['MX','México','+52'],['AR','Argentina','+54'],['CL','Chile','+56'],['UY','Uruguay','+598'],['BR','Brasil','+55'],['CR','Costa Rica','+506'],['PA','Panamá','+507'],['MA','Marruecos','+212'],['DZ','Argelia','+213'],['SN','Senegal','+221'],['NG','Nigeria','+234'],['GQ','Guinea Ecuatorial','+240'],['PH','Filipinas','+63'],['CN','China','+86'],['IN','India','+91'],['PK','Pakistán','+92'],['RO','Rumanía','+40'],['UA','Ucrania','+380'],['GE','Georgia','+995'],['RU','Rusia','+7'],['PT','Portugal','+351'],['FR','Francia','+33'],['IT','Italia','+39'],['GB','Reino Unido','+44'],['US','Estados Unidos','+1']];
FC.flag=k=>String.fromCodePoint(...k.toUpperCase().split('').map(ch=>127397+ch.charCodeAt(0)));
FC.telFull=(pref,num)=>{const n=String(num||'').replace(/\D/g,'');if(!n)return '';const x=FC.PREF.find(p=>p[0]===(pref||'ES'))||FC.PREF[0];return x[2]+' '+n;};
/* año de reclamación: del mismo mes del año pasado hasta el fin de la relación */
FC.ventana=c=>{const h=today();const y=+h.slice(0,4),m=+h.slice(5,7);const w0=Date.UTC(y-1,m-1,1);const ini=pd(c.rel.inicio);return {desde:iso(ini!=null?Math.max(ini,w0):w0),hasta:FC.endRel(c),w0:iso(w0)};};
FC.gent=c=>{const x=FC.pais(c.cli.pais);if(x)return x[2];return (c.cli.nacionalidad||'').trim().toLowerCase();};
const MESES=['ENERO','FEBRERO','MARZO','ABRIL','MAYO','JUNIO','JULIO','AGOSTO','SEPTIEMBRE','OCTUBRE','NOVIEMBRE','DICIEMBRE'];
FC.mesTxt=(y,m)=>`${MESES[m-1]} DEL ${y}`;
FC.mesKey=k=>FC.mesTxt(+k.slice(0,4),+k.slice(5,7));
/* horas que se pagan según el ejemplo: 40 de trabajo efectivo + hasta 20 de presencia; lo que pasa de 40 h efectivas cuenta como presencia */
FC.horasPag=(ef,pres)=>{ef=Math.round(ef*10)/10;pres=Math.round(pres*10)/10;return Math.min(ef,40)+Math.min(pres+Math.max(ef-40,0),20);};
FC.esMenor=(c,k)=>{const p=FC.per(c,k.persona);const e=p&&p.edad!==''?Number(p.edad):null;return e!=null?e<18:/hij|niet|niñ|beb/i.test((p&&p.papel)||'');};
FC.empleadoras=c=>{const ids=[];c.empleadores.forEach(e=>{if(e.titular&&!ids.includes(e.titular))ids.push(e.titular);});return ids;};
FC.coempValidados=c=>{const ids=[];c.empleadores.forEach(e=>(e.otros||[]).forEach(o=>{if(c.abg.coemp[o]!==false&&!ids.includes(o)&&!FC.empleadoras(c).includes(o))ids.push(o);}));return ids;};
FC.MODT={interna:'interna',externa:'externa',mixta:'mixta',horas:'externa por horas'};
FC.modTxt=m=>FC.MODT[m]||P('modalidad');
/* ===================== FICHA B · régimen general sin papeles ===================== */
FC.esB=c=>!!(c&&c.reg==='general');
FC.SOLO_C=['tareas','pru.llaves'];
FC.convVacio=()=>({actividad:'',cnae:'',nomina:'',codigo:'',nombre:'',ambito:'',vigencia:'',publicacion:'',enlace:'',categoria:'',grupo:'',categorias:[],tablas:[],pluses:'',jornadaSemanal:'',jornadaAnual:'',horasExtra:'',pagasNum:'',pagasCuantia:'',pagasProrrata:'',vacDias:'',vacTipo:'',vacBase:'',it:'',preaviso:'',preavisoPenal:'',otros:'',noEncontrado:'',porVerificar:'',fuente:'',ok:{}});
/* tabla salarial del convenio para el año (o la última anterior publicada) */
FC.convAnio=(c,y)=>{const T=((c.conv||{}).tablas||[]).filter(t=>+t.anio&&+t.anio<=y&&(numS(t.base)!=null||numS(t.anual)!=null)).sort((a,b)=>b.anio-a.anio);return T[0]||null;};
/* lo que debía percibir al mes a jornada completa: convenio de su categoría, con el SMI como mínimo en cómputo anual */
FC.salB=(st,y)=>{const c=st.c,K=c.conv||{};const smiP=FC.smiP(st,y);if(smiP==null)return null;const smiM=smiP*12/14,smiA=smiP*12;const T=FC.convAnio(c,y);
 if(T){const N=numS(T.pagasNum)!=null?numS(T.pagasNum):(numS(K.pagasNum)!=null?numS(K.pagasNum):2);const sin=(numS(T.base)||0)+(numS(T.pluses)||0);const paga=numS(T.pagaImporte)!=null?numS(T.pagaImporte):(numS(T.base)||0);const anual=numS(T.anual)!=null?numS(T.anual):sin*12+N*paga;
  if(anual>=smiA-0.005)return {fuente:'convenio',anio:+T.anio,otroAnio:+T.anio!==y,T,N,paga,sin:numS(T.anual)!=null&&numS(T.base)==null?(anual-N*paga)/12:sin,pro:anual/12,anual,smiA};}
 return {fuente:T?'SMI (el convenio queda por debajo)':'SMI (sin datos del convenio)',T,N:2,paga:smiM,sin:smiM,pro:smiP,anual:smiA,smiA};};
/* CIF: letra + 7 cifras + control (cifra o letra). Devuelve '' si es válido o está vacío */
FC.cifCheck=v=>{const n=String(v||'').toUpperCase().replace(/[\s.\-]/g,'');if(!n)return '';if(!/^[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]$/.test(n))return 'El CIF tiene una letra, 7 números y un carácter de control (ejemplo: B12345674).';
 const d=n.slice(1,8);let s=0;for(let i=0;i<7;i++){let x=+d[i];if(i%2===0){x*=2;x=Math.floor(x/10)+x%10;}s+=x;}const k=(10-s%10)%10,L='JABCDEFGHI'[k],ch=n[8];
 const soloL='KPQRSNW'.includes(n[0]),soloN='ABEH'.includes(n[0]);return (soloL?ch===L:soloN?ch===String(k):(ch===String(k)||ch===L))?'':'El carácter de control del CIF no corresponde. Revíselo con la documentación de la empresa.';};
/* NIF de una persona física (autónomo): DNI o NIE, con su letra de control */
FC.nifCheck=v=>{const n=String(v||'').toUpperCase().replace(/[\s.\-]/g,'');if(!n)return '';return FC.docCheck(/^[XYZ]/.test(n)?'NIE':'DNI',n);};
FC.newB=()=>{const st=FC.newC();st.tipo='B';const c=st.c;c.reg='general';c.conv=FC.convVacio();c.puesto={categoria:'',funciones:'',nomina:''};c.rel.horasContrato='';c.rel.horasAlta='';return st;};
FC.jornB=c=>numS((c.conv||{}).jornadaSemanal)||40;
FC.fracB=(c,efw)=>Math.min(1,(efw||0)/FC.jornB(c));
FC.esInterna=c=>!FC.esB(c)&&c.periodos.some(p=>p.modalidad==='interna'||p.modalidad==='mixta');
FC.califEf=c=>c.abg.calif||(c.fin.tipo==='despido'?'improcedente':'');
FC.acumEf=(c,T1,T2)=>c.abg.acum?c.abg.acum==='si':((T1&&T1.total||0)+(T2&&T2.total||0)+(T1&&T1.debidas||0)>0.005);
FC.domDe=(c,pidp)=>{const q=FC.per(c,pidp);if(q&&q.dom&&!FC.dirVacia(q.dom))return q.dom;const e=c.empleadores.find(x=>x.titular===pidp)||c.empleadores.find(x=>(x.otros||[]).includes(pidp));return e?e.dom:null;};

/* ---------------- jornada ---------------- */
const tmin=s=>{if(!s||!/^\d{1,2}:\d{2}$/.test(s))return null;const[h,m]=s.split(':').map(Number);if(h>24||m>59)return null;return h*60+m;};
const nightOf=(a,e)=>{let n=0;[[0,360],[1320,1800],[2760,2880]].forEach(([x,y])=>{n+=Math.max(0,Math.min(e,y)-Math.max(a,x));});return n;};
FC.tramo=t=>{const a=tmin(t.e),b=tmin(t.s);if(a==null||b==null)return null;const e=b<=a?b+1440:b;return {a,e,min:e-a,noct:nightOf(a,e),cruza:e>1440};};
FC.dia=d=>{const r={ef:0,pres:0,desc:0,noct:0,first:null,last:null,libre:!!d.libre,ok:true,n:0};if(d.libre)return r;
 const T=(d.tramos||[]).map(t=>({t,x:FC.tramo(t)}));T.forEach(o=>{if(!o.x&&(o.t.e||o.t.s))r.ok=false;});
 const D=T.filter(o=>o.x&&o.t.tipo==='descanso').map(o=>o.x);
 T.filter(o=>o.x&&o.t.tipo!=='descanso').forEach(o=>{let m=o.x.min,nt=o.x.noct;D.forEach(y=>{[0,1440].forEach(k=>{const a=Math.max(o.x.a,y.a+k),e=Math.min(o.x.e,y.e+k);if(e>a){m-=e-a;nt-=nightOf(a,e);}});});const mn=Math.min(Math.max(0,Number(o.t.menos)||0),m);if(mn){m-=mn;r.desc+=mn/60;}m=Math.max(0,m);nt=Math.max(0,Math.min(nt,m));
  if(o.t.tipo==='presencia')r.pres+=m/60;else{r.ef+=m/60;r.noct+=nt/60;}r.n++;
  r.first=r.first==null?o.x.a:Math.min(r.first,o.x.a);r.last=r.last==null?o.x.e:Math.max(r.last,o.x.e);});
 D.forEach(y=>{r.desc+=y.min/60;});return r;};
FC.semana=s=>{const D=FC.diasDe(s).map(FC.dia);const t={ef:0,pres:0,desc:0,noct:0};D.forEach(d=>{t.ef+=d.ef;t.pres+=d.pres;t.desc+=d.desc;t.noct+=d.noct;});
 const busy=[];D.forEach((d,i)=>{if(d.first!=null)busy.push([i*1440+d.first,i*1440+d.last]);});
 let minGap=null,maxGap=null,maxAt=null;
 if(busy.length){busy.sort((a,b)=>a[0]-b[0]);const M=[];busy.forEach(b=>{const L=M[M.length-1];if(L&&b[0]<=L[1])L[1]=Math.max(L[1],b[1]);else M.push(b.slice());});
  for(let i=0;i<M.length;i++){const cur=M[i],nx=i+1<M.length?M[i+1][0]:M[0][0]+10080;const g=nx-cur[1];if(minGap==null||g<minGap)minGap=g;if(maxGap==null||g>maxGap){maxGap=g;maxAt=[cur[1],nx];}}}
 return Object.assign({D,minGap,maxGap,maxAt},t);};
FC.endRel=c=>c.fin.fechaFin||c.rel.fin||today();
FC.calcJ=c=>{const map={},per=[],ov=[];const relEnd=FC.endRel(c);
 c.periodos.forEach((p,pi)=>{const r={id:p.id,i:pi,days:0,ef:0,pres:0,desc:0,noct:0,sem:p.semanas.map(FC.semana),ok:false,desde:p.desde,hasta:p.hasta||relEnd};const a=pd(p.desde),b=pd(p.hasta||relEnd);if(a==null||b==null||b<a){per.push(r);return;}r.ok=true;
  const mon0=a-((new Date(a).getUTCDay()+6)%7)*DAY;const n=p.semanas.length||1;
  for(let t=a;t<=b;t+=DAY){const f=iso(t);const dw=(new Date(t).getUTCDay()+6)%7;const wi=Math.floor((t-mon0)/(7*DAY))%n;const s=r.sem[wi];if(!s)continue;const d=s.D[dw];if(map[f]){ov.push({f,a:map[f].p,b:pi});continue;}map[f]={p:pi,ef:d.ef,pres:d.pres,desc:d.desc,noct:d.noct};r.days++;r.ef+=d.ef;r.pres+=d.pres;r.desc+=d.desc;r.noct+=d.noct;}
  per.push(r);});
 const tot={ef:0,pres:0,desc:0,noct:0};per.forEach(r=>{tot.ef+=r.ef;tot.pres+=r.pres;tot.desc+=r.desc;tot.noct+=r.noct;});
 const g={};ov.forEach(o=>{const k=o.a+'-'+o.b;g[k]=g[k]||{a:o.a,b:o.b,desde:o.f,hasta:o.f,n:0};g[k].hasta=o.f;g[k].n++;});
 return {per,map,tot,overlaps:Object.values(g)};};

/* ---------------- TABLA 1, TABLA 2, autorización ---------------- */
const dim=(y,m)=>new Date(Date.UTC(y,m,0)).getUTCDate();
/* parte del mes: mes completo = 1; mes incompleto = días ÷ 30 (siempre entre 30, sea cual sea el mes) */
FC.frMes=(dias,dim)=>dias>=dim?1:Math.min(dias,30)/30;
/* pagas extra: «prorrata» (en cada mes, SMI × 14 / 12, como el escrito de ejemplo) o «separado» (mes con SMI × 12 / 12 y tabla aparte de pagas) */
FC.pagasMet=c=>c.abg.pagasMetodo==='separado'?'separado':c.abg.pagasMetodo==='prorrata'?'prorrata':(FC.esB(c)&&(c.conv||{}).pagasProrrata==='no'?'separado':'prorrata');
FC.calcT1=(st,met)=>{const c=st.c;met=met||FC.pagasMet(c);const sep=met==='separado';const J=FC.calcJ(c);const ini=c.rel.inicio,fin=FC.endRel(c);const out={rows:[],blocked:{},sinJornada:0,sinDatos:0,total:0,totalNeto:0,years:{},J,metodo:met};const cobP={};
 if(pd(ini)==null||pd(fin)==null||pd(fin)<pd(ini))return out;const lim=pd(FC.ventana(c).w0);out.ventana=FC.ventana(c);const finR=!!(c.fin.fechaFin||c.rel.fin);
 let y=+ini.slice(0,4),m=+ini.slice(5,7);
 for(let guard=0;guard<600;guard++){const key=`${y}-${String(m).padStart(2,'0')}`;const d0=Date.UTC(y,m-1,1),d1=Date.UTC(y,m-1,dim(y,m));const a=Math.max(d0,pd(ini)),b=Math.min(d1,pd(fin));if(a>pd(fin))break;
  const cov=Math.round((b-a)/DAY)+1;let ef=0,pres=0,jd=0;for(let t=a;t<=b;t+=DAY){const x=J.map[iso(t)];if(x){ef+=x.ef;pres+=x.pres;jd++;}}
  const wk=cov/7,efw=ef/wk,presw=pres/wk,B=FC.esB(c),D=B?FC.salB(st,y):null,smiP=B?(D?D.pro:null):FC.smiP(st,y),smi=B?(D?(sep?D.sin:D.pro):null):(smiP!=null&&sep?smiP*12/14:smiP);const row={key,y,m,cov,a:iso(a),b:iso(b),dim:dim(y,m),efw,presw,jd,smi,deb:null,perc:null,dif:null,presc:d1<lim,estado:''};
  if(smi==null){row.estado='smi';out.blocked[y]=true;}else if(jd<cov){row.estado='jornada';out.sinJornada++;}else if(B){row.frac=FC.fracB(c,efw);row.D=D;row.deb=smi*row.frac*FC.frMes(cov,row.dim);row.pagaDev=D.paga*D.N/12*row.frac*FC.frMes(cov,row.dim);}else row.deb=smi*FC.horasPag(efw,presw)/40*FC.frMes(cov,row.dim);
  if(c.sal.fijo==='si'){const imp=numS(c.sal.importe);row.perc=imp!=null?imp*FC.frMes(cov,row.dim):null;}
  else if(c.sal.fijo==='no'){const mm=c.meses.find(x=>x.mes===key);if(!mm)row.perc=null;else if(mm.nocobro)row.perc=0;else{row.perc=(numS(mm.salario)||0)+(sep?0:(numS(mm.extra)||0))+((mm.segOrigen==='mismo'&&c.abg.incluirSegundo!==false)?(numS(mm.segundo)||0):0);if(sep&&numS(mm.extra))cobP[y]=(cobP[y]||0)+numS(mm.extra);}}
  c.incidencias.forEach(i=>{if(i.tipo==='pagado'&&(i.fecha||'').slice(0,7)===key&&row.perc!=null)row.perc+=numS(i.importe)||0;});
  if(finR&&d1>=pd(fin)&&c.sal.ultimoMes==='no')row.perc=0;else if(finR&&d1>=pd(fin)&&c.sal.ultimoMes==='si'&&numS(c.sal.ultimoMesImporte)!=null)row.perc=numS(c.sal.ultimoMesImporte);
  if(row.perc==null){out.sinDatos++;if(!row.estado)row.estado='sindatos';}
  if(row.deb!=null&&row.perc!=null)row.dif=row.deb-row.perc;
  out.rows.push(row);if(d1>=pd(fin))break;m++;if(m>12){m=1;y++;}}
 /* meses de interés: van en su propia tabla y no en la tabla 1 general */
 out.esp=[];const cuenta=R=>!R.every(r=>r.presc)||!!c.abg.incluirPrescritos;
 (c.rel.alta==='si'?c.altas:[]).forEach((al,ai)=>{const bru=numS(al.pagoBruto),net=numS(al.pagoNeto),a0=pd(al.pagoDesde),b0=pd(al.pagoHasta);if((bru==null&&net==null)||a0==null||b0==null||b0<a0)return;
  const R=out.rows.filter(r=>!r.esp&&pd(r.b)>=a0&&pd(r.a)<=b0);if(!R.length)return;let deb=0,okd=true;R.forEach(r=>{r.esp='alta';const ov=Math.round((Math.min(pd(r.b),b0)-Math.max(pd(r.a),a0))/DAY)+1;if(r.deb==null)okd=false;else deb+=r.deb/FC.frMes(r.cov,r.dim)*FC.frMes(ov,r.dim);});
  const perc=bru!=null?bru:net;out.esp.push({tipo:'alta',i:ai,a:iso(Math.max(a0,pd(R[0].a))),b:iso(Math.min(b0,pd(R[R.length-1].b))),deb:okd?deb:null,perc,bruto:bru,neto:net,dif:okd?deb-perc:null,parcial:pd(R[0].a)<a0||pd(R[R.length-1].b)>b0,rows:R,cuenta:cuenta(R)});});
 const UL=out.rows[out.rows.length-1];if(finR&&UL&&!UL.esp&&(c.sal.ultimoMes==='si'||c.sal.ultimoMes==='no')){UL.esp='ultimo';out.esp.unshift({tipo:'ultimo',a:UL.a,b:UL.b,deb:UL.deb,perc:UL.perc,dif:UL.dif,rows:[UL],cuenta:cuenta([UL])});}
 out.totalEsp=out.esp.reduce((s,e)=>s+(e.cuenta&&e.dif>0?e.dif:0),0);
 out.rows.forEach(r=>{if(r.esp||r.dif==null||(r.presc&&!c.abg.incluirPrescritos))return;out.total+=Math.max(0,r.dif);out.years[r.y]=(out.years[r.y]||0)+r.dif;});
 out.totalNeto=Object.values(out.years).reduce((s,v)=>s+Math.max(0,v),0);
 out.debidas=c.incidencias.filter(i=>i.tipo==='debido').reduce((s,i)=>s+(numS(i.importe)||0),0);
 /* pagas extra por separado: 2 al año = 2/12 de lo que debía percibir cada mes (sin prorrata); se resta lo cobrado como paga extra */
 out.pagas=[];out.totalPagas=0;if(sep){if(finR&&c.sal.ultimoMes==='si'&&numS(c.sal.finPagas)){const yl=+FC.endRel(c).slice(0,4);cobP[yl]=(cobP[yl]||0)+numS(c.sal.finPagas);}
  [...new Set(out.rows.map(r=>r.y))].forEach(yy=>{const R=out.rows.filter(r=>r.y===yy&&(!r.presc||c.abg.incluirPrescritos));if(!R.length)return;const ok=R.every(r=>r.deb!=null);const dev=ok?R.reduce((s,r)=>s+(r.pagaDev!=null?r.pagaDev:r.deb*2/12),0):null;const cob=cobP[yy]||0;
   out.pagas.push({y:yy,dev,cob,dif:dev!=null?dev-cob:null,a:R[0].a,b:R[R.length-1].b,cuenta:cuenta(R)});});
  out.totalPagas=out.pagas.reduce((s,p)=>s+(p.cuenta&&p.dif>0?p.dif:0),0);}
 out.pagoFinal=finR&&c.sal.ultimoMes==='si'?(numS(c.sal.finVac)||0)+(sep?0:(numS(c.sal.finPagas)||0))+(numS(c.sal.finOtros)||0):c.fin.pago==='si'?(numS(c.fin.pagoImporte)||0):0;
 return out;};
/* fichas anteriores: «¿Le pagaron algo al finalizar?» pasa al desglose del último mes (Salarios) */
FC.normFin=c=>{const f=c.fin||{};if(f.pago!=='si'||c.sal.ultimoMes)return;c.sal.ultimoMes='si';if(numS(f.pagoImporte)!=null&&numS(c.sal.finOtros)==null){c.sal.finOtros=f.pagoImporte;c.sal.finOtrosTxt=(f.pagoConcepto||'').trim()||'lo que le pagaron al finalizar';}f.pago='';f.pagoImporte='';f.pagoConcepto='';};
FC.calcT2=st=>{const c=st.c;const J=FC.calcJ(c);const ini=c.rel.inicio,fin=FC.endRel(c);const rows=[];if(pd(ini)==null||pd(fin)==null||pd(fin)<pd(ini))return {rows,total:0};const y0=+ini.slice(0,4),y1=+fin.slice(0,4);
 for(let y=y0;y<=y1;y++){const a=Math.max(Date.UTC(y,0,1),pd(ini)),b=Math.min(Date.UTC(y,11,31),pd(fin));const cov=Math.round((b-a)/DAY)+1;const diy=360;
  let ef=0,pres=0,jd=0;for(let t=a;t<=b;t+=DAY){const x=J.map[iso(t)];if(x){ef+=x.ef;pres+=x.pres;jd++;}}
  const hbAuto=jd?Math.min(40,FC.horasPag(ef/(jd/7),pres/(jd/7))):null;const hbM=numS(c.abg.horasBaseVac);const hb=hbM!=null?hbM:hbAuto;
  const B=FC.esB(c),D=B?FC.salB(st,y):null,K=c.conv||{};const vd=B&&numS(K.vacDias)?numS(K.vacDias):30;
  const fr=B&&jd?FC.fracB(c,ef/(jd/7)):null;const hbB=B?(hbM!=null?hbM:(fr!=null?fr*FC.jornB(c):null)):null;const smi=B?(D?D.pro:null):FC.smiP(st,y);
  const vT=B&&K.vacBase==='tabla'&&D&&D.T?numS(D.T.vacImporte):null;const base=B?(D&&hbB!=null?(vT!=null?vT:D.pro)*Math.min(1,hbB/FC.jornB(c)):null):(smi!=null&&hb!=null?smi*hb/40:null);
  const dev=Math.round(Math.min(vd,vd*cov/diy)*100)/100;
  let disfr=0,disfrNoPag=0,pagado=0;(c.vac.tuvo==='si'?c.vacaciones:[]).forEach(v=>{const va=pd(v.desde),vb=pd(v.hasta);if(va==null||vb==null||vb<va)return;const oa=Math.max(va,a),ob=Math.min(vb,b);const days=ob>=oa?Math.round((ob-oa)/DAY)+1:0;if(v.disfruto==='si'){disfr+=days;if(v.pagadas==='no')disfrNoPag+=days;}if(v.pagadas==='si'&&new Date(va).getUTCFullYear()===y)pagado+=numS(v.importe)||0;});
  /* dos formas de descontar: restar los días disfrutados (impD) o restar el dinero pagado por vacaciones (impM) */
  const pend=Math.round(Math.max(0,dev-disfr)*100)/100;const impD=base!=null?pend*base/30+disfrNoPag*base/30:null;const impM=base!=null?dev*base/30-pagado:null;
  rows.push({y,cov,dev,disfr,disfrNoPag,pagado,pend,hb:B?hbB:hb,base,impD,impM,imp:null,smi,anterior:false,vd,D});}
 const tot=k=>rows.reduce((s,r)=>s+(r[k]>0?r[k]:0),0);const totD=tot('impD'),totM=tot('impM');const hayD=rows.some(r=>r.disfr>0),hayM=rows.some(r=>r.pagado>0),ambas=hayD&&hayM;
 const elegido=ambas&&['dias','dinero'].includes(c.vac.metodo);const metodo=ambas?(elegido?c.vac.metodo:(totM>totD?'dinero':'dias')):(hayM?'dinero':'dias');
 rows.forEach(r=>{r.imp=metodo==='dinero'?r.impM:r.impD;});return {rows,total:metodo==='dinero'?totM:totD,totD,totM,ambas,metodo,elegido};};
/* los cálculos paso a paso, para el resumen (revisión y ficha en Word) */
FC.calcExplain=st=>{const c=st.c,T1=FC.calcT1(st),T2=FC.calcT2(st),S=[];const e2=x=>eurN(x)+' €',d2=x=>(Math.round(x*100)/100).toLocaleString('es-ES',{maximumFractionDigits:2});const MN=['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
 const fila=r=>{const nom=`${MN[r.m-1]} ${r.y}${r.cov<r.dim?` (${r.cov} días)`:''}`;if(r.deb==null)return `${nom}: no se calcula (${({smi:'SMI sin verificar',jornada:'falta la jornada de algún día'})[r.estado]||'faltan datos'}).`;
  if(r.D){const D=r.D,sepX=T1.metodo==='separado',J=FC.jornB(c),men=sepX?D.sin:D.pro;const orig=D.fuente==='convenio'?`convenio (tabla ${D.anio}${D.otroAnio?', la última publicada':''}): ${D.T&&numS(D.T.base)!=null?`base ${e2(numS(D.T.base))} + pluses ${e2(numS(D.T.pluses)||0)}`:`anual ${e2(D.anual)} / 12`}${sepX?'':` + prorrata de ${D.N} pagas de ${e2(D.paga)} (${D.N} × ${e2(D.paga)} / 12)`} = ${e2(men)}`:`${D.fuente}: SMI anual ${e2(D.smiA)}${sepX?` → ${e2(men)} al mes sin pagas`:` / 12 = ${e2(men)}`}`;
   return `${nom}: ${orig} · jornada: ${d2(r.efw)} h semanales de ${d2(J)} → ${d2(r.frac*100)} % → ${e2(men)} × ${d2(r.frac)}${r.cov<r.dim?` × ${Math.min(r.cov,30)} / 30`:''} = ${e2(r.deb)}. Percibido: ${r.perc!=null?e2(r.perc):'sin datos'}.${r.dif!=null?` Diferencia: ${e2(r.deb)} − ${e2(r.perc)} = ${e2(r.dif)}.`:''}${r.presc&&!c.abg.incluirPrescritos?' (Más de un año: no se suma.)':''}`;}
  const ef=Math.round(r.efw*10)/10,pr=Math.round(r.presw*10)/10,eP=Math.min(ef,40),pP=Math.min(pr+Math.max(ef-40,0),20),hp=eP+pP,men=r.smi*hp/40;
  return `${nom}: SMI ${e2(FC.SMI[r.y].m)}${T1.metodo==='separado'?' (sin prorrata de pagas extra)':` × 14 / 12 = ${e2(r.smi)}`} · horas que se pagan: ${d2(eP)} efectivas + ${d2(pP)} de presencia = ${d2(hp)} h (de ${d2(ef)} efectivas y ${d2(pr)} de presencia por semana) → ${e2(r.smi)} × ${d2(hp)} / 40 = ${e2(men)}${r.cov<r.dim?` × ${Math.min(r.cov,30)} / 30 = ${e2(r.deb)}`:''}. Percibido: ${r.perc!=null?e2(r.perc):'sin datos'}.${r.dif!=null?` Diferencia: ${e2(r.deb)} − ${e2(r.perc)} = ${e2(r.dif)}.`:''}${r.presc&&!c.abg.incluirPrescritos?' (Más de un año: no se suma.)':''}`;};
 S.push({titulo:'Tabla 1 · Diferencias salariales (mes a mes)',lineas:T1.rows.filter(r=>!r.esp).map(fila).concat([`Total: suma de las diferencias a favor = ${e2(T1.total)}.`])});
 if(T1.metodo==='separado')S.push({titulo:'Pagas extraordinarias (por separado)',lineas:(T1.pagas||[]).map(p=>`${p.y}: devengado = 2/12 de lo que debía percibir cada mes = ${p.dev!=null?e2(p.dev):'sin calcular'} · percibido como paga extra ${e2(p.cob)} → diferencia ${p.dif!=null?e2(p.dif):'—'}${p.cuenta?'':' (más de un año: no se suma)'}.`).concat([`Total pagas extraordinarias: ${e2(T1.totalPagas)}.`])});
 (T1.esp||[]).forEach(e=>{if(e.tipo==='ultimo')S.push({titulo:'Último mes trabajado',lineas:[fila(e.rows[0])]});else S.push({titulo:'Mes del alta en la Seguridad Social',lineas:e.rows.map(fila).concat([`Periodo del pago del ${fmt(e.a)} al ${fmt(e.b)}: debía percibir = la parte de cada mes que cae en el periodo (mensual × días / 30) = ${e.deb!=null?e2(e.deb):'sin calcular'}. Percibido: ${e2(e.perc)}${e.bruto!=null?' brutos':' netos'}.${e.dif!=null?` Diferencia: ${e2(e.dif)}.`:''}`])});});
 const din=T2.metodo==='dinero';S.push({titulo:'Tabla 2 · Vacaciones ('+(din?'restando el dinero pagado':'restando los días disfrutados')+')',lineas:T2.rows.map(r=>`${r.y}: ${r.cov} días trabajados → días generados = ${r.vd||30} × ${r.cov} / 360 = ${d2(r.dev)}${(r.vd||30)*r.cov/360>(r.vd||30)?` (máximo ${r.vd||30})`:''}${r.base!=null?(FC.esB(c)?` · base mensual = ${(c.conv||{}).vacBase==='tabla'?'importe fijo de las tablas':'salario mensual con prorrata de pagas'} ${e2(r.D&&r.D.pro||0)} × ${d2(r.hb)} h / ${d2(FC.jornB(c))} = ${e2(r.base)} · `:` · base mensual = ${e2(r.smi)} × ${d2(r.hb)} h / 40 = ${e2(r.base)} (horas semanales con un máximo de 40) · `)+(din?`importe = ${d2(r.dev)} × ${e2(r.base)} / 30 = ${e2(r.dev*r.base/30)} − ${e2(r.pagado)} pagados = ${e2(r.impM)}`:`disfrutados ${r.disfr} → pendientes ${d2(r.pend)} · importe = ${d2(r.pend)} × ${e2(r.base)} / 30 = ${e2(r.pend*r.base/30)}${r.disfrNoPag?` + ${r.disfrNoPag} días disfrutados sin pagar × ${e2(r.base)} / 30 = ${e2(r.disfrNoPag*r.base/30)} → total ${e2(r.impD)}`:''}`):' · no se calcula: SMI sin verificar'}.`).concat(T2.ambas?[`Comparación: restando los días disfrutados = ${e2(T2.totD)}; restando el dinero pagado = ${e2(T2.totM)}. Se usa ${din?'el dinero pagado':'los días disfrutados'}${T2.elegido?' (elegido)':' (la que da más)'}.`]:[]).concat([`Total vacaciones: ${e2(T2.total)}.`])});
 const t=FC.totales({T1,T2,c});S.push({titulo:'Totales',lineas:[t.lineas.map(([l,v])=>`${/^\(−\)/.test(l)?'− ':'+ '}${e2(v)} (${l.replace(/^\([+−]\)\s*(\d+\.\s*)?/,'')})`).join(' ')+` = Total principal ${e2(t.principal)}.`,`Mora del 10 %: ${e2(t.principal)} × 10 % = ${e2(t.mora)}.`,`Total pendiente: ${e2(t.principal)} + ${e2(t.mora)} = ${e2(t.total)}.`]});
 return S;};
FC.calcAut=c=>{const ini=pd(c.rel.inicio),fin=pd(FC.endRel(c));if(ini==null||fin==null||fin<ini)return null;const tot=Math.round((fin-ini)/DAY)+1;
 if(c.rel.autGlobal==='nunca')return {tot,con:0,sin:tot,nd:0};if(c.rel.autGlobal==='siempre')return {tot,con:tot,sin:0,nd:0};
 let con=0,sin=0;const seen=new Set();c.autorizacion.forEach(p=>{const a=pd(p.desde),b=pd(p.hasta||iso(fin));if(a==null||b==null)return;for(let t=Math.max(a,ini);t<=Math.min(b,fin);t+=DAY){if(seen.has(t))continue;seen.add(t);if(p.tipo==='con')con++;else if(p.tipo==='sin')sin++;}});return {tot,con,sin,nd:tot-con-sin};};
const dur=d=>{if(d==null)return '—';const y=Math.floor(d/365),m=Math.floor((d%365)/30.4);return [y?y+(y>1?' años':' año'):'',m?m+(m>1?' meses':' mes'):''].filter(Boolean).join(' y ')||d+' días';};
FC.dur=dur;

/* ---------------- evaluación ---------------- */
const isDesp=c=>c.fin.tipo==='despido';
FC.soloContacto=c=>c.filtro.abogado==='si'&&c.filtro.estudiar==='no';
const R=(s,p,l,cond)=>({s,p,l,cond});
FC.REQ=[R(0,'filtro.abogado','¿Otro abogado lleva el caso?'),R(0,'filtro.estudiar','¿Quiere que estudiemos su caso?',c=>c.filtro.abogado==='si'),R(0,'filtro.actuado','¿Ya hay papeleta o demanda?',c=>c.filtro.abogado==='cambiar'||c.filtro.estudiar==='si'),
 R(0,'filtro.reclamar','Qué quiere reclamar',c=>!FC.soloContacto(c)),R(0,'filtro.conocio','Cómo nos conoció'),R(4,'int.finReal','Internas: a qué hora terminaba realmente',c=>FC.esInterna(c)),R(4,'int.dormia','Internas: dónde dormía',c=>FC.esInterna(c)),R(4,'int.disponible','Internas: disponible después de acostarse',c=>FC.esInterna(c)),R(5,'sal.pagas','Pagas extra'),R(5,'sal.precioHora','Precio de la hora',c=>c.sal.porHoras==='si'),R(8,'pru.telefono','Si conserva el teléfono con las pruebas'),R(1,'cli.trato','Tratamiento'),R(1,'cli.nombre','Nombre'),R(1,'cli.apellidos','Apellidos'),R(1,'cli.doc','Documento'),R(1,'cli.docnum','Número de documento',c=>c.cli.doc&&c.cli.doc!=='ninguno'),R(1,'cli.emisorPais','País que emitió el documento',c=>c.cli.doc==='Pasaporte'&&!FC.pais(c.cli.pais)&&!c.cli.emisorPais),R(1,'cli.emisor','Quién emitió el documento',c=>c.cli.emisorPais==='otro'),R(1,'cli.pais','País de nacionalidad'),R(1,'cli.nacionalidad','Nacionalidad (gentilicio)',c=>c.cli.pais==='otra'),R(1,'cli.nac','Fecha de nacimiento'),R(1,'cli.tel','Teléfono'),R(1,'cli.email','Correo electrónico'),R(1,'cli.empadronada','Empadronamiento'),R(1,'cli.postalIgual','Dirección postal'),R(1,'cli.sindical','Cargo sindical'),
 R(2,'rel.inicio','Inicio de la relación'),R(2,'rel.contrato','Contrato verbal o escrito'),R(2,'rel.alta','Alta en la Seguridad Social'),R(2,'rel.autGlobal','Autorización de trabajo'),
 R(3,'tareas','Tareas'),
 R(5,'sal.fijo','¿Siempre la misma cantidad?'),R(5,'sal.importe','Salario mensual',c=>c.sal.fijo==='si'),R(5,'sal.forma','Forma de pago',c=>c.sal.fijo==='si'),
 R(6,'vac.tuvo','¿Tuvo vacaciones?'),
 R(7,'fin.tipo','¿Qué pasó con su trabajo?'),R(7,'fin.fechaCom','Día en que le comunicaron el despido',isDesp),R(7,'fin.fechaFin','Día en que dejó de trabajar',c=>['despido','renuncia','fallecimiento','otro'].includes(c.fin.tipo)),R(7,'fin.medio','Cómo le comunicaron el despido',isDesp),R(7,'fin.dicho','Qué le dijeron',isDesp),R(7,'fin.dia','Lo que pasó el día del despido',isDesp),R(7,'fin.fallQuien','Quién falleció',c=>c.fin.tipo==='fallecimiento'),R(7,'fin.burofax','¿Se envió burofax?',c=>['despido','fallecimiento','otro'].includes(c.fin.tipo)),
 R(8,'pru.llaves','Llaves de la vivienda'),R(8,'pru.audios','Audios o grabaciones')];
FC.evaluate=(st,hoy)=>{hoy=hoy||today();const c=st.c;const A=[],CX=[],INC=[],NSL=[];const al=(n,cod,t,d)=>A.push({nivel:n,cod,titulo:t,detalle:d});const cx=(id,t,d,s)=>CX.push({id,titulo:t,texto:d,s});
 const solo=FC.soloContacto(c);
 FC.REQ.forEach(r=>{if(r.cond&&!r.cond(c))return;if(FC.esB(c)&&FC.SOLO_C.includes(r.p))return;if(solo&&r.s>0&&!['cli.nombre','cli.tel','cli.email'].includes(r.p))return;if(c.ns[r.p]){NSL.push({p:r.p,l:r.l,s:r.s});return;}if(!has(getP(c,r.p)))INC.push({p:r.p,l:r.l,s:r.s});});
 if(!solo){
  const dirs=[['cli.dom','Dirección donde vive',1]];if(c.cli.empadronada==='si')dirs.push(['cli.padronDir','Dirección de empadronamiento',1]);if(c.cli.postalIgual==='no')dirs.push(['cli.postal','Dirección postal',1]);
  c.lugares.forEach((l,i)=>dirs.push([`lugares.${i}.dir`,'Lugar de trabajo '+(i+1),2]));c.empleadores.forEach((e,i)=>dirs.push([`empleadores.${i}.dom`,'Domicilio del empleador '+(i+1),2]));c.empleadores.forEach(e=>(e.otros||[]).forEach(id=>{const k=c.personas.findIndex(q=>q.id===id);if(k>=0&&!FC.dirVacia(c.personas[k].dom))dirs.push([`personas.${k}.dom`,'Domicilio de '+(FC.full(c.personas[k])||'otra persona empleadora'),2]);}));
  dirs.forEach(([p,l,s])=>{if(c.ns[p]){NSL.push({p,l,s});return;}const f=FC.dirFalta(getP(c,p));if(f.length)INC.push({p,l:`${l}: falta ${f.join(', ')}`,s});else if(!FC.dirComprobada(getP(c,p)))INC.push({p,l:`${l}: comprobar en Google Maps`,s});if(FC.dirCPmal(getP(c,p)))cx('cp_'+p,'Código postal de otra provincia',`«${l}»: el código postal ${getP(c,p).cp} no es de ${FC.provName(getP(c,p).prov)}.`,s);});
  
  if(c.rel.alta==='si')c.altas.forEach((a,i)=>{if((numS(a.pagoBruto)!=null||numS(a.pagoNeto)!=null)&&(pd(a.pagoDesde)==null||pd(a.pagoHasta)==null))INC.push({p:`altas.${i}.pagoDesde`,l:'Fechas que cubría el pago del mes del alta',s:5});});
  if(FC.esB(c)){const K=c.conv||{};c.empleadores.forEach((e,i)=>{const n=`Empresa ${i+1}`;if(e.tipoEmp==='fisica'&&(e.cif||'').trim()){const m=FC.nifCheck(e.cif);if(m)cx('nif_'+i,'NIF no válido',`${n}: ${m}`,2);}if(e.tipoEmp!=='fisica'){if(!(e.razon||'').trim())INC.push({p:`empleadores.${i}.razon`,l:`${n}: razón social`,s:2});if(!(e.cif||'').trim())INC.push({p:`empleadores.${i}.cif`,l:`${n}: CIF`,s:2});else{const m=FC.cifCheck(e.cif);if(m)cx('cif_'+i,'CIF no válido',`${n}: ${m}`,2);}if(!(e.actividad||'').trim())INC.push({p:`empleadores.${i}.actividad`,l:`${n}: actividad`,s:2});}});
   if(!((c.puesto||{}).categoria||'').trim())INC.push({p:'puesto.categoria',l:'Puesto: categoría o cargo',s:3});if(!((c.puesto||{}).funciones||'').trim())INC.push({p:'puesto.funciones',l:'Puesto: funciones reales',s:3});
   if(!(K.tablas||[]).some(t=>+t.anio&&(numS(t.base)!=null||numS(t.anual)!=null)))INC.push({p:'conv.tablas',l:'Convenio: tabla salarial de su categoría (si no, se calcula con el SMI)',s:3});
   const sinC=['nombre','categoria','tablas','jornada','pagas','vacaciones'].filter(k=>!(K.ok||{})[k]);if((K.nombre||(K.tablas||[]).length)&&sinC.length)A.push({nivel:'media',cod:'conv_ok',titulo:'Datos del convenio sin comprobar',detalle:`Falta marcar como comprobados: ${sinC.join(', ')}. Revíselos con el texto oficial (BOE o boletín) antes de presentar la papeleta.`});}
  {const m=FC.docCheck(c.cli.doc,c.cli.docnum);if(m)cx('doc_cli','Documento de la clienta no válido',m,1);}c.personas.forEach(q=>{const m=FC.docCheck(q.docTipo,q.docNum);if(m)cx('doc_'+q.id,'Documento no válido',`${FC.full(q)||'Una persona'}: ${m}`,2);});
  if(!c.empleadores.some(e=>e.titular))INC.push({p:'empleadores',l:'Empleador',s:2});c.empleadores.forEach((e,i)=>{const q=FC.per(c,e.titular);if(q&&!(q.nombre||'').trim())INC.push({p:`empleadores.${i}`,l:`Empleador ${i+1}: nombre`,s:2});if(q&&!(q.apellidos||'').trim())INC.push({p:`empleadores.${i}`,l:`Empleador ${i+1}: apellidos`,s:2});});
  if(!c.lugares.length)INC.push({p:'lugares',l:'Lugar de trabajo',s:2});
  if(c.rel.autGlobal==='parte'&&!c.autorizacion.some(a=>a.tipo&&a.desde))INC.push({p:'autorizacion',l:'Periodos con y sin autorización',s:2});
  if(c.rel.alta==='si'&&!c.altas.some(a=>a.alta))INC.push({p:'altas',l:'Fechas de alta en la Seguridad Social',s:2});
  c.empleadores.forEach((e,i)=>{const p=FC.per(c,e.titular);if(p&&!p.docNum)INC.push({p:`empleadores.${i}`,l:`Documento de ${p.nombre||'el empleador'}`,s:2});});
  if(['ninos','mayores','dependientes'].some(x=>c.tareas.includes(x))&&!c.cuidados.some(k=>k.persona))INC.push({p:'cuidados',l:'Personas que cuidaba',s:3});
  c.cuidados.forEach((k,i)=>{const p=FC.per(c,k.persona);if(p&&p.edad==='')INC.push({p:`cuidados.${i}`,l:'Edad de '+(p.nombre||'la persona cuidada'),s:3});if(p&&!FC.esMenor(c,k)&&!k.autonomia)INC.push({p:`cuidados.${i}`,l:'Nivel de dependencia de '+(p.nombre||'la persona cuidada'),s:3});});
  if(!c.periodos.length)INC.push({p:'periodos',l:'Periodo de jornada',s:4});
  c.periodos.forEach((p,i)=>{if(!p.desde)INC.push({p:`periodos.${i}`,l:`Periodo ${i+1}: fecha de inicio`,s:4});if(!p.modalidad)INC.push({p:`periodos.${i}`,l:`Periodo ${i+1}: interna, externa o mixta`,s:4});if(!p.semanas.some(w=>FC.diasDe(w).some(d=>d.tramos.some(t=>t.e&&t.s))))INC.push({p:`periodos.${i}`,l:`Periodo ${i+1}: horario de la semana modelo`,s:4});});
  if(c.sal.fijo==='no'&&!c.meses.length)INC.push({p:'meses',l:'Tabla de salarios mes a mes',s:5});
  if(c.vac.tuvo==='si'&&!c.vacaciones.some(v=>v.desde&&v.hasta))INC.push({p:'vacaciones',l:'Periodos de vacaciones',s:6});
  c.vacaciones.forEach((v,i)=>{if(c.vac.tuvo!=='si')return;['pagadas','disfruto'].forEach(k=>{if(!v[k])INC.push({p:`vacaciones.${i}`,l:`Vacaciones ${i+1}: ${k==='pagadas'?'¿se las pagaron?':'¿las disfrutó?'}`,s:6});});});
 }
 /* plazos */
 const f=c.filtro,F=c.fin;
 if(f.abogado==='si'&&f.estudiar==='no')al('media','solo_contacto','Caso con otro abogado: solo contacto','No quiere cambiar de abogado. Se guardan sus datos de contacto y no se completa la ficha.');
 if(['demanda','ambas'].includes(f.actuado))al('alta','demanda','Ya hay una demanda presentada',`Pedir copia${f.demFecha?' (presentada el '+fmt(f.demFecha)+')':''} y revisar lo actuado antes de presentar nada.`);
 if(f.abogado==='cambiar')al('alta','cambio_abogado','Quiere cambiar de abogado','Pedir la documentación de lo actuado y la venia antes de intervenir.');
 if(isDesp(c)&&!['demanda','ambas'].includes(f.actuado)){const base=SF.minDate([F.fechaCom,F.fechaFin]);
  if(!base)al('critica','sin_fecha','Despido sin fecha conocida','No consta cuándo se lo comunicaron ni el último día trabajado. El plazo para reclamar un despido es de 20 días hábiles: revisión del abogado hoy.');
  else if(pd(base)<=pd(hoy)){const cola=` Se cuenta desde ${fmt(base)}, de lunes a viernes, sin descontar festivos: es una estimación prudente, no una fecha de caducidad.`;
   const pap=['papeleta','ambas'].includes(f.actuado)?f.papFecha:null;
   if(['papeleta','ambas'].includes(f.actuado)&&!pap)al('alta','pap_sin_fecha','Papeleta anterior sin fecha','La papeleta suspende el plazo desde su presentación: hace falta la fecha del sello.'+cola);
   else if(pap&&pd(pap)>=pd(base)){const u1=SF.wd(base,pap);if(u1>=20)al('critica','cad_pre_pap','Posible caducidad antes de la papeleta anterior',`Pasaron ${u1} días laborables hasta la papeleta (${fmt(pap)}).`+cola);else al('alta','pap_susp','Papeleta anterior: plazo suspendido, recalcular',`Hasta la papeleta pasaron ${u1} días laborables. El cómputo se reanuda tras la conciliación o a los 15 días de presentarla (art. 65.1 LRJS).`+cola);}
   else{const u=SF.wd(base,hoy),q=20-u;if(u>=20)al('critica','cad_posible','Posible caducidad de la acción de despido',`Han pasado ${u} días laborables. Revisión inmediata.`+cola);else if(q<=6)al('critica','plazo_critico',`Plazo crítico: quedarían ${q} días hábiles o algo más`,'Presentar la papeleta en cuanto el abogado la revise.'+cola);else if(q<=12)al('alta','plazo_urgente',`Plazo urgente: quedarían ${q} días hábiles o algo más`,'Derivar hoy al abogado.'+cola);else al('media','plazo_curso',`Plazo en curso: quedarían ${q} días hábiles o algo más`,cola.trim());}}}
 if(F.firmo==='si')al('alta','firmo','Firmó un documento al salir',`${F.copia==='si'?'Tiene copia: subirla en Pruebas.':'No consta que tenga copia.'} Revisar los términos antes de presentar la papeleta.`);
 if(F.tipo==='fallecimiento')al('media','fallecimiento','Extinción por fallecimiento','Regla a validar por el abogado: un mes de salario si falleció el empleador (art. 49.1.g ET). No hay texto aprobado para este caso.');
 const J=FC.calcJ(c);J.overlaps.forEach(o=>{al('alta','solape','Dos periodos de jornada se solapan',`Periodos ${o.a+1} y ${o.b+1}: ${o.n} días entre ${fmt(o.desde)} y ${fmt(o.hasta)}. Esos días solo se cuentan una vez hasta que lo corrija.`);cx('solape_'+o.a+'_'+o.b,'Periodos de jornada solapados',`Periodos ${o.a+1} y ${o.b+1} (${fmt(o.desde)} a ${fmt(o.hasta)}).`,4);});
 const T1=FC.calcT1(st);(T1.esp||[]).forEach(e=>{if(e.parcial)cx('alta_parcial_'+e.i,'Periodo del pago del mes del alta',`El pago del ${fmt(e.a)} al ${fmt(e.b)} no cubre meses completos: los días de esos meses fuera de ese periodo no se reclaman. Revise las fechas.`,5);});const by=Object.keys(T1.blocked);if(by.length)al('media','smi','Salario mínimo sin verificar',`No hay importe comprobado para ${by.join(', ')}. Esos meses no se calculan hasta que el abogado lo confirme.`);
 if(T1.rows.some(r=>r.presc&&r.dif>0))al('alta','presc','Hay meses con más de un año','Las cantidades de más de un año pueden haber prescrito (art. 59.2 ET). Por defecto no se incluyen; lo decide el abogado.');
 const cuSemana=[];const JB=FC.esB(c)?FC.jornB(c):40;c.periodos.forEach((p,pi)=>p.semanas.forEach(s=>{const W=FC.semana(s);if(W.ef>JB)cuSemana.push(`periodo ${pi+1}, semana ${s.nombre}: ${n1(W.ef)} h efectivas`);if(W.pres>20)cuSemana.push(`periodo ${pi+1}, semana ${s.nombre}: ${n1(W.pres)} h de presencia`);}));
 if(cuSemana.length)al('media','jornada',FC.esB(c)?`Jornada por encima de la del convenio (${n1(JB)} h semanales)`:'Jornada por encima de los límites del art. 9 RD 1620/2011',cuSemana.join('; ')+'.'+(FC.esB(c)?' Las horas de más podrían reclamarse como horas extra: lo decide el abogado.':''));
 if(!solo&&st.c.fin.tipo){const O=FC.organismo(st);if(!O.ok)al('media','organismo','Organismo de conciliación pendiente',O.motivo==='sede'?'Falta elegir el municipio del lugar de trabajo o del domicilio del empleador.':`La tabla del despacho no tiene organismo para ${FC.provName(O.cpro)}: el abogado debe indicarlo.`);}
 if(c.cli.email&&!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(c.cli.email))INC.push({p:'cli.email',l:'Correo electrónico mal escrito',s:1});
 if(c.rel.alta==='si')c.altas.forEach((a,i)=>{if(a.alta&&!a.pagoMes&&!c.ns['altas.'+i+'.pagoMes'])INC.push({p:`altas.${i}`,l:`Alta ${i+1}: cuándo y cómo le pagaron el mes del alta`,s:2});});
 /* contradicciones */
 FC.ADULTO=p=>!!(p.m&&(p.m.titular||p.m.contrato||p.m.pago||p.m.ordenes||p.m.despidio))||FC.empleadoras(c).includes(p.id);
 c.personas.forEach((p,i)=>{if(p.edad===''||p.edad==null)return;const e=Number(p.edad);const min=FC.ADULTO(p)?18:0;if(!(e>=min&&e<=130))cx('edad_'+p.id,'Edad imposible',`${FC.full(p)||'Una persona'}: ${p.edad} años. ${min?'Quien contrata, paga, manda o es titular tiene que tener entre 18 y 130 años.':'La edad tiene que estar entre 0 y 130 años.'}`,2);});
 const ini=c.rel.inicio;[[F.fechaCom,'día en que le comunicaron el despido'],[F.fechaFin,'día en que dejó de trabajar'],[c.rel.fin,'fecha de fin']].forEach(([d,l])=>{if(ini&&d&&pd(ini)>pd(d))cx('ini_'+l,'Empezó después del final',`El inicio (${fmt(ini)}) es posterior al ${l} (${fmt(d)}).`,2);});
 [[ini,'inicio de la relación',2],[F.fechaFin,'día en que dejó de trabajar',7],[F.fechaCom,'día en que le comunicaron el despido',7]].forEach(([d,l,s])=>{if(d&&pd(d)>pd(hoy))cx('fut_'+l,'Fecha en el futuro',`${l.charAt(0).toUpperCase()+l.slice(1)}: ${fmt(d)}.`,s);});
 if(c.cli.nac&&ini&&SF.ageAt(c.cli.nac,ini)<16)cx('edad','Edad de inicio imposible','Según las fechas tenía menos de 16 años al empezar.',1);
 const fin=FC.endRel(c);c.periodos.forEach((p,i)=>{if(ini&&p.desde&&pd(p.desde)<pd(ini))cx('per_ini'+i,'Jornada antes del inicio',`El periodo ${i+1} empieza (${fmt(p.desde)}) antes que la relación (${fmt(ini)}).`,4);if(p.hasta&&fin&&pd(p.hasta)>pd(fin))cx('per_fin'+i,'Jornada después del final',`El periodo ${i+1} termina (${fmt(p.hasta)}) después del final de la relación (${fmt(fin)}).`,4);});
 const con=c.autorizacion.filter(a=>a.tipo==='con'),sin=c.autorizacion.filter(a=>a.tipo==='sin');con.forEach(a=>sin.forEach(b=>{const x=Math.max(pd(a.desde)||0,pd(b.desde)||0),y=Math.min(pd(a.hasta||fin)||0,pd(b.hasta||fin)||0);if(a.desde&&b.desde&&y>=x)cx('aut_'+a.id+b.id,'Con y sin autorización a la vez',`Hay fechas marcadas con y sin autorización (${fmt(iso(x))} a ${fmt(iso(y))}).`,2);}));
 c.altas.forEach((a,i)=>{if(a.alta&&a.baja&&pd(a.baja)<pd(a.alta))cx('alta'+i,'Baja anterior al alta',`Alta ${i+1}: baja ${fmt(a.baja)} antes del alta ${fmt(a.alta)}.`,2);});
 if(c.rel.alta==='si'&&c.rel.autGlobal==='nunca')cx('alta_aut','Alta sin autorización','Dice que estuvo de alta, pero que nunca tuvo autorización de trabajo. Comprobar con la vida laboral.',2);
 c.vacaciones.forEach((v,i)=>{if(ini&&v.desde&&pd(v.desde)<pd(ini))cx('vac'+i,'Vacaciones antes del inicio',`Periodo de vacaciones ${i+1} (${fmt(v.desde)}).`,6);if(v.desde&&v.hasta&&pd(v.hasta)<pd(v.desde))cx('vacf'+i,'Vacaciones con fechas al revés',`Periodo ${i+1}.`,6);});
 c.meses.forEach((m,i)=>{if(m.mes&&ini&&m.mes<ini.slice(0,7))cx('mes'+i,'Salario antes del inicio',`Mes ${m.mes} anterior al inicio de la relación.`,5);});
 return {alerts:A,contra:CX,inc:INC,ns:NSL,J,T1};};

/* ---------------- territorio: resultado A y B ---------------- */
FC.sedes=st=>{const c=st.c,o=[];c.lugares.forEach((l,i)=>{const m=FC.mun(l.dir.codm);if(m)o.push({k:'L:'+l.id,tipo:'Lugar de trabajo '+(i+1),dir:l.dir,m});});c.empleadores.forEach((e,i)=>{const m=FC.mun(e.dom.codm);const p=FC.per(c,e.titular);if(m)o.push({k:'E:'+e.id,tipo:'Domicilio de '+(p&&p.nombre?p.nombre:'empleador '+(i+1)),dir:e.dom,m});});return o;};
FC.sedeAuto=st=>{const S=FC.sedes(st);return S.find(x=>x.k.startsWith('L:'))||S[0]||null;};
FC.organismo=st=>{const c=st.c;const S=FC.sedes(st);let s=S.find(x=>x.k===c.abg.sede),auto=false;if(!s){s=FC.sedeAuto(st);auto=true;}if(!s)return {ok:false,motivo:'sede'};const cpro=s.m.cpro,ccaa=FC.ccaa(cpro);const o=FC.orgDe(cpro);return FC.orgOk(o)?{ok:true,cpro,ccaa,o,s,auto}:{ok:false,motivo:'org',cpro,ccaa,s,auto};};

/* ---------------- papeleta ---------------- */
FC.TAREAS=[['limpiar_casa','Limpiar la casa'],['limpiar_banos','Limpiar baños'],['limpiar_cocina','Limpiar cocina'],['lavar','Lavar ropa'],['planchar','Planchar'],['cocinar','Cocinar'],['compras','Hacer compras'],['ninos','Cuidar niños'],['mayores','Cuidar personas mayores'],['dependientes','Cuidar personas dependientes'],['citas','Acompañar a citas médicas'],['mascotas','Cuidar mascotas'],['pasear','Pasear mascotas'],['otras','Otras tareas']];
FC.TAREAP={limpiar_banos:'la limpieza de los baños',limpiar_cocina:'la limpieza de la cocina',lavar:'el lavado de la ropa',planchar:'el planchado',cocinar:'la preparación de las comidas',compras:'la realización de las compras',ninos:'el cuidado de los menores',mayores:'el cuidado de personas mayores',dependientes:'el cuidado de personas dependientes',citas:'el acompañamiento a citas médicas',mascotas:'el cuidado de las mascotas',pasear:'el paseo de las mascotas'};
FC.CUID=[['aseo','Aseo e higiene'],['vestir','Vestir'],['comida','Darle de comer'],['medicacion','Medicación'],['movilidad','Levantar, acostar o mover'],['colegio','Llevar y recoger del colegio'],['medico','Acompañar al médico'],['noche','Atención por la noche'],['deberes','Deberes y juegos'],['paseo','Paseos y compañía']];
FC.CUIDP={aseo:'su aseo e higiene personal',vestir:'vestirle',comida:'su alimentación',medicacion:'su medicación',movilidad:'levantarle, acostarle y movilizarle',colegio:'llevarle y recogerle del colegio',medico:'acompañarle al médico',noche:'atenderle por la noche',deberes:'ayudarle con los deberes',paseo:'sus paseos y compañía'};
FC.DIAG=[['alzheimer','Alzheimer o demencia'],['parkinson','Parkinson'],['ictus','Secuelas de un ictus'],['movilidad','Movilidad reducida'],['silla','Silla de ruedas'],['encamada','Encamada'],['incontinencia','Incontinencia'],['diabetes','Diabetes'],['corazon','Enfermedad del corazón'],['respiratoria','Oxígeno o enfermedad respiratoria'],['discapacidad','Discapacidad física o intelectual'],['mental','Enfermedad mental'],['sentidos','Problemas de vista u oído']];
FC.DIAGP={alzheimer:'Alzheimer u otra demencia',parkinson:'Parkinson',ictus:'secuelas de un ictus',movilidad:'movilidad reducida',silla:'necesidad de silla de ruedas',encamada:'encamamiento',incontinencia:'incontinencia',diabetes:'diabetes',corazon:'una enfermedad cardiaca',respiratoria:'una enfermedad respiratoria',discapacidad:'una discapacidad',mental:'una enfermedad mental',sentidos:'problemas de vista u oído'};
FC.AUT={independiente:'autónoma',leve:'con dependencia leve',moderada:'con dependencia moderada',severa:'con dependencia severa',total:'totalmente dependiente'};
FC.GRADO={no:'sin grado de dependencia reconocido',tramite:'con la valoración de dependencia en trámite',I:'con grado I de dependencia reconocido',II:'con grado II de dependencia reconocido',III:'con grado III de dependencia reconocido'};
FC.NOCHE={alguna:'alguna noche requería su atención',varias:'requería su atención varias veces cada noche',toda:'requería atención durante toda la noche'};
const ORD=['PRIMERO','SEGUNDO','TERCERO','CUARTO','QUINTO','SEXTO','SÉPTIMO','OCTAVO','NOVENO','DÉCIMO','UNDÉCIMO','DUODÉCIMO'];
const hm=(m,fin)=>{if(fin&&m>0&&m%1440===0)return '24:00h';m=((m%1440)+1440)%1440;return String(Math.floor(m/60)).padStart(2,'0')+':'+String(m%60).padStart(2,'0')+'h';};
/* descripción de una semana modelo con la forma del párrafo P024 */
FC.descSemana=s=>{const W=FC.semana(s);const work=W.D.map((d,i)=>({i,d})).filter(x=>x.d.first!=null);if(!work.length)return null;
 const groups=[];work.forEach(x=>{const g=groups[groups.length-1];const sig=x.d.first+'-'+x.d.last+'-'+Math.round(x.d.desc*60);if(g&&g.sig===sig&&g.to===x.i-1){g.to=x.i;}else groups.push({sig,from:x.i,to:x.i,d:x.d});});
 const gtxt=g=>`${g.from===g.to?'el '+DOWN[g.from]:(g.to-g.from===1?`${DOWN[g.from]} y ${DOWN[g.to]}`:`de ${DOWN[g.from]} a ${DOWN[g.to]}`)} desde las ${hm(g.d.first)} hasta las ${hm(g.d.last,true)}`;
 let libre='';if(W.maxAt&&W.maxGap>=1440){const a=W.maxAt[0],b=W.maxAt[1];const da=Math.floor((a%1440===0?a-1:a)/1440)%7,db=Math.floor(b/1440)%7;libre=`librando los ${DOWP[da]} desde las ${hm(a,true)} hasta el ${DOWN[db]} a las ${hm(b)}`;}else if(W.maxAt)libre='sin disfrutar de ningún día de descanso semanal';
 return {groups,uniform:groups.length===1,desc:Math.round(groups[0].d.desc*60),gtxt,libre,W};};
FC.pap=(st,hoy)=>{hoy=hoy||today();const c=st.c,E=FC.evaluate(st,hoy),T1=E.T1,T2=FC.calcT2(st);const fem=c.cli.trato!=='d';const g=(f,m)=>fem?f:m;
 const TR=g('La trabajadora','El trabajador'),tr=g('la trabajadora','el trabajador');
 const emps=FC.empleadoras(c).concat(FC.coempValidados(c)).map(id=>FC.per(c,id)).filter(Boolean);
 const pl=emps.length!==1;const e1=emps[0];
 const empArt=!emps.length?P('empleadores'):pl?'los empleadores':(e1.trato==='d'?'el empleador':'la empleadora');
 const alEmp=!emps.length?P('al empleador'):pl?'a los empleadores':(e1.trato==='d'?'al empleador':'a la empleadora');
 const vb=(p,s)=>pl?p:s;
 const out={head:[],hechos:[],nuevos:0};
 const org=FC.organismo(st);
 if(org.ok){out.head.push({k:'enc',text:org.o.enc1.toUpperCase(),st:'ok'});if(org.o.enc2)out.head.push({k:'enc',text:org.o.enc2.toUpperCase(),st:'ok'});}else out.head.push({k:'enc',text:'PENDIENTE DE VALIDACIÓN TERRITORIAL',st:'pend'});
 const doc=c.cli.doc,dn=c.cli.docnum;const D=SF.cfg.despacho;
 const up=s=>(s||'').trim().toUpperCase();const emi=()=>{const e=FC.emisorDe(c)||'';const m=/^(el|la|los|las)\s+(.+)$/i.exec(e);return m&&!/⟦/.test(e)?`${m[1]} ⟪${m[2].toUpperCase()}⟫`:`⟪${e}⟫`;};const conEm=doc==='Pasaporte'||doc==='NIE';
 out.head.push({k:'comp',st:'ok',text:`⟪${g('D.ª','D.')} ${up(c.cli.nombre)||P('nombre')} ${up(c.cli.apellidos)||P('apellidos')},⟫ mayor de edad, ${g('provista','provisto')} de ${doc&&doc!=='ninguno'?doc:P('documento')} núm. ⟪${dn||P('número')}${conEm?',':''}⟫${conEm?` emitido por ${emi()}`:''} y, con domicilio a efecto de notificaciones sito en ${D.dom}, teléfono: ${D.tel}, e-mail: ${D.email}, ante este centro comparece y como mejor en derecho proceda,`});
 out.head.push({k:'dice',st:'ok',text:'DICE:'});
 const cal=FC.califEf(c);const acum=FC.acumEf(c,T1,T2);const despide=isDesp(c);
 let materia;let mst='ok';if(despide){if(cal==='nulo')materia='DESPIDO NULO POR VULNERACIÓN DE DERECHOS FUNDAMENTALES Y SUBSIDIARIAMENTE IMPROCEDENTE'+(acum?', CON ACUMULACIÓN DE ACCIÓN DE RECLAMACIÓN DE CANTIDAD':'');else if(cal==='improcedente')materia='DESPIDO IMPROCEDENTE'+(acum?' CON ACUMULACIÓN DE RECLAMACIÓN DE CANTIDAD':'');else{materia=P('calificación del despido (abogado)');mst='pend';}}else materia='RECLAMACIÓN DE CANTIDAD';
 const empList=emps.length?emps.map(p=>`⟪${FC.trato(p)} ${up(p.nombre)||P('nombre')} ${up(p.apellidos)||P('apellidos')}⟫ ${p.trato==='d'?'provisto':'provista'} de ⟪${p.docTipo||P('documento')}⟫ núm. ⟪${p.docNum||P('número')},⟫ con domicilio sito en ${FC.fmtDir(FC.domDe(c,p.id),true)}`).join('; y '):P('empleadores');
 const esB=FC.esB(c);
 /* ficha B: la mercantil (o la persona física) a la que se cita */
 const empsB=esB?c.empleadores.map(e=>({e,adm:FC.per(c,e.titular)})).filter(x=>x.e.razon||x.adm):[];const jur=x=>x.e.tipoEmp!=='fisica';
 const LM=!esB?empArt:empsB.length>1?(empsB.every(jur)?'las mercantiles':'los empleadores'):empsB.length&&!jur(empsB[0])?(empsB[0].adm&&empsB[0].adm.trato==='d'?'el empleador':'la empleadora'):'la mercantil';
 const descEmpB=x=>{const d=FC.fmtDir(x.e.dom,true);if(!jur(x)){const q=x.adm;return `${q&&q.trato==='d'?'el empleador':'la empleadora'} ⟪${FC.trato(q)} ${up(q&&q.nombre)||P('nombre')} ${up(q&&q.apellidos)||P('apellidos')}⟫ ${q&&q.trato==='d'?'provisto':'provista'} de ⟪${(q&&q.docTipo)||P('documento')}⟫ núm. ⟪${(q&&q.docNum)||P('número')},⟫ con domicilio sito en ${d}`;}
  const q=x.adm;return `la mercantil ⟪${up(x.e.razon)||P('razón social')},⟫ provista de ⟪CIF⟫ núm. ⟪${(x.e.cif||'').toUpperCase()||P('CIF')}⟫ y con ${q&&q.trato==='da'?'la administradora':'el administrador'} de la misma ⟪${q?FC.trato(q)+' '+(up(q.nombre)||P('nombre'))+' '+(up(q.apellidos)||P('apellidos')):P('administrador')},⟫ con domicilio sito en ${d}, dedicado a la actividad de ${(x.e.actividad||'').trim()||P('actividad')}`;};
 const coB=esB?FC.coempValidados(c).map(id=>FC.per(c,id)).filter(Boolean).map(q=>`⟪${FC.trato(q)} ${up(q.nombre)||P('nombre')} ${up(q.apellidos)||P('apellidos')}⟫ ${q.trato==='d'?'provisto':'provista'} de ⟪${q.docTipo||P('documento')}⟫ núm. ⟪${q.docNum||P('número')},⟫ con domicilio sito en ${FC.fmtDir(FC.domDe(c,q.id),true)}`):[];
 if(esB)out.head.push({k:'p',st:empsB.length===1&&jur(empsB[0])&&!coB.length?mst:'nuevo',text:`Que interesa de este centro el intento de celebración de conciliación obligatoria por ⟪${materia}⟫ con ${empsB.length?empsB.map(descEmpB).concat(coB).join('; y '):P('empresa')}.`});
 else out.head.push({k:'p',st:mst,text:`Que interesa de este centro el intento de celebración de conciliación obligatoria por ⟪${materia}⟫ con ${empArt} ${empList}.`});
 const H=(titulo,paras)=>{if(paras.length)out.hechos.push({titulo,paras});};
 const p=(text,st,bold)=>({text,st:st||'ok',bold:!!bold});
 if(esB){/* ===== papeleta B, según el escrito de ejemplo de régimen general ===== */
  const K=c.conv||{},aTr=g('a la trabajadora','al trabajador'),convN=(K.nombre||'').trim()||P('convenio colectivo aplicable');const sepB=T1.metodo==='separado';
  const yFin=+(FC.endRel(c)||hoy).slice(0,4);const D=FC.salB(st,yFin);const eI=x=>Number.isInteger(Math.round(x*100)/100)?Math.round(x).toLocaleString('es-ES'):eurN(x);
  /* PRIMERO */
  const P1=[p(`${TR} inició su relación laboral con ${LM} en fecha ${dmy(c.rel.inicio)||P('fecha de inicio')}.`),p(`Que ${g('la misma','el mismo')} fue ${g('contratada','contratado')} como ⟪${up((c.puesto||{}).categoria)||P('categoría')}${K.grupo?' ('+up(K.grupo)+')':''}⟫ según clasificación profesional establecida en el ${convN}.`)];
  if(!D)P1.push(p(P('salario: SMI del año sin verificar'),'pend'));
  else if(D.fuente==='convenio'&&D.T&&numS(D.T.base)!=null){const T=D.T;const L=[`Salario base: ⟪${eurN(numS(T.base))} €⟫`];if(numS(T.pluses))L.push(`Pluses y complementos del convenio${K.pluses?' ('+K.pluses.trim().replace(/\.$/,'')+')':''}: ⟪${eurN(numS(T.pluses))} €⟫`);if(!sepB)L.push(`Prorrata de gratificaciones extraordinarias: ⟪${eurN(D.N*D.paga/12)} €⟫`);
   P1.push(p(`De conformidad con los anexos de las tablas salariales del citado convenio, ${tr} tenía derecho a percibir mensualmente los siguientes conceptos:`));P1.push({lista:L,st:'ok'});
   P1.push(sepB?p(`Resultando un ⟪salario mensual bruto total de ${eurN(D.sin)} euros⟫, más ${D.N} pagas extraordinarias de ${eurN(D.paga)} euros cada una.`,'nuevo'):p(`Resultando un ⟪salario mensual bruto total de ${eurN(D.pro)} euros⟫.`));}
  else if(D.fuente==='convenio')P1.push(p(`Según las tablas salariales del convenio aplicable, ${tr} debía percibir ⟪un salario bruto anual de ${eurN(D.anual)} euros⟫, por lo que el ⟪salario mensual⟫, incluyendo la prorrata de pagas extraordinarias, asciende a ⟪${eurN(D.pro)}⟫ euros, resultante de dividir dicha cuantía anual entre los 12 meses del ejercicio.`));
  else P1.push(p(`Al no alcanzar ${D.T?'las tablas salariales del citado convenio':'el salario de su categoría'} el salario mínimo interprofesional, ${tr} debía percibir como mínimo ⟪un salario bruto anual de ${eurN(D.anual)} euros⟫, conforme al Real Decreto que fija el salario mínimo interprofesional para ${yFin}, por lo que el ⟪salario mensual⟫, incluyendo la prorrata de pagas extraordinarias, asciende a ⟪${eurN(D.pro)}⟫ euros.`,'nuevo'));
  H('ANTIGÜEDAD, CATEGORÍA Y SALARIO.',P1);
  /* SEGUNDO */
  const aut=c.rel.autGlobal,alta=c.rel.alta,gen=FC.gent(c)||P('nacionalidad'),cont=c.rel.contrato==='escrito'?'escrito':c.rel.contrato==='verbal'?'verbal':P('verbal o escrito');const P2=[];
  if(aut==='siempre')P2.push(p(`${g('La compareciente','El compareciente')}, de nacionalidad ${gen}, fue ${g('contratada','contratado')}${c.rel.inicio?' en fecha ⟪'+dmy(c.rel.inicio)+'⟫':''}${c.rel.fin?' hasta ⟪'+dmy(c.rel.fin)+'⟫':''} mediante contrato ${cont}, de carácter indefinido y a tiempo completo, en virtud del art. 8.1 del Estatuto de los Trabajadores.`,c.rel.contrato==='escrito'?'ok':'nuevo'));
  else{P2.push(p(`${g('La compareciente','El compareciente')} de nacionalidad ${gen}, inicialmente ⟪fue ${g('contratada','contratado')} de forma irregular⟫ ⟪(careciendo de permiso de residencia y trabajo),⟫ mediante contrato ${cont} y con carácter indefinido, en virtud del art. 8.1 del Estatuto de los Trabajadores, sin haberse procedido a la correspondiente alta en la Tesorería General de la Seguridad Social como ${g('trabajadora','trabajador')}.`,c.rel.contrato==='verbal'?'ok':'nuevo'));
   const al=c.altas.filter(a=>a.alta);if(alta==='si'&&al.length)P2.push(p(`Con posterioridad, ${tr} obtuvo el permiso de residencia y trabajo siendo ${g('dada','dado')} de alta en la Tesorería General de la Seguridad Social en fecha ⟪${dmy(al[0].alta)}⟫ hasta ⟪${dmy(al[al.length-1].baja)||P('fecha de baja')}⟫ mediante contrato ${cont}, de carácter indefinido y a tiempo completo, en virtud del art. 8.1 del Estatuto de los Trabajadores.`,aut==='parte'?'ok':'nuevo'));}
  H('FORMA DE LA CONTRATACIÓN.',P2);
  /* TERCERO */
  const P3=[];const pers=c.periodos.filter(x=>x.desde);
  if(pers.length===1&&FC.descSemana(pers[0].semanas[0])){const ds=FC.descSemana(pers[0].semanas[0]);const W=ds.W;const hc=numS(c.rel.horasContrato),ha=numS(c.rel.horasAlta),J=FC.jornB(c);
   let t=`${TR} prestaba sus servicios por cuenta de ${LM} con una jornada laboral ${ds.groups.map(ds.gtxt).join(', y ').replace(/^el /,'de ')}${ds.desc?`, con un descanso de ${ds.desc} minutos`:''}${ds.libre?', '+ds.libre:''}, sumando así ${n1(W.ef)} horas semanales.`;
   if(hc!=null&&W.ef>hc)t+=` La jornada laboral que realizaba ${tr}, excedía de las horas previstas en el contrato celebrado por ambas partes, el cual estipulaba ${n1(hc)} horas semanales.`;
   if(ha!=null)t+=` Siendo además que el empleador dio de alta ${aTr} en la seguridad social como si realizase una jornada laboral de ${n1(ha)} horas.`;
   if(W.ef>J)t+=` La jornada laboral que realizaba ${tr}, excedía de las horas previstas según Convenio Colectivo aplicable.`;
   P3.push(p(t,ds.uniform&&pers[0].semanas.length===1?'ok':'nuevo'));}
  else if(pers.length)P3.push(p(`${TR} prestaba sus servicios por cuenta de ${LM} con la siguiente jornada: ${pers.map(x=>{const d=FC.descSemana(x.semanas[0]);const r=E.J.per.find(q=>q.id===x.id);return `del ${dmy(x.desde)} al ${dmy(r&&r.hasta)}${d?', '+d.groups.map(d.gtxt).join(', ')+(d.libre?', '+d.libre:''):''}${r&&r.days?`, con un promedio de ${n1(r.ef/(r.days/7))} horas semanales`:''}`;}).join('; ')}.`,'nuevo'));
  else P3.push(p(P('jornada: falta el periodo de jornada'),'pend'));
  const cargo=((c.puesto||{}).categoria||'').trim()||P('cargo'),fun=((c.puesto||{}).funciones||'').trim().replace(/\.$/,'')||P('funciones');const lug=c.lugares.filter(l=>!FC.dirVacia(l.dir));const e0=c.empleadores[0];const dsoc=e0&&!FC.dirVacia(e0.dom)?e0.dom:null;
  if(lug.length===1&&!(dsoc&&FC.dirSig(dsoc)===FC.dirSig(lug[0].dir)))P3.push(p(`${TR}, realizaba funciones propias de ${cargo}, tales como ${fun}, entre otras, en el centro de trabajo sito en ${FC.fmtDir(lug[0].dir,true)}.`));
  else{P3.push(p(`${TR}, realizaba funciones propias de ${cargo}, tales como ${fun}, entre otras, recibiendo ${tr} las órdenes pertinentes desde el domicilio social de la empresa sito en ${dsoc?FC.fmtDir(dsoc,true):P('domicilio social')}.`));
   if(lug.length>1||(lug.length===1&&dsoc&&FC.dirSig(dsoc)!==FC.dirSig(lug[0].dir)))P3.push(p(`Pasando a detallar esta parte algunas de las obras en las que participó ${tr} por orden de los empleadores, a título enunciativo, no limitativo: ${lug.map(l=>FC.fmtDir(l.dir,true)).join('; ')}.`));}
  H('JORNADA, CENTRO DE TRABAJO Y FUNCIONES.',P3);
  /* CUARTO */
  const FP={efectivo:'efectivo metálico',transferencia:'transferencias bancarias',bizum:'Bizum',otra:P('forma de pago')};const P4=[];
  if(c.sal.fijo==='si'){const imp=numS(c.sal.importe);P4.push(p(`Que, ${tr} percibía un salario mensual de ${imp!=null?eI(imp)+',-':P('importe')} euros, en ${listY((c.sal.forma||[]).map(f=>FP[f]).filter(Boolean))||P('forma de pago')}.`));}
  else if(c.sal.fijo==='no'){const M=c.meses.filter(m=>m.mes).sort((a,b)=>a.mes<b.mes?-1:1);const tot=m=>m.nocobro?0:(numS(m.salario)||0)+(numS(m.extra)||0);const fs=[...new Set(M.map(m=>m.forma).filter(Boolean))].map(f=>FP[f]).filter(Boolean);
   P4.push(p(`Que, ${tr} percibía un salario mensual variable en el periodo indicado, recibiendo ${M.map(m=>`en ${MESC[+m.mes.slice(5,7)-1].toLowerCase()} ${m.mes.slice(0,4)} la cantidad de ${eI(tot(m))},- euros`).join('; ')||P('importes de cada mes')}. Estas cantidades fueron abonadas mediante ${listY(fs)||P('forma de pago')}.`));}
  else P4.push(p(P('salario percibido'),'pend'));
  H('SALARIO PERCIBIDO.',P4);
  /* QUINTO */
  const F=c.fin,P5=[];const MED={carta:'carta',email:'correo electrónico',burofax:'burofax',whatsapp:'WhatsApp',telefono:'llamada telefónica',otro:P('medio')};
  if(F.tipo==='despido'){if(F.medio==='verbal'||!F.medio)P5.push(p(`Que en fecha ${dmy(F.fechaCom)||P('fecha')} ${LM} despidió verbalmente ${aTr} sin alegar causa justa.`,F.medio?'ok':'pend'));
   else P5.push(p(`Que, en fecha ${dmy(F.fechaCom)||P('fecha')} ${LM} notificó ${aTr} el despido por medio de ${MED[F.medio]||P('medio')} con efecto en fecha ${dmy(F.fechaFin)||P('fecha de efectos')}${F.motivo==='si'?` basándose en ${(F.dicho||'').trim().replace(/\.$/,'')||P('motivos')}, los cuales esta parte no reconoce`:', sin alegar causa justa'}.`,['carta','email'].includes(F.medio)&&F.motivo==='si'?'ok':'nuevo'));}
  else if(F.tipo==='renuncia')P5.push(F.renMedio==='escrito'?p(`Que en fecha ${dmy(F.fechaFin)||P('fecha')} ${tr} renunció por carta escrita a su puesto de trabajo.`):p(`Que en fecha ${dmy(F.fechaFin)||P('fecha')} ${tr} renunció a su puesto de trabajo, debido a las condiciones laborales del mismo.`));
  else if(F.tipo&&F.tipo!=='continua')P5.push(p(`Que en fecha ${dmy(F.fechaFin)||P('fecha')} finalizó la relación laboral${F.tipo==='fallecimiento'?' por fallecimiento del empleador':''}.`,'nuevo'));
  if(P5.length)H('NOTIFICACIÓN DEL FIN DE LA RELACIÓN LABORAL',P5);
  /* SEXTO */
  if(F.burofax==='si'&&F.tipo!=='continua')H('ENVÍO DE BUROFAX.',[!F.burRes||F.burRes==='sinresp'?p(`Que en fecha ${dmy(F.burFecha)||P('fecha')} se envió burofax a ${LM} solicitando carta de despido o readmisión y no se han tenido noticias.`):p(`Que en fecha ${dmy(F.burFecha)||P('fecha')} se envió burofax a ${LM} solicitando carta de despido o readmisión, ${({respondio:'que fue respondido',rehusado:'que fue rehusado',noretirado:'que no fue retirado'})[F.burRes]}.`,'nuevo')]);
  /* SÉPTIMO */
  if(despide){if(cal==='improcedente')H('DESPIDO IMPROCEDENTE.',[p(`Al efectuarse el despido incumpliendo los requisitos de forma establecidos legalmente en los artículos 55.1 del Estatuto de los Trabajadores y 108 de la LRJS, esta parte considera el mismo improcedente al producirse indefensión ${g('de la trabajadora','del trabajador')}.`)]);
   else if(cal==='nulo')H('DESPIDO NULO.',[p(`Esta parte considera que el despido debe ser calificado como nulo por ${P('causa de nulidad')}, y subsidiariamente como improcedente.`,'nuevo')]);}
  /* OCTAVO */
  const cantidad=acum||['renuncia','continua','otro','fallecimiento'].includes(F.tipo);
  if(cantidad){const P8=[p(`A la fecha ${despide?'del despido':'de la presente'}, ${LM} ${vb('adeudan','adeuda')} ${aTr} las cantidades que se detallan a continuación, calculadas según el ${convN}.`,despide?'ok':'nuevo')];
   const debM=D?(sepB?D.sin:D.pro):null;const perc=c.sal.fijo==='si'&&numS(c.sal.importe)!=null?eurN(numS(c.sal.importe))+' €/mes':'variable';
   P8.push(p(`El importe que ${tr} debía haber percibido mensualmente es el señalado en el Hecho Primero del presente escrito (${debM!=null?eurN(debM)+' €/mes':P('importe')}), mientras que las cantidades efectivamente percibidas son las que ${LM} le abonaba en ${listY((c.sal.forma||[]).map(f=>FP[f]).filter(Boolean))||'efectivo metálico y transferencia bancaria'} señaladas en el Hecho Cuarto (${perc}), generando una diferencia salarial cuya acumulación se detalla a continuación:`));
   if(FC.parrPagados({T1,c}))P8.push(p(FC.parrPagados({T1,c}),'ok'));
   P8.push({tabla:'T1',st:'ok'});
   (T1.esp||[]).filter(e=>e.cuenta).forEach(e=>{P8.push(p(e.tipo==='ultimo'?`Que en el último mes trabajado, ${tr} ${c.sal.ultimoMes==='no'?'no percibió cantidad alguna en concepto de salario':`percibió ${e.perc!=null?eurN(e.perc)+' €':P('importe')} en concepto de salario de los días trabajados`}. La diferencia salarial de ese mes se detalla en la tabla siguiente:`:`Que en el periodo del ${dmy(e.a)} al ${dmy(e.b)}, correspondiente al mes en que se dio de alta a ${tr} en la Seguridad Social, ${g('esta','este')} percibió ${[e.bruto!=null?eurN(e.bruto)+' € brutos':'',e.neto!=null?eurN(e.neto)+' € netos':''].filter(Boolean).join(' (')+(e.bruto!=null&&e.neto!=null?')':'')}. La diferencia salarial de ese periodo se detalla en la tabla siguiente:`,'nuevo'));P8.push({tabla:'X',t:FC.tablaEsp(c,e),st:'ok'});});
   const hayP=sepB&&(T1.pagas||[]).some(x=>x.cuenta);const t2=FC.tabla2({T2,c});
   if(hayP){const tp=FC.tablaPagas({T1,c});tp.titulo=tp.titulo.replace(/^3\./,'2.');t2.titulo=t2.titulo.replace(/^2\./,'3.');P8.push(p('A efectos del cálculo de la remuneración de las pagas extraordinarias devengadas y no percibidas durante el periodo detallado, la base retributiva aplicable consiste en ⟪la cantidad fija en las tablas de los anexos del convenio colectivo de aplicación⟫, según los importes vigentes en cada ejercicio y que se detallan a continuación:'));P8.push({tabla:'X',t:tp,st:'ok'});}
   P8.push(p(K.vacBase==='tabla'?'A efectos del cálculo de la remuneración de las vacaciones devengadas y no disfrutadas durante todo el periodo reclamado, la base retributiva aplicable consiste en ⟪la cantidad fija en las tablas de los anexos del convenio colectivo de aplicación⟫, según los importes vigentes en cada ejercicio y que se detallan a continuación:':'A efectos del cálculo de la remuneración de las vacaciones devengadas y no disfrutadas durante todo el periodo reclamado, la base retributiva aplicable se fija en cada anualidad conforme a la suma del ⟪salario base mensual más la prorrata de pagas extraordinarias⟫, según los importes vigentes en cada ejercicio y que se detallan a continuación:'));
   P8.push({tabla:'X',t:t2,st:'ok'});P8.push({tabla:'TOT',st:'ok'});H('CANTIDADES RECLAMADAS.',P8);}
  /* NOVENO y DÉCIMO */
  if(acum&&despide)H('ACUMULACIÓN DE ACCIONES.',[p(`De conformidad con lo dispuesto en el artículo 26 de la Ley Reguladora de la Jurisdicción Social, ${tr} podrá acumular a la acción de despido la reclamación de las cantidades vencidas, exigibles y de cuantía determinada adeudadas hasta dicha fecha, procediendo dicha acumulación al derivar ambas acciones de la misma relación laboral.`)]);
  H('REPRESENTACIÓN SINDICAL',[c.cli.sindical==='no'?p(`Que ${tr} no ha ostentado en el último año cargo sindical de ningún tipo.`):c.cli.sindical==='si'?p(`Que ${tr} ha ostentado en el último año ${P('cargo sindical o de representación')}.`,'nuevo'):p(P('cargo sindical en el último año'),'pend')]);
  out.hechos.forEach((h,i)=>h.n=ORD[i]||String(i+1));
  const allB=out.head.concat(...out.hechos.map(h=>h.paras));out.nuevos=allB.filter(x=>x.st==='nuevo').length;out.pend=allB.filter(x=>x.st==='pend').length;
  out.T1=T1;out.T2=T2;out.E=E;out.c=c;return out;}
 /* PRIMERO */
 const per=E.J.per.filter(r=>r.ok);const P1=[p(`${TR} inició su relación laboral con ${empArt} en fecha ${dmy(c.rel.inicio)||P('fecha de inicio')}.`),p(`Que ${g('la misma','el mismo')} fue ${g('contratada','contratado')} como ${g('EMPLEADA','EMPLEADO')} DEL HOGAR según Real Decreto 1620/2011, de 14 de noviembre, por el que se regula la relación laboral de carácter especial del servicio del hogar familiar.`),
  p('El artículo 9.1 de la citada norma determina claramente que “La jornada máxima semanal de carácter ordinario será de cuarenta horas de trabajo efectivo, sin perjuicio de los tiempos de presencia, (…).”.','ok',true),
  p('Asimismo, el artículo 9.2 del Real Decreto establece que “(…) las horas de presencia no podrán exceder de veinte horas semanales de promedio en un periodo de referencia de un mes y SE RETRIBUIRÁN CON UN SALARIO DE CUANTÍA NO INFERIOR AL CORRESPONDIENTE A LAS HORAS ORDINARIAS.”','ok',true)];
 const sepP=T1.metodo==='separado',PR=sepP?'(sin incluir la prorrata de pagas extraordinarias)':'(incluida prorrata)',smiS=y=>{const v=FC.smiP(st,y);return v!=null&&sepP?v*12/14:v;};
 const yFin=+(FC.endRel(c)||hoy).slice(0,4);const smiF=smiS(yFin);
 if(per.length===1){const r=per[0];const wk=r.days/7;const efw=r.ef/wk,prw=r.pres/wk;
  if(FC.horasPag(efw,prw)>=60-1e-9)P1.push(p(`En virtud del artículo 8.1 del referido Real Decreto se establece como retribución mensual el salario mínimo interprofesional de ${smiF!=null?eurN(smiF):P('SMI del año sin verificar')} euros ${PR} para una jornada laboral de 40 horas semanales por lo que, tomando en cuenta que la jornada legalmente establecida es de 40 horas semanales y los tiempos de presencia ascienden a un total de 20 horas semanales, sumando así un total de 60 horas, ${tr} debía percibir un salario mensual de ${smiF!=null?eurN(smiF*1.5):P('importe')} euros ${PR}, aunque ${tr} en realidad realizaba una jornada de ${n1(efw+prw)} horas semanales.`,sepP?'nuevo':'ok'));
  else P1.push(p(`En virtud del artículo 8.1 del referido Real Decreto se establece como retribución mensual el salario mínimo interprofesional de ${smiF!=null?eurN(smiF):P('SMI del año sin verificar')} euros ${PR} para una jornada laboral de 40 horas semanales por lo que, tomando en cuenta que ${tr} realizaba ${n1(efw)} horas semanales de trabajo efectivo${prw?' y '+n1(prw)+' horas de presencia':''}, debía percibir un salario mensual de ${smiF!=null?eurN(smiF*FC.horasPag(efw,prw)/40):P('importe')} euros ${PR}.`,'nuevo'));}
 else if(per.length>1)P1.push(p(`En virtud del artículo 8.1 del referido Real Decreto, el salario mínimo interprofesional ${PR} debe aplicarse a la jornada efectivamente realizada en cada periodo: ${per.map(r=>{const wk=r.days/7;const y=+(r.hasta||hoy).slice(0,4);const s=smiS(y);return `del ${dmy(r.desde)} al ${dmy(r.hasta)}, ${n1(r.ef/wk)} horas semanales de trabajo efectivo${r.pres?' y '+n1(r.pres/wk)+' de presencia':''}${s!=null?`, por lo que debía percibir ${eurN(s*FC.horasPag(r.ef/wk,r.pres/wk)/40)} euros mensuales con el SMI de ${y}`:''}`;}).join('; ')}.`,'nuevo'));
 else P1.push(p(P('jornada y salario que debía percibir: falta la jornada'),'pend'));
 H('ANTIGÜEDAD, CATEGORÍA Y SALARIO.',P1);
 /* SEGUNDO */
 const aut=c.rel.autGlobal;const alta=c.rel.alta;const P2=[];
 const gen=FC.gent(c)||P('nacionalidad');
 if(aut==='nunca'&&c.rel.contrato==='verbal'&&alta==='no')P2.push(p(`${g('La compareciente','El compareciente')} de nacionalidad ${gen}, fue ${g('contratada','contratado')} de forma irregular (careciendo de permiso de residencia y trabajo), mediante contrato verbal y con carácter indefinido, en virtud del art. 8.1 del Estatuto de los Trabajadores, sin haberse procedido a la correspondiente alta en la seguridad social como ${g('trabajadora','trabajador')}.`,'ok',true));
 else{let t=`${g('La compareciente','El compareciente')} de nacionalidad ${gen}, fue ${g('contratada','contratado')} ${aut==='nunca'?'de forma irregular (careciendo de permiso de residencia y trabajo), ':''}mediante contrato ${c.rel.contrato==='escrito'?'escrito':c.rel.contrato==='verbal'?'verbal':P('verbal o escrito')} y con carácter indefinido, en virtud del art. 8.1 del Estatuto de los Trabajadores${alta==='no'?`, sin haberse procedido a la correspondiente alta en la seguridad social como ${g('trabajadora','trabajador')}`:''}.`;
  if(aut==='parte')t+=' '+c.autorizacion.filter(a=>a.tipo&&a.desde).map(a=>`Del ${dmy(a.desde)} al ${dmy(a.hasta)||'final de la relación'} ${a.tipo==='con'?'contaba':'carecía'} de autorización de trabajo${a.permiso&&a.tipo==='con'?' ('+a.permiso+')':''}.`).join(' ');
  else if(aut==='siempre')t+=` Durante toda la relación ${g('la trabajadora','el trabajador')} contaba con autorización de trabajo.`;
  if(alta==='si')t+=' '+(c.altas.filter(a=>a.alta).map(a=>`Consta de alta en la Seguridad Social desde el ${dmy(a.alta)}${a.baja?' hasta el '+dmy(a.baja):''}.`).join(' ')||P('fechas de alta'));
  P2.push(p(t,'nuevo',true));}
 H('FORMA DE LA CONTRATACIÓN.',P2);
 /* TERCERO */
 const P3=[];const pers=c.periodos.filter(x=>x.desde);
 if(pers.length===1){const x=pers[0];const ds=FC.descSemana(x.semanas[0]);const r=per[0];
  if(ds&&x.semanas.length===1){const W=ds.W;const ok=W.ef>=40&&W.ef+W.pres>40;const lit=ok&&ds.uniform&&x.modalidad==='interna'&&!/^sin /.test(ds.libre);const first=ds.uniform?`realizando una jornada ${ds.gtxt(ds.groups[0]).replace(/^el /,'de ')}`:`realizando una jornada ${ds.groups.map(ds.gtxt).join(', y ')}`;
   P3.push(p(`${TR} prestaba sus servicios por cuenta de ${empArt} con una jornada laboral con carácter de ${FC.modTxt(x.modalidad)}, ${first}, ${ds.desc?`con un descanso de ${ds.desc} minutos, `:''}${/^sin /.test(ds.libre)?'':'y '}${ds.libre||P('días libres')}, sumando así un total de ${n1(W.ef+W.pres)} horas semanales, ${ok?'que incluyen las 40h de trabajo efectivo más el resto de horas de presencia superando así de esta manera la jornada laboral y tiempo de presencia legalmente establecido en el artículo 9 del Real Decreto.':`de las cuales ${n1(W.ef)} son de trabajo efectivo${W.pres?' y '+n1(W.pres)+' de presencia':''}${W.ef>40||W.pres>20?', superando así la jornada laboral y tiempo de presencia legalmente establecido en el artículo 9 del Real Decreto':''}.`}`,lit?'ok':'nuevo'));}
  else P3.push(p(`${TR} prestaba sus servicios por cuenta de ${empArt} con carácter de ${FC.modTxt(x.modalidad)}, alternando las siguientes semanas: ${x.semanas.map(s=>{const d=FC.descSemana(s);return d?`semana ${s.nombre}: ${d.groups.map(d.gtxt).join(', ')} (${n1(d.W.ef)} h de trabajo efectivo${d.W.pres?' y '+n1(d.W.pres)+' de presencia':''})`:'';}).filter(Boolean).join('; ')}${r?`, sumando un promedio de ${n1((r.ef+r.pres)/(r.days/7))} horas semanales`:''}.`,'nuevo'));}
 else if(pers.length>1)P3.push(p(`${TR} prestaba sus servicios por cuenta de ${empArt} con la siguiente jornada: ${pers.map((x,i)=>{const r=E.J.per.find(q=>q.id===x.id);const d=FC.descSemana(x.semanas[0]);return `del ${dmy(x.desde)} al ${dmy(r&&r.hasta)}, con carácter de ${FC.modTxt(x.modalidad)}${d?', '+d.groups.map(d.gtxt).join(', ')+(d.libre?', '+d.libre:''):''}${r&&r.days?`, con un promedio de ${n1(r.ef/(r.days/7))} horas semanales de trabajo efectivo${r.pres?' y '+n1(r.pres/(r.days/7))+' de presencia':''}`:''}`;}).join('; ')}, superando la jornada laboral y tiempo de presencia legalmente establecido en el artículo 9 del Real Decreto.`,'nuevo'));
 else P3.push(p(P('jornada: falta el periodo de jornada'),'pend'));
 const fx=c.tareas.filter(t=>FC.TAREAP[t]).map(t=>FC.TAREAP[t]);if(c.tareas.includes('otras')&&c.tareasOtras)fx.push(c.tareasOtras.trim().replace(/\.$/,''));
 const lug=c.lugares.filter(l=>!FC.dirVacia(l.dir));
 if(lug.length<=1)P3.push(p(`${g('La misma','El mismo')} realizaba las funciones propias de ${g('empleada','empleado')} del hogar, tales como la ordenanza y limpieza de la casa con todo lo que ello supone${fx.length?', '+listY(fx):''}, entre otras, en el centro de trabajo domicilio sito en ${lug.length?FC.fmtDir(lug[0].dir,true):P('dirección del lugar de trabajo')}.`));
 else P3.push(p(`${g('La misma','El mismo')} realizaba las funciones propias de ${g('empleada','empleado')} del hogar, tales como la ordenanza y limpieza de la casa con todo lo que ello supone${fx.length?', '+listY(fx):''}, entre otras, en los centros de trabajo domicilios sitos en ${lug.map(l=>`${FC.fmtDir(l.dir,true)}${l.desde?` (del ${dmy(l.desde)}${l.hasta?' al '+dmy(l.hasta):''})`:''}`).join(' y ')}.`,'nuevo'));
 const titIds=FC.empleadoras(c);const esTit=pr=>(pr.m&&pr.m.titular)||titIds.includes(pr.id);
 const cuid=c.cuidados.map(k=>k.persona);if(c.tareas.some(t=>t==='mayores'||t==='dependientes'))titIds.forEach(id=>{const pr=FC.per(c,id);if(pr&&!cuid.includes(id)&&Number(pr.edad)>=65)P3.push(p(`Asimismo, entre las funciones de ${tr} se encontraba atender las necesidades cotidianas de ${FC.perNom(pr)}, de ${pr.edad} años de edad, quien actuaba como titular del hogar familiar.`));});
 c.cuidados.forEach(k=>{const pr=FC.per(c,k.persona);if(!pr)return;
  if(esTit(pr)&&!FC.esMenor(c,k))P3.push(p(`Asimismo, entre las funciones de ${tr} se encontraba atender las necesidades cotidianas de ${FC.perNom(pr)}, de ${pr.edad||P('edad')} años de edad, quien actuaba como titular del hogar familiar.`));
  const det=FC.cuidTxt(c,k,tr,TR,g);if(det)P3.push(p(det,'nuevo'));});
 FC.coempValidados(c).forEach(id=>{const q=FC.per(c,id);const tit=FC.per(c,(c.empleadores.find(e=>(e.otros||[]).includes(id))||{}).titular);
  P3.push(p(`Cabe señalar que, esta parte se dirige igualmente contra ${FC.perNom(q)}, ${q.papel||P('parentesco')} de ${FC.perNom(tit)}, por cuanto que han intervenido de forma directa y personal en la relación laboral objeto del procedimiento, actuando como empleadores, siendo quienes han participado activamente tanto en la contratación y el despido de ${tr} como quienes abonaban el salario e impartían órdenes ${g('a la misma','al mismo')}, cumpliéndose con ello los requisitos que el artículo 1.1 del Estatuto de los Trabajadores marca para definir la relación laboral.`));});
 H('JORNADA, CENTRO DE TRABAJO Y FUNCIONES.',P3);
 /* CUARTO */
 const FP={efectivo:'en efectivo metálico',transferencia:'mediante transferencia',bizum:'mediante Bizum',otra:P('forma de pago')};
 if(c.sal.fijo==='si'){const fm=(c.sal.forma||[]);H('SALARIO PERCIBIDO.',[p(`Que, ${tr} percibía un salario mensual de ${numS(c.sal.importe)!=null?eurN(numS(c.sal.importe)):P('importe')}.- euros ${fm.length?fm.map(x=>FP[x]).join(' y '):P('forma de pago')}.`,fm.every(x=>x==='efectivo'||x==='transferencia')?'ok':'nuevo')]);}
 else if(c.sal.fijo==='no'){const M=c.meses.filter(m=>m.mes).sort((a,b)=>a.mes.localeCompare(b.mes));const tot=m=>m.nocobro?0:(numS(m.salario)||0)+(numS(m.extra)||0)+(numS(m.segundo)||0);
  const nxt=k=>{let y=+k.slice(0,4),mm=+k.slice(5,7)+1;if(mm>12){mm=1;y++;}return `${y}-${String(mm).padStart(2,'0')}`;};
  const G=[];M.forEach(m=>{const t=tot(m),L=G[G.length-1];if(L&&Math.abs(L.t-t)<0.005&&nxt(L.to)===m.mes)L.to=m.mes;else G.push({from:m.mes,to:m.mes,t});});
  const fms=[...new Set(M.map(m=>m.forma).filter(Boolean))];const fp=fms.length===1?' '+FP[fms[0]]:'';
  if(G.length===1&&M.length)H('SALARIO PERCIBIDO.',[p(`Que, ${tr} percibía un salario mensual de ${eurN(G[0].t)}.- euros${fp}.`,'ok')]);
  else{const it=G.map(x=>x.from===x.to?`en ${FC.mesKey(x.from)} percibió ${x.t?eurN(x.t)+' euros':'cantidad alguna'}`.replace('percibió cantidad alguna','no percibió cantidad alguna'):`desde ${FC.mesKey(x.from)} hasta ${FC.mesKey(x.to)} percibió ${x.t?eurN(x.t)+' euros mensuales':'cantidad alguna'}`.replace('percibió cantidad alguna','no percibió cantidad alguna'));
   H('SALARIO PERCIBIDO.',[p(M.length?`Que, ${tr} percibía cantidades variables${fp}, según el siguiente detalle: ${listY(it)}.`:P('meses cobrados'),M.length?'nuevo':'pend')]);}}
 else H('SALARIO PERCIBIDO.',[p(P('salario percibido'),'pend')]);
 /* QUINTO */
 const F=c.fin;const P5=[];const fc=dmy(F.fechaCom)||P('fecha'),ff=dmy(F.fechaFin)||P('fecha');
 if(F.tipo==='despido'){const MED={carta:'carta de despido',burofax:'burofax',email:'correo electrónico',whatsapp:'mensaje de WhatsApp'};
  if(F.medio==='verbal'){P5.push(p(`Que, en fecha ${fc}, ${empArt} ${vb('despidieron','despidió')} verbalmente a ${tr} sin entrega de carta de despido ni expresión de causa legal alguna que justificara dicha decisión.`));if(F.motivo==='si'&&F.docEntregado!=='si')P5.push(p(`${empArt.charAt(0).toUpperCase()+empArt.slice(1)} ${vb('alegaron','alegó')} ${F.dicho?'«'+F.dicho.trim().replace(/\.$/,'')+'»':P('motivos')}, motivos que esta parte no reconoce y que no constan acreditados mediante documento alguno.`));}
  else if(['carta','burofax','email','whatsapp'].includes(F.medio))P5.push(p(`Que en fecha ${fc}, ${empArt} ${vb('notificaron','notificó')} el despido a ${tr} por medio de ${MED[F.medio]} con fecha de efecto el ${ff}, basándose en ${F.dicho?'«'+F.dicho.trim().replace(/\.$/,'')+'»':P('motivos')}, los cuales esta parte no reconoce.`,F.medio==='whatsapp'?'nuevo':'ok'));
  else if(F.medio==='telefono')P5.push(p(`Que, en fecha ${fc}, ${empArt} ${vb('despidieron','despidió')} telefónicamente a ${tr} sin entrega de carta de despido ni expresión de causa legal alguna que justificara dicha decisión.`,'nuevo'));
  else P5.push(p(`Que, en fecha ${fc}, ${empArt} ${vb('despidieron','despidió')} a ${tr} ${P('forma de comunicación del despido')}.`,'nuevo'));}
 else if(F.tipo==='renuncia')P5.push(p(`Que en fecha ${ff} ${tr} renunció ${F.renMedio==='escrito'?'por escrito':'verbalmente'} a su puesto de trabajo, debido a ${F.renMotivo?F.renMotivo.trim().replace(/\.$/,''):'las condiciones laborales del mismo'}.`,F.renMedio==='escrito'?'nuevo':'ok'));
 else if(F.tipo==='fallecimiento'){const q=FC.per(c,F.fallQuien);P5.push(p(`Que, en fecha ${dmy(F.fallFecha)||ff}, falleció ${q?FC.perNom(q):P('persona fallecida')}${F.fallRel?', '+F.fallRel.trim():''}, extinguiéndose con ello la relación laboral en fecha ${ff}.`,'nuevo'));}
 else if(F.tipo==='otro')P5.push(p(`Que en fecha ${ff} se extinguió la relación laboral ${P('motivo de la extinción')}.`,'nuevo'));
 if(F.tipo&&F.tipo!=='continua')H('NOTIFICACIÓN DEL FIN DE LA RELACIÓN LABORAL.',P5);
 /* SEXTO */
 if(F.burofax==='si'&&F.tipo!=='continua'){const q=FC.per(c,F.burDest);const dest=q?(q.trato==='d'?'al empleador':'a la empleadora'):alEmp;H('ENVÍO DE BUROFAX.',[F.burRes==='sinresp'||!F.burRes?p(`Que en fecha ${dmy(F.burFecha)||P('fecha')} se envió burofax ${dest} solicitando carta de despido o readmisión y no se ha tenido noticias.`,F.burRes?'ok':'pend'):p(`Que en fecha ${dmy(F.burFecha)||P('fecha')} se envió burofax ${dest} solicitando carta de despido o readmisión, ${({respondio:'que fue respondido',rehusado:'que fue rehusado',noretirado:'que no fue retirado'})[F.burRes]}.`,'nuevo')]);}
 /* SÉPTIMO */
 if(despide){if(cal==='improcedente')H('DESPIDO IMPROCEDENTE.',[p('Al efectuarse el despido incumpliendo los requisitos de forma establecidos legalmente en el artículo 11.3 del Real Decreto 1620/2011, esta parte considera que el mismo debe ser calificado como improcedente.')]);
  else if(cal==='nulo')H('DESPIDO NULO.',[p(`Esta parte considera que el despido debe ser calificado como nulo por ${P('causa de nulidad')}, y subsidiariamente como improcedente.`,'nuevo')]);
  }
 /* OCTAVO */
 const cantidad=acum||['renuncia','continua','otro','fallecimiento'].includes(F.tipo);
 if(cantidad){const P8=[p(`Que en la fecha ${despide?'del despido':'de la presente'} ${empArt} le ${vb('adeudaban','adeudaba')} a ${tr} las siguientes cantidades:`,despide?'ok':'nuevo')];
  if(FC.parrPagados({T1,c}))P8.push(p(FC.parrPagados({T1,c}),'ok'));
  P8.push({tabla:'T1',st:'ok'});
  P8.push(p('El importe presente en el “debía percibir” de conformidad con lo suscrito en el Real Decreto 1620/2011 señalado en el Hecho Primero del presente escrito, es el respectivo a la suma de los conceptos que se detallan a continuación:'));
  P8.push({lista:T1.metodo==='separado'?['Salario base a razón de (40) horas.','Horas de presencia (20).']:['Salario base a razón de (40) horas.','Horas de presencia (20).','Se incluye el prorrateo de las pagas extra'],st:'ok'});
  (T1.esp||[]).filter(e=>e.cuenta).forEach(e=>{const S=c.sal,eu=x=>eurN(x)+' €';
   if(e.tipo==='ultimo'){const r=e.rows[0];const ex=[[S.finVac,'por vacaciones pendientes'],[S.finPagas,'por pagas extra'],[S.finIndem,'de indemnización'],[S.finOtros,'por '+((S.finOtrosTxt||'').trim()||'otros conceptos')]].filter(([v])=>numS(v)).map(([v,l])=>`${eu(numS(v))} ${l}`);
    P8.push(p(`Que en el último mes trabajado, ${MESC[r.m-1].toLowerCase()} del ${r.y}${r.cov<r.dim?` (${r.cov} días)`:''}, ${tr} ${S.ultimoMes==='no'?'no percibió cantidad alguna en concepto de salario':`percibió ${e.perc!=null?eu(e.perc):P('importe')} en concepto de salario de los días trabajados`}${ex.length?`, y al finalizar la relación laboral se le abonaron ${listY(ex)}`:''}. La diferencia salarial de ese mes se detalla en la tabla siguiente:`,'nuevo'));}
   else P8.push(p(`Que en el periodo del ${dmy(e.a)} al ${dmy(e.b)}, correspondiente al mes en que se dio de alta a ${tr} en la Seguridad Social, ${g('esta','este')} percibió ${[e.bruto!=null?eu(e.bruto)+' brutos':'',e.neto!=null?eu(e.neto)+' netos':''].filter(Boolean).join(' (')+(e.bruto!=null&&e.neto!=null?')':'')}. La diferencia salarial de ese periodo se detalla en la tabla siguiente:`,'nuevo'));
   P8.push({tabla:'X',t:FC.tablaEsp(c,e),st:'ok'});});
  const hbs=[...new Set(T2.rows.map(r=>r.hb!=null?n1(r.hb):null).filter(Boolean))];
  P8.push(p(`A efectos del cálculo de la remuneración de las vacaciones devengadas y no disfrutadas durante todo el periodo reclamado, la base retributiva aplicable se fija en cada anualidad conforme a la suma del salario base mensual (a razón de ${hbs.length===1?hbs[0]:P('horas')} horas) más la prorrata de pagas extraordinarias, según los importes vigentes en cada ejercicio y que se detallan a continuación:`,'ok',true));
  P8.push({tabla:'T2',st:'ok'});
  if(T1.metodo==='separado'&&(T1.pagas||[]).some(p=>p.cuenta)){P8.push(p(`Asimismo, ${empArt} ${vb('adeudan','adeuda')} a ${tr} las pagas extraordinarias devengadas y no percibidas, a razón de dos pagas al año, que se detallan a continuación:`,'nuevo'));P8.push({tabla:'X',t:FC.tablaPagas({T1,c}),st:'ok'});}
  P8.push({tabla:'TOT',st:'ok'});
  H('CANTIDADES RECLAMADAS.',P8);}
 /* NOVENO */
 if(acum&&despide)H('ACUMULACIÓN DE ACCIONES',[p(`De conformidad con lo dispuesto en el artículo 26 de la Ley Reguladora de la Jurisdicción Social, ${tr} podrá acumular a la acción de despido la reclamación de las cantidades vencidas, exigibles y de cuantía determinada adeudadas hasta dicha fecha, procediendo dicha acumulación al derivar ambas acciones de la misma relación laboral.`)]);
 /* DÉCIMO */
 H('REPRESENTACIÓN SINDICAL',[c.cli.sindical==='no'?p(`Que ${tr} no ha ostentado en el último año cargo sindical de ningún tipo.`):c.cli.sindical==='si'?p(`Que ${tr} ha ostentado en el último año ${P('cargo sindical o de representación')}.`,'nuevo'):p(P('cargo sindical en el último año'),'pend')]);
 out.hechos.forEach((h,i)=>h.n=ORD[i]||String(i+1));
 const all=out.head.concat(...out.hechos.map(h=>h.paras));out.nuevos=all.filter(x=>x.st==='nuevo').length;out.pend=all.filter(x=>x.st==='pend').length;
 out.T1=T1;out.T2=T2;out.E=E;out.c=c;return out;};
FC.cuidTxt=(c,k,tr,TR,g)=>{const pr=FC.per(c,k.persona);if(!pr)return '';const out=[];const cu=(k.cu||[]).filter(x=>!(x==='medicacion'&&k.medicacion)).map(x=>FC.CUIDP[x]).filter(Boolean);
 if(FC.esMenor(c,k)){const fe=/hija|nieta|niña|sobrina/i.test(pr.papel||'');let t=`${TR} se ocupaba también del cuidado de ${fe?'una menor':'un menor'} de ${pr.edad!==''?pr.edad+' años':P('edad')}${pr.papel?' ('+pr.papel+')':''}`;if(cu.length)t+=`, encargándose de ${listY(cu)}`;if(k.extra)t+=`, y llevándole a sus actividades (${k.extra.trim().replace(/\.$/,'')})`;return t+'.';}
 if(!k.autonomia&&!k.grado&&!(k.diag||[]).length&&!cu.length&&!k.medicacion)return '';
 const at=[k.autonomia?FC.AUT[k.autonomia]:'',FC.GRADO[k.grado]||''].filter(Boolean);const dg=(k.diag||[]).map(x=>FC.DIAGP[x]);if(k.diagOtro)dg.push(k.diagOtro.trim());
 let t=`${FC.perNom(pr)}, de ${pr.edad||P('edad')} años${at.length?', '+at.join(', '):''}`;if(dg.length)t+=`, padece ${listY(dg)}`;if(k.ayudas)t+=` y utiliza ${k.ayudas.trim().replace(/\.$/,'')}`;out.push(t+'.');
 if(cu.length||k.medicacion)out.push(`${TR} se ocupaba de ${listY(cu.length?cu:['su atención diaria'])}${k.medicacion?`, administrándole la medicación (${k.medicacion.trim().replace(/\.$/,'')})`:''}.`);
 if(FC.NOCHE[k.noche])out.push(`Además, ${FC.NOCHE[k.noche]}.`);if(k.centro)out.push(k.centro.trim().replace(/\.?$/,'.').replace(/^./,x=>x.toUpperCase()));
 return out.join(' ');};
FC.papText=G=>{const L=[];const strip=s=>String(s).replace(/[⟪⟫]/g,'');G.head.forEach(h=>{L.push((h.st==='nuevo'?'⟦Variante nueva: pendiente de aprobación⟧ ':'')+strip(h.text),'');});L.push('H E C H O S','');
 G.hechos.forEach(h=>{L.push(`${h.n}.- ${h.titulo}`);h.paras.forEach(x=>{if(x.t){L.push(tabText(x.t));}else if(x.tabla==='T1'){L.push(FC.t1Text(G));}else if(x.tabla==='T2'){L.push(FC.t2Text(G));}else if(x.tabla==='TOT'){L.push(FC.totText(G));}else if(x.lista){x.lista.forEach(i=>L.push('  • '+strip(i)));}else L.push((x.st==='nuevo'?'⟦Variante nueva: pendiente de aprobación⟧ ':'')+strip(x.text));});L.push('');});return L.join('\n');};
/* importe en letra (español, mayúsculas) */
FC.letras=x=>{const U=['','UNO','DOS','TRES','CUATRO','CINCO','SEIS','SIETE','OCHO','NUEVE','DIEZ','ONCE','DOCE','TRECE','CATORCE','QUINCE','DIECISÉIS','DIECISIETE','DIECIOCHO','DIECINUEVE','VEINTE','VEINTIUNO','VEINTIDÓS','VEINTITRÉS','VEINTICUATRO','VEINTICINCO','VEINTISÉIS','VEINTISIETE','VEINTIOCHO','VEINTINUEVE'];
 const D=['','','','TREINTA','CUARENTA','CINCUENTA','SESENTA','SETENTA','OCHENTA','NOVENTA'];const C=['','CIENTO','DOSCIENTOS','TRESCIENTOS','CUATROCIENTOS','QUINIENTOS','SEISCIENTOS','SETECIENTOS','OCHOCIENTOS','NOVECIENTOS'];
 const d99=n=>n<30?U[n]:D[Math.floor(n/10)]+(n%10?' Y '+U[n%10]:'');const d999=n=>n===100?'CIEN':((n>=100?C[Math.floor(n/100)]+(n%100?' ':''):'')+(n%100?d99(n%100):''));
 const apoc=t=>t.replace(/VEINTIUNO$/,'VEINTIÚN').replace(/(^| )UNO$/,'$1UN');
 const w=n=>{if(n===0)return 'CERO';let out=[];const mill=Math.floor(n/1e6),miles=Math.floor((n%1e6)/1000),r=n%1000;if(mill)out.push(mill===1?'UN MILLÓN':apoc(w(mill))+' MILLONES');if(miles)out.push(miles===1?'MIL':apoc(d999(miles))+' MIL');if(r)out.push(d999(r));return out.join(' ');};
 const cts=Math.round(x*100);const e=Math.floor(cts/100),c=cts%100;const eu=apoc(w(e))+(e===1?' EURO':' EUROS');return c?`${eu} Y ${apoc(d99(c))} ${c===1?'CÉNTIMO':'CÉNTIMOS'}`:eu;};
/* tabla de totales: diferencias + vacaciones (+ otras − abonado) = principal; mora del 10 %; total pendiente */
FC.totales=G=>{const r2=x=>Math.round(x*100)/100;const dif=r2(G.T1.total),vac=r2(G.T2.total),otras=r2(G.T1.debidas||0),abon=r2(G.T1.pagoFinal||0);const esp=(G.T1.esp||[]).reduce((s,e)=>s+(e.cuenta&&e.dif>0.005?r2(e.dif):0),0);const principal=r2(dif+vac+esp+r2(G.T1.totalPagas||0)+otras-abon);const mora=r2(principal*0.10);const total=r2(principal+mora);
 const L=[['(+) 1. Subtotal por diferencias salariales',dif],['(+) 2. Subtotal por vacaciones acumuladas',vac]];(G.T1.esp||[]).forEach(e=>{if(e.cuenta&&e.dif>0.005)L.push([`(+) ${L.length+1}. Diferencia salarial ${e.tipo==='ultimo'?'del último mes trabajado':'del mes del alta en la Seguridad Social'}`,r2(e.dif)]);});if(G.T1.totalPagas)L.push([`(+) ${L.length+1}. Subtotal por pagas extraordinarias`,r2(G.T1.totalPagas)]);if(otras)L.push([`(+) ${L.length+1}. Otras cantidades adeudadas`,otras]);if(abon)L.push(['(−) Cantidad abonada al finalizar la relación',abon]);
 return {lineas:L,principal,mora,total,letras:FC.letras(total)};};
FC.totText=G=>{const t=FC.totales(G);return ['  TOTALES CANTIDADES RECLAMADAS'].concat(t.lineas.map(([l,v])=>`  ${l}: ${eurN(v)} €`),[`  Total Principal: ${eurN(t.principal)} €`,`  Mora 10%: ${eurN(t.mora)} €`,`  Total Pendiente: ${eurN(t.total)} €`,`  ${t.letras}`]).join('\n');};
/* modelo común de las tablas de la papeleta (formato acordado por el despacho) */
const MESC=['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
const dsl=x=>x?x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4):'⟦fecha⟧';
FC.t1Pagados=G=>{const c=G.c;return G.T1.rows.filter(r=>!r.esp&&(!r.presc||c.abg.incluirPrescritos)&&r.dif!=null&&r.dif<=0.005);};
FC.parrPagados=G=>{const M=FC.t1Pagados(G);if(!M.length)return '';const Y=[];M.forEach(r=>{let y=Y.find(x=>x.y===r.y);if(!y)Y.push(y={y:r.y,m:[]});y.m.push(MESC[r.m-1].toLowerCase());});
 return `En los devengos correspondientes de salario base más el complemento a salario base ${Y.map(y=>`del año ${y.y} de ${listY(y.m)}`).join(' y ')} ${G.c.cli.trato==='d'?'el demandante':'la demandante'} percibió lo correspondiente al convenio aplicable.`;};
const filaMes=(r,est)=>[`${MESC[r.m-1]} ${r.y}${r.cov<r.dim?` (${r.cov} días)`:''}`,r.deb!=null?eurN(r.deb)+' €':(est[r.estado]||'—'),r.perc!=null?eurN(r.perc)+' €':'⟦sin datos⟧',r.dif!=null?eurN(r.dif)+' €':'—'];
FC.tablaEsp=(c,e)=>{const r=e.rows[e.rows.length-1];const rows=e.tipo==='ultimo'?[filaMes(r,{smi:'⟦SMI sin verificar⟧',jornada:'⟦falta jornada⟧',sindatos:'⟦sin datos⟧'})]:[[`Del ${dsl(e.a)} al ${dsl(e.b)}`,e.deb!=null?eurN(e.deb)+' €':'⟦falta jornada o SMI⟧',eurN(e.perc)+' €'+(e.bruto==null?' (neto)':''),e.dif!=null?eurN(e.dif)+' €':'—']];
 return {titulo:`Diferencia salarial ${e.tipo==='ultimo'?'del último mes trabajado':'del mes del alta en la Seguridad Social'} (del ${dsl(e.a)} al ${dsl(e.b)})`,head:['Concepto','Debía Percibir','Percibido','Diferencia'],rows,foot:['Total diferencia salarial','','TOTAL',eurN(e.dif!=null?Math.max(0,e.dif):0)+' €'],w:[3000,2000,1800,2000]};};
FC.tablaPagas=G=>{const c=G.c;const P=(G.T1.pagas||[]).filter(p=>p.cuenta);const rows=P.map(p=>[String(p.y),p.dev!=null?eurN(p.dev)+' €':'⟦falta jornada o SMI⟧',eurN(p.cob)+' €',p.dif!=null?eurN(p.dif)+' €':'—']);
 return {titulo:`3. Pagas extraordinarias devengadas por el periodo del ${dsl(P.length?P[0].a:null)} al ${dsl(P.length?P[P.length-1].b:null)}`,head:['Año','Devengado','Percibido','Diferencia'],rows,foot:['Total pagas extraordinarias','','TOTAL',eurN(G.T1.totalPagas||0)+' €'],w:[1800,2400,2200,2400]};};
FC.tabla1=G=>{const c=G.c;const est={smi:'⟦SMI sin verificar⟧',jornada:'⟦falta jornada⟧',sindatos:'⟦sin datos⟧'};const R0=G.T1.rows.filter(r=>!r.esp&&(!r.presc||c.abg.incluirPrescritos));const R=R0.filter(r=>!(r.dif!=null&&r.dif<=0.005));
 const rows=R.map(r=>[`${MESC[r.m-1]} ${r.y}${r.cov<r.dim?` (${r.cov} días)`:''}`,r.deb!=null?eurN(r.deb)+' €':(est[r.estado]||'—'),r.perc!=null?eurN(r.perc)+' €':'⟦sin datos⟧',r.dif!=null?eurN(r.dif)+' €':'—']);
 return {titulo:`1. Diferencias salariales por el periodo del ${dsl(R0.length?R0[0].a:null)} al ${dsl(R0.length?R0[R0.length-1].b:null)}`,head:['Concepto','Debía Percibir','Percibido','Diferencia'],rows,foot:['Total diferencia salarial','','TOTAL',eurN(G.T1.total)+' €'],w:[3000,2000,1800,2000]};};
FC.tabla2=G=>{const c=G.c;const din=G.T2.metodo==='dinero';const rows=G.T2.rows.map(r=>[String(r.y),r.base!=null?eurN(r.base)+' €':'⟦SMI sin verificar⟧',n2(r.dev),din?eurN(r.pagado)+' €':String(r.disfr),r.imp!=null?eurN(r.imp)+' €':'—']);
 return {titulo:`2. Vacaciones devengadas y no disfrutadas por el periodo del ${dsl(c.rel.inicio)} al ${dsl(FC.endRel(c))}`,head:['Año','Base mensual','Días devengados',din?'Pagado':'Días disfrutados','Importe'],rows,foot:['Total vacaciones','','','TOTAL',eurN(G.T2.total)+' €'],w:[1400,1950,1750,1750,1950]};};
const tabText=t=>['  '+t.titulo,'  '+t.head.join(' | ')].concat(t.rows.map(r=>'  '+r.join(' | ')),['  '+t.foot.filter(Boolean).join(' | ')]).join('\n');
FC.t1Text=G=>tabText(FC.tabla1(G));
FC.t2Text=G=>tabText(FC.tabla2(G));
FC.tabText=tabText;

/* ---------------- conversión desde la ficha C anterior ---------------- */
FC.migrate=old=>{const st=FC.newC();const c=st.c;const V=(id)=>SF.V(old,id);st.id=old.id;st.creada=old.creada;
 c.cli.trato=V('cli_trato')||'';c.cli.nombre=V('cli_nombre')||'';c.cli.doc=({DNI:'DNI',NIE:'NIE',pasaporte:'Pasaporte',ninguno:'ninguno'})[V('cli_doc')]||'';c.cli.docnum=V('cli_docnum')||'';c.cli.nac=V('cli_nac')||'';c.cli.tel=V('cli_tel')||'';c.cli.email=V('cli_email')||'';
 const od=V('cli_dom');if(od&&typeof od==='object'){Object.assign(c.cli.dom,{via:od.via||'',calle:od.calle||'',num:od.num||'',bloque:od.bloque||'',esc:od.esc||'',piso:od.piso||'',puerta:od.puerta||'',cp:od.cp||'',prov:/^\d{5}$/.test(od.cp||'')?od.cp.slice(0,2):'',munq:od.loc||'',ind:od.ind||''});}
 const map={};(old.personas||[]).forEach(p=>{const n=FC.T.personas(c);Object.assign(n,{nombre:p.nombre||'',papel:p.relacion||'',tel:p.tel||'',email:p.email||'',docNum:p.dni||'',edad:p.edad||'',trabajo:p.trabajo||''});n.m={vive:p.roles.includes('vive'),contrato:p.roles.includes('contrato'),ordenes:p.roles.includes('ordenes'),pago:p.roles.includes('pago'),despidio:p.roles.includes('despidio'),titular:p.roles.includes('dueno')};c.personas.push(n);map[p.id]=n.id;});
 (old.entorno||[]).forEach(x=>{const n=FC.T.personas(c);Object.assign(n,{nombre:x.nombre||'',papel:x.relacion||'',tel:x.tel||'',frec:x.frec||'',dias:x.dias||'',vio:x.vio||'',testigo:x.testigo||''});n.m={visita:true};c.personas.push(n);});
 (old.cuidados||[]).forEach(k=>{const n=FC.T.personas(c);Object.assign(n,{nombre:k.nombre||'',papel:k.parentesco||'',edad:k.edad||''});c.personas.push(n);const q=FC.T.cuidados(c);Object.assign(q,{persona:n.id,autonomia:({ayuda:'moderada',dependiente:'total'})[k.autonomia]||k.autonomia||'',grado:k.grado||'',diag:k.diag||[],diagOtro:k.diagOtro||'',ayudas:k.ayudas||'',medicacion:k.medicacion||'',noche:k.noche||'',centro:k.centro||'',sanitarios:k.sanitarios||'',colegio:k.colegio||'',extra:k.extra||'',rutina:k.rutina||'',cu:k.cu||[],obs:[k.obs,k.hist].filter(Boolean).join(' ')});c.cuidados.push(q);});
 const tit=c.personas.find(p=>p.m.titular);if(tit){const e=FC.T.empleadores(c);e.titular=tit.id;c.empleadores.push(e);}
 const hd=V('hog_dir');if(hd&&typeof hd==='object'){const l=FC.T.lugares(c);Object.assign(l.dir,{via:hd.via||'',calle:hd.calle||'',num:hd.num||'',piso:hd.piso||'',puerta:hd.puerta||'',cp:hd.cp||'',prov:/^\d{5}$/.test(hd.cp||'')?hd.cp.slice(0,2):'',munq:hd.loc||''});c.lugares.push(l);}
 c.rel.inicio=V('rel_inicio')||'';c.rel.autGlobal=V('cli_permiso')==='no'?'nunca':V('cli_permiso')==='si'?'siempre':'';
 const TM={limpieza:'limpiar_casa',cocina:'cocinar',plancha:'planchar',ninos:'ninos',mayores:'mayores',dependiente:'dependientes',compras:'compras',mascotas:'mascotas',otras:'otras'};c.tareas=(V('hog_tareas')||[]).map(x=>TM[x]).filter(Boolean);
 c.relDia=V('rel_dia')||'';const sr=V('sal_real');if(sr){c.sal.fijo='si';c.sal.importe=sr;c.sal.forma=(V('sal_cobro')||[]).filter(x=>['efectivo','transferencia','bizum','otra'].includes(x));}
 const et=V('ext_tipo');c.fin.tipo=({despido:'despido',no_llaman:'despido',baja_forzada:'despido',voluntaria:'renuncia',sigue:'continua',otro:'otro'})[et]||'';c.fin.fechaCom=V('fecha_com')||'';c.fin.fechaFin=V('fecha_efectos')||V('rel_ultimo')||'';c.fin.medio=({palabra:'verbal',escrito:'carta',mensaje:'whatsapp'})[V('ext_forma')]||'';c.fin.dicho=V('ext_literal_txt')||V('ext_dicho')||'';c.fin.dia=V('ext_dia')||'';c.fin.firmo=V('ext_firmo')||'';
 c.pru.llaves=V('hog_llaves')||'';c.obs=old.obs||'';c.migrada=true;return st;};

/* ---------------- ejemplo ficticio ---------------- */
FC.DEMO_NAME='Interna que cuidaba a una señora con Alzheimer';
FC.demo=hoy=>{hoy=hoy||today();const st=FC.newC();const c=st.c;const d=(dd)=>SF.addDays(hoy,dd);
 c.filtro.abogado='no';Object.assign(c.filtro,{reclamar:['despido','salarios','vacaciones'],conocio:['tiktok'],motivo:'Que le paguen lo que le deben y no quedarse sin nada después de tantos meses.',hechaPor:'ASESOR_01 (ficticio)'});Object.assign(c.int,{finReal:'00:00',dormia:'persona',disponible:'si',disponibleTxt:'para cambiar el pañal y dar agua a Carmen, dos o tres veces por noche'});
 Object.assign(c.cli,{trato:'da',nombre:'Rosa',apellidos:'Quispe Mamani (ficticia)',doc:'Pasaporte',docnum:'BB000000 (ficticio)',emisor:'',pais:'PE',nacionalidad:'',nac:'1985-09-20',tel:'600 000 303',email:'rosa.ficticia@example.com',empadronada:'si',padronFecha:'2025-03-10',postalIgual:'si',sindical:'no'});
 c.int=c.int||{};Object.assign(c.cli.dom,{via:'Calle',calle:'Supuesta (ficticia)',num:'22',piso:'3',puerta:'C',cp:'28039',prov:'28',codm:'28079'});Object.assign(c.cli.padronDir,c.cli.dom);
 const pe=(o)=>{const p=FC.T.personas(c);Object.assign(p,o);c.personas.push(p);return p;};
 const carmen=pe({trato:'da',nombre:'Carmen',apellidos:'López Ruiz (ficticia)',papel:'señora de la casa',edad:'88',docTipo:'DNI',docNum:'00000000T (ficticio)',m:{vive:true,titular:true}});
 const luis=pe({trato:'d',nombre:'Luis',apellidos:'Martín López (ficticio)',papel:'hijo',edad:'56',docTipo:'DNI',docNum:'11111111H (ficticio)',trabajo:'ingeniero, vive en otra casa',m:{contrato:true,ordenes:true,pago:true,despidio:true,visita:true},frec:'varias',dias:'martes y viernes por la tarde',vio:'si',testigo:'no'});
 pe({trato:'da',nombre:'Ana',apellidos:'Torres (ficticia)',papel:'nieta de Carmen',edad:'30',m:{visita:true},frec:'mensual',dias:'algún sábado por la mañana',vio:'si',testigo:'ns'});
 pe({trato:'d',nombre:'José (ficticio)',papel:'portero del edificio',m:{visita:true},frec:'diaria',vio:'si',testigo:'si'});
 const e=FC.T.empleadores(c);e.titular=carmen.id;e.otros=[luis.id];Object.assign(e.dom,{via:'Calle',calle:'Residencial Ficticia',num:'5',piso:'4',puerta:'A',cp:'28016',prov:'28',codm:'28079'});c.empleadores.push(e);
 luis.dom=Object.assign(FC.newDir(),{via:'Calle',calle:'Otra Ficticia',num:'9',piso:'2',puerta:'B',cp:'28003',prov:'28',codm:'28079'});
 const fin0=SF.wdBack(hoy,6);e.desde=d(-420);e.hasta=fin0;luis.empDesde=d(-420);luis.empHasta=fin0;
 const l=FC.T.lugares(c);Object.assign(l.dir,e.dom);l.desde=d(-420);l.hasta=fin0;l.quienes=[carmen.id,luis.id];c.lugares.push(l);
 /* sin papeles al empezar; autorización por arraigo y alta en la Seguridad Social unos meses antes del despido */
 const dAlta=(()=>{const x=SF.addDays(hoy,-120);return x.slice(0,8)+'01';})();const dAntes=SF.addDays(dAlta,-1);const finMesAlta=(()=>{const y=+dAlta.slice(0,4),m=+dAlta.slice(5,7);return `${dAlta.slice(0,8)}${String(new Date(Date.UTC(y,m,0)).getUTCDate()).padStart(2,'0')}`;})();
 Object.assign(c.rel,{inicio:d(-420),contrato:'verbal',alta:'si',autGlobal:'parte'});
 c.autorizacion.push(Object.assign(FC.T.autorizacion(c),{tipo:'sin',desde:d(-420),hasta:dAntes}),Object.assign(FC.T.autorizacion(c),{tipo:'con',desde:dAlta,hasta:'',permiso:'arraigo sociolaboral (ficticio)'}));
 c.altas.push(Object.assign(FC.T.altas(c),{alta:dAlta,baja:fin0,emps:[carmen.id],fuente:'cliente',pagoBruto:'1100',pagoNeto:'980',pagoDesde:dAlta,pagoHasta:finMesAlta,pagoMes:SF.addDays(finMesAlta,1),pagoMesForma:'transferencia',pagoMesObs:'ese mes le pagaron por transferencia y con nómina; antes, siempre en efectivo'}));
 c.tareas=['limpiar_casa','limpiar_banos','limpiar_cocina','lavar','planchar','cocinar','compras','mayores','dependientes','citas'];
 const k=FC.T.cuidados(c);Object.assign(k,{persona:carmen.id,autonomia:'severa',grado:'II',diag:['alzheimer','movilidad','incontinencia'],ayudas:'andador y cama articulada',medicacion:'pastillas a las 9, 14 y 21 h',noche:'varias',centro:'acudía a un centro de día los lunes y miércoles de 10 a 13 h',rutina:'se levantaba a las 8, comía a las 13:30, siesta hasta las 16 y se acostaba a las 21:30',cu:['aseo','vestir','comida','medicacion','movilidad','medico','noche']});c.cuidados.push(k);
 const pj=FC.T.periodos(c);Object.assign(pj,{desde:d(-420),modalidad:'interna',lugar:l.id});const w=pj.semanas[0];
 for(let i=0;i<5;i++){w.dias[i].tramos=[FC.newTramo(c,'efectivo','08:00','22:00'),FC.newTramo(c,'descanso','14:00','16:00'),FC.newTramo(c,'presencia','22:00','00:00')];}
 w.dias[5].tramos=[FC.newTramo(c,'efectivo','08:00','14:00')];w.dias[6].libre=true;FC.dias2turnos(c,w);c.periodos.push(pj);
 Object.assign(c.sal,{fijo:'si',importe:'900',forma:['efectivo'],dia:'el día 1 de cada mes'});Object.assign(c.sal,{ultimoMes:'si',ultimoMesImporte:'300',finVac:'150',pagas:'no',entregaDonde:'en la cocina',entregaPresentesP:[carmen.id],entregaPresentes:'normalmente nadie; a veces Carmen'});c.vac.autoriza=[luis.id];c.fin.quien=[luis.id];c.sal.entrega=[luis.id];Object.assign(c.pru,{telefono:'si',conversaciones:'si',convCon:[luis.id]});
 c.vac.tuvo='si';const v=FC.T.vacaciones(c);Object.assign(v,{desde:'2026-08-01',hasta:'2026-08-15',pagadas:'no',disfruto:'si'});c.vacaciones.push(v);
 c.vacaciones.push(Object.assign(FC.T.vacaciones(c),{desde:'2025-12-22',hasta:'2025-12-28',pagadas:'si',importe:'200',disfruto:'no'}));
 Object.assign(c.fin,{tipo:'despido',fechaCom:SF.wdBack(hoy,6),fechaFin:SF.wdBack(hoy,6),medio:'verbal',dicho:'que ya no la necesitaban porque iban a llevar a su madre a una residencia',motivo:'si',docEntregado:'no',pidieronFirmar:'no',firmo:'no',pago:'',pagoImporte:'',pagoConcepto:'',dia:'Luis llegó a las 10, delante de su madre le dijo que recogiera sus cosas y le pidió las llaves. Le dio 450 € en efectivo: 300 € del mes y 150 € de vacaciones.',burofax:'si',burFecha:SF.wdBack(hoy,2),burDest:luis.id,burRes:'sinresp'});
 c.fin.dia=c.fin.dia;Object.assign(c.pru,{llaves:'si',acceso:'si',audios:'si'});
 Object.assign(c.pruebas[0],{nombre:'Audios de WhatsApp de Luis',tipo:'Audio',desc:'Le pide que se quede también los domingos',fecha:d(-60),hecho:'jornada'});
 Object.assign(c.abg,{calif:'',acum:''});[c.cli.dom,c.cli.padronDir,...c.lugares.map(l=>l.dir),...c.empleadores.map(e=>e.dom),luis.dom].forEach(d=>{d.gmaps=FC.dirSig(d);});
 return st;};

/* ejemplo ficticio de la ficha B: peón de la construcción sin papeles (como el escrito de ejemplo de régimen general) */
FC.DEMO_NAME_B='Peón de la construcción sin papeles en Barcelona, despedido de palabra';
FC.demoB=hoy=>{hoy=hoy||today();const st=FC.newB();const c=st.c;const d=dd=>SF.addDays(hoy,dd);const fin0=SF.wdBack(hoy,5);
 Object.assign(c.filtro,{abogado:'no',reclamar:['despido','salarios','vacaciones'],conocio:['tiktok'],motivo:'Cobrar lo que marca el convenio y que le paguen el despido.',hechaPor:'ASESOR_02 (ficticio)'});
 Object.assign(c.cli,{trato:'d',nombre:'Carlos',apellidos:'Mendoza Ruiz (ficticio)',doc:'Pasaporte',docnum:'CC000000 (ficticio)',pais:'CO',nac:'1992-02-14',tel:'600 000 404',email:'carlos.ficticio@example.com',empadronada:'si',postalIgual:'si',sindical:'no'});
 Object.assign(c.cli.dom,{via:'Calle',calle:'Imaginaria (ficticia)',num:'14',piso:'1',puerta:'A',cp:'08901',prov:'08',codm:'08101'});Object.assign(c.cli.padronDir,c.cli.dom);
 const pe=o=>{const p=FC.T.personas(c);Object.assign(p,o);c.personas.push(p);return p;};
 const adm=pe({trato:'d',nombre:'Pedro',apellidos:'Gómez Prueba (ficticio)',papel:'administrador de la empresa',docTipo:'DNI',docNum:'22222222J (ficticio)',m:{titular:true,contrato:true,pago:true,despidio:true}});
 const enc=pe({trato:'d',nombre:'Andrés (ficticio)',papel:'encargado de obra',m:{ordenes:true},vio:'si',testigo:'ns'});
 pe({trato:'d',nombre:'Mario (ficticio)',papel:'compañero, oficial de primera',m:{},vio:'si',testigo:'si'});
 const e=FC.T.empleadores(c);Object.assign(e,{titular:adm.id,tipoEmp:'juridica',razon:'Construcciones Ficticias SL',cif:'B12345674',actividad:'construcción de edificios',cnae:'4121',desde:d(-400),hasta:fin0});Object.assign(e.dom,{via:'Calle',calle:'Industria Ficticia',num:'3',cp:'08902',prov:'08',codm:'08101'});c.empleadores.push(e);
 [['Obra Ficticia Norte','25','08905'],['Obra Ficticia Sur','7','08906']].forEach(([n,num,cp])=>{const l=FC.T.lugares(c);Object.assign(l.dir,{via:'Avenida',calle:n,num,cp,prov:'08',codm:'08101'});l.desde=d(-400);l.hasta=fin0;l.quienes=[adm.id];c.lugares.push(l);});
 Object.assign(c.rel,{inicio:d(-400),contrato:'verbal',alta:'no',autGlobal:'nunca',horasContrato:'',horasAlta:''});
 Object.assign(c.puesto,{categoria:'Peón ordinario',funciones:'carga y descarga de materiales, limpieza de la obra y ayuda a los oficiales',nomina:''});
 /* convenio real (comprobado en el BOPB y el BOE): construcción y obras públicas de la provincia de Barcelona; ver convenios/08001065011994-construccion-barcelona */
 Object.assign(c.conv,{actividad:'construcción de edificios',cnae:'4121',codigo:'08001065011994',nombre:'Convenio colectivo de trabajo del sector de la Construcción y Obras Públicas de la provincia de Barcelona',ambito:'provincial — Barcelona (art. 2)',
  vigencia:'2017-2021, prorrogado (arts. 4 a 6); tablas 2025 y 2026 provisionales (acta de 16-12-2025)',publicacion:'Texto: BOPB 29-3-2019. Tablas 2026: BOPB 17-3-2026 (anuncio 3909929); tablas 2025: anuncio 3909928',enlace:'https://bop.diba.cat/anunci/3909929',categoria:'Peón ordinario',grupo:'Grupo 1, nivel XII',
  pluses:'plus de convenio y plus de distancia, transporte y desgaste de herramientas',jornadaSemanal:'40',jornadaAnual:'1.736 (art. 71 del VII Convenio General)',horasExtra:'2026: 15,76 €/h diurnas en día laborable y 18,91 €/h nocturnas, sábados, domingos y festivos (art. 24 y Anexo III)',
  pagasNum:'2',pagasCuantia:'importe fijo de la tabla (junio y Navidad), devengo semestral por días naturales (arts. 14.1.4 y 17)',pagasProrrata:'no',vacDias:'30',vacTipo:'naturales',vacBase:'tabla',
  it:'Hospitalización: 100 % del salario base y pluses salariales durante el ingreso y 60 días más (art. 70 VII Convenio General). Accidente de trabajo sin hospitalización: garantía de salario base + plus de convenio desde el día 16 hasta 80 días (art. 28.2). Primera baja del año: 100 % los 3 primeros días (art. 28.7)',
  preaviso:'personal obrero: 1 semana (art. 38)',preavisoPenal:'descuento en la liquidación de los días no preavisados (art. 38.2)',otros:'Prohibido prorratear pagas y vacaciones o pactar «salario global» (art. 17.6 y art. 61 VII Convenio General). Antigüedad: solo la consolidada en 1997 (art. 18)',
  porVerificar:'Tablas de 2025 y 2026 provisionales, pendientes de la cláusula de garantía salarial',fuente:'convenio real comprobado en el BOPB y el BOE (resumen del despacho)',ok:{nombre:true,categoria:true,tablas:true,jornada:true,pagas:true,vacaciones:true,it:true,preaviso:true}});
 [['2025','935.27','747.70','2135.41','2135.41'],['2026','963.33','766.12','2199.47','2199.47']].forEach(([anio,base,pluses,paga,vac])=>c.conv.tablas.push(Object.assign(FC.T.tablas(c),{anio,base,pluses,pagasNum:'2',pagaImporte:paga,vacImporte:vac})));
 const pj=FC.T.periodos(c);Object.assign(pj,{desde:d(-400),modalidad:'completa',lugar:c.lugares[0].id});const w=pj.semanas[0];
 for(let i=0;i<5;i++)w.dias[i].tramos=[FC.newTramo(c,'efectivo','07:00','18:00'),FC.newTramo(c,'descanso','13:00','14:00')];w.dias[5].libre=true;w.dias[6].libre=true;FC.dias2turnos(c,w);c.periodos.push(pj);
 Object.assign(c.sal,{fijo:'si',importe:'1000',forma:['efectivo','transferencia'],dia:'a primeros de mes',pagas:'no',entrega:[adm.id],entregaDonde:'en la caseta de obra',ultimoMes:'si',ultimoMesImporte:'400'});
 c.vac.tuvo='si';c.vacaciones.push(Object.assign(FC.T.vacaciones(c),{desde:d(-160),hasta:d(-146),disfruto:'si',pagadas:'no'}));c.vac.autoriza=[enc.id];
 Object.assign(c.fin,{tipo:'despido',quien:[adm.id],fechaCom:fin0,fechaFin:fin0,medio:'verbal',dicho:'que no había más trabajo y que no volviera',motivo:'no',docEntregado:'no',pidieronFirmar:'no',firmo:'no',dia:'El administrador le dijo en la obra, delante del encargado, que no había más trabajo y que no volviera. Le pagó 400 € del mes.',burofax:'si',burFecha:SF.wdBack(hoy,2),burDest:adm.id,burRes:'sinresp'});
 Object.assign(c.pru,{telefono:'si',conversaciones:'si',convCon:[enc.id],audios:'no'});
 Object.assign(c.pruebas[0],{nombre:'Mensajes de WhatsApp con el encargado',tipo:'Mensajes',desc:'Le dice a qué obra tiene que ir cada día',fecha:d(-30),hecho:'antiguedad'});
 [c.cli.dom,c.cli.padronDir,...c.lugares.map(l=>l.dir),...c.empleadores.map(e=>e.dom)].forEach(x=>{x.gmaps=FC.dirSig(x);});
 return st;};

/* ---------------- pruebas automáticas ---------------- */
FC.runTests=()=>{const H='2026-10-26';const prev=FC._hoy;FC._hoy=H;const out=[];const T=(e,cmp,fn)=>{let ok=false,det='';try{const r=fn();ok=r===true||!!(r&&r.ok);det=r&&r.det?r.det:'';}catch(x){det='Error: '+x.message;}out.push({e,c:cmp,ok,det});};
 const st0=()=>{const st=FC.newC();return st;};let st,c,r,G,txt;
 T('Jornada (hogar)','Tramo de 22:00 a 06:00 = 8 h, todas nocturnas',()=>{const x=FC.dia({tramos:[{e:'22:00',s:'06:00',tipo:'efectivo'}]});return {ok:x.ef===8&&x.noct===8,det:`${x.ef} h, ${x.noct} nocturnas`};});
 T('Jornada (hogar)','Descanso dentro de un tramo se descuenta y se registra aparte',()=>{const x=FC.dia({tramos:[{e:'09:00',s:'22:00',tipo:'efectivo'},{e:'14:00',s:'16:00',tipo:'descanso'}]});return {ok:x.ef===11&&x.desc===2,det:`efectivas ${x.ef}, descanso ${x.desc}`};});
 T('Jornada (hogar)','Presencia separada del trabajo efectivo',()=>{const x=FC.dia({tramos:[{e:'08:00',s:'22:00',tipo:'efectivo'},{e:'22:00',s:'00:00',tipo:'presencia'}]});return {ok:x.ef===14&&x.pres===2};});
 st=st0();c=st.c;let pj=FC.T.periodos(c);pj.desde='2026-10-01';pj.hasta='2026-10-07';for(let i=0;i<5;i++)pj.semanas[0].dias[i].tramos=[FC.newTramo(c,'efectivo','09:00','17:00')];c.periodos.push(pj);
 T('Jornada (hogar)','Semana incompleta: del jueves 1 al miércoles 7 = 5 días, 40 h',()=>{const J=FC.calcJ(c);return {ok:J.per[0].days===7&&J.tot.ef===40,det:`${J.tot.ef} h`};});
 st=st0();c=st.c;pj=FC.T.periodos(c);pj.desde='2026-10-05';pj.hasta='2026-10-18';for(let i=0;i<5;i++)pj.semanas[0].dias[i].tramos=[FC.newTramo(c,'efectivo','09:00','17:00')];const wB=FC.newSemana(c,'B');for(let i=0;i<5;i++)wB.dias[i].tramos=[FC.newTramo(c,'efectivo','09:00','13:00')];pj.semanas.push(wB);c.periodos.push(pj);
 T('Jornada (hogar)','Dos semanas modelo alternas: 40 h + 20 h = 60 h',()=>{const J=FC.calcJ(c);return {ok:J.tot.ef===60,det:J.tot.ef+' h'};});
 const pj2=FC.T.periodos(c);pj2.desde='2026-10-15';pj2.hasta='2026-10-25';pj2.semanas[0].dias[0].tramos=[FC.newTramo(c,'efectivo','09:00','10:00')];c.periodos.push(pj2);
 T('Jornada (hogar)','Avisa del solape y no cuenta dos veces los días',()=>{const J=FC.calcJ(c);return {ok:J.overlaps.length===1&&J.overlaps[0].n===4&&J.tot.ef===60+1,det:J.overlaps.map(o=>o.n+' días').join(',')+'; total '+J.tot.ef};});
 st=st0();c=st.c;c.rel.inicio='2026-10-01';c.fin.fechaFin='2026-10-31';pj=FC.T.periodos(c);pj.desde='2026-10-01';for(let i=0;i<7;i++)pj.semanas[0].dias[i].tramos=[FC.newTramo(c,'efectivo','08:00','16:00'),FC.newTramo(c,'presencia','16:00','19:00')];c.periodos.push(pj);
 T('TABLA 1','Mes completo de 2026 con 40 h efectivas y 20 de presencia o más: debía percibir 2.136,75 €',()=>{c.sal.fijo='si';c.sal.importe='900';const t=FC.calcT1(st);const r=t.rows[0];return {ok:Math.abs(r.deb-2136.75)<0.01&&Math.abs(r.dif-1236.75)<0.01,det:`debía ${eurN(r.deb)} · percibió ${eurN(r.perc)} · dif ${eurN(r.dif)}`};});
 T('TABLA 1','Salario variable sin datos del mes: «sin datos», no se cuenta como impagado',()=>{c.sal.fijo='no';c.meses=[];const t=FC.calcT1(st);return {ok:t.rows[0].estado==='sindatos'&&t.total===0};});
 T('TABLA 1','Mes marcado «no cobró» sí cuenta como impagado',()=>{const m=FC.T.meses(c);m.mes='2026-10';m.nocobro=true;c.meses=[m];const t=FC.calcT1(st);return {ok:Math.abs(t.total-2136.75)<0.01,det:eurN(t.total)};});
 st=st0();c=st.c;c.rel.inicio='2023-05-01';c.fin.fechaFin='2023-05-31';pj=FC.T.periodos(c);pj.desde='2023-05-01';for(let i=0;i<5;i++)pj.semanas[0].dias[i].tramos=[FC.newTramo(c,'efectivo','09:00','17:00')];c.periodos.push(pj);c.sal.fijo='si';c.sal.importe='500';
 T('Importes legales','Un año sin SMI verificado bloquea su cálculo',()=>{const t=FC.calcT1(st);return {ok:t.rows[0].estado==='smi'&&t.blocked[2023]};});
 T('Importes legales','Al confirmarlo el abogado, se calcula',()=>{c.abg.smiVer[2023]=true;const t=FC.calcT1(st);return {ok:t.rows[0].deb!=null,det:eurN(t.rows[0].deb)};});
 st=st0();c=st.c;c.rel.inicio='2025-01-01';c.fin.fechaFin='2026-10-20';pj=FC.T.periodos(c);pj.desde='2025-01-01';for(let i=0;i<5;i++)pj.semanas[0].dias[i].tramos=[FC.newTramo(c,'efectivo','09:00','17:00')];c.periodos.push(pj);c.vac.tuvo='no';
 T('TABLA 2','Año 2025 completo sin vacaciones: 30 días pendientes = una base mensual (1.381,33 €)',()=>{const t=FC.calcT2(st);const r=t.rows.find(x=>x.y===2025);return {ok:Math.abs(r.dev-30)<1e-9&&Math.abs(r.imp-1381.3333)<0.01,det:`${n1(r.dev)} días · ${eurN(r.imp)}`};});
 T('TABLA 2','Suma las vacaciones de todos los años de la relación',()=>{const t=FC.calcT2(st);const sum=t.rows.reduce((a,r)=>a+(r.imp>0?r.imp:0),0);return {ok:t.rows.length===2&&Math.abs(t.total-sum)<0.01,det:eurN(t.total)};});
 st=st0();c=st.c;c.rel.inicio='2024-01-01';c.fin.fechaFin='2025-12-31';c.rel.autGlobal='parte';c.autorizacion=[{id:'a',tipo:'sin',desde:'2024-01-01',hasta:'2024-12-31'},{id:'b',tipo:'con',desde:'2025-01-01',hasta:''}];
 T('Autorización','Calcula días con y sin autorización por separado del alta',()=>{const a=FC.calcAut(c);return {ok:a.sin===366&&a.con===365&&a.nd===0,det:`sin ${a.sin} · con ${a.con}`};});
 T('Territorio','Mieres en Asturias: un único municipio (no el de Girona)',()=>{const r=FC.munSearch('33','Mieres');return {ok:r.length>=1&&r[0].codm==='33037'&&!r.some(x=>x.codm==='17105'),det:r.map(x=>x.name+' '+x.codm).join(', ')};});
 T('Territorio','Nombre homónimo en dos provincias: hay que elegir provincia',()=>{const a=FC.munAll('Arroyomolinos');return {ok:a.length===2,det:a.map(x=>x.name+' ('+FC.provName(x.cpro)+')').join(', ')};});
 T('Territorio','Nombres bilingües: «Alcoi» encuentra Alcoy/Alcoi',()=>{const r=FC.munSearch('03','Alcoi');return {ok:r.length&&/Alcoy/.test(r[0].name),det:r[0]&&r[0].name};});
 T('Tabla 1','Último mes trabajado: «no le pagaron» pone 0 y «sí» pone lo que dice',()=>{const s=FC.demo(H),k=s.c;k.sal.ultimoMes='';k.sal.ultimoMesImporte='';const last=()=>{const r=FC.calcT1(s).rows;return r[r.length-1].perc;};const base=last();k.sal.ultimoMes='no';const a=last();k.sal.ultimoMes='si';k.sal.ultimoMesImporte='250';const b=last();k.sal.ultimoMesImporte='';const d=last();return {ok:a===0&&b===250&&d===base&&base!==0,det:[base,a,b,d].join(' / ')};});
 T('Tabla 1','Meses cobrados correctamente: fuera de la tabla y en el párrafo «En los devengos…» agrupados por año',()=>{const s=FC.demo(H),k=s.c;k.sal.ultimoMes='';k.rel.alta='no';k.sal.fijo='no';const R=FC.calcT1(s).rows.filter(r=>!r.presc);const ok=[R[1],R[2],R[R.length-2]];k.meses=R.map(r=>Object.assign(FC.T.meses(k),{mes:r.key,salario:ok.includes(r)?'5000':'100'}));const G={T1:FC.calcT1(s),c:k};const t=FC.tabla1(G),par=FC.parrPagados(G);const nom=r=>MESC[r.m-1].toLowerCase();
  const exp=`del año ${ok[0].y} de ${ok[0].y===ok[1].y?nom(ok[0])+' y '+nom(ok[1]):nom(ok[0])}`;return {ok:t.rows.length===R.length-3&&!t.rows.some(x=>x[0].startsWith(MESC[ok[0].m-1]+' '+ok[0].y))&&par.startsWith('En los devengos correspondientes de salario base más el complemento a salario base '+exp)&&/la demandante percibió lo correspondiente al convenio aplicable\.$/.test(par),det:par};});
 T('Tabla 1','Último mes con su propia tabla; vacaciones, pagas y otros del finiquito se descuentan; la indemnización no',()=>{const s=FC.demo(H),k=s.c;k.sal.ultimoMes='si';k.sal.ultimoMesImporte='300';k.sal.finVac='200';k.sal.finPagas='100';k.sal.finIndem='999';const T1=FC.calcT1(s);const e=T1.esp.find(x=>x.tipo==='ultimo');const G={T1,T2:FC.calcT2(s),c:k};const t=FC.tabla1(G);const tot=FC.totales(G);const last=T1.rows[T1.rows.length-1];
  return {ok:!!e&&e.perc===300&&!t.rows.some(x=>x[0].startsWith(MESC[last.m-1]+' '+last.y))&&T1.pagoFinal===300&&tot.lineas.some(([l,v])=>/último mes trabajado/.test(l)&&Math.abs(v-Math.round(e.dif*100)/100)<0.005)&&/Diferencia salarial del último mes trabajado/.test(FC.papText(FC.pap(s,H))),det:JSON.stringify(tot.lineas)};});
 T('Tabla 1','Mes del alta con su propia tabla: bruto como percibido y debía percibir del periodo',()=>{const s=FC.demo(H),k=s.c;const R=FC.calcT1(s).rows.filter(r=>!r.presc&&r.deb!=null&&r.cov===r.dim);const r=R[2];k.rel.alta='si';k.altas=[Object.assign(FC.T.altas(k),{alta:r.a,pagoBruto:'500',pagoNeto:'450',pagoDesde:r.a,pagoHasta:r.b})];const T1=FC.calcT1(s);const e=T1.esp.find(x=>x.tipo==='alta');const t=FC.tablaEsp(k,e);
  return {ok:!!e&&e.perc===500&&Math.abs(e.deb-r.deb)<0.01&&!e.parcial&&!FC.tabla1({T1,c:k}).rows.some(x=>x[0].startsWith(MESC[r.m-1]+' '+r.y))&&/mes del alta/.test(t.titulo)&&/500 € brutos \(450 € netos\)/.test(FC.papText(FC.pap(s,H)).replace(/500,00/g,'500').replace(/450,00/g,'450')),det:e&&[e.deb,e.perc,e.dif].join(' / ')};});
 T('Totales','Vacaciones: por defecto, horas semanales con un máximo de 40',()=>{const s=FC.demo(H);const T2=FC.calcT2(s);return {ok:T2.rows.length>0&&T2.rows.every(r=>r.hb!=null&&r.hb<=40)&&T2.rows.some(r=>r.hb===40),det:T2.rows.map(r=>r.hb).join(', ')};});
 T('Correcciones','Fichas anteriores: «¿Le pagaron algo al finalizar?» pasa al desglose del último mes',()=>{const s=FC.demo(H),k=s.c;k.sal.ultimoMes='';k.sal.ultimoMesImporte='';k.sal.finVac='';Object.assign(k.fin,{pago:'si',pagoImporte:'120',pagoConcepto:'finiquito'});const antes=FC.calcT1(s).pagoFinal;FC.normFin(k);const T1=FC.calcT1(s);return {ok:antes===120&&T1.pagoFinal===120&&k.sal.ultimoMes==='si'&&k.sal.finOtros==='120'&&k.sal.finOtrosTxt==='finiquito'&&k.fin.pago==='',det:[antes,T1.pagoFinal].join(' / ')};});
 T('Word','Rellenar desde Word: solo lo vacío, direcciones con municipio del mapa y lista de lo que falta',()=>{if(!FC.aplicarImport)return {ok:false,det:'sin importador'};const s=FC.newC(),k=s.c;k.cli.nombre='Ya escrito';const R=FC.aplicarImport(k,{cliente:{nombre:'Otro',apellidos:'Prueba',documento:'NIE',telefono:'+51 987654321',domicilio:{calle:'Mayor',numero:'1',cp:'28013',municipio:'Madrid'},email:null},empleadores:[{nombre:'Ana',apellidos:'Test',domicilio:null}],jornada:{modalidad:'externa',turnos:[{dias:[0,1,2,3,4],entrada:'9:00',salida:'14:30'}]},relacion:{inicio:'2025-13-40'}});
  return {ok:k.cli.nombre==='Ya escrito'&&k.cli.apellidos==='Prueba'&&k.cli.doc==='NIE'&&k.cli.telPref==='PE'&&k.cli.tel==='987654321'&&k.cli.dom.codm==='28079'&&k.empleadores.length===1&&k.periodos[0].semanas[0].turnos[0].s==='14:30'&&!k.rel.inicio&&R.falta.includes('Cliente: correo electrónico')&&R.falta.includes('Empleador 1: domicilio')&&R.falta.includes('Relación: fecha de inicio'),det:JSON.stringify(R.falta.slice(0,5))};});
 T('Tabla 1','Mes incompleto: siempre entre 30 días (18 días de agosto = 18/30 del mes)',()=>({ok:FC.frMes(18,31)===18/30&&FC.frMes(31,31)===1&&FC.frMes(15,28)===0.5&&FC.frMes(28,28)===1&&Math.round(2136.75*FC.frMes(18,31)*100)/100===1282.05}));
 T('Totales','Vacaciones entre 360: 199 días = 30 × 199 / 360 días; un año completo, máximo 30',()=>{const s2=FC.demo(H),k=s2.c;k.rel.inicio='2025-01-01';k.fin.fechaFin='2026-07-18';k.rel.fin='2026-07-18';const R=FC.calcT2(s2).rows;const r25=R.find(r=>r.y===2025),r26=R.find(r=>r.y===2026);return {ok:r25.dev===30&&r26.dev===16.58&&Math.abs(r26.imp-1424.5*16.58/30)<0.005&&r26.cov===199,det:R.map(r=>r.y+':'+r.cov+'→'+r.dev).join(' ')};});
 T('Totales','Vacaciones: días con 2 decimales antes de multiplicar (16,58 × 1.424,50 / 30 = 787,27 €)',()=>{const s2=FC.demo(H),k=s2.c;k.rel.inicio='2026-02-01';k.fin.fechaFin='2026-08-18';k.rel.fin='2026-08-18';k.vac.tuvo='no';const r=FC.calcT2(s2).rows[0];return {ok:r.dev===16.58&&Math.round(r.imp*100)/100===787.27,det:r.dev+' / '+r.imp};});
 T('Totales','Vacaciones con días disfrutados y dinero pagado: se calculan las dos formas, se usa la mayor y se puede elegir',()=>{const s2=FC.demo(H),k=s2.c;k.rel.inicio='2026-01-01';k.fin.fechaFin='2026-07-18';k.rel.fin='2026-07-18';k.vac.tuvo='si';k.vacaciones=[Object.assign(FC.T.vacaciones(k),{desde:'2026-03-01',hasta:'2026-03-10',disfruto:'si',pagadas:'si',importe:'100'})];
  const a=FC.calcT2(s2);const base=a.rows[0].base;const okA=a.ambas&&Math.abs(a.totD-(a.rows[0].dev-10)*base/30)<0.005&&Math.abs(a.totM-(a.rows[0].dev*base/30-100))<0.005&&a.metodo==='dinero'&&!a.elegido&&a.total===a.totM;k.vac.metodo='dias';const b=FC.calcT2(s2);const t=FC.tabla2({T2:b,c:k});
  return {ok:okA&&b.metodo==='dias'&&b.elegido&&b.total===b.totD&&t.head[3]==='Días disfrutados'&&FC.tabla2({T2:a,c:k}).head[3]==='Pagado',det:[a.totD,a.totM].join(' / ')};});
 T('Pagas extra','Por separado: cada mes sin prorrata y tabla de pagas (2/12); suma igual que prorrateadas si no hay pagos de pagas',()=>{const s2=FC.demo(H),k=s2.c;k.sal.ultimoMes='';const A=FC.calcT1(s2,'prorrata'),B=FC.calcT1(s2,'separado');const dA=A.rows.filter(r=>!r.presc).reduce((s,r)=>s+(r.deb||0),0),dB=B.rows.filter(r=>!r.presc).reduce((s,r)=>s+(r.deb||0),0),pB=B.pagas.reduce((s,p)=>s+(p.dev||0),0);
  const r=B.rows.find(x=>x.deb!=null&&x.cov===x.dim);return {ok:Math.abs(dA-(dB+pB))<0.01&&Math.abs(r.smi-FC.SMI[r.y].m)<0.005&&A.totalPagas===0&&B.totalPagas>0&&FC.pagasMet(k)==='prorrata',det:[dA,dB,pB].map(x=>x.toFixed(2)).join(' / ')};});
 T('Pagas extra','Por separado: lo cobrado como paga extra se resta en su tabla y no en el mes; la papeleta lleva su tabla y su línea de totales',()=>{const s2=FC.demo(H),k=s2.c;k.sal.ultimoMes='';k.sal.fijo='no';const R=FC.calcT1(s2,'prorrata').rows;k.meses=R.map(r=>Object.assign(FC.T.meses(k),{mes:r.key,salario:'900',extra:r.m===12?'500':''}));k.abg.pagasMetodo='separado';
  const B=FC.calcT1(s2);const dic=B.rows.find(r=>r.m===12);const p=B.pagas.find(x=>x.y===dic.y);const t=FC.papText(FC.pap(s2,H));return {ok:dic.perc===900&&p.cob===500&&/3\. Pagas extraordinarias devengadas/.test(t)&&/Subtotal por pagas extraordinarias/.test(t)&&!/Se incluye el prorrateo/.test(t),det:dic.perc+' / '+p.cob};});
 T('Pagas extra','Por separado: el hecho PRIMERO usa el SMI sin prorrata y lo dice',()=>{const s2=FC.demo(H),k=s2.c;k.abg.pagasMetodo='separado';const t=FC.papText(FC.pap(s2,H));k.abg.pagasMetodo='';const t0=FC.papText(FC.pap(s2,H));return {ok:/salario mínimo interprofesional de 1\.221,00 euros \(sin incluir la prorrata de pagas extraordinarias\)/.test(t)&&/1\.831,50 euros \(sin incluir/.test(t)&&/1\.424,50 euros \(incluida prorrata\)/.test(t0)};});
 T('Pagas extra','Por separado: los meses de más de un año no cuentan en las pagas (igual que en la tabla 1)',()=>{const s2=FC.demo(H),k=s2.c;const B=FC.calcT1(s2,'separado');const exp=B.rows.filter(r=>!r.presc&&r.deb!=null).reduce((t,r)=>t+r.deb*2/12,0);return {ok:B.rows.some(r=>r.presc)&&Math.abs(B.totalPagas-exp)<0.01,det:B.totalPagas.toFixed(2)+' / '+exp.toFixed(2)};});
 T('Ficha B','Convenio con el SMI como mínimo: si la tabla queda por debajo, manda el SMI anual',()=>{const s2=FC.demoB(H),k=s2.c;const a=FC.salB(s2,2026);k.conv.tablas=[Object.assign(FC.T.tablas(k),{anio:'2026',base:'900',pluses:'0',pagasNum:'2',pagaImporte:'900'})];const b=FC.salB(s2,2026);k.conv.tablas=[];const c2=FC.salB(s2,2026);
  return {ok:a.fuente==='convenio'&&Math.abs(a.pro-(963.33+766.12+2*2199.47/12))<0.01&&Math.abs(a.sin-1729.45)<0.01&&/^SMI/.test(b.fuente)&&Math.abs(b.anual-1221*14)<0.01&&/sin datos/.test(c2.fuente),det:[a.pro,b.fuente,c2.fuente].join(' / ')};});
 T('Ficha B','Jornada parcial: lo que debía percibir se reduce en proporción a la jornada del convenio',()=>{const s2=FC.demoB(H),k=s2.c;k.conv.jornadaSemanal='40';const w=k.periodos[0].semanas[0];w.turnos=[];for(let i=0;i<5;i++)w.dias[i].tramos=[FC.newTramo(k,'efectivo','09:00','13:00')];FC.dias2turnos(k,w);const r=FC.calcT1(s2).rows.find(x=>x.deb!=null&&x.cov===x.dim);return {ok:Math.abs(r.frac-r.efw/40)<1e-9&&r.frac>0.45&&r.frac<0.56&&Math.abs(r.deb-r.D.sin*r.frac)<0.01,det:r.frac+' / '+r.efw};});
 T('Ficha B','Pagas por separado por defecto si el convenio no permite prorratearlas',()=>{const s2=FC.demoB(H),k=s2.c;const a=FC.pagasMet(k);k.conv.pagasProrrata='si';const b=FC.pagasMet(k);k.abg.pagasMetodo='separado';const c2=FC.pagasMet(k);return {ok:a==='separado'&&b==='prorrata'&&c2==='separado'};});
 T('Ficha B','CIF: válido, control incorrecto y formato incorrecto',()=>({ok:FC.cifCheck('B12345674')===''&&/no corresponde/.test(FC.cifCheck('B12345675'))&&/una letra, 7 números/.test(FC.cifCheck('123'))&&FC.cifCheck('')===''}));
 T('Ficha B','Papeleta con la redacción del escrito de régimen general',()=>{const t=FC.papText(FC.pap(FC.demoB(H),H));return {ok:/Salario base: 963,33 €/.test(t)&&/según clasificación profesional establecida en el Convenio colectivo de trabajo del sector de la Construcción y Obras Públicas de la provincia de Barcelona/.test(t)&&/con la mercantil CONSTRUCCIONES FICTICIAS SL, provista de CIF núm\. B12345674 y con el administrador de la misma D\. PEDRO GÓMEZ PRUEBA \(FICTICIO\), con domicilio sito en .*dedicado a la actividad de construcción de edificios\./.test(t)&&/inicialmente fue contratado de forma irregular \(careciendo de permiso de residencia y trabajo\)/.test(t)&&/artículos 55\.1 del Estatuto de los Trabajadores y 108 de la LRJS/.test(t)&&/Pasando a detallar esta parte algunas de las obras/.test(t)&&/la cantidad fija en las tablas de los anexos del convenio/.test(t)&&!/Real Decreto 1620/.test(t)&&!/[⟪⟫]/.test(t)};});
 T('Ficha B','Importar el resumen del convenio (formato de la skill) y elegir la categoría del puesto',()=>{const s2=FC.newB(),k=s2.c;k.puesto.categoria='Peón';FC.convAplicar(k,{convenio:{nombre:'Convenio X',codigo:'99000000011999'},categorias:[{grupo:'Nivel XII',categoria:'Peón ordinario',salario:{'2025':{base_mensual:1200,pagas:14},'2026':{base_mensual:1250,pagas:14}},articulo:'Anexo I'},{grupo:'Nivel X',categoria:'Oficial de primera',salario:{'2026':{base_mensual:1500,pagas:14}}}],jornada:{semanal_horas:40,anual_horas:1736,articulo:'art. 25'},pagas_extra:{numero:2,prorrateables:false},vacaciones:{dias:30,tipo:'naturales'},preaviso:{dias_por_grupo:'15 días',penalizacion:'un día por día',articulo:'art. 45'}},'prueba');
  return {ok:k.conv.nombre==='Convenio X'&&k.conv.categoria==='Peón ordinario'&&k.conv.tablas.length===2&&k.conv.tablas[1].base==='1250'&&k.conv.tablas[1].pagasNum==='2'&&k.conv.pagasProrrata==='no'&&k.conv.jornadaSemanal==='40'&&/art\. 45/.test(k.conv.preaviso),det:JSON.stringify(k.conv.tablas)};});
 T('Ficha B','Convenios de la app: la búsqueda no distingue tildes ni mayúsculas y encuentra por código',()=>{const L=FC.convFiltra?FC.convFiltra('CONSTRUCCION Y OBRAS PUBLICAS'):[];const k=FC.convFiltra?FC.convFiltra('08001065011994'):[];return {ok:!!window.CONVENIOS&&L.length===1&&k.length===1&&FC.convFiltra('hosteleria madrid').length===0,det:L.length+' / '+k.length};});
 T('Ficha B','Datos de la empresa leídos de axesor: solo rellena lo vacío y avisa si el CIF no coincide',()=>{const s2=FC.newB(),k=s2.c;const e=FC.T.empleadores(k);const p=FC.T.personas(k);k.personas.push(p);e.titular=p.id;e.cif='B12345674';e.razon='Ya Escrita SL';k.empleadores.push(e);FC.empAplicar(k,e,{razon:'Otra SL',cif:'B99999999',cnae:'4121',actividad:'construcción',domicilio:{calle:'Mayor',numero:'1',cp:'08001',municipio:'Barcelona'},administradores:[{cargo:'Administrador único',nombre:'X Y Z'}]});
  return {ok:e.razon==='Ya Escrita SL'&&e.cnae==='4121'&&e.dom.calle==='Mayor'&&e.dom.prov==='08'&&p.nombre==='X Y Z'&&/no coincide/.test(e.fuenteDatos)};});
 T('Ficha B','Empresa: el CIF se pide justo después de elegir empresa o persona; la persona física usa NIF (DNI o NIE)',()=>({ok:FC.nifCheck('12345678Z')===''&&FC.nifCheck('X1234567L')===''&&/letra/.test(FC.nifCheck('12345678A'))&&FC.nifCheck('')===''}));
 T('Correcciones','NIE: solo países de la Unión Europea, con su nombre oficial en la papeleta',()=>{const s2=FC.demo(H),k=s2.c;k.cli.doc='NIE';k.cli.docnum='X1234567L';k.cli.emisorPais='FR';const t=FC.papText(FC.pap(s2,H));return {ok:FC.PAISES_UE.length===27&&FC.PAISES_UE[0][0]==='ES'&&/emitido por la REPÚBLICA FRANCESA/.test(t),det:(t.match(/emitido por [^,]*/)||[''])[0]};});
 T('Papeleta Word','Negritas como el escrito del despacho, DICE subrayado, títulos a 14 y sin «Variante nueva»',()=>{const G=FC.pap(FC.demo(H),H);const x=FC.docXml(G);return {ok:!/Variante nueva/.test(x)&&/<w:b\/><w:sz w:val="28"\/>/.test(x)&&/<w:b\/><w:u w:val="single"\/>.*?DICE:/.test(x)&&/<w:ind w:firstLine="703"\/><\/w:pPr><w:r><w:rPr><w:b\/>[^]*?PRIMERO|1\.- /.test(x)&&/<w:b\/>[^<]*<\/w:rPr><w:t xml:space="preserve">D\.ª ROSA QUISPE MAMANI/.test(x)&&!/[⟪⟫]/.test(x)};});
 T('Documentos','DNI y NIE con letra correcta: válidos',()=>({ok:FC.docCheck('DNI','12345678Z')===''&&FC.docCheck('DNI','12.345.678-z')===''&&FC.docCheck('NIE','X1234567L')===''&&FC.docCheck('nie','Y0000000Z')===''&&FC.docCheck('Pasaporte','ABC')===''}));
 T('Documentos','DNI o NIE con letra o formato incorrecto: aviso',()=>({ok:/no corresponde/.test(FC.docCheck('DNI','12345678A'))&&/8 números/.test(FC.docCheck('DNI','1234567Z'))&&/no corresponde/.test(FC.docCheck('NIE','X1234567T'))&&/X, Y o Z/.test(FC.docCheck('NIE','A1234567L'))}));
 T('Territorio','Sede social del municipio según el CSV',()=>{const m=FC.mun('28176');return {ok:m&&m.social==='MOSTOLES',det:m&&(m.name+' → '+m.social)};});
 st=st0();c=st.c;c.cli.dom=Object.assign(FC.newDir(),{via:'Calle',calle:'Mayor',num:'1',cp:'08001',prov:'28',codm:'28079'});r=FC.evaluate(st,H);
 T('Territorio','Código postal de otra provincia: contradicción',()=>({ok:r.contra.some(x=>x.id==='cp_cli.dom')}));
 c.cli.dom.codm='';r=FC.evaluate(st,H);
 T('Territorio','Municipio escrito pero no elegido de la lista: pendiente',()=>({ok:r.inc.some(x=>x.p==='cli.dom'&&/municipio elegido/.test(x.l))}));
 st=FC.demo(H);FC.st=st;G=FC.pap(st,H);txt=FC.papText(G);
 T('Papeleta','Nunca aparecen las instrucciones internas del ejemplo',()=>({ok:!/ESCRITO ALBERT|SOLO EN CASO DE EXISTIR|PUNTOS A CONSIDERAR|\(RENUNCIA\)|\(SI ES POR MEDIO/.test(txt)}));
 T('Papeleta','Despido verbal con motivos sin documento: textos del ejemplo',()=>({ok:/despidieron verbalmente|despidió verbalmente/.test(txt)&&/motivos que esta parte no reconoce y que no constan acreditados/.test(txt)}));
 T('Organismo','Trabajo en Madrid: encabezamiento automático de la tabla del despacho',()=>({ok:/^A LA CONSEJERÍA DE ECONOMÍA, EMPLEO Y HACIENDA MADRID\n+SERVICIO DE MEDIACIÓN, ARBITRAJE Y CONCILIACIÓN\n/.test(txt),det:txt.split('\n').slice(0,2).join(' / ')}));
 T('Organismo','Se toma del lugar de trabajo aunque el empleador viva en otra provincia',()=>{const e=st.c.empleadores[0].dom;const sv=JSON.stringify(e);Object.assign(e,{prov:'46',codm:'46250',cp:'46001'});const t=FC.papText(FC.pap(st,H));Object.assign(e,JSON.parse(sv));return {ok:/^A LA CONSEJERÍA DE ECONOMÍA, EMPLEO Y HACIENDA MADRID/.test(t)};});
 T('Organismo','Si el abogado elige el domicilio del empleador (Valencia), cambia el organismo',()=>{const e=st.c.empleadores[0].dom;const sv=JSON.stringify(e);Object.assign(e,{prov:'46',codm:'46250',cp:'46001'});st.c.abg.sede='E:'+st.c.empleadores[0].id;const t=FC.papText(FC.pap(st,H));Object.assign(e,JSON.parse(sv));st.c.abg.sede='';return {ok:/^VICEPRESIDENCIA PRIMERA Y CONSELLERIA DE VIVIENDA/.test(t)&&/SECCIÓN DE RELACIONES COLECTIVAS Y CONCILIACIÓN - VALENCIA/.test(t),det:t.split('\n').slice(0,2).join(' / ')};});
 T('Organismo','Ceuta: la tabla no tiene organismo, queda PENDIENTE DE VALIDACIÓN TERRITORIAL',()=>{const l=st.c.lugares[0].dir;const sv=JSON.stringify(l);const m=Object.values(FC.idx.byP['51'])[0];Object.assign(l,{prov:'51',codm:m.codm});const t=FC.papText(FC.pap(st,H));const a=FC.evaluate(st,H).alerts.some(x=>x.cod==='organismo');Object.assign(l,JSON.parse(sv));return {ok:/^PENDIENTE DE VALIDACIÓN TERRITORIAL/.test(t)&&a};});
 T('Organismo','Las 50 provincias con organismo en la tabla y Ceuta y Melilla vacías',()=>{const P=Object.keys(window.TERR.prov);const sin=P.filter(k=>!FC.orgTabla(k));return {ok:P.length===52&&sin.join()==='51,52',det:'sin organismo: '+sin.join(', ')};});
 T('Papeleta','Familiar marcado como empleador por el asesor: entra por defecto y el abogado puede quitarlo',()=>{const a=/se dirige igualmente contra D\. Luis Martín López \(ficticio\), hijo de D\.ª Carmen López Ruiz/.test(txt)&&/con los empleadores/.test(txt)&&/los empleadores despidieron verbalmente/.test(txt);const id=st.c.personas[1].id;st.c.abg.coemp[id]=false;const t2=FC.papText(FC.pap(st,H));delete st.c.abg.coemp[id];return {ok:a&&!/se dirige igualmente/.test(t2)&&/con la empleadora/.test(t2)};});
 T('Papeleta','P017 del ejemplo: 40 + 20 = 60 h, 2.136,75 € y la jornada real (76 h)',()=>({ok:/sumando así un total de 60 horas, la trabajadora debía percibir un salario mensual de 2\.136,75 euros \(incluida prorrata\), aunque la trabajadora en realidad realizaba una jornada de 76 horas semanales\./.test(txt)}));
 T('Papeleta','Interna de lunes a viernes: frase del ejemplo con días libres calculados',()=>{const t=FC.papText(FC.pap(st,H));return {ok:/con carácter de interna, realizando una jornada de lunes a viernes desde las 08:00h hasta las 24:00h/.test(t)&&/librando los sábados desde las 14:00h hasta el lunes a las 08:00h/.test(t),det:(t.match(/con carácter de interna[^.]*\./)||[''])[0].slice(0,220)};});
 T('Papeleta','Burofax: hecho SEXTO; sin burofax, los hechos se renumeran',()=>{const a=/SEXTO\.- ENVÍO DE BUROFAX/.test(txt);st.c.fin.burofax='no';const t2=FC.papText(FC.pap(st,H));st.c.fin.burofax='si';return {ok:a&&/SEXTO\.- DESPIDO IMPROCEDENTE/.test(t2)&&!/BUROFAX/.test(t2)};});
 T('Papeleta','Despido por WhatsApp: se marca como variante nueva',()=>{st.c.fin.medio='whatsapp';const G2=FC.pap(st,H);st.c.fin.medio='verbal';return {ok:/⟦Variante nueva: pendiente de aprobación⟧ Que en fecha .* mensaje de WhatsApp/.test(FC.papText(G2))};});
 T('Papeleta','Trabajador hombre: concordancia en masculino',()=>{st.c.cli.trato='d';const t=FC.papText(FC.pap(st,H));st.c.cli.trato='da';return {ok:/^D\. ROSA/m.test(t)&&/provisto de Pasaporte/.test(t)&&/El trabajador inició/.test(t)&&!/La trabajadora inició/.test(t)};});
 T('Organismo','Corrección del abogado: sustituye a la tabla',()=>{const save=SF.cfg.org['28'];SF.cfg.org['28']={enc1:'A ORGANISMO DE PRUEBA',enc2:'SECCIÓN DE PRUEBA'};const t=FC.papText(FC.pap(st,H));SF.cfg.org['28']=save;if(!save)delete SF.cfg.org['28'];return {ok:/^A ORGANISMO DE PRUEBA\n+SECCIÓN DE PRUEBA/.test(t)};});
 T('Papeleta','Las tablas se generan con los datos de jornada y salario',()=>({ok:/Total diferencia salarial \| TOTAL \| [\d.]+,\d\d €/.test(txt)&&/Total vacaciones \| TOTAL/.test(txt)}));
 st=FC.demo(H);st.c.personas.push(Object.assign(FC.T.personas(st.c),{nombre:'Lucas (ficticio)',papel:'nieto',edad:'7'}));const kk=FC.T.cuidados(st.c);kk.persona=st.c.personas[st.c.personas.length-1].id;kk.colegio='Colegio Ficticio';kk.cu=['colegio'];st.c.cuidados.push(kk);
 T('Papeleta','Menores: solo la edad, nunca el nombre ni el colegio',()=>{const t=FC.papText(FC.pap(st,H));return {ok:/un menor de 7 años/.test(t)&&!/Lucas|Colegio Ficticio/.test(t)};});
 st=st0();st.c.filtro.abogado='si';st.c.filtro.estudiar='no';r=FC.evaluate(st,H);
 T('Filtro','Caso con otro abogado que no quiere cambiar: solo contacto',()=>({ok:FC.soloContacto(st.c)&&r.inc.every(x=>x.s<=1)&&r.alerts.some(a=>a.cod==='solo_contacto'),det:r.inc.map(x=>x.l).join(', ')}));
 st=st0();st.c.fin.tipo='despido';st.c.fin.fechaCom=SF.wdBack(H,25);r=FC.evaluate(st,H);
 T('Plazos','Despido hace 25 días laborables: alerta crítica aunque falte todo lo demás',()=>({ok:r.alerts.some(a=>a.cod==='cad_posible'&&a.nivel==='critica')}));
 T('Conversión','Una ficha C antigua se convierte sin perder los datos principales',()=>{const old=SF.buildScen('C',H);const n=FC.migrate(old);return {ok:n.v===2&&n.c.cli.nombre===SF.V(old,'cli_nombre')&&n.c.cuidados.length===old.cuidados.length&&n.c.empleadores.length===1,det:`${n.c.personas.length} personas, ${n.c.cuidados.length} cuidados`};});
 st=FC.demo(H);FC.st=st;txt=FC.papText(FC.pap(st,H));
 T('Revisión Word','D.ª en vez de Dña. y apellidos separados',()=>({ok:/^D\.ª ROSA QUISPE MAMANI \(FICTICIA\), mayor de edad/m.test(txt)&&!/Dña\./.test(txt)}));
 T('Revisión Word','Sin apellidos: se marca el hueco',()=>{const a=st.c.cli.apellidos;st.c.cli.apellidos='';const t=FC.papText(FC.pap(st,H));st.c.cli.apellidos=a;return {ok:/D\.ª ROSA ⟦apellidos⟧/.test(t)};});
 T('Revisión Word','Gentilicio en minúsculas desde el país elegido',()=>({ok:/de nacionalidad peruana, fue contratada/.test(txt)&&/emitido por la REPÚBLICA DEL PERÚ/.test(txt)}));
 T('Revisión Word','El encabezamiento DICE no lleva marca de variante',()=>({ok:/\n\nQue interesa de este centro el intento de celebración de conciliación obligatoria por DESPIDO IMPROCEDENTE CON ACUMULACIÓN DE RECLAMACIÓN DE CANTIDAD con los empleadores/.test(txt)}));
 T('Revisión Word','Materia: las cuatro fórmulas del despacho',()=>{const m=()=>(FC.papText(FC.pap(st,H)).match(/obligatoria por (.*?) con (los|la|el) /)||[])[1];const r=[];st.c.abg.acum='no';r.push(m());st.c.abg.calif='nulo';st.c.abg.acum='si';r.push(m());st.c.abg.calif='';st.c.abg.acum='';const ft=st.c.fin.tipo;st.c.fin.tipo='continua';r.push(m());st.c.fin.tipo=ft;
  return {ok:r[0]==='DESPIDO IMPROCEDENTE'&&r[1]==='DESPIDO NULO POR VULNERACIÓN DE DERECHOS FUNDAMENTALES Y SUBSIDIARIAMENTE IMPROCEDENTE, CON ACUMULACIÓN DE ACCIÓN DE RECLAMACIÓN DE CANTIDAD'&&r[2]==='RECLAMACIÓN DE CANTIDAD',det:r.join(' | ')};});
 T('Revisión Word','Sin calificación del abogado: título DESPIDO IMPROCEDENTE y párrafo fijo',()=>({ok:/\.- DESPIDO IMPROCEDENTE\.\nAl efectuarse el despido incumpliendo los requisitos de forma establecidos legalmente en el artículo 11\.3/.test(txt)}));
 st=FC.demo(H);c=st.c;Object.assign(c.rel,{autGlobal:'siempre',alta:'no'});{const w=c.periodos[0].semanas[0];const t=FC.newTurno(c,[0,1,2,3,4,5,6]);Object.assign(t,{e:'09:00',s:'00:30'});w.turnos=[t];}
 T('Revisión Word','98 h efectivas sin presencia: cuenta 60 h y 2.136,75 €',()=>{const t=FC.papText(FC.pap(st,H));return {ok:/2\.136,75 euros \(incluida prorrata\), aunque la trabajadora en realidad realizaba una jornada de 108,5 horas semanales/.test(t),det:(t.match(/debía percibir[^.]*\./)||[''])[0]};});
 T('Revisión Word','Sin día libre: no inventa una libranza',()=>{const t=FC.papText(FC.pap(st,H));return {ok:/sin disfrutar de ningún día de descanso semanal/.test(t)&&!/librando/.test(t)};});
 T('Revisión Word','Contrato verbal con autorización y sin alta: «, sin haberse procedido…»',()=>{const t=FC.papText(FC.pap(st,H));return {ok:/con carácter indefinido, en virtud del art\. 8\.1 del Estatuto de los Trabajadores, sin haberse procedido a la correspondiente alta en la seguridad social como trabajadora\./.test(t)&&!/de forma irregular/.test(t)};});
 st=FC.demo(H);c=st.c;c.sal.fijo='no';c.meses=[['2026-06',1100],['2026-07',1100],['2026-08',1300],['2026-09',650]].map(([k,v])=>Object.assign(FC.T.meses(c),{mes:k,salario:String(v),forma:'efectivo'}));
 T('Revisión Word','Meses iguales agrupados y con nombre del mes',()=>{const t=FC.papText(FC.pap(st,H));return {ok:/desde JUNIO DEL 2026 hasta JULIO DEL 2026 percibió 1\.100,00 euros mensuales, en AGOSTO DEL 2026 percibió 1\.300,00 euros y en SEPTIEMBRE DEL 2026 percibió 650,00 euros/.test(t),det:(t.match(/percibía cantidades[^\n]*/)||[''])[0]};});
 T('Revisión Word','Si todos los meses son iguales, frase fija del ejemplo',()=>{c.meses.forEach(m=>m.salario='1100');const t=FC.papText(FC.pap(st,H));return {ok:/percibía un salario mensual de 1\.100,00\.- euros en efectivo metálico\./.test(t)};});
 st=FC.demo(H);c=st.c;c.cuidados=[];
 T('Revisión Word','Titular mayor aunque no se haya rellenado su ficha de cuidados: párrafo del titular',()=>{const t=FC.papText(FC.pap(st,H));return {ok:/atender las necesidades cotidianas de D\.ª Carmen López Ruiz \(ficticia\), de 88 años de edad, quien actuaba como titular del hogar familiar/.test(t)};});
 T('Revisión Word','El Word se genera con Arial 12, justificado, sangría 1,24 cm, 8 pt después e interlineado 1,5',()=>{const st2=FC.demo(H);const z=FC.docx(FC.pap(st2,H));const x=FC._lastDocXml;return {ok:z&&z.length>2000&&/w:ascii="Arial"/.test(FC._lastStyles)&&/<w:sz w:val="24"\/>/.test(FC._lastStyles)&&/<w:jc w:val="both"\/>/.test(FC._lastStyles)&&/w:firstLine="703"/.test(FC._lastStyles)&&/w:after="160"/.test(FC._lastStyles)&&/w:line="360"/.test(FC._lastStyles)&&/<w:tbl>/.test(x),det:z?z.length+' bytes':'sin archivo'};});
 T('Turnos','Ejemplo de la calculadora: L–V 09:00–00:30 con 120 min, S–D 08:00–09:00, S 22:00–00:00, D 22:00–00:30 = 74 h',()=>{const s=FC.newSemana(st0().c);const c2=st0().c;const mk=(d,e,x,m)=>Object.assign(FC.newTurno(c2,d),{e,s:x,descMin:m});s.turnos=[mk([0,1,2,3,4],'09:00','00:30','120'),mk([5,6],'08:00','09:00','0'),mk([5],'22:00','00:00','0'),mk([6],'22:00','00:30','0')];const W=FC.semana(s);return {ok:Math.abs(W.ef-74)<1e-9,det:n1(W.ef)+' h'};});
 T('Turnos','Descanso con horario (14:00–16:00) se descuenta y queda registrado',()=>{const c2=st0().c;const s=FC.newSemana(c2);const t=Object.assign(FC.newTurno(c2,[0]),{e:'08:00',s:'22:00'});t.desc=[Object.assign(FC.newDesc(c2),{e:'14:00',s:'16:00'})];s.turnos=[t];const W=FC.semana(s);return {ok:W.ef===12&&W.desc===2};});
 T('Turnos','Descanso de madrugada en un turno nocturno (22:00–06:00 con descanso 02:00–03:00)',()=>{const c2=st0().c;const s=FC.newSemana(c2);const t=Object.assign(FC.newTurno(c2,[0]),{e:'22:00',s:'06:00'});t.desc=[Object.assign(FC.newDesc(c2),{e:'02:00',s:'03:00'})];s.turnos=[t];const W=FC.semana(s);return {ok:W.ef===7&&W.noct===7&&W.desc===1,det:`${W.ef} h, ${W.noct} nocturnas`};});
 T('Turnos','Una semana guardada por días se convierte a turnos sin cambiar las horas',()=>{const st2=FC.demo(H);const w=st2.c.periodos[0].semanas[0];return {ok:w.turnos.length>=2&&Math.abs(FC.semana(w).ef-66)<1e-9&&Math.abs(FC.semana(w).pres-10)<1e-9,det:w.turnos.length+' turnos, '+n1(FC.semana(w).ef)+' h'};});
 st=FC.demo(H);c=st.c;
 T('Correcciones','Nacionalidad siempre en femenino («de nacionalidad peruana»), también si es un hombre',()=>{c.cli.trato='d';const t=FC.papText(FC.pap(st,H));c.cli.trato='da';return {ok:/de nacionalidad peruana/.test(t)};});
 T('Correcciones','NIE: «emitido por el Reino de España» por defecto, o el país que se elija',()=>{c.cli.doc='NIE';c.cli.docnum='X0000000T';const a=FC.papText(FC.pap(st,H));c.cli.emisorPais='PT';const b=FC.papText(FC.pap(st,H));c.cli.doc='Pasaporte';c.cli.emisorPais='';return {ok:/provista de NIE núm\. X0000000T, emitido por el REINO DE ESPAÑA/.test(a)&&/emitido por la REPÚBLICA PORTUGUESA/.test(b)};});
 T('Correcciones','Año de reclamación: hoy 26/10/2026 → desde 01/10/2025; con inicio posterior, desde el inicio',()=>{const sv=c.rel.inicio;c.rel.inicio='2026-02-10';const v1=FC.ventana(c);c.rel.inicio='2024-03-15';const v2=FC.ventana(c);const T1=FC.calcT1(st);c.rel.inicio=sv;const first=T1.rows.find(r=>!r.presc);return {ok:v1.desde==='2026-02-10'&&v2.desde==='2025-10-01'&&first&&first.key==='2025-10'&&T1.rows.filter(r=>r.presc).length===19,det:`${v1.desde} · ${v2.desde} · primer mes ${first&&first.key}`};});
 T('Correcciones','Edad de la titular fuera de 18–130: contradicción',()=>{const p=c.personas[0];const e=p.edad;p.edad='1';const r=FC.evaluate(st,H);p.edad=e;return {ok:r.contra.some(x=>x.id==='edad_'+p.id)};});
 T('Correcciones','Teléfono con prefijo: +34 por defecto y solo números',()=>({ok:FC.telFull('','600 000-303')==='+34 600000303'&&FC.telFull('PE','987654321')==='+51 987654321'}));
 T('Totales','Importe en letra como en el ejemplo: 14.318,51 €',()=>{const t=FC.letras(14318.51);return {ok:t==='CATORCE MIL TRESCIENTOS DIECIOCHO EUROS Y CINCUENTA Y UN CÉNTIMOS',det:t};});
 T('Totales','Letras: 1.000.021,01 y 21.100 €',()=>{const a=FC.letras(1000021.01),b=FC.letras(21100);return {ok:a==='UN MILLÓN VEINTIÚN EUROS Y UN CÉNTIMO'&&b==='VEINTIÚN MIL CIEN EUROS',det:a+' | '+b};});
 T('Totales','Ejemplo de la captura: 11.228,38 + 1.788,45 = 13.016,83; mora 1.301,68; total 14.318,51',()=>{const t=FC.totales({T1:{total:11228.38,debidas:0,pagoFinal:0},T2:{total:1788.45}});return {ok:t.principal===13016.83&&t.mora===1301.68&&t.total===14318.51};});
 st=FC.demo(H);c=st.c;c.rel.inicio='2024-03-01';
 T('Totales','Vacaciones: suma todos los años, no solo el último',()=>{const T2=FC.calcT2(st);const sum=T2.rows.reduce((s,r)=>s+(r.imp>0?r.imp:0),0);return {ok:T2.rows.length===3&&Math.abs(T2.total-sum)<0.005&&T2.rows.every(r=>!r.anterior),det:T2.rows.map(r=>r.y+': '+eurN(r.imp||0)).join(' · ')};});
 T('Totales','La papeleta incluye la tabla de totales tras la TABLA 2',()=>{const t=FC.papText(FC.pap(st,H));return {ok:/Total vacaciones[\s\S]*TOTALES CANTIDADES RECLAMADAS[\s\S]*Mora 10%[\s\S]*Total Pendiente: [\d.]+,\d\d €\n  [A-ZÁÉÍÓÚ ]+ EUROS/.test(t)};});
 st=FC.demo(H);c=st.c;c.sal.ultimoMes='';c.rel.alta='no';c.rel.inicio='2025-06-15';c.fin.fechaFin='2026-09-15';c.fin.fechaCom='2026-09-15';c.sal.fijo='no';c.meses=[];for(const [k,v] of [['2025-10',1100],['2025-11',1100],['2025-12',1100],['2026-01',1100],['2026-02',1100],['2026-03',1100],['2026-04',1100],['2026-05',1100],['2026-06',1100],['2026-07',1300],['2026-08',1300],['2026-09',650]])c.meses.push(Object.assign(FC.T.meses(c),{mes:k,salario:String(v)}));
 T('Tabla 1','Formato del despacho: título con el periodo, meses con nombre, mes incompleto con sus días y fila de total (ejemplo: 11.228,38 €)',()=>{const G=FC.pap(st,H);const t=FC.tabla1(G);return {ok:t.titulo==='1. Diferencias salariales por el periodo del 01/10/2025 al 15/09/2026'&&t.rows[0][0]==='Octubre 2025'&&t.rows[11][0]==='Septiembre 2026 (15 días)'&&t.rows[11][1]==='1.068,38 €'&&t.foot[3]==='11.228,38 €',det:t.titulo+' · '+t.rows[11].join(' / ')+' · '+t.foot[3]};});
 st=FC.demo(H);c=st.c;
 T('Google Maps','La búsqueda usa vía, número, portal, código postal, municipio y provincia; no escalera, piso ni puerta',()=>{const d=Object.assign(FC.newDir(),{via:'Calle',calle:'de Abtao',num:'20',bloque:'',esc:'izquierda',piso:'2',puerta:'C',cp:'28007',prov:'28',codm:'28079'});const q=FC.dirQuery(d);return {ok:q==='Calle de Abtao 20, 28007 Madrid, Madrid, España'&&/google\.com\/maps\/search\/\?api=1&query=/.test(FC.gmapsUrl(d)),det:q};});
 T('Google Maps','Si cambia la calle después de comprobarla, vuelve a quedar pendiente; si cambia el piso, no',()=>{const d=c.lugares[0].dir;const a=FC.dirComprobada(d);d.piso='7';const b=FC.dirComprobada(d);d.num='99';const r=FC.evaluate(st,H);const x=FC.dirComprobada(d);return {ok:a&&b&&!x&&r.inc.some(i=>/Lugar de trabajo 1: comprobar en Google Maps/.test(i.l)),det:r.inc.map(i=>i.l).join('; ')};});
 FC._hoy=prev;return out;};
})();
