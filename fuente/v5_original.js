/* =====================================================================
   FICHA DEMANDA LABORAL v5 — código original de la abogada.
   Cambios marcados con [SF]: cálculo de caducidad (calcCad) y salida de
   la descarga (doDownload). El resto se conserva tal cual.
   ===================================================================== */
const STP=[
  'Datos del trabajador/a',
  'Situación administrativa y antecedentes',
  'Empresa y administradores',
  'Indicios de laboralidad',
  'Contrato, categoría y convenio',
  'Jornada, horario y descansos',
  'Extinción: hechos y forma',
  'Plazos de caducidad y SMAC',
  'Calificación del despido',
  'Finiquito y acuerdos previos',
  'Reclamación de cantidades',
  'Pruebas y aseguramiento',
  'Preparación del juicio',
  'Resumen, alertas y demandados',
];
let C=0;
const D={admins:[{n:'',dni:'',dom:'',per:''}],testigos:[],pruebas_docs:[],causas_nulidad:[],funciones_hogar:[],sit_especial:[],irregular:false,hogar:false,nulo:false,concurso:false,menor_inicio:false,menores_terceros:false,apoyo_terceros:false,sepe_solicitado:false,relaciones_previas:false,grupo_empresas:false,sucesion:false,periodo_prueba:false,hex:false,presencia:false,smac_celebrado:false,sal_pend:false,pagas:false,vac:false,hpend:false,finiquito:false,reforma2012:false};

const gv=id=>{const e=document.getElementById(id);return e?e.value:''};
const gc=id=>{const e=document.getElementById(id);return e?e.checked:false};
const gr=n=>{const e=document.querySelector(`input[name="${n}"]:checked`);return e?e.value:''};
const gcs=c=>[...document.querySelectorAll('.'+c+':checked')].map(e=>e.value);
const tog=(id,v)=>{const e=document.getElementById(id);if(e)e.classList.toggle('hid',!v)};
const yn=v=>v?'SÍ':'No';

function rp(){
  document.getElementById('prog').innerHTML=STP.map((_,i)=>`<div class="ps ${i<C?'d':i===C?'a':''}"></div>`).join('');
  document.getElementById('sn').textContent=`Paso ${C+1} de ${STP.length}`;
  document.getElementById('st').textContent=STP[C];
  document.getElementById('bp').style.display=C===0?'none':'';
  const last=C===STP.length-1;
  document.getElementById('bn').classList.toggle('hid',last);
  document.getElementById('bdl').classList.toggle('hid',!last);
}

function collect(){
  const m={
    0:()=>{D.nombre=gv('tw_n');D.dni=gv('tw_d');D.nss=gv('tw_nss');D.nacimiento=gv('tw_nb');D.nacion=gv('tw_na');D.tel=gv('tw_t');D.tel2=gv('tw_t2');D.domicilio=gv('tw_dom');D.dom_notif=gv('tw_domn');D.email=gv('tw_em');D.idioma=gv('tw_idioma');D.interprete=gc('tw_interp');D.interprete_juicio=gc('tw_intj');D.menor_inicio=gc('men_in');D.hogar=gr('hogar')==='si';D.hogar_tipo=gr('hogar_t');},
    1:()=>{D.irregular=gr('irreg')==='si';D.permiso_tipo=gv('permiso_tipo');D.permiso_vence=gv('permiso_vence');D.sepe_solicitado=gc('sepe_sol');D.sepe_fecha=gv('sepe_fecha');D.sepe_denegado=gc('sepe_den');D.relaciones_previas=gc('rel_prev');D.rel_prev_desc=gv('rel_prev_desc');D.grupo_empresas=gc('grupo_emp');D.grupo_desc=gv('grupo_desc');D.sucesion=gc('sucesion');D.sucesion_desc=gv('sucesion_desc');},
    2:()=>{D.emp_tipo=gr('emp_tipo');D.emp_n=gv('en');D.emp_cif=gv('ec');D.emp_dom=gv('ed');D.emp_dom_notif=gv('ed2');D.emp_act=gv('ea');D.emp_ccol=gv('eccol');D.emp_tel=gv('et');D.emp_ntrab=gv('emp_ntrab');D.juzgado=gv('juzgado');D.concurso=gr('conc')==='si';D.adm_concursal=gv('ac2');D.adm_con_dom=gv('ac2_dom');D.admins=[];document.querySelectorAll('.adr').forEach(r=>{const ins=r.querySelectorAll('input');D.admins.push({n:ins[0]?.value||'',dni:ins[1]?.value||'',dom:ins[2]?.value||'',per:ins[3]?.value||''});});},
    3:()=>{D.quien_contrato=gv('qc');D.cargo_contrato=gv('cc');D.como_contrato=gv('cco');D.lugar_contrato=gv('lc');D.forma_contrato=gr('fc');D.acuerdo=gv('ac');D.quien_ordenes=gv('qo');D.cargo_ordenes=gv('co');D.tipo_ordenes=gv('to');D.control_ausencias=gv('cau');D.quien_paga=gv('qp');D.forma_pago=gr('fp');D.dia_pago=gv('dp');D.pago_desc=gv('pd');D.uniforme=gc('uni');D.uniforme_d=gv('uni_d');D.materiales=gc('mat');D.mat_d=gv('mat_d');D.exclusividad=gc('excl');D.excl_d=gv('excl_d');D.acceso_sistema=gc('acc_sis');D.acc_sis_d=gv('acc_sis_d');D.no_cotizacion_nota=gc('no_cot');},
    4:()=>{D.rel_ini=gv('ri');D.rel_fin=gv('rf');D.ant_real=gv('ant_r');D.contrato_tipo=gv('ct');D.periodo_prueba=gc('pp');D.pp_dur=gv('pp_d');D.categoria=gv('cat');D.ccol_cat=gv('ccol_c');D.ccol_year=gv('ccol_year');D.ccol_salmin=gv('ccol_salmin');D.func_vs_cat=gv('func_vs_cat');D.diferencia_salarial=gc('dif_sal');D.dif_sal_d=gv('dif_sal_d');D.salario_bruto=gv('sb');D.prorrata=gr('pror');D.plus_hab=gv('plus');D.sal_reg=gv('sr');D.reforma2012=gc('ref2012');D.ant_pre2012=gv('ant_pre');D.ant_post2012=gv('ant_post');D.ind_pre=gv('ind_pre');D.ind_post=gv('ind_post');D.ind_total=gv('ind_tot');D.lugar_trabajo=gv('lt');D.otros_centros=gv('oc');D.funciones=gv('func');D.funciones_hogar=gcs('fhog');D.registro_jornada=gr('reg_jorn');D.reg_jorn_d=gv('reg_jorn_d');D.festivos_dom=gc('festivos');D.festivos_d=gv('festivos_d');D.doc_nom=gc('doc_n');D.doc_vida=gc('doc_v');D.doc_bases=gc('doc_b');D.menores_terceros=gc('men3');D.menores_desc=gv('men3_d');D.apoyo_terceros=gc('apo3');},
    5:()=>{D.jornada_tipo=gv('jt');D.horas_pact=gv('hp');D.horas_real=gv('hr');D.horario=gv('hor');D.descansos=gv('desc_j');D.hex=gc('hex');D.hex_d=gv('hex_d');D.presencia=gc('pres');D.pres_d=gv('pres_d');},
    6:()=>{D.tipo_ext=gr('te');D.fecha_desp=gv('fd');D.forma_desp=gv('fd2');D.carta=gc('carta');D.causa_emp=gv('ce');D.sit_especial=gcs('sitspec');D.sit_especial_d=gv('sitspec_d');D.hechos=gv('hech');D.testigos_despido=gv('tw_desp');},
    7:()=>{D.papeleta_fecha=gv('pap_f');D.papeleta_quien=gr('pap_q');D.smac_exp=gv('smac_exp');D.smac_celebrado=gc('smac');D.smac_fecha=gv('smac_f');D.smac_resultado=gv('smac_r');D.smac_empresa_comp=gr('smac_comp');D.fecha_presc_cant=gv('fpresc');},
    8:()=>{D.nulo=gr('nulo')==='si';D.causas_nulidad=gcs('cnul');D.hechos_nulidad=gv('hn');D.acumulacion=gc('acum');D.acum_desc=gv('acum_d');},
    9:()=>{D.finiquito=gc('fini');D.fini_firmo=gc('fini_f');D.fini_fecha=gv('fini_fecha');D.fini_importe=gv('fini_imp');D.fini_terminos=gv('fini_t');D.fini_bajo_presion=gc('fini_bp');D.fini_sello=gc('fini_s');D.anticipo=gc('anticipo');D.anticipo_d=gv('anticipo_d');D.acuerdo_previo=gc('acdo_prev');D.acdo_desc=gv('acdo_d');D.posib_acuerdo=gr('pos_acd');},
    10:()=>{D.sal_pend=gc('sp');D.sal_pend_d=gv('sp_d');D.pagas=gc('pg');D.pagas_d=gv('pg_d');D.vac=gc('vac');D.vac_d=gv('vac_d');D.vac_presc=gc('vac_presc');D.hpend=gc('hpe');D.hpend_d=gv('hpe_d');D.otros_cant=gv('otc');D.total_cant=gv('tot');D.fecha_presc_cant2=gv('fpresc2');},
    11:()=>{D.pruebas_docs=gcs('pdoc');D.pd_aseg=gc('pd_aseg');D.pd_riesgo=gc('pd_riesgo');D.dilig=gc('dilig');D.acc_correo=gc('acc_cor');D.pericial=gc('peric');D.pericial_d=gv('peric_d');D.otras_pruebas=gv('op');D.obs=gv('obs');D.testigos=[];document.querySelectorAll('.twb').forEach(r=>{const ins=r.querySelectorAll('input');D.testigos.push({n:ins[0]?.value||'',dni:ins[1]?.value||'',tel:ins[2]?.value||'',acredita:ins[3]?.value||'',activo:ins[4]?.checked||false});});},
    12:()=>{D.int_hechos=gv('int_h');D.int_debil=gv('int_deb');D.docs_juicio=gv('docs_j');D.preg_emp=gv('preg_e');D.riesgos=gv('riesg');D.estrategia=gv('estrat');D.posib_acuerdo=gr('pos_acd');},
  };
  if(m[C])m[C]();
}

function render(){document.getElementById('sc').innerHTML='';RS[C]();rp();}
function nxt(){collect();if(C<STP.length-1){C++;render();scrollTo(0,0);}}
function prev(){collect();if(C>0){C--;render();scrollTo(0,0);}}

const RS=[s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11,s12,s13];

function s0(){document.getElementById('sc').innerHTML=`
<div class="sec"><div class="sec-t"><i class="ti ti-user" aria-hidden="true"></i>Identificación del/la trabajador/a</div>
<div class="g2"><div class="f"><label class="req">Nombre y apellidos completos</label><input id="tw_n" value="${D.nombre||''}" placeholder="Nombre completo"></div>
<div class="f"><label class="req">DNI / NIE / Pasaporte (número exacto)</label><input id="tw_d" value="${D.dni||''}" placeholder="Número del documento"></div></div>
<div class="g3"><div class="f"><label class="req">Número de afiliación a la Seguridad Social (NSS)</label><input id="tw_nss" value="${D.nss||''}" placeholder="12 dígitos — si consta"><span class="hint">Si el trabajador es irregular y nunca fue dado de alta, indicarlo: "No consta alta".</span></div>
<div class="f"><label class="req">Fecha de nacimiento</label><input type="date" id="tw_nb" value="${D.nacimiento||''}"></div>
<div class="f"><label class="req">Nacionalidad</label><input id="tw_na" value="${D.nacion||''}" placeholder="Ej: Marroquí, Ecuatoriana..."></div></div>
<div class="g2"><div class="f"><label class="req">Teléfono principal</label><input id="tw_t" value="${D.tel||''}" placeholder="612 345 678"></div>
<div class="f"><label>Teléfono alternativo / familiar de contacto</label><input id="tw_t2" value="${D.tel2||''}" placeholder="Otro contacto en caso de no localización"></div></div>
<div class="f"><label>Correo electrónico</label><input id="tw_em" value="${D.email||''}" placeholder="correo@ejemplo.com"></div>
<div class="g2"><div class="f"><label class="req">Domicilio completo (calle, número, piso, localidad, CP)</label><input id="tw_dom" value="${D.domicilio||''}" placeholder="Domicilio habitual completo"></div>
<div class="f"><label>Domicilio a efectos de notificaciones (si difiere del anterior)</label><input id="tw_domn" value="${D.dom_notif||''}" placeholder="Solo si es diferente al domicilio habitual"></div></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-language" aria-hidden="true"></i>Idioma e intérprete</div>
<div class="g3"><div class="f"><label>Idioma principal</label><input id="tw_idioma" value="${D.idioma||''}" placeholder="Ej: Árabe, Rumano, Wolof..."></div>
<div class="f"><label class="cp" style="margin-top:16px"><input type="checkbox" id="tw_interp" ${D.interprete?'checked':''}>Necesita intérprete para las entrevistas con el/la abogado/a</label></div>
<div class="f"><label class="cp" style="margin-top:16px"><input type="checkbox" id="tw_intj" ${D.interprete_juicio?'checked':''}>Necesitará intérprete en el acto del juicio oral</label></div></div>
<div class="al w" style="margin-top:4px"><i class="ti ti-alert-triangle" aria-hidden="true"></i>Si necesita intérprete en juicio: comunicarlo al Juzgado con la debida antelación y solicitar intérprete oficial.</div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-home" aria-hidden="true"></i>Empleado/a del hogar</div>
<div class="f"><label class="req">¿Es empleado/a del hogar familiar?</label>
<div class="rg"><label><input type="radio" name="hogar" value="si" ${D.hogar?'checked':''} onchange="tog('hb',true)">Sí</label>
<label><input type="radio" name="hogar" value="no" ${!D.hogar?'checked':''} onchange="tog('hb',false)">No</label></div></div>
<div id="hb" class="${D.hogar?'':'hid'}"><div class="rg"><label><input type="radio" name="hogar_t" value="interna" ${D.hogar_tipo==='interna'?'checked':''}>Interna (reside en el domicilio del empleador)</label>
<label><input type="radio" name="hogar_t" value="externa" ${D.hogar_tipo==='externa'?'checked':''}>Externa (no reside, acude por horas/días)</label></div></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-shield" aria-hidden="true"></i>Cuestiones procesales</div>
<label class="cp"><input type="checkbox" id="men_in" ${D.menor_inicio?'checked':''}>Era menor de 18 años cuando comenzó la relación laboral</label>
<span class="hint hd" style="margin-top:3px;display:block">Aunque ahora sea mayor de edad. Puede afectar al procedimiento y a la intervención del Ministerio Fiscal.</span></div>`;}

