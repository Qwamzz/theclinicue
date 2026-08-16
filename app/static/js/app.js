// Bootstrap: resolve the session, wire the chrome, then hand over to the router.

import { api } from './api.js';
import { buildNav, route } from './router.js';
import { store } from './store.js';
import { toast } from './ui.js';

function paintChrome() {
  const topbar = document.getElementById('topbar');
  const footer = document.getElementById('footer');
  const who = document.getElementById('who');
  const userBox = document.querySelector('.topbar-user');

  topbar.hidden = false;
  footer.hidden = false;

  if (store.user) {
    const roleLabel = { PATIENT: 'Patient', STAFF: 'Front desk', ADMIN: 'Administrator' }[store.role];
    who.textContent = `${store.user.full_name} · ${roleLabel}`;
    userBox.classList.add('show');
  } else {
    who.textContent = '';
    userBox.classList.remove('show');
  }
  buildNav();
}

async function start() {
  try {
    const session = await api.session();
    store.setUser(session.authenticated ? session.user : null);
  } catch {
    // A failed session probe means the server is unreachable, not that the
    // user is signed out - say so rather than silently bouncing to login.
    store.setUser(null);
    toast('Could not reach the clinic server. Some features may not work.', 'error');
  }

  paintChrome();
  store.subscribe(paintChrome);

  document.getElementById('nav-toggle').addEventListener('click', (event) => {
    const nav = document.getElementById('primary-nav');
    const open = nav.classList.toggle('open');
    event.currentTarget.setAttribute('aria-expanded', String(open));
  });

  document.getElementById('signout').addEventListener('click', async () => {
    try {
      await api.logout();
    } catch {
      // Even if the call fails, clearing local state is the honest outcome of
      // pressing "sign out" - the cookie is HttpOnly and will expire.
    }
    store.clear();
    toast('Signed out.');
    window.location.hash = '#/login';
    await route();
  });

  window.addEventListener('hashchange', route);
  await route();
}

start();
