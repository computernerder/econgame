"use strict";
// Dependencies are supplied by the same read-only model that renders initial HTML.
document.querySelectorAll('form [data-field-context]').forEach(source => {
  const form = source.closest('form');
  const context = JSON.parse(source.textContent);
  const field = name => form.elements.namedItem(name);
  const originalLabels = Object.fromEntries([...form.querySelectorAll('[data-field-label]')].map(node => [node.dataset.fieldLabel,node.textContent]));
  const matches = conditions => Array.isArray(conditions)
    ? conditions.some(matches)
    : Object.entries(conditions).every(([name,allowed]) => (Array.isArray(allowed) ? allowed : [allowed]).includes(field(name)?.value || ''));
  const update = () => {
    const errors = [];
    // DOM order follows dependency order: service, recipient, delivery, target.
    for (const control of [...form.elements]) {
      const rule = context.fields[control.name];
      if (!rule) continue;
      const visible = matches(rule.show || {});
      const label = control.closest('label');
      if (label) label.hidden = !visible;
      control.disabled = !visible;
      control.required = visible && Boolean(rule.required);
      if (rule.options) {
        const previous = control.value;
        const options = rule.options.filter(option => matches(option.when || {}));
        // Duplicate business options can come from different matching departments.
        const unique = [...new Map(options.map(option => [option.value,option])).values()];
        control.replaceChildren();
        for (const choice of unique) {
          const option = document.createElement('option');
          option.value = choice.value; option.textContent = choice.label;
          option.dataset.accountLabel = choice.label;
          control.append(option);
        }
        control.value = unique.some(option => option.value === previous) ? previous : unique[0]?.value || '';
        if (!unique.length) {
          const empty = document.createElement('option');
          empty.value = ''; empty.textContent = 'No eligible options'; empty.disabled = true;
          control.append(empty); control.value = '';
          if (control.required) errors.push(rule.empty);
        }
      }
      const text = label?.querySelector('[data-field-label]');
      if (text) text.textContent = rule.labels?.find(label => matches(label.when))?.text || originalLabels[control.name];
    }
    const notes = form.querySelector('[data-context-notes]');
    notes.replaceChildren();
    for (const note of context.notes || []) {
      if (!matches(note.when || {})) continue;
      const text = document.createElement('p'); text.className = 'fine-print'; text.textContent = note.text;
      notes.append(text);
    }
    const error = form.querySelector('[data-context-errors]');
    error.hidden = errors.length === 0; error.textContent = errors.join(' ');
    for (const button of form.querySelectorAll('[type="submit"]')) button.disabled = errors.length > 0;
    const setup = form.querySelector('[data-context-setup]');
    if (setup) setup.hidden = !errors.length || !['internal','mixed'].includes(field('mode')?.value);
    // Rebuilt account options retain the existing live balance decoration.
    window.fundingBalances?.refresh(form);
  };
  form.addEventListener('change', update);
  update();
});