function s1(){document.getElementById('sc').innerHTML=`
<div class="sec"><div class="sec-t"><i class="ti ti-file-certificate" aria-hidden="true"></i>Situación administrativa</div>
<div class="f"><label class="req">¿El/la trabajador/a está en situación irregular (sin permiso de residencia y/o trabajo en vigor)?</label>
<div class="rg"><label><input type="radio" name="irreg" value="si" ${D.irregular?'checked':''} onchange="toggleIrregSepe(true)">Sí — irregular</label>
<label><input type="radio" name="irreg" value="no" ${!D.irregular?'checked':''} onchange="toggleIrregSepe(false)">No — regular</label></div></div>
<div id="irrb" class="${D.irregular?'':'hid'}">
<div class="g2"><div class="f"><label>Tipo de documento / permiso que tiene (aunque no autorice a trabajar)</label><input id="permiso_tipo" value="${D.permiso_tipo||''}" placeholder="Ej: NIE en trámite, permiso residencia sin trabajo, solicitud de asilo..."></div>
<div class="f"><label>Fecha de vencimiento del permiso (si aplica)</label><input type="date" id="permiso_vence" value="${D.permiso_vence||''}"></div></div></div></div>
<div id="sepe_box" class="sec ${D.irregular?'hid':''}"><div class="sec-t"><i class="ti ti-building-community" aria-hidden="true"></i>Prestación por desempleo (SEPE)</div>
<div class="al i"><i class="ti ti-info-circle" aria-hidden="true"></i>La solicitud de desempleo acredita la extinción y puede ser relevante en juicio.</div>
<label class="cp"><input type="checkbox" id="sepe_sol" ${D.sepe_solicitado?'checked':''} onchange="tog('sepeb',this.checked)">Solicitó o cobra prestación por desempleo</label>
<div id="sepeb" class="${D.sepe_solicitado?'':'hid'}" style="margin-top:6px">
<div class="g2"><div class="f"><label>Fecha de solicitud en el SEPE</label><input type="date" id="sepe_fecha" value="${D.sepe_fecha||''}"></div>
<div class="f"><label class="cp" style="margin-top:16px"><input type="checkbox" id="sepe_den" ${D.sepe_denegado?'checked':''}>Fue denegada</label></div></div></div></div>
<div id="sepe_irreg_note" class="sec ${D.irregular?'':'hid'}"><div class="sec-t"><i class="ti ti-building-community" aria-hidden="true"></i>Prestación por desempleo — No aplica</div>
<div class="al w"><i class="ti ti-info-circle" aria-hidden="true"></i>Al no haber cotización por la situación irregular, el/la trabajador/a no genera derecho a prestación por desempleo. La ausencia de alta y cotización es en sí misma un indicio de la irregularidad de la contratación, relevante para sustentar la demanda.</div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-history" aria-hidden="true"></i>Relaciones laborales previas con el mismo empleador</div>
<div class="al w"><i class="ti ti-alert-triangle" aria-hidden="true"></i>Si hubo contratos o períodos previos, la antigüedad real puede ser mayor. Los períodos previos pueden sumarse aunque hubiera interrupciones.</div>
<label class="cp"><input type="checkbox" id="rel_prev" ${D.relaciones_previas?'checked':''} onchange="tog('relpb',this.checked)">Hubo relación laboral previa con el mismo empleador o empresa</label>
<div id="relpb" class="${D.relaciones_previas?'':'hid'}" style="margin-top:6px">
<div class="f"><label class="req">Describir períodos previos (fechas, si cotizó, si hubo interrupciones)</label>
<textarea id="rel_prev_desc" placeholder="Ej: Trabajó de enero a junio 2021 sin contrato, luego paró 2 meses y volvió en octubre 2021...">${D.rel_prev_desc||''}</textarea></div></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-sitemap" aria-hidden="true"></i>Grupo de empresas / pluralidad de empleadores / sucesión empresarial</div>
<div class="g2">
<div class="f"><label class="cp" style="margin-bottom:5px"><input type="checkbox" id="grupo_emp" ${D.grupo_empresas?'checked':''} onchange="tog('grpb',this.checked)">Recibía órdenes o pagos de más de una empresa o empleador</label>
<div id="grpb" class="${D.grupo_empresas?'':'hid'}"><textarea id="grupo_desc" placeholder="Nombres de las empresas implicadas, CIFs si se conocen, cómo se relacionaban entre sí...">${D.grupo_desc||''}</textarea></div></div>
<div class="f"><label class="cp" style="margin-bottom:5px"><input type="checkbox" id="sucesion" ${D.sucesion?'checked':''} onchange="tog('sucb',this.checked)">La empresa cambió de nombre, CIF o titular durante la relación laboral</label>
<div id="sucb" class="${D.sucesion?'':'hid'}"><textarea id="sucesion_desc" placeholder="Nombre antiguo y nuevo, fechas del cambio, si el trabajador continuó en las mismas condiciones...">${D.sucesion_desc||''}</textarea></div></div></div></div>`;}

function toggleIrregSepe(v){
  tog('irrb',v);
  tog('sepe_box',!v);
  tog('sepe_irreg_note',v);
}

function s2(){const ah=D.admins.map((a,i)=>aRow(i,a)).join('');
document.getElementById('sc').innerHTML=`
<div class="sec"><div class="sec-t"><i class="ti ti-building" aria-hidden="true"></i>Datos de la empresa o empleador demandado</div>
<div class="f"><label class="req">¿El empleador es persona física o jurídica?</label>
<div class="rg"><label><input type="radio" name="emp_tipo" value="juridica" ${D.emp_tipo==='juridica'?'checked':''}>Persona jurídica (S.L., S.A., cooperativa, asociación...)</label>
<label><input type="radio" name="emp_tipo" value="fisica" ${D.emp_tipo==='fisica'?'checked':''}>Persona física (autónomo, particular, hogar familiar)</label></div></div>
<div class="g2"><div class="f"><label class="req">Razón social / nombre completo del empleador</label><input id="en" value="${D.emp_n||''}" placeholder="Empresa S.L. o Nombre Apellidos (si persona física)"></div>
<div class="f"><label class="req">CIF / NIF / DNI del empleador</label><input id="ec" value="${D.emp_cif||''}" placeholder="B12345678 / 12345678X"></div></div>
<div class="g2"><div class="f"><label class="req">Domicilio social / del empleador (para notificaciones judiciales)</label><input id="ed" value="${D.emp_dom||''}" placeholder="Calle, número, localidad, CP"></div>
<div class="f"><label>Otro domicilio / establecimiento donde notificar (si difiere)</label><input id="ed2" value="${D.emp_dom_notif||''}" placeholder="Centro de trabajo u otro domicilio conocido"></div></div>
<div class="g3"><div class="f"><label>Actividad / sector</label><input id="ea" value="${D.emp_act||''}" placeholder="Hostelería, construcción, cuidados..."></div>
<div class="f"><label>Convenio colectivo aplicable</label><input id="eccol" value="${D.emp_ccol||''}" placeholder="Convenio de..."></div>
<div class="f"><label>Teléfono de la empresa</label><input id="et" value="${D.emp_tel||''}" placeholder="Teléfono"></div></div>
<div class="g2"><div class="f"><label>Número aproximado de trabajadores en la empresa</label><input id="emp_ntrab" value="${D.emp_ntrab||''}" placeholder="Ej: 5, 20, más de 50..."></div>
<div class="f"><label>Juzgado de lo Social competente</label><input id="juzgado" value="${D.juzgado||''}" placeholder="Juzgado de lo Social nº X de ..."></div></div>
<div class="f"><label class="req">¿Empresa en concurso de acreedores?</label>
<div class="rg"><label><input type="radio" name="conc" value="si" ${D.concurso===true?'checked':''} onchange="tog('concb',true)">Sí — en concurso</label>
<label><input type="radio" name="conc" value="no" ${D.concurso===false?'checked':''} onchange="tog('concb',false)">No</label>
<label><input type="radio" name="conc" value="ver">Pendiente verificar en Registro Mercantil</label></div></div>
<div id="concb" class="${D.concurso===true?'':'hid'}">
<div class="al w"><i class="ti ti-alert-triangle" aria-hidden="true"></i>En concurso: se demanda también al administrador/a concursal.</div>
<div class="g2" style="margin-top:6px"><div class="f"><label class="req">Nombre completo del administrador/a concursal</label><input id="ac2" value="${D.adm_concursal||''}" placeholder="Nombre + NIF"></div>
<div class="f"><label>Domicilio del administrador/a concursal</label><input id="ac2_dom" value="${D.adm_con_dom||''}" placeholder="Domicilio a efectos de notificación"></div></div></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-user-shield" aria-hidden="true"></i>Administradores/as durante la relación laboral</div>
<div class="al i"><i class="ti ti-info-circle" aria-hidden="true"></i>Incluir TODOS los que ejercieron durante la relación laboral. En irregulares serán demandados como posibles responsables solidarios.</div>
<div id="adm-l" style="margin-top:7px">${ah}</div>
<button class="bsm a" onclick="addAdm()" style="margin-top:5px"><i class="ti ti-plus" aria-hidden="true"></i> Añadir administrador/a</button></div>`;}

function aRow(i,a){return `<div class="adr ar"><div class="f"><label style="font-size:10px;color:var(--text-muted)">Nombre completo</label><input placeholder="Nombre y apellidos" value="${a.n||''}"></div><div class="f"><label style="font-size:10px;color:var(--text-muted)">DNI / NIF</label><input placeholder="DNI" value="${a.dni||''}"></div><div class="f"><label style="font-size:10px;color:var(--text-muted)">Domicilio</label><input placeholder="Domicilio (para notificación)" value="${a.dom||''}"></div><div class="f"><label style="font-size:10px;color:var(--text-muted)">Período en el cargo</label><input placeholder="Ej: 2019–2023" value="${a.per||''}"></div><button class="bsm r" onclick="this.closest('.adr').remove()" style="align-self:end"><i class="ti ti-trash" aria-hidden="true"></i></button></div>`;}
function addAdm(){const l=document.getElementById('adm-l');const d=document.createElement('div');d.innerHTML=aRow(Date.now(),{});l.appendChild(d.firstElementChild);}

