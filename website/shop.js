(() => {
  // Email confirmation may return tokens in the fragment; login uses the form.
  if (new URLSearchParams(location.hash.slice(1)).has('access_token')) {
    history.replaceState(null, '', location.pathname + location.search);
    location.replace('konto.html');
  }
  const get = id => document.getElementById(id);
  const status = get('shop-status');
  const say = message => { if (status) status.textContent = message; };
  async function api(path, data) {
    const response = await fetch(`/api/${path}`, data === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    const result = await response.json();
    if (!response.ok) { const error = new Error(result.error || 'Bitte versuche es erneut.'); error.status = response.status; throw error; }
    return result;
  }
  const nav = document.querySelector('header nav');
  if (nav) {
    for (const [url, label] of [['konto.html', 'Mein Konto'], ['warenkorb.html', 'Warenkorb']]) {
      const link = document.createElement('a'); link.href = url; link.textContent = label; nav.append(link); link.addEventListener('click', () => { nav.classList.remove('open'); const toggle = document.querySelector('.menu-toggle'); toggle.setAttribute('aria-expanded', 'false'); toggle.setAttribute('aria-label', 'Menü öffnen'); toggle.textContent = '☰'; });
    }
  }
  const add = get('add-to-cart');
  if (add) add.addEventListener('click', async () => {
    if (!window.graviaValidDesign()) return;
    add.disabled = true;
    const design = [get('design-summary').value.replace(/\nStückzahl: [^\n]*/, ''), get('editor-summary')?.value].filter(Boolean).join('\n\n');
    const item = { product: get('personal-product').value, design, quantity: Number(get('personal-quantity').value), engraving: get('personal-input').value.trim() };
    try {
      await api('cart/add', item);
      say('Dein Design liegt im Warenkorb.');
      get('view-cart').hidden = false;
    } catch (error) {
      if (error.status === 401) {
        try { sessionStorage.setItem('gravia-pending-cart', JSON.stringify(item)); location.href = 'konto.html?weiter=warenkorb'; }
        catch { say('Bitte melde dich über „Mein Konto“ an und füge dein Design danach hinzu.'); }
      } else say(error.message);
    } finally { add.disabled = false; }
  });
  async function account() {
    const { user } = await api('account');
    get('account-forms').hidden = !!user;
    get('account-profile').hidden = !user;
    if (user) {
      get('account-name').textContent = user.name;
      get('account-email').textContent = user.email;
      if (new URLSearchParams(location.search).get('weiter') === 'warenkorb') {
        const pending = sessionStorage.getItem('gravia-pending-cart');
        if (pending) {
          await api('cart/add', JSON.parse(pending));
          sessionStorage.removeItem('gravia-pending-cart');
        }
        location.href = 'warenkorb.html';
      }
    }
  }
  for (const action of ['login', 'register']) {
    const form = get(`${action}-form`);
    if (!form) continue;
    const feedback = document.createElement('p');
    feedback.setAttribute('role', 'status');
    feedback.setAttribute('aria-live', 'polite');
    form.querySelector('button').before(feedback);
    const report = message => {
      feedback.textContent = message;
      feedback.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    };
    form.addEventListener('invalid', event => {
      report(event.target.name === 'password' && action === 'register'
        ? 'Bitte gib ein Passwort mit mindestens 12 Zeichen ein.'
        : 'Bitte fülle alle Felder aus und prüfe deine E-Mail-Adresse.');
    }, true);
    form.addEventListener('submit', async event => {
      event.preventDefault(); const button = form.querySelector('button'); const label = button.textContent; button.disabled = true; button.textContent = 'Bitte warten …'; report('Anfrage wird gesendet …');
      try {
        const result = await api(action, Object.fromEntries(new FormData(form)));
        form.reset();
        report(result.confirmation_required ? 'Bitte öffne die Bestätigungs-E-Mail und bestätige deine Adresse. Melde dich danach hier an.' : 'Du bist angemeldet.');
        await account();
      }
      catch (error) { report(error.message); }
      finally { button.disabled = false; button.textContent = label; }
    });
  }
  get('logout')?.addEventListener('click', async () => {
    try { await api('logout', {}); await account(); say('Du bist abgemeldet.'); }
    catch (error) { say(error.message); }
  });
  function node(tag, text, className) {
    const element = document.createElement(tag); element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  function productPicture(item) {
    const picture = node('div', '', 'cart-picture');
    if (item.set) {
      picture.classList.add('cart-set-picture');
      for (const board of item.set.items) picture.append(node('span', board.title.replace('Gravia ', ''), 'cart-set-board'));
      return picture;
    }
    if (item.product === 'wood' || window.graviaBoards?.[item.product] || item.product === 'jewelry') {
      const img = document.createElement('img');
      const shapeName = item.design.match(/^Form: (Herz|Rechteck|Rund)\s*$/m)?.[1];
      const shape = { Herz: 'heart', Rechteck: 'rectangle', Rund: 'round' }[shapeName];
      img.src = item.product !== 'jewelry' ? 'assets/gravia-wood-one.png' : `assets/gravia-mark-${shape || 'all'}.png`;
      img.alt = item.title + (shape ? ` – ${shapeName}` : '');
      img.loading = 'lazy';
      img.width = 300; img.height = 220;
      picture.append(img);
    } else {
      // These products use illustrations on the product overview, too.
      picture.classList.add(`cart-picture-${item.product}`);
      picture.setAttribute('role', 'img');
      picture.setAttribute('aria-label', item.product === 'cards' ? 'Kartenhalter mit Spielkarten – Beispielansicht' : 'Individuelles 3D-Druck-Produkt – beispielhafte Vase');
      const illustration = node('div', '', 'cart-illustration');
      illustration.setAttribute('aria-hidden', 'true');
      if (item.product === 'cards') {
        const cards = node('div', '', 'cart-playing-cards');
        for (const face of ['A ♠', 'K ♥', 'Q ♣']) cards.append(node('span', face));
        illustration.append(cards, node('div', 'LET’S PLAY.', 'cart-card-holder'));
      } else {
        illustration.append(node('div', '', 'cart-vase'));
      }
      picture.append(illustration, node('span', 'Beispielansicht', 'cart-picture-caption'));
    }
    return picture;
  }
  async function cart() {
    const container = get('cart-items');
    try {
      const { items } = await api('cart'); container.replaceChildren();
      get('cart-empty').hidden = items.length > 0;
      get('cart-count').textContent = `${items.reduce((sum, item) => sum + item.quantity, 0)} Stück · ${items.length} Positionen`;
      for (const item of items) {
        const article = node('article', '', 'cart-item');
        const content = node('div', '', 'cart-item-content');
        article.append(productPicture(item), content);
        const money = cents => new Intl.NumberFormat('de-AT', { style: 'currency', currency: 'EUR' }).format(cents / 100);
        const board = window.graviaBoards?.[item.product];
        content.append(node('h2', item.title), node('p', item.set ? `${money(item.set.total)} / Set · ${money(item.set.total * item.quantity)} gesamt · inkl. 20 % USt.` : board ? `${money(board.price)} / Stück · ${money(board.price * item.quantity)} gesamt · inkl. 20 % USt.` : 'Preis auf Anfrage', 'eyebrow'));
        if (board) content.append(node('p', board.dimensions), node('p', 'Beispielbild', 'preview-note'));
        const details = node('details', ''); details.append(node('summary', 'Deine Gestaltung'), node('p', item.design, 'cart-design')); content.append(details);
        if (item.set) {
          content.append(node('p', 'Gravur je Brett enthalten.'));
          const inquire = node('button', 'Dieses Set anfragen ↗', 'text-link');
          inquire.type = 'button';
          inquire.addEventListener('click', () => {
            try { sessionStorage.setItem('gravia-set-draft', JSON.stringify({ items: item.set.items, quantity: item.quantity })); location.href = 'sets.html#anfrage'; }
            catch { say('Bitte öffne die Set-Auswahl und trage deine Gravuren dort ein.'); }
          });
          content.append(inquire);
        }
        const label = node('label', item.set ? 'Anzahl Sets' : 'Stückzahl'); const input = document.createElement('input');
        input.type = 'number'; input.min = '1'; input.max = '1000'; input.step = '1'; input.value = item.quantity;
        label.append(input); content.append(label);
        const save = node('button', 'Menge speichern', 'button dark'); save.type = 'button';
        const remove = node('button', 'Entfernen', 'text-link'); remove.type = 'button';
        async function mutate(path, data) {
          save.disabled = remove.disabled = true;
          try { await api(path, data); await cart(); say('Warenkorb aktualisiert.'); }
          catch (error) { say(error.message); }
          finally { save.disabled = remove.disabled = false; }
        }
        save.addEventListener('click', () => { if (input.reportValidity()) mutate('cart/update', { id: item.id, quantity: Number(input.value) }); });
        remove.addEventListener('click', () => mutate('cart/remove', { id: item.id }));
        const actions = node('div', '', 'cart-actions'); actions.append(save, remove); content.append(actions); container.append(article);
      }
    } catch (error) {
      if (error.status === 401) { get('cart-login').hidden = false; get('cart-empty').hidden = true; }
      else say(error.message);
    }
  }
  if (get('account-forms')) account().catch(error => say(error.message));
  if (get('cart-items')) cart();
})();
