"use strict";

// Account balances come from the ledger; the browser only formats the display.
window.fundingBalances = (() => {
  let accounts = JSON.parse(document.getElementById('funding-accounts').dataset.accounts);
  const selectors = [];
  const note = 'Cash on hand. Reserved project funds and unused credit are excluded. Existing obligations and approval limits still apply.';

  document.querySelectorAll('form[data-action] select:not([multiple]), #scope-select').forEach(select => {
    if (![...select.options].some(option => accounts[option.value]) && !select.hasAttribute('data-funding-account')) return;
    for (const option of select.options) {
      if (accounts[option.value]) option.dataset.accountLabel ??= option.textContent;
    }
    let output = null;
    if (select.id !== 'scope-select') {
      // Keep the field's accessible name stable when its balance changes.
      const label = select.labels?.[0];
      if (label && !select.hasAttribute('aria-label') && !select.hasAttribute('aria-labelledby')) {
        const name = label.querySelector('[data-field-label]')?.textContent || [...label.childNodes].filter(node => node.nodeType === Node.TEXT_NODE)
          .map(node => node.textContent).join(' ').trim();
        if (name) select.setAttribute('aria-label', name);
      }
      output = document.createElement('small');
      output.id = 'funding-balance-' + selectors.length;
      output.className = 'funding-balance';
      output.setAttribute('role', 'status');
      select.setAttribute('aria-describedby', [select.getAttribute('aria-describedby'), output.id].filter(Boolean).join(' '));
      output.title = note;
      select.after(output);
    }
    selectors.push({select, output});
    select.addEventListener('change', render);
  });

  function render() {
    for (const {select, output} of selectors) {
      for (const option of select.options) {
        const account = accounts[option.value];
        if (account && option.dataset.accountLabel) {
          const text = option.dataset.accountLabel + ' · ' + account.label + ' cash';
          if (option.textContent !== text) option.textContent = text;
        }
      }
      if (!output) continue;
      const account = select.disabled ? null : accounts[select.value];
      output.hidden = !account;
      const text = account ? account.name + ' · Cash on hand: ' + account.label : '';
      if (output.textContent !== text) output.textContent = text;
      output.classList.toggle('negative', !!account && account.cash < 0);
      output.dataset.account = account ? select.value : '';
    }
    document.querySelectorAll('[data-account-cash]').forEach(element => {
      const account = accounts[element.dataset.accountCash];
      const text = account ? account.label : 'Unavailable';
      if (element.textContent !== text) element.textContent = text;
      element.classList.toggle('negative', !!account && account.cash < 0);
      element.title = note;
    });
  }

  function review(form) {
    const container = document.getElementById('review-funding');
    container.replaceChildren();
    const ids = new Set();
    if (form) {
      form.querySelectorAll('[data-account-cash], .funding-balance').forEach(element => {
        const id = element.dataset.accountCash || element.dataset.account;
        if (accounts[id]) ids.add(id);
      });
    }
    for (const id of ids) {
      const line = document.createElement('p');
      line.className = 'dialog-cash';
      line.append(accounts[id].name + ' · Cash on hand: ');
      const amount = document.createElement('strong');
      amount.dataset.accountCash = id;
      line.append(amount);
      container.append(line);
    }
    document.getElementById('review-scope-cash').hidden = ids.size > 0;
    render();
  }

  render();
  return {review, refresh:render, update(data) { if (data) { accounts = data; render(); } }};
})();