function s3(){document.getElementById('sc').innerHTML=`
<div class="al d"><i class="ti ti-alert-triangle" aria-hidden="true"></i><strong>Bloque crítico para trabajadores/as irregulares.</strong> Estos indicios son la base de la demanda. No dejar ningún campo sin cumplimentar.</div>
<div class="sec" style="margin-top:.5rem"><div class="sec-t"><i class="ti ti-user-check" aria-hidden="true"></i>¿Quién contrató y cómo?</div>
<div class="g2"><div class="f"><label class="req">Nombre completo de quien le ofreció / contrató</label><input id="qc" value="${D.quien_contrato||''}" placeholder="Nombre y apellidos de la persona"></div>
<div class="f"><label class="req">Cargo / relación con la empresa</label><input id="cc" value="${D.cargo_contrato||''}" placeholder="Propietario, socio, encargado, gerente, administrador..."></div></div>
<div class="g2"><div class="f"><label class="req">¿Cómo le ofrecieron el trabajo? (describir con detalle)</label>
<textarea id="cco" placeholder="Ej: A través de un familiar. Fue al local y habló con el dueño D. X, quien le dijo que empezara el lunes...">${D.como_contrato||''}</textarea></div>
<div class="f"><label>¿Dónde se produjo la contratación?</label><input id="lc" value="${D.lugar_contrato||''}" placeholder="En el establecimiento, por teléfono, en el domicilio...">
<label class="req" style="margin-top:8px">Forma en que se formalizó el acuerdo</label>
<div class="rg" style="margin-top:3px"><label><input type="radio" name="fc" value="verbal" ${D.forma_contrato==='verbal'?'checked':''}>Verbal</label>
<label><input type="radio" name="fc" value="whatsapp" ${D.forma_contrato==='whatsapp'?'checked':''}>WhatsApp</label>
<label><input type="radio" name="fc" value="escrito" ${D.forma_contrato==='escrito'?'checked':''}>Escrito no oficial</label>
<label><input type="radio" name="fc" value="contrato" ${D.forma_contrato==='contrato'?'checked':''}>Contrato firmado</label></div></div></div>
<div class="f"><label class="req">¿Qué condiciones se acordaron exactamente al inicio?</label>
<textarea id="ac" placeholder="Cuánto iba a cobrar, qué días, en qué horario, qué funciones, si se habló de alta en SS, si se mencionó período de prueba...">${D.acuerdo||''}</textarea></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-hierarchy" aria-hidden="true"></i>¿Quién daba órdenes e instrucciones?</div>
<div class="g2"><div class="f"><label class="req">Nombre completo de quien daba las órdenes</label><input id="qo" value="${D.quien_ordenes||''}" placeholder="Nombre y apellidos"></div>
<div class="f"><label class="req">Cargo / relación con la empresa</label><input id="co" value="${D.cargo_ordenes||''}" placeholder="Propietario, encargado, gerente..."></div></div>
<div class="f"><label class="req">¿Qué tipo de órdenes daba y cómo?</label>
<textarea id="to" style="min-height:80px" placeholder="Indicaba las tareas diarias, marcaba los turnos por WhatsApp, llamaba para saber su ubicación, revisaba el trabajo, corregía la forma de hacerlo, imponía normas de vestimenta, decidía cuándo tomaba vacaciones, controlaba llegadas y salidas...">${D.tipo_ordenes||''}</textarea></div>
<div class="f"><label class="req">¿Cómo se controlaban ausencias, llegadas tarde y cumplimiento del horario?</label>
<textarea id="cau" placeholder="Apuntaba los días que faltaba, descontaba del salario, había libro de firmas o app de fichaje, le llamaban si llegaba tarde, había cámaras de vigilancia...">${D.control_ausencias||''}</textarea></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-cash" aria-hidden="true"></i>¿Quién pagaba y cómo?</div>
<div class="g2"><div class="f"><label class="req">Nombre completo de quien realizaba el pago</label><input id="qp" value="${D.quien_paga||''}" placeholder="Persona que entregaba el dinero o hacía la transferencia"></div>
<div class="f"><label class="req">Día / frecuencia del pago</label><input id="dp" value="${D.dia_pago||''}" placeholder="Ej: Último viernes de cada mes, cada semana los viernes..."></div></div>
<div class="f"><label class="req">Forma de pago</label>
<div class="rg"><label><input type="radio" name="fp" value="efectivo" ${D.forma_pago==='efectivo'?'checked':''}>Efectivo (mano a mano)</label>
<label><input type="radio" name="fp" value="transferencia" ${D.forma_pago==='transferencia'?'checked':''}>Transferencia bancaria</label>
<label><input type="radio" name="fp" value="bizum" ${D.forma_pago==='bizum'?'checked':''}>Bizum</label>
<label><input type="radio" name="fp" value="mixto" ${D.forma_pago==='mixto'?'checked':''}>Mixto (efectivo + transferencia)</label>
<label><input type="radio" name="fp" value="otro" ${D.forma_pago==='otro'?'checked':''}>Otro</label></div></div>
<div class="f"><label class="req">Describir el pago con todo el detalle posible</label>
<textarea id="pd" placeholder="Importe exacto. Si variaba, por qué. Si alguna vez no pagaron o pagaron tarde. A qué número de cuenta o teléfono (Bizum). Quién estaba presente cuando se pagaba en efectivo. Si hubo recibos o justificantes...">${D.pago_desc||''}</textarea></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-tools" aria-hidden="true"></i>Medios de trabajo, exclusividad y acceso a sistemas</div>
<div class="g2"><div class="f"><label class="cp" style="margin-bottom:5px"><input type="checkbox" id="uni" ${D.uniforme?'checked':''} onchange="tog('unib',this.checked)">La empresa proporcionaba uniforme / ropa / EPI</label>
<div id="unib" class="${D.uniforme?'':'hid'}"><input id="uni_d" value="${D.uniforme_d||''}" placeholder="Tipo, si llevaba logo de la empresa, quién lo entregaba..."></div></div>
<div class="f"><label class="cp" style="margin-bottom:5px"><input type="checkbox" id="mat" ${D.materiales?'checked':''} onchange="tog('matb',this.checked)">La empresa proporcionaba herramientas / materiales / vehículo</label>
<div id="matb" class="${D.materiales?'':'hid'}"><input id="mat_d" value="${D.mat_d||''}" placeholder="Qué herramientas, maquinaria, vehículo..."></div></div></div>
<div class="g2"><div class="f"><label class="cp" style="margin-bottom:5px"><input type="checkbox" id="excl" ${D.exclusividad?'checked':''} onchange="tog('exclb',this.checked)">Se exigía exclusividad (no podía trabajar para otros)</label>
<div id="exclb" class="${D.exclusividad?'':'hid'}"><input id="excl_d" value="${D.excl_d||''}" placeholder="Cómo se le indicó, si se le prohibió expresamente..."></div></div>
<div class="f"><label class="cp" style="margin-bottom:5px"><input type="checkbox" id="acc_sis" ${D.acceso_sistema?'checked':''} onchange="tog('accsb',this.checked)">Tenía acceso a sistemas, correo corporativo o herramientas digitales de la empresa</label>
<div id="accsb" class="${D.acceso_sistema?'':'hid'}"><input id="acc_sis_d" value="${D.acc_sis_d||''}" placeholder="Tipo de acceso, si sigue activo tras el despido, si hay capturas..."></div></div></div>
<label class="cp" style="margin-top:5px"><input type="checkbox" id="no_cot" ${D.no_cotizacion_nota?'checked':''}>Confirmado: nunca fue dado de alta ni cotizó en Seguridad Social durante esta relación laboral</label>
<span class="hint hw" style="margin-top:3px;display:block">Indicio adicional relevante de irregularidad en la contratación.</span></div>`;}

function s4(){const fh=['Limpieza del hogar','Cocina y preparación de comidas','Cuidado de menores de edad','Cuidado de personas mayores','Cuidado de personas con discapacidad/dependencia','Compras y recados','Lavandería y plancha','Conducción/acompañamiento','Cuidado de animales','Jardinería','Atención nocturna','Vigilancia del domicilio','Otros trabajos del hogar'];
document.getElementById('sc').innerHTML=`
<div class="sec"><div class="sec-t"><i class="ti ti-calendar" aria-hidden="true"></i>Duración de la relación laboral</div>
<div class="g3"><div class="f"><label class="req">Fecha de inicio real de la relación laboral</label><input type="date" id="ri" value="${D.rel_ini||''}" onchange="calcA()"><span class="hint">La fecha real, aunque difiera de la del contrato.</span></div>
<div class="f"><label class="req">Fecha de extinción / despido</label><input type="date" id="rf" value="${D.rel_fin||''}" onchange="calcA()"></div>
<div class="f"><label>Fecha inicio según contrato (si difiere de la real)</label><input type="date" id="ant_r" value="${D.ant_real||''}" onchange="calcA()"><span class="hint">Si el inicio real fue antes, puede reclamarse esa antigüedad.</span></div></div>
<div id="abox" class="al i"><i class="ti ti-clock" aria-hidden="true"></i><span id="atxt">Rellena las fechas para calcular la antigüedad.</span></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-file-text" aria-hidden="true"></i>Tipo de contrato</div>
<div class="g2"><div class="f"><label class="req">Tipo de contrato</label>
<select id="ct"><option value="">— Seleccionar —</option>
<option value="indefinido" ${D.contrato_tipo==='indefinido'?'selected':''}>Indefinido</option>
<option value="temporal" ${D.contrato_tipo==='temporal'?'selected':''}>Temporal</option>
<option value="practicas" ${D.contrato_tipo==='practicas'?'selected':''}>Prácticas / formación dual</option>
<option value="obra" ${D.contrato_tipo==='obra'?'selected':''}>Obra o servicio</option>
<option value="verbal" ${D.contrato_tipo==='verbal'?'selected':''}>Verbal (sin contrato escrito)</option>
<option value="hogar" ${D.contrato_tipo==='hogar'?'selected':''}>Hogar familiar</option></select></div>
<div class="f"><label>¿Estaba en período de prueba en el momento del despido?</label>
<label class="cp" style="margin-top:3px"><input type="checkbox" id="pp" ${D.periodo_prueba?'checked':''} onchange="tog('ppb',this.checked)">Sí, en período de prueba</label>
<div id="ppb" class="${D.periodo_prueba?'':'hid'}" style="margin-top:4px"><input id="pp_d" value="${D.pp_dur||''}" placeholder="Duración pactada y fecha de inicio del período de prueba"></div></div></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-map-pin" aria-hidden="true"></i>Lugar de trabajo y funciones</div>
<div class="g2"><div class="f"><label class="req">Centro / lugar de trabajo principal (nombre y dirección exacta)</label><input id="lt" value="${D.lugar_trabajo||''}" placeholder="Nombre del local, establecimiento o dirección completa"></div>
<div class="f"><label>Otros centros, domicilios o desplazamientos habituales</label><input id="oc" value="${D.otros_centros||''}" placeholder="Otros domicilios de clientes, obras, tiendas de la cadena..."></div></div>
${D.hogar?`<div class="f"><label>Funciones del hogar (marcar todas las que apliquen)</label>
<div class="cg3" style="margin-top:4px">${fh.map(f=>`<label class="cp"><input type="checkbox" class="fhog" value="${f}" ${(D.funciones_hogar||[]).includes(f)?'checked':''}>${f}</label>`).join('')}</div></div>`:''}
<div class="f"><label class="req">Descripción detallada y completa de todas las funciones y tareas realizadas</label>
<textarea id="func" style="min-height:100px" placeholder="Describir con el máximo detalle. Ej: Abría el local a las 9h, preparaba la barra, atendía clientes, servía comidas y bebidas, realizaba cobros en efectivo y TPV, recibía pedidos de proveedor, limpiaba cocina y barra al cierre, cerraba el local a las 23h...">${D.funciones||''}</textarea>
<span class="hint">No dejar en blanco. Cada detalle puede ser relevante en juicio y en la determinación de la categoría profesional.</span></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-scale" aria-hidden="true"></i>Categoría profesional, convenio y tablas salariales</div>
<div class="al i"><i class="ti ti-info-circle" aria-hidden="true"></i>Conviene enlazar las funciones descritas con la categoría que realmente le corresponde según convenio, y comparar el salario percibido con el salario mínimo de tablas. Esto puede revelar diferencias salariales reclamables además del despido.</div>
<div class="g2" style="margin-top:6px"><div class="f"><label class="req">Categoría / grupo profesional que figura en contrato o nómina (si existe)</label><input id="cat" value="${D.categoria||''}" placeholder="Ej: Peón, camarero/a, auxiliar..."></div>
<div class="f"><label class="req">Convenio colectivo de referencia para esa categoría</label><input id="ccol_c" value="${D.ccol_cat||''}" placeholder="Convenio aplicable según actividad/sector"></div></div>
<div class="f"><label class="req">A la vista de las funciones descritas: ¿qué categoría profesional le correspondería realmente según el convenio?</label>
<textarea id="func_vs_cat" style="min-height:70px" placeholder="Analizar si las funciones reales encajan con una categoría superior a la que figura en contrato o nómina. Ej: Aunque figura como 'ayudante de cocina', realizaba funciones propias de 'cocinero/a' según el convenio de hostelería (preparación de platos, gestión de pedidos, supervisión de personal)...">${D.func_vs_cat||''}</textarea></div>
<div class="g3" style="margin-top:6px"><div class="f"><label>Año/período de las tablas salariales de referencia</label><input id="ccol_year" value="${D.ccol_year||''}" placeholder="Ej: Tablas 2024"></div>
<div class="f"><label>Salario mínimo según tablas del convenio para la categoría (€/mes)</label><input id="ccol_salmin" value="${D.ccol_salmin||''}" placeholder="Verificar en BOE/BOP del convenio antes de la demanda"></div>
<div class="f"><label class="cp" style="margin-top:16px"><input type="checkbox" id="dif_sal" ${D.diferencia_salarial?'checked':''} onchange="tog('difsalb',this.checked)">Hay diferencia salarial reclamable respecto a tablas</label></div></div>
<div id="difsalb" class="${D.diferencia_salarial?'':'hid'}" style="margin-top:6px"><div class="f"><label class="req">Calcular y describir la diferencia salarial</label>
<textarea id="dif_sal_d" placeholder="Ej: Salario mínimo de tablas para 'cocinero/a' 2024 = 1.450€/mes. Percibía 1.100€/mes. Diferencia = 350€/mes × 14 pagas × X años = importe total reclamable por diferencias salariales.">${D.dif_sal_d||''}</textarea></div></div>
<div class="al w" style="margin-top:6px"><i class="ti ti-alert-triangle" aria-hidden="true"></i>IMPORTANTE: verificar las tablas salariales vigentes del convenio en el BOE/BOP correspondiente antes de presentar la demanda. Esta ficha no sustituye esa comprobación documental.</div></div>`;
setTimeout(calcA,60);}

function s5_old(){}

function calcA(){
  const i=gv('ri'),f=gv('rf'),el=document.getElementById('atxt'),b=document.getElementById('abox');if(!el)return;
  if(i&&f){const ms=new Date(f)-new Date(i);if(ms<0){b.className='al d';el.textContent='Error: fecha de extinción anterior al inicio.';return;}
  const d=Math.floor(ms/86400000),y=Math.floor(d/365),m=Math.floor((d%365)/30),dd=d%30;
  b.className='al s';el.textContent=`Antigüedad: ${y} año${y!==1?'s':''}, ${m} mes${m!==1?'es':''}, ${dd} día${dd!==1?'s':''}. Total: ${d} días.`;
  }else{b.className='al i';el.textContent='Rellena las fechas para calcular la antigüedad.';}
}

