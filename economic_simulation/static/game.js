"use strict";
// randomUUID requires HTTPS, but getRandomValues also works on a private HTTP LAN.
function commandId() {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
const token = document.querySelector('meta[name="game-token"]').content;
const campaign_session = document.querySelector('meta[name="campaign-session"]')?.content;
const revision = Number(document.querySelector('meta[name="revision"]').content);
const scope = document.querySelector('meta[name="scope"]').content;
const notice = document.getElementById('notice');
const actionDialog = document.getElementById('action-dialog');
const advanceDialog = document.getElementById('advance-dialog');
let pending = null;
let busy = false;

function recoveryError(data, fallback) {
  const error = new Error(typeof data.detail === 'string' ? data.detail : fallback);
  error.recoveryLinks = Array.isArray(data.recovery_links) ? data.recovery_links : [];
  return error;
}

function appendRecoveryLinks(container, links = []) {
  if (!links.length) return;
  const nav = document.createElement('nav');
  nav.className = 'recovery-links';
  nav.setAttribute('aria-label', 'Resolve this blocker');
  links.forEach(link => {
    let control;
    if (link.behavior === 'refresh' || link.behavior === 'time') {
      control = document.createElement('button');
      control.type = 'button';
      control.addEventListener('click', () => {
        if (link.behavior === 'refresh') location.reload();
        else {
          if (actionDialog.open) actionDialog.close();
          const pause = document.getElementById('cancel-skip');
          if (pause) { if (advanceDialog.open) advanceDialog.close(); pause.scrollIntoView({block:'center'}); pause.focus(); }
          else location.reload();
        }
      });
    } else {
      // Only locally generated game routes are accepted; text is never HTML.
      if (typeof link.url !== 'string' || !link.url.startsWith('/?')) return;
      control = document.createElement('a');
      control.href = link.url;
    }
    control.className = 'secondary';
    control.textContent = link.label + ' →';
    nav.append(control);
  });
  container.append(nav);
}

function message(text, error = false, links = []) {
  // Older sessions can contain notices saved before whole-dollar display.
  notice.textContent = text.replace(/([−-]?)\$([−-]?)(\d[\d,]*\.\d+)/g, (_, before, after, amount) => {
    const rounded = Math.round(Number(amount.replaceAll(',', '')));
    return ((before || after) && rounded ? '−' : '') + '$' + rounded.toLocaleString('en-US');
  });
  notice.className = 'notice' + (error ? ' error' : '');
  notice.hidden = false;
  appendRecoveryLinks(notice, links);
}

async function command(payload) {
  if (busy) return;
  busy = true;
  const buttons = [...document.querySelectorAll('button')];
  buttons.forEach(b => b.disabled = true);
  try {
    const response = await fetch('/api/command', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-Game-Token': token},
      body: JSON.stringify({...payload, revision, campaign_session})
    });
    const data = await response.json();
    if (!response.ok) throw recoveryError(data, 'The input could not be accepted. Check the fields and try again.');
    sessionStorage.setItem('game-notice', data.message);
    if (['new_campaign','open_campaign'].includes(payload.action)) {
      location.assign('/?page=overview');
    } else if (payload.action === 'copy_campaign') {
      location.assign('/?page=games');
    } else if (payload.action === 'hire_for_role') {
      location.assign('/?page=business&business_id=' + encodeURIComponent(payload.args.business_id) + '&scope=' + encodeURIComponent(payload.args.business_id));
    } else location.reload();
  } catch (error) {
    const text = error.message || 'The game could not be reached. Your last saved state is safe.';
    message(text, true, error.recoveryLinks);
    if (actionDialog.open) {
      const dialogError = document.getElementById('dialog-error');
      dialogError.textContent = text;
      appendRecoveryLinks(dialogError, error.recoveryLinks);
    } else notice.scrollIntoView({block:'center'});
    if (advanceDialog.open) advanceDialog.close();
    buttons.forEach(b => b.disabled = false);
    busy = false;
  }
}

document.querySelectorAll('input[data-exact-dollars]').forEach(input => {
  input.addEventListener('input', () => { input.dataset.moneyEdited = 'true'; });
});
const savedMessage = sessionStorage.getItem('game-notice');
if (savedMessage) { message(savedMessage); sessionStorage.removeItem('game-notice'); }

