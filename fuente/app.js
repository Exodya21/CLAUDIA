(function(){
const SF = window.SF = {};
/* ================= utilidades ================= */
const DAY=864e5;
SF.pd=s=>{if(!s||typeof s!=='string')return null;const p=s.split('-').map(Number);if(p.length!==3||!p[0]||!p[1]||!p[2])return null;return Date.UTC(p[0],p[1]-1,p[2]);};
SF.iso=t=>{const d=new Date(t);return d.getUTCFullYear()+'-'+String(d.getUTCMonth()+1).padStart(2,'0')+'-'+String(d.getUTCDate()).padStart(2,'0');};
SF.fmt=s=>{const t=SF.pd(s);return t==null?'—':new Date(t).toLocaleDateString('es-ES',{timeZone:'UTC',day:'2-digit',month:'2-digit',year:'numeric'});};
SF.fmtL=s=>{const t=SF.pd(s);return t==null?'—':new Date(t).toLocaleDateString('es-ES',{timeZone:'UTC',day:'numeric',month:'long',year:'numeric'});};
SF.today=()=>{const n=new Date();return n.getFullYear()+'-'+String(n.getMonth()+1).padStart(2,'0')+'-'+String(n.getDate()).padStart(2,'0');};
SF.wd=(a,b)=>{const ta=SF.pd(a),tb=SF.pd(b);if(ta==null||tb==null||tb<=ta)return 0;let c=0;for(let t=ta+DAY;t<=tb;t+=DAY){const w=new Date(t).getUTCDay();if(w>0&&w<6)c++;}return c;};
SF.wdBack=(hoy,n)=>{let t=SF.pd(hoy),c=0;while(c<n){const w=new Date(t).getUTCDay();if(w>0&&w<6)c++;t-=DAY;}return SF.iso(t);};
SF.wdDay=(h,n)=>SF.iso(SF.pd(SF.wdBack(h,n))+DAY);
SF.addDays=(s,n)=>SF.iso(SF.pd(s)+n*DAY);
SF.days=(a,b)=>Math.round((SF.pd(b)-SF.pd(a))/DAY);
SF.ageAt=(b,at)=>{const x=new Date(SF.pd(at)),y=new Date(SF.pd(b));let a=x.getUTCFullYear()-y.getUTCFullYear();if(x.getUTCMonth()<y.getUTCMonth()||(x.getUTCMonth()===y.getUTCMonth()&&x.getUTCDate()<y.getUTCDate()))a--;return a;};
SF.minDate=arr=>{const v=arr.filter(Boolean).sort((a,b)=>SF.pd(a)-SF.pd(b));return v[0]||null;};
/* meses entre a (incluido) y b (excluido); la fracción de mes cuenta como mes completo */
SF.monthsCeil=(a,b)=>{const A=new Date(SF.pd(a)),B=new Date(SF.pd(b));if(B<=A)return 0;let m=(B.getUTCFullYear()-A.getUTCFullYear())*12+(B.getUTCMonth()-A.getUTCMonth());if(B.getUTCDate()<A.getUTCDate())m--;const anchor=Date.UTC(A.getUTCFullYear(),A.getUTCMonth()+m,A.getUTCDate());return m+(B.getTime()>anchor?1:0);};
SF.PROV=['Araba/Álava','Albacete','Alicante','Almería','Ávila','Badajoz','Illes Balears','Barcelona','Burgos','Cáceres','Cádiz','Castellón','Ciudad Real','Córdoba','A Coruña','Cuenca','Girona','Granada','Guadalajara','Gipuzkoa','Huelva','Huesca','Jaén','León','Lleida','La Rioja','Lugo','Madrid','Málaga','Murcia','Navarra','Ourense','Asturias','Palencia','Las Palmas','Pontevedra','Salamanca','Santa Cruz de Tenerife','Cantabria','Segovia','Sevilla','Soria','Tarragona','Teruel','Toledo','Valencia','Valladolid','Bizkaia','Zamora','Zaragoza','Ceuta','Melilla'];
SF.VIAS=['Calle','Avenida','Plaza','Paseo','Carretera','Camino','Ronda','Travesía','Glorieta','Urbanización','Polígono','Otro'];
SF.provDeCP=cp=>{if(!/^\d{5}$/.test(cp||''))return null;const n=+cp.slice(0,2);return n>=1&&n<=52?SF.PROV[n-1]:null;};
SF.dirFalta=d=>{if(!d||typeof d!=='object')return ['dirección'];const f=[];if(!d.calle)f.push('nombre de la vía');if(!d.num)f.push('número (o «s/n»)');if(!/^\d{5}$/.test(d.cp||''))f.push('código postal');if(!d.loc)f.push('localidad');if(!d.prov)f.push('provincia');return f;};
SF.fmtDir=(d,P,conInd)=>{const m=x=>P?P(x):'['+x+']';if(!d||typeof d!=='object')return m('dirección completa');const via=d.via&&d.via!=='Otro'?d.via+' ':'';const parts=[d.calle?via+d.calle:m('nombre de la vía'),d.num?(/^s\/?n$/i.test(d.num)?'s/n':'n.º '+d.num):m('número')];const pi=[d.bloque?'portal '+d.bloque:'',d.esc?'esc. '+d.esc:'',d.piso?d.piso+(/^\d+$/.test(d.piso)?'.º':''):'',d.puerta||''].filter(Boolean).join(' ');if(pi)parts.push(pi);parts.push(`${/^\d{5}$/.test(d.cp||'')?d.cp:m('código postal')} ${d.loc||m('localidad')}`);let r=parts.join(', ')+` (${d.prov||m('provincia')})`;if(conInd&&d.ind)r+=' — '+d.ind;return r;};
const lcf=x=>x?x.charAt(0).toLowerCase()+x.slice(1):x;
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
SF.esc=esc;
const eur=n=>{const neg=n<0;const [e,d]=Math.abs(Math.round(n*100)/100).toFixed(2).split('.');return (neg?'-':'')+e.replace(/\B(?=(\d{3})+(?!\d))/g,'.')+','+d+' €';};
const num1=n=>(Math.round(n*10)/10).toLocaleString('es-ES',{maximumFractionDigits:1});
SF.eur=eur;

/* SMI mensual en 14 pagas. 2026: RD 126/2026 (BOE 19/02/2026). 2025: RD 87/2025. 2024: RD 145/2024. */
SF.SMI={2015:648.6,2016:655.2,2017:707.7,2018:735.9,2019:900,2020:950,2021:965,2022:1000,2023:1080,2024:1134,2025:1184,2026:1221};
SF.smiMes=year=>{const y=Math.min(Math.max(year,2015),2026);return SF.SMI[y]*14/12;};

SF.TIPOS={
 A:{k:'A',corto:'Régimen general con papeles',d:'Tiene permiso para trabajar en España, aunque no tenga contrato escrito ni nóminas.',emp:'la empresa',Emp:'La empresa',paso2:'Empresa o empleador'},
 B:{k:'B',corto:'Régimen general sin papeles',d:'No tiene permiso para trabajar. Da igual si hubo contrato, alta o nóminas: sus derechos laborales existen.',emp:'la empresa',Emp:'La empresa',paso2:'Empresa o empleador'},
 C:{k:'C',corto:'Empleada de hogar sin papeles',d:'Trabajó en una casa particular (limpieza, cuidados, cocina) sin permiso para trabajar.',emp:'la parte empleadora',Emp:'La parte empleadora',paso2:'Empleador o empleadora'}
};

/* ================= preguntas ================= */
const STEPS=['Cliente','Empleador','Relación laboral','Jornada y salario','Qué ocurrió','Pruebas','Revisión','Papeleta'];
SF.STEPS=STEPS;
const V=(st,id)=>{const a=st.ans[id];if(!a||a.ns)return undefined;const v=a.v;if(v===''||v==null||(Array.isArray(v)&&!v.length))return undefined;if(typeof v==='object'&&!Array.isArray(v)&&!Object.values(v).some(x=>x))return undefined;return v;};
const NS=(st,id)=>!!(st.ans[id]&&st.ans[id].ns);
SF.V=V;SF.NS=NS;
const DESP=['despido','no_llaman','fin_contrato','baja_forzada'];
const despLike=st=>DESP.includes(V(st,'ext_tipo'));
SF.despLike=despLike;
const inc=(st,id,x)=>(V(st,id)||[]).includes(x);
const SI=[['si','Sí'],['no','No']];

SF.Q=[
 /* 0 · Cliente */
 {id:'cli_trato',s:0,ty:'op',req:1,c:'Tratamiento',t:'¿Cómo hay que nombrarle en los papeles?',o:[['d','Don (D.)'],['da','Doña (D.ª)']]},
 {id:'cli_nombre',s:0,ty:'txt',req:1,c:'Nombre',t:'Nombre y apellidos',h:'Tal como salen en su documento. Ejemplo: María López García. En este prototipo, solo nombres inventados.'},
 {id:'cli_doc',s:0,ty:'op',req:1,ns:1,c:'Documento',t:'¿Qué documento de identidad tiene?',h:'DNI es el de los españoles. NIE es el número de extranjero. Si solo tiene pasaporte, vale igual.',o:[['DNI','DNI'],['NIE','NIE'],['pasaporte','Pasaporte'],['ninguno','Ninguno']]},
 {id:'cli_docnum',s:0,ty:'txt',req:1,ns:1,c:'Número de documento',t:'Número del documento',show:st=>['DNI','NIE','pasaporte'].includes(V(st,'cli_doc'))},
 {id:'cli_nac',s:0,ty:'date',ns:1,c:'Fecha de nacimiento',t:'Fecha de nacimiento',h:'Sirve para saber si era menor de edad cuando empezó a trabajar.'},
 {id:'cli_tel',s:0,ty:'txt',req:1,c:'Teléfono',t:'Teléfono con WhatsApp',h:'Pida también el número de un familiar por si cambia de móvil.'},
 {id:'cli_email',s:0,ty:'txt',req:1,ns:1,c:'Correo electrónico',t:'Correo electrónico',h:'Además del WhatsApp. Sirve para enviarle documentos y avisos. Si no tiene, marque «No lo sabe» y explíquelo abajo.'},
 {id:'cli_dom',s:0,ty:'dir',req:1,c:'Domicilio',t:'¿Dónde vive? Dirección exacta',h:'Rellene cada casilla. El código postal fija la provincia y el juzgado: sin una dirección exacta no se puede notificar.'},
 {id:'cli_permiso',s:0,ty:'op',req:1,ns:1,c:'Permiso de trabajo',t:'Mientras trabajó allí, ¿tenía permiso para trabajar en España?',h:'Pregunte sin juzgar. Tener o no papeles no le quita el derecho a cobrar lo trabajado.',o:[['si','Sí'],['no','No'],['tramite','Estaba en trámite']]},
 {id:'cli_interp',s:0,ty:'op',c:'Necesita intérprete',t:'¿Necesita intérprete?',o:SI},
 {id:'cli_rep',s:0,f:'AB',ty:'op',ns:1,c:'Representante de los trabajadores',t:'En el último año, ¿fue delegado o representante de los trabajadores?',h:'Casi nunca pasa, pero la papeleta tiene que decirlo.',o:SI},

 /* 1 · Empleador */
 {id:'emp_tipo',s:1,f:'AB',ty:'op',req:1,ns:1,c:'Tipo de empleador',t:'¿Para quién trabajaba?',h:'Pista: si en nóminas, facturas o el cartel pone «S.L.» o «S.A.», es una empresa.',o:[['empresa','Una empresa o sociedad'],['autonomo','Un autónomo (una persona con su negocio)']]},
 {id:'emp_nombre',s:1,f:'AB',ty:'txt',req:1,ns:1,c:'Nombre de la empresa',t:'¿Cómo se llama la empresa?',h:'Como sale en nóminas o facturas. Si solo sabe el nombre del local (por ejemplo «Bar La Esquina»), escríbalo: el despacho buscará el nombre legal.',show:st=>V(st,'emp_tipo')!=='autonomo'},
 {id:'emp_cif',s:1,f:'AB',ty:'txt',ns:1,c:'CIF de la empresa',t:'¿Sabe el CIF de la empresa?',h:'Es el número fiscal de la empresa, como el NIT en Colombia. Ejemplo: B12345678. Sale en nóminas y tickets.',show:st=>V(st,'emp_tipo')!=='autonomo'},
 {id:'aut_nombre',s:1,f:'AB',ty:'txt',req:1,ns:1,c:'Nombre del autónomo',t:'Nombre y apellidos del dueño',show:st=>V(st,'emp_tipo')==='autonomo'},
 {id:'aut_dni',s:1,f:'AB',ty:'txt',ns:1,c:'DNI/NIE del autónomo',t:'¿Sabe su DNI o NIE?',show:st=>V(st,'emp_tipo')==='autonomo'},
 {id:'aut_negocio',s:1,f:'AB',ty:'txt',c:'Nombre del negocio',t:'Nombre del negocio, si tiene',h:'Ejemplo: «Reformas Pepe».',show:st=>V(st,'emp_tipo')==='autonomo'},
 {id:'emp_dom',s:1,f:'AB',ty:'dir',req:1,ns:1,c:'Domicilio del empleador',t:'¿Dónde está la oficina de la empresa o dónde vive el dueño?',h:'Es la dirección a la que se envían los papeles oficiales. Si no la sabe, márquelo: el despacho la buscará.'},
 {id:'emp_centro',s:1,f:'AB',ty:'dir',req:1,c:'Lugar de trabajo',t:'¿En qué dirección trabajaba?',h:'El sitio donde iba cada día. Si era un local dentro de un centro comercial, ponga el número de local en «Puerta».'},
 {id:'emp_otros',s:1,f:'AB',ty:'op',c:'Otros centros',t:'¿Trabajaba también en otros sitios para ellos?',o:SI},
 {id:'emp_otros_txt',s:1,f:'AB',ty:'txt',c:'Otros centros (direcciones)',t:'¿Qué otros sitios? Direcciones',show:st=>V(st,'emp_otros')==='si'},
 {id:'emp_estado',s:1,f:'AB',ty:'op',ns:1,c:'Situación del negocio',t:'¿El negocio sigue abierto?',o:[['abierto','Sí, sigue abierto'],['cerrado','Cerró o desapareció'],['concurso','Está en quiebra o concurso']]},
 {id:'hog_dir',s:1,f:'C',ty:'dir',req:1,c:'Dirección de la casa',t:'¿En qué dirección estaba la casa donde trabajaba?',h:'Dirección completa con piso y puerta: es donde se citará a la persona empleadora.'},

 /* 2 · Relación laboral (las preguntas de quién contrató/mandaba/pagaba van en el bloque de personas) */
 {id:'rel_inicio',s:2,ty:'date',req:1,ns:1,aprox:1,c:'Inicio',t:'¿Cuándo empezó a trabajar allí?',h:'La fecha real, aunque el contrato diga otra. Si duda, busque el primer mensaje con el jefe o el primer pago.'},
 {id:'hog_interna',s:2,f:'C',ty:'op',req:1,c:'Interna o externa',t:'¿Era interna o externa?',h:'Interna: vivía y dormía en la casa. Externa: iba a trabajar y volvía a su casa. Si cambió con el tiempo, explíquelo abajo con las fechas.',o:[['interna','Interna'],['externa','Externa']]},
 {id:'hog_pernocta',s:2,f:'C',ty:'op',c:'Dormía en la casa',t:'¿Dormía en la casa todas las noches?',o:[['si','Sí'],['algunas','Algunas noches'],['no','No']],show:st=>V(st,'hog_interna')==='interna'},
 {id:'hog_contexto',s:2,f:'C',ty:'area',c:'Cómo era la casa',t:'¿Cómo era trabajar en esa casa? Cuente el contexto',h:'Cómo se organizaba la familia, quién estaba en casa y cuándo, cómo le daban las instrucciones (en persona, notas, WhatsApp), si estaba sola con las personas que cuidaba, qué pasaba los fines de semana. Ejemplo: «Los padres salían a las 8 y volvían a las 20; ella se quedaba sola con los niños y la abuela todo el día».'},
 {id:'hog_mascotas',s:2,f:'C',ty:'txt',c:'Mascotas',t:'¿Había mascotas? ¿Cuáles y qué hacía con ellas?',h:'Ejemplo: «un perro, que sacaba a pasear dos veces al día».'},
 {id:'hog_llaves',s:2,f:'C',ty:'op',c:'Tenía llaves',t:'¿Tenía llaves de la casa?',h:'Tener llaves demuestra la confianza y que trabajaba allí.',o:SI},
 {id:'hog_alarma',s:2,f:'C',ty:'op',c:'Conocía la alarma',t:'¿Conocía el código de la alarma?',o:SI},
 {id:'hog_segunda',s:2,f:'C',ty:'op',c:'Otra casa de la familia',t:'¿Iba con la familia a otra casa (playa, pueblo) en vacaciones o fines de semana?',o:SI},
 {id:'hog_segunda_txt',s:2,f:'C',ty:'txt',c:'Dónde y cuándo',t:'¿Dónde está esa casa y cuándo iba?',h:'Ejemplo: «una casa en Cullera (Valencia), en julio y agosto».',show:st=>V(st,'hog_segunda')==='si'},
 {id:'rel_antes',s:2,f:'AB',ty:'op',c:'Trabajo anterior con ellos',t:'¿Había trabajado antes para ellos y lo dejó un tiempo?',o:SI},
 {id:'rel_antes_txt',s:2,f:'AB',ty:'txt',c:'Época anterior',t:'¿Cuándo fue esa otra época?',show:st=>V(st,'rel_antes')==='si'},
 {id:'rel_como',s:2,f:'BC',ty:'area',c:'Cómo empezó',t:'¿Cómo consiguió el trabajo? Cuente cómo empezó todo',h:'Quién le habló del trabajo, cómo fue la primera conversación, qué le prometieron (sueldo, horario, papeles), el primer día. Ejemplo: «Una prima que trabajaba en el edificio le presentó a la señora; le dijo que serían 1.000 € y que la daría de alta en unos meses».'},
 {id:'hist_trato',s:2,ty:'area',c:'Cómo la trataban',t:'¿Cómo le trataban? Cuente cómo era la relación',h:'Si había gritos o malas caras, si le cambiaban el horario sin avisar, si le prometieron papeles o subir el sueldo y no cumplieron, si le pagaban tarde. Con ejemplos y fechas si las recuerda.'},
 {id:'hist_cambios',s:2,ty:'area',c:'Qué cambió con el tiempo',t:'¿Cambió algo con el tiempo?',h:'Más tareas, otra persona a cuidar, más horas, menos sueldo, cuando enfermó alguien de la casa… Ejemplo: «Desde enero la abuela empeoró y tenía que levantarse cada noche».'},
 {id:'rel_dondeempezo',s:2,f:'B',ty:'txt',c:'Dónde empezó',t:'¿Dónde empezó a trabajar el primer día?'},
 {id:'rel_contrato',s:2,f:'AB',ty:'op',ns:1,req:1,c:'Contrato escrito',t:'¿Tenía contrato escrito?',o:SI},
 {id:'rel_contrato_fecha',s:2,f:'A',ty:'date',ns:1,c:'Fecha del contrato',t:'¿Qué fecha de inicio pone el contrato?',h:'Si es posterior a la fecha real, la papeleta reclamará la real.',show:st=>V(st,'rel_contrato')==='si'},
 {id:'rel_alta',s:2,f:'AB',ty:'op',ns:1,req:1,c:'Alta en la Seguridad Social',t:'¿Estaba dado de alta en la Seguridad Social?',h:'Estar de alta es estar afiliado y cotizando, como estar afiliado a salud y pensión en Colombia. Se comprueba con la vida laboral.',o:SI},
 {id:'rel_nominas',s:2,f:'A',ty:'op',c:'Tiene nóminas',t:'¿Tiene nóminas?',o:SI},
 {id:'rel_puesto',s:2,f:'AB',ty:'txt',ns:1,c:'Puesto en contrato o nómina',t:'¿Qué puesto pone en su contrato o nómina?',h:'Cópielo tal cual, por ejemplo «Ayudante de cocina». No confunda con el «grupo de cotización», que es un número del 1 al 11.',show:st=>V(st,'rel_contrato')==='si'||V(st,'rel_nominas')==='si'},
 {id:'rel_trabajo',s:2,f:'AB',ty:'txt',req:1,c:'Trabajo que hacía',t:'¿Qué trabajo hacía?',h:'En pocas palabras. Ejemplo: camarero, peón de obra, dependienta.'},
 {id:'hog_tareas',s:2,f:'C',ty:'multi',req:1,c:'Tareas',t:'¿Qué tareas hacía?',o:[['limpieza','Limpieza'],['cocina','Cocina'],['plancha','Lavar y planchar'],['ninos','Cuidar niños'],['mayores','Cuidar a una persona mayor'],['dependiente','Cuidar a una persona enferma o dependiente'],['compras','Compras y recados'],['mascotas','Mascotas'],['otras','Otras']]},
 {id:'rel_dia',s:2,ty:'area',req:1,c:'Un día normal',t:'Describa lo que hacía en un día normal, de la mañana a la noche',h:'Ejemplo: «Llegaba a las 9, abría el bar, preparaba desayunos, a las 14 servía comidas, limpiaba la cocina y cerraba a las 23».'},
 {id:'rel_ordenes',s:2,f:'B',ty:'txt',c:'Cómo le daban órdenes',t:'¿Cómo le daban las órdenes?',h:'En persona, por WhatsApp, con una lista en la pared…'},
 {id:'rel_ultimo',s:2,ty:'date',req:1,ns:1,c:'Último día de trabajo',t:'¿Cuál fue su último día de trabajo?',h:'Si sigue trabajando, márquelo en la explicación.'},

 /* 3 · Jornada y salario */
 {id:'jor_horas',s:3,ty:'num',req:1,ns:1,c:'Horas reales por semana',t:'¿Cuántas horas trabajaba realmente a la semana?',h:'Sume solo el tiempo trabajando: la pausa de la comida no cuenta. Ejemplo: de 9 a 14 y de 17 a 21, de lunes a sábado, son 54 horas. Luego puede apuntar los horarios en la tabla de abajo.'},
 {id:'jor_tipo',s:3,ty:'op',c:'Tipo de horario',t:'¿Su horario era siempre igual?',o:[['fijo','Siempre igual'],['variable','Cambiaba cada semana'],['turnos','Por turnos']]},
 {id:'jor_noche',s:3,ty:'op',c:'Trabajo nocturno',t:'¿Trabajaba de noche o pasada la medianoche?',o:SI},
 {id:'jor_festivos',s:3,ty:'op',c:'Domingos y festivos',t:'¿Trabajaba domingos o festivos?',o:[['si','Sí'],['aveces','A veces'],['no','No']]},
 {id:'jor_fichaje',s:3,f:'AB',ty:'op',ns:1,c:'Fichaje',t:'¿Fichaba o firmaba al entrar y salir?',h:'La empresa está obligada a llevar ese registro desde 2019. Si no lo hacía, es un punto a favor del trabajador.',o:SI},
 {id:'hog_presencia',s:3,f:'C',ty:'op',c:'Tiempo de presencia',t:'¿Tenía que estar disponible en la casa aunque no estuviera trabajando?',h:'Por ejemplo, de noche por si la abuela necesitaba algo. Ese tiempo se llama «tiempo de presencia» y se apunta aparte en la tabla.',o:SI},
 {id:'sal_real',s:3,ty:'num',req:1,ns:1,c:'Lo que cobraba al mes (€)',t:'¿Cuánto cobraba de verdad al mes, en euros?',h:'Lo que le daban en la mano o en la cuenta, no lo que dice el papel.'},
 {id:'sal_pactado',s:3,f:'BC',ty:'num',ns:1,c:'Lo que le prometieron (€)',t:'¿Cuánto le prometieron al empezar?'},
 {id:'sal_cobro',s:3,ty:'multi',ns:1,c:'Forma de pago',t:'¿Cómo le pagaban?',o:[['efectivo','En efectivo'],['transferencia','Transferencia'],['bizum','Bizum (pago por el móvil, como Nequi)'],['otra','Otra']]},
 {id:'sal_frec',s:3,ty:'op',c:'Frecuencia de pago',t:'¿Cada cuánto le pagaban?',o:[['mes','Cada mes'],['quincena','Cada quincena'],['semana','Cada semana'],['dia','Cada día']]},
 {id:'sal_pagas',s:3,ty:'op',ns:1,c:'Pagas extra',t:'¿Le pagaban pagas extra en verano y Navidad?',o:[['aparte','Sí, aparte'],['incluidas','Sí, repartidas en cada mes'],['no','No']]},
 {id:'sal_vac',s:3,ty:'op',ns:1,c:'Vacaciones pagadas',t:'¿Tuvo vacaciones pagadas?',o:[['si','Sí, todas'],['parte','Solo algunas'],['no','No']]},
 {id:'deb',s:3,ty:'op',req:1,ns:1,c:'Le deben dinero',t:'¿Le deben dinero?',o:SI},
 {id:'deb_conc',s:3,ty:'multi',c:'Qué le deben',t:'¿Qué le deben?',o:[['salarios','Sueldos de algún mes'],['pagas','Pagas extra'],['vacaciones','Vacaciones'],['horas','Horas de más'],['otro','Otra cosa']],show:st=>V(st,'deb')==='si'},
 {id:'deb_desde',s:3,ty:'date',ns:1,c:'Deuda desde',t:'¿Desde cuándo le deben?',h:'El mes más antiguo. Lo que tenga más de un año se puede perder.',show:st=>V(st,'deb')==='si'},
 {id:'deb_importe',s:3,ty:'num',ns:1,c:'Sueldos impagados declarados (€)',t:'¿Cuánto le deben de sueldos sin pagar? (si lo sabe)',h:'Solo sueldos de meses no pagados. Pagas, vacaciones y horas las calcula la ficha.',show:st=>V(st,'deb')==='si'&&inc(st,'deb_conc','salarios')},

 /* 4 · Qué ocurrió */
 {id:'ext_tipo',s:4,ty:'op',req:1,c:'Qué pasó',t:'¿Qué pasó con el trabajo?',o:st=>[['despido','Le despidieron'],['no_llaman','Dejaron de llamarle o no le dejaron entrar']].concat(st.tipo==='C'?[]:[['fin_contrato','Le dijeron que se acababa el contrato']]).concat([['baja_forzada','Le hicieron firmar que se iba'],['voluntaria','Se fue por decisión propia'],['sigue','Sigue trabajando, pero le deben dinero'],['otro','Otra cosa']])},
 {id:'ext_quien',s:4,ty:'txt',ns:1,c:'Quién se lo dijo',t:'¿Quién se lo dijo?',h:'Nombre y qué papel tenía. Márquelo también como «Le despidió» en la lista de personas.',show:despLike},
 {id:'ext_forma',s:4,ty:'op',req:1,ns:1,c:'Forma de comunicación',t:'¿Se lo dijeron por escrito, por mensaje o de palabra?',o:[['escrito','Por escrito (carta o burofax)'],['mensaje','Por mensaje (WhatsApp, SMS, correo)'],['palabra','De palabra'],['nada','No le dijeron nada']],show:despLike},
 {id:'ext_carta',s:4,ty:'op',c:'Tiene la carta',t:'¿Tiene esa carta?',o:SI,show:st=>V(st,'ext_forma')==='escrito'},
 {id:'ext_dicho',s:4,ty:'txt',ns:1,req:1,c:'Lo que le dijeron',t:'¿Qué le dijeron cuando le despidieron?',h:'Lo que recuerde. Ejemplo: «que ya no había trabajo», «que no volviera».',show:st=>despLike(st)&&V(st,'ext_forma')!=='nada'},
 {id:'ext_literal',s:4,ty:'op',c:'Recuerda las palabras exactas',t:'¿Recuerda las palabras exactas que utilizaron?',o:SI,show:st=>despLike(st)&&V(st,'ext_forma')!=='nada'},
 {id:'ext_literal_txt',s:4,ty:'txt',c:'Palabras exactas',t:'Escriba esas palabras tal cual',h:'Sin corregirlas. Irán entre comillas en la papeleta.',show:st=>V(st,'ext_literal')==='si'},
 {id:'fecha_com',s:4,ty:'date',req:1,ns:1,aprox:1,c:'Fecha en que se lo dijeron',t:'¿Qué día se lo dijeron?',h:'Es el dato más urgente: para reclamar un despido hay solo 20 días hábiles. Si no recuerda el día exacto, busque el último mensaje con el jefe y marque «fecha aproximada».',show:despLike},
 {id:'fecha_efectos',s:4,ty:'date',ns:1,c:'Desde qué día no trabaja',t:'¿Desde qué día ya no le dejaron trabajar?',h:'Si fue el mismo día que se lo dijeron, ponga esa misma fecha.',show:despLike},
 {id:'ext_dia',s:4,ty:'area',req:1,c:'Lo que pasó el día del despido',t:'Describa lo que pasó el día del despido',h:'Con todo el detalle posible: a qué hora llegó, con quién habló, qué le dijeron exactamente, quién estaba delante, qué hizo después (si recogió sus cosas, si le pidieron las llaves, si le pagaron algo). Escríbalo en tercera persona: «Llegó a las 9 y la señora le dijo…».',show:st=>V(st,'ext_tipo')!=='sigue'},
 {id:'ext_hablo',s:4,ty:'txt',c:'Con quién más habló',t:'¿Con quién más habló ese día o en los días siguientes?',h:'Por ejemplo: llamó al dueño para preguntar, escribió a la encargada, habló con un compañero.',show:despLike},
 {id:'ext_testigos',s:4,ty:'op',c:'Testigos del despido',t:'¿Alguien vio u oyó cómo le despidieron?',o:SI,show:despLike},
 {id:'ext_testigos_txt',s:4,ty:'txt',c:'Quiénes lo vieron',t:'¿Quiénes? Nombres y teléfonos',show:st=>V(st,'ext_testigos')==='si'},
 {id:'ext_sit',s:4,ty:'multi',req:1,ns:1,c:'Situación especial',t:'Cuando le despidieron, ¿estaba en alguna de estas situaciones?',h:'Pregunte con tacto. Cualquiera de ellas puede hacer que el despido sea NULO, y entonces deben readmitirle.',o:[['embarazo','Embarazo o recién nacido'],['baja','Baja médica o enfermedad'],['hijos','Horario reducido o permiso por hijos'],['reclamo','Había reclamado algo o denunciado'],['acoso','Sufría acoso o malos tratos'],['vg','Víctima de violencia de género'],['ninguna','Ninguna']],show:despLike},
 {id:'ext_firmo',s:4,ty:'op',req:1,ns:1,c:'Firmó un papel al irse',t:'¿Firmó algún papel al irse?',h:'Finiquito, baja voluntaria, «recibí»… Un papel firmado puede perjudicar mucho: no le diga que no tiene importancia.',o:SI,show:st=>despLike(st)},
 {id:'ext_firmo_nc',s:4,ty:'op',ns:1,c:'Escribió «no conforme»',t:'¿Escribió «no conforme» al lado de su firma?',o:SI,show:st=>V(st,'ext_firmo')==='si'},
 {id:'ext_firmo_presion',s:4,ty:'op',c:'Le obligaron a firmar',t:'¿Le obligaron o no entendía lo que firmaba?',o:SI,show:st=>V(st,'ext_firmo')==='si'},
 {id:'pap',s:4,ty:'op',req:1,ns:1,c:'Papeleta ya presentada',t:'¿Ha presentado ya la papeleta de conciliación para reclamar sus derechos?',h:'Es el papel que se presenta antes de ir al juzgado. A veces lo presenta un sindicato o un conocido.',o:SI,show:st=>despLike(st)||V(st,'deb')==='si'},
 {id:'pap_fecha',s:4,ty:'date',ns:1,c:'Fecha de la papeleta',t:'¿Qué día la presentó? (la fecha del sello)',show:st=>V(st,'pap')==='si'},
 {id:'acto',s:4,ty:'op',ns:1,c:'Acto de conciliación celebrado',t:'¿Ya se celebró la reunión de conciliación?',o:SI,show:st=>V(st,'pap')==='si'},
 {id:'acto_fecha',s:4,ty:'date',c:'Fecha del acto',t:'¿Qué día fue la reunión?',show:st=>V(st,'acto')==='si'},
 {id:'acto_res',s:4,ty:'op',c:'Resultado del acto',t:'¿Cómo terminó?',o:[['sin','Sin acuerdo'],['con','Con acuerdo'],['nofue','La empresa no fue']],show:st=>V(st,'acto')==='si'},
 {id:'abog',s:4,ty:'op',req:1,ns:1,c:'Otro abogado',t:'¿Otro abogado está llevando actualmente este caso?',o:SI},
 {id:'abog_que',s:4,ty:'area',c:'Qué ha hecho el otro abogado',t:'¿Qué ha hecho ese abogado y cuándo?',show:st=>V(st,'abog')==='si'},
 {id:'abog_just',s:4,ty:'op',c:'Justificantes del otro abogado',t:'¿Tiene los papeles que lo demuestren?',o:SI,show:st=>V(st,'abog')==='si'},
 {id:'dem',s:4,ty:'op',ns:1,c:'Demanda presentada',t:'¿Ya se presentó la demanda en el juzgado?',o:SI,show:st=>V(st,'pap')==='si'||V(st,'abog')==='si'},
 {id:'dem_fecha',s:4,ty:'date',c:'Fecha de la demanda',t:'¿Qué día se presentó la demanda?',show:st=>V(st,'dem')==='si'},

 /* 5 · Pruebas (preguntas concretas que alimentan la lista) */
 {id:'pru_msgs',s:5,ty:'op',req:1,c:'Mensajes con el jefe',t:'¿Tiene mensajes de WhatsApp, SMS o correos electrónicos con el jefe o con quien le mandaba?',h:'Pida que no los borre y que exporte la conversación entera.',o:SI},
 {id:'pru_email',s:5,ty:'op',c:'Correos con el empleador',t:'¿Se escribían también por correo electrónico?',h:'Pida que reenvíe esos correos o haga capturas donde se vea la fecha y la dirección.',o:SI},
 {id:'pru_fotos',s:5,ty:'op',req:1,c:'Fotos o vídeos',t:'¿Tiene fotos o vídeos trabajando allí?',o:SI},
 {id:'pru_menores',s:5,ty:'op',c:'Niños en fotos o vídeos',t:'¿Aparecen niños en esas fotos o vídeos?',h:'Si aparecen, interviene el Ministerio Fiscal. Los niños nunca se citan como testigos.',o:SI,show:st=>V(st,'pru_fotos')==='si'},
 {id:'pru_testigos',s:5,ty:'op',req:1,c:'Testigos de la relación',t:'¿Hay compañeros, vecinos u otras personas que sepan que trabajaba allí?',o:SI},
 {id:'pru_testigos_txt',s:5,ty:'area',c:'Testigos (quiénes y qué saben)',t:'¿Quiénes son y qué pueden contar?',h:'Nombre, teléfono, qué vieron y si siguen trabajando allí. En el prototipo, datos inventados.',show:st=>V(st,'pru_testigos')==='si'}
];
SF.QM={};SF.Q.forEach(q=>SF.QM[q.id]=q);
SF.vis=(st,q)=>(!q.f||q.f.includes(st.tipo))&&(q.show?!!q.show(st):true);
SF.opts=(st,q)=>typeof q.o==='function'?q.o(st):q.o;
SF.show=(st,q)=>{const a=st.ans[q.id];if(!a)return '—';if(a.ns)return 'No lo sabe';const v=a.v;if(v===''||v==null)return '—';if(Array.isArray(v)){const o=SF.opts(st,q);return v.map(x=>{const f=o.find(p=>p[0]===x);return f?f[1]:x;}).join(', ');}if(q.ty==='op'){const f=SF.opts(st,q).find(p=>p[0]===v);return f?f[1]:v;}if(q.ty==='dir')return typeof v==='object'?SF.fmtDir(v,null,true):'—';if(q.ty==='date')return SF.fmt(v)+(a.aprox?' (aprox.)':'');if(q.ty==='num')return String(v).replace('.',',')+(/€/.test(q.c)?' €':'');return v;};

SF.CUID=[['aseo','Aseo e higiene'],['vestir','Vestir'],['comida','Darle de comer'],['medicacion','Medicación'],['movilidad','Levantar, acostar o mover'],['colegio','Llevar y recoger del colegio'],['medico','Acompañar al médico'],['noche','Atención por la noche'],['deberes','Deberes y juegos'],['paseo','Paseos y compañía']];
SF.AUT={independiente:'persona autónoma',leve:'con dependencia leve, que necesitaba ayuda en algunas actividades diarias',moderada:'con dependencia moderada, que necesitaba ayuda varias veces al día',severa:'con dependencia severa, que necesitaba ayuda para casi todo',total:'totalmente dependiente, sin capacidad para valerse por sí misma',ayuda:'que necesitaba ayuda en su vida diaria',dependiente:'persona totalmente dependiente'};
SF.DIAG=[['alzheimer','Alzheimer o demencia'],['parkinson','Parkinson'],['ictus','Secuelas de un ictus'],['movilidad','Movilidad reducida'],['silla','Silla de ruedas'],['encamada','Encamada'],['incontinencia','Incontinencia (pañal)'],['diabetes','Diabetes'],['corazon','Enfermedad del corazón'],['respiratoria','Oxígeno o enfermedad respiratoria'],['discapacidad','Discapacidad física o intelectual'],['mental','Enfermedad mental'],['sentidos','Problemas de vista u oído']];
SF.DIAGP={alzheimer:'Alzheimer u otra demencia',parkinson:'Parkinson',ictus:'secuelas de un ictus',movilidad:'movilidad reducida',silla:'necesidad de silla de ruedas',encamada:'encamamiento',incontinencia:'incontinencia',diabetes:'diabetes',corazon:'una enfermedad cardiaca',respiratoria:'una enfermedad respiratoria',discapacidad:'una discapacidad',mental:'una enfermedad mental',sentidos:'problemas de vista u oído'};
SF.CUIDP={aseo:'su aseo e higiene personal',vestir:'vestirle',comida:'su alimentación',medicacion:'su medicación',movilidad:'levantarle, acostarle y movilizarle',colegio:'llevarle y recogerle del colegio',medico:'acompañarle al médico',noche:'atenderle por la noche',deberes:'ayudarle con los deberes y jugar con él',paseo:'sus paseos y compañía'};
SF.GRADO={no:'sin grado de dependencia reconocido',tramite:'con la valoración de dependencia en trámite',I:'con grado I de dependencia reconocido',II:'con grado II de dependencia reconocido',III:'con grado III de dependencia reconocido'};
SF.NOCHE={alguna:'Alguna noche requería su atención',varias:'Se despertaba varias veces cada noche y requería su atención',toda:'Necesitaba atención durante toda la noche'};
SF.FREC={diaria:'a diario',varias:'varias veces por semana',semanal:'una vez por semana',quincenal:'cada quince días',mensual:'una vez al mes',ocasional:'de forma ocasional'};
SF.esMenor=c=>{const conE=c.edad!==''&&c.edad!=null;return conE?Number(c.edad)<18:/hij|niet|niñ|beb/i.test(c.parentesco||'');};
const NUMW=['','una','dos','tres','cuatro','cinco','seis','siete','ocho','nueve','diez'];
const listY=a=>a.length>1?a.slice(0,-1).join(', ')+' y '+a[a.length-1]:(a[0]||'');
SF.OBS_TPL='Comida y alojamiento (si se los daban y si le descontaban dinero por ello): \nSalud del trabajador/a: \nSituación familiar: \nLo que contó el cliente y no encaja en otra pregunta: \nOtros: ';
SF.ROLES=[['contrato','Le contrató'],['ordenes','Le daba órdenes'],['horario','Decidía su horario'],['pago','Le pagaba'],['despidio','Le despidió'],['dueno','Dueño/a o administrador/a']];
SF.ROLE_Q=[['contrato','¿Quién le contrató?'],['ordenes','¿Quién le daba las órdenes?'],['horario','¿Quién decidía su horario?'],['pago','¿Quién le pagaba?']];

/* ================= estado ================= */
SF.genId=()=>{const d=new Date();return 'F-'+d.getFullYear()+String(d.getMonth()+1).padStart(2,'0')+String(d.getDate()).padStart(2,'0')+'-'+Math.random().toString(36).slice(2,6).toUpperCase();};
const patVacio=()=>{const p={};for(let i=1;i<=7;i++)p[i]={e:'',s:'',d:'',p:'',tk:[]};return p;};
SF.newFicha=tipo=>({id:SF.genId(),tipo,creada:new Date().toISOString(),ans:{},personas:[],rolesNS:{},cuidados:[],entorno:[],obs:'',jor:{ref:40,patron:patVacio(),dias:[],desde:'',hasta:'',tareas:[]},pruebas:{},dudas:[],
 abg:{organo:'',localidad:'',letrado:'',domNotif:'',calif:'auto',convenio:'',convenioFuente:'',categoriaD:'',grupoCot:'',regOverride:'',precioHora:'',diasAnio:'',topeMens:'',incluirAdminsA:false,admins:true,advCostas:true,advITSS:true,advAlta:true,advRegistro:true,advExtr:false,advPruebas:true,incObs:false,estimaciones:true,obs:''},
 seq:0,log:[]});
SF.setAns=(st,id,v,ns,extra)=>{const prev=st.ans[id];const a=prev||{v:'',ns:false,nota:'',estado:'declarado'};a.v=v;a.ns=!!ns;if(extra&&'aprox' in extra)a.aprox=extra.aprox;if(a.estado==='comprobado')a.estado='declarado';st.ans[id]=a;st.log.push({ts:new Date().toISOString(),id,v:ns?'No lo sabe':v});};
SF.setNota=(st,id,t)=>{const a=st.ans[id]||{v:'',ns:false,nota:'',estado:'declarado'};a.nota=t;st.ans[id]=a;};
SF.persWith=(st,r)=>st.personas.filter(p=>p.roles.includes(r)&&p.nombre.trim());

/* ================= jornada ================= */
const tmin=s=>{if(!s||!/^\d{1,2}:\d{2}$/.test(s))return null;const[h,m]=s.split(':').map(Number);return h*60+m;};
SF.rowCalc=(r)=>{const e=tmin(r.e),s=tmin(r.s);if(e==null||s==null)return null;let end=s<=e?s+1440:s;const d=Math.max(0,Number(r.d)||0);const work=Math.max(0,end-e-d);
 let noct=0;[[0,360],[1320,1800],[2760,2880]].forEach(([a,b])=>{noct+=Math.max(0,Math.min(end,b)-Math.max(e,a));});
 return {ef:work/60,noct:Math.min(noct,work)/60,pres:Math.max(0,Number(r.p)||0),cruza:end>1440};};
const dow=f=>{const w=new Date(SF.pd(f)).getUTCDay();return w===0?7:w;};
const DOWN=['','lunes','martes','miércoles','jueves','viernes','sábado','domingo'];
SF.DOWN=DOWN;
const weekKey=f=>SF.iso(SF.pd(f)-(dow(f)-1)*DAY);
SF.jorStats=(st)=>{const ref=Number(st.jor.ref)||40;const W={};let largos=0,noct=0,nDias=0;
 st.jor.dias.forEach(r=>{const c=SF.rowCalc(r);if(!c||!r.f)return;nDias++;const k=weekKey(r.f);W[k]=W[k]||{k,ef:0,pres:0,n:0};W[k].ef+=c.ef;W[k].pres+=c.pres;W[k].n++;if(c.ef>9)largos++;noct+=c.noct;});
 const weeks=Object.values(W).sort((a,b)=>SF.pd(a.k)-SF.pd(b.k));weeks.forEach(w=>{w.exceso=Math.max(0,w.ef-ref);});
 const full=weeks.filter(w=>w.n>=5);const base=full.length?full:weeks;
 const avg=base.length?base.reduce((s,w)=>s+w.ef,0)/base.length:null;
 const avgPres=base.length?base.reduce((s,w)=>s+w.pres,0)/base.length:null;
 return {ref,weeks,avg,avgPres,avgExceso:avg!=null?Math.max(0,avg-ref):null,largos,noct,nDias};};
SF.fillPattern=(st,desde,hasta)=>{if(!SF.pd(desde)||!SF.pd(hasta)||SF.pd(hasta)<SF.pd(desde))return {ok:false,error:'Indique un periodo válido (desde y hasta).'};
 if(SF.days(desde,hasta)>400)return {ok:false,error:'Como máximo 400 días de una vez.'};
 const have=new Set(st.jor.dias.map(r=>r.f));let n=0;
 for(let t=SF.pd(desde);t<=SF.pd(hasta);t+=DAY){const f=SF.iso(t);if(have.has(f))continue;const p=st.jor.patron[dow(f)];if(!p||!p.e||!p.s)continue;st.seq++;st.jor.dias.push({id:'J'+st.seq,f,e:p.e,s:p.s,d:p.d,p:p.p,tk:(p.tk||[]).slice(),obs:'',fuente:'habitual'});n++;}
 st.jor.dias.sort((a,b)=>SF.pd(a.f)-SF.pd(b.f));return {ok:true,n};};

/* ================= cálculos económicos ================= */
SF.calc=(st,hoy)=>{hoy=hoy||SF.today();const v=id=>V(st,id),A=st.abg;const K={};
 K.inicio=v('rel_inicio');K.fin=v('fecha_efectos')||v('rel_ultimo')||v('fecha_com')||null;
 const J=SF.jorStats(st);K.J=J;
 K.horas=J.avg!=null&&J.weeks.some(w=>w.n>=5)?J.avg:(Number(v('jor_horas'))||null);
 K.horasFuente=J.avg!=null&&J.weeks.some(w=>w.n>=5)?'registro':'declaradas';
 const sal=Number(v('sal_real'))||0;K.sal=sal;
 const yr=K.fin?new Date(SF.pd(K.fin)).getUTCFullYear():new Date(SF.pd(hoy)).getUTCFullYear();
 K.jf=K.horas?Math.min(1,K.horas/40):1;
 K.smiMes=SF.smiMes(yr)*K.jf;
 const pf=v('sal_pagas')==='incluidas'?1:14/12;K.pagasFactor=pf;
 K.base=sal?sal*pf:0;
 K.regCalc=sal?Math.max(K.base,K.smiMes):null;K.regPorSMI=sal&&K.smiMes>K.base;
 K.reg=Number(A.regOverride)||K.regCalc;K.diario=K.reg?K.reg*12/365:null;
 /* antigüedad e indemnización */
 if(K.inicio&&K.fin&&SF.pd(K.fin)>=SF.pd(K.inicio)){
  const finEx=SF.addDays(K.fin,1),corte='2012-02-12';
  const pre=SF.pd(K.inicio)<SF.pd(corte)?SF.monthsCeil(K.inicio,SF.pd(finEx)<SF.pd(corte)?finEx:corte):0;
  const post=SF.pd(finEx)>SF.pd(corte)?SF.monthsCeil(SF.pd(K.inicio)>SF.pd(corte)?K.inicio:corte,finEx):0;
  K.mesesPre=pre;K.mesesPost=post;K.antigDias=SF.days(K.inicio,K.fin)+1;
  if(st.tipo==='C'){const da=Number(A.diasAnio),tm=Number(A.topeMens);if(da&&tm){K.indDias=Math.min((pre+post)/12*da,tm*365/12);K.indRegla=`${da} días por año con tope de ${tm} mensualidades (fijado por el abogado)`;}else{K.indDias=null;K.indRegla=null;}}
  else{const dPre=pre/12*45,dPost=post/12*33;K.dPre=dPre;K.dPost=dPost;K.indDias=dPre>720?Math.min(dPre,42*365/12):Math.min(dPre+dPost,720);K.indRegla=pre?'45 días por año hasta el 11/02/2012 y 33 días por año desde el 12/02/2012 (DT 11.ª ET)':'33 días de salario por año de servicio, prorrateando por meses, con un máximo de 24 mensualidades (art. 56.1 ET)';}
  K.ind=K.indDias!=null&&K.diario?K.indDias*K.diario:null;
 }
 /* periodo reclamable de cantidades: último año antes del fin (prescripción, art. 59.2 ET) */
 const finC=K.fin||hoy;const desdeC=K.inicio&&SF.pd(K.inicio)>SF.pd(finC)-365*DAY?K.inicio:SF.addDays(finC,-365);
 K.mesesC=K.inicio?SF.monthsCeil(desdeC,SF.addDays(finC,1)):null;if(K.mesesC>12)K.mesesC=12;
 K.items=[];
 const add=(c,imp,det,est)=>K.items.push({c,imp,det,est});
 if(v('deb')==='si'&&inc(st,'deb_conc','salarios'))add('Salarios no abonados',Number(v('deb_importe'))||null,'Cantidad declarada por '+(v('cli_trato')==='da'?'la trabajadora':'el trabajador'),false);
 if(A.estimaciones&&K.mesesC){
  if(v('sal_pagas')==='no'&&sal){const mb=Math.max(sal,SF.smiMes(yr)*12/14*K.jf);add('Pagas extraordinarias no abonadas',2*mb*K.mesesC/12,`2 pagas al año de ${eur(mb)} (art. 31 ET), parte proporcional de ${K.mesesC} meses`,true);}
  if(v('sal_vac')==='no'&&K.diario)add('Vacaciones no disfrutadas ni compensadas',30*K.diario*K.mesesC/12,`30 días naturales por año (art. 38 ET), parte proporcional de ${K.mesesC} meses`,true);
  if(sal&&K.smiMes>K.base&&K.horas){const s14=SF.SMI[Math.min(Math.max(yr,2015),2026)]*K.jf;const pg=v('sal_pagas');const dif=pg==='incluidas'?s14*14/12-sal:pg==='aparte'?(s14-sal)*14/12:s14-sal;if(dif>0)add('Diferencias hasta el salario mínimo interprofesional',dif*K.mesesC,`${eur(dif)} al mes durante ${K.mesesC} meses (SMI ${yr}: ${eur(SF.SMI[Math.min(Math.max(yr,2015),2026)]).replace(',00','')}/mes en 14 pagas, proporcional a ${num1(K.horas)} h semanales${pg==='no'?'; las pagas extraordinarias se reclaman aparte':''})`,true);}
 }
 K.horasExceso=null;
 const refH=st.tipo==='C'?40:(Number(st.jor.ref)||40);
 if(K.horas&&K.horas>refH&&K.mesesC){const sem=Math.min(52,K.mesesC*52/12);K.horasExceso=(K.horas-refH)*sem;const ph=Number(A.precioHora);add('Horas de trabajo por encima de la jornada máxima',ph?K.horasExceso*ph:null,`${num1(K.horas-refH)} h por semana × ${num1(sem)} semanas = ${num1(K.horasExceso)} horas${ph?' a '+eur(ph)+' la hora':' (precio por hora a fijar por el abogado)'}`,K.horasFuente!=='registro');}
 if(v('deb')==='si'){const have=c=>K.items.some(i=>i.c.toLowerCase().includes(c));const M=[['pagas','pagas extraordinarias','Pagas extraordinarias pendientes'],['vacaciones','vacaciones','Vacaciones pendientes de disfrute o compensación'],['horas','horas','Horas de trabajo por encima de la jornada'],['otro','otros conceptos','Otros conceptos declarados']];M.forEach(([k,c,l])=>{if(inc(st,'deb_conc',k)&&!have(c))add(l,null,'Concepto declarado; importe a fijar por el abogado',false);});}
 K.totalCant=K.items.reduce((s,i)=>s+(i.imp||0),0);
 K.calif=A.calif!=='auto'?A.calif:((v('ext_sit')||[]).some(x=>x!=='ninguna')?'nulo':'improcedente');
 K.califAuto=A.calif==='auto';
 return K;};

/* ================= alertas, contradicciones, pendientes ================= */
SF.evaluate=(st,hoy)=>{hoy=hoy||SF.today();const v=id=>V(st,id),ns=id=>NS(st,id);
 const R={alerts:[],contra:[],incompletos:[],desconocidos:[],pruebas:[],dudas:[]};
 const A=(n,cod,t,d)=>R.alerts.push({nivel:n,cod,titulo:t,detalle:d});
 const dl=despLike(st);
 if(v('dem')==='si')A('alta','demanda','Ya hay una demanda presentada',`Según el cliente, la demanda se presentó${v('dem_fecha')?' el '+SF.fmt(v('dem_fecha')):''}. No se presenta otra papeleta sin que el abogado revise lo actuado.`);
 if(v('abog')==='si')A('alta','otro_abogado','Otro abogado lleva el caso',`Pedir los justificantes de lo hecho (${v('abog_just')==='si'?'dice tenerlos':'no consta que los tenga'}) y confirmar si hay papeleta o demanda antes de seguir.`);
 if(dl&&v('dem')!=='si'){
  const base=SF.minDate([v('fecha_com'),v('fecha_efectos'),v('rel_ultimo')]);
  const aprox=!!((st.ans.fecha_com||{}).aprox);
  if(!base)A('critica','sin_fecha','Posible despido sin fecha conocida','No consta cuándo se lo dijeron ni el último día trabajado. El plazo para reclamar un despido es de 20 días hábiles: revisión del abogado hoy.');
  else if(SF.pd(base)<=SF.pd(hoy)){
   const falta=[];if(!v('fecha_com'))falta.push('día en que se lo comunicaron');if(!v('fecha_efectos'))falta.push('fecha de efectos');falta.push('festivos nacionales, autonómicos y locales');
   const cola=` Se toma la fecha más antigua declarada (${SF.fmt(base)})${aprox?', que es aproximada':''}. Es una estimación prudente que cuenta de lunes a viernes sin descontar festivos, no una fecha de caducidad. Para fijarla, el abogado necesita: ${falta.join(', ')}.`;
   const pap=v('pap')==='si'?v('pap_fecha'):null;
   if(v('pap')==='si'&&!pap)A('alta','pap_sin_fecha','Papeleta presentada sin fecha conocida','La papeleta suspende el plazo desde su presentación. Sin la fecha del sello no se puede estimar cuánto queda.'+cola);
   else if(pap&&SF.pd(pap)>=SF.pd(base)){
    const u1=SF.wd(base,pap);
    if(u1>=20)A('critica','cad_pre_pap','Posible caducidad antes de la papeleta',`Entre ${SF.fmt(base)} y la papeleta (${SF.fmt(pap)}) pasaron ${u1} días laborables. Revisión del abogado inmediata.`+cola);
    else{const lim=SF.addDays(pap,15);const res=v('acto')==='si'&&v('acto_fecha')?SF.minDate([v('acto_fecha'),lim]):lim;
     if(SF.pd(res)>SF.pd(hoy))A('alta','pap_susp',`Plazo suspendido por la papeleta: quedarían ${20-u1} días hábiles o algo más al reanudarse`,`Hasta la papeleta pasaron ${u1} días laborables. El cómputo se reanuda tras el intento de conciliación o, si no se celebra, a los 15 días de presentarla (art. 65.1 LRJS).`+cola);
     else{const u=u1+SF.wd(res,hoy),q=20-u;
      if(q<=0)A('critica','cad_posible','Posible caducidad de la acción de despido',`Antes de la papeleta: ${u1} días; desde que se reanudó el plazo (${SF.fmt(res)}): ${SF.wd(res,hoy)}. Total aproximado ${u} días laborables.`+cola);
      else A(q<=6?'critica':q<=12?'alta':'media','plazo_reanudado',`Plazo reanudado tras la papeleta: quedarían ${q} días hábiles o algo más`,`Antes de la papeleta: ${u1} días; desde ${SF.fmt(res)}: ${SF.wd(res,hoy)}.`+cola);}}
   } else {const u=SF.wd(base,hoy),q=20-u;
    if(u>=20)A('critica','cad_posible','Posible caducidad de la acción de despido',`Han pasado ${u} días laborables. Puede no haber caducado si hubo festivos o una papeleta no declarada. Revisión inmediata.`+cola);
    else if(q<=6)A('critica','plazo_critico',`Plazo crítico: quedarían ${q} días hábiles o algo más`,'Presentar la papeleta en cuanto el abogado la revise.'+cola);
    else if(q<=12)A('alta','plazo_urgente',`Plazo urgente: quedarían ${q} días hábiles o algo más`,'Derivar hoy al abogado.'+cola);
    else A('media','plazo_curso',`Plazo de despido en curso: quedarían ${q} días hábiles o algo más`,cola.trim());}
   if(ns('pap'))A('alta','pap_ns','No se sabe si ya hay papeleta','Si la presentó un sindicato u otra persona, cambia el plazo. Confirmarlo hoy.');
  }
 }
 if(v('ext_tipo')==='baja_forzada')A('alta','baja_forzada','Le hicieron firmar la baja: posible despido encubierto','Si se trata como despido, corre el plazo de 20 días hábiles desde la fecha de la firma.');
 if(v('ext_tipo')==='voluntaria')A('media','voluntaria','Se fue por decisión propia','El despacho no tramita dimisiones. Si le deben dinero, se puede reclamar la cantidad.');
 const sit=(v('ext_sit')||[]).filter(x=>x!=='ninguna');
 if(dl&&sit.length)A('alta','nulidad','Posible despido nulo','El cliente declara una situación protegida. El abogado valora reclamar la nulidad (readmisión y salarios). Interviene el Ministerio Fiscal.');
 if(v('ext_firmo')==='si')A('alta','firmo','Firmó un papel al irse',`${v('ext_firmo_nc')==='si'?'Dice que escribió «no conforme».':'No consta que escribiera «no conforme».'} Conseguir copia antes de presentar la papeleta.`);
 if(v('cli_rep')==='si')A('alta','representante','Fue representante de los trabajadores','Tiene garantías especiales (art. 68 ET). La papeleta debe adaptarse.');
 if(v('cli_nac')&&v('rel_inicio')){const e=SF.ageAt(v('cli_nac'),v('rel_inicio'));if(e>=16&&e<18)A('alta','menor','Era menor de edad al empezar',`Tenía ${e} años. Interviene el Ministerio Fiscal.`);}
 if(v('pru_menores')==='si')A('media','menores_fotos','Aparecen niños en las pruebas','Interviene el Ministerio Fiscal. Los niños nunca se citan como testigos.');
 if(v('deb')==='si'){const d=v('deb_desde');if(d){const n=SF.days(d,hoy);if(n>365)A('alta','presc','Parte de la deuda puede haber prescrito',`Lo más antiguo es de ${SF.fmt(d)}: más de un año (art. 59.2 ET).`);else if(n>=300)A('alta','presc_prox','La deuda más antigua está cerca del año',`Desde ${SF.fmt(d)}. Reclamar cuanto antes.`);}else A('media','deuda_sin_fecha','Deuda sin fecha','Sin el mes más antiguo no se puede valorar la prescripción.');}
 if(st.tipo!=='A'&&['pru_msgs','pru_fotos','pru_testigos'].every(k=>v(k)==='no')&&!(v('sal_cobro')||[]).some(x=>x==='transferencia'||x==='bizum'))A('alta','sin_pruebas','No hay pruebas declaradas de la relación laboral','Sin contrato ni alta, y sin mensajes, fotos, testigos ni pagos rastreables. Buscar otros indicios antes de presentar la papeleta (ver lista de pruebas).');
 if(v('emp_estado')==='concurso')A('media','concurso','Empresa en concurso','La papeleta debe dirigirse también a la administración concursal.');
 const K=SF.calc(st,hoy);
 if(K.regPorSMI&&K.horas)A('media','smi','Cobraba por debajo del salario mínimo',`Con ${num1(K.horas)} h semanales le correspondían al menos ${eur(K.smiMes)} al mes (14 pagas prorrateadas). La papeleta reclama la diferencia.`);
 if(st.tipo==='C'&&K.J.avgPres!=null&&K.J.avgPres>20)A('media','presencia','Más de 20 horas semanales de presencia',`Media de ${num1(K.J.avgPres)} h. Revisar con el art. 9 del RD 1620/2011.`);
 /* contradicciones */
 const Cx=(id,t,d,q)=>R.contra.push({id,titulo:t,texto:d,qids:q});
 const ini=v('rel_inicio'),fc=v('fecha_com'),fe=v('fecha_efectos'),ul=v('rel_ultimo');
 if(st.tipo==='A'&&v('cli_permiso')==='no')Cx('ficha_permiso','La ficha no corresponde','Se abrió la ficha «con papeles», pero dice que no tenía permiso de trabajo. Cambie a la ficha B o C.',['cli_permiso']);
 if(st.tipo!=='A'&&v('cli_permiso')==='si')Cx('ficha_permiso','La ficha no corresponde','Se abrió una ficha «sin papeles», pero dice que tenía permiso de trabajo. Cambie a la ficha A.',['cli_permiso']);
 [[fc,'fecha_com'],[fe,'fecha_efectos'],[ul,'rel_ultimo']].forEach(([d,id])=>{if(ini&&d&&SF.pd(ini)>SF.pd(d))Cx('ini_'+id,'Empezó después del final',`Inicio ${SF.fmt(ini)} posterior a «${SF.QM[id].c.toLowerCase()}» (${SF.fmt(d)}).`,['rel_inicio',id]);});
 [[fc,'fecha_com'],[fe,'fecha_efectos'],[ul,'rel_ultimo'],[ini,'rel_inicio']].forEach(([d,id])=>{if(d&&SF.pd(d)>SF.pd(hoy))Cx('fut_'+id,'Fecha en el futuro',`«${SF.QM[id].c}»: ${SF.fmt(d)}.`,[id]);});
 if(ul&&fe&&SF.pd(ul)>SF.pd(fe))Cx('ult_ef','Trabajó después de la fecha de efectos',`Último día ${SF.fmt(ul)}, pero no le dejaron trabajar desde ${SF.fmt(fe)}.`,['rel_ultimo','fecha_efectos']);
 const pf=v('pap_fecha'),bs=SF.minDate([fc,fe]);
 if(pf&&bs&&SF.pd(pf)<SF.pd(bs))Cx('pap_previa','Papeleta anterior al despido',`La papeleta (${SF.fmt(pf)}) es anterior al despido (${SF.fmt(bs)}). Puede ser otra reclamación.`,['pap_fecha','fecha_com']);
 SF.Q.filter(q=>q.ty==='dir'&&SF.vis(st,q)).forEach(q=>{const d=V(st,q.id);if(!d)return;const p=SF.provDeCP(d.cp);if(p&&d.prov&&p!==d.prov)Cx('cp_'+q.id,'Código postal y provincia no cuadran',`«${q.c}»: el código postal ${d.cp} es de ${p}, pero se ha puesto ${d.prov}.`,[q.id]);});
 if(v('rel_alta')==='si'&&v('cli_permiso')==='no')Cx('alta_permiso','Alta sin permiso','Dice que estaba de alta pero sin permiso de trabajo. Comprobar con la vida laboral.',['rel_alta','cli_permiso']);
 if(v('cli_nac')&&ini&&SF.ageAt(v('cli_nac'),ini)<16)Cx('edad','Edad de inicio imposible','Según las fechas tenía menos de 16 años al empezar.',['cli_nac','rel_inicio']);
 if(v('deb_desde')&&ini&&SF.pd(v('deb_desde'))<SF.pd(ini))Cx('deuda_previa','Deuda anterior al inicio','La deuda empieza antes de la relación laboral.',['deb_desde','rel_inicio']);
 if(v('ext_tipo')==='fin_contrato'&&v('rel_contrato')==='no')Cx('fin_sin_contrato','Fin de contrato sin contrato','Dice que se acabó el contrato, pero que no tenía contrato escrito. Aclarar qué le dijeron.',['ext_tipo','rel_contrato']);
 const dh=Number(v('jor_horas'));if(dh&&K.J.weeks.some(w=>w.n>=5)&&K.J.avg&&Math.abs(K.J.avg-dh)/Math.max(K.J.avg,dh)>0.25)Cx('horas','Horas declaradas distintas del registro',`Dice ${num1(dh)} h a la semana; la tabla da una media de ${num1(K.J.avg)} h.`,['jor_horas']);
 /* incompletos */
 SF.Q.forEach(q=>{if(!SF.vis(st,q))return;if(NS(st,q.id)){R.desconocidos.push({id:q.id,label:q.c});return;}if(q.req&&V(st,q.id)===undefined)R.incompletos.push({id:q.id,label:q.c,s:q.s});else if(q.ty==='dir'&&V(st,q.id)){const f=SF.dirFalta(V(st,q.id));if(f.length)R.incompletos.push({id:q.id,label:`${q.c}: falta ${f.join(', ')}`,s:q.s});}});
 if(st.tipo==='C'&&['ninos','mayores','dependiente'].some(x=>inc(st,'hog_tareas',x))&&!(st.cuidados||[]).some(c=>c.nombre||c.edad))R.incompletos.push({id:'cuidados',label:'Personas que cuidaba',s:2});
 (st.cuidados||[]).forEach(c=>{if((c.nombre||c.edad)&&(c.edad===''||c.edad==null))R.incompletos.push({id:'cuidados',label:'Edad de '+(c.nombre||'una persona cuidada'),s:2});});
 if(!st.personas.some(p=>p.nombre.trim()))R.incompletos.push({id:'personas',label:st.tipo==='C'?'Personas de la casa':'Personas de la empresa',s:1});
 SF.ROLE_Q.forEach(([r,t])=>{if(!SF.persWith(st,r).length&&!st.rolesNS[r])R.incompletos.push({id:'rol_'+r,label:t.replace(/[¿?]/g,''),s:2});else if(st.rolesNS[r])R.desconocidos.push({id:'rol_'+r,label:t.replace(/[¿?]/g,'')});});
 R.pruebas=SF.pruebasReq(st,K);
 R.contra.forEach(c=>R.dudas.push('Contradicción: '+c.titulo+'. '+c.texto));
 ['fecha_com','rel_inicio','pap','ext_sit','ext_firmo','emp_dom','rel_alta','deb_desde'].forEach(id=>{if(NS(st,id)&&SF.vis(st,SF.QM[id]))R.dudas.push('El cliente no sabe: '+SF.QM[id].c.toLowerCase()+'. ¿Cómo lo conseguimos?');});
 R.K=K;return R;};

/* ================= pruebas dinámicas ================= */
SF.PR_EST=[['pendiente','Pendiente'],['tiene','Lo tiene'],['conseguira','Lo conseguirá'],['no_existe','No existe'],['no_aplica','No aplica']];
SF.pruebasReq=(st,K)=>{const v=id=>V(st,id),L=[];const P=(key,t,por)=>L.push({key,t,por});const T=st.tipo;
 P('identidad','Documento de identidad (foto por las dos caras)','Identificar al cliente en la papeleta');
 if(v('pru_email')==='si')P('correos','Correos electrónicos con '+(T==='C'?'la persona empleadora':'la empresa')+' (reenviados o en captura, con fecha y dirección)','Prueban órdenes, horarios, pagos o el despido');
 if(T==='A'){if(v('rel_contrato')==='si')P('contrato','Contrato de trabajo','Dice que tenía contrato');P('nominas',v('rel_nominas')==='no'?'Nóminas (pedirlas a la empresa: está obligada a darlas)':'Nóminas de los últimos 12 meses','Salario, puesto y grupo de cotización');P('vida','Informe de vida laboral','Comprobar alta, fechas y empresa');if(despLike(st))P('certificado','Certificado de empresa (si se lo dieron)','Fechas y causa que declara la empresa');}
 if(T==='B'){if(v('rel_contrato')==='si')P('contrato','Contrato de trabajo','Dice que tenía contrato');if(v('rel_alta')!=='no')P('vida','Informe de vida laboral','Comprobar si tuvo alta');
  P('chat','Conversaciones con el jefe o encargado, exportadas con fecha','Prueban quién mandaba, horarios y pagos');
  if((v('sal_cobro')||[]).some(x=>x==='transferencia'||x==='bizum'))P('pagos','Capturas de Bizum o extractos de transferencias','Prueban quién pagaba y cuánto');else P('efectivo','Cualquier rastro del pago en efectivo: sobres, notas, mensajes sobre el dinero','Prueba del salario cuando se cobraba en mano');
  P('fotos','Fotos o vídeos trabajando allí (uniforme, local, compañeros)','Prueban que trabajaba en ese sitio');P('turnos','Cuadrantes, listas de turnos o fotos del horario','Prueban horario y dependencia');
  P('testigos','Compañeros, clientes o vecinos que puedan confirmar que trabajaba allí','Prueba testifical de la relación');P('indicios','Otros indicios: llaves, tarjetas de la empresa, publicaciones del negocio en redes, reseñas que le mencionen','Refuerzan la existencia de la relación');}
 if(T==='C'){P('chat','Conversaciones con la persona empleadora, exportadas con fecha','Prueban órdenes, horarios y pagos');
  if((v('sal_cobro')||[]).some(x=>x==='transferencia'||x==='bizum'))P('pagos','Capturas de Bizum o extractos de transferencias','Prueban el salario');else P('efectivo','Cualquier rastro del pago en efectivo: notas, mensajes sobre el dinero','Prueba del salario cobrado en mano');
  P('tareas','Lista escrita de tareas y horarios, día por día','Base para jornada y tiempo de presencia');if((st.entorno||[]).some(x=>x.vio==='si'))P('visitas','Teléfonos de las visitas que la veían trabajar ('+(st.entorno||[]).filter(x=>x.vio==='si').map(x=>x.nombre).join(', ')+')','Testigos que conocen la casa por dentro');P('testigos','Vecinos, porteros, otras empleadas o familiares que la vieran trabajar','Prueba testifical de la relación');
  if(v('hog_interna')==='interna'||v('hog_aloj')==='si')P('residencia','Pruebas de que vivía en la casa: empadronamiento, cartas recibidas allí, mensajes','Acreditan el régimen de interna');
  P('fotos','Fotos o vídeos en la casa'+(inc(st,'hog_tareas','ninos')?' (si aparecen niños, avisar: interviene el Ministerio Fiscal)':''),'Prueban la prestación de servicios');}
 const f=v('ext_forma');
 if(despLike(st)){if(f==='escrito')P('carta','Carta de despido o burofax, todas las páginas','Fecha y causa que alega la empresa');if(f==='mensaje')P('msg_desp','Captura del mensaje del despido con la fecha y el número visibles','Prueba la fecha y la forma del despido');if(f==='palabra'||V(st,'ext_testigos')==='si')P('test_desp','Nombres y teléfonos de quienes lo vieron u oyeron','Prueba del despido verbal');if(f==='nada')P('msg_despues','Mensajes posteriores preguntando por el trabajo sin respuesta','Prueban que le dejaron de dar trabajo');}
 if(v('ext_firmo')==='si')P('firmado','Copia de lo que firmó al irse','Revisar si renunció a algo');
 if(v('pap')==='si')P('papeleta','Papeleta anterior con el sello de registro','Cambia el plazo');if(v('acto')==='si')P('acta','Acta de la conciliación','Resultado del acto');if(v('abog')==='si')P('otro_abog','Justificantes del otro abogado (papeleta, demanda, poder)','Evitar duplicar actuaciones');if(v('dem')==='si')P('demanda','Copia de la demanda presentada','Evitar duplicar actuaciones');
 if(v('deb')==='si')P('deuda','Mensajes reclamando el dinero o pruebas de lo no pagado','Prueba de la deuda');
 if((K.horas&&K.horas>40)||v('jor_noche')==='si'||inc(st,'deb_conc','horas'))P('horario','Cuadrantes, fichajes, mensajes de turnos o fotos de horarios','Prueban las horas de más y la nocturnidad');
 if(v('jor_fichaje')==='si')P('fichajes','Copia del registro de fichajes (o pedirla a la empresa)','La empresa está obligada a conservarlo 4 años');
 const s=V(st,'ext_sit')||[];if(s.includes('embarazo'))P('embarazo','Informe médico del embarazo y prueba de que la empresa lo sabía','Nulidad del despido');if(s.includes('baja'))P('baja','Partes de baja o informes médicos','Posible discriminación por enfermedad');if(s.includes('reclamo'))P('reclamo','Copia de la reclamación o denuncia anterior','Posible represalia');if(s.includes('acoso'))P('acoso','Mensajes, denuncias o testigos del acoso','Vulneración de derechos fundamentales');if(s.includes('vg'))P('vg','Orden de protección o informe que acredite la situación','Nulidad del despido');if(s.includes('hijos'))P('hijos','Solicitud o concesión de la reducción o del permiso','Nulidad del despido');
 return L;};

/* ================= papeleta ================= */
SF.tareasTxt=st=>{const T=(st.jor.tareas||[]).filter(x=>x.t&&x.t.trim());if(!T.length)return '';const fr=x=>x.desde&&x.hasta?` (de ${x.desde} a ${x.hasta})`:'';const n=st.jor.dias.filter(r=>SF.rowCalc(r)).length;const cnt=x=>st.jor.dias.filter(r=>(r.tk||[]).includes(x.id)).length;
 const norm=T.filter(x=>!x.extra),ext=T.filter(x=>x.extra);let r='';
 if(norm.length)r+=`Su jornada se distribuía así: ${norm.map(x=>lcf(x.t.trim())+fr(x)).join('; ')}.`;
 if(ext.length)r+=`${r?' ':''}Las horas que excedían su jornada las dedicaba, por indicación de la parte requerida, a: ${ext.map(x=>{const c=cnt(x);return lcf(x.t.trim())+fr(x)+(c&&n?`, en ${c} de los ${n} días registrados`:'');}).join('; ')}.`;
 return r;};
SF.cuidadosTxt=(st,P,tr,Tr)=>{const v=id=>V(st,id),out=[];
 /* convivientes */
 const res=SF.persWith(st,'vive');
 if(res.length)out.push(`En la vivienda residían ${(a=>a.length>1?a.slice(0,-1).join('; ')+'; y '+a[a.length-1]:a[0])(res.map(p=>`${p.nombre}${p.relacion?' ('+p.relacion+')':''}${p.edad?', de '+p.edad+' años':''}${p.trabajo?', '+lcf(p.trabajo.trim().replace(/\.$/,'')):''}`))}${(st.cuidados||[]).length?', además de las personas a las que cuidaba':''}.`);
 if(v('hog_mascotas'))out.push('En la casa había además '+lcf(v('hog_mascotas').trim().replace(/\.$/,''))+'.');
 /* personas cuidadas */
 const C=(st.cuidados||[]).filter(c=>c.nombre||(c.edad!==''&&c.edad!=null));
 if(C.length){out.push(`${Tr} tenía a su cargo el cuidado de ${C.length>1?NUMW[C.length]||C.length:'una'} persona${C.length>1?'s':''}.`);
  C.forEach(c=>{const conE=c.edad!==''&&c.edad!=null,e=Number(c.edad);const cu=(c.cu||[]).filter(k=>!(k==='medicacion'&&c.medicacion)).map(k=>SF.CUIDP[k]).filter(Boolean);
   if(SF.esMenor(c)){const fe=/hija|nieta|niña|sobrina/i.test(c.parentesco||'');let t=`${fe?'Una menor':'Un menor'} de ${conE?e+(e===1?' año':' años'):P('edad del menor')}${c.parentesco?' ('+c.parentesco+')':''}`;t+=cu.length?`, de quien se ocupaba de ${listY(cu)}`:'';if(c.extra)t+=`, llevándole además a sus actividades (${c.extra.trim().replace(/\.$/,'')})`;out.push(t+'.');if(c.rutina)out.push(`Su horario diario era el siguiente: ${lcf(c.rutina.trim().replace(/\.$/,''))}.`);return;}
   const at=[c.autonomia?SF.AUT[c.autonomia]:'',SF.GRADO[c.grado]||''].filter(Boolean);const dg=(c.diag||[]).map(k=>SF.DIAGP[k]);if(c.diagOtro)dg.push(c.diagOtro.trim());
   let t=`${c.nombre||P('nombre')}${c.parentesco?' ('+c.parentesco+')':''}, de ${conE?e+' años':P('edad de '+(c.nombre||'la persona'))}${at.length?', '+at.join(', '):''}`;if(dg.length)t+=`, que padece ${listY(dg)}`;if(c.ayudas)t+=` y utiliza ${lcf(c.ayudas.trim().replace(/\.$/,''))}`;out.push(t+'.');
   if(cu.length||c.medicacion)out.push(`${Tr} se ocupaba de ${listY(cu.length?cu:['su atención diaria'])}${c.medicacion?`, administrándole la medicación (${c.medicacion.trim().replace(/\.$/,'')})`:''}.`);
   if(SF.NOCHE[c.noche])out.push(SF.NOCHE[c.noche]+'.');
   if(c.rutina)out.push(`Su horario diario era el siguiente: ${lcf(c.rutina.trim().replace(/\.$/,''))}.`);
   if(c.centro)out.push(lcf(c.centro.trim()).replace(/^/,'Además, ').replace(/\.?$/,'.'));
   if(c.sanitarios)out.push(`La atendían también ${lcf(c.sanitarios.trim().replace(/\.$/,''))}.`);
   if(c.obs)out.push(c.obs.trim().replace(/\.?$/,'.'));
   if(c.hist)out.push(c.hist.trim().replace(/\.?$/,'.'));});}
 /* llaves, alarma, segunda residencia */
 const ll=v('hog_llaves')==='si',al=v('hog_alarma')==='si';if(ll||al)out.push(`${Tr} ${ll?'disponía de llaves de la vivienda':''}${ll&&al?' y ':''}${al?'conocía el código de la alarma':''}, lo que evidencia la confianza depositada en ella y la habitualidad de su trabajo.`);
 if(v('hog_segunda')==='si')out.push(`Acompañaba además a la familia a ${v('hog_segunda_txt')?lcf(v('hog_segunda_txt').trim().replace(/\.$/,'')):P('segunda residencia y fechas')}, donde continuaba prestando sus servicios.`);
 /* visitas */
 const E=(st.entorno||[]).filter(x=>x.nombre&&x.nombre.trim());
 if(E.length){out.push(`A la vivienda acudían con regularidad, entre otras personas: ${E.map(x=>`${x.nombre}${x.relacion?' ('+x.relacion+')':''}${x.frec?', '+SF.FREC[x.frec]:''}${x.dias?' ('+x.dias.trim().replace(/\.$/,'')+')':''}${x.que?', que '+lcf(x.que.trim().replace(/\.$/,'').replace(/^que /i,'')):''}`).join('; ')}.`);
  const vi=E.filter(x=>x.vio==='si');if(vi.length)out.push(`${listY(vi.map(x=>x.nombre))} ${vi.length>1?'la veían':'la veía'} desempeñar su trabajo de forma habitual.`);}
 const ctx=v('hog_contexto');if(ctx)out.push('Sobre la organización del trabajo en el hogar: '+lcf(ctx.trim()).replace(/\.?$/,'.'));
 return out.join(' ');};
SF.mediosPrueba=st=>{const v=id=>V(st,id),L=[];const tiene=k=>(st.pruebas[k]||{}).estado==='tiene';
 if(v('pru_msgs')==='si'||tiene('chat'))L.push('conversaciones escritas mantenidas con la parte requerida');
 if(v('pru_email')==='si'||tiene('correos'))L.push('correos electrónicos intercambiados con la parte requerida');
 if(v('ext_forma')==='mensaje'||tiene('msg_desp'))L.push('el mensaje con el que se le comunicó el despido');
 if((v('ext_forma')==='escrito'&&v('ext_carta')==='si')||tiene('carta'))L.push('la comunicación escrita de despido');
 if((v('sal_cobro')||[]).some(x=>x==='transferencia'||x==='bizum')||tiene('pagos'))L.push('justificantes de los pagos recibidos');
 if(v('pru_fotos')==='si'||tiene('fotos'))L.push('fotografías y vídeos de la prestación de servicios');
 if(st.jor.dias.length)L.push('el registro detallado de la jornada realizada');
 if(v('pru_testigos')==='si'||tiene('testigos'))L.push('testigos que conocen la prestación de servicios');
 if(v('ext_testigos')==='si'||tiene('test_desp'))L.push('testigos de la comunicación del despido');
 const M={contrato:'el contrato de trabajo',nominas:'las nóminas',vida:'el informe de vida laboral',turnos:'cuadrantes de turnos',fichajes:'registros de fichaje',horario:'documentos sobre el horario',embarazo:'documentación médica del embarazo',baja:'partes médicos',reclamo:'la reclamación previa',acoso:'pruebas del acoso',vg:'la acreditación de la situación de violencia de género',hijos:'la solicitud de reducción o permiso',residencia:'pruebas de su residencia en el domicilio',indicios:'otros indicios documentales'};
 Object.keys(M).forEach(k=>{if(tiene(k))L.push(M[k]);});return [...new Set(L)];};
SF.P=t=>'⟦'+t+'⟧';
SF.genPapeleta=(st,hoy)=>{hoy=hoy||SF.today();const R=SF.evaluate(st,hoy),K=R.K,v=id=>V(st,id),A=st.abg,P=SF.P,T=st.tipo;
 const fem=v('cli_trato')==='da';const tr=fem?'la trabajadora':'el trabajador',Tr=fem?'La trabajadora':'El trabajador',sr=fem?'D.ª':'D.',aTr=fem?'a la trabajadora':'al trabajador',dTr=fem?'de la trabajadora':'del trabajador';const lc=x=>x?x.charAt(0).toLowerCase()+x.slice(1):x;
 const nom=v('cli_nombre')||P('nombre del trabajador');const doc=v('cli_doc')&&v('cli_doc')!=='ninguno'?`${v('cli_doc')==='pasaporte'?'pasaporte':v('cli_doc')} n.º ${v('cli_docnum')||P('número de documento')}`:P('documento de identidad');
 const H=[];const out=(k,t)=>H.push({k,t});
 /* partes requeridas */
 const partes=[];let empN;
 if(T==='C'){const tit=st.personas.filter(p=>p.nombre.trim()&&(p.roles.includes('dueno')||p.roles.includes('contrato')||p.roles.includes('pago')));
  (tit.length?tit:[{nombre:P('nombre de la persona empleadora'),dni:''}]).forEach(p=>partes.push(`${p.nombre}${p.dni?', con DNI/NIE '+p.dni:', '+P('DNI/NIE de '+p.nombre)}, en su condición de titular del hogar familiar empleador, con domicilio en ${SF.fmtDir(v('hog_dir'),P)}`));
  empN=tit.length?tit.map(p=>p.nombre).join(' y '):P('persona empleadora');}
 else if(v('emp_tipo')==='autonomo'){empN=v('aut_nombre')||P('nombre del empleador');partes.push(`${empN}${v('aut_dni')?', con DNI/NIE '+v('aut_dni'):', '+P('DNI/NIE del empleador')}${v('aut_negocio')?', titular del negocio «'+v('aut_negocio')+'»':''}, con domicilio en ${v('emp_dom')?SF.fmtDir(v('emp_dom'),P):P('domicilio del empleador')}`);}
 else{empN=v('emp_nombre')||P('denominación social de la empresa');partes.push(`la mercantil ${empN}, con CIF ${v('emp_cif')||P('CIF')}, con domicilio social en ${v('emp_dom')?SF.fmtDir(v('emp_dom'),P):P('domicilio social')}`);
  if(A.admins&&(T==='B'||A.incluirAdminsA)){SF.persWith(st,'dueno').forEach(p=>partes.push(`${p.nombre}${p.dni?', con DNI/NIE '+p.dni:', '+P('DNI/NIE de '+p.nombre)}, en su condición de administrador/a de la citada mercantil durante la relación laboral, como posible responsable solidario`));}
  if(v('emp_estado')==='concurso')partes.push(`la administración concursal de ${empN}, ${P('nombre y domicilio de la administración concursal')}`);}
 const ordenes=SF.persWith(st,'ordenes').map(p=>p.nombre+(p.relacion?' ('+p.relacion+')':'')).join(', ');
 const pagador=SF.persWith(st,'pago').map(p=>p.nombre).join(', ');const contrato=SF.persWith(st,'contrato').map(p=>p.nombre).join(', ');
 const ini=v('rel_inicio');const iniT=ini?SF.fmtL(ini):P('fecha de inicio');
 const centro=T==='C'?'el domicilio familiar sito en '+SF.fmtDir(v('hog_dir'),P):(v('emp_centro')?'el centro de trabajo sito en '+SF.fmtDir(v('emp_centro'),P):P('centro de trabajo'));
 const fun=T==='C'?`funciones de empleada de hogar${V(st,'hog_interna')?' en régimen de '+V(st,'hog_interna')+(V(st,'hog_pernocta')==='si'?', pernoctando en el domicilio':V(st,'hog_pernocta')==='algunas'?', pernoctando algunas noches en el domicilio':''):P('régimen de interna o externa')}, realizando las tareas de ${V(st,'hog_tareas')?(l=>l.length>1?l.slice(0,-1).join(', ')+' y '+l[l.length-1]:l[0])(V(st,'hog_tareas').map(x=>({limpieza:'limpieza',cocina:'cocina',plancha:'lavado y planchado',ninos:'cuidado de menores',mayores:'cuidado de una persona mayor',dependiente:'atención a una persona dependiente',compras:'compras y recados',mascotas:'cuidado de animales',otras:'otras tareas domésticas'})[x])):P('tareas')}`:(A.categoriaD?`la categoría de ${A.categoriaD}`:`las funciones de ${lc(v('rel_trabajo'))||P('trabajo realizado')}`);
 const dia=v('rel_dia');
 const CB={efectivo:'en efectivo',transferencia:'mediante transferencia bancaria',bizum:'mediante Bizum',otra:'por otros medios'};const cobro=(v('sal_cobro')||[]).map(x=>CB[x]).join(' y ');
 /* HECHOS */
 let n=0;const ord=['PRIMERO','SEGUNDO','TERCERO','CUARTO','QUINTO','SEXTO','SÉPTIMO','OCTAVO','NOVENO','DÉCIMO','UNDÉCIMO','DUODÉCIMO'];const H1=t=>H.push({lbl:ord[n++],t});
 H1(`${Tr} ha prestado servicios por cuenta y bajo la dependencia de ${T==='C'?'la parte requerida':empN} desde el ${iniT}${(st.ans.rel_inicio||{}).aprox?' '+P('confirmar día exacto de inicio'):''}, en ${centro}, desempeñando ${fun}${dia?'. Su actividad diaria consistía en: '+lc(dia).replace(/\.$/,''):''}.${v('rel_contrato_fecha')&&ini&&SF.pd(v('rel_contrato_fecha'))>SF.pd(ini)?` Aunque el contrato escrito fija el inicio el ${SF.fmtL(v('rel_contrato_fecha'))}, la prestación real de servicios comenzó el ${iniT}, fecha que debe computarse a efectos de antigüedad.`:''}`);
 if(v('rel_como'))H1('Sobre el inicio de la relación: '+lcf(v('rel_como').trim()).replace(/\.?$/,'.'));
 if(T==='C'){const ct=SF.cuidadosTxt(st,P,tr,Tr);if(ct)H1(ct);}
 if(v('hist_cambios'))H1('A lo largo de la relación, '+lcf(v('hist_cambios').trim()).replace(/\.?$/,'.'));
 if(v('hist_trato'))H1('En cuanto al trato recibido: '+lcf(v('hist_trato').trim()).replace(/\.?$/,'.'));
 H1(`${ordenes?`Recibía las órdenes e instrucciones de ${ordenes}`:'Recibía órdenes e instrucciones de la parte requerida'}${SF.persWith(st,'horario').length?', que fijaba su horario':''}${contrato?`; fue contratad${fem?'a':'o'} por ${contrato}`:''}. Percibía como retribución ${K.sal?eur(K.sal)+' mensuales':P('salario mensual')}${cobro?', abonados '+cobro:''}${pagador?' por '+pagador:''}${v('sal_frec')?', con periodicidad '+({mes:'mensual',quincena:'quincenal',semana:'semanal',dia:'diaria'})[v('sal_frec')]:''}. Concurren, por tanto, todas las notas de una relación laboral: prestación personal, voluntaria, retribuida, por cuenta ajena y dentro del ámbito de organización y dirección del empleador (art. 1.1 ET), cuya existencia se presume (art. 8.1 ET).`);
 if(T!=='A'||v('rel_alta')==='no'||v('rel_contrato')==='no'){
  const sinAlta=T==='C'||v('rel_alta')==='no';const sinContr=T==='C'||v('rel_contrato')==='no';
  H1(`${T==='A'?'':`${Tr} carecía de autorización administrativa para trabajar. Esta circunstancia no invalida el contrato de trabajo respecto de sus derechos ni le priva de las prestaciones que pudieran corresponderle (art. 36.5 de la Ley Orgánica 4/2000), y es responsabilidad exclusiva de quien le contrató. `}${sinContr&&sinAlta?`La parte requerida nunca formalizó contrato por escrito ni dio de alta ${aTr} en la Seguridad Social, incumpliendo las obligaciones de afiliación, alta y cotización que le impone la Ley General de la Seguridad Social.`:sinAlta?`La parte requerida no dio de alta ${aTr} en la Seguridad Social, incumpliendo sus obligaciones de afiliación, alta y cotización.`:sinContr?'La relación nunca se formalizó por escrito.':''}`);}
 /* jornada */
 const J=K.J;const hs=K.horas;
 if(hs||J.nDias){let t=`${Tr} realizaba una jornada real de ${hs?num1(hs)+' horas semanales de trabajo efectivo':P('horas semanales')}${K.horasFuente==='registro'?` de media, según el registro diario que se aportará (${J.nDias} días anotados)`:''}`;
  const hab=[1,2,3,4,5,6,7].map(d=>st.jor.patron[d]).some(p=>p.e&&p.s);
  if(hab){t+=', con el siguiente horario habitual: '+[1,2,3,4,5,6,7].filter(d=>st.jor.patron[d].e&&st.jor.patron[d].s).map(d=>{const p=st.jor.patron[d];return `${DOWN[d]} de ${p.e} a ${p.s}${Number(p.d)?' (descanso de '+p.d+' min)':''}`;}).join('; ');}
  t+='.';
  {const TT=SF.tareasTxt(st);if(TT)t+=' '+TT;}
  const lim=T==='C'?40:(Number(st.jor.ref)||40);
  if(hs&&hs>lim)t+=` Esta jornada supera en ${num1(hs-lim)} horas semanales la jornada máxima de ${lim} horas semanales de trabajo efectivo ${T==='C'?'(art. 9 del RD 1620/2011)':'(art. 34.1 ET)'}, sin que dichas horas le hayan sido retribuidas ni compensadas.`;
  if(J.largos&&T!=='C')t+=` En ${J.largos} de los días registrados se superaron las 9 horas de trabajo efectivo (art. 34.3 ET).`;
  if(v('jor_noche')==='si'||J.noct>0)t+=` Parte de la jornada se desarrollaba en horario nocturno${J.noct?' ('+num1(J.noct)+' horas entre las 22:00 y las 6:00 en los días registrados)':''}.`;
  if(v('jor_festivos')==='si')t+=' Trabajaba también en domingos y festivos.';if(v('jor_festivos')==='aveces')t+=' Trabajaba también, en ocasiones, en domingos y festivos.';
  if(T==='C'&&(v('hog_presencia')==='si'||J.avgPres)){t+=` Además del trabajo efectivo, debía permanecer en el domicilio a disposición de la parte empleadora${J.avgPres?' una media de '+num1(J.avgPres)+' horas semanales':''}, tiempo de presencia que debe retribuirse o compensarse conforme al art. 9 del RD 1620/2011${J.avgPres>20?', y que excede el límite de 20 horas semanales de promedio mensual':''}.`;}
  if(T!=='C'&&v('jor_fichaje')==='no')t+=` La empresa no llevaba el registro diario de jornada obligatorio (art. 34.9 ET), por lo que, conforme al principio de facilidad probatoria (art. 217.7 LEC), le corresponderá acreditar una jornada distinta de la aquí descrita.`;
  H1(t);}
 if(K.regPorSMI&&K.horas){const y=K.fin?new Date(SF.pd(K.fin)).getUTCFullYear():2026,s14=SF.SMI[Math.min(Math.max(y,2015),2026)]*K.jf;H1(v('sal_pagas')==='no'?`El salario abonado, ${eur(K.sal)} mensuales en doce mensualidades y sin pagas extraordinarias, es inferior al salario mínimo interprofesional, que para la jornada realizada asciende a ${eur(s14)} mensuales en catorce pagas (Real Decreto 126/2026 y precedentes), por lo que se reclaman las diferencias y las pagas extraordinarias no abonadas.`:`El salario abonado, ${eur(K.base)} mensuales incluida la parte proporcional de pagas extraordinarias, es inferior al salario mínimo interprofesional, que para la jornada realizada asciende a ${eur(K.smiMes)} mensuales (Real Decreto 126/2026 y precedentes), por lo que se reclaman las diferencias.`);}
 /* extinción */
 if(despLike(st)){const f=v('ext_forma'),fcom=v('fecha_com'),fef=v('fecha_efectos')||fcom;const quien=v('ext_quien')||SF.persWith(st,'despidio').map(p=>p.nombre).join(', ');
  const pal=v('ext_literal_txt');const dicho=v('ext_dicho');
  let t=`El ${fcom?SF.fmtL(fcom):P('fecha del despido')}${(st.ans.fecha_com||{}).aprox?' '+P('confirmar fecha exacta'):''}, ${quien?(/^(La|El|Los|Las|Un|Una) /.test(quien)?lc(quien):quien)+(/,/.test(quien)?',':''):P('quién comunicó el despido')} comunicó ${aTr}`;
  const tipo=v('ext_tipo');
  if(tipo==='no_llaman')t=`Desde el ${fef?SF.fmtL(fef):P('fecha')}, la parte requerida dejó de proporcionar trabajo ${aTr}${f==='nada'?' sin comunicación alguna':''}, lo que constituye un despido tácito`;
  else if(tipo==='baja_forzada')t+=` que debía firmar un documento de baja voluntaria${v('ext_firmo_presion')==='si'?', que firmó bajo presión y sin comprender su alcance, por lo que carece de valor como dimisión':''}. Se trata de un despido encubierto`;
  else if(tipo==='fin_contrato')t+=` la finalización de su contrato, extinción que encubre un despido`;
  else t+=` ${f==='palabra'?'verbalmente':f==='mensaje'?'mediante mensaje':f==='escrito'?'por escrito':''} la extinción de la relación laboral`;
  if(f!=='nada'&&tipo!=='no_llaman'){if(pal)t+=`, con estas palabras: «${pal}»`;else if(dicho)t+=`, alegando ${dicho.replace(/^que /i,'que ').replace(/\.$/,'')}`;}
  t+=`, con efectos del ${fef?SF.fmtL(fef):P('fecha de efectos')}.`;
  if(f==='escrito')t+=` Los hechos que, en su caso, se imputan en la comunicación escrita se niegan en su totalidad.`;
  else t+=T==='C'?` No se entregó comunicación escrita ni se respetaron los requisitos de forma y preaviso exigidos por el art. 11 del RD 1620/2011.`:` No se entregó carta de despido con expresión de los hechos que lo motivan y su fecha de efectos, como exige el art. 55.1 ET, lo que determina, como mínimo, la improcedencia del despido (art. 55.4 ET).`;
  if(v('ext_testigos')==='si')t+=' Hubo testigos de la comunicación.';
  if(v('ext_dia'))t+=' Lo ocurrido ese día fue lo siguiente: '+v('ext_dia').trim().replace(/\.?$/,'.');
  if(v('ext_hablo'))t+=' Además, '+lcf(v('ext_hablo').trim()).replace(/\.?$/,'.');
  H1(t);
  const sit=(v('ext_sit')||[]).filter(x=>x!=='ninguna');
  if(sit.length){const M={embarazo:`${Tr} se encontraba embarazada o en periodo de protección por nacimiento, lo que determina la nulidad del despido con independencia de que la parte requerida lo conociera (art. 55.5.b ET)`,baja:`${Tr} se encontraba en situación de baja médica o enfermedad, por lo que el despido constituye una discriminación por razón de enfermedad (Ley 15/2022) y debe declararse nulo`,hijos:`${Tr} disfrutaba de reducción de jornada o de un permiso por cuidado de hijos, situación protegida por el art. 55.5.b ET`,reclamo:`${Tr} había reclamado previamente sus derechos, por lo que el despido es una represalia contraria a la garantía de indemnidad (art. 24 CE)`,acoso:`${Tr} venía sufriendo una situación de acoso, por lo que el despido vulnera sus derechos fundamentales`,vg:`${Tr} es víctima de violencia de género, situación protegida por el art. 55.5.b ET`};
   H1(sit.map(x=>M[x]).join('. ')+'. El despido es, por tanto, NULO, con las consecuencias del art. 55.6 ET.');}
  if(v('ext_firmo')==='si')H1(`El documento que se hizo firmar ${aTr} a la salida ${v('ext_firmo_nc')==='si'?'lleva la mención «no conforme» y ':''}no supone renuncia a ninguno de sus derechos, que son irrenunciables (art. 3.5 ET)${v('ext_firmo_presion')==='si'?', y fue firmado bajo presión':''}.`);
 }
 /* cantidades */
 if(A.incObs&&st.obs){const ob=st.obs.split('\n').map(l=>{const i=l.indexOf(':');return i>=0?[l.slice(0,i).trim(),l.slice(i+1).trim()]:['',l.trim()];}).filter(x=>x[1]).map(x=>x[0]?`${x[0].replace(/\s*\(.*\)$/,'')}: ${x[1].replace(/\.$/,'')}`:x[1].replace(/\.$/,''));if(ob.length)H1('Otros hechos relevantes. '+ob.join('. ')+'.');}
 if(!despLike(st)&&v('ext_dia'))H1('Los hechos ocurridos fueron los siguientes: '+v('ext_dia').trim().replace(/\.?$/,'.'));
 if(K.items.length)H1(`A la fecha de la extinción, la parte requerida adeuda ${aTr} las siguientes cantidades, que se detallan en el suplico: ${K.items.map(i=>i.c.toLowerCase()).join('; ')}.`);
 if(A.advPruebas){const L=SF.mediosPrueba(st);if(L.length)H1(`Para acreditar estos hechos, ${tr} dispone, entre otros, de los siguientes medios de prueba: ${L.join('; ')}, que se aportarán en el momento procesal oportuno.`);}
 if(T!=='C'){const rep=v('cli_rep');H1(rep==='si'?P('ostentó la condición de representante: adaptar garantías (art. 68 ET)'):rep==='no'?`${Tr} no ostenta ni ha ostentado en el último año la condición de representante legal o sindical de los trabajadores.`:P('confirmar si fue representante de los trabajadores en el último año'));}
 if(v('pap')==='si')H1(`${P('se presentó una papeleta anterior el '+(v('pap_fecha')?SF.fmt(v('pap_fecha')):'?')+': revisar antes de presentar esta')}`);

 /* SUPLICO */
 const S=[];const cal=K.calif;const fef=v('fecha_efectos')||v('fecha_com');
 if(T!=='A'||v('rel_alta')==='no'||(v('rel_contrato_fecha')&&ini&&SF.pd(v('rel_contrato_fecha'))>SF.pd(ini))||!despLike(st))S.push(`Reconozca la existencia de la relación laboral con ${tr} desde el ${iniT}, con ${T==='C'?'la condición de empleada de hogar':(A.categoriaD?'la categoría de '+A.categoriaD:'las funciones descritas')} y un salario regulador de ${K.reg?eur(K.reg)+' mensuales ('+eur(K.diario)+' diarios)':P('salario regulador')}.`);
 if(despLike(st)){
  if(cal==='nulo')S.push(`Reconozca la NULIDAD del despido de ${fef?SF.fmtL(fef):P('fecha de efectos')} y readmita de inmediato ${aTr} en su puesto y condiciones, abonándole los salarios dejados de percibir desde esa fecha a razón de ${K.diario?eur(K.diario)+' diarios':P('salario diario')}${T!=='A'?', con el alta en la Seguridad Social desde el inicio de la relación':''}, más la indemnización por vulneración de derechos fundamentales que se fije ${P('cuantía (art. 183 LRJS)')}. Subsidiariamente, reconozca la improcedencia del despido en los términos del apartado siguiente.`);
  const indT=K.ind!=null?`${eur(K.ind)}, resultado de ${num1(K.indDias)} días de salario (${K.indRegla})`:(T==='C'?P('indemnización conforme al RD 1620/2011: fijar días por año y tope'):P('indemnización: faltan fechas o salario'));
  S.push(`${cal==='nulo'?'Subsidiariamente, reconozca':'Reconozca'} la IMPROCEDENCIA del despido y, a su opción, readmita ${aTr} con abono de los salarios de tramitación a razón de ${K.diario?eur(K.diario)+' diarios':P('salario diario')}, o le abone una indemnización de ${indT}.`);}
 if(K.items.length){S.push(`Abone ${aTr} las siguientes cantidades, más el 10 % de interés anual por mora (art. 29.3 ET):`);}
 /* ADVERTENCIAS */
 const W=[];
 if(A.advCostas)W.push(`Si la parte requerida no comparece sin justa causa al acto de conciliación, el Juzgado le impondrá las costas del proceso, incluidos los honorarios del letrado ${dTr} hasta 600 euros, cuando la sentencia coincida esencialmente con lo aquí solicitado (art. 66.3 LRJS).`);
 if(A.advITSS)W.push(`${Tr} se reserva el derecho a poner estos hechos en conocimiento de la Inspección de Trabajo y Seguridad Social, sin perjuicio de las acciones judiciales que le asisten.`);
 if(A.advAlta&&(T!=='A'||v('rel_alta')==='no'))W.push(`La falta de alta en la Seguridad Social constituye infracción grave (art. 22.2 LISOS) y hace responsable a la parte requerida de las prestaciones que por ello pudieran corresponder ${aTr}.`);
 if(A.advRegistro&&T!=='C'&&v('jor_fichaje')==='no')W.push(`La ausencia del registro diario de jornada constituye infracción grave en materia de tiempo de trabajo (art. 7.5 LISOS).`);
 if(A.advExtr&&T!=='A')W.push(`La ocupación de personas extranjeras sin autorización de trabajo constituye infracción muy grave (art. 54.1.d LO 4/2000), sancionable con multa de 10.001 a 100.000 euros por cada persona ocupada (art. 55.1.c LO 4/2000).`);
 const pend=[];
 return {H,S,W,partes,K,R,tr,Tr,sr,nom,doc,empN,cal,
  cabecera:{organo:A.organo||P('órgano de conciliación (SMAC u órgano autonómico)'),localidad:A.localidad||P('localidad'),letrado:A.letrado||P('letrado/a del despacho'),dom:A.domNotif||P('domicilio del despacho para notificaciones')}};};

SF.papToText=G=>{const s=[];const st=SF.st,v=id=>V(st,id),P=SF.P;
 s.push(`AL ${G.cabecera.organo.toUpperCase()}`,'');
 s.push(`${G.sr} ${G.nom}, mayor de edad, con ${G.doc}, con domicilio en ${SF.fmtDir(v('cli_dom'),P)}${v('cli_email')?', correo electrónico '+v('cli_email'):''}, y a efectos de notificaciones en ${G.cabecera.dom}, representad${G.sr==='D.ª'?'a':'o'} por ${G.cabecera.letrado} ${P('acreditar representación')}, ante este Servicio comparece y, como mejor proceda, DICE:`,'');
 s.push(`Que por medio del presente escrito presenta PAPELETA DE CONCILIACIÓN en materia de ${despLike(st)?'DESPIDO'+(G.K.items.length?' Y RECLAMACIÓN DE CANTIDAD':''):'RECLAMACIÓN DE CANTIDAD'} frente a:`,'');
 G.partes.forEach((p,i)=>s.push(`${i+1}. ${p}.`));s.push('','Y lo fundamenta en los siguientes','','HECHOS','');
 G.H.forEach(h=>s.push(`${h.lbl}.- ${h.t}`,''));
 s.push('Por lo expuesto,','','SOLICITA','');
 s.push('Que tenga por presentada esta papeleta, la admita y cite a las partes al preceptivo acto de conciliación, en el que se solicitará que la parte requerida se avenga a:','');
 G.S.forEach((x,i)=>s.push(`${i+1}.º ${x}`));
 if(G.K.items.length){G.K.items.forEach(i=>s.push(`   — ${i.c}: ${i.imp!=null?SF.eur(i.imp):P('importe')} (${i.det}${i.est?'; estimación':''}).`));s.push(`   TOTAL CANTIDADES: ${SF.eur(G.K.totalCant)}${G.K.items.some(i=>i.imp==null)?' + importes pendientes de fijar':''}.`);}
 s.push('');
 if(G.W.length){s.push('ADVERTENCIAS','');G.W.forEach(w=>s.push(w,''));}
 s.push(`OTROSÍ DIGO: que ${G.tr} comparecerá al acto representad${G.sr==='D.ª'?'a':'o'} por letrado, designando a efectos de notificaciones el domicilio indicado.`,'');
 s.push(`En ${G.cabecera.localidad}, a ${SF.fmtL(SF.today())}.`,'','Fdo.: '+G.nom,'Fdo.: '+G.cabecera.letrado);
 return s.join('\n');};

/* ================= escenarios ficticios ================= */
const mk=(tipo,ans,extra)=>{const st=SF.newFicha(tipo);Object.entries(ans).forEach(([k,v])=>{st.ans[k]=v==='?'?{v:'',ns:true,nota:'',estado:'declarado'}:{v,ns:false,nota:'',estado:'declarado'};});if(extra)extra(st);return st;};
const per=(st,nombre,relacion,roles,dni)=>{st.seq++;st.personas.push({id:'P'+st.seq,nombre,relacion,tel:'',dni:dni||'',roles});};
const pat=(st,days,e,s,d,p,tk)=>days.forEach(x=>{st.jor.patron[x]={e,s,d:String(d||''),p:String(p||''),tk:(tk||[]).slice()};});
const DIR=(via,calle,num,piso,puerta,cp,loc,prov)=>({via,calle,num,piso,puerta,cp,loc,prov});
const tarea=(st,t,desde,hasta,extra)=>{st.seq++;const id='T'+st.seq;st.jor.tareas.push({id,t,desde,hasta,extra:!!extra});return id;};
SF.SCEN=[
 {id:'A',tipo:'A',nombre:'Dependienta con contrato, despedida por WhatsApp',build:h=>mk('A',{cli_trato:'da',cli_nombre:'Ana Ruiz Prieto (ficticia)',cli_doc:'NIE',cli_docnum:'X0000000T (ficticio)',cli_nac:'1990-05-02',cli_tel:'600 000 101',cli_dom:DIR('Calle','Inventada (ficticia)','3','2','B','28013','Madrid','Madrid'),cli_permiso:'si',cli_interp:'no',cli_rep:'no',emp_tipo:'empresa',emp_nombre:'Modas Ejemplo Ficticio S.L.',emp_cif:'B00000000 (ficticio)',emp_dom:DIR('Avenida','Supuesta (ficticia)','10','','','28046','Madrid','Madrid'),emp_centro:DIR('Calle','del Centro Comercial Imaginario (ficticio)','5','','local 12','28050','Madrid','Madrid'),emp_otros:'no',emp_estado:'abierto',rel_inicio:'2021-03-01',rel_antes:'no',rel_contrato:'si',rel_contrato_fecha:'2021-06-01',rel_alta:'si',rel_nominas:'si',rel_puesto:'Dependienta',rel_trabajo:'Dependienta de tienda de ropa',rel_dia:'Abría la tienda, atendía a clientes, cobraba en caja, reponía género y hacía el cierre de caja',rel_ultimo:SF.wdDay(h,5),jor_horas:'45',jor_tipo:'fijo',jor_noche:'no',jor_festivos:'aveces',jor_fichaje:'no',sal_real:'1300',sal_cobro:['transferencia'],sal_frec:'mes',sal_pagas:'aparte',sal_vac:'parte',deb:'si',deb_conc:['vacaciones','horas'],deb_desde:SF.addDays(h,-200),ext_tipo:'despido',ext_quien:'Laura (encargada)',ext_forma:'mensaje',ext_dicho:'que no hacía falta que volviera',ext_literal:'si',ext_literal_txt:'mañana ya no vengas, no te necesitamos',fecha_com:SF.wdDay(h,5),fecha_efectos:SF.wdDay(h,5),ext_dia:'Recibió el WhatsApp a las 21:30, ya en su casa. Al día siguiente fue a la tienda y la encargada no la dejó entrar; le dijo que ya le pagarían lo que le debían',ext_hablo:'llamó a Pedro Sanz, el administrador, que no le cogió el teléfono',ext_testigos:'no',ext_sit:['ninguna'],ext_firmo:'no',pap:'no',abog:'no',pru_msgs:'si',pru_fotos:'no',pru_testigos:'si',pru_testigos_txt:'Compañera de tienda (ficticia): horario y despido'},st=>{per(st,'Laura Gómez (ficticia)','encargada',['ordenes','horario','despidio']);per(st,'Pedro Sanz (ficticio)','administrador',['contrato','pago','dueno']);tarea(st,'Atender a clientes, cobrar y reponer género','10:00','19:30');const t1=tarea(st,'Cierre de caja, recuento y ordenar el almacén','19:30','20:30',1);pat(st,[1,2,3,4,5],'10:00','20:30',30,0,[t1]);pat(st,[6],'10:00','14:00',0);st.abg.organo='Servicio de Mediación, Arbitraje y Conciliación (SMAC) de Madrid';st.abg.localidad='Madrid';})},
 {id:'B',tipo:'B',nombre:'Camarero sin papeles, despido de palabra',build:h=>mk('B',{cli_trato:'d',cli_nombre:'Kevin Arboleda Ríos (ficticio)',cli_doc:'pasaporte',cli_docnum:'AA000000 (ficticio)',cli_nac:'1997-04-11',cli_tel:'600 000 202',cli_dom:DIR('Calle','Ficticia','8','1','A','28012','Madrid','Madrid'),cli_permiso:'no',cli_interp:'no',cli_rep:'no',emp_tipo:'empresa',emp_nombre:'Bar La Esquina Ficticia S.L.',emp_cif:'?',emp_dom:'?',emp_centro:DIR('Calle','Ejemplo (ficticia)','1','','','28005','Madrid','Madrid'),emp_otros:'no',emp_estado:'abierto',rel_inicio:SF.addDays(h,-610),rel_antes:'no',rel_como:'Un amigo le presentó al dueño',rel_dondeempezo:'En el mismo bar',rel_contrato:'no',rel_alta:'no',rel_trabajo:'Camarero de barra y sala',rel_dia:'Abría el bar a las 12, preparaba la barra, servía comidas y cenas, limpiaba la cocina y cerraba a medianoche',rel_ordenes:'En persona y por WhatsApp',rel_ultimo:SF.wdDay(h,8),jor_horas:'52',jor_tipo:'fijo',jor_noche:'si',jor_festivos:'si',jor_fichaje:'no',sal_real:'1100',sal_pactado:'1200',sal_cobro:['efectivo'],sal_frec:'mes',sal_pagas:'no',sal_vac:'no',deb:'si',deb_conc:['salarios','pagas','vacaciones','horas'],deb_desde:SF.addDays(h,-240),deb_importe:'550',ext_tipo:'despido',ext_quien:'Antonio, el dueño',ext_forma:'palabra',ext_dicho:'que ya no había trabajo para él',ext_literal:'si',ext_literal_txt:'aquí ya no pintas nada, no vuelvas',fecha_com:SF.wdDay(h,8),fecha_efectos:SF.wdDay(h,8),ext_dia:'Llegó a las 12 como siempre. Antonio le esperaba en la barra, delante de la cocinera, le dijo que no volviera y le pidió las llaves del local',ext_hablo:'al día siguiente le escribió por WhatsApp pidiéndole lo que le debía y no le contestó',ext_testigos:'si',ext_testigos_txt:'Cocinera del bar (ficticia)',ext_sit:['ninguna'],ext_firmo:'no',pap:'no',abog:'no',pru_msgs:'si',pru_fotos:'si',pru_menores:'no',pru_testigos:'si',pru_testigos_txt:'Cocinera (ficticia) y un cliente habitual (ficticio)'},st=>{per(st,'Antonio Pérez (ficticio)','dueño y administrador',['contrato','ordenes','horario','pago','despidio','dueno'],'00000000A (ficticio)');tarea(st,'Preparar la barra y recibir pedidos','12:00','13:00');tarea(st,'Servir comidas y cenas en barra y sala','13:00','23:00');const t1=tarea(st,'Cierre: cuadrar la caja y limpiar cocina y barra','23:00','00:00',1);pat(st,[2,3,4,5,6,7],'12:00','00:00',150,0,[t1]);st.abg.organo='Servicio de Mediación, Arbitraje y Conciliación (SMAC) de Madrid';st.abg.localidad='Madrid';})},
 {id:'C',tipo:'C',nombre:'Interna que cuidaba niños y a una abuela',build:h=>mk('C',{cli_trato:'da',cli_nombre:'Rosa Quispe Mamani (ficticia)',cli_doc:'pasaporte',cli_docnum:'BB000000 (ficticio)',cli_nac:'1985-09-20',cli_tel:'600 000 303',cli_email:'rosa.ficticia@example.com',rel_como:'Una prima que trabajaba de portera en el edificio le presentó a la señora. En la primera conversación le prometieron 1.000 € al mes y que la darían de alta en cuanto tuviera papeles',hist_cambios:'desde enero la abuela empeoró y tenía que levantarse varias veces cada noche, sin que le subieran el sueldo',hist_trato:'la señora le gritaba si los niños llegaban tarde al colegio y le descontaba dinero cuando rompía algo; le pagaba a veces con una semana de retraso',pru_email:'no',cli_dom:DIR('Calle','Supuesta (ficticia)','22','3','C','28039','Madrid','Madrid'),cli_permiso:'no',cli_interp:'no',hog_dir:DIR('Calle','Residencial Ficticia','5','4','A','28016','Madrid','Madrid'),hog_contexto:'los padres trabajaban fuera de lunes a viernes y llegaban a casa sobre las 20 h; los fines de semana la señora le dejaba una lista de tareas',hog_mascotas:'un perro, que sacaba a pasear dos veces al día',hog_llaves:'si',hog_alarma:'si',hog_segunda:'si',hog_segunda_txt:'una casa en Cullera (Valencia), en julio y agosto',hog_num:'1',rel_inicio:SF.addDays(h,-480),hog_interna:'interna',hog_tareas:['limpieza','cocina','ninos','mayores'],rel_dia:'Levantaba y vestía a los niños, los llevaba al colegio, limpiaba la casa, cocinaba, atendía a la abuela y la acostaba',hog_pernocta:'si',rel_ultimo:SF.wdDay(h,3),jor_horas:'60',jor_tipo:'fijo',jor_noche:'si',jor_festivos:'aveces',hog_presencia:'si',sal_real:'900',sal_pactado:'1000',sal_cobro:['efectivo','bizum'],sal_frec:'mes',sal_pagas:'no',sal_vac:'no',deb:'si',deb_conc:['pagas','vacaciones'],deb_desde:SF.addDays(h,-300),ext_tipo:'despido',ext_quien:'La señora de la casa',ext_forma:'palabra',ext_dicho:'que ya no la necesitaban',ext_literal:'no',ext_dia:'Por la mañana, después de llevar a los niños al colegio, la señora le dijo en la cocina que ya no la necesitaban y que recogiera sus cosas ese mismo día. Le había contado su embarazo dos semanas antes',ext_hablo:'llamó al marido de la señora, que le contestó que era decisión de su mujer',fecha_com:SF.wdDay(h,3),fecha_efectos:SF.wdDay(h,3),ext_testigos:'no',ext_sit:['embarazo'],ext_firmo:'no',pap:'no',abog:'no',pru_msgs:'si',pru_fotos:'si',pru_menores:'si',pru_testigos:'si',pru_testigos_txt:'Portera del edificio (ficticia)'},st=>{per(st,'Elena Martín (ficticia)','señora de la casa',['contrato','ordenes','horario','pago','despidio','dueno','vive'],'?');st.personas[0].edad='45';st.personas[0].trabajo='abogada en un despacho del centro de Madrid';per(st,'Javier Ruiz (ficticio)','marido de la señora',['vive']);st.personas[1].edad='47';st.personas[1].trabajo='ingeniero, trabaja fuera de lunes a viernes';tarea(st,'Levantar y vestir a los niños, desayunos y llevarlos al colegio','07:00','09:00');tarea(st,'Limpieza, compra y comida','09:00','14:00');tarea(st,'Atender a la abuela, recoger a los niños, deberes y cenas','14:00','21:00');const t1=tarea(st,'Planchar y dejar preparada la comida del día siguiente','21:00','22:00',1);const t2=tarea(st,'Atender a la abuela durante la noche (presencia)','22:00','07:00',1);
  pat(st,[1,2,3,4,5],'07:00','22:00',180,3,[t1,t2]);pat(st,[6],'08:00','14:00',0,0);
  st.cuidados.push({id:'K1',nombre:'Lucas (ficticio)',parentesco:'hijo',edad:'7',autonomia:'ayuda',cu:['aseo','vestir','comida','colegio','deberes'],colegio:'Colegio Ficticio San Juan, de 9 a 16:30',extra:'fútbol los martes y jueves de 17:30 a 18:30',saludN:'alérgico a los frutos secos',rutina:'',obs:''},{id:'K2',nombre:'Sofía (ficticia)',parentesco:'hija',edad:'4',autonomia:'ayuda',cu:['aseo','vestir','comida','colegio','paseo'],colegio:'Escuela infantil Ficticia, de 9 a 15',extra:'natación los viernes de 17 a 18',rutina:'',obs:''},{id:'K3',nombre:'Carmen López (ficticia)',parentesco:'madre de la señora',edad:'88',autonomia:'severa',grado:'II',hist:'Por las mañanas había que levantarla, asearla en la cama y darle el desayuno triturado. No reconocía a veces a su hija y se ponía nerviosa por la tarde; solo se calmaba con la trabajadora',diag:['alzheimer','movilidad','incontinencia','diabetes'],diagOtro:'',ayudas:'andador y cama articulada',medicacion:'pastillas a las 9, 14 y 21 h e insulina antes de la cena',noche:'varias',centro:'acudía a un centro de día los lunes y miércoles de 10 a 13 h, y la trabajadora la llevaba y recogía',sanitarios:'una fisioterapeuta dos tardes por semana y la enfermera del centro de salud cada quince días',rutina:'se levantaba a las 8, comía a las 13:30, dormía la siesta hasta las 16, cenaba a las 20 y se acostaba a las 21:30',cu:['aseo','comida','medicacion','movilidad','medico','noche'],obs:''});
  st.entorno.push({id:'E1',nombre:'Luis López (ficticio)',relacion:'hijo de Carmen',tel:'',frec:'semanal',dias:'los domingos de 11 a 14 h',que:'visitaba a su madre y comía con la familia',vio:'si',testigo:'ns'},{id:'E2',nombre:'Marta Gil (ficticia)',relacion:'fisioterapeuta de Carmen',tel:'',frec:'varias',dias:'martes y jueves de 17 a 18 h',que:'le hacía rehabilitación',vio:'si',testigo:'si'},{id:'E3',nombre:'Ana Torres (ficticia)',relacion:'nieta de Carmen',tel:'',frec:'mensual',dias:'algún sábado por la mañana',que:'visitaba a su abuela',vio:'si',testigo:'ns'},{id:'E4',nombre:'José (ficticio)',relacion:'portero del edificio',tel:'',frec:'diaria',dias:'',que:'la veía entrar y salir con los niños y con Carmen',vio:'si',testigo:'si'});
  st.obs='Comida y alojamiento (si se los daban y si le descontaban dinero por ello): tenía habitación en la casa y comía allí; no le descontaban nada.';st.abg.organo='Servicio de Mediación, Arbitraje y Conciliación (SMAC) de Madrid';st.abg.localidad='Madrid';})}
];
SF.buildScen=(id,hoy)=>{const sc=SF.SCEN.find(s=>s.id===id);const st=sc.build(hoy||SF.today());st.personas.forEach(p=>{if(p.dni==='?')p.dni='';});const fin=V(st,'rel_ultimo');if(fin){const d=SF.addDays(fin,-27);SF.fillPattern(st,d,fin);st.jor.desde=d;st.jor.hasta=fin;}return st;};

/* ================= pruebas automáticas ================= */
SF.runTests=()=>{const H='2026-10-26';const out=[];const T=(e,c,fn)=>{let ok=false,det='';try{const r=fn();ok=r===true||!!(r&&r.ok);det=r&&r.det?r.det:'';}catch(x){det='Error: '+x.message;}out.push({e,c,ok,det});};
 const al=(R,c)=>R.alerts.find(a=>a.cod===c);let st,R,G,txt;
 st=mk('B',{cli_nombre:'Prueba Uno (ficticio)',ext_tipo:'despido'});R=SF.evaluate(st,H);
 T('Entrevista incompleta','Alerta crítica de despido sin fecha aunque falte casi todo',()=>({ok:al(R,'sin_fecha')&&al(R,'sin_fecha').nivel==='critica'}));
 T('Entrevista incompleta','Lista los datos obligatorios que faltan',()=>({ok:R.incompletos.length>=15,det:R.incompletos.length+' pendientes'}));
 T('Entrevista incompleta','La papeleta marca los huecos y no inventa nada',()=>{G=SF.genPapeleta(st,H);SF.st=st;txt=SF.papToText(G);const n=(txt.match(/⟦/g)||[]).length;return {ok:n>=8&&/⟦CIF⟧|⟦denominación social/.test(txt),det:n+' huecos marcados'};});
 st=mk('B',{ext_tipo:'despido',rel_inicio:SF.wdBack(H,3),fecha_com:SF.wdBack(H,10),pap:'si',pap_fecha:SF.addDays(SF.wdBack(H,10),-6),cli_permiso:'si'});R=SF.evaluate(st,H);
 T('Fechas contradictorias','Inicio posterior al despido',()=>({ok:R.contra.some(c=>c.id==='ini_fecha_com')}));
 T('Fechas contradictorias','Papeleta anterior al despido',()=>({ok:R.contra.some(c=>c.id==='pap_previa')}));
 T('Fechas contradictorias','Ficha «sin papeles» con permiso declarado',()=>({ok:R.contra.some(c=>c.id==='ficha_permiso')}));
 T('Fechas contradictorias','Cada contradicción pasa a dudas del abogado',()=>({ok:R.dudas.filter(d=>/^Contradicción/.test(d)).length===R.contra.length}));
 st=mk('B',{ext_tipo:'despido',fecha_com:SF.wdBack(H,25)});R=SF.evaluate(st,H);
 T('Posible caducidad','Alerta crítica con solo dos datos',()=>({ok:al(R,'cad_posible')&&al(R,'cad_posible').nivel==='critica'}));
 T('Posible caducidad','No da una fecha de caducidad y dice qué falta para fijarla',()=>({ok:/no una fecha de caducidad/.test(al(R,'cad_posible').detalle)&&/fecha de efectos/.test(al(R,'cad_posible').detalle)}));
 st=mk('A',{ext_tipo:'despido',fecha_com:SF.wdBack(H,15),fecha_efectos:SF.wdBack(H,15)});st.ans.fecha_com.aprox=true;R=SF.evaluate(st,H);
 T('Plazo crítico','15 días laborables: quedarían 5, nivel crítico, avisa de fecha aproximada',()=>({ok:al(R,'plazo_critico')&&/5 días/.test(al(R,'plazo_critico').titulo)&&/aproximada/.test(al(R,'plazo_critico').detalle)}));
 st=mk('A',{ext_tipo:'despido',fecha_com:SF.wdBack(H,12),pap:'si',pap_fecha:SF.wdBack(H,4)});R=SF.evaluate(st,H);
 T('Papeleta presentada','Suspende el plazo: avisa de recálculo y no de caducidad',()=>({ok:!!al(R,'pap_susp')&&!al(R,'cad_posible'),det:R.alerts.map(a=>a.cod).join(', ')}));
 st=mk('A',{ext_tipo:'despido',fecha_com:SF.wdBack(H,25),pap:'si',pap_fecha:SF.wdBack(H,20),acto:'si',acto_fecha:SF.wdBack(H,10)});R=SF.evaluate(st,H);
 T('Papeleta y acto celebrado','Reanuda tras el acto: 5 + 10 días, quedarían 5',()=>{const a=al(R,'plazo_reanudado');return {ok:!!a&&a.nivel==='critica'&&/5 días/.test(a.titulo),det:a?a.titulo:R.alerts.map(x=>x.cod).join(',')};});
 st=mk('A',{ext_tipo:'despido',fecha_com:SF.wdBack(H,5),abog:'si',dem:'si'});R=SF.evaluate(st,H);
 T('Otro abogado y demanda','Avisa de ambos y no estima plazos',()=>({ok:!!al(R,'otro_abogado')&&!!al(R,'demanda')&&!R.alerts.some(a=>/plazo|cad/.test(a.cod))}));
 st=mk('B',{ext_tipo:'despido',fecha_com:SF.wdBack(H,3),rel_alta:'no',rel_contrato:'no',sal_cobro:['efectivo'],pru_msgs:'no',pru_fotos:'no',pru_testigos:'no'});R=SF.evaluate(st,H);
 T('Ausencia de pruebas','Alerta alta por falta de pruebas',()=>({ok:al(R,'sin_pruebas')&&al(R,'sin_pruebas').nivel==='alta'}));
 T('Ausencia de pruebas','Propone el checklist de existencia de la relación',()=>({ok:['chat','efectivo','fotos','turnos','testigos','indicios'].every(k=>R.pruebas.some(p=>p.key===k)),det:R.pruebas.map(p=>p.key).join(', ')}));
 st=SF.newFicha('B');
 T('Jornada','Turno de 22:00 a 06:00 con 30 min de descanso = 7,5 h; cruza medianoche',()=>{const c=SF.rowCalc({e:'22:00',s:'06:00',d:30});return {ok:Math.abs(c.ef-7.5)<1e-9&&c.cruza&&Math.abs(c.noct-7.5)<1e-9,det:c.ef+' h, nocturnas '+c.noct};});
 T('Jornada','Copia el horario habitual y permite excepciones',()=>{pat(st,[1,2,3,4,5],'09:00','19:00',0);const r=SF.fillPattern(st,'2026-10-05','2026-10-16');st.jor.dias[2].s='15:00';const S=SF.jorStats(st);return {ok:r.n===10&&S.weeks.length===2&&Math.abs(S.weeks[0].ef-46)<1e-9&&Math.abs(S.weeks[1].ef-50)<1e-9,det:r.n+' días; semanas '+S.weeks.map(w=>w.ef).join(' / ')};});
 T('Jornada','Días de 10 h se señalan para revisar, no se califican solos como extra',()=>{const S=SF.jorStats(st);return {ok:S.largos===9&&S.weeks[1].exceso===10,det:S.largos+' días >9 h; exceso semana 2: '+S.weeks[1].exceso+' h'};});
 st=SF.newFicha('C');pat(st,[1,2,3,4,5,6,7],'08:00','16:00',60,3);SF.fillPattern(st,'2026-10-05','2026-10-11');
 T('Hogar','La presencia se cuenta aparte del trabajo efectivo',()=>{const S=SF.jorStats(st);return {ok:Math.abs(S.avg-49)<1e-9&&Math.abs(S.avgPres-21)<1e-9,det:`efectivo ${S.avg} h, presencia ${S.avgPres} h`};});
 T('Hogar','Más de 20 h de presencia genera aviso',()=>({ok:!!al(SF.evaluate(st,H),'presencia')}));
 st=mk('A',{rel_inicio:'2010-01-15',fecha_efectos:'2026-10-15',ext_tipo:'despido',sal_real:'1500',sal_pagas:'incluidas',jor_horas:'40'});
 T('Indemnización','Tramos 2012: 25 meses a 45 + 177 meses a 33 = 580,5 días',()=>{const K=SF.calc(st,H);return {ok:K.mesesPre===25&&K.mesesPost===177&&Math.abs(K.indDias-580.5)<1e-6,det:`${K.mesesPre} + ${K.mesesPost} meses → ${K.indDias} días = ${eur(K.ind)}`};});
 st=mk('A',{rel_inicio:'1995-01-01',fecha_efectos:'2026-10-15',ext_tipo:'despido',sal_real:'2000',sal_pagas:'incluidas',jor_horas:'40'});
 T('Indemnización','Si el tramo anterior supera 720 días, se aplica ese tramo como máximo',()=>{const K=SF.calc(st,H);return {ok:Math.abs(K.indDias-772.5)<1e-6,det:K.indDias+' días'};});
 st=SF.buildScen('B',H);SF.st=st;G=SF.genPapeleta(st,H);txt=SF.papToText(G);
 T('Papeleta sin papeles','Invoca art. 36.5 LO 4/2000 y la presunción del art. 8.1 ET',()=>({ok:/36\.5/.test(txt)&&/8\.1 ET/.test(txt)}));
 T('Papeleta sin papeles','Demanda al administrador como posible responsable solidario',()=>({ok:/administrador\/a de la citada mercantil/.test(txt)}));
 T('Papeleta sin papeles','Reclama diferencias hasta el SMI con cifra',()=>({ok:G.K.items.some(i=>/salario mínimo/.test(i.c)&&i.imp>0),det:G.K.items.map(i=>i.c+': '+(i.imp!=null?eur(i.imp):'—')).join(' | ')}));
 T('Papeleta sin papeles','Sin CIF no inventa: deja el hueco marcado',()=>({ok:/⟦CIF⟧/.test(txt)}));
 T('Papeleta sin papeles','No incluye la advertencia de extranjería salvo que el abogado la active',()=>({ok:!/54\.1\.d/.test(txt)}));
 st=SF.buildScen('C',H);SF.st=st;G=SF.genPapeleta(st,H);txt=SF.papToText(G);
 T('Papeleta hogar','Habla de «titular del hogar familiar» y no de empresa',()=>({ok:/titular del hogar familiar/.test(txt)&&!/la mercantil/.test(txt)}));
 T('Papeleta hogar','No calcula indemnización sin la regla que fije el abogado',()=>({ok:G.K.ind==null&&/RD 1620\/2011: fijar días/.test(txt)}));
 T('Papeleta hogar','Embarazo: pide la nulidad (art. 55.5.b ET)',()=>({ok:G.cal==='nulo'&&/NULIDAD/.test(txt)&&/55\.5\.b/.test(txt)}));
 st=mk('B',{ext_tipo:'despido',fecha_com:'?',pap:'?'});R=SF.evaluate(st,H);
 T('«No lo sabe»','Va a información desconocida y a dudas, no a pendientes',()=>({ok:R.desconocidos.some(d=>d.id==='fecha_com')&&!R.incompletos.some(d=>d.id==='fecha_com')&&R.dudas.some(d=>/día en que|en que se lo dijeron|se lo dijeron/.test(d))}));
 st=mk('A',{cli_dom:DIR('Calle','Mayor','1','','','08001','Madrid','Madrid')});R=SF.evaluate(st,H);
 T('Direcciones','Detecta código postal de otra provincia',()=>({ok:R.contra.some(c=>c.id==='cp_cli_dom'),det:(R.contra.find(c=>c.id==='cp_cli_dom')||{}).texto}));
 st=mk('A',{cli_dom:{via:'Calle',calle:'Mayor',num:'1'}});R=SF.evaluate(st,H);
 T('Direcciones','Una dirección sin código postal, localidad y provincia queda pendiente',()=>{const i=R.incompletos.find(x=>x.id==='cli_dom');return {ok:!!i&&/código postal/.test(i.label)&&/provincia/.test(i.label),det:i&&i.label};});
 st=SF.buildScen('B',H);SF.st=st;txt=SF.papToText(SF.genPapeleta(st,H));
 T('Papeleta completa','La dirección sale entera, con código postal y provincia',()=>({ok:/Calle Ficticia, n\.º 8, 1\.º A, 28012 Madrid \(Madrid\)/.test(txt)}));
 T('Papeleta completa','Incluye en qué ocupaba las horas de más y cuántos días',()=>({ok:/horas que excedían su jornada las dedicaba/.test(txt)&&/días registrados/.test(txt)}));
 T('Papeleta completa','Incluye lo que pasó el día del despido y con quién habló',()=>({ok:/Lo ocurrido ese día/.test(txt)&&/le pidió las llaves/.test(txt)&&/escribió por WhatsApp/.test(txt)}));
 T('Papeleta completa','Menciona las pruebas de que dispone',()=>({ok:/dispone, entre otros, de los siguientes medios de prueba/.test(txt)}));
 st=SF.buildScen('C',H);SF.st=st;txt=SF.papToText(SF.genPapeleta(st,H));
 T('Hogar','Interna con pernocta en la papeleta',()=>({ok:/régimen de interna, pernoctando en el domicilio/.test(txt)}));
 T('Hogar','Personas cuidadas: los menores sin nombre, solo con edad',()=>({ok:/Un menor de 7 años/.test(txt)&&!/Lucas|Sofía/.test(txt)&&/Carmen López \(ficticia\) \(madre de la señora\), de 88 años, con dependencia severa/.test(txt)}));
 T('Hogar','Entorno de la casa como posibles testigos',()=>({ok:/acudían con regularidad, entre otras personas: Luis López/.test(txt)}));
 T('Observaciones','No pasan a la papeleta salvo que el abogado lo active',()=>{const a=!/tenía habitación en la casa/.test(txt);st.abg.incObs=true;const b=/Otros hechos relevantes\. Comida y alojamiento: tenía habitación/.test(SF.papToText(SF.genPapeleta(st,H)));return {ok:a&&b};});
 T('Hogar','La pregunta de comida y habitación ya no está en la entrevista',()=>({ok:!SF.QM.hog_aloj}));
 T('Hogar','Ya no se pregunta el número de casas, dormitorios ni baños',()=>({ok:!SF.QM.hog_num&&!SF.QM.hog_dorm&&!SF.QM.hog_banos}));
 T('Hogar','La historia pasa a la papeleta: inicio, cambios, trato y cuidado de la abuela',()=>({ok:/Sobre el inicio de la relación: una prima/.test(txt)&&/A lo largo de la relación, desde enero/.test(txt)&&/En cuanto al trato recibido/.test(txt)&&/solo se calmaba con la trabajadora/.test(txt)}));
 T('Contacto','Pide el correo electrónico y lo incluye en la papeleta',()=>({ok:!!SF.QM.cli_email&&/correo electrónico rosa\.ficticia@example\.com/.test(txt)}));
 T('Entrevista','«Describa lo que pasó el día del despido» sustituye a «¿Quiere contar algo más…?»',()=>({ok:!SF.QM.ext_relato&&SF.QM.ext_dia.t==='Describa lo que pasó el día del despido'}));
 st=SF.buildScen('C',H);SF.st=st;txt=SF.papToText(SF.genPapeleta(st,H));
 T('Hogar','Persona dependiente: grado, Alzheimer, aparatos, medicación y noches',()=>({ok:/grado II de dependencia/.test(txt)&&/Alzheimer/.test(txt)&&/andador/.test(txt)&&/insulina/.test(txt)&&/varias veces cada noche/.test(txt)}));
 T('Hogar','Quién vivía en la casa y a qué se dedicaba',()=>({ok:/En la vivienda residían Elena Martín/.test(txt)&&/ingeniero/.test(txt)}));
 T('Hogar','Visitas con nombre, frecuencia y que la veían trabajar',()=>({ok:/Ana Torres \(ficticia\) \(nieta de Carmen\), una vez al mes/.test(txt)&&/la veían desempeñar su trabajo/.test(txt)}));
 T('Hogar','Llaves, alarma y segunda residencia',()=>({ok:/disponía de llaves de la vivienda y conocía el código de la alarma/.test(txt)&&/Cullera/.test(txt)}));
 T('Hogar','Ni el nombre ni el colegio de los menores salen en la papeleta',()=>({ok:!/Lucas|Sofía|San Juan|Escuela infantil|frutos secos/.test(txt)&&/fútbol/.test(txt)}));
 st=SF.buildScen('A',H);
 T('Hechos declarados','Nada aparece como comprobado sin que el abogado lo marque',()=>({ok:Object.values(st.ans).every(a=>a.estado==='declarado')}));
 return out;};

/* ================= interfaz ================= */
SF.list=[];SF.st=null;SF.step=0;SF.view='entrevista';SF.mode='asesor';SF.lastSync={};
const $=id=>document.getElementById(id);
SF.toast=(m,e)=>{$('toastHost').innerHTML=`<div class="x-toast${e?' err':''}" role="status">${esc(m)}</div>`;clearTimeout(SF._t);SF._t=setTimeout(()=>$('toastHost').innerHTML='',e?5000:2600);};
SF.modal=(titulo,txt,opts)=>{opts=opts||{};$('modalHost').innerHTML=`<div class="x-modal" role="dialog" aria-modal="true" aria-labelledby="mdT"><div><div class="x-row" style="justify-content:space-between"><h2 class="x-h2" id="mdT">${esc(titulo)}</h2><button class="x-btn sm" type="button" id="mdX">Cerrar</button></div>${opts.lead?`<p class="x-lead">${esc(opts.lead)}</p>`:''}<textarea class="x-ta" id="mdTxt" ${opts.edit?'':'readonly'}>${esc(txt)}</textarea><div class="x-row">${opts.edit?`<button class="x-btn pri" type="button" id="mdOk">${esc(opts.ok||'Aceptar')}</button>`:`<button class="x-btn pri" type="button" id="mdCopy">Copiar</button>`}</div></div></div>`;
 $('mdX').onclick=()=>$('modalHost').innerHTML='';
 if($('mdCopy'))$('mdCopy').onclick=()=>SF.copy(txt,$('mdTxt'));
 if($('mdOk'))$('mdOk').onclick=()=>{opts.onOk($('mdTxt').value);};};
SF.copy=(txt,ta)=>{const fb=()=>{if(ta){ta.removeAttribute('readonly');ta.select();}SF.toast('Seleccionado: copie con Ctrl+C o mantenga pulsado');};try{if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(txt).then(()=>SF.toast('Copiado'),fb);else fb();}catch(e){fb();}};
SF.exportar=(txt,fname,titulo)=>SF.modal(titulo,txt,{lead:'Copie el texto y péguelo en un documento. Nombre sugerido: '+fname});

/* --- inicio --- */
function renderInicio(){const L=SF.list;
 $('vInicio').innerHTML=`<header class="x-top"><div><div class="x-brand">Despacho Rafael Serrano · Laboral</div><div class="x-title">¿Qué ficha abrimos?</div><div class="x-sub">Elija según la situación del cliente mientras trabajó. Son nombres de trabajo internos: no deciden la calificación jurídica.</div></div></header>
 <div class="x-pick">${['A','B','C'].map(k=>`<button class="x-opt ${k.toLowerCase()}" type="button" data-new="${k}"><span class="k">${k}</span><span class="t">${SF.TIPOS[k].corto}</span><span class="d">${SF.TIPOS[k].d}</span></button>`).join('')}</div>
 <div class="x-card x-stack" style="margin-top:14px"><h2 class="x-h3">Ejemplos ficticios</h2><div class="x-row">${SF.SCEN.map(s=>`<button class="x-btn sm" type="button" data-demo="${s.id}">${s.id} · ${esc(s.id==='C'?FC.DEMO_NAME:s.id==='B'&&window.FC?FC.DEMO_NAME_B:s.nombre)}</button>`).join('')}</div>${window.FC&&FC.DEMOS_C?`<h3 class="x-h3" style="margin-top:6px">Ficha C · casos tipo de empleada de hogar</h3><div class="x-row">${FC.DEMOS_C.map(x=>`<button class="x-btn sm" type="button" data-demo="${x.id}">${x.id} · Ficha ${esc(x.ficha||'')} · ${esc(x.nombre)}</button>`).join('')}</div>`:''}</div>
 <div class="x-card x-stack" style="margin-top:12px"><h2 class="x-h3">Fichas guardadas en esta sesión</h2>${L.length?`<table class="x-tbl"><thead><tr><th>Ficha</th><th>Cliente</th><th>Tipo</th><th>Pendientes</th><th></th></tr></thead><tbody>${L.map((st,i)=>{const v2=st.v>=2;const R=v2?FC.evaluate(st):SF.evaluate(st);return `<tr><td class="mono">${st.id}</td><td>${esc((v2?st.c.cli.nombre:V(st,'cli_nombre'))||'—')}</td><td>${st.tipo}</td><td>${v2?R.inc.length:R.incompletos.length}${R.alerts.some(a=>a.nivel==='critica')?' · <b style="color:var(--crit)">urgente</b>':''}</td><td><button class="x-btn sm" type="button" data-open="${i}">Abrir</button></td></tr>`;}).join('')}</tbody></table>`:'<p class="x-empty">Ninguna todavía. Se pierden al cerrar la página: use «Copia de seguridad» para guardar una.</p>'}
 <div class="x-row"><button class="x-btn sm" type="button" id="btnImport">Recuperar una copia de seguridad</button></div></div>`;}
SF.open=st=>{if((st.tipo==='C'||(st.tipo==='B'&&st.v>=2))&&window.FC)return FC.open(st);st.cuidados=st.cuidados||[];st.entorno=st.entorno||[];st.obs=st.obs||'';st.jor.tareas=st.jor.tareas||[];st.abg.advPruebas=st.abg.advPruebas!==false;SF.st=st;if(!SF.list.includes(st))SF.list.push(st);SF.step=0;SF.view='entrevista';SF.lastSync={};SF.resetV5();$('vInicio').hidden=true;$('vFicha').hidden=false;render();window.scrollTo(0,0);};
SF.home=()=>{if(SF.view==='v5'){try{collect();}catch(e){}}$('vFicha').hidden=true;$('vInicio').hidden=false;renderInicio();window.scrollTo(0,0);};

/* --- ficha --- */
let R=null;
function evalNow(){R=SF.evaluate(SF.st);return R;}
function renderHead(){const st=SF.st,t=SF.TIPOS[st.tipo];$('fBrand').textContent=`Ficha ${st.tipo} · ${t.corto}`;$('fTitle').textContent=V(st,'cli_nombre')||'Cliente sin nombre';
 $('fSub').innerHTML=`<span>Ficha <b class="mono">${st.id}</b></span><span>${t.Emp.replace('La ','')}: <b>${esc(V(st,'emp_nombre')||V(st,'aut_nombre')||SF.persWith(st,'dueno').map(p=>p.nombre).join(', ')||'—')}</b></span><span>Pendientes <b>${R.incompletos.length}</b></span><button class="x-link" type="button" id="btnTipo">Cambiar de ficha</button>`;}
function renderBand(){const b=$('band');const o={critica:0,alta:1,media:2};const al=R.alerts.slice().sort((x,y)=>o[x.nivel]-o[y.nivel]);const crit=al.some(a=>a.nivel==='critica'),alta=al.some(a=>a.nivel==='alta');
 b.className='x-band'+(crit?' crit':alta?' alta':'');const show=SF.bandAll?al:al.filter(a=>a.nivel!=='media').slice(0,4);
 b.innerHTML=`<div class="x-band-h"><span>Plazos y avisos para el abogado</span><span class="mono">${al.filter(a=>a.nivel!=='media').length} urgentes · ${al.filter(a=>a.nivel==='media').length} avisos</span></div>${al.length?`<ul>${show.map(a=>`<li class="x-al"><span class="x-lvl lvl-${a.nivel}">${a.nivel==='critica'?'Crítica':a.nivel==='alta'?'Alta':'Aviso'}</span><div><b>${esc(a.titulo)}</b><span class="d">${esc(a.detalle)}</span></div></li>`).join('')}</ul>${al.length>show.length||SF.bandAll?`<div class="x-band-more"><button class="x-link" type="button" id="bandMore">${SF.bandAll?'Ver solo urgentes':'Ver todos ('+al.length+')'}</button></div>`:''}`:'<div class="x-band-more x-lead">Sin avisos con los datos actuales. Esto no sustituye la revisión del abogado.</div>'}`;}
function renderViews(){const V5=SF.mode==='abogado';const vs=[['entrevista','Ficha'],...(V5?[['v5','Ficha original v5 (abogado)']]:[]),['tests','Pruebas automáticas'],['inv','Qué ha cambiado']];
 $('views').innerHTML=vs.map(([k,l])=>`<button class="x-view" role="tab" type="button" data-view="${k}" aria-selected="${SF.view===k}">${l}</button>`).join('');
 $('pEntrevista').hidden=SF.view!=='entrevista';$('pV5').hidden=SF.view!=='v5';$('pTests').hidden=SF.view!=='tests';$('pInv').hidden=SF.view!=='inv';}
function renderSteps(){const st=SF.st;const cnt=i=>R.incompletos.filter(x=>x.s===i).length;
 $('steps').innerHTML=STEPS.map((s,i)=>{const lbl=i===1?SF.TIPOS[st.tipo].paso2:s;const c=i<6?cnt(i):0;return `<button type="button" class="x-step${i<6&&!c&&i!==SF.step?' done':''}${i===7?' paper':''}" data-step="${i}" ${i===SF.step?'aria-current="step"':''}><span class="n">${i+1}</span>${esc(lbl)}${c?`<span class="c">${c}</span>`:''}</button>`;}).join('');}

function dirHTML(q,a){const d=a.ns||!a.v||typeof a.v!=='object'?{}:a.v;const dis=a.ns?'disabled':'';const f=(k,l,sm,inner)=>`<div class="x-fld${sm?' sm':''}" style="grid-column:span ${sm?1:sm===0?6:2}"><label for="d_${q.id}_${k}">${l}</label>${inner||`<input class="x-in x-dir" id="d_${q.id}_${k}" data-dq="${q.id}" data-dk="${k}" value="${esc(d[k]||'')}" ${dis}>`}</div>`;
 const cpP=SF.provDeCP(d.cp||'');const bad=cpP&&d.prov&&cpP!==d.prov;
 return `<div class="x-addr">${f('via','Tipo de vía',false,`<select class="x-sel x-dir" id="d_${q.id}_via" data-dq="${q.id}" data-dk="via" ${dis}><option value="">—</option>${SF.VIAS.map(x=>`<option ${d.via===x?'selected':''}>${x}</option>`).join('')}</select>`)}<div class="x-fld" style="grid-column:span 4"><label for="d_${q.id}_calle">Nombre de la vía</label><input class="x-in x-dir" id="d_${q.id}_calle" data-dq="${q.id}" data-dk="calle" value="${esc(d.calle||'')}" ${dis}></div>${f('num','Número',1)}${f('bloque','Portal o bloque',1)}${f('esc','Escalera',1)}${f('piso','Piso',1)}${f('puerta','Puerta',1)}${f('cp','Código postal',1,`<input class="x-in x-dir" id="d_${q.id}_cp" data-dq="${q.id}" data-dk="cp" inputmode="numeric" maxlength="5" value="${esc(d.cp||'')}" ${dis}>`)}<div class="x-fld" style="grid-column:span 3"><label for="d_${q.id}_loc">Localidad</label><input class="x-in x-dir" id="d_${q.id}_loc" data-dq="${q.id}" data-dk="loc" value="${esc(d.loc||'')}" ${dis}></div><div class="x-fld" style="grid-column:span 3"><label for="d_${q.id}_prov">Provincia</label><select class="x-sel x-dir" id="d_${q.id}_prov" data-dq="${q.id}" data-dk="prov" ${dis}><option value="">—</option>${SF.PROV.map(x=>`<option ${d.prov===x?'selected':''}>${x}</option>`).join('')}</select></div><div class="x-fld" style="grid-column:1/-1"><label for="d_${q.id}_ind">Indicaciones para encontrarla (opcional)</label><input class="x-in x-dir" id="d_${q.id}_ind" data-dq="${q.id}" data-dk="ind" value="${esc(d.ind||'')}" placeholder="Timbre, nombre en el buzón, local dentro de un centro comercial…" ${dis}></div></div>${bad?`<div class="x-flag">El código postal ${esc(d.cp)} es de ${esc(cpP)}, no de ${esc(d.prov)}.</div>`:''}${q.ns?`<div class="x-opts"><button type="button" class="x-o ns" data-q="${q.id}" data-ns="1" aria-pressed="${a.ns?'true':'false'}">No lo sabe</button></div>`:''}`;}
function qHTML(q){const st=SF.st,a=st.ans[q.id]||{};const miss=q.req&&V(st,q.id)===undefined&&!a.ns;
 const nsb=q.ns?`<button type="button" class="x-o ns" data-q="${q.id}" data-ns="1" aria-pressed="${a.ns?'true':'false'}">No lo sabe</button>`:'';let inp;
 if(q.ty==='dir'){inp=dirHTML(q,a);}else if(q.ty==='op'||q.ty==='multi'){inp=`<div class="x-opts" role="group" aria-label="${esc(q.t)}">${SF.opts(st,q).map(([v,l])=>{const on=!a.ns&&(Array.isArray(a.v)?a.v.includes(v):a.v===v);return `<button type="button" class="x-o" data-q="${q.id}" data-v="${v}" aria-pressed="${on}">${esc(l)}</button>`;}).join('')}${nsb}</div>`;}
 else{const val=a.ns?'':(a.v||'');if(q.ty==='area')inp=`<div class="x-inrow"><textarea class="x-in" id="q_${q.id}" data-q="${q.id}" ${a.ns?'disabled':''}>${esc(val)}</textarea>${nsb}</div>`;
  else{const ty=q.ty==='date'?'date':q.ty==='num'?'number':'text';inp=`<div class="x-inrow"><input class="x-in" id="q_${q.id}" data-q="${q.id}" type="${ty}" ${q.ty==='num'?'min="0" step="any" inputmode="decimal"':''} value="${esc(val)}" ${a.ns?'disabled':''}>${nsb}${q.aprox?`<label class="x-aprox"><input type="checkbox" data-aprox="${q.id}" ${a.aprox?'checked':''}> Fecha aproximada</label>`:''}</div>`;}}
 return `<div class="x-q${q.req?' req':''}${miss?' miss':''}" id="qq_${q.id}"><label class="x-qt" ${q.ty==='op'||q.ty==='multi'||q.ty==='dir'?'':'for="q_'+q.id+'"'}>${esc(q.t)}</label>${q.h?`<div class="x-help">${esc(q.h)}</div>`:''}${inp}<details class="x-nota" ${a.nota?'open':''}><summary>${a.nota?'Explicación':'Añadir explicación libre'}</summary><textarea class="x-ta" data-nota="${q.id}" placeholder="Lo que cuente el cliente con sus palabras">${esc(a.nota||'')}</textarea></details></div>`;}
function qs(step,filter){const st=SF.st;return SF.Q.filter(q=>q.s===step&&SF.vis(st,q)&&(!filter||filter(q))).map(qHTML).join('');}

function personasHTML(){const st=SF.st,C=st.tipo==='C';return `<div class="x-sec x-stack"><h2>${C?'Personas de la casa':'Personas de la empresa'}</h2><p class="x-help">Añada a todas las personas que tuvieron que ver con el trabajo y marque qué hacía cada una. Ejemplo: ${C?'«Elena, la señora de la casa: me contrató y me pagaba; Javier, su marido: vivía en la casa». Apunte a todos los adultos que vivían allí, aunque no mandaran':'«Antonio, el dueño: me contrató y me pagaba; Luisa, la encargada: me daba órdenes»'}.</p>
 <div class="x-ppl">${st.personas.map(p=>`<div class="x-p" data-pid="${p.id}"><div class="x-fld"><label for="pn_${p.id}">Nombre</label><input class="x-in" id="pn_${p.id}" data-pk="nombre" value="${esc(p.nombre)}"></div><div class="x-fld"><label for="pr_${p.id}">Quién es</label><input class="x-in" id="pr_${p.id}" data-pk="relacion" value="${esc(p.relacion)}" placeholder="${C?'señora de la casa, hijo…':'dueño, encargado…'}"></div><div class="x-fld"><label for="pt_${p.id}">Teléfono</label><input class="x-in" id="pt_${p.id}" data-pk="tel" value="${esc(p.tel)}"></div><div class="x-fld"><label for="pm_${p.id}">Correo electrónico</label><input class="x-in" id="pm_${p.id}" type="email" data-pk="email" value="${esc(p.email||'')}"></div><div class="x-fld"><label for="pd_${p.id}">DNI/NIE (si lo sabe)</label><input class="x-in" id="pd_${p.id}" data-pk="dni" value="${esc(p.dni)}"></div>${C?`<div class="x-fld"><label for="pe_${p.id}">Edad aproximada</label><input class="x-in" id="pe_${p.id}" data-pk="edad" value="${esc(p.edad||'')}"></div><div class="x-fld" style="grid-column:span 2"><label for="pw_${p.id}">A qué se dedica y dónde trabaja</label><input class="x-in" id="pw_${p.id}" data-pk="trabajo" value="${esc(p.trabajo||'')}" placeholder="abogada en un despacho del centro; trabaja fuera de lunes a viernes"></div>`:''}<div class="roles">${SF.ROLES.map(([r,l])=>`<button type="button" class="x-chip" data-role="${r}" aria-pressed="${p.roles.includes(r)}">${C&&r==='dueno'?'Es titular de la casa':esc(l)}</button>`).join('')}${C?`<button type="button" class="x-chip" data-role="vive" aria-pressed="${p.roles.includes('vive')}">Vivía en la casa</button>`:''}<button type="button" class="x-btn sm" data-pdel="1" style="margin-left:auto">Quitar</button></div></div>`).join('')||'<p class="x-empty">Todavía no hay nadie.</p>'}</div>
 <div class="x-row"><button class="x-btn" type="button" id="pAdd">Añadir persona</button></div></div>`;}
function cuidadosHTML(){const st=SF.st;const sel=(c,k,opts)=>`<select class="x-sel" id="c${k}_${c.id}" data-ck="${k}"><option value="">—</option>${opts.map(([v,l])=>`<option value="${v}" ${c[k]===v?'selected':''}>${l}</option>`).join('')}</select>`;const inp=(c,k,l,ph,full)=>`<div class="x-fld"${full?' style="grid-column:1/-1"':''}><label for="c${k}_${c.id}">${l}</label><input class="x-in" id="c${k}_${c.id}" data-ck="${k}" value="${esc(c[k]||'')}" placeholder="${esc(ph||'')}"></div>`;
 return `<div class="x-sec x-stack"><h2>Personas que cuidaba</h2><p class="x-help">Rellene una ficha por cada persona a la que cuidaba: niños, mayores o enfermos. Cuantos más detalles, mejor: demuestran que la trabajadora conocía la casa por dentro y lo que hacía cada día. Los nombres de los menores y su colegio se quedan en la ficha; en la papeleta solo aparece su edad.</p>
 <div class="x-ppl">${(st.cuidados||[]).map(c=>{const m=SF.esMenor(c);return `<div class="x-p" data-cid="${c.id}">
  ${inp(c,'nombre','Nombre','')}${inp(c,'parentesco','Quién es en la familia','hijo, hija, madre de la señora…')}<div class="x-fld"><label for="cedad_${c.id}">Edad</label><input class="x-in" id="cedad_${c.id}" type="number" min="0" max="120" data-ck="edad" value="${esc(c.edad)}"></div><div class="x-fld" style="grid-column:span 2"><label for="cautonomia_${c.id}">Nivel de dependencia en el día a día</label>${sel(c,'autonomia',[['independiente','Independiente: se valía sola'],['leve','Leve: ayuda en algunas cosas'],['moderada','Moderada: ayuda varias veces al día'],['severa','Severa: ayuda para casi todo'],['total','Total: no podía hacer nada sola']])}</div>
  ${m?`${inp(c,'colegio','Colegio o guardería y horario (solo para la ficha)','Colegio …, de 9 a 16:30')}${inp(c,'extra','Actividades a las que le llevaba y horarios','fútbol martes y jueves de 17:30 a 18:30')}${inp(c,'saludN','Alergias, comidas especiales u otras necesidades','')}`:
  `<div class="x-fld"><label for="cgrado_${c.id}">Grado de dependencia reconocido</label>${sel(c,'grado',[['no','No tiene'],['tramite','En trámite'],['I','Grado I'],['II','Grado II'],['III','Grado III'],['ns','No lo sabe']])}</div>
  <div class="roles"><span class="x-lead" style="width:100%">Enfermedades o limitaciones</span>${SF.DIAG.map(([k,l])=>`<button type="button" class="x-chip" data-cdg="${k}" aria-pressed="${(c.diag||[]).includes(k)}">${l}</button>`).join('')}</div>
  ${inp(c,'diagOtro','Otra enfermedad o detalle','')}${inp(c,'ayudas','Aparatos que usaba','andador, silla, grúa, cama articulada, oxígeno')}${inp(c,'medicacion','Medicación que le daba y a qué horas','pastillas a las 9, 14 y 21 h')}<div class="x-fld"><label for="cnoche_${c.id}">¿La necesitaba por la noche?</label>${sel(c,'noche',[['no','No'],['alguna','Alguna noche'],['varias','Varias veces cada noche'],['toda','Toda la noche']])}</div>${inp(c,'centro','¿Iba a centro de día o tenía otra cuidadora? Días y horario','')}${inp(c,'sanitarios','Médicos, enfermeras o fisioterapeutas que la atendían','')}`}
  <div class="roles"><span class="x-lead" style="width:100%">¿Qué hacía con esta persona?</span>${SF.CUID.map(([k,l])=>`<button type="button" class="x-chip" data-ccu="${k}" aria-pressed="${(c.cu||[]).includes(k)}">${l}</button>`).join('')}</div>
  ${inp(c,'rutina','Su horario del día: a qué hora se levantaba, comía, dormía la siesta, se acostaba','',1)}<div class="x-fld" style="grid-column:1/-1"><label for="chist_${c.id}">Cuente cómo era cuidar a esta persona</label><textarea class="x-in" id="chist_${c.id}" data-ck="hist" style="min-height:90px;resize:vertical" placeholder="Cómo era un día con ella, lo más difícil, qué le pedía, cómo estaba de salud, si alguien más la cuidaba…">${esc(c.hist||'')}</textarea>${m?'<span class="x-help">De los menores esto queda solo en la ficha.</span>':''}</div>${inp(c,'obs','Otros detalles','',1)}
  <div class="roles"><button type="button" class="x-btn sm" data-cdel="1" style="margin-left:auto">Quitar</button></div></div>`;}).join('')||'<p class="x-empty">Todavía no hay nadie.</p>'}</div>
 <div class="x-row"><button class="x-btn" type="button" id="cAdd">Añadir persona cuidada</button></div></div>`;}
function entornoHTML(){const st=SF.st;const sel=(x,k,opts)=>`<select class="x-sel" id="e${k}_${x.id}" data-ek="${k}"><option value="">—</option>${opts.map(([v,l])=>`<option value="${v}" ${x[k]===v?'selected':''}>${l}</option>`).join('')}</select>`;const inp=(x,k,l,ph,w)=>`<div class="x-fld"${w?` style="grid-column:span ${w}"`:''}><label for="e${k}_${x.id}">${l}</label><input class="x-in" id="e${k}_${x.id}" data-ek="${k}" value="${esc(x[k]||'')}" placeholder="${esc(ph||'')}"></div>`;
 return `<div class="x-sec x-stack"><h2>Visitas y otras personas que iban a la casa</h2><p class="x-help">Hijos y nietos que venían a ver a la abuela, amigos de la familia, otras empleadas o cuidadoras, médicos, enfermeras, fisioterapeutas, el portero, vecinos… Apunte a todos con su nombre: cuantos más, más difícil es negar que trabajaba allí.</p>
 <div class="x-ppl">${(st.entorno||[]).map(x=>`<div class="x-p" data-eid="${x.id}">${inp(x,'nombre','Nombre','')}${inp(x,'relacion','Quién es','hijo de la abuela, portero…')}${inp(x,'tel','Teléfono o correo (si lo sabe)','')}<div class="x-fld"><label for="efrec_${x.id}">¿Cada cuánto iba?</label>${sel(x,'frec',[['diaria','Todos los días'],['varias','Varias veces por semana'],['semanal','Una vez por semana'],['quincenal','Cada quince días'],['mensual','Una vez al mes'],['ocasional','De vez en cuando']])}</div>${inp(x,'dias','Qué días y a qué hora','los domingos de 11 a 14 h',2)}${inp(x,'que','Qué hacía en la casa','visitaba a su madre y comía con la familia',2)}<div class="x-fld"><label for="evio_${x.id}">¿La veía trabajar?</label>${sel(x,'vio',[['si','Sí'],['no','No']])}</div><div class="x-fld"><label for="etestigo_${x.id}">¿Podría declarar?</label>${sel(x,'testigo',[['si','Sí, probablemente'],['no','No querrá'],['ns','No lo sabe']])}</div><div class="roles"><button type="button" class="x-btn sm" data-edel="1" style="margin-left:auto">Quitar</button></div></div>`).join('')||'<p class="x-empty">Nadie apuntado.</p>'}</div>
 <div class="x-row"><button class="x-btn" type="button" id="eAdd">Añadir persona</button></div></div>`;}
function tareasHTML(){const st=SF.st,T=st.jor.tareas||[];return `<div class="x-card x-stack"><h3 class="x-h3">En qué ocupaba cada hora</h3><p class="x-help">Apunte las tareas con su horario. Marque «Horas de más» en las que hacía fuera de su horario normal, por ejemplo «cerrar la caja y limpiar la cocina, de 23 a 00 h» o «atender a la abuela por la noche». Después marque en la tabla de días cuándo las hizo. Todo pasa a la papeleta.</p>
 <div class="x-tw"><table class="x-t"><thead><tr><th>Tarea</th><th>Desde</th><th>Hasta</th><th>Horas de más</th><th></th></tr></thead><tbody>${T.map(x=>`<tr data-tid="${x.id}"><td class="wrap"><input type="text" data-tk2="t" value="${esc(x.t)}" style="width:100%;min-width:220px" aria-label="Tarea"></td><td><input type="time" data-tk2="desde" value="${x.desde||''}" aria-label="Desde"></td><td><input type="time" data-tk2="hasta" value="${x.hasta||''}" aria-label="Hasta"></td><td><input type="checkbox" data-tk2="extra" ${x.extra?'checked':''} aria-label="Horas de más"></td><td><button class="x-btn sm" type="button" data-tdel="1" aria-label="Quitar tarea">×</button></td></tr>`).join('')||'<tr><td colspan="5" class="x-empty" style="white-space:normal">Sin tareas todavía.</td></tr>'}</tbody></table></div>
 <div class="x-row"><button class="x-btn" type="button" id="tAdd">Añadir tarea</button></div></div>`;}
const tkChips=(st,list,attr)=>{const E=(st.jor.tareas||[]).filter(x=>x.extra&&x.t);return E.map(x=>`<button type="button" class="x-chip" ${attr}="${x.id}" aria-pressed="${(list||[]).includes(x.id)}" style="padding:2px 8px;font-size:11.5px" title="${esc(x.t)}">${esc(x.t.length>24?x.t.slice(0,23)+'…':x.t)}</button>`).join(' ');};
function rolesHTML(){const st=SF.st;return `<div class="x-sec x-stack"><h2>Quién mandaba</h2><p class="x-help">Toque el nombre de cada persona que corresponda. Si falta alguien, añádalo en el paso anterior.</p>${SF.ROLE_Q.map(([r,t])=>`<div class="x-q req${!SF.persWith(st,r).length&&!st.rolesNS[r]?' miss':''}"><span class="x-qt">${t}</span><div class="x-opts">${st.personas.filter(p=>p.nombre.trim()).map(p=>`<button type="button" class="x-o" data-rolep="${p.id}" data-r="${r}" aria-pressed="${p.roles.includes(r)&&!st.rolesNS[r]}">${esc(p.nombre)}</button>`).join('')}<button type="button" class="x-o ns" data-rolens="${r}" aria-pressed="${!!st.rolesNS[r]}">No lo sabe</button></div></div>`).join('')}</div>`;}

function jorHTML(){const st=SF.st,C=st.tipo==='C',J=SF.jorStats(st);const EXT=(st.jor.tareas||[]).some(x=>x.extra&&x.t);const fu=[['habitual','Horario habitual'],['memoria','Lo recuerda'],['cuadrante','Cuadrante'],['fichaje','Fichaje'],['mensajes','Mensajes'],['otra','Otra']];
 const rows=[];let wk=null;
 st.jor.dias.forEach(r=>{const k=r.f?weekKey(r.f):'';if(k!==wk&&wk!==null){const w=J.weeks.find(x=>x.k===wk);if(w)rows.push(weekRow(w,C,EXT));}wk=k;rows.push(dayRow(r,C,fu,EXT));});
 if(wk){const w=J.weeks.find(x=>x.k===wk);if(w)rows.push(weekRow(w,C,EXT));}
 return `<div class="x-sec x-stack"><h2>Registro de jornada día a día</h2>
 <p class="x-help">Primero apunte el horario habitual de cada día de la semana. Después rellene un periodo con ese horario y corrija los días que fueron distintos. Las horas se calculan solas, incluidos los turnos que pasan de medianoche. Más de 9 horas en un día se marca para revisar, pero no cuenta automáticamente como hora extra.</p>
${tareasHTML()}
 <div class="x-card x-stack"><h3 class="x-h3">Horario habitual</h3><div class="x-tw"><table class="x-t"><thead><tr><th>Día</th><th>Entrada</th><th>Salida</th><th>Descansos (min)</th>${C?'<th>Presencia (h)</th>':''}<th>Horas</th>${EXT?'<th>Horas de más en…</th>':''}</tr></thead><tbody>${[1,2,3,4,5,6,7].map(d=>{const p=st.jor.patron[d],c=SF.rowCalc(p);return `<tr data-pd="${d}"><td>${DOWN[d]}</td><td><input type="time" data-pf="e" value="${p.e}" aria-label="Entrada ${DOWN[d]}"></td><td><input type="time" data-pf="s" value="${p.s}" aria-label="Salida ${DOWN[d]}"></td><td><input type="number" min="0" step="5" data-pf="d" value="${p.d}" aria-label="Descanso ${DOWN[d]}"></td>${C?`<td><input type="number" min="0" step="0.5" data-pf="p" value="${p.p}" aria-label="Presencia ${DOWN[d]}"></td>`:''}<td class="calc">${c?num1(c.ef):'—'}</td>${EXT?`<td class="wrap">${tkChips(st,p.tk,'data-ptk')}</td>`:''}</tr>`;}).join('')}</tbody></table></div>
 <div class="x-row"><div class="x-fld"><label for="jDesde">Desde</label><input class="x-in" type="date" id="jDesde" value="${st.jor.desde}"></div><div class="x-fld"><label for="jHasta">Hasta</label><input class="x-in" type="date" id="jHasta" value="${st.jor.hasta}"></div><button class="x-btn pri" type="button" id="jFill" style="align-self:flex-end">Rellenar con el horario habitual</button><button class="x-btn" type="button" id="jAdd" style="align-self:flex-end">Añadir un día suelto</button>${st.jor.dias.length?`<button class="x-btn" type="button" id="jClear" style="align-self:flex-end">Vaciar la tabla</button>`:''}</div></div>
 <div class="x-nums"><div class="x-num"><div class="n">${J.avg!=null?num1(J.avg):'—'}</div><div class="l">Horas efectivas por semana (media)</div></div><div class="x-num ${J.avgExceso?'warn':''}"><div class="n">${J.avgExceso!=null?num1(J.avgExceso):'—'}</div><div class="l">Por encima de ${C?'40':J.ref} h semanales</div></div>${C?`<div class="x-num ${J.avgPres>20?'warn':''}"><div class="n">${J.avgPres!=null?num1(J.avgPres):'—'}</div><div class="l">Presencia por semana (aparte)</div></div>`:`<div class="x-num ${J.largos?'warn':''}"><div class="n">${J.largos}</div><div class="l">Días de más de 9 h (revisar)</div></div>`}<div class="x-num"><div class="n">${num1(J.noct)}</div><div class="l">Horas nocturnas (22 a 6 h)</div></div></div>
 <div class="x-tw"><table class="x-t" id="jTable"><thead><tr><th>Fecha</th><th>Día</th><th>Entrada</th><th>Salida</th><th>Descansos (min)</th>${C?'<th>Presencia (h)</th>':''}<th>Horas efectivas</th><th>Revisar</th>${EXT?'<th>Horas de más en…</th>':''}<th>Observaciones</th><th>Fuente</th><th></th></tr></thead><tbody>${rows.join('')||`<tr><td colspan="${(C?11:10)+(EXT?1:0)}" class="x-empty" style="white-space:normal">Sin días todavía. Rellene el horario habitual y pulse «Rellenar».</td></tr>`}</tbody></table></div></div>`;}
function dayRow(r,C,fu,EXT){const c=SF.rowCalc(r);return `<tr data-jr="${r.id}"><td><input type="date" data-jf="f" value="${r.f}" aria-label="Fecha"></td><td>${r.f?DOWN[dow(r.f)]:''}</td><td><input type="time" data-jf="e" value="${r.e}" aria-label="Entrada"></td><td><input type="time" data-jf="s" value="${r.s}" aria-label="Salida"></td><td><input type="number" min="0" step="5" data-jf="d" value="${r.d}" aria-label="Descansos"></td>${C?`<td><input type="number" min="0" step="0.5" data-jf="p" value="${r.p}" aria-label="Presencia"></td>`:''}<td class="calc">${c?num1(c.ef)+(c.cruza?' ↷':''):'—'}</td><td class="x-flag">${c&&c.ef>9?'Más de 9 h':''}</td>${EXT?`<td class="wrap">${tkChips(SF.st,r.tk,'data-rtk')}</td>`:''}<td><input type="text" data-jf="obs" value="${esc(r.obs)}" aria-label="Observaciones" style="width:150px"></td><td><select data-jf="fuente" aria-label="Fuente">${fu.map(([k,l])=>`<option value="${k}" ${r.fuente===k?'selected':''}>${l}</option>`).join('')}</select></td><td><button class="x-btn sm" type="button" data-jdel="1" aria-label="Quitar día">×</button></td></tr>`;}
function weekRow(w,C,EXT){return `<tr class="week"><td colspan="${C?6:5}">Semana del ${SF.fmt(w.k)} · ${w.n} días</td><td class="calc">${num1(w.ef)}</td><td colspan="${EXT?5:4}">${w.exceso?`<span class="x-flag">${num1(w.exceso)} h por encima de ${C?40:SF.st.jor.ref}</span>`:''}${C&&w.pres?` · presencia ${num1(w.pres)} h`:''}</td></tr>`;}

function pruebasHTML(){const st=SF.st;return `<div class="x-sec x-stack"><h2>Lo que hay que reunir</h2><p class="x-help">Esta lista sale de lo que ha contado el cliente. Marque qué tiene ya y qué conseguirá. ${st.tipo==='B'?'Sin contrato ni alta, estas pruebas son las que demuestran que trabajaba allí.':''}</p>
 <div class="x-card">${R.pruebas.map(p=>{const s=st.pruebas[p.key]||{estado:'pendiente',nota:''};return `<div class="x-pr" data-pr="${p.key}"><div><b>${esc(p.t)}</b><div class="why">${esc(p.por)}</div><input class="x-in" style="margin-top:6px" data-prn="1" value="${esc(s.nota)}" placeholder="Nota: cuándo lo traerá, dónde está…" aria-label="Nota sobre ${esc(p.t)}"></div><div class="st" role="group" aria-label="Estado">${SF.PR_EST.map(([k,l])=>`<button type="button" class="x-o" data-pre="${k}" aria-pressed="${s.estado===k}" style="padding:4px 9px;font-size:12.5px">${l}</button>`).join('')}</div></div>`;}).join('')}</div></div>`;}

function revisionHTML(){const st=SF.st,K=R.K,C=st.tipo==='C';const ab=SF.mode==='abogado';
 const grp=(t,ids)=>{const rows=ids.map(id=>SF.QM[id]).filter(q=>q&&SF.vis(st,q)&&(V(st,q.id)!==undefined));return rows.length?`<div class="x-card x-stack"><h3 class="x-h3">${t}</h3><table class="x-tbl"><tbody>${rows.map(q=>{const a=st.ans[q.id];const cx=R.contra.some(c=>c.qids.includes(q.id));const e=cx?'contradictorio':a.estado;return `<tr><td style="width:38%;color:var(--muted)">${esc(q.c)}</td><td>${esc(SF.show(st,q))}${a.nota?`<div class="x-help" style="margin-top:3px">${esc(a.nota)}</div>`:''}</td><td style="width:1%">${ab&&!cx?`<select class="x-sel" data-est="${q.id}" style="width:auto;font-size:12px;padding:2px 4px" aria-label="Estado de ${esc(q.c)}"><option value="declarado" ${e==='declarado'?'selected':''}>Declarado</option><option value="comprobado" ${e==='comprobado'?'selected':''}>Comprobado con documento</option><option value="pendiente" ${e==='pendiente'?'selected':''}>Pendiente de comprobar</option></select>`:`<span class="x-tag e-${e}">${{declarado:'Declarado',comprobado:'Comprobado',pendiente:'Por comprobar',contradictorio:'Contradictorio'}[e]}</span>`}</td></tr>`;}).join('')}</tbody></table></div>`:'';};
 const prs=R.pruebas.map(p=>({p,s:(st.pruebas[p.key]||{}).estado||'pendiente'}));
 return `<div class="x-stack">
 <div class="x-card x-stack"><h3 class="x-h3">Observaciones generales</h3><p class="x-help">Lo que no tiene casilla propia: si le daban comida o habitación y si se lo descontaban, salud, situación familiar, lo que contó el cliente y no encaja en otra pregunta. Use el guion si le ayuda. El abogado decide si pasa a la papeleta.</p><textarea class="x-ta" id="obsTxt" data-obs="1" style="min-height:140px" aria-label="Observaciones generales">${esc(st.obs||'')}</textarea><div class="x-row"><button class="x-btn sm" type="button" id="obsTpl">Insertar guion</button></div></div>
 <div class="x-2">
  <div class="x-card x-stack"><h3 class="x-h3">Lo que falta</h3>${R.incompletos.length?`<ul class="x-mini">${R.incompletos.map(i=>`<li class="w"><button class="x-link" type="button" data-goto="${i.s}" data-q="${i.id}">${esc(i.label)}</button> <span class="x-lead">· paso ${i.s+1}</span></li>`).join('')}</ul>`:'<p class="x-empty">Nada obligatorio pendiente.</p>'}${R.desconocidos.length?`<h3 class="x-h3">No lo sabe</h3><ul class="x-mini">${R.desconocidos.map(d=>`<li>${esc(d.label)}</li>`).join('')}</ul>`:''}</div>
  <div class="x-card x-stack"><h3 class="x-h3">Contradicciones</h3>${R.contra.length?`<ul class="x-mini">${R.contra.map(c=>`<li class="c"><b>${esc(c.titulo)}</b><br>${esc(c.texto)}</li>`).join('')}</ul>`:'<p class="x-empty">No se detectan.</p>'}</div>
 </div>
 <div class="x-card x-stack"><h3 class="x-h3">Cifras que irán a la papeleta</h3><dl class="x-dl"><dt>Antigüedad</dt><dd>${K.inicio?SF.fmt(K.inicio):'—'} → ${K.fin?SF.fmt(K.fin):'—'}${K.antigDias?` (${K.antigDias} días)`:''}</dd><dt>Jornada</dt><dd>${K.horas?num1(K.horas)+' h/semana ('+(K.horasFuente==='registro'?'según el registro':'declaradas')+')':'—'}</dd><dt>Salario regulador</dt><dd>${K.reg?eur(K.reg)+' / mes · '+eur(K.diario)+' / día':'—'}${K.regPorSMI?' · se toma el mínimo legal (SMI)':''}</dd><dt>Indemnización estimada</dt><dd>${K.ind!=null?eur(K.ind)+' ('+num1(K.indDias)+' días)':(C?'La fija el abogado (RD 1620/2011)':'—')}</dd>${K.items.map(i=>`<dt>${esc(i.c)}</dt><dd>${i.imp!=null?eur(i.imp):'Importe por fijar'}${i.est?' · estimación':''}</dd>`).join('')}</dl></div>
 ${grp('Cliente',['cli_nombre','cli_doc','cli_docnum','cli_nac','cli_tel','cli_email','cli_dom','cli_permiso','cli_rep'])}
 ${grp(C?'Empleador o empleadora':'Empresa o empleador',['emp_tipo','emp_nombre','emp_cif','aut_nombre','aut_dni','emp_dom','emp_centro','emp_estado','hog_dir','hog_num'])}
 ${grp('Otros detalles de la casa',['hog_llaves','hog_alarma','hog_segunda','hog_segunda_txt','hog_mascotas'])}
 ${grp('Relación laboral y funciones',['rel_inicio','hog_interna','hog_pernocta','rel_contrato','rel_contrato_fecha','rel_alta','rel_puesto','rel_trabajo','hog_tareas','rel_como','rel_dia','hog_contexto','hist_cambios','hist_trato','rel_ultimo'])}
 ${C&&((st.cuidados||[]).length||(st.entorno||[]).length)?`<div class="x-card x-stack"><h3 class="x-h3">Personas que cuidaba y entorno</h3>${(st.cuidados||[]).map(c=>`<div>• <b>${esc(c.nombre||'—')}</b>${c.parentesco?' ('+esc(c.parentesco)+')':''}, ${c.edad!==''?esc(c.edad)+' años':'edad sin indicar'}${c.autonomia?', '+SF.AUT[c.autonomia]:''}${c.grado&&SF.GRADO[c.grado]?', '+SF.GRADO[c.grado]:''}${(c.diag||[]).length?' · '+c.diag.map(k=>SF.DIAGP[k]).join(', '):''}${(c.cu||[]).length?' · cuidados: '+c.cu.map(k=>SF.CUID.find(x=>x[0]===k)[1].toLowerCase()).join(', '):''}${c.colegio?' · colegio: '+esc(c.colegio):''}${c.obs?' · '+esc(c.obs):''}</div>`).join('')}${(st.entorno||[]).map(x=>`<div>• ${esc(x.nombre)}${x.relacion?', '+esc(x.relacion):''}${x.frec?', '+SF.FREC[x.frec]:''}${x.que?' — '+esc(x.que):''}${x.vio==='si'?' · la veía trabajar':''}${x.testigo==='si'?' · podría declarar':''}</div>`).join('')}</div>`:''}
 ${grp('Jornada y salario',['jor_horas','jor_noche','jor_festivos','jor_fichaje','hog_presencia','sal_real','sal_pactado','sal_cobro','sal_pagas','sal_vac','deb','deb_conc','deb_desde','deb_importe'])}
 ${grp('Extinción declarada',['ext_tipo','ext_quien','ext_forma','ext_dicho','ext_literal_txt','fecha_com','fecha_efectos','ext_dia','ext_hablo','ext_sit','ext_firmo','ext_firmo_nc'])}
 ${grp('Conciliación y actuaciones previas',['pap','pap_fecha','acto','acto_fecha','acto_res','abog','abog_que','dem','dem_fecha'])}
 <div class="x-2"><div class="x-card x-stack"><h3 class="x-h3">Pruebas que ya tiene</h3>${prs.filter(x=>x.s==='tiene').map(x=>`<div>• ${esc(x.p.t)}</div>`).join('')||'<p class="x-empty">Ninguna marcada.</p>'}</div><div class="x-card x-stack"><h3 class="x-h3">Pruebas pendientes</h3>${prs.filter(x=>x.s==='pendiente'||x.s==='conseguira').map(x=>`<div>• ${esc(x.p.t)}${x.s==='conseguira'?' <span class="x-tag e-pendiente">la conseguirá</span>':''}</div>`).join('')||'<p class="x-empty">Nada pendiente.</p>'}</div></div>
 <div class="x-card x-stack"><h3 class="x-h3">Dudas para el abogado</h3><ul class="x-mini">${R.dudas.map(d=>`<li>${esc(d)}</li>`).join('')}${st.dudas.map((d,i)=>`<li>${esc(d)} <button class="x-link" type="button" data-dudadel="${i}">quitar</button></li>`).join('')}</ul><div class="x-row"><input class="x-in" id="dudaTxt" placeholder="Escriba una duda para el abogado" style="flex:1 1 260px;width:auto" aria-label="Nueva duda"><button class="x-btn" type="button" id="dudaAdd">Añadir</button></div></div>
 <p class="x-lead">«Declarado» es lo que cuenta el cliente. «Comprobado» lo marca el abogado cuando lo ha visto en un documento. La calificación jurídica (improcedente, nulo) es una interpretación del abogado y se decide en el paso 8.</p>
 </div>`;}

function papeletaHTML(){const st=SF.st,A=st.abg,ab=SF.mode==='abogado';const G=SF.genPapeleta(st);const K=G.K;const C=st.tipo==='C';
 const mark=s=>esc(s).replace(/⟦(.*?)⟧/g,(m,x)=>`<mark title="Dato pendiente">${x}</mark>`);
 const txt=SF.papToText(G);const npend=(txt.match(/⟦/g)||[]).length;
 const total=(K.ind||0)+K.totalCant;
 const opt=ab?`<div class="x-card x-stack x-opts2"><h3 class="x-h3">Datos del abogado</h3>
  <div class="x-fld"><label for="aOrg">Órgano de conciliación</label><input class="x-in" id="aOrg" data-a="organo" value="${esc(A.organo)}" placeholder="SMAC de Madrid, órgano autonómico…"></div>
  <div class="x-fld"><label for="aLoc">Localidad de firma</label><input class="x-in" id="aLoc" data-a="localidad" value="${esc(A.localidad)}"></div>
  <div class="x-fld"><label for="aLet">Letrado/a que representa</label><input class="x-in" id="aLet" data-a="letrado" value="${esc(A.letrado)}"></div>
  <div class="x-fld"><label for="aDom">Domicilio para notificaciones</label><input class="x-in" id="aDom" data-a="domNotif" value="${esc(A.domNotif)}"></div>
  <div class="x-fld"><label for="aCal">Calificación del despido</label><select class="x-sel" id="aCal" data-a="calif"><option value="auto" ${A.calif==='auto'?'selected':''}>Según lo declarado (${K.calif==='nulo'?'nulo':'improcedente'})</option><option value="improcedente" ${A.calif==='improcedente'?'selected':''}>Improcedente</option><option value="nulo" ${A.calif==='nulo'?'selected':''}>Nulo y subsidiariamente improcedente</option></select></div>
  ${C?`<div class="x-row"><div class="x-fld" style="flex:1"><label for="aDA">Días de salario por año</label><input class="x-in" id="aDA" type="number" min="0" data-a="diasAnio" value="${esc(A.diasAnio)}"></div><div class="x-fld" style="flex:1"><label for="aTM">Tope en mensualidades</label><input class="x-in" id="aTM" type="number" min="0" data-a="topeMens" value="${esc(A.topeMens)}"></div></div><p class="x-help">Indemnización del empleo de hogar según el RD 1620/2011 y su reforma de 2022: la ficha no la presupone.</p>`:''}
  <div class="x-fld"><label for="aGC">Grupo de cotización (dato de Seguridad Social, no es categoría)</label><input class="x-in" id="aGC" data-a="grupoCot" value="${esc(A.grupoCot)}"></div>
  <div class="x-fld"><label for="aConv">Convenio colectivo de referencia</label><input class="x-in" id="aConv" data-a="convenio" value="${esc(A.convenio)}"></div>
  <div class="x-fld"><label for="aConvF">Fuente del convenio (boletín y fecha)</label><input class="x-in" id="aConvF" data-a="convenioFuente" value="${esc(A.convenioFuente)}"></div>
  <div class="x-fld"><label for="aCatD">Categoría que podría corresponder</label><input class="x-in" id="aCatD" data-a="categoriaD" value="${esc(A.categoriaD)}" placeholder="Pendiente de revisión del abogado"><span class="x-help">${A.convenio&&A.convenioFuente?'Se usará en la papeleta si la rellena.':'Pendiente de revisión del abogado: sin convenio y fuente, la ficha no propone ninguna categoría y la papeleta describe las funciones.'}</span></div>
  ${C?'':`<div class="x-fld"><label for="aRef">Jornada de referencia (h/semana)</label><input class="x-in" id="aRef" type="number" min="1" data-jref="1" value="${esc(st.jor.ref)}"><span class="x-help">40 h por ley; menos si el convenio lo dice.</span></div>`}
  <div class="x-fld"><label for="aPH">Precio de la hora de más (€)</label><input class="x-in" id="aPH" type="number" min="0" step="0.01" data-a="precioHora" value="${esc(A.precioHora)}"></div>
  <div class="x-fld"><label for="aReg">Salario regulador mensual corregido (€)</label><input class="x-in" id="aReg" type="number" min="0" step="0.01" data-a="regOverride" value="${esc(A.regOverride)}" placeholder="${K.regCalc?num1(K.regCalc):''}"></div>
  <label class="x-check"><input type="checkbox" data-ab="estimaciones" ${A.estimaciones?'checked':''}> Incluir estimaciones de pagas, vacaciones y diferencias con el SMI</label>
  ${st.tipo==='A'?`<label class="x-check"><input type="checkbox" data-ab="incluirAdminsA" ${A.incluirAdminsA?'checked':''}> Citar también al administrador</label>`:''}
  <label class="x-check"><input type="checkbox" data-ab="incObs" ${A.incObs?'checked':''}> Incluir las observaciones generales en la papeleta</label>
  <h3 class="x-h3">Advertencias a la parte requerida</h3>
  <label class="x-check"><input type="checkbox" data-ab="advPruebas" ${A.advPruebas?'checked':''}> Mencionar las pruebas de que dispone</label>
  <label class="x-check"><input type="checkbox" data-ab="advCostas" ${A.advCostas?'checked':''}> Costas si no comparece (art. 66.3 LRJS)</label>
  <label class="x-check"><input type="checkbox" data-ab="advITSS" ${A.advITSS?'checked':''}> Reserva de denuncia a la Inspección de Trabajo</label>
  <label class="x-check"><input type="checkbox" data-ab="advAlta" ${A.advAlta?'checked':''}> Falta de alta: infracción grave</label>
  ${C?'':`<label class="x-check"><input type="checkbox" data-ab="advRegistro" ${A.advRegistro?'checked':''}> Falta de registro de jornada: infracción grave</label>`}
  ${st.tipo!=='A'?`<label class="x-check"><input type="checkbox" data-ab="advExtr" ${A.advExtr?'checked':''}> Sanción por emplear sin autorización (LO 4/2000)</label><p class="x-help" style="color:var(--warn)">Valore antes si mencionar la situación administrativa puede perjudicar al cliente.</p>`:''}
 </div>`:`<div class="x-card x-stack"><h3 class="x-h3">Revisión del abogado</h3><p class="x-lead">La papeleta es un borrador con lo que ha contado el cliente. La calificación, el convenio y las advertencias las decide el abogado: cambie el usuario a «Abogado/a» arriba para verlas.</p></div>`;
 return `<div class="x-pgrid"><div class="x-stack">
  <div class="x-total"><span class="l">Se reclama (estimación)</span><span class="n">${eur(total)}</span><span class="l">${K.ind!=null?'Indemnización '+eur(K.ind)+' + ':''}cantidades ${eur(K.totalCant)}${K.items.some(i=>i.imp==null)?' + importes por fijar':''}${K.diario&&despLike(st)?` · y ${eur(K.diario)} por cada día de salarios de tramitación`:''}</span></div>
  <div class="x-card x-stack"><div class="x-row" style="justify-content:space-between"><span><b class="mono" style="font-size:20px;color:${npend?'var(--warn)':'var(--ok)'}">${npend}</b> datos por completar</span><button class="x-btn pri" type="button" id="papCopy">Copiar papeleta</button></div><p class="x-help">Los huecos aparecen resaltados en la hoja. El texto copiado los muestra entre ⟦ ⟧ para encontrarlos fácilmente.</p></div>
  ${opt}</div>
  <article class="x-paper" aria-label="Borrador de papeleta de conciliación">
   <h1>AL ${mark(G.cabecera.organo.toUpperCase())}</h1>
   <p>${G.sr} <b>${mark(G.nom)}</b>, mayor de edad, con ${mark(G.doc)}, con domicilio en ${mark(SF.fmtDir(V(st,'cli_dom'),SF.P))}${V(st,'cli_email')?', correo electrónico '+esc(V(st,'cli_email')):''}, y a efectos de notificaciones en ${mark(G.cabecera.dom)}, representad${G.sr==='D.ª'?'a':'o'} por ${mark(G.cabecera.letrado)} ${mark(SF.P('acreditar representación'))}, ante este Servicio comparece y, como mejor proceda, <b>DICE</b>:</p>
   <p>Que por medio del presente escrito presenta <b>PAPELETA DE CONCILIACIÓN</b> en materia de <b>${despLike(st)?'DESPIDO'+(K.items.length?' Y RECLAMACIÓN DE CANTIDAD':''):'RECLAMACIÓN DE CANTIDAD'}</b> frente a:</p>
   ${G.partes.map((p,i)=>`<p>${i+1}. ${mark(p)}.</p>`).join('')}
   <p>Y lo fundamenta en los siguientes</p>
   <h2>Hechos</h2>
   ${G.H.map(h=>`<p><span class="lbl">${h.lbl}.-</span> ${mark(h.t)}</p>`).join('')}
   <p>Por lo expuesto,</p>
   <h2>Solicita</h2>
   <p>Que tenga por presentada esta papeleta, la admita y cite a las partes al preceptivo acto de conciliación, en el que se solicitará que la parte requerida se avenga a:</p>
   ${G.S.map((x,i)=>`<p><b>${i+1}.º</b> ${mark(x)}</p>`).join('')}
   ${K.items.length?`<table><tbody>${K.items.map(i=>`<tr><td>${esc(i.c)}<br><span style="font-size:12.5px;color:#5b5a52">${esc(i.det)}${i.est?' · estimación':''}</span></td><td class="r">${i.imp!=null?eur(i.imp):'<mark>importe</mark>'}</td></tr>`).join('')}<tr class="tot"><td>Total cantidades</td><td class="r">${eur(K.totalCant)}</td></tr></tbody></table>`:''}
   ${G.W.length?`<h2>Advertencias</h2>${G.W.map(w=>`<p>${esc(w)}</p>`).join('')}`:''}
   <p><b>OTROSÍ DIGO</b>: que ${G.tr} comparecerá al acto representad${G.sr==='D.ª'?'a':'o'} por letrado, designando a efectos de notificaciones el domicilio indicado.</p>
   <p>En ${mark(G.cabecera.localidad)}, a ${SF.fmtL(SF.today())}.</p>
   <p class="firma">Fdo.: ${mark(G.nom)} &nbsp;&nbsp;&nbsp; Fdo.: ${mark(G.cabecera.letrado)}</p>
  </article></div>`;}

function asideHTML(){const st=SF.st;const crit=R.alerts.filter(a=>a.nivel==='critica').length;return `<aside class="x-aside"><div class="x-card x-stack"><h2 class="x-h3">Control de la ficha</h2><div class="x-nums"><div class="x-num ${R.incompletos.length?'warn':''}"><div class="n">${R.incompletos.length}</div><div class="l">Sin responder</div></div><div class="x-num"><div class="n">${R.desconocidos.length}</div><div class="l">«No lo sabe»</div></div><div class="x-num ${R.contra.length?'bad':''}"><div class="n">${R.contra.length}</div><div class="l">Contradicciones</div></div><div class="x-num ${crit?'bad':''}"><div class="n">${crit}</div><div class="l">Alertas críticas</div></div></div>
 ${R.contra.length?`<ul class="x-mini">${R.contra.map(c=>`<li class="c"><b>${esc(c.titulo)}</b><br>${esc(c.texto)}</li>`).join('')}</ul>`:''}
 ${R.incompletos.filter(i=>i.s===SF.step).length?`<h3 class="x-h3">Falta en este paso</h3><ul class="x-mini">${R.incompletos.filter(i=>i.s===SF.step).map(i=>`<li class="w">${esc(i.label)}</li>`).join('')}</ul>`:''}</div></aside>`;}

function renderStep(){const st=SF.st,s=SF.step;let body='';
 if(s===0)body=`<div class="x-sec x-stack"><h2>Cliente</h2>${qs(0)}</div>`;
 if(s===1)body=`<div class="x-sec x-stack"><h2>${SF.TIPOS[st.tipo].paso2}</h2>${qs(1)}</div>${personasHTML()}`;
 if(s===2&&st.tipo==='C'){if(!st.cuidados.length){st.seq++;st.cuidados.push({id:'K'+st.seq,nombre:'',parentesco:'',edad:'',autonomia:'',hist:'',grado:'',diag:[],diagOtro:'',ayudas:'',medicacion:'',noche:'',centro:'',sanitarios:'',colegio:'',extra:'',saludN:'',rutina:'',cu:[],obs:''});}
  const q=ids=>SF.Q.filter(x=>ids.includes(x.id)&&SF.vis(st,x)).sort((a,b)=>ids.indexOf(a.id)-ids.indexOf(b.id)).map(qHTML).join('');
  body=`<div class="x-sec x-stack"><h2>Relación laboral</h2>${q(['rel_inicio','hog_interna','hog_pernocta'])}</div>
  <div class="x-sec x-stack"><h2>La historia, contada por ella</h2><p class="x-help">Deje que lo cuente con calma y escriba todo. Estos relatos son los que permiten describir en la papeleta cómo era el trabajo con todo detalle.</p>${q(['rel_como','hog_contexto','rel_dia','hist_cambios','hist_trato'])}</div>
  <div class="x-sec x-stack"><h2>Las tareas</h2>${q(['hog_tareas'])}</div>
  ${cuidadosHTML()}${rolesHTML()}${entornoHTML()}
  <div class="x-sec x-stack"><h2>Otros detalles de la casa</h2>${q(['hog_llaves','hog_alarma','hog_segunda','hog_segunda_txt','hog_mascotas','rel_ultimo'])}</div>`;}
 else if(s===2){const first=['rel_inicio','hog_interna','hog_pernocta','rel_antes','rel_antes_txt','rel_como','rel_dondeempezo'];body=`<div class="x-sec x-stack"><h2>Relación laboral</h2>${qs(2,q=>first.includes(q.id))}</div>${rolesHTML()}<div class="x-sec x-stack"><h2>${st.tipo==='C'?'El trabajo en la casa':'El trabajo'}</h2>${qs(2,q=>!first.includes(q.id))}</div>${st.tipo==='C'?cuidadosHTML()+entornoHTML():''}`;}
 if(s===3)body=`<div class="x-sec x-stack"><h2>Jornada</h2>${qs(3,q=>q.id.startsWith('jor')||q.id==='hog_presencia')}</div>${jorHTML()}<div class="x-sec x-stack"><h2>Salario</h2>${qs(3,q=>!(q.id.startsWith('jor')||q.id==='hog_presencia'))}</div>`;
 if(s===4)body=`<div class="x-sec x-stack"><h2>Qué ocurrió con el trabajo</h2>${qs(4)}</div>`;
 if(s===5)body=`<div class="x-sec x-stack"><h2>Documentos y pruebas</h2>${qs(5)}</div>${pruebasHTML()}`;
 if(s===6)body=`<div class="x-sec"><h2 style="margin-bottom:10px">Revisión y pendientes</h2>${revisionHTML()}</div>`;
 if(s===7)body=`<div class="x-sec"><h2 style="margin-bottom:6px">Papeleta de conciliación</h2><p class="x-lead" style="margin-bottom:12px">Borrador generado con lo que consta en la ficha. No inventa datos: lo que falta aparece resaltado. Debe revisarlo y firmarlo el abogado antes de presentarlo.</p>${papeletaHTML()}</div>`;
 const nav=`<div class="x-nav"><button class="x-btn" type="button" data-go="${s-1}" ${s===0?'disabled':''}>Anterior</button>${s<7?`<button class="x-btn pri" type="button" data-go="${s+1}">${s===6?'Generar papeleta':'Siguiente: '+(s+1===1?SF.TIPOS[st.tipo].paso2:STEPS[s+1])}</button>`:''}</div>`;
 $('stepBody').innerHTML=s>=6?body+nav:`<div class="x-grid"><div>${body}${nav}</div>${asideHTML()}</div>`;}
function render(){evalNow();renderHead();renderBand();renderViews();if(SF.view==='entrevista'){renderSteps();renderStep();}if(SF.view==='tests')renderTests();if(SF.view==='inv')renderInv();}
function soft(){evalNow();renderHead();renderBand();renderSteps();const a=document.querySelector('.x-aside');if(a){a.outerHTML=asideHTML();}}
SF.render=render;

/* --- v5 --- */
const MAP=[['nombre','cli_nombre'],['tel','cli_tel'],['nacimiento','cli_nac'],['domicilio',st=>V(st,'cli_dom')?SF.fmtDir(V(st,'cli_dom')):undefined],['dni',st=>V(st,'cli_docnum')],['interprete',st=>V(st,'cli_interp')?V(st,'cli_interp')==='si':undefined],
 ['hogar',st=>st.tipo==='C'],['hogar_tipo','hog_interna'],['irregular',st=>st.tipo!=='A'],['menor_inicio',st=>V(st,'cli_nac')&&V(st,'rel_inicio')?SF.ageAt(V(st,'cli_nac'),V(st,'rel_inicio'))<18:undefined],
 ['emp_tipo',st=>st.tipo==='C'?'fisica':({empresa:'juridica',autonomo:'fisica'})[V(st,'emp_tipo')]],['emp_n',st=>st.tipo==='C'?SF.persWith(st,'dueno').map(p=>p.nombre).join(', ')||undefined:(V(st,'emp_nombre')||V(st,'aut_nombre'))],['emp_cif',st=>V(st,'emp_cif')||V(st,'aut_dni')],['emp_dom',st=>{const d=st.tipo==='C'?V(st,'hog_dir'):V(st,'emp_dom');return d?SF.fmtDir(d):undefined;}],
 ['lugar_trabajo',st=>{const d=st.tipo==='C'?V(st,'hog_dir'):V(st,'emp_centro');return d?SF.fmtDir(d):undefined;}],['otros_centros','emp_otros_txt'],['concurso',st=>V(st,'emp_estado')?V(st,'emp_estado')==='concurso':undefined],
 ['admins',st=>{const a=SF.persWith(st,'dueno');return a.length?a.map(p=>({n:p.nombre,dni:p.dni,dom:'',per:''})):undefined;}],
 ['quien_contrato',st=>SF.persWith(st,'contrato').map(p=>p.nombre).join(', ')||undefined],['quien_ordenes',st=>SF.persWith(st,'ordenes').map(p=>p.nombre).join(', ')||undefined],['quien_paga',st=>SF.persWith(st,'pago').map(p=>p.nombre).join(', ')||undefined],
 ['como_contrato','rel_como'],['lugar_contrato','rel_dondeempezo'],['tipo_ordenes','rel_ordenes'],['forma_contrato',st=>V(st,'rel_contrato')==='si'?'contrato':(V(st,'rel_contrato')==='no'?'verbal':undefined)],['no_cotizacion_nota',st=>V(st,'rel_alta')?V(st,'rel_alta')==='no':undefined],
 ['forma_pago',st=>{const c=V(st,'sal_cobro');if(!c)return undefined;return c.length>1?'mixto':c[0];}],['dia_pago',st=>V(st,'sal_frec')?SF.show(st,SF.QM.sal_frec):undefined],
 ['rel_ini','rel_inicio'],['rel_fin',st=>V(st,'fecha_efectos')||V(st,'rel_ultimo')],['ant_real','rel_contrato_fecha'],['contrato_tipo',st=>st.tipo==='C'?'hogar':(V(st,'rel_contrato')==='no'?'verbal':undefined)],['categoria','rel_puesto'],['funciones','rel_dia'],
 ['funciones_hogar',st=>{const m={limpieza:'Limpieza del hogar',cocina:'Cocina y preparación de comidas',ninos:'Cuidado de menores de edad',mayores:'Cuidado de personas mayores',dependiente:'Cuidado de personas con discapacidad/dependencia',compras:'Compras y recados',plancha:'Lavandería y plancha',mascotas:'Cuidado de animales',otras:'Otros trabajos del hogar'};const t=V(st,'hog_tareas');return t?t.map(x=>m[x]).filter(Boolean):undefined;}],
 ['salario_bruto','sal_real'],['horas_real',st=>{const K=SF.calc(st);return K.horas?String(Math.round(K.horas*10)/10):undefined;}],['jornada_tipo',st=>({fijo:'completa',turnos:'turnos'})[V(st,'jor_tipo')]],
 ['horario',st=>{const p=st.jor.patron;const l=[1,2,3,4,5,6,7].filter(d=>p[d].e&&p[d].s).map(d=>`${DOWN[d]}: ${p[d].e}–${p[d].s}`);return l.length?l.join('\n'):undefined;}],['descansos',st=>{const p=st.jor.patron;const l=[1,2,3,4,5,6,7].filter(d=>Number(p[d].d)).map(d=>`${DOWN[d]}: ${p[d].d} min`);return l.length?l.join('\n'):undefined;}],
 ['presencia',st=>st.tipo==='C'&&V(st,'hog_presencia')?V(st,'hog_presencia')==='si':undefined],['registro_jornada',st=>V(st,'jor_fichaje')==='no'?'no':undefined],['festivos_dom',st=>V(st,'jor_festivos')?V(st,'jor_festivos')!=='no':undefined],
 ['tipo_ext',st=>({despido:'despido',no_llaman:'despido',fin_contrato:'fin_contrato',baja_forzada:'despido',voluntaria:'renuncia'})[V(st,'ext_tipo')]],['fecha_desp',st=>V(st,'fecha_efectos')||V(st,'fecha_com')],
 ['forma_desp',st=>({escrito:'carta',mensaje:'whatsapp',palabra:'verbal',nada:'no_llamaron'})[V(st,'ext_forma')]],['carta',st=>V(st,'ext_forma')?V(st,'ext_forma')==='escrito':undefined],['causa_emp',st=>V(st,'ext_literal_txt')||V(st,'ext_dicho')],
 ['sit_especial',st=>{const s=V(st,'ext_sit');if(!s)return undefined;const m={embarazo:'embarazo',baja:'baja_it',hijos:'reduccion',reclamo:'denuncia',acoso:'acoso',vg:'viol_gen'};return s.map(x=>m[x]).filter(Boolean);}],['hechos',st=>V(st,'ext_dia')||V(st,'ext_relato')],['testigos_despido','ext_testigos_txt'],
 ['papeleta_fecha','pap_fecha'],['papeleta_quien',st=>V(st,'pap')==='si'?(V(st,'abog')==='si'?'otro':'trabajador'):(V(st,'pap')==='no'?'pendiente':undefined)],['smac_celebrado',st=>V(st,'acto')?V(st,'acto')==='si':undefined],['smac_fecha','acto_fecha'],['smac_resultado',st=>V(st,'acto_res')?SF.show(st,SF.QM.acto_res):undefined],['smac_empresa_comp',st=>V(st,'acto_res')?(V(st,'acto_res')==='nofue'?'no':'si'):undefined],
 ['nulo',st=>SF.calc(st).calif==='nulo'],['finiquito',st=>V(st,'ext_firmo')?V(st,'ext_firmo')==='si':undefined],['fini_firmo',st=>V(st,'ext_firmo')?V(st,'ext_firmo')==='si':undefined],['fini_sello',st=>V(st,'ext_firmo_nc')?V(st,'ext_firmo_nc')==='si':undefined],['fini_bajo_presion',st=>V(st,'ext_firmo_presion')?V(st,'ext_firmo_presion')==='si':undefined],
 ['sal_pend',st=>V(st,'deb')==='si'?(V(st,'deb_conc')||[]).includes('salarios'):undefined],['pagas',st=>V(st,'deb')==='si'?(V(st,'deb_conc')||[]).includes('pagas'):undefined],['vac',st=>V(st,'deb')==='si'?(V(st,'deb_conc')||[]).includes('vacaciones'):undefined],['hpend',st=>V(st,'deb')==='si'?(V(st,'deb_conc')||[]).includes('horas'):undefined],
 ['fecha_presc_cant','deb_desde'],['fecha_presc_cant2','deb_desde'],['menores_terceros',st=>V(st,'pru_menores')?V(st,'pru_menores')==='si':undefined],['categoria_conv',st=>undefined],
 ['ccol_cat',st=>st.abg.convenio||undefined],['grupo_cot',st=>undefined]];
const empty=v=>v===undefined||v===null||v===''||v===false||(Array.isArray(v)&&(!v.length||(v.length===1&&v[0]&&v[0].n==='')));
SF.syncV5=()=>{const st=SF.st;let n=0;const keep=[];MAP.forEach(([k,f])=>{const nv=typeof f==='string'?V(st,f):f(st);if(nv===undefined)return;const cur=D[k],had=k in SF.lastSync;if((!had&&empty(cur))||(had&&JSON.stringify(cur)===JSON.stringify(SF.lastSync[k]))){if(JSON.stringify(cur)!==JSON.stringify(nv)){D[k]=JSON.parse(JSON.stringify(nv));n++;}SF.lastSync[k]=nv;}else if(JSON.stringify(cur)!==JSON.stringify(nv))keep.push(k);});render_v5();$('syncInfo').innerHTML=`<li>${n?n+' campos rellenados desde la ficha.':'Al día con la ficha.'}</li>${keep.length?`<li class="w">No se sobrescriben ${keep.length} campos cambiados aquí por el abogado.</li>`:''}`;};
function render_v5(){render_orig();}
SF.resetV5=()=>{Object.keys(D).forEach(k=>delete D[k]);Object.assign(D,{admins:[{n:'',dni:'',dom:'',per:''}],testigos:[],pruebas_docs:[],causas_nulidad:[],funciones_hogar:[],sit_especial:[],irregular:false,hogar:false,nulo:false,concurso:false,menor_inicio:false,menores_terceros:false,apoyo_terceros:false,sepe_solicitado:false,relaciones_previas:false,grupo_empresas:false,sucesion:false,periodo_prueba:false,hex:false,presencia:false,smac_celebrado:false,sal_pend:false,pagas:false,vac:false,hpend:false,finiquito:false,reforma2012:false});C_reset();render_orig();};

/* --- pruebas automáticas e inventario --- */
function renderTests(){const keep=SF.st;const res=SF.runTests();SF.st=keep;const ok=res.filter(r=>r.ok).length;
 $('pTests').innerHTML=`<div class="x-card x-stack"><h2 class="x-h2">${ok} de ${res.length} comprobaciones superadas</h2><p class="x-lead">Se ejecutan con fichas inventadas y fecha fija (lunes 26/10/2026), sin tocar la ficha abierta.</p><div class="x-row"><button class="x-btn" type="button" id="runTests">Volver a ejecutar</button></div><div style="overflow-x:auto"><table class="x-tbl"><thead><tr><th>Caso</th><th>Comprobación</th><th>Resultado</th><th>Detalle</th></tr></thead><tbody>${res.map(r=>`<tr><td>${esc(r.e)}</td><td>${esc(r.c)}</td><td class="${r.ok?'res-ok':'res-ko'}">${r.ok?'Correcto':'Falla'}</td><td>${esc(r.det)}</td></tr>`).join('')}</tbody></table></div></div>`;}
SF.INV=[
 ['1 · Datos del trabajador',[['tw_n','Nombre','Conservado','cli_nombre'],['tw_d','DNI/NIE/Pasaporte','Renombrado','cli_doc + cli_docnum'],['tw_nss','Número de la Seguridad Social','Trasladado al abogado','v5'],['tw_nb','Fecha de nacimiento','Conservado','cli_nac'],['tw_na','Nacionalidad','Trasladado al abogado','v5'],['tw_t','Teléfono','Conservado','cli_tel'],['tw_t2 / tw_em','Teléfono alternativo, correo','Condicional','ayuda de cli_tel; v5'],['tw_dom','Domicilio','Conservado','cli_dom'],['tw_domn','Domicilio de notificaciones','Trasladado al abogado','papeleta: domicilio del despacho'],['tw_idioma / tw_interp','Idioma, intérprete en entrevistas','Renombrado','cli_interp'],['tw_intj','Intérprete en juicio','Trasladado al abogado','v5'],['hogar / hogar_t','Empleo de hogar, interna o externa','Renombrado','elección de ficha C + hog_interna'],['men_in','Menor al inicio','Condicional','se calcula con nacimiento e inicio']]],
 ['2 · Situación administrativa',[['irreg','Situación irregular','Renombrado','elección de ficha A/B/C + cli_permiso'],['permiso_tipo / permiso_vence','Tipo y vencimiento del permiso','Trasladado al abogado','v5'],['sepe_*','Prestación por desempleo','Trasladado al abogado','v5'],['rel_prev','Relación previa','Conservado','rel_antes'],['grupo_emp / sucesion','Grupo de empresas, sucesión','Trasladado al abogado','v5']]],
 ['3 · Empresa y administradores',[['emp_tipo','Persona física o jurídica','Renombrado','emp_tipo: empresa / autónomo / no lo sabe'],['en / ec','Razón social, CIF','Conservado','emp_nombre, emp_cif (o aut_nombre, aut_dni)'],['ed','Domicilio social','Conservado','emp_dom'],['ed2','Otro domicilio','Renombrado','emp_centro, emp_otros_txt'],['ea','Actividad o sector','Retirado del asesor con autorización','v5 (abogado)'],['eccol','Convenio','Trasladado al abogado','papeleta: convenio y fuente'],['et / emp_ntrab / juzgado','Teléfono, plantilla, juzgado','Trasladado al abogado','v5'],['conc / ac2','Concurso, administrador concursal','Renombrado','emp_estado; hueco en la papeleta'],['admins','Administradores','Renombrado','personas con «Dueño/a o administrador/a»']]],
 ['4 · Indicios de laboralidad',[['qc / cc','Quién contrató, cargo','Renombrado','personas + «¿Quién le contrató?»'],['cco / lc','Cómo y dónde le contrataron','Condicional','rel_como, rel_dondeempezo (B, C)'],['fc','Forma del acuerdo','Renombrado','rel_contrato'],['ac','Condiciones acordadas','Renombrado','sal_pactado + explicación libre'],['qo / co / to','Órdenes','Renombrado','personas + rel_ordenes'],['cau','Control de ausencias','Renombrado','«¿Quién decidía su horario?»'],['qp / dp / fp / pd','Pago','Renombrado','«¿Quién le pagaba?», sal_frec, sal_cobro'],['uni','Uniforme','Condicional','lista de pruebas (B)'],['mat','Herramientas','Trasladado al abogado','v5'],['excl','Exclusividad','Retirado del asesor con autorización','v5 (abogado)'],['acc_sis','Acceso a sistemas','Retirado del asesor con autorización','v5 (abogado)'],['no_cot','Nunca dado de alta','Renombrado','rel_alta']]],
 ['5 · Contrato, categoría y convenio',[['ri','Inicio real','Conservado','rel_inicio'],['rf','Fecha de extinción','Renombrado','fecha_efectos / rel_ultimo'],['ant_r','Inicio según contrato','Condicional','rel_contrato_fecha (A)'],['ct','Tipo de contrato','Trasladado al abogado','v5'],['pp','Periodo de prueba','Trasladado al abogado','v5'],['lt / oc','Lugar de trabajo, otros centros','Renombrado','emp_centro, emp_otros_txt'],['fhog','Funciones del hogar','Renombrado','hog_tareas (C)'],['func','Funciones detalladas','Renombrado','rel_trabajo + rel_dia'],['cat','Categoría en contrato o nómina','Renombrado','rel_puesto'],['ccol_c','Convenio de referencia','Trasladado al abogado','papeleta: convenio'],['func_vs_cat','«A la vista de las funciones descritas…»','Retirado del asesor con autorización','papeleta: categoría que podría corresponder (abogado)'],['ccol_year / ccol_salmin / dif_sal','Tablas salariales','Trasladado al abogado','v5']]],
 ['6 · Jornada, salario e indemnización',[['sb','Salario bruto','Renombrado','sal_real'],['pror','Prorrata de pagas','Renombrado','sal_pagas'],['plus / sr','Pluses, salario regulador','Trasladado al abogado','papeleta: salario regulador corregido'],['ref2012 …','Tramos de 2012','Renombrado','cálculo automático de la indemnización'],['jt','Tipo de jornada','Renombrado','jor_tipo'],['hp','Horas pactadas','Retirado del asesor con autorización','v5 (abogado)'],['hr','Horas reales','Renombrado','jor_horas + registro diario'],['hor / desc_j','Horario, descansos','Renombrado','registro de jornada día a día'],['hex','Horas extra','Renombrado','exceso calculado por semana'],['pres','Horas de presencia','Condicional','solo ficha C (columna de presencia)'],['reg_jorn','Registro de jornada','Renombrado','jor_fichaje'],['festivos','Domingos y festivos','Conservado','jor_festivos'],['doc_n / doc_v / doc_b','Nóminas, vida laboral, bases','Renombrado','lista de pruebas'],['men3','«Se aportarán imágenes, vídeos…»','Retirado del asesor con autorización','pru_fotos + pru_menores'],['apo3','Personas con medidas de apoyo','Trasladado al abogado','v5']]],
 ['7 · Extinción',[['te','Tipo de extinción','Renombrado','ext_tipo'],['fd','Fecha del despido','Renombrado','fecha_com + fecha_efectos'],['fd2 / carta','Forma de comunicación','Renombrado','ext_forma'],['ce','Causa alegada','Renombrado','ext_dicho + ext_literal_txt'],['sitspec','Situación especial','Renombrado','ext_sit'],['hech','Relato','Conservado','ext_relato'],['tw_desp','Testigos del despido','Conservado','ext_testigos_txt']]],
 ['8 · Plazos y SMAC',[['fd_cad / pap_f','Fechas para el plazo','Renombrado','banda de plazos'],['pap_q','Quién presentó la papeleta','Renombrado','pap + abog'],['smac_exp','Expediente SMAC','Trasladado al abogado','v5'],['smac / smac_f / smac_r / smac_comp','Acto de conciliación','Renombrado','acto, acto_fecha, acto_res'],['fpresc','Cantidad más antigua','Renombrado','deb_desde']]],
 ['9 · Calificación',[['nulo / cnul / hn','Nulidad','Trasladado al abogado','papeleta: calificación'],['acum','Acumulación','Trasladado al abogado','v5']]],
 ['10 · Finiquito y acuerdos',[['fini / fini_f','Finiquito firmado','Renombrado','ext_firmo'],['fini_s','«No conforme»','Conservado','ext_firmo_nc'],['fini_bp','Firmado bajo presión','Conservado','ext_firmo_presion'],['fini_fecha / fini_imp / fini_t','Detalle del finiquito','Trasladado al abogado','v5'],['anticipo / acdo_prev / pos_acd','Anticipos, conversaciones, acuerdo','Trasladado al abogado','v5']]],
 ['11 · Cantidades',[['sp / pg / vac / hpe','Conceptos adeudados','Renombrado','deb_conc + cálculo automático'],['otc / tot','Otros, total','Trasladado al abogado','papeleta: total'],['fpresc2','Fecha más antigua','Renombrado','deb_desde']]],
 ['12 · Pruebas',[['pdoc','Documentación disponible','Renombrado','lista dinámica de pruebas'],['pd_aseg / pd_riesgo / acc_cor / dilig / peric','Aseguramiento de prueba','Trasladado al abogado','v5'],['testigos','Testigos','Conservado','pru_testigos_txt'],['op / obs','Otras pruebas, notas','Trasladado al abogado','v5']]],
 ['13 · Preparación del juicio',[['int_h … estrat','Interrogatorio, riesgos, estrategia','Trasladado al abogado','v5']]],
 ['14 · Resumen y demandados',[['resumen','Alertas, demandados, tarjetas','Renombrado','paso 7 (revisión) y paso 8 (papeleta)'],['descarga','Exportar ficha','Conservado','v5 → «Exportar ficha completa»']]]];
function renderInv(){const cnt={};SF.INV.forEach(([,f])=>f.forEach(x=>cnt[x[2]]=(cnt[x[2]]||0)+1));
 $('pInv').innerHTML=`<div class="x-stack"><div class="x-card x-stack"><h2 class="x-h2">Qué ha cambiado respecto a la ficha v5</h2><p class="x-lead">Ningún dato se pierde: lo que ya no pregunta el asesor sigue en la «Ficha original v5», visible para el abogado. ${Object.entries(cnt).map(([k,v])=>`${k}: ${v}`).join(' · ')}.</p></div>
 ${SF.INV.map(([t,f])=>`<div class="x-card x-stack"><h3 class="x-h3">${esc(t)}</h3><div style="overflow-x:auto"><table class="x-tbl"><thead><tr><th>Campo v5</th><th>Qué era</th><th>Destino</th><th>Dónde está ahora</th></tr></thead><tbody>${f.map(x=>`<tr><td class="mono">${esc(x[0])}</td><td>${esc(x[1])}</td><td><span class="x-tag" style="color:var(${x[2].startsWith('Retirado')?'--warn':x[2].startsWith('Traslad')?'--pro':x[2]==='Condicional'?'--accent':'--ok'})">${esc(x[2])}</span></td><td>${esc(x[3])}</td></tr>`).join('')}</tbody></table></div></div>`).join('')}</div>`;}

/* --- eventos --- */
function bind(){
 $('vInicio').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;
  if(b.dataset.new)SF.open(b.dataset.new==='C'?FC.newC():b.dataset.new==='B'&&window.FC?FC.newB():SF.newFicha(b.dataset.new));
  if(b.dataset.demo){const dc=window.FC&&FC.DEMOS_C&&FC.DEMOS_C.find(x=>x.id===b.dataset.demo);SF.open(dc?dc.fn():b.dataset.demo==='C'?FC.demo():b.dataset.demo==='B'&&window.FC?FC.demoB():SF.buildScen(b.dataset.demo));SF.toast('Ejemplo ficticio cargado');}
  if(b.dataset.open)SF.open(SF.list[Number(b.dataset.open)]);
  if(b.id==='btnImport')SF.modal('Recuperar copia de seguridad','',{edit:1,ok:'Recuperar',lead:'Pegue aquí el texto de una copia de seguridad.',onOk:t=>{try{const st=JSON.parse(t);if(!st||!st.tipo||!(st.ans||st.c))throw 0;$('modalHost').innerHTML='';SF.open(st);SF.toast('Ficha recuperada');}catch(x){SF.toast('Ese texto no es una copia de seguridad válida',1);}}});});
 $('modeSel').onchange=e=>{SF.mode=e.target.value;if(SF.view==='v5'&&SF.mode!=='abogado')SF.view='entrevista';render();SF.toast(SF.mode==='abogado'?'Modo abogado: datos jurídicos y ficha v5 visibles':'Modo asesor');};
 $('btnSave').onclick=()=>{SF.toast('Ficha guardada en esta sesión');SF.home();};
 $('btnExport').onclick=()=>{if(SF.view==='v5'){try{collect();}catch(e){}}SF.modal('Copia de seguridad',JSON.stringify(SF.st),{lead:'Copie este texto y guárdelo. Para recuperarlo, use «Recuperar una copia de seguridad» en el inicio. Solo datos ficticios.'});};
 $('views').addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(!b)return;if(SF.view==='v5'){try{collect();}catch(x){}}SF.view=b.dataset.view;render();if(SF.view==='v5')SF.syncV5();});
 $('vFicha').addEventListener('click',e=>{if(e.target.id==='btnTipo'){const t=SF.st.tipo;SF.modal('Cambiar de ficha','',{edit:1,ok:'Cambiar',lead:`Escriba A, B o C. Ahora es ${t}. Las respuestas se conservan; las preguntas que no correspondan a la nueva ficha dejarán de mostrarse.`,onOk:v=>{v=v.trim().toUpperCase();if(!['A','B','C'].includes(v)){SF.toast('Escriba A, B o C',1);return;}SF.st.tipo=v;$('modalHost').innerHTML='';render();SF.toast('Ficha cambiada a '+v);}});}
  if(e.target.id==='bandMore'){SF.bandAll=!SF.bandAll;renderBand();}});
 $('steps').addEventListener('click',e=>{const b=e.target.closest('[data-step]');if(!b)return;SF.step=Number(b.dataset.step);render();window.scrollTo(0,$('steps').offsetTop-8);});
 $('pTests').addEventListener('click',e=>{if(e.target.id==='runTests'){renderTests();SF.toast('Pruebas ejecutadas');}});
 const sb=$('stepBody');
 sb.addEventListener('click',e=>{const st=SF.st;const b=e.target.closest('button');if(!b)return;
  if(b.dataset.go!==undefined){SF.step=Number(b.dataset.go);render();window.scrollTo(0,$('steps').offsetTop-8);return;}
  if(b.dataset.goto!==undefined){SF.step=Number(b.dataset.goto);render();const el=$('qq_'+b.dataset.q);if(el)el.scrollIntoView({block:'center'});return;}
  if(b.classList.contains('x-o')&&b.dataset.q){const id=b.dataset.q,q=SF.QM[id],a=st.ans[id];
   if(b.dataset.ns){a&&a.ns?SF.setAns(st,id,'',false):SF.setAns(st,id,'',true);}
   else if(q.ty==='multi'){let arr=a&&!a.ns&&Array.isArray(a.v)?a.v.slice():[];const v=b.dataset.v;if(arr.includes(v))arr=arr.filter(x=>x!==v);else arr=v==='ninguna'?['ninguna']:arr.filter(x=>x!=='ninguna').concat(v);SF.setAns(st,id,arr,false);}
   else{a&&!a.ns&&a.v===b.dataset.v?SF.setAns(st,id,'',false):SF.setAns(st,id,b.dataset.v,false);}
   const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(b.id==='pAdd'){st.seq++;st.personas.push({id:'P'+st.seq,nombre:'',relacion:'',tel:'',dni:'',roles:[]});const y=window.scrollY;render();window.scrollTo(0,y);const ins=document.querySelectorAll('.x-p input[data-pk="nombre"]');if(ins.length)ins[ins.length-1].focus();return;}
  const pe=b.closest('[data-pid]');if(pe){const p=st.personas.find(x=>x.id===pe.dataset.pid);if(b.dataset.role){const r=b.dataset.role;p.roles=p.roles.includes(r)?p.roles.filter(x=>x!==r):p.roles.concat(r);if(st.rolesNS[r])delete st.rolesNS[r];}if(b.dataset.pdel)st.personas=st.personas.filter(x=>x!==p);const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(b.dataset.rolep){const p=st.personas.find(x=>x.id===b.dataset.rolep),r=b.dataset.r;p.roles=p.roles.includes(r)?p.roles.filter(x=>x!==r):p.roles.concat(r);delete st.rolesNS[r];const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(b.dataset.rolens){const r=b.dataset.rolens;if(st.rolesNS[r])delete st.rolesNS[r];else{st.rolesNS[r]=true;}const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(b.id==='jFill'){const r=SF.fillPattern(st,$('jDesde').value,$('jHasta').value);if(!r.ok){SF.toast(r.error,1);return;}st.jor.desde=$('jDesde').value;st.jor.hasta=$('jHasta').value;SF.toast(r.n?`${r.n} días añadidos`:'No se añadió ningún día: falta el horario habitual o ya estaban');const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(b.id==='jAdd'){st.seq++;const last=st.jor.dias.length?st.jor.dias[st.jor.dias.length-1].f:(V(st,'rel_ultimo')||SF.today());st.jor.dias.push({id:'J'+st.seq,f:st.jor.dias.length?SF.addDays(last,1):last,e:'',s:'',d:'',p:'',obs:'',fuente:'memoria'});const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(b.id==='jClear'){st.jor.dias=[];const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(b.dataset.jdel){const id=b.closest('[data-jr]').dataset.jr;st.jor.dias=st.jor.dias.filter(r=>r.id!==id);const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(b.dataset.pre){const k=b.closest('[data-pr]').dataset.pr;st.pruebas[k]=Object.assign(st.pruebas[k]||{nota:''},{estado:b.dataset.pre});const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(b.id==='dudaAdd'){const t=$('dudaTxt').value.trim();if(!t){SF.toast('Escriba la duda primero',1);return;}st.dudas.push(t);const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(b.dataset.dudadel!==undefined){st.dudas.splice(Number(b.dataset.dudadel),1);const y=window.scrollY;render();window.scrollTo(0,y);return;}
  const rr=()=>{const y=window.scrollY;render();window.scrollTo(0,y);};
  if(b.id==='cAdd'){st.seq++;st.cuidados.push({id:'K'+st.seq,nombre:'',parentesco:'',edad:'',autonomia:'',hist:'',grado:'',diag:[],diagOtro:'',ayudas:'',medicacion:'',noche:'',centro:'',sanitarios:'',colegio:'',extra:'',saludN:'',rutina:'',cu:[],obs:''});rr();return;}
  const ce=b.closest('[data-cid]');if(ce){const c=st.cuidados.find(x=>x.id===ce.dataset.cid);if(b.dataset.ccu){const k=b.dataset.ccu;c.cu=(c.cu||[]).includes(k)?c.cu.filter(x=>x!==k):(c.cu||[]).concat(k);}if(b.dataset.cdg){const k=b.dataset.cdg;c.diag=(c.diag||[]).includes(k)?c.diag.filter(x=>x!==k):(c.diag||[]).concat(k);}if(b.dataset.cdel)st.cuidados=st.cuidados.filter(x=>x!==c);rr();return;}
  if(b.id==='eAdd'){st.seq++;st.entorno.push({id:'E'+st.seq,nombre:'',relacion:'',tel:'',frec:'',dias:'',que:'',vio:'',testigo:''});rr();return;}
  if(b.dataset.edel){const id=b.closest('[data-eid]').dataset.eid;st.entorno=st.entorno.filter(x=>x.id!==id);rr();return;}
  if(b.id==='tAdd'){st.seq++;st.jor.tareas.push({id:'T'+st.seq,t:'',desde:'',hasta:'',extra:false});rr();return;}
  if(b.dataset.tdel){const id=b.closest('[data-tid]').dataset.tid;st.jor.tareas=st.jor.tareas.filter(x=>x.id!==id);Object.values(st.jor.patron).forEach(p=>p.tk=(p.tk||[]).filter(x=>x!==id));st.jor.dias.forEach(r=>r.tk=(r.tk||[]).filter(x=>x!==id));rr();return;}
  if(b.dataset.ptk){const p=st.jor.patron[b.closest('[data-pd]').dataset.pd];const k=b.dataset.ptk;p.tk=(p.tk||[]).includes(k)?p.tk.filter(x=>x!==k):(p.tk||[]).concat(k);rr();return;}
  if(b.dataset.rtk){const r=st.jor.dias.find(x=>x.id===b.closest('[data-jr]').dataset.jr);const k=b.dataset.rtk;r.tk=(r.tk||[]).includes(k)?r.tk.filter(x=>x!==k):(r.tk||[]).concat(k);rr();return;}
  if(b.id==='obsTpl'){const cur=(st.obs||'').trim();st.obs=cur?(cur+'\n'+SF.OBS_TPL):SF.OBS_TPL;rr();const ta=$('obsTxt');if(ta)ta.focus();return;}
  if(b.id==='papCopy'){SF.copy(SF.papToText(SF.genPapeleta(st)));return;}
 });
 sb.addEventListener('input',e=>{const t=e.target,st=SF.st;
  if(t.dataset.dq){const id=t.dataset.dq,a=st.ans[id];const o=Object.assign({},a&&!a.ns&&a.v&&typeof a.v==='object'?a.v:{});o[t.dataset.dk]=t.value.trim();SF.setAns(st,id,o,false);return;}
  if(t.dataset.ck){const c=st.cuidados.find(x=>x.id===t.closest('[data-cid]').dataset.cid);c[t.dataset.ck]=t.value;return;}
  if(t.dataset.ek){const x=st.entorno.find(y=>y.id===t.closest('[data-eid]').dataset.eid);x[t.dataset.ek]=t.value;return;}
  if(t.dataset.tk2&&t.type!=='checkbox'){const x=st.jor.tareas.find(y=>y.id===t.closest('[data-tid]').dataset.tid);x[t.dataset.tk2]=t.value;return;}
  if(t.dataset.obs){st.obs=t.value;return;}
  if(t.dataset.q&&t.classList.contains('x-in')){const a=st.ans[t.dataset.q];SF.setAns(st,t.dataset.q,t.value.trim(),false,a&&a.aprox!==undefined?{aprox:a.aprox}:undefined);return;}
  if(t.dataset.nota){SF.setNota(st,t.dataset.nota,t.value);return;}
  const pe=t.closest('[data-pid]');if(pe&&t.dataset.pk){const p=st.personas.find(x=>x.id===pe.dataset.pid);p[t.dataset.pk]=t.value;return;}
  if(t.dataset.prn!==undefined){const k=t.closest('[data-pr]').dataset.pr;st.pruebas[k]=Object.assign(st.pruebas[k]||{estado:'pendiente'},{nota:t.value});return;}});
 sb.addEventListener('change',e=>{const t=e.target,st=SF.st;
  if(t.dataset.dq){const id=t.dataset.dq,a=st.ans[id];const o=Object.assign({},a&&!a.ns&&a.v&&typeof a.v==='object'?a.v:{});o[t.dataset.dk]=t.value.trim();if(t.dataset.dk==='cp'){const p=SF.provDeCP(o.cp);if(p&&!o.prov){o.prov=p;const ps=$('d_'+id+'_prov');if(ps)ps.value=p;}}SF.setAns(st,id,o,false);if(t.tagName==='SELECT'){const y=window.scrollY;render();window.scrollTo(0,y);}else soft();return;}
  if(t.dataset.ck){const c=st.cuidados.find(x=>x.id===t.closest('[data-cid]').dataset.cid);c[t.dataset.ck]=t.value;if(t.dataset.ck==='edad'||t.dataset.ck==='parentesco'){const y=window.scrollY;render();window.scrollTo(0,y);}else soft();return;}
  if(t.dataset.ek){const x=st.entorno.find(y=>y.id===t.closest('[data-eid]').dataset.eid);x[t.dataset.ek]=t.value;return;}
  if(t.dataset.tk2){const x=st.jor.tareas.find(y=>y.id===t.closest('[data-tid]').dataset.tid);if(t.type==='checkbox')x.extra=t.checked;else x[t.dataset.tk2]=t.value;const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(t.dataset.obs)return;
  if(t.dataset.q&&t.classList.contains('x-in')){soft();return;}
  if(t.dataset.nota!==undefined||t.dataset.prn!==undefined)return;
  if(t.closest('[data-pid]')){const y=window.scrollY;if(t.dataset.pk==='nombre'){render();window.scrollTo(0,y);}else soft();return;}
  if(t.dataset.aprox){const id=t.dataset.aprox,a=st.ans[id];if(!a||a.ns||!a.v){t.checked=false;SF.toast('Primero indique una fecha',1);return;}a.aprox=t.checked;soft();return;}
  const pd=t.closest('[data-pd]');if(pd&&t.dataset.pf){st.jor.patron[pd.dataset.pd][t.dataset.pf]=t.value;const y=window.scrollY;render();window.scrollTo(0,y);return;}
  const jr=t.closest('[data-jr]');if(jr&&t.dataset.jf){const r=st.jor.dias.find(x=>x.id===jr.dataset.jr);r[t.dataset.jf]=t.value;if(['f','e','s','d','p'].includes(t.dataset.jf)){if(t.dataset.jf==='f')st.jor.dias.sort((a,b)=>SF.pd(a.f)-SF.pd(b.f));if(r.fuente==='habitual'&&t.dataset.jf!=='f')r.fuente='memoria';const y=window.scrollY;render();window.scrollTo(0,y);}return;}
  if(t.dataset.est){st.ans[t.dataset.est].estado=t.value;soft();return;}
  if(t.dataset.a){st.abg[t.dataset.a]=t.value;const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(t.dataset.jref){st.jor.ref=Number(t.value)||40;const y=window.scrollY;render();window.scrollTo(0,y);return;}
  if(t.dataset.ab){st.abg[t.dataset.ab]=t.checked;const y=window.scrollY;render();window.scrollTo(0,y);return;}
 });
 document.addEventListener('keydown',e=>{if(e.key==='Escape')$('modalHost').innerHTML='';});
}
bind();SF.renderInicio=renderInicio;SF.v5Data=()=>D;
})();