function s5(){document.getElementById('sc').innerHTML=`
<div class="sec"><div class="sec-t"><i class="ti ti-currency-euro" aria-hidden="true"></i>Salario y cálculo de indemnización</div>
<div class="g2"><div class="f"><label class="req">Salario bruto mensual realmente percibido (€)</label><input type="number" id="sb" value="${D.salario_bruto||''}" placeholder="Importe real cobrado" onchange="calcInd()"></div>
<div class="f"><label class="req">¿Las pagas extras van prorrateadas en el mensual?</label>
<div class="rg" style="margin-top:3px"><label><input type="radio" name="pror" value="si" ${D.prorrata==='si'?'checked':''} onchange="calcInd()">Sí</label>
<label><input type="radio" name="pror" value="no" ${D.prorrata==='no'?'checked':''} onchange="calcInd()">No — se cobran aparte</label>
<label><input type="radio" name="pror" value="nc" ${D.prorrata==='nc'?'checked':''}>No consta</label></div></div></div>
<div class="g2"><div class="f"><label>Pluses y complementos habituales (especificar e importes)</label><input id="plus" value="${D.plus_hab||''}" placeholder="Plus transporte 50€, nocturnidad 100€..." onchange="calcInd()">
<span class="hint">Los pluses habituales forman parte del salario regulador base de la indemnización.</span></div>
<div class="f"><label class="req">Salario regulador real estimado (€/mes) — base de la indemnización</label><input type="number" id="sr" value="${D.sal_reg||''}" placeholder="Bruto mensual + prorrata pagas + pluses" onchange="calcInd()">
<span class="hint hw">Este importe determina la indemnización. Calcularlo con cuidado.</span></div></div>
${D.diferencia_salarial?`<div class="cmp-box"><div class="cmp-row"><span class="lbl">Salario mínimo según tablas convenio</span><span class="val">${D.ccol_salmin?D.ccol_salmin+' €':'—'}</span></div><div class="cmp-row"><span class="lbl">Salario realmente percibido</span><span class="val">${D.salario_bruto?D.salario_bruto+' €':'—'}</span></div></div>`:''}
<div class="sep"></div>
<div class="al w"><i class="ti ti-alert-triangle" aria-hidden="true"></i><strong>Tramos de indemnización — Reforma laboral 2012:</strong> Si la relación comenzó ANTES del 12/02/2012, se aplican dos tramos: 45 días/año hasta esa fecha (máx. 42 mensualidades) y 33 días/año desde entonces (máx. 24 mensualidades en total).</div>
<label class="cp" style="margin-top:6px"><input type="checkbox" id="ref2012" ${D.reforma2012?'checked':''} onchange="tog('ref2012b',this.checked);calcInd()">La relación laboral comenzó ANTES del 12 de febrero de 2012</label>
<div id="ref2012b" class="${D.reforma2012?'':'hid'}" style="margin-top:8px">
<div class="g2"><div class="f"><label>Antigüedad acumulada ANTES del 12/02/2012</label><input id="ant_pre" value="${D.ant_pre2012||''}" placeholder="Ej: 3 años y 45 días" onchange="calcInd()"></div>
<div class="f"><label>Antigüedad acumulada DESDE el 12/02/2012</label><input id="ant_post" value="${D.ant_post2012||''}" placeholder="Ej: 5 años y 120 días" onchange="calcInd()"></div></div>
<div class="g3"><div class="f"><label>Indemnización tramo pre-2012 (€)</label><input id="ind_pre" value="${D.ind_pre||''}" placeholder="A 45 días/año"></div>
<div class="f"><label>Indemnización tramo post-2012 (€)</label><input id="ind_post" value="${D.ind_post||''}" placeholder="A 33 días/año"></div>
<div class="f"><label>Indemnización TOTAL estimada (€)</label><input id="ind_tot" value="${D.ind_total||''}" placeholder="Suma de ambos tramos"></div></div></div>
<div id="ind_res" class="al s hid" style="margin-top:6px"><i class="ti ti-calculator" aria-hidden="true"></i><span id="ind_txt"></span></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-clock" aria-hidden="true"></i>Tipo y distribución de la jornada</div>
<div class="al w"><i class="ti ti-alert-triangle" aria-hidden="true"></i><strong>Los períodos de descanso NO computan como tiempo de trabajo.</strong> Detallar con precisión.</div>
<div class="g3"><div class="f"><label class="req">Tipo de jornada</label>
<select id="jt"><option value="">— Seleccionar —</option>
<option value="completa" ${D.jornada_tipo==='completa'?'selected':''}>Completa (40 h/sem)</option>
<option value="parcial" ${D.jornada_tipo==='parcial'?'selected':''}>Parcial</option>
<option value="reducida" ${D.jornada_tipo==='reducida'?'selected':''}>Reducción de jornada</option>
<option value="turnos" ${D.jornada_tipo==='turnos'?'selected':''}>Turnos rotativos</option>
<option value="nocturna" ${D.jornada_tipo==='nocturna'?'selected':''}>Nocturna</option>
<option value="guardia" ${D.jornada_tipo==='guardia'?'selected':''}>Guardias/disponibilidad</option></select></div>
<div class="f"><label class="req">Horas semanales pactadas</label><input type="number" id="hp" value="${D.horas_pact||''}" placeholder="Ej: 40"></div>
<div class="f"><label class="req">Horas semanales realmente trabajadas</label><input type="number" id="hr" value="${D.horas_real||''}" placeholder="Ej: 48"><span class="hint hw">Si superan las pactadas, la diferencia es reclamable.</span></div></div>
<div class="f"><label class="req">Horario de trabajo exacto (días y horas de entrada y salida)</label>
<textarea id="hor" style="min-height:90px" placeholder="Especificar día a día. Ej:&#10;— Lunes a viernes: de 09:00 a 14:00 h y de 16:00 a 20:00 h&#10;— Sábados: de 10:00 a 14:00 h&#10;— Domingos y festivos: libre&#10;Indicar si el horario variaba según semanas o temporadas.">${D.horario||''}</textarea></div>
<div class="f"><label class="req">Períodos de descanso — especificar duración exacta (NO computan como trabajo)</label>
<textarea id="desc_j" style="min-height:75px" placeholder="Ej:&#10;— Pausa para comer: de 14:00 a 16:00 h (2 horas). NO computable.&#10;— Pausa de café: aprox. 15 min a las 11:00 h. NO computable.&#10;&#10;Si no había ningún descanso: indicarlo expresamente — es relevante.">${D.descansos||''}</textarea></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-clock-plus" aria-hidden="true"></i>Horas extraordinarias y de presencia</div>
<label class="cp"><input type="checkbox" id="hex" ${D.hex?'checked':''} onchange="tog('hexb',this.checked)">Se realizaron horas extraordinarias no compensadas ni retribuidas</label>
<div id="hexb" class="${D.hex?'':'hid'}" style="margin-top:6px"><div class="f"><label class="req">Descripción (tareas, horarios exactos, frecuencia, quién las ordenaba, si se prometió pago)</label>
<textarea style="min-height:80px" id="hex_d" placeholder="Ej: Todos los viernes de 20:00 a 23:00 h realizaba cierre de caja e inventario (3h extra/semana). Lo pedía el encargado D. X. Le dijeron que lo pagarían 'cuando hubiera dinero'. Nunca se abonó. Aprox. 12 h/mes...">${D.hex_d||''}</textarea></div></div>
${D.hogar?`<div class="sep"></div>
<div class="al i"><i class="ti ti-info-circle" aria-hidden="true"></i>Las horas de presencia son reclamables cuando la jornada supera 40 h/semana. Imprescindible desglosar tareas y horarios con el máximo detalle.</div>
<label class="cp" style="margin-top:5px"><input type="checkbox" id="pres" ${D.presencia?'checked':''} onchange="tog('presb',this.checked)">Se reclamarán horas de presencia</label>
<div id="presb" class="${D.presencia?'':'hid'}" style="margin-top:6px"><div class="f"><label class="req">Descripción exhaustiva: tareas exactas, horarios y si podía descansar libremente</label>
<textarea style="min-height:90px" id="pres_d" placeholder="Ej: De 23:00 a 07:00 h permanecía en el domicilio atendiendo al Sr. X cuando era necesario (cambios, medicación). No podía ausentarse. Si dormía podía descansar pero debía permanecer disponible. Todos los días incluidos festivos...">${D.pres_d||''}</textarea></div></div>`:''}
</div>
<div class="sec"><div class="sec-t"><i class="ti ti-clock-record" aria-hidden="true"></i>Registro de jornada y trabajo en festivos</div>
<div class="g2"><div class="f"><label class="req">¿Existía registro de jornada (obligatorio desde 12/05/2019)?</label>
<div class="rg" style="margin-top:3px"><label><input type="radio" name="reg_jorn" value="si_fav" ${D.registro_jornada==='si_fav'?'checked':''}>Sí — refleja las horas reales (favorable)</label>
<label><input type="radio" name="reg_jorn" value="si_man" ${D.registro_jornada==='si_man'?'checked':''}>Sí — pero está manipulado o no refleja la realidad</label>
<label><input type="radio" name="reg_jorn" value="no" ${D.registro_jornada==='no'?'checked':''}>No existía ningún registro</label>
<label><input type="radio" name="reg_jorn" value="nc" ${D.registro_jornada==='nc'?'checked':''}>No se sabe</label></div>
<input id="reg_jorn_d" value="${D.reg_jorn_d||''}" placeholder="Detalles sobre el sistema de registro..." style="margin-top:5px"></div>
<div class="f"><label class="cp" style="margin-bottom:5px"><input type="checkbox" id="festivos" ${D.festivos_dom?'checked':''} onchange="tog('festb',this.checked)">Trabajaba en domingos y/o festivos (con los recargos económicos correspondientes)</label>
<div id="festb" class="${D.festivos_dom?'':'hid'}"><textarea id="festivos_d" style="min-height:55px" placeholder="Con qué frecuencia, si se compensaba o pagaba el plus de festivo/domingo, importe si se conoce...">${D.festivos_d||''}</textarea></div></div></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-files" aria-hidden="true"></i>Documentación laboral disponible y personas en el procedimiento</div>
<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
<label class="cp"><input type="checkbox" id="doc_n" ${D.doc_nom?'checked':''}>Nóminas</label>
<label class="cp"><input type="checkbox" id="doc_v" ${D.doc_vida?'checked':''}>Vida laboral (INSS)</label>
<label class="cp"><input type="checkbox" id="doc_b" ${D.doc_bases?'checked':''}>Bases de cotización</label></div>
<div class="al w"><i class="ti ti-info-circle" aria-hidden="true"></i>El Ministerio Fiscal debe ser parte cuando en el procedimiento intervengan o se vean involucrados menores de edad o personas con medidas de apoyo — aunque no sean el/la trabajador/a.</div>
<div class="g2" style="margin-top:5px"><div class="f"><label class="cp" style="margin-bottom:4px"><input type="checkbox" id="men3" ${D.menores_terceros?'checked':''} onchange="tog('men3b',this.checked)">Se aportarán imágenes, vídeos o fotografías donde aparezcan menores de edad (ej: niños/as al cuidado de la empleada de hogar)</label>
<div id="men3b" class="${D.menores_terceros?'':'hid'}"><textarea id="men3_d" style="min-height:60px" placeholder="Describir: número de menores que aparecen, edades aproximadas, tipo de material (fotos/vídeos), contexto en que se aportan como prueba del trabajo realizado.">${D.menores_desc||''}</textarea>
<div class="al i" style="margin-top:5px"><i class="ti ti-info-circle" aria-hidden="true"></i>Los menores NO se citan como testigos en ningún procedimiento de este despacho. Solo se recoge aquí si habrá material gráfico donde aparezcan, lo que determina la intervención del Ministerio Fiscal.</div></div></div>
<div class="f"><label class="cp"><input type="checkbox" id="apo3" ${D.apoyo_terceros?'checked':''}>El procedimiento implicará referencias a personas con medidas de apoyo declaradas judicialmente</label></div></div></div>`;
setTimeout(calcInd,60);}

function calcInd(){
  const sr=parseFloat(gv('sr')||gv('sb')||0);
  const ri=D.rel_ini,rf=D.rel_fin;
  const res=document.getElementById('ind_res'),txt=document.getElementById('ind_txt');
  if(!res||!txt||gc('ref2012'))return;
  if(!sr||!ri||!rf){res.classList.add('hid');return;}
  const ms=new Date(rf)-new Date(ri);if(ms<0)return;
  const dias=Math.floor(ms/86400000);
  const ind=Math.round(dias/365*33*sr/12);
  const max=Math.round(sr*24);
  const final=Math.min(ind,max);
  res.classList.remove('hid');
  txt.textContent=`Indemnización orientativa (33 días/año): ${final.toLocaleString('es-ES')} € | ${dias} días de antigüedad × 33 días/año × ${sr} €/mes ÷ 12. Límite: ${max.toLocaleString('es-ES')} € (24 mensualidades). Verificar con salario regulador definitivo antes de la demanda.`;
}

function s6(){document.getElementById('sc').innerHTML=`
<div class="al d"><i class="ti ti-x" aria-hidden="true"></i>El despacho no tramita abandono forzoso ni dimisión voluntaria. Solo despido.</div>
<div class="sec" style="margin-top:.5rem"><div class="sec-t"><i class="ti ti-door-exit" aria-hidden="true"></i>Tipo y forma de extinción</div>
<div class="f"><label class="req">¿Cómo se extinguió la relación laboral?</label>
<div class="rg"><label><input type="radio" name="te" value="despido" ${D.tipo_ext==='despido'?'checked':''}>Despido por la empresa</label>
<label><input type="radio" name="te" value="renuncia" ${D.tipo_ext==='renuncia'?'checked':''}>Renuncia del/la trabajador/a</label>
<label><input type="radio" name="te" value="mutuo" ${D.tipo_ext==='mutuo'?'checked':''}>Mutuo acuerdo</label>
<label><input type="radio" name="te" value="fin_contrato" ${D.tipo_ext==='fin_contrato'?'checked':''}>Fin de contrato temporal</label></div></div>
<div class="g2"><div class="f"><label class="req">Fecha efectiva del despido</label><input type="date" id="fd" value="${D.fecha_desp||''}"></div>
<div class="f"><label class="req">¿Cómo se comunicó el despido?</label>
<select id="fd2"><option value="">— Seleccionar —</option>
<option value="carta" ${D.forma_desp==='carta'?'selected':''}>Carta de despido entregada en mano</option>
<option value="burofax" ${D.forma_desp==='burofax'?'selected':''}>Burofax</option>
<option value="verbal" ${D.forma_desp==='verbal'?'selected':''}>Verbal en persona</option>
<option value="whatsapp" ${D.forma_desp==='whatsapp'?'selected':''}>WhatsApp / mensaje</option>
<option value="email" ${D.forma_desp==='email'?'selected':''}>Correo electrónico</option>
<option value="no_entrada" ${D.forma_desp==='no_entrada'?'selected':''}>No le dejaron entrar / cambiaron cerradura</option>
<option value="no_llamaron" ${D.forma_desp==='no_llamaron'?'selected':''}>Dejaron de llamarle / de darle turnos</option>
<option value="otro" ${D.forma_desp==='otro'?'selected':''}>Otro</option></select></div></div>
<div class="g2"><div class="f"><label class="cp" style="margin-bottom:5px"><input type="checkbox" id="carta" ${D.carta?'checked':''}>Se entregó carta de despido con causa escrita</label>
<div class="f"><label>Causa alegada por la empresa</label><input id="ce" value="${D.causa_emp||''}" placeholder="Causa indicada verbalmente o en la carta de despido"></div></div>
<div class="f"><label>Situación especial del/la trabajador/a en el momento exacto del despido</label>
<div class="cg" style="margin-top:4px">
${[['baja_it','En baja por incapacidad temporal'],['embarazo','Embarazada o en permiso maternidad'],['excedencia','En excedencia o permiso parental'],['reduccion','Con reducción de jornada activa'],['denuncia','Había denunciado a la empresa o presentado queja formal'],['acoso','Había comunicado situación de acoso'],['viol_gen','Víctima de violencia de género']].map(([v,l])=>`<label class="cp"><input type="checkbox" class="sitspec" value="${v}" ${(D.sit_especial||[]).includes(v)?'checked':''}>${l}</label>`).join('')}
</div>
<input id="sitspec_d" value="${D.sit_especial_d||''}" placeholder="Especificar / ampliar la situación especial" style="margin-top:5px"></div></div>
<div class="f"><label class="req">Relato detallado de los hechos del despido</label>
<textarea id="hech" style="min-height:110px" placeholder="Describir con el máximo detalle:&#10;— Cuándo y dónde ocurrió exactamente&#10;— Quién comunicó el despido (nombre y cargo)&#10;— Qué se dijo exactamente (palabras textuales si se recuerdan)&#10;— Si hubo testigos presentes (nombres si se conocen)&#10;— Qué pasó después: si firmó algo, si le recogieron material, si le pidieron las llaves, si le bloquearon el acceso...">${D.hechos||''}</textarea></div>
<div class="f"><label>Testigos presentes en el momento del despido o que supieron de él inmediatamente</label>
<input id="tw_desp" value="${D.testigos_despido||''}" placeholder="Nombres de personas que presenciaron o conocieron inmediatamente el despido"></div></div>`;}

