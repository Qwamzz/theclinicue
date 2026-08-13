// Minimal observable session state. Role information held here drives
// navigation only — every authorisation decision is made server-side
// (NFR-SEC-06). Editing this object in the console changes what is drawn and
// nothing that is permitted.

const listeners = new Set();

export const store = {
  user: null,
  ready: false,

  subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },

  notify() {
    for (const fn of listeners) fn(this.user);
  },

  setUser(user) {
    this.user = user || null;
    this.ready = true;
    this.notify();
  },

  clear() {
    this.user = null;
    this.notify();
  },

  get role() {
    return this.user ? this.user.role : null;
  },

  isStaff() {
    return this.role === 'STAFF' || this.role === 'ADMIN';
  },

  isAdmin() {
    return this.role === 'ADMIN';
  },

  landingRoute() {
    if (this.isAdmin()) return '#/admin/reports';
    if (this.isStaff()) return '#/staff';
    return '#/book';
  },
};
