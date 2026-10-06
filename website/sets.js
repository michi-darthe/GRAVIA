(() => {
  const $ = id => document.getElementById(id);
  const boards = window.graviaBoards;
  const money = cents => new Intl.NumberFormat('de-AT', {style:'currency', currency:'EUR'}).format(cents / 100);
  const controls = new Map();
  let rules, current = null, busy = false, pending = null;
  const node = (tag, text, className) => { const el = document.createElement(tag); el.textContent = text; if (className) el.className = className; return el; };
  const selectedItems = () => [...controls].filter(([, c]) => c.check.checked).map(([product, c]) => ({product, engraving:c.text.value.trim()}));
  function validText(value) { return value.trim().length > 0 && [...value.trim()].length <= 28 && !/[\x00-\x1f]/.test(value); }
  function update() {
    const items = selectedItems();
    current = GraviaSetsCore.quote(items.map(i => i.product), boards, rules);
    for (const c of controls.values()) {
      c.text.disabled = !c.check.checked;
      c.text.required = c.check.checked;
      c.field.hidden = !c.check.checked;
      c.text.setCustomValidity(c.check.checked && !validText(c.text.value) ? 'Bitte gib für dieses Brett einen Gravurtext mit 1–28 Zeichen ein.' : '');
    }
    const title = current?.title || 'Dein Set wartet auf dich.';
    const recognition = !current ? 'Wähle zuerst deine Bretter.' : current.preset
      ? `Automatisch erkannt: ${title}. Für diese Kombination gilt der feste Setpreis.`
      : 'Deine eigene Kombination – der Rabatt richtet sich nach der Anzahl unterschiedlicher Bretter.';
    $('set-title').textContent = title;
    if ($('set-recognition').textContent !== recognition) $('set-recognition').textContent = recognition;
    document.querySelectorAll('[data-set-preset]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.setPreset === (current?.id || 'set-custom'))));
    $('set-selected').replaceChildren(...items.map(i => node('li', boards[i.product].title)));
    $('set-prices').hidden = !current;
    if (current) {
      $('set-subtotal').textContent = money(current.subtotal);
      $('set-discount-label').textContent = current.preset ? 'Set-Ersparnis' : `Rabatt · ${current.discount_rate} %`;
      $('set-discount').textContent = '−' + money(current.discount);
      $('set-total').textContent = money(current.total);
      const quantity = Number($('set-quantity').value);
      $('set-grand-label').textContent = `Gesamt · ${quantity === 1 ? '1 Set' : quantity + ' Sets'}`;
      $('set-grand-total').textContent = $('set-quantity').validity.valid ? money(current.total * quantity) : 'Anzahl prüfen';
    }
    const missing = items.filter(i => !validText(i.engraving)).length;
    $('set-engraving-status').textContent = !items.length ? 'Wähle mindestens ein Brett aus.' : missing
      ? `Noch ${missing} ${missing === 1 ? 'Gravurtext fehlt' : 'Gravurtexte fehlen'}. Jedes Brett braucht einen eigenen Text.`
      : 'Alle Gravurtexte eingetragen · ohne Aufpreis.';
    const ready = !!current && !missing && $('set-quantity').validity.valid && !busy;
    $('set-add').disabled = $('set-send').disabled = !ready;
    // Retain typed engravings when navigating away, including the login round trip.
    try { sessionStorage.setItem('gravia-set-draft', JSON.stringify({items, quantity:Number($('set-quantity').value)})); } catch { /* Optional persistence. */ }
  }
  function validDesign() {
    if (!current) { $('set-status').textContent = 'Bitte wähle mindestens ein Brett aus.'; return false; }
    return $('set-design-form').reportValidity();
  }
  function choose(ids) {
    for (const [id, c] of controls) c.check.checked = ids.includes(id);
    update();
    $('konfigurator').scrollIntoView({behavior:'smooth', block:'start'});
  }
  async function api(path, data) {
    const response = await fetch('/api/' + path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) { const error = new Error(result.error || 'Bitte versuche es erneut.'); error.status = response.status; throw error; }
    return result;
  }
  $('set-design-form').addEventListener('submit', event => event.preventDefault());
  $('set-quantity').addEventListener('input', () => { if (rules) update(); });
  $('set-add').addEventListener('click', async () => {
    if (!validDesign() || busy) return;
    const item = {product:'board-set', items:selectedItems(), quantity:Number($('set-quantity').value)};
    busy = true; update(); $('set-status').textContent = 'Dein Set wird gespeichert …';
    try {
      await api('cart/add', item);
      $('set-status').textContent = 'Dein Set mit allen Gravurtexten liegt im Warenkorb.';
      $('set-cart-link').hidden = false;
    } catch (error) {
      if (error.status === 401) {
        try { sessionStorage.setItem('gravia-pending-cart', JSON.stringify(item)); location.href = 'konto.html?weiter=warenkorb'; }
        catch { $('set-status').textContent = 'Bitte melde dich über „Mein Konto“ an und füge dein Set danach hinzu.'; }
      } else $('set-status').textContent = error.message;
    } finally { busy = false; update(); }
  });
  $('set-inquiry-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (!validDesign() || busy) return;
    const values = Object.fromEntries(new FormData(event.target));
    const data = {name:values.name, email:values.email, website:values.website, message:'Anfrage zu meinem gravierten Brett-Set.\n' + values.message.trim(),
      product:'Personalisiertes Schneidbrett', board_set:selectedItems(), set_quantity:Number($('set-quantity').value)};
    const signature = JSON.stringify(data);
    if (!pending || pending.signature !== signature) pending = {signature, id:crypto.randomUUID()};
    data.request_id = pending.id;
    busy = true; update(); $('set-inquiry-status').textContent = 'Deine Set-Anfrage wird gespeichert …';
    try {
      const result = await api('inquiries', data);
      $('set-inquiry-status').textContent = `Danke! Dein Set mit allen Gravurtexten wurde angefragt. Anfragenummer: ${result.id}. Wir melden uns per E-Mail.`;
    } catch (error) { $('set-inquiry-status').textContent = error.message; }
    finally { busy = false; update(); }
  });
  async function initialize() {
    const response = await fetch('set_catalog.json');
    if (!response.ok) throw new Error('Die Sets konnten nicht geladen werden. Bitte lade die Seite neu.');
    rules = await response.json();
    for (const preset of [...rules.presets, {id:'set-custom', title:'Dein eigenes Set', products:[]}]) {
      const article = node('article', '', 'set-preset');
      article.append(node('h3', preset.title));
      if (preset.products.length) {
        const subtotal = preset.products.reduce((sum, id) => sum + boards[id].price, 0);
        article.append(node('p', preset.products.map(id => boards[id].title.replace('Gravia ', '')).join(' + ')), node('p', `Einzeln ${money(subtotal)}`), node('strong', money(preset.price)), node('p', `${money(subtotal - preset.price)} sparen · inkl. 20 % USt.`, 'set-hint'));
      } else article.append(node('p', 'Kombiniere deine Lieblingsbretter. Fertige Sets erkennen wir automatisch.'), node('p', '5 % Rabatt ab zwei unterschiedlichen Brettern.', 'set-hint'));
      const button = node('button', preset.products.length ? 'Dieses Set gestalten ↗' : 'Selbst zusammenstellen ↗', 'button dark');
      button.type = 'button'; button.dataset.setPreset = preset.id; button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => choose(preset.products)); article.append(button); $('set-presets').append(article);
    }
    for (const [id, board] of Object.entries(boards)) {
      const card = node('div', '', 'set-board');
      const choice = node('label', '', 'set-choice');
      const check = document.createElement('input'); check.type = 'checkbox'; check.id = 'choose-' + id;
      choice.append(check, node('span', board.title));
      card.append(choice, node('p', `${board.dimensions} · ${money(board.price)} inkl. 20 % USt.`));
      const field = node('label', 'Dein Gravurtext · im Preis enthalten'); field.htmlFor = 'engraving-' + id; field.hidden = true;
      const text = document.createElement('input'); text.type = 'text'; text.id = field.htmlFor; text.maxLength = 28; text.placeholder = 'Zum Beispiel: Familie Müller'; text.disabled = true; text.autocomplete = 'off';
      field.append(text); card.append(field); $('set-products').append(card);
      controls.set(id, {check, text, field}); check.addEventListener('change', update); text.addEventListener('input', update);
    }
    const preset = rules.presets.find(p => p.id === new URLSearchParams(location.search).get('set'));
    // A cart inquiry supplies a draft; normal preset links take precedence over an old draft.
    if (preset) for (const [id, c] of controls) c.check.checked = preset.products.includes(id);
    else {
      try {
        const draft = JSON.parse(sessionStorage.getItem('gravia-set-draft'));
        if (Array.isArray(draft?.items)) for (const item of draft.items) {
          const c = controls.get(item.product); if (!c) continue;
          c.check.checked = true; c.text.value = typeof item.engraving === 'string' ? item.engraving.slice(0,28) : '';
        }
        if (Number.isInteger(draft?.quantity) && draft.quantity >= 1 && draft.quantity <= 1000) $('set-quantity').value = draft.quantity;
      } catch { /* Ignore a missing or malformed optional draft. */ }
    }
    $('set-status').textContent = ''; update();
  }
  initialize().catch(error => { $('set-status').textContent = error.message; });
})();