function s7(){document.getElementById('sc').innerHTML=`
<div class="sec"><div class="sec-t"><i class="ti ti-alarm" aria-hidden="true"></i>Caducidad de la acción por despido — VERIFICACIÓN OBLIGATORIA</div>
<div class="al d"><i class="ti ti-alert-triangle" aria-hidden="true"></i><strong>La acción por despido caduca a los 20 días HÁBILES desde la fecha del despido</strong> (art. 59.3 ET). La presentación de la papeleta de conciliación interrumpe el plazo. El cómputo excluye sábados, domingos y festivos. Verificar siempre el calendario de festivos locales y autonómicos.</div>
<div class="g2" style="margin-top:8px"><div class="f"><label class="req">Fecha del despido (para calcular la caducidad)</label><input type="date" id="fd_cad" value="${D.fecha_desp||''}" onchange="calcCad()"></div>
<div class="f"><label>Fecha de presentación de la papeleta de conciliación</label><input type="date" id="pap_f" value="${D.papeleta_fecha||''}" onchange="calcCad()">
<span class="hint">La papeleta interrumpe el plazo. Usar la fecha del registro de entrada, no la de celebración.</span></div></div>
<div id="cad_res" style="margin-top:4px"></div>
<div class="f" style="margin-top:8px"><label>¿Quién presentó la papeleta de conciliación?</label>
<div class="rg"><label><input type="radio" name="pap_q" value="despacho" ${D.papeleta_quien==='despacho'?'checked':''}>El despacho</label>
<label><input type="radio" name="pap_q" value="trabajador" ${D.papeleta_quien==='trabajador'?'checked':''}>El/la trabajador/a por su cuenta (antes de venir al despacho)</label>
<label><input type="radio" name="pap_q" value="otro" ${D.papeleta_quien==='otro'?'checked':''}>Otro abogado/a previo</label>
<label><input type="radio" name="pap_q" value="pendiente" ${D.papeleta_quien==='pendiente'?'checked':''}>Pendiente de presentar</label></div></div>
<div class="f"><label>Número de expediente SMAC / referencia (si consta)</label><input id="smac_exp" value="${D.smac_exp||''}" placeholder="Número de expediente o referencia del SMAC"></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-clock" aria-hidden="true"></i>Prescripción de cantidades — VERIFICACIÓN OBLIGATORIA</div>
<div class="al w"><i class="ti ti-alert-triangle" aria-hidden="true"></i><strong>Las cantidades laborales prescriben al año</strong> desde que fueron exigibles (art. 59.1 ET). Los conceptos devengados hace más de 1 año pueden estar prescritos. Verificar cada concepto individualmente.</div>
<div class="g2" style="margin-top:6px"><div class="f"><label>Fecha más antigua de las cantidades que se pretenden reclamar</label>
<input type="date" id="fpresc" value="${D.fecha_presc_cant||''}" onchange="calcPresc()">
<span class="hint hw">Si esta fecha supera el año, esas cantidades pueden estar prescritas. Analizar concepto a concepto.</span></div>
<div class="f"></div></div>
<div id="presc_res" style="margin-top:4px"></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-scale" aria-hidden="true"></i>Acto de conciliación previa (SMAC / UMAC)</div>
<div class="al i"><i class="ti ti-info-circle" aria-hidden="true"></i>Requisito procesal previo obligatorio. Sin acto de conciliación (o intento) la demanda es inadmisible salvo excepciones legales expresamente previstas.</div>
<label class="cp" style="margin-top:6px"><input type="checkbox" id="smac" ${D.smac_celebrado?'checked':''} onchange="tog('smacb',this.checked)">Ya se celebró el acto de conciliación previa</label>
<div id="smacb" class="${D.smac_celebrado?'':'hid'}" style="margin-top:6px">
<div class="g2"><div class="f"><label class="req">Fecha del acto de conciliación</label><input type="date" id="smac_f" value="${D.smac_fecha||''}"></div>
<div class="f"><label class="req">Resultado del acto</label><input id="smac_r" value="${D.smac_resultado||''}" placeholder="Sin avenencia / Con avenencia (indicar acuerdo) / Empresa incompareciente"></div></div>
<div class="f"><label>¿Compareció la empresa?</label>
<div class="rg"><label><input type="radio" name="smac_comp" value="si" ${D.smac_empresa_comp==='si'?'checked':''}>Sí, compareció</label>
<label><input type="radio" name="smac_comp" value="no" ${D.smac_empresa_comp==='no'?'checked':''}>No compareció (incomparecencia — tiene efectos procesales)</label></div></div></div></div>`;
setTimeout(()=>{calcCad();calcPresc();},60);}

/* [SF] calcCad corregido. La v5 mostraba una fecha de caducidad y, si había papeleta,
   volvía a contar 20 días desde la papeleta (la papeleta suspende el cómputo, no lo reinicia).
   Ahora: recuento prudente de días laborables, sin fecha límite definitiva. */
function calcCad(){
  const fd=gv('fd_cad'),pf=gv('pap_f'),el=document.getElementById('cad_res');if(!el)return;
  if(!fd){el.innerHTML='';return;}
  const hoy=SF.today();
  const nota=` <em style="font-size:11px;opacity:.8">Recuento de lunes a viernes sin descontar festivos nacionales, autonómicos ni locales. No es una fecha de caducidad: la fija el abogado con el calendario oficial.</em>`;
  if(pf){
    const up=SF.wd(fd,pf);
    if(SF.pd(pf)<SF.pd(fd)){el.innerHTML=`<div class="al d">La fecha de la papeleta es anterior a la del despido: revisar ambas fechas.${nota}</div>`;return;}
    el.innerHTML=`<div class="al ${up>=20?'d':'w'}">${up>=20?'<strong>POSIBLE CADUCIDAD ANTERIOR A LA PAPELETA.</strong> ':''}Entre el despido y la papeleta (${SF.fmt(pf)}) transcurrieron ${up} días laborables. La papeleta suspende el cómputo (art. 65.1 LRJS); el abogado debe calcular los días restantes.${nota}</div>`;return;
  }
  const u=SF.wd(fd,hoy),q=20-u;
  let cls,msg;
  if(SF.pd(fd)>SF.pd(hoy)){cls='al d';msg='La fecha del despido es futura: revisar.';}
  else if(u>=20){cls='al d';msg=`<strong>POSIBLE CADUCIDAD.</strong> Han transcurrido ${u} días laborables desde el despido. Revisión jurídica inmediata: comprobar festivos y si hubo papeleta no declarada.`;}
  else if(q<=6){cls='al d';msg=`<strong>URGENTÍSIMO.</strong> Han transcurrido ${u} días laborables; en la estimación prudente quedan ${q}. Avisar hoy al abogado.`;}
  else if(q<=12){cls='al w';msg=`<strong>Plazo justo.</strong> ${u} días laborables transcurridos; en la estimación prudente quedan ${q}.`;}
  else{cls='al s';msg=`Plazo en curso: ${u} días laborables transcurridos; en la estimación prudente quedan ${q}.`;}
  el.innerHTML=`<div class="${cls}">${msg}${nota}</div>`;}

function calcPresc(){
  const fp=gv('fpresc'),el=document.getElementById('presc_res');if(!el||!fp)return;
  const hoy=new Date(),fc=new Date(fp),ua=new Date(hoy);ua.setFullYear(ua.getFullYear()-1);
  const presc=fc<ua;const dias=Math.ceil((hoy-fc)/86400000);
  el.innerHTML=`<div class="al ${presc?'d':'s'}">${presc?`<i class="ti ti-x" aria-hidden="true"></i> <strong>ALERTA PRESCRIPCIÓN:</strong> La cantidad más antigua data de hace ${dias} días (${fc.toLocaleDateString('es-ES')}), superior al año. Esas cantidades pueden estar prescritas (art. 59.1 ET). Analizar qué conceptos son reclamables.`:`<i class="ti ti-check" aria-hidden="true"></i> ${dias} días desde la cantidad más antigua (${fc.toLocaleDateString('es-ES')}) — dentro del plazo de 1 año.`}</div>`;}

function s8(){const causas=[['embarazo','Embarazo / maternidad (art. 55.5 b ET)'],['baja_it','Durante incapacidad temporal'],['conciliacion','Ejercicio derechos conciliación familiar'],['acoso_lab','Acoso laboral'],['acoso_sex','Acoso sexual o por razón de sexo'],['viol_gen','Víctima de violencia de género (art. 55.5 b ET)'],['discrim_sexo','Discriminación por sexo/identidad de género'],['discrim_origen','Discriminación por origen racial/étnico'],['discrim_relig','Discriminación por religión/convicciones'],['discrim_discap','Discriminación por discapacidad/enfermedad'],['paternidad','Paternidad/permiso parental'],['enfermedad','Enfermedad crónica/discapacidad sobrevenida'],['menor_rel','Trabajador/a era menor al inicio de la relación laboral'],['otros','Otros motivos (especificar en hechos)']];
document.getElementById('sc').innerHTML=`
<div class="sec"><div class="sec-t"><i class="ti ti-gavel" aria-hidden="true"></i>Calificación de la demanda</div>
<div class="f"><label class="req">¿Se reclamará la nulidad del despido?</label>
<div class="rg"><label><input type="radio" name="nulo" value="si" ${D.nulo?'checked':''} onchange="tog('nulob',true)">Sí — nulo y subsidiariamente improcedente</label>
<label><input type="radio" name="nulo" value="no" ${!D.nulo?'checked':''} onchange="tog('nulob',false)">No — únicamente improcedente</label></div></div>
<div id="nulob" class="${D.nulo?'':'hid'}">
<div class="al w" style="margin-top:6px"><i class="ti ti-alert-triangle" aria-hidden="true"></i>Despido nulo: el Ministerio Fiscal será parte obligatoria en el procedimiento.</div>
<div class="f" style="margin-top:7px"><label class="req">Causas de nulidad (marcar todas las que concurran)</label>
<div class="cg" style="margin-top:4px">${causas.map(([v,l])=>`<label class="cp"><input type="checkbox" class="cnul" value="${v}" ${(D.causas_nulidad||[]).includes(v)?'checked':''}>${l}</label>`).join('')}</div></div>
<div class="f" style="margin-top:7px"><label class="req">Hechos concretos que justifican la nulidad (desarrollar con precisión)</label>
<textarea id="hn" style="min-height:110px" placeholder="— Cuándo se produjo o comunicó la situación protegida&#10;— Si la empresa tenía conocimiento y desde cuándo&#10;— Proximidad temporal entre la situación protegida y el despido&#10;— Indicios objetivos de discriminación o represalia&#10;— Si se agotó la vía interna de denuncia de acoso&#10;— Conexión causal entre la causa de nulidad y la decisión extintiva">${D.hechos_nulidad||''}</textarea></div></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-copy" aria-hidden="true"></i>Acumulación de acciones</div>
<div class="al i"><i class="ti ti-info-circle" aria-hidden="true"></i>La demanda por despido puede acumularse con la reclamación de cantidades (art. 26 LRJS). Verificar si es conveniente acumular o presentar por separado.</div>
<label class="cp" style="margin-top:5px"><input type="checkbox" id="acum" ${D.acumulacion?'checked':''} onchange="tog('acumb',this.checked)">Se acumulará la reclamación de cantidades a la acción por despido</label>
<div id="acumb" class="${D.acumulacion?'':'hid'}" style="margin-top:6px">
<div class="f"><textarea id="acum_d" placeholder="Indicar si hay alguna particularidad en la acumulación, si se presentarán por separado y por qué...">${D.acum_desc||''}</textarea></div></div></div>`;}

