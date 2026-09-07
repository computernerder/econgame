"use strict";
// A compact menu keeps every destination reachable without a long horizontal strip.
const navigationToggle = document.getElementById('navigation-toggle');
const mainNavigation = document.getElementById('main-navigation');
if (navigationToggle && mainNavigation) {
  function setNavigation(open) {
    navigationToggle.setAttribute('aria-expanded', String(open));
    mainNavigation.dataset.open = String(open);
  }
  navigationToggle.addEventListener('click', () => setNavigation(navigationToggle.getAttribute('aria-expanded') !== 'true'));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !document.querySelector('dialog[open]') && navigationToggle.getAttribute('aria-expanded') === 'true') {
      setNavigation(false); navigationToggle.focus();
    }
  });
}
// Load existing department settings and matching role staff before any review.
document.querySelectorAll('form[data-action="department_configure"]').forEach(form => {
  const source = form.querySelector('[data-department-context]');
  if (!source) return;
  const context = JSON.parse(source.textContent);
  const field = name => form.elements.namedItem(name);
  const load = () => {
    const provider = field('provider').value, role = field('department').value;
    const company = context.businesses[provider];
    const saved = context.departments[`${provider}:${role}`];
    field('tools').min = company?.industry === 'office' && role === 'real_estate_agent' ? 0 : 1;
    field('tools').value = saved?.tools ?? 1;
    field('regions').value = saved ? saved.regions.join(',') : company?.region || '';
    field('industries').value = saved ? saved.industries.join(',') : company?.industry || '';
    field('leader').value = saved?.leader || '';
    const selected = saved?.staff || [];
    const matching = context.staff.filter(e => e.provider === provider && e.role === role &&
      (['active','joining'].includes(e.status) || selected.includes(e.value)));
    field('staff').replaceChildren();
    for (const employee of matching) {
      const option = document.createElement('option');
      option.value = employee.value; option.textContent = employee.label;
      option.selected = selected.includes(employee.value); field('staff').append(option);
    }
    const name = field('department').selectedOptions[0]?.textContent || 'Service';
    form.querySelector('[data-department-status]').textContent = company
      ? `${saved ? 'Editing saved' : 'New'} ${name} department · ${company.name}${matching.length ? '' : ' · No staff in this role yet; hire staff to provide capacity.'}`
      : 'Choose an employing company to configure its department.';
    const hire = form.querySelector('[data-department-hire]');
    if (hire) {
      hire.hidden = !company;
      hire.href = '/?' + new URLSearchParams({page:'hiring',scope:provider,business_id:provider,role});
    }
  };
  field('provider').addEventListener('change', load);
  field('department').addEventListener('change', load);
  load();
});
// A destination inside a collapsed panel must reveal the actual control.
function revealTask() {
  let id;
  try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
  const target = id && document.getElementById(id);
  if (!target) return;
  for (let node = target; node; node = node.parentElement) {
    if (node.tagName === 'DETAILS') node.open = true;
  }
  target.scrollIntoView({block:'start'});
  // Keyboard users land on the revealed task, not back at the top of the page.
  if (!target.matches('a[href],button,input,select,textarea,summary,[tabindex]')) target.setAttribute('tabindex','-1');
  target.focus({preventScroll:true});
}
window.addEventListener('hashchange', revealTask);
revealTask();

// Conversion fields have no effect on repairs; keep the choice with that task.
document.querySelectorAll('form[data-action="property_work"]').forEach(form => {
  const kind = form.querySelector('[name="kind"]');
  const use = form.querySelector('[name="use"]');
  if (!kind || !use) return;
  const update = () => { use.closest('label').hidden = kind.value !== 'conversion'; };
  kind.addEventListener('change', update); update();
});

