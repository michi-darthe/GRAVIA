(() => {
  const get = id => document.getElementById(id);
  const stage = get('product-visual');
  const text = get('personal-text');
  const symbols = get('editor-symbols');
  const active = get('active-element');
  const nodes = { text, symbols };
  const positions = { text: { x: 50, y: 50, rotation: 0 }, symbols: { x: 50, y: 60, rotation: 0 } };
  const palette = [['♡','Herz'],['♥','Gefülltes Herz'],['☆','Stern'],['★','Gefüllter Stern'],['∞','Unendlichkeit'],['✿','Blume'],['☀','Sonne'],['☾','Mond'],['♫','Musik'],['✓','Haken'],['✦','Funkeln'],['⚓','Anker']];
  const status = get('editor-status');
  const detail = document.createElement('textarea');
  detail.readOnly = true; detail.rows = 4; detail.id = 'editor-summary';
  const label = document.createElement('label'); label.textContent = 'Positionen und Symbole'; label.append(detail);
  get('design-summary').parentElement.after(label);
  const message = get('inquiry-form').elements.namedItem('message');
  message.maxLength = 2500;
  function refresh() {
    for (const [key, node] of Object.entries(nodes)) {
      const point = positions[key];
      node.style.left = `${point.x}%`; node.style.top = `${point.y}%`;
      node.style.setProperty('--editor-rotation', `${point.rotation}deg`);
      node.classList.toggle('selected-element', active.value === key);
    }
    const point = positions[active.value];
    for (const axis of ['x', 'y', 'rotation']) {
      get(`editor-${axis}`).value = point[axis];
      get(`editor-${axis}-value`).textContent = `${point[axis]}${axis === 'rotation' ? '°' : ' %'}`;
    }
    symbols.style.fontSize = `${get('symbol-size').value}px`;
    const unavailable = get('personal-product').value === 'jewelry' && !document.querySelector('[name="mark-shape"]:checked');
    symbols.hidden = unavailable || !symbols.textContent;
    get('personal-position').disabled = true;
    detail.value = `Textposition: X ${positions.text.x} %, Y ${positions.text.y} %, Drehung ${positions.text.rotation}°\nSymbole: ${symbols.textContent || 'Keine'}\nSymbolposition: X ${positions.symbols.x} %, Y ${positions.symbols.y} %, Drehung ${positions.symbols.rotation}°, Größe ${get('symbol-size').value} px\nPositionen relativ zur gesamten Produktvorschau.`;
  }
  function defaults() {
    const jewelry = get('personal-product').value === 'jewelry';
    positions.text = { x: 50, y: jewelry ? 65 : 50, rotation: jewelry ? 0 : get('personal-product').value === 'wood' ? -23 : 0 };
    positions.symbols = { x: 50, y: jewelry ? 75 : 62, rotation: positions.text.rotation };
    refresh();
  }
  for (const [symbol, name] of palette) {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = symbol; button.setAttribute('aria-label', `${name} hinzufügen`); button.title = name;
    button.addEventListener('click', () => {
      if (Array.from(symbols.textContent).length >= 6) { status.textContent = 'Maximal sechs Symbole. Entferne die Symbolgruppe, um neu zu beginnen.'; return; }
      symbols.textContent += symbol; active.value = 'symbols'; status.textContent = `${name} hinzugefügt.`; refresh();
    });
    get('symbol-palette').append(button);
  }
  get('clear-symbols').addEventListener('click', () => { symbols.textContent = ''; active.value = 'text'; status.textContent = 'Symbole entfernt.'; refresh(); });
  active.addEventListener('change', refresh);
  for (const axis of ['x', 'y', 'rotation']) get(`editor-${axis}`).addEventListener('input', event => { positions[active.value][axis] = Number(event.target.value); refresh(); });
  get('symbol-size').addEventListener('input', refresh);
  get('center-element').addEventListener('click', () => { positions[active.value].x = 50; positions[active.value].y = get('personal-product').value === 'jewelry' ? 65 : 50; refresh(); });
  const clamp = value => Math.max(10, Math.min(90, Math.round(value)));
  for (const [key, node] of Object.entries(nodes)) {
    let drag = null;
    node.addEventListener('pointerdown', event => {
      if (event.button !== 0) return;
      active.value = key;
      const rect = stage.getBoundingClientRect();
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, start: { ...positions[key] }, width: rect.width, height: rect.height };
      node.setPointerCapture(event.pointerId); node.focus(); refresh(); event.preventDefault();
    });
    node.addEventListener('pointermove', event => {
      if (!drag || drag.id !== event.pointerId) return;
      positions[key].x = clamp(drag.start.x + (event.clientX - drag.x) / drag.width * 100);
      positions[key].y = clamp(drag.start.y + (event.clientY - drag.y) / drag.height * 100);
      refresh();
    });
    for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) node.addEventListener(event, () => { drag = null; });
    node.addEventListener('keydown', event => {
      const movement = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
      if (!movement) return;
      event.preventDefault(); active.value = key;
      positions[key].x = clamp(positions[key].x + movement[0]); positions[key].y = clamp(positions[key].y + movement[1]); refresh();
    });
  }
  get('personal-product').addEventListener('change', defaults);
  document.querySelectorAll('[name="mark-shape"]').forEach(option => option.addEventListener('change', defaults));
  get('reset-design').addEventListener('click', () => { symbols.textContent = ''; get('symbol-size').value = '28'; defaults(); });
  document.querySelector('.personalize-controls').addEventListener('input', refresh);
  document.querySelector('.personalize-controls').addEventListener('change', refresh);
  get('inquiry-form').addEventListener('formdata', event => {
    refresh();
    event.formData.set('message', `${event.formData.get('message')}\n\n${detail.value}`);
  });
  defaults();
})();
