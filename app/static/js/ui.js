// DOM helpers.
//
// `h` is the only element factory in the app and it assigns text through
// textContent, never innerHTML. That is what makes stored XSS structurally
// impossible here rather than a matter of remembering to escape (FR-58).

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);

  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'text') el.textContent = String(value);
    else if (key === 'html') throw new Error('raw HTML is not permitted; use text');
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else if (key === 'style' && typeof value === 'object') Object.assign(el.style, value);
    else if (key.startsWith('on') && typeof value === 'function') {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value === true) el.setAttribute(key, '');
    else el.setAttribute(key, String(value));
  }

  for (const child of children.flat(3)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function mount(node) {
  const main = document.getElementById('main');
  clear(main);
  main.append(node);
  main.focus({ preventScroll: true });
  window.scrollTo({ top: 0 });
}

// ---------------------------------------------------------------- toasts

let toastTimer = 0;

export function toast(message, kind = '') {
  const host = document.getElementById('toasts');
  const node = h('div', { class: `toast ${kind}`.trim(), text: message });
  host.append(node);
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => node.remove(), kind === 'error' ? 6000 : 3500);
}

// ---------------------------------------------------------------- modal

export function confirmDialog(title, body, confirmLabel = 'Confirm') {
  return new Promise((resolve) => {
    const backdrop = document.getElementById('modal-backdrop');
    const confirm = document.getElementById('modal-confirm');
    const cancel = document.getElementById('modal-cancel');
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').textContent = body;
    confirm.textContent = confirmLabel;
    backdrop.hidden = false;
    confirm.focus();

    const finish = (answer) => {
      backdrop.hidden = true;
      confirm.removeEventListener('click', onYes);
      cancel.removeEventListener('click', onNo);
      document.removeEventListener('keydown', onKey);
      resolve(answer);
    };
    const onYes = () => finish(true);
    const onNo = () => finish(false);
    const onKey = (event) => { if (event.key === 'Escape') finish(false); };

    confirm.addEventListener('click', onYes);
    cancel.addEventListener('click', onNo);
    document.addEventListener('keydown', onKey);
  });
}

// ------------------------------------------------------------- formatting

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export function addDays(iso, days) {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function formatDate(iso, { weekday = true } = {}) {
  if (!iso) return '';
  const date = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return iso;
  const day = DAYS[(date.getUTCDay() + 6) % 7].slice(0, 3);
  const label = `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
  return weekday ? `${day} ${label}` : label;
}

export function weekdayName(index) {
  return DAYS[index] || String(index);
}

export function relativeDay(iso) {
  const today = todayISO();
  if (iso === today) return 'Today';
  if (iso === addDays(today, 1)) return 'Tomorrow';
  if (iso === addDays(today, -1)) return 'Yesterday';
  return formatDate(iso);
}

export function statusLabel(status) {
  return String(status || '').replace(/_/g, ' ').toLowerCase()
    .replace(/^./, (c) => c.toUpperCase());
}

export function badge(status) {
  // The text label is not decoration: colour alone must never carry meaning
  // (NFR-USA-05 / WCAG 1.4.1).
  return h('span', { class: `badge badge-${status}`, text: statusLabel(status) });
}

export function notice(kind, message) {
  return h('div', { class: `notice notice-${kind}`, text: message });
}

export function empty(title, detail) {
  return h('div', { class: 'empty' }, h('strong', { text: title }), detail ? h('span', { text: detail }) : null);
}

// ------------------------------------------------------------------ forms

/** Paint server-side field errors onto a form, and focus the first bad input. */
export function applyFieldErrors(form, fields) {
  form.querySelectorAll('.field-error').forEach((node) => node.remove());
  form.querySelectorAll('[aria-invalid]').forEach((node) => node.removeAttribute('aria-invalid'));
  if (!fields) return;

  let first = null;
  for (const [name, message] of Object.entries(fields)) {
    const input = form.elements[name];
    if (!input) continue;
    input.setAttribute('aria-invalid', 'true');
    input.insertAdjacentElement('afterend', h('span', { class: 'field-error', text: message }));
    if (!first) first = input;
  }
  if (first) first.focus();
}

export function field(label, input, hint) {
  return h('div', { class: 'field' },
    h('label', { for: input.id || input.name, text: label }),
    input,
    hint ? h('span', { class: 'hint', text: hint }) : null);
}

export function input(name, attrs = {}) {
  return h('input', { name, id: `f-${name}`, ...attrs });
}

export function select(name, options, attrs = {}) {
  return h('select', { name, id: `f-${name}`, ...attrs },
    options.map((option) => h('option', { value: option.value, text: option.label,
      selected: option.selected })));
}

/** Run an async action while disabling its button, so a slow link cannot
 *  produce a double booking from an impatient second tap. */
export async function withBusy(button, action) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = 'Working…';
  try {
    return await action();
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}
