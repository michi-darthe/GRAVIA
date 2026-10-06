(() => {
  'use strict';
  const $ = id => document.getElementById(id), NS = 'http://www.w3.org/2000/svg';
  let products = [], product, objects = [], selected = -1, undo = [], redo = [], drawing = false, drag = null, pending = null;
  // Return to the original simple setup; advanced objects remain in this editor.
  $('back-simple').href = 'produkt.html' + location.search;
  const labels = {text:'Text',rect:'Rechteck',ellipse:'Ellipse',image:'Foto',path:'Freihand',svg:'SVG-Import'};
  const props = ['x','y','width','height','rotation','fill','stroke','strokeWidth','text','font','fontSize','align'];
  const numeric = new Set(['x','y','width','height','rotation','strokeWidth','fontSize']);
  const say = text => { $('status').textContent = text; };
  const copy = value => JSON.parse(JSON.stringify(value));
  const state = () => JSON.stringify({objects, selected});
  function checkpoint() { undo.push(state()); if (undo.length>30) undo.shift(); redo=[]; }
  function restore(serialized) { ({objects,selected}=JSON.parse(serialized)); render(); }
  function clamp(n,min,max) { return Math.max(min,Math.min(max,n)); }
  function svgNode(name, attrs={}, text) { const n=document.createElementNS(NS,name); for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,v); if(text!==undefined)n.textContent=text; return n; }
  function objectNode(o) {
    const g=svgNode('g',{transform:`translate(${o.x} ${o.y}) rotate(${o.rotation})`,fill:o.fill,stroke:o.stroke,'stroke-width':o.strokeWidth});
    const w=o.width,h=o.height;
    if(o.type==='text') {
      const t=svgNode('text',{'font-family':o.font,'font-size':o.fontSize,'text-anchor':o.align});
      o.text.split('\n').forEach((line,i)=>t.append(svgNode('tspan',{x:0,dy:i?o.fontSize*1.2:0},line))); g.append(t);
    } else if(o.type==='rect')g.append(svgNode('rect',{x:-w/2,y:-h/2,width:w,height:h}));
    else if(o.type==='ellipse')g.append(svgNode('ellipse',{cx:0,cy:0,rx:w/2,ry:h/2}));
    else if(o.type==='svg')g.append(svgNode('image',{x:-w/2,y:-h/2,width:w,height:h,href:'data:image/svg+xml;charset=utf-8,'+encodeURIComponent(o.source),preserveAspectRatio:'xMidYMid meet'}));
    else if(o.type==='image')g.append(svgNode('image',{x:-w/2,y:-h/2,width:w,height:h,href:o.src,preserveAspectRatio:'xMidYMid meet'}));
    else g.append(svgNode('path',{d:o.points.map(([x,y],i)=>`${i?'L':'M'}${(x-.5)*w} ${(y-.5)*h}`).join(' '),fill:'none','stroke-linecap':'round','stroke-linejoin':'round'}));
    return g;
  }
  function render(sync=true) {
    if(!product)return;
    const canvas=$('canvas'), [ax,ay,aw,ah]=product.area;
    canvas.replaceChildren(); canvas.setAttribute('viewBox',`0 0 ${product.width} ${product.height}`);
    canvas.style.aspectRatio=`${product.width}/${product.height}`;
    canvas.append(svgNode('rect',{x:ax,y:ay,width:aw,height:ah,fill:'#fcfcf9',stroke:'#6a8d71','stroke-width':product.width/650,'stroke-dasharray':`${product.width/100} ${product.width/150}`,'pointer-events':'none'}));
    let outside=false;
    objects.forEach((o,i)=>{
      const g=objectNode(o); g.dataset.index=i; canvas.append(g);
      const bounds=g.getBBox();
      const rad=o.rotation*Math.PI/180;
      const corners=[[bounds.x,bounds.y],[bounds.x+bounds.width,bounds.y],[bounds.x,bounds.y+bounds.height],[bounds.x+bounds.width,bounds.y+bounds.height]].map(([x,y])=>[o.x+x*Math.cos(rad)-y*Math.sin(rad),o.y+x*Math.sin(rad)+y*Math.cos(rad)]);
      if(corners.some(([x,y])=>x<ax||x>ax+aw||y<ay||y>ay+ah))outside=true;
      if(i===selected)g.append(svgNode('rect',{x:bounds.x-1,y:bounds.y-1,width:Math.max(1,bounds.width)+2,height:Math.max(1,bounds.height)+2,fill:'none',stroke:'#168a62','stroke-width':product.width/500,'stroke-dasharray':`${product.width/120} ${product.width/180}`,'pointer-events':'none'}));
    });
    $('overflow').textContent=outside?'Ein Teil deines Designs liegt außerhalb des Gravurbereichs und wird beim Export abgeschnitten.':'';
    $('layers').replaceChildren();
    objects.map((o,i)=>({o,i})).reverse().forEach(({o,i})=>{const b=document.createElement('button');b.type='button';b.textContent=`${labels[o.type]} ${o.type==='text'?'· '+o.text.slice(0,28):i+1}`;b.setAttribute('aria-pressed',i===selected);b.onclick=()=>{selected=i;render();};$('layers').append(b);});
    $('undo').disabled=!undo.length; $('redo').disabled=!redo.length;
    $('download').disabled=$('send').disabled=!objects.length;
    $('request-summary').textContent=`${product.name} · ${product.width} × ${product.height} mm · ${objects.length} Objekte${product.price_cents ? ` · ${(product.price_cents/100).toLocaleString('de-AT',{style:'currency',currency:'EUR'})} / Stück inkl. 20 % USt.` : ''}`;
    const o=objects[selected];$('properties').disabled=!o;$('no-selection').hidden=!!o;
    if(o && sync){
      $('object-title').textContent=labels[o.type];$('text-options').hidden=o.type!=='text';
      props.forEach(key=>{if(o[key]!==undefined)$(key).value=['fill','stroke'].includes(key)&&o[key]==='none'?'#000000':numeric.has(key)?Math.round(o[key]*100)/100:o[key];});
      $('no-fill').checked=o.fill==='none';
      $('width').disabled=$('height').disabled=o.type==='text';
      $('x').max=$('width').max=product.width;$('y').max=$('height').max=product.height;
    }
  }
  function add(type, extra={}) {
    if(objects.length>=80){say('Maximal 80 Objekte pro Design.');return;}
    checkpoint(); const [x,y,w,h]=product.area;
    objects.push({type,x:x+w/2,y:y+h/2,width:w/3,height:h/3,rotation:0,fill:'#000000',stroke:'#000000',strokeWidth:type==='path'?Math.max(.2,w/300):0,...(type==='text'?{text:'Dein Text',font:'sans-serif',fontSize:Math.max(2,w/12),align:'middle'}:{}),...extra});
    selected=objects.length-1;render();
  }
  function changeProduct() {
    product=products.find(p=>p.id===$('product').value); objects=[];selected=-1;undo=[];redo=[];
    $('dimensions').textContent=`${product.width} × ${product.height} mm · Gravur ${product.area[2]} × ${product.area[3]} mm`;
    $('example-note').textContent=product.confirmed?'':product.dimensions_confirmed?'Brettmaße hinterlegt · Gravurfläche und Position stimmen wir vor der Fertigung ab.':'Beispielmaße – vor der Produktion vom GRAVIA-Team bestätigen lassen.';
    add('text',{text:[new URLSearchParams(location.search).get('text')||'Dein Name',new URLSearchParams(location.search).get('zeile')].filter(Boolean).join('\n').slice(0,500)});undo=[];render();
  }
  document.querySelectorAll('[data-add]').forEach(b=>b.onclick=()=>{if(product)add(b.dataset.add);});
  $('product').onchange=()=>{
    if(objects.length && !window.confirm('Produkt wechseln? Das aktuelle Design wird ersetzt. Lade es vorher als SVG herunter, wenn du es behalten möchtest.')){$('product').value=product.id;return;}
    changeProduct();
  };
  props.forEach(key=>$(key).addEventListener('change',()=>{
    const o=objects[selected];if(!o)return;
    if(!$(key).checkValidity() || (key==='text'&&!$(key).value.trim())){say('Bitte eine gültige Eingabe verwenden.');render();return;}
    checkpoint();o[key]=numeric.has(key)?Number($(key).value):$(key).value;
    if(key==='stroke'&&!o.strokeWidth)o.strokeWidth=.2;render();
  }));
  $('no-fill').onchange=()=>{if(selected<0)return;checkpoint();objects[selected].fill=$('no-fill').checked?'none':$('fill').value;render();};
  $('undo').onclick=()=>{if(undo.length){redo.push(state());restore(undo.pop());}};
  $('redo').onclick=()=>{if(redo.length){undo.push(state());restore(redo.pop());}};
  $('center').onclick=()=>{if(selected<0)return;checkpoint();objects[selected].x=product.area[0]+product.area[2]/2;objects[selected].y=product.area[1]+product.area[3]/2;render();};
  $('duplicate').onclick=()=>{if(selected<0)return;const o=copy(objects[selected]);add(o.type,{...o,x:clamp(o.x+product.width/50,0,product.width),y:clamp(o.y+product.height/50,0,product.height)});};
  $('delete').onclick=()=>{if(selected<0)return;checkpoint();objects.splice(selected,1);selected=Math.min(selected,objects.length-1);render();};
  function reorder(delta){const n=selected+delta;if(selected<0||n<0||n>=objects.length)return;checkpoint();[objects[selected],objects[n]]=[objects[n],objects[selected]];selected=n;render();}
  $('forward').onclick=()=>reorder(1);$('backward').onclick=()=>reorder(-1);
  $('zoom').oninput=()=>{$('canvas').style.width=$('zoom').value+'%';};
  $('draw').onclick=()=>{drawing=!drawing;$('draw').setAttribute('aria-pressed',drawing);$('canvas').classList.toggle('drawing',drawing);say(drawing?'Ziehe auf der Fläche, um eine Linie zu zeichnen.':'Objekte auswählen und verschieben.');};
  function point(event){const p=new DOMPoint(event.clientX,event.clientY).matrixTransform($('canvas').getScreenCTM().inverse());return{x:clamp(p.x,0,product.width),y:clamp(p.y,0,product.height)};}
  $('canvas').onpointerdown=event=>{
    if(!product||event.button!==0)return;const p=point(event);$('canvas').focus();
    if(drawing){drag={id:event.pointerId,points:[p]};}
    else {const target=event.target.closest('[data-index]');selected=target?Number(target.dataset.index):-1;if(selected>=0){checkpoint();drag={id:event.pointerId,start:p,original:copy(objects[selected])};}render();}
    $('canvas').setPointerCapture(event.pointerId);event.preventDefault();
  };
  $('canvas').onpointermove=event=>{
    if(!drag||drag.id!==event.pointerId)return;const p=point(event);
    if(drag.points){if(drag.points.length<2000)drag.points.push(p);let line=$('draft-path');if(!line){line=svgNode('path',{id:'draft-path',fill:'none',stroke:'#000000','stroke-width':Math.max(.2,product.area[2]/300),'pointer-events':'none'});$('canvas').append(line);}line.setAttribute('d',drag.points.map((p,i)=>`${i?'L':'M'}${p.x} ${p.y}`).join(' '));}
    else {objects[selected].x=clamp(drag.original.x+p.x-drag.start.x,0,product.width);objects[selected].y=clamp(drag.original.y+p.y-drag.start.y,0,product.height);render();}
  };
  function finish(event){if(!drag||drag.id!==event.pointerId)return;
    if(drag.points&&drag.points.length>1){const pts=drag.points,x=Math.min(...pts.map(p=>p.x)),y=Math.min(...pts.map(p=>p.y)),w=Math.max(.1,Math.max(...pts.map(p=>p.x))-x),h=Math.max(.1,Math.max(...pts.map(p=>p.y))-y);add('path',{x:x+w/2,y:y+h/2,width:w,height:h,fill:'none',points:pts.map(p=>[(p.x-x)/w,(p.y-y)/h])});}drag=null;render();}
  $('canvas').onpointerup=finish;$('canvas').onpointercancel=()=>{drag=null;render();};
  $('canvas').onkeydown=event=>{const delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[event.key];if(delta&&selected>=0){event.preventDefault();checkpoint();const o=objects[selected],step=event.shiftKey?5:.5;o.x=clamp(o.x+delta[0]*step,0,product.width);o.y=clamp(o.y+delta[1]*step,0,product.height);render();}if(event.key==='Delete')$('delete').click();};
  $('photo').onchange=async()=>{const file=$('photo').files[0];if(!file)return;
    try{if(!['image/png','image/jpeg'].includes(file.type)||file.size>2_000_000)throw new Error('Bitte PNG oder JPG bis 2 MB wählen.');
      if(!product)throw new Error('Bitte zuerst ein Produkt laden.');
      const src=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
      const img=new Image();img.src=src;await img.decode();const w=product.area[2]/2,h=Math.min(product.area[3],w*img.height/img.width);add('image',{src,width:Math.min(w,h*img.width/img.height),height:h});say('Foto hinzugefügt.');
    }catch(error){say(error.message||'Foto konnte nicht geladen werden.');}finally{$('photo').value='';}
  };
  $('svg-import').onchange=async()=>{const file=$('svg-import').files[0];if(!file||!product)return;try{if(file.size>500000)throw new Error('SVG darf maximal 500 KB groß sein.');const result=await api('/api/svg/import',{source:await file.text()});const root=new DOMParser().parseFromString(result.source,'image/svg+xml').documentElement;const box=root.getAttribute('viewBox').replaceAll(',',' ').trim().split(/\s+/).map(Number);const w=product.area[2]/2,h=Math.min(product.area[3],w*box[3]/box[2]);add('svg',{source:result.source,width:Math.min(w,h*box[2]/box[3]),height:h});say('SVG als gemeinsames Objekt importiert.');}catch(error){say(error.message);}finally{$('svg-import').value='';}};
  function design(){return{product:product.id,quantity:Number($('quantity').value),objects:copy(objects)};}
  async function api(url,data){const response=await fetch(url,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const result=await response.json();if(!response.ok)throw new Error(result.error||'Anfrage fehlgeschlagen.');return result;}
  $('download').onclick=async()=>{const button=$('download');button.disabled=true;try{const result=await api('/api/svg/render',design());const url=URL.createObjectURL(new Blob([result.svg],{type:'image/svg+xml'}));const a=document.createElement('a');a.href=url;a.download=result.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);say('SVG erstellt. Bitte Maße, Schriften und Fotoeinstellungen vor der Produktion prüfen.');}catch(error){say(error.message);}finally{button.disabled=false;}};
  $('design-request').onsubmit=async event=>{
    event.preventDefault();if(!objects.length)return;const form=event.target,values=Object.fromEntries(new FormData(form));
    const payload={name:values.name,email:values.email,website:values.website,product:product.inquiry,message:`SVG-Gestaltung: ${product.name}\n${values.message}`.trim(),design:design()};
    const signature=JSON.stringify(payload);if(!pending||pending.signature!==signature)pending={signature,id:crypto.randomUUID()};payload.request_id=pending.id;
    $('send').disabled=true;$('request-status').textContent='Anfrage und SVG werden gespeichert …';
    try{const result=await api('/api/inquiries',payload);$('request-status').textContent=`Anfrage ${result.id.slice(0,8)} mit SVG gespeichert. Wir melden uns per E-Mail.`;}catch(error){$('request-status').textContent=error.message;}finally{$('send').disabled=false;}
  };
  api('/api/svg/products').then(result=>{products=result.products;for(const p of products){const o=document.createElement('option');o.value=p.id;o.textContent=p.name+(p.price_cents ? ` · ${(p.price_cents/100).toLocaleString('de-AT',{style:'currency',currency:'EUR'})} inkl. 20 % USt.` : '');$('product').append(o);}const params=new URLSearchParams(location.search);if(products.some(p=>p.id===params.get('produkt')))$('product').value=params.get('produkt');$('product').disabled=false;changeProduct();const quantity=Number(params.get('menge'));if(Number.isInteger(quantity)&&quantity>=1&&quantity<=1000)$('quantity').value=quantity;const unsupported=(params.has('produkt')&&!products.some(p=>p.id===params.get('produkt')))||(params.has('form')&&params.get('form')!=='rectangle');say(unsupported?'Für diese Produktvariante ist noch keine SVG-Vorlage eingerichtet. Bitte wähle ein verfügbares Produkt; der Anhänger ist hier rechteckig.':'Dein Design wird erst beim Absenden gespeichert. SVG-Download ist jederzeit möglich.');}).catch(error=>say(error.message));
})();