function s9(){document.getElementById('sc').innerHTML=`
<div class="sec"><div class="sec-t"><i class="ti ti-file-check" aria-hidden="true"></i>Finiquito — ALERTA CRÍTICA</div>
<div class="al d"><i class="ti ti-alert-triangle" aria-hidden="true"></i><strong>Un finiquito firmado sin reservas puede destruir la demanda.</strong> Verificar con máximo detalle si firmó algo, en qué condiciones y en qué términos exactos.</div>
<label class="cp" style="margin-top:6px"><input type="checkbox" id="fini" ${D.finiquito?'checked':''} onchange="tog('finib',this.checked)">La empresa presentó o entregó un finiquito</label>
<div id="finib" class="${D.finiquito?'':'hid'}" style="margin-top:7px">
<div class="g2"><div class="f"><label class="req">¿El/la trabajador/a firmó el finiquito?</label>
<label class="cp" style="margin-top:3px"><input type="checkbox" id="fini_f" ${D.fini_firmo?'checked':''} onchange="tog('fini_det',this.checked)">Sí, firmó el finiquito</label></div>
<div class="f"><label>Fecha de firma del finiquito</label><input type="date" id="fini_fecha" value="${D.fini_fecha||''}"></div></div>
<div id="fini_det" class="${D.fini_firmo?'':'hid'}">
<div class="al d" style="margin-top:5px"><i class="ti ti-x" aria-hidden="true"></i><strong>El/la trabajador/a firmó el finiquito.</strong> Analizar urgentemente si lo firmó con o sin reservas, qué decía literalmente, si fue bajo presión o engaño. Esto puede condicionar toda la estrategia procesal.</div>
<div class="g2" style="margin-top:7px"><div class="f"><label class="req">Importe del finiquito firmado</label><input id="fini_imp" value="${D.fini_importe||''}" placeholder="Importe bruto del finiquito"></div>
<div class="f"><label class="req">Términos exactos del finiquito (literalidad si es posible)</label><input id="fini_t" value="${D.fini_terminos||''}" placeholder="¿Decía 'saldo y finiquito total'? ¿Incluía reserva de acciones?"></div></div>
<div class="g2"><div class="f"><label class="cp"><input type="checkbox" id="fini_bp" ${D.fini_bajo_presion?'checked':''}>Lo firmó bajo presión, sin tiempo para leer, sin asesoramiento o manifestando no estar de acuerdo</label></div>
<div class="f"><label class="cp"><input type="checkbox" id="fini_s" ${D.fini_sello?'checked':''}>El finiquito lleva anotado "no conforme" u observación similar por parte del trabajador/a</label></div></div></div>
<div class="f" style="margin-top:6px"><label>Si NO lo firmó: términos del finiquito ofrecido (qué le ofrecieron)</label>
<input placeholder="Qué le ofrecieron aunque no firmara, o qué decía el documento que no quiso firmar" value="${D.fini_terminos_ofrecido||''}"></div></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-coin" aria-hidden="true"></i>Anticipos y deudas con la empresa</div>
<label class="cp"><input type="checkbox" id="anticipo" ${D.anticipo?'checked':''} onchange="tog('antipob',this.checked)">Recibió anticipos o préstamos de la empresa pendientes de devolver</label>
<div id="antipob" class="${D.anticipo?'':'hid'}" style="margin-top:6px">
<div class="f"><label>Detallar (importe, fechas, si hay documento, si se descontaba del salario)</label>
<textarea id="anticipo_d" placeholder="Importe, cuándo se recibió, si se firmó algo, si se descontaba del salario, si la empresa puede compensarlo en la liquidación...">${D.anticipo_d||''}</textarea></div></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-handshake" aria-hidden="true"></i>Conversaciones previas al despido / posibilidad de acuerdo</div>
<label class="cp"><input type="checkbox" id="acdo_prev" ${D.acuerdo_previo?'checked':''} onchange="tog('acdob',this.checked)">Hubo conversaciones o propuestas de acuerdo antes del despido</label>
<div id="acdob" class="${D.acuerdo_previo?'':'hid'}" style="margin-top:6px">
<div class="f"><label>Describir las conversaciones o propuestas previas</label>
<textarea id="acdo_d" placeholder="Quién propuso qué, en qué términos, si hubo oferta económica y cuál fue...">${D.acdo_desc||''}</textarea></div></div>
<div class="f" style="margin-top:8px"><label>¿Existe posibilidad real de alcanzar un acuerdo en conciliación?</label>
<div class="rg" style="margin-top:3px"><label><input type="radio" name="pos_acd" value="si" ${D.posib_acuerdo==='si'?'checked':''}>Sí, es probable</label>
<label><input type="radio" name="pos_acd" value="no" ${D.posib_acuerdo==='no'?'checked':''}>No, el cliente prefiere ir a juicio</label>
<label><input type="radio" name="pos_acd" value="nc" ${D.posib_acuerdo==='nc'?'checked':''}>Depende de la oferta</label></div></div></div>`;}

function s10(){document.getElementById('sc').innerHTML=`
<div class="sec"><div class="sec-t"><i class="ti ti-currency-euro" aria-hidden="true"></i>Cantidades derivadas de la relación laboral</div>
<div class="al i"><i class="ti ti-building-bank" aria-hidden="true"></i>FOGASA se incluye siempre como parte en todas las demandas del despacho. Verificar los límites de responsabilidad del FOGASA vigentes.</div>
<div class="al w" style="margin-top:0"><i class="ti ti-clock" aria-hidden="true"></i><strong>Prescripción de cantidades: 1 año</strong> desde que fueron exigibles (art. 59.1 ET). Verificar que todos los conceptos son del último año. Las cantidades anteriores pueden estar prescritas salvo interrupción.</div>
${D.diferencia_salarial?`<div class="al w"><i class="ti ti-scale" aria-hidden="true"></i><strong>Diferencias salariales detectadas respecto a tablas del convenio</strong> — incluir como concepto reclamable adicional (ver paso 5).</div>`:''}
<div class="g2" style="margin-top:6px">
<div class="f"><label class="cp" style="margin-bottom:4px"><input type="checkbox" id="sp" ${D.sal_pend?'checked':''} onchange="tog('spb',this.checked)">Salarios pendientes de pago</label>
<div id="spb" class="${D.sal_pend?'':'hid'}"><textarea id="sp_d" style="min-height:55px" placeholder="Meses e importes. Ej: agosto, sept. y oct. 2024 a 1.200€/mes = 3.600€. Indicar si algún mes supera el año.">${D.sal_pend_d||''}</textarea></div></div>
<div class="f"><label class="cp" style="margin-bottom:4px"><input type="checkbox" id="pg" ${D.pagas?'checked':''} onchange="tog('pgb',this.checked)">Pagas extraordinarias pendientes</label>
<div id="pgb" class="${D.pagas?'':'hid'}"><textarea id="pg_d" style="min-height:55px" placeholder="Ej: Paga verano 2024 = 600€ + parte proporcional navidad 2024 = 300€. Verificar si alguna supera el año.">${D.pagas_d||''}</textarea></div></div>
<div class="f"><label class="cp" style="margin-bottom:4px"><input type="checkbox" id="vac" ${D.vac?'checked':''} onchange="tog('vacb',this.checked)">Vacaciones no disfrutadas / no compensadas</label>
<div id="vacb" class="${D.vac?'':'hid'}">
<textarea id="vac_d" style="min-height:40px" placeholder="Días pendientes por año y valor. Ej: 15 días 2024 = 600€. 20 días 2023 = 800€.">${D.vac_d||''}</textarea>
<label class="cp" style="margin-top:4px"><input type="checkbox" id="vac_presc" ${D.vac_presc?'checked':''}>Hay vacaciones de años anteriores — verificar si están prescritas</label></div></div>
<div class="f"><label class="cp" style="margin-bottom:4px"><input type="checkbox" id="hpe" ${D.hpend?'checked':''} onchange="tog('hpeb',this.checked)">Horas extraordinarias o de presencia pendientes</label>
<div id="hpeb" class="${D.hpend?'':'hid'}"><textarea id="hpe_d" style="min-height:55px" placeholder="Ej: Aprox. 120 h extra no compensadas en 2024 a 12€/h = 1.440€. Verificar si algún período supera el año.">${D.hpend_d||''}</textarea></div></div></div>
<div class="f"><label>Otros conceptos económicos reclamables</label>
<textarea id="otc" style="min-height:45px" placeholder="Plus transporte, comisiones, dietas, complementos, festivos/domingos no pagados, nocturnidad, ropa de trabajo, diferencias salariales respecto a tablas del convenio...">${D.otros_cant||''}</textarea></div>
<div class="g2"><div class="f"><label>Estimación total de cantidades (excl. indemnización por despido) (€)</label>
<input id="tot" value="${D.total_cant||''}" placeholder="Suma de todos los conceptos económicos pendientes"></div>
<div class="f"><label>Fecha más antigua de los conceptos reclamados (verificación de prescripción)</label>
<input type="date" id="fpresc2" value="${D.fecha_presc_cant2||''}" onchange="calcPresc2()">
<div id="presc_res2" style="margin-top:4px"></div></div></div></div>`;
setTimeout(calcPresc2,50);}

function calcPresc2(){
  const fp=gv('fpresc2'),el=document.getElementById('presc_res2');if(!el||!fp)return;
  const hoy=new Date(),fc=new Date(fp),ua=new Date(hoy);ua.setFullYear(ua.getFullYear()-1);
  const presc=fc<ua;const dias=Math.ceil((hoy-fc)/86400000);
  el.innerHTML=`<div class="al ${presc?'d':'s'} ">${presc?`<i class="ti ti-x" aria-hidden="true"></i> <strong>POSIBLE PRESCRIPCIÓN:</strong> ${dias} días desde la cantidad más antigua. Analizar qué conceptos concretos superan el año.`:`<i class="ti ti-check" aria-hidden="true"></i> ${dias} días — dentro del plazo de 1 año.`}</div>`;}

function s11(){const docs=[['contrato','Contrato de trabajo'],['nominas','Nóminas'],['vida_lab','Vida laboral (INSS)'],['bases_cot','Bases de cotización'],['carta_desp','Carta de despido'],['burofax','Burofax'],['whatsapp','Capturas de WhatsApp (conversaciones)'],['grupo_wapp','Grupo de WhatsApp de trabajo'],['email','Correos electrónicos'],['transferencias','Transferencias bancarias'],['bizum','Comprobantes de Bizum'],['fotos','Fotografías (trabajo, uniforme, lugar...)'],['videos','Vídeos o grabaciones de audio'],['horarios','Horarios / registros de jornada'],['redes','Publicaciones RRSS de la empresa'],['web_emp','Web/anuncio donde aparece trabajando'],['dni_adm','DNI / NIF del administrador/empresa'],['facturas','Facturas o albaranes'],['tickets','Tickets de caja o TPV'],['finiquito_doc','Finiquito (firmado o no firmado)']];
const twH=(D.testigos&&D.testigos.length?D.testigos:[]).map(t=>twRow(t)).join('');
document.getElementById('sc').innerHTML=`
<div class="sec"><div class="sec-t"><i class="ti ti-files" aria-hidden="true"></i>Documentación y pruebas disponibles</div>
<div class="cg" style="margin-top:4px">${docs.map(([v,l])=>`<label class="cp"><input type="checkbox" class="pdoc" value="${v}" ${(D.pruebas_docs||[]).includes(v)?'checked':''}>${l}</label>`).join('')}</div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-device-mobile" aria-hidden="true"></i>Aseguramiento de prueba digital</div>
<div class="g2"><div class="f"><label class="cp"><input type="checkbox" id="pd_aseg" ${D.pd_aseg?'checked':''}>Las pruebas digitales están aseguradas (capturas con fecha, exportadas y almacenadas)</label></div>
<div class="f"><label class="cp"><input type="checkbox" id="pd_riesgo" ${D.pd_riesgo?'checked':''}>Hay riesgo de que la empresa elimine pruebas digitales (perfiles, chats, accesos)</label></div></div>
<div class="g2" style="margin-top:4px"><div class="f"><label class="cp"><input type="checkbox" id="acc_cor" ${D.acc_correo?'checked':''}>El/la trabajador/a sigue teniendo acceso al correo corporativo o sistemas de la empresa tras el despido</label></div>
<div class="f"><label class="cp"><input type="checkbox" id="dilig" ${D.dilig?'checked':''}>Se valorará solicitar diligencia preliminar de aseguramiento o anticipación de prueba</label></div></div>
<label class="cp" style="margin-top:4px"><input type="checkbox" id="peric" ${D.pericial?'checked':''} onchange="tog('pericb',this.checked)">Será necesaria prueba pericial (médica, contable, informática forense, etc.)</label>
<div id="pericb" class="${D.pericial?'':'hid'}" style="margin-top:5px"><input id="peric_d" value="${D.pericial_d||''}" placeholder="Tipo de pericial necesaria y razón por la que se solicita"></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-users" aria-hidden="true"></i>Testigos identificados</div>
<div class="al w"><i class="ti ti-info-circle" aria-hidden="true"></i>Cada testigo debe poder acreditar algo concreto y determinado. Indicar si trabaja actualmente en la empresa (riesgo de presión). Recordatorio: los menores de edad NUNCA se incluyen como testigos.</div>
<div id="tw-list" style="margin-top:7px">${twH}</div>
<button class="bsm a" onclick="addTw()" style="margin-top:5px"><i class="ti ti-plus" aria-hidden="true"></i> Añadir testigo</button></div>
<div class="sec"><div class="sec-t"><i class="ti ti-note" aria-hidden="true"></i>Otras pruebas y observaciones internas</div>
<div class="f"><label>Otras pruebas relevantes</label><textarea id="op" style="min-height:50px" placeholder="Indicios, documentos de terceros, reconocimientos previos del empleador, reseñas de clientes, tarjetas de visita entregadas por la empresa, anuncios donde aparece trabajando...">${D.otras_pruebas||''}</textarea></div>
<div class="f"><label>Observaciones internas / notas del abogado/a</label><textarea id="obs" style="min-height:50px" placeholder="Alertas del caso, aspectos a investigar, valoración inicial, dudas jurídicas a resolver...">${D.obs||''}</textarea></div></div>`;}

function twRow(t){t=t||{};return `<div class="twb"><div class="g2"><div class="f"><label style="font-size:10px;color:var(--text-muted)">Nombre completo</label><input placeholder="Nombre y apellidos" value="${t.n||''}"></div>
<div class="f"><label style="font-size:10px;color:var(--text-muted)">DNI (si se conoce)</label><input placeholder="DNI" value="${t.dni||''}"></div></div>
<div class="g2"><div class="f"><label style="font-size:10px;color:var(--text-muted)">Teléfono</label><input placeholder="Teléfono" value="${t.tel||''}"></div>
<div class="f" style="padding-top:14px"><label style="font-size:12px;display:flex;align-items:center;gap:5px;cursor:pointer"><input type="checkbox" ${t.activo?'checked':''}> Trabaja actualmente en la empresa (riesgo de presión)</label></div></div>
<div class="f"><label style="font-size:10px;color:var(--text-muted)">¿Qué puede acreditar exactamente?</label>
<input placeholder="Ej: Acredita el horario real y que el despido fue verbal por el encargado Sr. X en presencia de D.ª Y" value="${t.acredita||''}"></div>
<div style="text-align:right;margin-top:5px"><button class="bsm r" onclick="this.closest('.twb').remove()"><i class="ti ti-trash" aria-hidden="true"></i> Eliminar</button></div></div>`;}
function addTw(){const l=document.getElementById('tw-list');const d=document.createElement('div');d.innerHTML=twRow({});l.appendChild(d.firstElementChild);}

