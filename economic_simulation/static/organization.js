(() => {
  const panel = document.querySelector('[data-org-chart]');
  const tree = panel?.querySelector('.org-tree');
  if (!tree) return;
  const viewport = panel.querySelector('.org-viewport');
  const zoom = panel.querySelector('#org-zoom');
  const search = panel.querySelector('#org-search');
  const status = panel.querySelector('[data-org-search-status]');
  const toggles = [...tree.querySelectorAll('[data-org-toggle]')];
  const cards = [...tree.querySelectorAll('[data-org-name]')];
  function expand(button, open) {
    const branch = button.closest('.org-branch');
    const children = branch.querySelector(':scope > .org-children');
    if (!children) return;
    children.hidden = !open;
    button.setAttribute('aria-expanded', String(open));
    button.setAttribute('aria-label', `${open ? 'Collapse' : 'Expand'} branch below ${button.closest('.org-node').querySelector('.org-title').textContent}`);
    button.firstElementChild.textContent = open ? '−' : '+';
  }
  toggles.forEach(button => button.addEventListener('click', () => expand(button, button.getAttribute('aria-expanded') !== 'true')));
  panel.querySelector('[data-org-expand]').addEventListener('click', () => toggles.forEach(button => expand(button, true)));
  panel.querySelector('[data-org-collapse]').addEventListener('click', () => toggles.forEach(button => expand(button, false)));
  function setZoom(value) {
    [...tree.classList].filter(name => name.startsWith('org-zoom-')).forEach(name => tree.classList.remove(name));
    tree.classList.add(`org-zoom-${value}`);
    zoom.value = String(value);
  }
  zoom.addEventListener('change', () => setZoom(zoom.value));
  panel.querySelector('[data-org-fit]').addEventListener('click', () => {
    setZoom(100);
    const ratio = (viewport.clientWidth - 12) / tree.offsetWidth;
    setZoom([100, 80, 65, 50, 35].find(value => value / 100 <= ratio) || 35);
    viewport.scrollLeft = 0;
    viewport.scrollTop = 0;
  });
  viewport.scrollLeft = Math.max(0, (tree.offsetWidth - viewport.clientWidth) / 2);
  let previousExpansion = null;
  search.addEventListener('input', () => {
    const query = search.value.trim().toLocaleLowerCase();
    if (query && previousExpansion === null) previousExpansion = toggles.map(button => button.getAttribute('aria-expanded') === 'true');
    if (!query && previousExpansion !== null) {
      toggles.forEach((button, i) => expand(button, previousExpansion[i]));
      previousExpansion = null;
    }
    tree.classList.toggle('org-searching', Boolean(query));
    const matches = [];
    cards.forEach(card => {
      const match = Boolean(query) && card.dataset.orgName.toLocaleLowerCase().includes(query);
      card.classList.toggle('org-match', match);
      if (!match) return;
      matches.push(card);
      let branch = card.closest('.org-branch').parentElement.closest('.org-branch');
      while (branch) {
        const button = branch.querySelector(':scope > .org-node > [data-org-toggle]');
        if (button) expand(button, true);
        branch = branch.parentElement.closest('.org-branch');
      }
    });
    status.textContent = query ? `${matches.length} matching ${matches.length === 1 ? 'card' : 'cards'} in this chart.` : '';
    if (matches[0]) {
      const bounds = matches[0].getBoundingClientRect();
      const frame = viewport.getBoundingClientRect();
      viewport.scrollLeft += bounds.left - frame.left - (viewport.clientWidth - bounds.width) / 2;
      viewport.scrollTop += bounds.top - frame.top - 20;
    }
  });
})();
