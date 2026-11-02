(function(){
'use strict';
/* Papeleta en Word (.docx) generada en el navegador, sin librerías.
   Formato acordado por el despacho: Arial 12, justificado, sangría de primera línea 1,24 cm,
   espaciado posterior 8 pt e interlineado 1,5. */
const FC=window.FC,SF=window.SF;
const X=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const eurN=x=>SF.eur(x).replace(' €','');
const n1=x=>{const r=Math.round(x*10)/10;return (Number.isInteger(r)?String(r):r.toFixed(1)).replace('.',',');};
/* runs: texto con ⟦huecos⟧ resaltados en amarillo */
function runs(text,o){o=o||{};const out=[];String(text).split(/(⟦[^⟧]*⟧)/).forEach(part=>{if(!part)return;const hole=/^⟦.*⟧$/.test(part);const t=hole?'['+part.slice(1,-1)+']':part;
 out.push(`<w:r><w:rPr>${o.b?'<w:b/>':''}${hole||o.hl?'<w:highlight w:val="yellow"/>':''}${o.sz?`<w:sz w:val="${o.sz}"/><w:szCs w:val="${o.sz}"/>`:''}</w:rPr><w:t xml:space="preserve">${X(t)}</w:t></w:r>`);});return out.join('');}
const par=(inner,ppr)=>`<w:p>${ppr?`<w:pPr>${ppr}</w:pPr>`:''}${inner}</w:p>`;
const CENTER='<w:jc w:val="center"/><w:ind w:firstLine="0"/>';
const NOIND='<w:ind w:firstLine="0"/>';
const MARK='[Variante nueva: pendiente de aprobación] ';
function para(x){if(x.lista)return x.lista.map(i=>par(runs('•  '+i),'<w:ind w:left="703" w:firstLine="0"/>')).join('');
 return par((x.st==='nuevo'?runs(MARK,{hl:1,b:1}):'')+runs(x.text,{b:x.bold}));}
function cell(t,o){o=o||{};return `<w:tc><w:tcPr><w:tcW w:w="${o.w||2000}" w:type="dxa"/></w:tcPr>${par(runs(t,{b:o.b,sz:20}),`<w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="${o.r?'right':'left'}"/>`)}</w:tc>`;}
function table(head,rows,ws){const B='<w:tblBorders>'+['top','left','bottom','right','insideH','insideV'].map(k=>`<w:${k} w:val="single" w:sz="4" w:space="0" w:color="808080"/>`).join('')+'</w:tblBorders>';
 const tr=(cs,b)=>`<w:tr>${cs.map((c,i)=>cell(c,{b,r:i>0,w:ws[i]})).join('')}</w:tr>`;
 return `<w:tbl><w:tblPr><w:tblW w:w="${ws.reduce((a,b)=>a+b,0)}" w:type="dxa"/><w:jc w:val="center"/>${B}<w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>${ws.map(w=>`<w:gridCol w:w="${w}"/>`).join('')}</w:tblGrid>${tr(head,true)}${rows.map(r=>tr(r,r._b)).join('')}</w:tbl>`+par('','<w:spacing w:after="0"/>');}
function ftab(t){const W=t.w,N=W.length,TW=W.reduce((a,b)=>a+b,0);
 const tc=(txt,o)=>`<w:tc><w:tcPr><w:tcW w:w="${o.span?TW:W[o.i]}" w:type="dxa"/>${o.span?`<w:gridSpan w:val="${N}"/>`:''}${o.sh?'<w:shd w:val="clear" w:color="auto" w:fill="D9D9D9"/>':''}</w:tcPr>${par(runs(txt,{b:o.b,sz:22}),`<w:spacing w:after="0" w:line="264" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="${o.jc||'left'}"/>`)}</w:tc>`;
 const B='<w:tblBorders>'+['top','left','bottom','right','insideH','insideV'].map(k=>`<w:${k} w:val="single" w:sz="4" w:space="0" w:color="000000"/>`).join('')+'</w:tblBorders>';
 const rows=[`<w:tr>${tc(t.titulo,{span:1,b:1})}</w:tr>`,`<w:tr>${t.head.map((h,i)=>tc(h,{i,b:1,sh:1,jc:'center'})).join('')}</w:tr>`].concat(t.rows.map(r=>`<w:tr>${r.map((v,i)=>tc(v,{i,jc:i?'right':'left'})).join('')}</w:tr>`),[`<w:tr>${t.foot.map((v,i)=>tc(v,{i,b:1,sh:1,jc:i===N-1?'right':(i===0?'left':'center')})).join('')}</w:tr>`]);
 return `<w:tbl><w:tblPr><w:tblW w:w="${TW}" w:type="dxa"/><w:jc w:val="center"/>${B}<w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>${W.map(w=>`<w:gridCol w:w="${w}"/>`).join('')}</w:tblGrid>${rows.join('')}</w:tbl>`+par('','<w:spacing w:after="0"/>');}
const t1=G=>ftab(FC.tabla1(G));
FC.tabHtml=(t,inline)=>{const N=t.head.length;const bd='border:1px solid #000;padding:3px 8px;';const gr='background:#d9d9d9;';const R=v=>X(v).replace(/⟦([^⟧]*)⟧/g,'<mark style="background:yellow">[$1]</mark>');
 return `<table class="fc-tab" style="border-collapse:collapse;${inline?'font-family:Arial;font-size:11pt;margin:0 auto 8pt;':''}"><tr><td colspan="${N}" style="${bd}font-weight:bold">${R(t.titulo)}</td></tr><tr>${t.head.map(h=>`<td style="${bd}${gr}font-weight:bold;text-align:center">${X(h)}</td>`).join('')}</tr>${t.rows.map(r=>`<tr>${r.map((v,i)=>`<td style="${bd}text-align:${i?'right':'left'};white-space:nowrap">${R(v)}</td>`).join('')}</tr>`).join('')}<tr>${t.foot.map((v,i)=>`<td style="${bd}${gr}font-weight:bold;text-align:${i===N-1?'right':(i?'center':'left')};white-space:nowrap">${X(v)}</td>`).join('')}</tr></table>`;};
function tot(G){const t=FC.totales(G);const W=[6400,2600];
 const tc=(txt,o)=>`<w:tc><w:tcPr><w:tcW w:w="${o.span?W[0]+W[1]:W[o.i||0]}" w:type="dxa"/>${o.span?'<w:gridSpan w:val="2"/>':''}${o.sh?'<w:shd w:val="clear" w:color="auto" w:fill="D9D9D9"/>':''}</w:tcPr>${par(runs(txt,{b:o.b,sz:o.sz||22}),`<w:spacing w:after="0" w:line="276" w:lineRule="auto"/><w:ind w:firstLine="0"/><w:jc w:val="${o.jc||'left'}"/>`)}</w:tc>`;
 const R=c=>`<w:tr>${c}</w:tr>`;const B='<w:tblBorders>'+['top','left','bottom','right','insideH','insideV'].map(k=>`<w:${k} w:val="single" w:sz="4" w:space="0" w:color="000000"/>`).join('')+'</w:tblBorders>';
 const rows=[R(tc('TOTALES CANTIDADES RECLAMADAS',{span:1,b:1,sz:26,jc:'center',sh:1}))].concat(t.lineas.map(([l,v])=>R(tc(l,{i:0})+tc(eurN(v)+' €',{i:1,jc:'right'}))),
  [R(tc('Total Principal',{i:0,b:1,jc:'right',sh:1})+tc(eurN(t.principal)+' €',{i:1,b:1,jc:'right',sh:1})),R(tc('Mora 10%',{i:0,jc:'right'})+tc(eurN(t.mora)+' €',{i:1,jc:'right'})),R(tc('Total Pendiente…',{i:0,b:1,jc:'right',sh:1})+tc(eurN(t.total)+' €',{i:1,b:1,jc:'right',sh:1})),R(tc(t.letras,{span:1,jc:'center'}))]);
 return `<w:tbl><w:tblPr><w:tblW w:w="${W[0]+W[1]}" w:type="dxa"/><w:jc w:val="center"/>${B}<w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>${W.map(w=>`<w:gridCol w:w="${w}"/>`).join('')}</w:tblGrid>${rows.join('')}</w:tbl>`+par('','<w:spacing w:after="0"/>');}
const t2=G=>ftab(FC.tabla2(G));
FC.docXml=G=>{const B=[];
 G.head.forEach(h=>{if(h.k==='enc')B.push(par(runs(h.text,{b:1,hl:h.st==='pend'}),CENTER));else if(h.k==='dice')B.push(par(runs(h.text,{b:1}),NOIND));else B.push(para(h));
  if(h.k==='enc')B.push(par('',CENTER));});
 B.push(par(runs('H E C H O S',{b:1}),CENTER));
 G.hechos.forEach(h=>{B.push(par(runs(`${h.n}.- ${h.titulo}`,{b:1}),NOIND));h.paras.forEach(x=>{if(x.t)B.push(ftab(x.t));else if(x.tabla==='T1')B.push(t1(G));else if(x.tabla==='T2')B.push(t2(G));else if(x.tabla==='TOT')B.push(tot(G));else B.push(para(x));});});
 return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>${B.join('')}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1418" w:right="1418" w:bottom="1418" w:left="1701" w:header="709" w:footer="709" w:gutter="0"/></w:sectPr></w:body></w:document>`;};
const STYLES=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/><w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="es-ES"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:before="0" w:after="160" w:line="360" w:lineRule="auto"/><w:ind w:firstLine="703"/><w:jc w:val="both"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style><w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style></w:styles>`;
const CT=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>`;
const RELS=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`;
const DRELS=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`;
/* zip sin compresión */
const CRC=(()=>{const t=new Uint32Array(256);for(let n=0;n<256;n++){let c=n;for(let k=0;k<8;k++)c=c&1?0xEDB88320^(c>>>1):c>>>1;t[n]=c>>>0;}return t;})();
const crc32=b=>{let c=0xFFFFFFFF;for(let i=0;i<b.length;i++)c=CRC[(c^b[i])&255]^(c>>>8);return (c^0xFFFFFFFF)>>>0;};
const utf8=str=>{if(typeof TextEncoder!=='undefined')return new TextEncoder().encode(str);const b=unescape(encodeURIComponent(str));const u=new Uint8Array(b.length);for(let i=0;i<b.length;i++)u[i]=b.charCodeAt(i);return u;};
function zip(files){const enc={encode:utf8};const parts=[],cent=[];let off=0;
 files.forEach(([name,str])=>{const nb=enc.encode(name),db=enc.encode(str),cr=crc32(db);
  const h=new DataView(new ArrayBuffer(30));h.setUint32(0,0x04034b50,true);h.setUint16(4,20,true);h.setUint16(6,0x0800,true);h.setUint16(8,0,true);h.setUint16(10,0,true);h.setUint16(12,0x21,true);h.setUint32(14,cr,true);h.setUint32(18,db.length,true);h.setUint32(22,db.length,true);h.setUint16(26,nb.length,true);h.setUint16(28,0,true);
  parts.push(new Uint8Array(h.buffer),nb,db);
  const c=new DataView(new ArrayBuffer(46));c.setUint32(0,0x02014b50,true);c.setUint16(4,20,true);c.setUint16(6,20,true);c.setUint16(8,0x0800,true);c.setUint16(10,0,true);c.setUint16(12,0,true);c.setUint16(14,0x21,true);c.setUint32(16,cr,true);c.setUint32(20,db.length,true);c.setUint32(24,db.length,true);c.setUint16(28,nb.length,true);c.setUint32(42,off,true);
  cent.push(new Uint8Array(c.buffer),nb);off+=30+nb.length+db.length;});
 const cs=cent.reduce((a,b)=>a+b.length,0);const e=new DataView(new ArrayBuffer(22));e.setUint32(0,0x06054b50,true);e.setUint16(8,files.length,true);e.setUint16(10,files.length,true);e.setUint32(12,cs,true);e.setUint32(16,off,true);
 const all=parts.concat(cent,[new Uint8Array(e.buffer)]);const out=new Uint8Array(all.reduce((a,b)=>a+b.length,0));let p=0;all.forEach(b=>{out.set(b,p);p+=b.length;});return out;}
FC.totHtml=(G,inline)=>{const t=FC.totales(G);const bd=inline?'border:1px solid #000;':'';const st=(o)=>`style="${bd}padding:3px 8px;${o||''}"`;const gr='background:#d9d9d9;';
 return `<table class="fc-tot" style="border-collapse:collapse;${inline?'font-family:Arial;font-size:11pt;margin:0 auto 8pt;':''}"><tr><td colspan="2" ${st(gr+'text-align:center;font-weight:bold;font-size:'+(inline?'13pt':'1.1em'))}>TOTALES CANTIDADES RECLAMADAS</td></tr>${t.lineas.map(([l,v])=>`<tr><td ${st()}>${X(l)}</td><td ${st('text-align:right;white-space:nowrap')}>${eurN(v)} €</td></tr>`).join('')}<tr><td ${st(gr+'text-align:right;font-weight:bold')}>Total Principal</td><td ${st(gr+'text-align:right;font-weight:bold;white-space:nowrap')}>${eurN(t.principal)} €</td></tr><tr><td ${st('text-align:right')}>Mora 10%</td><td ${st('text-align:right;white-space:nowrap')}>${eurN(t.mora)} €</td></tr><tr><td ${st(gr+'text-align:right;font-weight:bold')}>Total Pendiente…</td><td ${st(gr+'text-align:right;font-weight:bold;white-space:nowrap')}>${eurN(t.total)} €</td></tr><tr><td colspan="2" ${st('text-align:center')}>${X(t.letras)}</td></tr></table>`;};
FC._pack=(doc,styles)=>zip([['[Content_Types].xml',CT],['_rels/.rels',RELS],['word/_rels/document.xml.rels',DRELS],['word/document.xml',doc],['word/styles.xml',styles]]);
FC.docx=G=>{const doc=FC.docXml(G);FC._lastDocXml=doc;FC._lastStyles=STYLES;return zip([['[Content_Types].xml',CT],['_rels/.rels',RELS],['word/_rels/document.xml.rels',DRELS],['word/document.xml',doc],['word/styles.xml',STYLES]]);};
/* HTML con el mismo formato, para «copiar con formato» y pegar en Word */
FC.papHtml=G=>{const st='font-family:Arial;font-size:12pt;line-height:150%;text-align:justify;text-indent:1.24cm;margin:0 0 8pt 0';const c0='font-family:Arial;font-size:12pt;line-height:150%;text-align:center;font-weight:bold;margin:0 0 8pt 0';const ni=st.replace('text-indent:1.24cm','text-indent:0');
 const R=t=>X(t).replace(/⟦([^⟧]*)⟧/g,'<span style="background:yellow">[$1]</span>');
 const P=x=>x.lista?x.lista.map(i=>`<p style="${ni};margin-left:1.24cm">•&nbsp;&nbsp;${R(i)}</p>`).join(''):`<p style="${st}${x.bold?';font-weight:bold':''}">${x.st==='nuevo'?`<b style="background:yellow">${MARK}</b>`:''}${R(x.text)}</p>`;
 const tb=(h,rows)=>`<table style="border-collapse:collapse;font-family:Arial;font-size:10pt;margin:0 auto 8pt">${[h].concat(rows).map((r,i)=>`<tr>${r.map((v,j)=>`<td style="border:1px solid #808080;padding:2px 6px;text-align:${j?'right':'left'};${i===0||i===rows.length?'font-weight:bold':''}">${R(v)}</td>`).join('')}</tr>`).join('')}</table>`;
 const c=G.c;const T1=G.T1.rows.filter(r=>!r.presc||c.abg.incluirPrescritos).map(r=>[FC.mesTxt(r.y,r.m),r.deb!=null?eurN(r.deb)+' €':'⟦sin calcular⟧',r.perc!=null?eurN(r.perc)+' €':'⟦sin datos⟧',r.dif!=null?eurN(r.dif)+' €':'—']).concat([['TOTAL','','',eurN(G.T1.total)+' €']]);
 const T2=G.T2.rows.filter(r=>!r.anterior||c.abg.incluirPrescritos).map(r=>[String(r.y),r.base!=null?eurN(r.base)+' €':'⟦SMI sin verificar⟧',n1(r.dev),String(r.disfr),r.imp!=null?eurN(r.imp)+' €':'—']).concat([['TOTAL','','','',eurN(G.T2.total)+' €']]);
 const B=[];G.head.forEach(h=>{if(h.k==='enc')B.push(`<p style="${c0}">${R(h.text)}</p>`);else if(h.k==='dice')B.push(`<p style="${ni};font-weight:bold">${R(h.text)}</p>`);else B.push(P(h));});
 B.push(`<p style="${c0}">H E C H O S</p>`);G.hechos.forEach(h=>{B.push(`<p style="${ni};font-weight:bold">${X(h.n+'.- '+h.titulo)}</p>`);h.paras.forEach(x=>B.push(x.t?FC.tabHtml(x.t,true):x.tabla==='TOT'?FC.totHtml(G,true):x.tabla==='T1'?FC.tabHtml(FC.tabla1(G),true):x.tabla==='T2'?FC.tabHtml(FC.tabla2(G),true):P(x)));});
 return B.join('');};
})();
(function(){
/* La ficha completa (preguntas y respuestas) en Word */
const FC=window.FC;
const X=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const R=(t,o)=>{o=o||{};return String(t).split('\n').map((line,i)=>`${i?'<w:r><w:br/></w:r>':''}<w:r><w:rPr>${o.b?'<w:b/>':''}${o.i?'<w:i/>':''}${o.c?`<w:color w:val="${o.c}"/>`:''}${o.sz?`<w:sz w:val="${o.sz}"/><w:szCs w:val="${o.sz}"/>`:''}</w:rPr><w:t xml:space="preserve">${X(line)}</w:t></w:r>`).join('');};
const P=(inner,ppr)=>`<w:p>${ppr?`<w:pPr>${ppr}</w:pPr>`:''}${inner}</w:p>`;
const BRD='<w:tblBorders>'+['top','left','bottom','right','insideH','insideV'].map(k=>`<w:${k} w:val="single" w:sz="4" w:space="0" w:color="A6A6A6"/>`).join('')+'</w:tblBorders>';
const TC=(t,w,o)=>{o=o||{};return `<w:tc><w:tcPr><w:tcW w:w="${w}" w:type="dxa"/>${o.sh?`<w:shd w:val="clear" w:color="auto" w:fill="${o.sh}"/>`:''}</w:tcPr>${P(R(t,o),'<w:spacing w:before="20" w:after="20"/>')}</w:tc>`;};
const TBL=(rows,ws)=>`<w:tbl><w:tblPr><w:tblW w:w="${ws.reduce((a,b)=>a+b,0)}" w:type="dxa"/>${BRD}<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="90" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>${ws.map(w=>`<w:gridCol w:w="${w}"/>`).join('')}</w:tblGrid>${rows.join('')}</w:tbl>`+P('','<w:spacing w:after="0"/>');
FC.fichaXml=M=>{const B=[];let qa=[];const W=9000;
 const flush=()=>{if(!qa.length)return;B.push(TBL(qa.map(([q,a,n])=>`<w:tr><w:trPr><w:cantSplit/></w:trPr>${TC(q,3600,{b:1,sh:'F2F2F2'})}${TC((a&&a.trim())?a:'—'+(n?'':''),5400,{c:(a&&a.trim())?null:'C00000'})}</w:tr>`+(n?`<w:tr>${TC('Explicación',3600,{i:1,sh:'F2F2F2'})}${TC(n,5400,{i:1})}</w:tr>`:'')),[3600,5400]));qa=[];};
 M.forEach(x=>{if(x.t==='qa'){qa.push([x.q,x.a,x.n]);return;}flush();
  if(x.t==='title')B.push(P(R(x.text,{b:1,sz:30}),'<w:jc w:val="center"/><w:spacing w:after="60"/>'));
  else if(x.t==='meta')B.push(P(R(x.text,{sz:20,c:'595959'}),'<w:jc w:val="center"/><w:spacing w:after="240"/>'));
  else if(x.t==='h1')B.push(P(R(x.text,{b:1,sz:26,c:'0B5D4B'}),'<w:keepNext/><w:spacing w:before="360" w:after="120"/><w:pBdr><w:bottom w:val="single" w:sz="8" w:space="2" w:color="0B5D4B"/></w:pBdr>'));
  else if(x.t==='h2')B.push(P(R(x.text,{b:1,sz:23}),'<w:keepNext/><w:spacing w:before="200" w:after="80"/>'));
  else if(x.t==='h3')B.push(P(R(x.text,{b:1,i:1,sz:22}),'<w:keepNext/><w:spacing w:before="140" w:after="60"/>'));
  else if(x.t==='p')B.push(P(R(x.text,{c:x.warn?'C00000':null}),'<w:spacing w:after="80"/>'));
  else if(x.t==='tab'){const n=x.head.length,ws=Array(n).fill(Math.floor(W/n));B.push(TBL([`<w:tr><w:trPr><w:tblHeader/></w:trPr>${x.head.map((h,i)=>TC(h,ws[i],{b:1,sh:'D9D9D9',sz:18})).join('')}</w:tr>`].concat(x.rows.map(r=>`<w:tr>${r.map((v,i)=>TC(v,ws[i],{sz:18})).join('')}</w:tr>`)),ws));}});
 flush();
 return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>${B.join('')}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1418" w:header="709" w:footer="709" w:gutter="0"/></w:sectPr></w:body></w:document>`;};
FC.FICHA_STYLES=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial" w:cs="Arial"/><w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:val="es-ES"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:before="0" w:after="0" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style><w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style></w:styles>`;
})();

FC.fichaDocx=M=>{const doc=FC.fichaXml(M);FC._lastFichaXml=doc;return FC._pack(doc,FC.FICHA_STYLES);};
