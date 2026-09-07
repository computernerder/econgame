"use strict";
// Drafts are local to this browser tab and campaign. They never issue commands.
(() => {
  const campaign = document.querySelector('meta[name="campaign-session"]')?.content;
  const context = location.pathname + location.search;
  const prefix = 'empire-draft:' + campaign + ':' + context + ':';
  const storage = {
    get(key) { try { return JSON.parse(sessionStorage.getItem(key)); } catch (_) { return null; } },
    set(key, value) { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (_) {} },
    remove(key) { try { sessionStorage.removeItem(key); } catch (_) {} }
  };
  document.querySelectorAll('form[data-action]').forEach((form, index) => {
    if (['advance','new_campaign','open_campaign','copy_campaign'].includes(form.dataset.action)) return;
    const identity = [...form.querySelectorAll('input[type="hidden"]')].map(el => [el.name, el.value]);
    const key = prefix + JSON.stringify([form.dataset.action, form.dataset.title, identity, index]);
    const fields = [...form.elements].filter(el => el.name && !['hidden','password','file','submit'].includes(el.type));
    const original = new Map(fields.map(el => [el, el.type === 'checkbox' ? el.checked : el.multiple ? [...el.selectedOptions].map(o => o.value) : el.value]));
    const restore = values => {
      fields.forEach(el => {
        if (!(el.name in values)) return;
        const value = values[el.name];
        if (el.type === 'checkbox') el.checked = value === true;
        else if (el.multiple) [...el.options].forEach(o => { o.selected = Array.isArray(value) && value.includes(o.value); });
        else if (el.tagName !== 'SELECT' || [...el.options].some(o => o.value === value)) el.value = value;
        if (el.dataset.exactDollars !== undefined && el.value !== el.defaultValue) el.dataset.moneyEdited = 'true';
        el.dispatchEvent(new Event('change', {bubbles:true}));
      });
    };
    const hint = document.createElement('p');
    hint.className = 'draft-status fine-print'; hint.hidden = true;
    const status = document.createElement('span');
    const reset = document.createElement('button'); reset.type = 'button'; reset.className = 'text-link'; reset.textContent = 'Discard draft';
    hint.append(status, document.createTextNode(' '), reset); form.append(hint);
    let restoring = false;
    const saved = storage.get(key);
    if (saved) {
      restore(saved); restore(saved);
      status.textContent = 'Draft restored. Review current costs and eligibility before confirming.'; hint.hidden = false;
    }
    reset.addEventListener('click', () => {
      restoring = true;
      restore(Object.fromEntries(fields.map(el => [el.name, original.get(el)])));
      fields.forEach(el => { delete el.dataset.moneyEdited; });
      restoring = false; storage.remove(key); hint.hidden = true;
    });
    const save = () => {
      if (restoring) return;
      storage.set(key, Object.fromEntries(fields.map(el => [el.name, el.type === 'checkbox' ? el.checked : el.multiple ? [...el.selectedOptions].map(o => o.value) : el.value])));
      status.textContent = 'Draft saved in this tab.'; hint.hidden = false;
    };
    form.addEventListener('input', save); form.addEventListener('change', save);
    document.addEventListener('game-command-complete', event => {
      if (event.detail.command_id === form.dataset.commandId) storage.remove(key);
    });
  });
  // All rows remain in the document and available without JavaScript.
  document.querySelectorAll('table[data-paginate]').forEach(table => {
    const rows = [...(table.tBodies[0]?.rows || [])];
    const size = Number(table.dataset.paginate) || 15;
    if (rows.length <= size) return;
    let page = 0;
    const nav = document.createElement('nav'); nav.className = 'table-pages'; nav.setAttribute('aria-label','Table pages');
    const previous = document.createElement('button'); previous.type = 'button'; previous.className = 'secondary'; previous.textContent = 'Previous';
    const next = document.createElement('button'); next.type = 'button'; next.className = 'secondary'; next.textContent = 'Next';
    const count = document.createElement('span'); count.setAttribute('role','status');
    nav.append(previous, count, next); table.before(nav);
    const show = () => {
      rows.forEach((row,index) => { row.hidden = index < page*size || index >= (page+1)*size; });
      count.textContent = `${page*size+1}–${Math.min(rows.length,(page+1)*size)} of ${rows.length}`;
      previous.disabled = page === 0; next.disabled = (page+1)*size >= rows.length;
    };
    previous.addEventListener('click', () => { page--; show(); });
    next.addEventListener('click', () => { page++; show(); });
    show();
  });
})();