document.querySelectorAll('[data-preview]').forEach(button => button.addEventListener('click', () => {
  pending = {action: button.dataset.preview, args: {property_id: button.dataset.property, business_id: button.dataset.business, employment_id: button.dataset.employment, entity: scope}, command_id: commandId()};
  document.getElementById('action-title').textContent = button.dataset.title;
  document.getElementById('action-description').textContent = button.dataset.description;
  document.getElementById('action-amount').textContent = button.dataset.amount;
  document.getElementById('dialog-error').textContent = '';
  document.getElementById('action-links').replaceChildren();
  window.fundingBalances?.review(null);
  actionDialog.showModal();
}));
document.getElementById('action-confirm').addEventListener('click', () => {if (pending) command(pending);});
document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.getElementById('advance-open').addEventListener('click', () => advanceDialog.showModal());
function advancePreferences() {
  const minimum = document.getElementById('skip-minimum');
  // An open pre-update page can still be using the earlier dialog markup.
  if (!minimum) return {};
  if (!minimum.checkValidity()) {
    if (!advanceDialog.open) advanceDialog.showModal();
    minimum.reportValidity();
    return null;
  }
  const amount = !minimum.dataset.moneyEdited && minimum.value === minimum.defaultValue ? minimum.dataset.exactDollars : minimum.value;
  return {pause_routine:document.getElementById('skip-routine').checked, financial_pause_threshold_dollars:amount};
}
document.getElementById('skip-quiet')?.addEventListener('click', () => {
  document.getElementById('skip-routine').checked = false;
  const minimum = document.getElementById('skip-minimum');
  minimum.value = '1000'; minimum.dataset.moneyEdited = 'true';
});
document.querySelectorAll('[data-period], [data-resume-target]').forEach(button => button.addEventListener('click', () => {
  const preferences = advancePreferences();
  if (!preferences) return;
  const target = button.dataset.resumeTarget ? {target:button.dataset.resumeTarget} : {period:button.dataset.period};
  command({action:'advance', args:{...target,...preferences}, command_id:commandId()});
}));
document.querySelectorAll('[data-immediate]').forEach(button => button.addEventListener('click', () => command({action:button.dataset.immediate, args:{}, command_id:commandId()})));
document.querySelectorAll('form[data-action]').forEach(form => form.addEventListener('submit', async event => {
  event.preventDefault();
  form.querySelector('.form-error')?.remove();
  const args = Object.fromEntries(new FormData(form));
  form.querySelectorAll('input[data-exact-dollars]').forEach(input => {
    if (!input.dataset.moneyEdited && input.value === input.defaultValue) args[input.name] = input.dataset.exactDollars;
  });
  form.querySelectorAll("select[multiple]").forEach(input => args[input.name] = Array.from(input.selectedOptions, option => option.value).join(","));
  form.querySelectorAll('input[type="checkbox"]:not(:disabled)').forEach(input => args[input.name] = input.checked);
  if (form.dataset.action === 'advance') {
    const preferences = advancePreferences();
    if (!preferences) return;
    Object.assign(args, preferences);
  }
  const fingerprint = JSON.stringify(args);
  if (form.dataset.fingerprint !== fingerprint) {
    form.dataset.fingerprint = fingerprint;
    form.dataset.commandId = commandId();
  }
  const payload = {action:form.dataset.action, args, command_id:form.dataset.commandId};
  if (form.dataset.review === 'true') {
    try {
      const response = await fetch('/api/preview', {method:'POST', headers:{'Content-Type':'application/json','X-Game-Token':token}, body:JSON.stringify({...payload,revision,campaign_session})});
      const data = await response.json();
      if (!response.ok) throw recoveryError(data, 'Check the entered values.');
      pending = payload;
      document.getElementById('action-title').textContent = form.dataset.title;
      document.getElementById('action-description').textContent = data.message + ' ' + data.description;
      document.getElementById('action-amount').textContent = '';
      document.getElementById('dialog-error').textContent = '';
      document.getElementById('action-links').replaceChildren();
      appendRecoveryLinks(document.getElementById('action-links'), data.action_links);
      window.fundingBalances?.review(form);
      actionDialog.showModal();
    } catch (error) {
      const inline = document.createElement('div');
      inline.className = 'form-error'; inline.setAttribute('role','alert'); inline.tabIndex = -1;
      inline.textContent = error.message;
      appendRecoveryLinks(inline,error.recoveryLinks);
      form.prepend(inline); inline.focus(); inline.scrollIntoView({block:'center'});
    }
  } else command(payload);
}));
document.getElementById('scope-select').addEventListener('change', event => {
  const destination = event.target.selectedOptions[0]?.dataset.url;
  if (destination) location.assign(destination);
  else { const url = new URL(location.href); url.searchParams.set('scope', event.target.value); location.assign(url); }
});

