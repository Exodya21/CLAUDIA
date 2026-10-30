const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs');
const vc=new VirtualConsole();const errs=[];vc.on('jsdomError',e=>errs.push(e.message));vc.on('error',e=>errs.push(String(e)));
const dom=new JSDOM('<!doctype html><html><body>'+fs.readFileSync(process.argv[2]||require('path').join(__dirname,'..','super_ficha_laboral.html'),'utf8')+'</body></html>',{runScripts:'dangerously',virtualConsole:vc,pretendToBeVisual:true});
const w=dom.window;w.scrollTo=()=>{};const d=w.document;const $=id=>d.getElementById(id);
const click=el=>{if(!el)throw new Error('no element');el.dispatchEvent(new w.MouseEvent('click',{bubbles:true}));};
const q=s=>d.querySelector(s);
setTimeout(async()=>{
 console.log('errors load',errs);const SF=w.SF,FC=w.FC;
 const r=SF.runTests();r.filter(x=>!x.ok).forEach(x=>console.log('FAIL',x.e,'|',x.c,'|',x.det));console.log('pass',r.filter(x=>x.ok).length,'/',r.length);
 console.log('inicio has C demo:',/Interna que cuidaba a una señora/.test($('vInicio').innerHTML));
 // new blank C
 click(q('[data-new="C"]'));console.log('vC visible',!$('vC').hidden,'vFicha hidden',$('vFicha').hidden);
 for(let s=0;s<=10;s++){FC.step=s;try{FC.render()}catch(e){console.log('blank render',s,e.stack.split('\n').slice(0,3).join(' '))}}
 // interactions on blank
 FC.step=0;FC.render();click(q('[data-op="filtro.abogado"][data-v="si"]'));click(q('[data-op="filtro.estudiar"][data-v="no"]'));console.log('solo contacto steps',d.querySelectorAll('.x-step').length);
 click(q('[data-op="filtro.estudiar"][data-v="si"]'));console.log('steps after',d.querySelectorAll('.x-step').length,'actuado q',!!q('[data-op="filtro.actuado"]'));
 FC.step=2;FC.render();click(q('[data-add="empleadores"]'));const nm=q('[data-p="personas.0.nombre"]');nm.value='Ana Test (ficticia)';nm.dispatchEvent(new w.Event('input',{bubbles:true}));nm.dispatchEvent(new w.Event('change',{bubbles:true}));
 await new Promise(r=>setTimeout(r,5));click(q('[data-tog="personas.0.m.titular"]'));console.log('emp titular auto',FC.st.c.empleadores[0].titular===FC.st.c.personas[0].id);
 const pv=q('[data-p="empleadores.0.dom.prov"]');pv.value='28';pv.dispatchEvent(new w.Event('change',{bubbles:true}));await new Promise(r=>setTimeout(r,5));
 const cpi=q('[data-p="empleadores.0.dom.cp"]');cpi.value='28801';cpi.dispatchEvent(new w.Event('change',{bubbles:true}));await new Promise(r=>setTimeout(r,5));console.log('prov from cp',FC.st.c.empleadores[0].dom.prov);const ms=q('[data-p="empleadores.0.dom.codm"]');console.log('options',ms.options.length,ms.options[1].textContent);ms.value='28005';ms.dispatchEvent(new w.Event('change',{bubbles:true}));await new Promise(r=>setTimeout(r,5));console.log('codm',FC.st.c.empleadores[0].dom.codm);
 FC.step=4;FC.render();click(q('[data-add="periodos"]'));console.log('periodos',FC.st.c.periodos.length,'semanas',FC.st.c.periodos[0].semanas.length);
 click(q('[data-add="periodos.0.semanas.0.turnos"]'));const T0=FC.st.c.periodos[0].semanas[0].turnos[0];console.log('turno dias',T0.dias.join(''));
 const set=async(sel,v)=>{const e=q(sel);e.value=v;e.dispatchEvent(new w.Event('input',{bubbles:true}));e.dispatchEvent(new w.Event('change',{bubbles:true}));await new Promise(r=>setTimeout(r,5));};
 await set('[data-p="periodos.0.semanas.0.turnos.0.e"]','09:00');await set('[data-p="periodos.0.semanas.0.turnos.0.s"]','00:30');await set('[data-p="periodos.0.semanas.0.turnos.0.descMin"]','120');
 click(q('[data-add="periodos.0.semanas.0.turnos"]'));click(q('[data-tday="periodos.0.semanas.0.turnos.1"][data-d="5"]'));click(q('[data-tday="periodos.0.semanas.0.turnos.1"][data-d="6"]'));
 await set('[data-p="periodos.0.semanas.0.turnos.1.e"]','08:00');await set('[data-p="periodos.0.semanas.0.turnos.1.s"]','09:00');
 click(q('[data-add="periodos.0.semanas.0.turnos.1.desc"]'));await set('[data-p="periodos.0.semanas.0.turnos.1.desc.0.e"]','08:30');await set('[data-p="periodos.0.semanas.0.turnos.1.desc.0.s"]','08:45');
 console.log('total UI',q('.fc-total').textContent,'semana ef',FC.semana(FC.st.c.periodos[0].semanas[0]).ef);
 click(q('[data-dup="periodos.0.semanas"]'));const W=FC.semana(FC.st.c.periodos[0].semanas[1]);console.log('dup semana ef',W.ef,'nombre',FC.st.c.periodos[0].semanas[1].nombre);
 FC.step=5;FC.render();click(q('[data-op="sal.fijo"][data-v="no"]'));const ri=q('[data-p="rel.inicio"]');FC.st.c.rel.inicio='2026-01-10';click($('fcMeses'));console.log('meses',FC.st.c.meses.length);
 FC.step=8;FC.render();click(q('[data-add="pruebas"]'));console.log('pruebas',FC.st.c.pruebas.length);
 click(q('[data-del="pruebas.1"]'));console.log('pruebas after del',FC.st.c.pruebas.length);
 click($('fcSave'));console.log('home visible',!$('vInicio').hidden,'list',$('vInicio').querySelectorAll('[data-open]').length);
 // demo
 click(q('[data-demo="C"]'));const sel=$('fcMode');sel.value='abogado';sel.dispatchEvent(new w.Event('change',{bubbles:true}));
 for(let s=0;s<=10;s++){FC.step=s;try{FC.render()}catch(e){console.log('demo render',s,e.stack.split('\n').slice(0,3).join(' '))}}
 FC.step=9;FC.render();click($('fcV5'));console.log('v5 inside',!!q('#vC #pV5'),'emp_n',w.SF.v5Data().emp_n,w.SF.v5Data().nombre);click($('fcV5'));
 FC.step=10;FC.render();console.log('paper len',q('.x-paper').textContent.length,'nuevo',d.querySelectorAll('.fc-nuevo').length);
 const E=FC.evaluate(FC.st);console.log('ALERTS',E.alerts.map(a=>a.nivel+':'+a.titulo).join(' | '));console.log('INC',E.inc.map(i=>i.l).join(', '));console.log('CONTRA',E.contra.map(i=>i.titulo).join(', '));
 console.log('\n===== PAPELETA C =====\n'+FC.papText(FC.pap(FC.st)));
 // legacy A/B still open
 click($('fcSave'));click(q('[data-demo="A"]'));console.log('A opens vFicha',!$('vFicha').hidden,$('vC').hidden);
 console.log('errors end',errs);
},500);
