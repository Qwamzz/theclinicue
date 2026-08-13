import { api, ApiError } from '../api.js';
import { applyFieldErrors, field, h, input, mount, notice, toast, withBusy } from '../ui.js';
import { store } from '../store.js';

function heading() {
  return h('div', { class: 'hero' },
    h('h1', { text: 'Book your clinic visit before you travel' }),
    h('p', { text: 'See real appointment times, get a ticket number on arrival, and know how long the wait is.' }));
}

function demoCredentials() {
  return h('div', { class: 'demo-creds' },
    h('strong', { text: 'Demonstration accounts' }),
    h('br'),
    h('code', { text: 'patient@theclinicue.com / Patient#2026' }), h('br'),
    h('code', { text: 'staff@theclinicue.com / Staff#2026' }), h('br'),
    h('code', { text: 'admin@theclinicue.com / Admin#2026' }));
}

export function renderAuth(mode = 'login') {
  const wrap = h('div', { class: 'auth-wrap' });
  const tabs = h('div', { class: 'auth-tabs', role: 'tablist' });
  const panel = h('div');

  const loginTab = h('button', {
    role: 'tab', 'aria-selected': String(mode === 'login'), type: 'button',
    text: 'Sign in', onclick: () => switchTo('login'),
  });
  const registerTab = h('button', {
    role: 'tab', 'aria-selected': String(mode === 'register'), type: 'button',
    text: 'Create account', onclick: () => switchTo('register'),
  });
  tabs.append(loginTab, registerTab);

  function switchTo(next) {
    loginTab.setAttribute('aria-selected', String(next === 'login'));
    registerTab.setAttribute('aria-selected', String(next === 'register'));
    panel.replaceChildren(next === 'login' ? loginForm() : registerForm());
    window.location.hash = next === 'login' ? '#/login' : '#/register';
  }

  panel.append(mode === 'register' ? registerForm() : loginForm());
  wrap.append(heading(), tabs, panel, h('div', { class: 'card' }, demoCredentials()));
  mount(wrap);
}

function loginForm() {
  const email = input('email', { type: 'email', autocomplete: 'username', required: true });
  const password = input('password', { type: 'password', autocomplete: 'current-password', required: true });
  const submit = h('button', { class: 'btn btn-block', type: 'submit', text: 'Sign in' });
  const errorSlot = h('div');

  const form = h('form', { class: 'card', novalidate: true },
    h('h2', { text: 'Sign in' }),
    errorSlot,
    field('Email address', email),
    field('Password', password),
    submit);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorSlot.replaceChildren();
    await withBusy(submit, async () => {
      try {
        const result = await api.login(email.value.trim(), password.value);
        store.setUser(result.user);
        toast(`Welcome back, ${result.user.full_name.split(' ')[0]}.`, 'success');
        window.location.hash = store.landingRoute();
      } catch (err) {
        if (err instanceof ApiError && err.fields) applyFieldErrors(form, err.fields);
        errorSlot.replaceChildren(notice('error', err.message));
      }
    });
  });

  return form;
}

function registerForm() {
  const fullName = input('full_name', { type: 'text', autocomplete: 'name', required: true });
  const email = input('email', { type: 'email', autocomplete: 'email', required: true });
  const phone = input('phone', { type: 'tel', autocomplete: 'tel', required: true, placeholder: '+233 24 000 0000' });
  const password = input('password', { type: 'password', autocomplete: 'new-password', required: true });
  const submit = h('button', { class: 'btn btn-block', type: 'submit', text: 'Create account' });
  const errorSlot = h('div');

  const form = h('form', { class: 'card', novalidate: true },
    h('h2', { text: 'Create your account' }),
    h('p', { class: 'card-sub', text: 'We only ask for what is needed to book you in. No medical information is stored.' }),
    errorSlot,
    field('Full name', fullName),
    field('Email address', email),
    field('Phone number', phone, 'So the clinic can reach you if plans change.'),
    field('Password', password, 'At least 8 characters, including a letter and a number.'),
    submit);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorSlot.replaceChildren();
    await withBusy(submit, async () => {
      try {
        const result = await api.register({
          full_name: fullName.value.trim(),
          email: email.value.trim(),
          phone: phone.value.trim(),
          password: password.value,
        });
        store.setUser(result.user);
        toast('Account created. You can book straight away.', 'success');
        window.location.hash = '#/book';
      } catch (err) {
        if (err instanceof ApiError && err.fields) applyFieldErrors(form, err.fields);
        errorSlot.replaceChildren(notice('error', err.message));
      }
    });
  });

  return form;
}