function updateCash(data) {
  if (data.campaign_session && data.campaign_session !== campaign_session) { location.assign('/?page=games'); return; }
  window.fundingBalances?.update(data.account_balances);
  if (typeof data.inbox_count === 'number') document.querySelectorAll('[data-inbox-count]').forEach(element => {
    const text = String(data.inbox_count);
    if (element.textContent !== text) element.textContent = text;
  });
  const indicator = document.getElementById('leadership-indicator');
  if (indicator && data.leadership_activity) {
    const text = data.leadership_activity.label;
    if (indicator.textContent !== text) indicator.textContent = text;
    indicator.classList.toggle('has-updates', data.leadership_activity.new > 0 || data.leadership_activity.pending > 0);
  }
  if (data.cash_scope !== scope || typeof data.cash_label !== 'string') return;
  document.querySelectorAll('[data-cash-on-hand]').forEach(element => {
    element.textContent = data.cash_label;
    element.classList.toggle('negative', data.cash_on_hand < 0);
    element.removeAttribute('title');
  });
}
const cashProgressUrl = '/api/progress?scope=' + encodeURIComponent(scope);
if (document.body.dataset.running !== 'true') {
  async function refreshCash() {
    try {
      const response = await fetch(cashProgressUrl);
      if (!response.ok) throw new Error('Balance unavailable');
      updateCash(await response.json());
    } catch (_) {
      document.querySelectorAll('[data-cash-on-hand]').forEach(element => element.title = 'Last known balance. Reconnecting…');
    }
    setTimeout(refreshCash, 2000);
  }
  refreshCash();
}
if (document.body.dataset.running === 'true') {
  document.getElementById('advance-open').disabled = true;
  async function poll() {
    try {
      const response = await fetch(cashProgressUrl);
      if (!response.ok) throw new Error('Could not read progress. Refresh to reconnect.');
      const data = await response.json();
      updateCash(data);
      document.getElementById('progress-text').textContent = data.running ? `Advanced ${data.completed} of ${data.total} days.` : data.message;
      const progress = document.getElementById('skip-progress');
      if (progress) progress.value = data.completed;
      if (!data.running) { location.reload(); return; }
      setTimeout(poll, 400);
    } catch (error) { message(error.message, true); }
  }
  poll();
}
const cancelButton = document.getElementById('cancel-skip');
if (cancelButton) cancelButton.addEventListener('click', async () => {
  try {
    const response = await fetch('/api/cancel', {method:'POST', headers:{'X-Game-Token':token,'X-Game-Session':campaign_session}});
    if (!response.ok) throw new Error('Could not pause. Refresh to reconnect.');
    cancelButton.disabled = true;
  } catch (error) { message(error.message, true); }
});

const forecastForm = document.getElementById('forecast-form');
if (forecastForm) forecastForm.addEventListener('submit', async event => {
  event.preventDefault();
  const button = forecastForm.querySelector('button');
  const result = document.getElementById('forecast-results');
  button.disabled = true;
  result.textContent = 'Calculating three demand scenarios…';
  try {
    const response = await fetch('/api/forecast', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Game-Token': token}, body: JSON.stringify({action: 'forecast', args: {days: new FormData(forecastForm).get('days')}, revision, campaign_session, command_id: commandId()})});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The forecast could not be calculated.');
    result.replaceChildren();
    const assumptions = document.createElement('p');
    assumptions.textContent = data.assumptions;
    result.append(assumptions);
    const table = document.createElement('table');
    const header = table.createTHead().insertRow();
    ['Scenario', 'Through', 'Cash', 'Cash change', 'Period profit'].forEach(text => {
      const cell = document.createElement('th'); cell.textContent = text; header.append(cell);
    });
    const body = table.createTBody();
    const money = cents => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD', minimumFractionDigits:0, maximumFractionDigits:0}).format(cents / 100);
    data.results.forEach(item => {
      const row = body.insertRow();
      [item.scenario, item.date, money(item.cash), money(item.cash_change), money(item.profit)].forEach(text => row.insertCell().textContent = text);
    });
    result.append(table);
  } catch (error) { result.textContent = error.message; }
  finally { button.disabled = false; }
});

const guidedHiring = document.getElementById('guided-hiring-offer');
if (guidedHiring) {
  const hours = guidedHiring.querySelector('[name="weekly_hours"]');
  const salary = guidedHiring.querySelector('[name="amount_dollars"]');
  const updateOfferSummary = () => {
    const amount = Number(salary.value);
    if (!Number.isFinite(amount) || amount < 0) return;
    const money = value => new Intl.NumberFormat('en-US', {style:'currency', currency:'USD', minimumFractionDigits:0, maximumFractionDigits:0}).format(value);
    document.getElementById('hiring-hours-label').textContent = `Proposed ${hours.value} h/week offer`;
    document.getElementById('hiring-salary-label').textContent = money(amount) + '/month';
    const recruitmentFee = Number(guidedHiring.dataset.recruitmentFee);
    document.getElementById('hiring-funds-label').textContent = money(amount + recruitmentFee / 100);
    document.getElementById('hiring-funds-warning').hidden = Number(guidedHiring.dataset.cash) >= Math.round(amount * 100) + recruitmentFee;
  };
  salary.addEventListener('input', updateOfferSummary);
  hours.addEventListener('input', () => {
    const count = Number(hours.value);
    if (Number.isInteger(count) && count >= 4 && count <= 60) {
      salary.value = (Math.floor(Number(guidedHiring.dataset.marketPay) * count / 40) / 100).toFixed(0);
      salary.dataset.moneyEdited = 'true';
      updateOfferSummary();
    }
  });
}
