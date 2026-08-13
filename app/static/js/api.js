// Thin fetch wrapper: JSON in, JSON out, CSRF header on every unsafe verb,
// and one uniform error shape so views never parse response bodies themselves.

const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export class ApiError extends Error {
  constructor(status, body) {
    super((body && body.message) || 'Something went wrong. Please try again.');
    this.status = status;
    this.code = (body && body.error) || 'HTTP_ERROR';
    this.fields = (body && body.fields) || null;
  }
}

function csrfFromCookie() {
  const match = document.cookie.match(/(?:^|;\s*)cq_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

async function request(method, path, { body, query } = {}) {
  let url = path;
  if (query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') params.append(key, value);
    }
    const qs = params.toString();
    if (qs) url += (url.includes('?') ? '&' : '?') + qs;
  }

  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (UNSAFE.has(method)) headers['X-CSRF-Token'] = csrfFromCookie();

  let response;
  try {
    response = await fetch(url, {
      method,
      headers,
      credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // Distinguish "the network failed" from "the server said no": on the
    // intermittent connections this app targets, that difference is the whole
    // difference between "try again" and "fix your input".
    throw new ApiError(0, {
      error: 'NETWORK',
      message: 'No connection to the clinic server. Check your internet and try again.',
    });
  }

  if (response.status === 204) return null;

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) throw new ApiError(response.status, payload);
  return payload;
}

export const api = {
  get: (path, query) => request('GET', path, { query }),
  post: (path, body) => request('POST', path, { body }),
  patch: (path, body) => request('PATCH', path, { body }),
  del: (path) => request('DELETE', path),

  // Auth
  session: () => request('GET', '/api/auth/session'),
  login: (email, password) => request('POST', '/api/auth/login', { body: { email, password } }),
  register: (payload) => request('POST', '/api/auth/register', { body: payload }),
  logout: () => request('POST', '/api/auth/logout', { body: {} }),

  // Catalogue and booking
  services: () => request('GET', '/api/services'),
  practitioners: () => request('GET', '/api/practitioners'),
  availability: (practitionerId) =>
    request('GET', '/api/availability', { query: { practitioner_id: practitionerId } }),
  slots: (practitionerId, serviceId, date) =>
    request('GET', '/api/slots', {
      query: { practitioner_id: practitionerId, service_id: serviceId, date },
    }),
  book: (payload) => request('POST', '/api/appointments', { body: payload }),
  myAppointments: (scope) => request('GET', '/api/appointments/mine', { query: { scope } }),
  cancel: (id) => request('POST', `/api/appointments/${id}/cancel`, { body: {} }),

  // Front desk
  daySheet: (query) => request('GET', '/api/appointments', { query }),
  findPatients: (q) => request('GET', '/api/appointments/lookup', { query: { q } }),
  checkIn: (appointmentId) =>
    request('POST', '/api/queue/check-in', { body: { appointment_id: appointmentId } }),
  callNext: (practitionerId) =>
    request('POST', '/api/queue/call-next', { body: { practitioner_id: practitionerId } }),
  complete: (appointmentId) =>
    request('POST', '/api/queue/complete', { body: { appointment_id: appointmentId } }),
  noShow: (appointmentId) =>
    request('POST', '/api/queue/no-show', { body: { appointment_id: appointmentId } }),
  liveQueue: (practitionerId, date) =>
    request('GET', '/api/queue', { query: { practitioner_id: practitionerId, date } }),
  myPosition: () => request('GET', '/api/queue/my-position'),

  // Administration
  adminUsers: (query) => request('GET', '/api/admin/users', { query }),
  adminUpdateUser: (id, body) => request('PATCH', `/api/admin/users/${id}`, { body }),
  adminServices: () => request('GET', '/api/admin/services'),
  adminCreateService: (body) => request('POST', '/api/admin/services', { body }),
  adminUpdateService: (id, body) => request('PATCH', `/api/admin/services/${id}`, { body }),
  adminPractitioners: () => request('GET', '/api/admin/practitioners'),
  adminCreatePractitioner: (body) => request('POST', '/api/admin/practitioners', { body }),
  adminUpdatePractitioner: (id, body) => request('PATCH', `/api/admin/practitioners/${id}`, { body }),
  adminAvailability: (practitionerId) =>
    request('GET', '/api/admin/availability', { query: { practitioner_id: practitionerId } }),
  adminCreateAvailability: (body) => request('POST', '/api/admin/availability', { body }),
  adminDeleteAvailability: (id) => request('DELETE', `/api/admin/availability/${id}`),
  adminAudit: (query) => request('GET', '/api/admin/audit', { query }),
  reportDaily: (date) => request('GET', '/api/admin/reports/daily', { query: { date } }),
  reportUtilisation: (from, to) =>
    request('GET', '/api/admin/reports/utilisation', { query: { from, to } }),
};