function s12(){document.getElementById('sc').innerHTML=`
<div class="sec"><div class="sec-t"><i class="ti ti-message-question" aria-hidden="true"></i>Interrogatorio — hechos clave que el/la trabajador/a debe relatar</div>
<div class="f"><label class="req">Hechos principales que debe narrar con seguridad y precisión en el juicio</label>
<textarea id="int_h" style="min-height:120px" placeholder="Enumerar cronológicamente:&#10;1. Cómo empezó a trabajar (quién le contrató, cuándo, dónde, condiciones acordadas)&#10;2. A quién reportaba y qué tipo de órdenes recibía&#10;3. Cómo era la jornada real y el horario exacto&#10;4. Quién le pagaba, cuándo y cómo&#10;5. Qué materiales o herramientas le daba la empresa&#10;6. Cómo se produjo el despido (quién, cuándo, qué dijo exactamente)&#10;7. Si hubo testigos presentes en el momento del despido">${D.int_hechos||''}</textarea></div>
<div class="f"><label class="req">Puntos débiles / posibles contradicciones a trabajar antes del juicio</label>
<textarea id="int_deb" style="min-height:90px" placeholder="Aspectos que la empresa intentará rebatir. Posibles inconsistencias. Preguntas difíciles que puede recibir. Qué debe responder y cómo. Qué NO debe decir...">${D.int_debil||''}</textarea></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-briefcase" aria-hidden="true"></i>Documentos físicos a llevar al juicio</div>
<div class="f"><label class="req">Listado completo de documentos para el acto del juicio oral</label>
<textarea id="docs_j" style="min-height:80px" placeholder="Ej:&#10;— Capturas de WhatsApp (impresas y en soporte digital)&#10;— Transferencias bancarias acreditativas del pago&#10;— Fotografías en el lugar de trabajo&#10;— Original de la carta de despido&#10;— Cualquier documentación que obre en poder del cliente...">${D.docs_juicio||''}</textarea></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-help-circle" aria-hidden="true"></i>Interrogatorio a la empresa / administrador</div>
<div class="f"><label>Preguntas clave para el interrogatorio al representante de la empresa o al administrador</label>
<textarea id="preg_e" style="min-height:90px" placeholder="Ej:&#10;— ¿Quién tomó la decisión de prescindir del/la trabajador/a?&#10;— ¿Por qué no se dio de alta en Seguridad Social?&#10;— ¿Quién pagaba el salario y de qué cuenta salía?&#10;— ¿Qué instrucciones recibía y de quién?&#10;— ¿Tenía libertad de horario o debía cumplir uno fijo?&#10;— ¿Le proporcionaba la empresa uniforme o herramientas?">${D.preg_emp||''}</textarea></div></div>
<div class="sec"><div class="sec-t"><i class="ti ti-alert-triangle" aria-hidden="true"></i>Riesgos y estrategia procesal</div>
<div class="g2"><div class="f"><label class="req">Riesgos procesales o de fondo identificados</label>
<textarea id="riesg" style="min-height:80px" placeholder="Ej: Falta de prueba del salario exacto. Testigos que pueden rehusar declarar. Posible alegación de relación mercantil. Empresa puede aportar registros de jornada. Finiquito firmado sin reservas...">${D.riesgos||''}</textarea></div>
<div class="f"><label class="req">Estrategia procesal y línea argumental principal</label>
<textarea id="estrat" style="min-height:80px" placeholder="Línea principal de la demanda. Pruebas más sólidas. Indicios de laboralidad a destacar. Si se pedirá prueba documental a la empresa en juicio. Valoración global de fortalezas...">${D.estrategia||''}</textarea></div></div>
<div class="sep"></div>
<div class="f"><label>¿Existe posibilidad real de alcanzar un acuerdo en conciliación?</label>
<div class="rg" style="margin-top:3px"><label><input type="radio" name="pos_acd" value="si" ${D.posib_acuerdo==='si'?'checked':''}>Sí, es probable un acuerdo</label>
<label><input type="radio" name="pos_acd" value="no" ${D.posib_acuerdo==='no'?'checked':''}>No, el cliente prefiere ir a juicio</label>
<label><input type="radio" name="pos_acd" value="nc" ${D.posib_acuerdo==='nc'?'checked':''}>Depende de la oferta</label></div></div></div>`;}

function s13(){
  const dems=[];
  dems.push({c:'emp',i:'ti-building',t:`${D.emp_tipo==='fisica'?'Empleador (pers. física)':'Empresa'}: ${D.emp_n||'—'} (CIF: ${D.emp_cif||'—'})`});
  if(D.irregular)(D.admins||[]).filter(a=>a.n).forEach(a=>dems.push({c:'adm',i:'ti-user-shield',t:`Administrador/a: ${a.n}${a.per?' | '+a.per:''}`}));
  if(D.concurso===true)dems.push({c:'con',i:'ti-scale',t:`Adm. Concursal: ${D.adm_concursal||'—'}`});
  dems.push({c:'fog',i:'ti-building-bank',t:'FOGASA (siempre)'});
  const fc=[];
  if(D.nulo)fc.push('despido nulo');if(D.menores_terceros)fc.push('imágenes/vídeos con menores en el procedimiento');if(D.apoyo_terceros)fc.push('personas con medidas de apoyo');if(D.menor_inicio)fc.push('trabajador/a era menor al inicio');
  if(fc.length)dems.push({c:'fis',i:'ti-gavel',t:`Ministerio Fiscal — ${fc.join(', ')}`});

  const alertas=[];
  if(!D.nombre)alertas.push('Nombre del trabajador/a no cumplimentado');
  if(!D.dni)alertas.push('DNI / NIE / Pasaporte no cumplimentado');
  if(!D.emp_n)alertas.push('Nombre de la empresa / empleador no cumplimentado');
  if(!D.fecha_desp)alertas.push('Fecha del despido no cumplimentada — sin ella no se puede calcular la caducidad');
  if(!D.papeleta_fecha&&!D.smac_celebrado)alertas.push('Papeleta de conciliación no presentada / no consta fecha de presentación');
  if(D.finiquito&&D.fini_firmo&&!D.fini_terminos)alertas.push('ALERTA CRÍTICA: Firmó finiquito — revisar términos y consecuencias antes de interponer la demanda');
  if(!D.sal_reg&&!D.salario_bruto)alertas.push('Salario regulador no cumplimentado — necesario para calcular la indemnización');
  if(!D.funciones)alertas.push('Funciones del/la trabajador/a no descritas — imprescindible para la demanda');
  if(!D.hechos)alertas.push('Relato de hechos del despido no cumplimentado');
  if(D.nulo&&(D.causas_nulidad||[]).length===0)alertas.push('Se marcó despido nulo pero no se indicaron las causas de nulidad');
  if(D.diferencia_salarial&&!D.ccol_salmin)alertas.push('Se indicó diferencia salarial pero falta el salario mínimo de tablas del convenio');

  const ms=D.rel_ini&&D.rel_fin?new Date(D.rel_fin)-new Date(D.rel_ini):null;
  const dias=ms?Math.floor(ms/86400000):null;

  document.getElementById('sc').innerHTML=`
${alertas.length?`<div class="al d" style="margin-bottom:.9rem"><i class="ti ti-alert-triangle" aria-hidden="true"></i><div><strong>Campos incompletos / alertas detectadas (${alertas.length}):</strong><ul style="margin:5px 0 0 14px;font-size:12px">${alertas.map(a=>`<li style="margin-bottom:3px">${a}</li>`).join('')}</ul></div></div>`:'<div class="al s" style="margin-bottom:.9rem"><i class="ti ti-check" aria-hidden="true"></i>Ficha completa sin alertas detectadas. Revisar antes de descargar.</div>'}
<div class="sec"><div class="sec-t"><i class="ti ti-list-check" aria-hidden="true"></i>Partes demandadas</div>
<div style="margin-top:4px">${dems.map(d=>`<span class="dt ${d.c}"><i class="ti ${d.i}" aria-hidden="true"></i> ${d.t}</span>`).join('')}</div>
${D.irregular?'<div class="al w" style="margin-top:8px"><i class="ti ti-info-circle" aria-hidden="true"></i>Trabajador/a irregular: empresa + todos los administradores que hayan ejercido durante la relación laboral (posible responsabilidad solidaria).</div>':''}
${D.concurso===true?'<div class="al w" style="margin-top:5px"><i class="ti ti-alert-triangle" aria-hidden="true"></i>Empresa en concurso: también se demanda al administrador/a concursal.</div>':''}
${fc.length?`<div class="al d" style="margin-top:5px"><i class="ti ti-gavel" aria-hidden="true"></i>Ministerio Fiscal: parte obligatoria por — ${fc.join(' / ')}.</div>`:''}
${D.fini_firmo?'<div class="al d" style="margin-top:5px"><i class="ti ti-x" aria-hidden="true"></i><strong>ALERTA FINIQUITO FIRMADO:</strong> Revisar los términos del finiquito antes de interponer la demanda. Puede condicionar toda la estrategia procesal.</div>':''}</div>
<div class="sec"><div class="sec-t"><i class="ti ti-clipboard-text" aria-hidden="true"></i>Resumen del expediente</div>
<div class="g2" style="gap:7px">
<div class="cs"><div class="cl">Trabajador/a</div><div class="cv">${D.nombre||'—'}</div><div class="csb">${D.irregular?'Irregular':'Regular'}${D.hogar?' · Hogar ('+D.hogar_tipo+')':''}</div></div>
<div class="cs"><div class="cl">Empresa</div><div class="cv">${D.emp_n||'—'}</div><div class="csb">${D.concurso===true?'EN CONCURSO':'Sin concurso'}${D.grupo_empresas?' · Grupo empresas':''}</div></div>
<div class="cs"><div class="cl">Antigüedad</div><div class="cv">${D.rel_ini||'—'} → ${D.rel_fin||'—'}</div><div class="csb">${dias?dias+' días':'-'}</div></div>
<div class="cs"><div class="cl">Calificación</div><div class="cv">${D.nulo?'Nulo + improcedente':'Improcedente'}</div><div class="csb">${D.tipo_ext||'—'}</div></div>
<div class="cs"><div class="cl">Salario regulador</div><div class="cv">${D.sal_reg||D.salario_bruto||'—'} €/mes</div><div class="csb">${D.categoria||'—'}${D.diferencia_salarial?' · Diferencias tablas':''}</div></div>
<div class="cs"><div class="cl">SMAC / Conciliación</div><div class="cv">${D.smac_celebrado?'Celebrado':'Pendiente'}</div><div class="csb">${D.papeleta_fecha?'Papeleta: '+D.papeleta_fecha:'Sin papeleta registrada'}</div></div></div></div>`;}

