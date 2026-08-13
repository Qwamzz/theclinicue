// Hash router.
//
// Hash routing keeps the app deployable as plain static files behind the same
// process that serves the API — no rewrite rule, no reverse proxy.
//
// The role guards here decide what is *drawn*. They are not security: every
// endpoint re-checks the caller's role server-side (NFR-SEC-06).

import { store } from './store.js';
import { h, mount, notice } from './ui.js';
import { renderAuth } from './views/auth.js';
import { renderBooking, renderMyAppointments } from './views/patient.js';
import { renderStaffConsole } from './views/staff.js';
import { renderAudit, renderClinicSetup, renderReports, renderUsers } from './views/admin.js';

const ROUTES = [
  { path: '/login', view: () => renderAuth('login'), anonymous: true },
  { path: '/register', view: () => renderAuth('register'), anonymous: true },
  { path: '/book', view: renderBooking, roles: ['PATIENT', 'STAFF', 'ADMIN'] },
  { path: '/appointments', view: renderMyAppointments, roles: ['PATIENT', 'STAFF', 'ADMIN'] },
  { path: '/staff', view: renderStaffConsole, roles: ['STAFF', 'ADMIN'] },
  { path: '/admin/reports', view: renderReports, roles: ['ADMIN'] },
  { path: '/admin/users', view: renderUsers, roles: ['ADMIN'] },
  { path: '/admin/clinic', view: renderClinicSetup, roles: ['ADMIN'] },
  { path: '/admin/audit', view: renderAudit, roles: ['ADMIN'] },
];

const NAV = [
  { path: '/book', label: 'Book', roles: ['PATIENT', 'STAFF', 'ADMIN'] },
  { path: '/appointments', label: 'My appointments', roles: ['PATIENT', 'STAFF', 'ADMIN'] },
  { path: '/staff', label: 'Front desk', roles: ['STAFF', 'ADMIN'] },
  { path: '/admin/reports', label: 'Reports', roles: ['ADMIN'] },
  { path: '/admin/users', label: 'Users', roles: ['ADMIN'] },
  { path: '/admin/clinic', label: 'Clinic setup', roles: ['ADMIN'] },
  { path: '/admin/audit', label: 'Audit log', roles: ['ADMIN'] },
];

export function currentPath() {
  const raw = window.location.hash.replace(/^#/, '');
  return raw && raw.startsWith('/') ? raw : '/';
}

export function buildNav() {
  const nav = document.getElementById('primary-nav');
  nav.replaceChildren();
  if (!store.user) return;

  const here = currentPath();
  for (const item of NAV) {
    if (!item.roles.includes(store.role)) continue;
    nav.append(h('a', {
      href: `#${item.path}`,
      text: item.label,
      'aria-current': here === item.path ? 'page' : null,
      onclick: () => document.getElementById('primary-nav').classList.remove('open'),
    }));
  }
}

export async function route() {
  const path = currentPath();

  if (path === '/' || path === '') {
    window.location.hash = store.user ? store.landingRoute() : '#/login';
    return;
  }

  const match = ROUTES.find((r) => r.path === path);

  if (!match) {
    mount(h('div', { class: 'card' },
      h('h1', { text: 'Page not found' }),
      h('p', { text: 'That link does not lead anywhere in TheClinicue.' }),
      h('a', { class: 'btn', href: `#${store.user ? store.landingRoute().slice(1) : '/login'}`,
        text: 'Go back' })));
    return;
  }

  if (match.anonymous) {
    if (store.user) { window.location.hash = store.landingRoute(); return; }
    await match.view();
    buildNav();
    return;
  }

  if (!store.user) {
    window.location.hash = '#/login';
    return;
  }

  if (match.roles && !match.roles.includes(store.role)) {
    mount(h('div', { class: 'card' },
      notice('error', 'You do not have permission to view that page.'),
      h('a', { class: 'btn', href: `#${store.landingRoute().slice(1)}`, text: 'Back to your area' })));
    buildNav();
    return;
  }

  buildNav();
  try {
    await match.view();
  } catch (err) {
    mount(h('div', { class: 'card' },
      notice('error', err.message || 'This page could not be loaded.'),
      h('button', { class: 'btn', type: 'button', text: 'Try again',
        onclick: () => route() })));
  }
  buildNav();
}
