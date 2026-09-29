(() => {
const filters = document.querySelectorAll('.filter');
filters.forEach(button => button.addEventListener('click', () => {
  filters.forEach(filter => { const active = filter === button; filter.classList.toggle('active', active); filter.setAttribute('aria-pressed', String(active)); });
  document.querySelectorAll('.product').forEach(product => { product.hidden = button.dataset.filter !== 'all' && product.dataset.category !== button.dataset.filter; });
}));
const menuButton = document.querySelector('.menu-toggle');
const navigation = document.querySelector('.header nav');
menuButton.addEventListener('click', () => {
  const open = navigation.classList.toggle('open');
  menuButton.setAttribute('aria-expanded', String(open));
  menuButton.setAttribute('aria-label', open ? 'Menü schließen' : 'Menü öffnen');
  menuButton.textContent = open ? '×' : '☰';
});
navigation.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
  navigation.classList.remove('open'); menuButton.setAttribute('aria-expanded', 'false'); menuButton.setAttribute('aria-label', 'Menü öffnen'); menuButton.textContent = '☰';
}));
document.querySelectorAll('[data-product], [data-business]').forEach(link => link.addEventListener('click', () => {
  document.querySelector('#product-select').value = link.dataset.product || 'Firmenprojekt / Größere Stückzahl';
}));
const form = document.querySelector('#inquiry-form');
const submitButton = form.querySelector('[type="submit"]');
const inquiryStatus = document.querySelector('#inquiry-status');
let pendingRequest = null;
let sending = false;
form.addEventListener('invalid', () => {
  inquiryStatus.dataset.state = 'error';
  inquiryStatus.textContent = 'Bitte prüfe die markierten Felder und gib einen Namen sowie eine gültige E-Mail-Adresse ein.';
}, true);
function requestId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (sending || !form.reportValidity()) return;
  let timeout;
  try {
  const payload = Object.fromEntries(new FormData(form));
  const signature = JSON.stringify(payload);
  if (!pendingRequest || pendingRequest.signature !== signature) {
    pendingRequest = { signature, id: requestId() };
  }
  payload.request_id = pendingRequest.id;
  sending = true;
  submitButton.disabled = true;
  form.setAttribute('aria-busy', 'true');
  inquiryStatus.dataset.state = 'pending';
  inquiryStatus.textContent = 'Deine Anfrage wird gesendet …';
  const controller = new AbortController();
  timeout = setTimeout(() => controller.abort(), 15000);
    const response = await fetch('/api/inquiries', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload), signal: controller.signal,
    });
    let result;
    try { result = await response.json(); }
    catch { throw new Error('Der Anfrageversand ist nicht erreichbar. Bitte versuche es später erneut.'); }
    if (!response.ok) throw new Error(result.error || 'Der Versand ist momentan nicht möglich.');
    if (result.status !== 'accepted' || !result.id) throw new Error('Der Eingang konnte nicht bestätigt werden. Bitte erneut versuchen.');
    inquiryStatus.dataset.state = 'success';
    inquiryStatus.textContent = `Danke! Deine Anfrage wurde gespeichert. Deine Anfragenummer: ${result.id}. Wir melden uns per E-Mail bei dir.`;
    // Preserve any edits made while the previous request was sending.
    if (JSON.stringify(Object.fromEntries(new FormData(form))) === signature) form.reset();
    pendingRequest = null;
  } catch (error) {
    inquiryStatus.dataset.state = 'error';
    inquiryStatus.textContent = error.name === 'AbortError' || error instanceof TypeError
      ? 'Der Eingang konnte wegen eines Verbindungsproblems nicht bestätigt werden. Deine Eingaben bleiben erhalten. Bitte erneut senden; dieselbe Anfrage wird nur einmal gespeichert.'
      : error.message;
  } finally {
    clearTimeout(timeout);
    sending = false;
    submitButton.disabled = false;
    form.removeAttribute('aria-busy');
  }
});
fetch('/api/status').then(response => response.json()).then(result => {
  if (!result.ready && !sending && !inquiryStatus.textContent) {
    inquiryStatus.textContent = 'Der Anfrageversand wird gerade eingerichtet. Bitte versuche es später erneut.';
  }
}).catch(() => {
  if (!sending && !inquiryStatus.textContent) inquiryStatus.textContent = 'Der Anfrageversand ist derzeit nicht erreichbar.';
});

// Personalization preview uses textContent so customer input stays plain text.
const engravingInput = document.querySelector('#engraving-input');
const previewObject = document.querySelector('#preview-object');
if (engravingInput) {
const studioProduct = document.querySelector('#studio-product');
const studioShape = document.querySelector('#studio-mark-shape');
const studioChain = document.querySelector('#studio-mark-chain');
const names = { wood: 'Gravia Wood One', jewelry: 'Gravia Mark', cards: '3D-gedruckte Kartenhalterung', custom: 'Individuelles 3D-Druck-Produkt' };
const updatePreview = () => {
  const product = studioProduct.value;
  const jewelry = product === 'jewelry';
  document.querySelector('#engraving-preview').textContent = engravingInput.value || 'Dein Unikat.';
  document.querySelector('#engraving-count').textContent = `${engravingInput.value.length} / 28`;
  document.querySelector('#studio-mark-options').hidden = !jewelry;
  previewObject.dataset.product = product;
  const photo = document.querySelector('#studio-photo');
  photo.hidden = !['wood', 'jewelry'].includes(product);
  photo.src = jewelry ? `assets/gravia-mark-${studioShape.value}.png` : 'assets/gravia-wood-one.png';
  photo.alt = jewelry ? `${names[product]} – ${studioShape.selectedOptions[0].textContent}` : names[product];
  document.querySelector('#studio-shape').hidden = !photo.hidden;
  document.querySelector('#studio-product-name').textContent = names[product];
  const params = new URLSearchParams({ produkt: product, text: engravingInput.value });
  if (jewelry) { params.set('form', studioShape.value); params.set('kette', studioChain.value); }
  document.querySelector('#use-design').href = `gestalten.html?${params}`;
};
engravingInput.addEventListener('input', updatePreview);
[studioProduct, studioShape, studioChain].forEach(control => control.addEventListener('change', updatePreview));
updatePreview();
}
const header = document.querySelector('.header');
const updateHeader = () => header.classList.toggle('scrolled', window.scrollY > 30);
window.addEventListener('scroll', updateHeader, { passive: true });
updateHeader();
if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.remove('pending'); observer.unobserve(entry.target); }
    });
  }, { threshold: 0.08 });
  document.querySelectorAll('.section-heading, .studio-controls, .steps article, .about-brand-image, .faq-list').forEach(element => {
    element.classList.add('reveal', 'pending'); observer.observe(element);
  });
}
// Escape closes the mobile navigation and returns focus to its button.
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && navigation.classList.contains('open')) {
    menuButton.click(); menuButton.focus();
  }
});

})();