function doDownload(){
  collect();
  const f=(l,v)=>`${l}: ${v||'—'}`;
  const bl=(t,s)=>`\n${'━'.repeat(62)}\n${t}\n${'━'.repeat(62)}\n${s}`;
  const admT=(D.admins||[]).filter(a=>a.n).map(a=>`  • ${a.n} | DNI: ${a.dni||'—'} | Dom: ${a.dom||'—'} | Período: ${a.per||'—'}`).join('\n')||'  (ninguno indicado)';
  const twT=(D.testigos||[]).filter(t=>t.n).map(t=>`  • ${t.n} | DNI: ${t.dni||'—'} | Tel: ${t.tel||'—'} | En activo empresa: ${yn(t.activo)}\n    Acredita: ${t.acredita||'—'}`).join('\n')||'  (ninguno indicado)';
  const dems=[];
  dems.push('  [EMPRESA] '+(D.emp_n||'—')+' — CIF: '+(D.emp_cif||'—')+' — '+(D.emp_dom||'—'));
  if(D.irregular)(D.admins||[]).filter(a=>a.n).forEach(a=>dems.push('  [ADMINISTRADOR/A] '+a.n+' | DNI: '+a.dni+' | Período: '+a.per));
  if(D.concurso===true)dems.push('  [ADM. CONCURSAL] '+(D.adm_concursal||'—')+' | Dom: '+(D.adm_con_dom||'—'));
  dems.push('  [FOGASA] — siempre incluido');
  const fc=[];
  if(D.nulo)fc.push('despido nulo');if(D.menores_terceros)fc.push('imágenes/vídeos con menores en el procedimiento');if(D.apoyo_terceros)fc.push('personas con medidas de apoyo');if(D.menor_inicio)fc.push('trabajador/a era menor al inicio');
  if(fc.length)dems.push('  [MINISTERIO FISCAL] — '+fc.join(', '));

  const txt=`${'═'.repeat(65)}
  FICHA DE DEMANDA LABORAL — DESPACHO JURÍDICO
  Ficha: ${SF.st.id} · ${SF.TIPOS[SF.st.tipo].corto}
  Fecha y hora de elaboración: ${new Date().toLocaleString('es-ES')}
${'═'.repeat(65)}
${bl('1. DATOS DEL TRABAJADOR/A',
[f('Nombre y apellidos',D.nombre),f('DNI/NIE/Pasaporte',D.dni),f('NSS (Número Seguridad Social)',D.nss),f('Fecha de nacimiento',D.nacimiento),f('Nacionalidad',D.nacion),f('Teléfono principal',D.tel),f('Teléfono alternativo',D.tel2),f('Domicilio',D.domicilio),f('Domicilio a efectos de notificaciones',D.dom_notif||'Igual al anterior'),f('Correo electrónico',D.email),f('Idioma',D.idioma),f('Intérprete en entrevistas',yn(D.interprete)),f('Intérprete en juicio',yn(D.interprete_juicio)),f('Empleado/a de hogar',D.hogar?'SÍ — '+D.hogar_tipo:'No'),f('Era menor de edad al inicio de la relación laboral',yn(D.menor_inicio))].join('\n'))}
${bl('2. SITUACIÓN ADMINISTRATIVA Y ANTECEDENTES',
[f('Situación administrativa',D.irregular?'IRREGULAR (sin permiso de residencia y/o trabajo)':'Regular'),f('Tipo de permiso/documento',D.permiso_tipo),f('Vencimiento permiso',D.permiso_vence),'',D.irregular?'PRESTACIÓN POR DESEMPLEO: No aplica — el trabajador no cotizó por su situación irregular. La ausencia de alta es en sí misma indicio de irregularidad.':f('Solicitó prestación SEPE',yn(D.sepe_solicitado))+(D.sepe_solicitado?'\n'+f('Fecha solicitud SEPE',D.sepe_fecha)+'\n'+f('Prestación denegada',yn(D.sepe_denegado)):''),'',f('Relación laboral previa mismo empleador',yn(D.relaciones_previas)),D.relaciones_previas?f('Descripción períodos previos',D.rel_prev_desc):'','',f('Grupo de empresas / pluralidad empleadores',yn(D.grupo_empresas)),D.grupo_empresas?f('Detalle',D.grupo_desc):'',f('Sucesión empresarial',yn(D.sucesion)),D.sucesion?f('Detalle',D.sucesion_desc):''].join('\n'))}
${bl('3. EMPRESA Y ADMINISTRADORES',
[f('Tipo de empleador',D.emp_tipo==='fisica'?'Persona física':'Persona jurídica'),f('Razón social / nombre',D.emp_n),f('CIF/NIF/DNI',D.emp_cif),f('Domicilio social',D.emp_dom),f('Otro domicilio/notificación',D.emp_dom_notif||'—'),f('Actividad',D.emp_act),f('Convenio colectivo',D.emp_ccol),f('Teléfono',D.emp_tel),f('Número de trabajadores',D.emp_ntrab),f('Juzgado de lo Social',D.juzgado),f('En concurso de acreedores',D.concurso===true?'SÍ':'No'),D.concurso===true?f('Administrador/a concursal',D.adm_concursal):'',D.concurso===true?f('Domicilio adm. concursal',D.adm_con_dom):'','','ADMINISTRADORES/AS DURANTE LA RELACIÓN LABORAL:\n'+admT].join('\n'))}
${bl('4. INDICIOS DE LABORALIDAD',
[f('Quién contrató',D.quien_contrato),f('Cargo',D.cargo_contrato),f('Cómo le ofrecieron el trabajo',D.como_contrato),f('Lugar contratación',D.lugar_contrato),f('Forma formalización',D.forma_contrato),f('Condiciones acordadas al inicio',D.acuerdo),'',f('Quién daba órdenes',D.quien_ordenes),f('Cargo',D.cargo_ordenes),f('Tipo de órdenes y control',D.tipo_ordenes),f('Control de ausencias/horario',D.control_ausencias),'',f('Quién pagaba',D.quien_paga),f('Forma de pago',D.forma_pago),f('Frecuencia/día de pago',D.dia_pago),f('Descripción del pago',D.pago_desc),'',f('Uniforme/EPI por empresa',yn(D.uniforme)),D.uniforme?f('Detalle uniforme',D.uniforme_d):'',f('Herramientas/materiales/vehículo',yn(D.materiales)),D.materiales?f('Detalle',D.mat_d):'',f('Exclusividad exigida',yn(D.exclusividad)),D.exclusividad?f('Detalle',D.excl_d):'',f('Acceso a sistemas/correo corporativo',yn(D.acceso_sistema)),D.acceso_sistema?f('Detalle',D.acc_sis_d):'',f('Confirmado: nunca dado de alta/cotizado',yn(D.no_cotizacion_nota))].join('\n'))}
${bl('5. CONTRATO, CATEGORÍA Y CONVENIO',
[f('Fecha inicio real',D.rel_ini),f('Fecha extinción',D.rel_fin),f('Fecha inicio según contrato (si difiere)',D.ant_real||'—'),f('Tipo de contrato',D.contrato_tipo),f('En período de prueba al despido',yn(D.periodo_prueba)),D.periodo_prueba?f('Duración período prueba',D.pp_dur):'','',f('Lugar de trabajo principal',D.lugar_trabajo),f('Otros centros/desplazamientos',D.otros_centros||'—'),D.hogar&&(D.funciones_hogar||[]).length?f('Funciones de hogar (checklist)',(D.funciones_hogar||[]).join(', ')):'','','FUNCIONES Y TAREAS DETALLADAS:\n'+(D.funciones||'—'),'',f('Categoría según contrato/nómina',D.categoria),f('Convenio colectivo de referencia',D.ccol_cat),'FUNCIONES vs CATEGORÍA REAL SEGÚN CONVENIO:\n'+(D.func_vs_cat||'—'),f('Año/período tablas salariales',D.ccol_year||'—'),f('Salario mínimo según tablas para la categoría',D.ccol_salmin?D.ccol_salmin+' €':'—'),f('Diferencia salarial detectada',yn(D.diferencia_salarial)),D.diferencia_salarial?'CÁLCULO DE LA DIFERENCIA SALARIAL:\n'+(D.dif_sal_d||'—'):'','NOTA: Verificar tablas salariales vigentes en BOE/BOP del convenio antes de presentar la demanda.'].join('\n'))}
${bl('6. SALARIO, INDEMNIZACIÓN, JORNADA Y DESCANSOS',
[f('Salario bruto mensual real',D.salario_bruto?D.salario_bruto+' €':'—'),f('Prorrata pagas extras',D.prorrata),f('Pluses habituales',D.plus_hab||'—'),f('Salario regulador (base indemnización)',D.sal_reg?D.sal_reg+' €':'—'),f('Reforma 2012 aplica',yn(D.reforma2012)),D.reforma2012?f('Antigüedad pre-2012',D.ant_pre2012):'',D.reforma2012?f('Antigüedad post-2012',D.ant_post2012):'',D.reforma2012?f('Ind. tramo pre-2012',D.ind_pre?D.ind_pre+' €':'—'):'',D.reforma2012?f('Ind. tramo post-2012',D.ind_post?D.ind_post+' €':'—'):'',D.reforma2012?f('Ind. TOTAL estimada',D.ind_total?D.ind_total+' €':'—'):'','',f('Tipo de jornada',D.jornada_tipo),f('Horas semanales pactadas',D.horas_pact),f('Horas semanales reales',D.horas_real),'','HORARIO DE TRABAJO:\n'+(D.horario||'—'),'','PERÍODOS DE DESCANSO (no computan como trabajo):\n'+(D.descansos||'—'),'',f('Horas extraordinarias no compensadas',yn(D.hex)),D.hex?'DESCRIPCIÓN HORAS EXTRA:\n'+(D.hex_d||'—'):'',D.hogar?f('Horas de presencia reclamadas',yn(D.presencia)):'',D.hogar&&D.presencia?'DESCRIPCIÓN HORAS DE PRESENCIA:\n'+(D.pres_d||'—'):'','',f('Registro de jornada',D.registro_jornada||'—'),D.reg_jorn_d?f('Detalle registro',D.reg_jorn_d):'',f('Trabajo en festivos/domingos',yn(D.festivos_dom)),D.festivos_dom?f('Detalle festivos',D.festivos_d):'','',f('Nóminas disponibles',yn(D.doc_nom)),f('Vida laboral disponible',yn(D.doc_vida)),f('Bases de cotización disponibles',yn(D.doc_bases)),'',f('Imágenes/vídeos con menores en el procedimiento',yn(D.menores_terceros)),D.menores_terceros?f('Detalle del material con menores',D.menores_desc):'',D.menores_terceros?'NOTA: Los menores NO se citan como testigos; solo se aporta material gráfico.':'',f('Personas con medidas de apoyo en procedimiento',yn(D.apoyo_terceros))].join('\n'))}
${bl('7. EXTINCIÓN DE LA RELACIÓN LABORAL',
[f('Tipo de extinción',D.tipo_ext),f('Fecha efectiva del despido',D.fecha_desp),f('Forma de comunicación',D.forma_desp),f('Carta de despido entregada',yn(D.carta)),f('Causa alegada por la empresa',D.causa_emp||'—'),f('Situación especial al momento del despido',(D.sit_especial||[]).join(', ')||'Ninguna'),D.sit_especial_d?f('Detalle situación especial',D.sit_especial_d):'','','RELATO DE HECHOS DEL DESPIDO:\n'+(D.hechos||'—'),'',f('Testigos en el momento del despido',D.testigos_despido||'—')].join('\n'))}
${bl('8. PLAZOS DE CADUCIDAD Y SMAC',
[f('Fecha del despido',D.fecha_desp||'—'),'NOTA: Caducidad acción por despido — 20 días hábiles desde el despido (art. 59.3 ET).',f('Fecha papeleta de conciliación',D.papeleta_fecha||'No presentada'),f('Quién presentó la papeleta',D.papeleta_quien||'—'),f('Número expediente SMAC',D.smac_exp||'—'),f('Acto de conciliación celebrado',yn(D.smac_celebrado)),D.smac_celebrado?f('Fecha del acto',D.smac_fecha):'',D.smac_celebrado?f('Resultado',D.smac_resultado):'',D.smac_celebrado?f('Compareció la empresa',D.smac_empresa_comp):'','',f('Fecha más antigua de cantidades reclamadas',D.fecha_presc_cant||'—'),'NOTA: Prescripción de cantidades — 1 año desde que fueron exigibles (art. 59.1 ET).'].join('\n'))}
${bl('9. CALIFICACIÓN DEL DESPIDO Y ACUMULACIÓN',
[f('Calificación',D.nulo?'NULO Y SUBSIDIARIAMENTE IMPROCEDENTE':'IMPROCEDENTE'),D.nulo?f('Causas de nulidad',(D.causas_nulidad||[]).join(' | ')):'',D.nulo?'HECHOS QUE JUSTIFICAN LA NULIDAD:\n'+(D.hechos_nulidad||'—'):'','',f('Acumulación de acción de cantidades al despido',yn(D.acumulacion)),D.acumulacion?f('Observaciones acumulación',D.acum_desc||'—'):''].join('\n'))}
${bl('10. FINIQUITO, ANTICIPOS Y CONVERSACIONES PREVIAS',
[f('La empresa presentó finiquito',yn(D.finiquito)),D.finiquito?f('El/la trabajador/a firmó el finiquito',yn(D.fini_firmo)):'',D.fini_firmo?f('Fecha de firma',D.fini_fecha||'—'):'',D.fini_firmo?f('Importe del finiquito',D.fini_importe||'—'):'',D.fini_firmo?f('Términos del finiquito',D.fini_terminos||'—'):'',D.fini_firmo?f('Firmado bajo presión',yn(D.fini_bajo_presion)):'',D.fini_firmo?f('Con anotación "no conforme"',yn(D.fini_sello)):'','',f('Anticipos o préstamos pendientes',yn(D.anticipo)),D.anticipo?f('Detalle anticipo',D.anticipo_d||'—'):'','',f('Conversaciones previas de acuerdo',yn(D.acuerdo_previo)),D.acuerdo_previo?f('Descripción',D.acdo_desc||'—'):'',f('Posibilidad de acuerdo en conciliación',D.posib_acuerdo||'—')].join('\n'))}
${bl('11. RECLAMACIÓN DE CANTIDADES',
[f('Salarios pendientes',yn(D.sal_pend)),D.sal_pend?D.sal_pend_d:'',f('Pagas extraordinarias pendientes',yn(D.pagas)),D.pagas?D.pagas_d:'',f('Vacaciones no disfrutadas',yn(D.vac)),D.vac?D.vac_d:'',D.vac_presc?'  ⚠ Hay vacaciones de años anteriores — verificar prescripción':'',f('Horas extra/presencia pendientes',yn(D.hpend)),D.hpend?D.hpend_d:'',D.diferencia_salarial?'Diferencias salariales respecto a tablas convenio:\n'+(D.dif_sal_d||'—'):'',f('Otros conceptos',D.otros_cant||'—'),f('TOTAL CANTIDADES (excl. indemnización)',D.total_cant?D.total_cant+' €':'Por determinar'),'NOTA: Prescripción de cantidades — 1 año desde que fueron exigibles (art. 59.1 ET). Verificar cada concepto individualmente.'].join('\n'))}
${bl('12. PRUEBAS Y DOCUMENTACIÓN',
[f('Documentación disponible',(D.pruebas_docs||[]).join(', ')||'—'),f('Pruebas digitales aseguradas',yn(D.pd_aseg)),f('Riesgo eliminación pruebas digitales',yn(D.pd_riesgo)),f('Acceso a correo/sistemas tras despido',yn(D.acc_correo)),f('Diligencia preliminar valorada',yn(D.dilig)),f('Pericial necesaria',yn(D.pericial)),D.pericial?f('Tipo de pericial',D.pericial_d||'—'):'','','TESTIGOS:\n'+twT,'',f('Otras pruebas',D.otras_pruebas||'—'),f('Observaciones internas',D.obs||'—')].join('\n'))}
${bl('13. PREPARACIÓN DEL JUICIO',
[f('Hechos clave para el interrogatorio',D.int_hechos||'—'),f('Puntos débiles a trabajar',D.int_debil||'—'),f('Documentos físicos para el juicio',D.docs_juicio||'—'),f('Preguntas para el interrogatorio a la empresa',D.preg_emp||'—'),f('Riesgos identificados',D.riesgos||'—'),f('Estrategia procesal',D.estrategia||'—'),f('Posibilidad de acuerdo en conciliación',D.posib_acuerdo||'—')].join('\n'))}
${bl('14. PARTES DEMANDADAS',dems.join('\n'))}
${'═'.repeat(65)}
  FIN DE LA FICHA — ${new Date().toLocaleString('es-ES')}
${'═'.repeat(65)}`;

  /* [SF] el visor de artefactos bloquea las descargas: se muestra el texto para copiarlo y, si el navegador lo permite, se descarga */
  SF.exportar(txt,'ficha_demanda_'+(D.nombre||'trabajador').replace(/\s+/g,'_').replace(/[^a-zA-Z0-9_]/g,'')+'_'+new Date().toISOString().slice(0,10)+'.txt','Ficha jurídica completa (formato v5)');
}

render();

window.render_orig=render;function C_reset(){C=0;}
