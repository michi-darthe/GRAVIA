(() => {
  const products = {
    ...window.graviaBoards,
    jewelry: { title: 'Gravia Mark', inquiry: 'Personalisierter Schmuck', description: 'Personalisierbarer Edelstahl-Anhänger mit individueller Gravur. Erhältlich mit Kette als Halskette oder einzeln ohne Kette – in drei verschiedenen Formen.' },
    cards: { title: '3D-gedruckte Kartenhalterung', inquiry: '3D-gedruckte Kartenhalterung', description: 'Dein persönlicher Begleiter für den Spieleabend. Gib deinen Wunschtext ein – die Umsetzung auf dem Kartenhalter klären wir mit dir.' },
    custom: { title: 'Individuelles 3D-Druck-Produkt', inquiry: 'Individuelles 3D-Druck-Produkt', description: 'Deine Idee, individuell gefertigt. Probiere deinen Wunschtext aus und beschreibe unten, welches Produkt du dir vorstellst.' },
  };
  // Prices in cents. Fill in confirmed prices; null keeps the price on request.
  const markPrices = { heart: null, rectangle: null, round: null, chain: null };
  const shapes = { heart: 'Herz', rectangle: 'Rechteck', round: 'Rund' };
  const money = cents => new Intl.NumberFormat('de-AT', { style: 'currency', currency: 'EUR' }).format(cents / 100);
  const selectedShape = () => document.querySelector('[name="mark-shape"]:checked')?.value;
  const withChain = () => document.querySelector('[name="mark-chain"]:checked').value === 'with';
  const product = document.querySelector('#personal-product');
  const input = document.querySelector('#personal-input');
  const font = document.querySelector('#personal-font');
  const second = document.querySelector('#personal-second');
  const size = document.querySelector('#personal-size');
  const position = document.querySelector('#personal-position');
  const alignment = document.querySelector('#personal-align');
  const quantity = document.querySelector('#personal-quantity');
  const preview = document.querySelector('#personal-text');
  const visual = document.querySelector('#product-visual');
  const form = document.querySelector('#inquiry-form');
  const message = form.elements.namedItem('message');
  const inquiryProduct = document.querySelector('#product-select');
  const params = new URLSearchParams(location.search);
  product.value = Object.hasOwn(products, params.get('produkt')) ? params.get('produkt') : 'wood-compact';
  if (Object.hasOwn(shapes, params.get('form'))) document.querySelector(`[name="mark-shape"][value="${params.get('form')}"]`).checked = true;
  if (params.get('kette') === 'with') document.querySelector('[name="mark-chain"][value="with"]').checked = true;
  input.value = (params.get('text') || '').slice(0, 28);
  second.value = (params.get('zeile') || '').slice(0, 28);
  if (Array.from(font.options).some(option => option.value === params.get('schrift'))) font.value = params.get('schrift');
  if (['75','80','85','90','95','100','105','110','115'].includes(params.get('groesse'))) size.value = params.get('groesse');
  if (['left','center','right'].includes(params.get('ausrichtung'))) alignment.value = params.get('ausrichtung');
  const amount = Number(params.get('menge'));
  if (Number.isInteger(amount) && amount >= 1 && amount <= 1000) quantity.value = String(amount);
  // Keep the design in a dedicated read-only field and include it in the existing
  // message payload, so the server's storage and email delivery stay unchanged.
  const summaryLabel = document.createElement('label');
  summaryLabel.textContent = 'Deine Personalisierung';
  const summary = document.createElement('textarea');
  summary.readOnly = true;
  summary.rows = 3;
  summary.id = 'design-summary';
  summaryLabel.append(summary);
  message.parentElement.before(summaryLabel);
  inquiryProduct.parentElement.hidden = true;
  message.required = false;
  message.minLength = 0;
  message.maxLength = 3000;
  message.placeholder = 'Weitere Wünsche, Stückzahl oder Wunschtermin (optional) …';
  function update() {
    const selected = products[product.value];
    document.title = `${selected.title} personalisieren — GRAVIA`;
    document.querySelector('#product-title').textContent = selected.title;
    document.querySelector('#product-description').textContent = selected.description;
    const isMark = product.value === 'jewelry';
    const board = window.graviaBoards[product.value];
    const details = document.querySelector('#board-details');
    details.hidden = !board;
    details.textContent = board ? `${board.dimensions} · ${money(board.price)} / Stück inkl. 20 % USt. · ${quantity.validity.valid ? money(board.price * Number(quantity.value)) + ' gesamt' : 'Stückzahl prüfen'} · Individuelle Gravur inklusive` : '';
    const shape = selectedShape();
    const photo = document.querySelector('#product-photo');
    photo.hidden = !window.graviaBoards[product.value] && !isMark;
    photo.src = isMark ? `assets/gravia-mark-${shape || 'all'}.png` : 'assets/gravia-wood-one.png';
    photo.alt = isMark ? `Gravia Mark – ${shape ? shapes[shape] : 'alle drei Formen'}` : `${selected.title} – Beispielbild`;
    document.querySelector('#product-shape').hidden = !photo.hidden;
    document.querySelector('#mark-options').hidden = !isMark;
    document.querySelector('#engraving-controls').hidden = isMark && !shape;
    preview.hidden = isMark && !shape;
    visual.dataset.shape = shape || 'all';
    const base = shape ? markPrices[shape] : null;
    const total = base !== null && (!withChain() || markPrices.chain !== null)
      ? base + (withChain() ? markPrices.chain : 0) : null;
    document.querySelector('#mark-price').textContent = total === null ? 'Preis auf Anfrage' : `${money(total)} / Stück · ${quantity.validity.valid ? money(total * Number(quantity.value)) + ' gesamt' : 'Stückzahl prüfen'}`;
    document.querySelector('#mark-selection').textContent = shape
      ? `${shapes[shape]} · ${withChain() ? 'mit Kette' : 'ohne Kette'}` : 'Wähle zuerst deine Form.';
    document.querySelector('#personal-continue').textContent = isMark && !shape ? 'Zuerst deine Form wählen ↑' : 'Mit diesem Design anfragen ↗';
    visual.dataset.product = window.graviaBoards[product.value] ? 'wood' : product.value;
    preview.dataset.font = font.value;
    preview.textContent = [input.value || 'Dein Name', second.value].filter(Boolean).join('\n');
    preview.style.scale = Number(size.value) / 100;
    preview.style.marginTop = { upper: '-3%', center: '0', lower: '3%' }[position.value];
    preview.style.textAlign = alignment.value;
    document.querySelector('#size-output').textContent = `${size.value} %`;
    document.querySelector('#personal-count').textContent = `${input.value.length} / 28`;
    inquiryProduct.value = selected.inquiry;
    summary.value = `Produkt: ${selected.title}\nWunschtext: ${input.value.trim() || '(noch offen)'}\nSchriftstil: ${font.selectedOptions[0].textContent}`;
    summary.value += `\nZweite Zeile: ${second.value.trim() || 'Keine'}\nTextgröße: ${size.value} %\nPosition: ${position.selectedOptions[0].textContent}\nAusrichtung: ${alignment.selectedOptions[0].textContent}\nStückzahl: ${quantity.value}`;
    if (isMark) {
      summary.value += `\nForm: ${shape ? shapes[shape] : '(noch offen)'}\nAusführung: ${withChain() ? 'Mit Kette (Halskette)' : 'Ohne Kette'}\nPreis: ${total === null ? 'Auf Anfrage' : money(total)}`;
    }
    if (board) summary.value += `\nMaße: ${board.dimensions}\nStückpreis: ${money(board.price)} inkl. 20 % USt.`;
    summary.rows = isMark || board ? 11 : 8;
    input.setCustomValidity('');
  }
  product.addEventListener('change', () => {
    const url = new URL(location.href);
    url.searchParams.set('produkt', product.value);
    history.replaceState(null, '', url);
    update();
  });
  document.querySelectorAll('[name="mark-shape"], [name="mark-chain"]').forEach(option => option.addEventListener('change', update));
  input.addEventListener('input', update);
  font.addEventListener('change', update);
  [second, size, position, alignment, quantity].forEach(control => control.addEventListener('input', update));
  document.querySelector('#reset-design').addEventListener('click', () => {
    input.value = ''; second.value = ''; font.value = 'classic'; size.value = '100';
    position.value = 'center'; alignment.value = 'center';
    update(); input.focus();
  });
  function validDesign() {
    if (!quantity.reportValidity()) { quantity.focus(); return false; }
    if (product.value === 'jewelry' && !selectedShape()) {
      document.querySelector('#mark-selection').textContent = 'Bitte wähle deine Form, bevor du deine Gravur gestaltest.';
      document.querySelector('[name="mark-shape"]').focus();
      return false;
    }
    input.setCustomValidity(input.value.trim() || document.querySelector('#editor-symbols')?.textContent ? '' : 'Bitte gib deinen Namen oder Wunschtext ein.');
    if (input.reportValidity()) return true;
    input.focus();
    return false;
  }
  window.graviaValidDesign = validDesign;
  window.graviaInquiryDesign = () => ({
    product: product.value, text: input.value.trim(), second: second.value.trim(),
    font: font.value, size: Number(size.value), position: position.value,
    align: alignment.value, quantity: Number(quantity.value),
    shape: selectedShape() || '', chain: withChain() ? 'with' : 'without'
  });
  document.querySelector('#personal-continue').addEventListener('click', event => {
    if (!validDesign()) event.preventDefault();
  });
  form.addEventListener('submit', event => {
    if (!validDesign()) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
  form.addEventListener('formdata', event => {
    event.formData.set('message', `${summary.value}\n\n${message.value}`.trim());
  });
  form.addEventListener('reset', () => { setTimeout(update, 0); });
  update();
})();