// Keep every condition tied to the selected building, including focused links.
document.querySelectorAll('form[data-action="property_work"]').forEach(form => {
  const source = form.querySelector('[data-work-properties]');
  const property = form.querySelector('[name="property_id"]');
  const system = form.querySelector('[name="system"]');
  if (!source || !property || !system) return;
  const contexts = JSON.parse(source.textContent);
  const kind = form.elements.kind, provider = form.elements.provider;
  const repairAll = form.querySelector('[data-repair-all]');
  const originalTitle = form.dataset.title;
  const grid = form.querySelector('[data-work-systems]');
  const plainLabels = Object.fromEntries([...system.options].map(o => [o.value, o.textContent.split(' · ')[0]]));
  const part = (tag, text, className) => {
    const node = document.createElement(tag); node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  function selection() {
    const rows = contexts[property.value]?.systems || [];
    const selected = rows.find(row => row.key === system.value);
    const all = system.value === 'all';
    if (all && kind.value !== 'repair') {kind.value = 'repair'; kind.dispatchEvent(new Event('change', {bubbles:true}));}
    for (const option of kind.options) option.disabled = all && option.value !== 'repair';
    form.dataset.title = all ? 'Repair all · ' + (contexts[property.value]?.name || 'Property') : originalTitle;
    const summary = contexts[property.value]?.repair_summary?.[provider.value === 'outside' ? 'outside' : 'internal'] || '';
    form.querySelector('[data-repair-summary]').textContent = summary;
    repairAll.disabled = !contexts[property.value]?.repair_count;
    grid.querySelectorAll('[data-work-system]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.workSystem === system.value)));
    form.querySelector('[data-work-detail]').textContent = selected
      ? [selected.name, `${selected.condition}/100`, selected.priority, selected.credential, selected.work].filter(Boolean).join(' · ') : all ? 'All eligible systems selected. Systems at 100 or already being worked on are skipped. Ordinary repairs improve condition; they do not guarantee full restoration.' : '';
  }
  function updateProperty() {
    const context = contexts[property.value];
    const rows = context?.systems || [];
    form.querySelector('[data-work-property]').textContent = context ? `${context.name} · As of ${context.date}` : '';
    const empty = form.querySelector('[data-work-empty]');
    empty.hidden = rows.length > 0;
    empty.textContent = context?.empty || 'Choose an owned building to see its current system conditions.';
    for (const option of system.options) option.textContent = rows.find(row => row.key === option.value)?.option || plainLabels[option.value];
    grid.replaceChildren();
    for (const row of rows) {
      const button = part('button', '', 'work-condition-card');
      button.type = 'button'; button.dataset.workSystem = row.key;
      const meter = document.createElement('meter');
      meter.min = 0; meter.max = 100; meter.value = row.condition;
      meter.setAttribute('aria-label', `${row.name} condition`);
      button.append(part('span', row.name, 'work-system-name'), part('strong', `${row.condition}/100`), meter,
        part('span', `${row.priority} · ${row.age} years old`));
      if (row.work) button.append(part('span', row.work, 'work-underway'));
      button.addEventListener('click', () => { system.value = row.key; system.dispatchEvent(new Event('change', {bubbles:true})); });
      grid.append(button);
    }
    selection();
  }
  property.addEventListener('change', updateProperty);
  system.addEventListener('change', selection);
  provider.addEventListener('change', selection);
  repairAll.addEventListener('click', () => {
    system.value = 'all'; system.dispatchEvent(new Event('change', {bubbles:true}));
    form.requestSubmit();
  });
  updateProperty();
});
// Restaurant rosters stay searchable at 30–50 staff without hiding coverage forecasts.
{
  const search = document.getElementById('restaurant-search');
  const role = document.getElementById('restaurant-role');
  const count = document.getElementById('restaurant-roster-count');
  if (search && role && count) {
    const rows = [...document.querySelectorAll('[data-restaurant-name]')];
    const filter = () => {
      const query = search.value.trim().toLocaleLowerCase();
      let shown = 0;
      for (const row of rows) {
        const text = (row.dataset.restaurantName + ' ' + row.dataset.restaurantRole).toLocaleLowerCase();
        row.hidden = Boolean((role.value && role.value !== row.dataset.restaurantRole) || !text.includes(query));
        if (!row.hidden) shown++;
      }
      count.textContent = `${shown} of ${rows.length} employees shown`;
    };
    search.addEventListener('input', filter);
    role.addEventListener('change', filter);
    filter();
  }
}
