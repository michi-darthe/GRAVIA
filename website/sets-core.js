/* Pure set pricing, shared by the configurator and browser checks. Prices are cents. */
(() => {
  function quote(ids, boards, rules) {
    if (!Array.isArray(ids) || ids.length > 4 || new Set(ids).size !== ids.length || ids.some(id => !Object.hasOwn(boards, id))) {
      throw new Error('Bitte wähle unterschiedliche, verfügbare Bretter aus.');
    }
    if (!ids.length) return null;
    const products = Object.keys(boards).filter(id => ids.includes(id));
    const key = [...products].sort().join('|');
    const preset = rules.presets.find(set => [...set.products].sort().join('|') === key);
    const subtotal = products.reduce((sum, id) => sum + boards[id].price, 0);
    const rate = preset ? null : rules.discounts[String(products.length)];
    const discount = preset ? subtotal - preset.price : Math.floor((subtotal * rate + 50) / 100);
    return { id: preset?.id || 'set-custom', title: preset?.title || 'Dein individuelles Gravia Set',
      products, subtotal, discount_rate: rate, discount, total: subtotal - discount, preset: !!preset };
  }
  globalThis.GraviaSetsCore = { quote };
})();
