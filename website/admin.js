(() => {
  const $=id=>document.getElementById(id);
  const node=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
  async function load(){
    $('refresh').disabled=true;$('admin-list').replaceChildren();
    try{const response=await fetch('/api/admin/inquiries');const result=await response.json();if(!response.ok)throw new Error(result.error);
      $('admin-status').textContent=result.items.length?`${result.items.length} Anfragen`:'Noch keine SVG-Anfragen vorhanden.';
      for(const item of result.items){const a=node('article','');a.className='admin-item';a.append(node('h2',`${item.payload.name} · ${item.product} · ${item.quantity} Stück`),node('p',`${new Date(item.created*1000).toLocaleString('de-AT')} · ${item.id}`),node('p',item.payload.email),node('p',(item.payload.design_summary?.texts||[]).join('\n')),node('p',item.payload.message));
        const label=node('label','Bearbeitungsstatus'),select=node('select','');for(const text of ['Neu','In Prüfung','In Produktion','Erledigt']){const option=node('option',text);option.value=text;select.append(option);}select.value=item.status;label.append(select);a.append(label);
        select.onchange=async()=>{select.disabled=true;try{const response=await fetch('/api/admin/status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:item.id,status:select.value})});if(!response.ok)throw new Error('Status konnte nicht gespeichert werden.');item.status=select.value;$('admin-status').textContent='Status gespeichert.';}catch(error){select.value=item.status;$('admin-status').textContent=error.message;}finally{select.disabled=false;}};
        const link=node('a','SVG herunterladen ↓');link.href='/api/admin/svg?id='+encodeURIComponent(item.id);link.className='button dark';a.append(link);$('admin-list').append(a);
      }
    }catch(error){$('admin-status').textContent=error.message||'Anfragen konnten nicht geladen werden.';}finally{$('refresh').disabled=false;}
  }
  $('refresh').onclick=load;load();
})();
