import { api } from '../api.js';
import {
  addDays, empty, field, formatDate, h, input, mount, notice, select,
  todayISO, toast, weekdayName, withBusy,
} from '../ui.js';
import { store } from '../store.js';

function shell(title, subtitle) {
  const page = h('div');
  mount(page);
  page.append(h('div', { class: 'page-head' },
    h('h1', { text: title }), h('p', { text: subtitle })));
  return page;
}

// ---------------------------------------------------------------- reports

export async function renderReports() {
  const page = shell('Reports', 'Attendance, no-shows, waiting time and clinician utilisation.');

  const dateInput = input('report_date', { type: 'date', value: todayISO() });
  const fromInput = input('from', { type: 'date', value: addDays(todayISO(), -13) });
  const toInput = input('to', { type: 'date', value: todayISO() });

  const dailySlot = h('div');
  const utilSlot = h('div');

  page.append(
    h('div', { class: 'card' },
      h('h2', { text: 'Daily summary' }),
      h('form', { class: 'toolbar', novalidate: true,
        onsubmit: (e) => { e.preventDefault(); loadDaily(); } },
        field('Date', dateInput),
        h('button', { class: 'btn', type: 'submit', text: 'Show' })),
      dailySlot),
    h('div', { class: 'card' },
      h('h2', { text: 'Clinician utilisation' }),
      h('form', { class: 'toolbar', novalidate: true,
        onsubmit: (e) => { e.preventDefault(); loadUtilisation(); } },
        field('From', fromInput), field('To', toInput),
        h('button', { class: 'btn', type: 'submit', text: 'Show' })),
      utilSlot));

  async function loadDaily() {
    dailySlot.replaceChildren(h('p', { class: 'hint', text: 'Loading…' }));
    try {
      const report = await api.reportDaily(dateInput.value);
      const noShowClass = report.no_show_rate > 15 ? 'bad' : report.no_show_rate > 8 ? 'warn' : 'good';

      const stats = h('div', { class: 'stats' },
        stat('Total booked', report.total),
        stat('Completed', report.by_status.COMPLETED, 'good'),
        stat('No-show rate', `${report.no_show_rate}%`, noShowClass),
        stat('Mean wait', report.mean_wait_minutes === null ? '—' : `${report.mean_wait_minutes} m`, 'warn'),
        stat('Cancelled', report.by_status.CANCELLED),
        stat('Still waiting', report.by_status.CHECKED_IN));

      const throughput = report.throughput && report.throughput.length
        ? h('div', { class: 'table-wrap' }, h('table', null,
          h('thead', null, h('tr', null, h('th', { text: 'Clinician' }),
            h('th', { class: 'num', text: 'Consultations completed' }))),
          h('tbody', null, report.throughput.map((row) => h('tr', null,
            h('td', { text: row.practitioner_name }),
            h('td', { class: 'num', text: row.completed }))))))
        : null;

      dailySlot.replaceChildren(
        h('p', { class: 'card-sub', text: formatDate(report.date) }),
        stats,
        h('p', { class: 'hint', style: { marginTop: '.75rem' },
          text: 'The no-show rate excludes cancellations from its denominator: a patient who cancelled was not expected to attend.' }),
        throughput);
    } catch (err) {
      dailySlot.replaceChildren(notice('error', err.message));
    }
  }

  async function loadUtilisation() {
    utilSlot.replaceChildren(h('p', { class: 'hint', text: 'Loading…' }));
    try {
      const report = await api.reportUtilisation(fromInput.value, toInput.value);
      if (!report.items.length) {
        utilSlot.replaceChildren(empty('No clinicians configured'));
        return;
      }
      utilSlot.replaceChildren(h('div', { class: 'table-wrap' }, h('table', null,
        h('thead', null, h('tr', null,
          h('th', { text: 'Clinician' }),
          h('th', { class: 'num', text: 'Slots offered' }),
          h('th', { class: 'num', text: 'Appointments' }),
          h('th', { text: 'Utilisation' }),
          h('th', { class: 'num', text: 'No-show' }))),
        h('tbody', null, report.items.map((row) => {
          const pct = row.utilisation_pct;
          const tone = pct === null ? '' : pct >= 75 ? '' : pct >= 50 ? 'warn' : 'bad';
          return h('tr', null,
            h('td', null, h('div', { text: row.practitioner_name }),
              h('div', { class: 'appt-meta', text: row.specialty || '' })),
            h('td', { class: 'num', text: row.slots_offered }),
            h('td', { class: 'num', text: row.appointments }),
            h('td', null,
              h('div', { class: `bar ${tone}` },
                h('span', { style: { width: `${Math.min(100, pct || 0)}%` } })),
              h('span', { class: 'appt-meta', text: pct === null ? 'no availability set' : `${pct}%` })),
            h('td', { class: 'num', text: `${row.no_show_pct}%` }));
        })))));
    } catch (err) {
      utilSlot.replaceChildren(notice('error', err.message));
    }
  }

  await loadDaily();
  await loadUtilisation();
}

function stat(label, value, tone = '') {
  return h('div', { class: 'stat' },
    h('div', { class: 'stat-label', text: label }),
    h('div', { class: `stat-value ${tone}`.trim(), text: value }));
}

// ------------------------------------------------------------------ users

export async function renderUsers() {
  const page = shell('User accounts', 'Change roles and deactivate accounts. You cannot change your own.');
  const searchInput = input('q', { type: 'search', placeholder: 'Name, email or phone' });
  const roleSelect = select('role', [
    { value: '', label: 'All roles' }, { value: 'PATIENT', label: 'Patient' },
    { value: 'STAFF', label: 'Staff' }, { value: 'ADMIN', label: 'Administrator' }]);
  const slot = h('div');

  page.append(h('div', { class: 'card' },
    h('form', { class: 'toolbar', novalidate: true,
      onsubmit: (e) => { e.preventDefault(); load(); } },
      field('Search', searchInput), field('Role', roleSelect),
      h('button', { class: 'btn', type: 'submit', text: 'Apply' })),
    slot));

  roleSelect.addEventListener('change', load);

  async function load() {
    slot.replaceChildren(h('p', { class: 'hint', text: 'Loading…' }));
    try {
      const result = await api.adminUsers({ q: searchInput.value.trim(), role: roleSelect.value, limit: 50 });
      if (!result.items.length) { slot.replaceChildren(empty('No accounts match')); return; }

      slot.replaceChildren(
        h('p', { class: 'card-sub', text: `${result.total} account${result.total === 1 ? '' : 's'}` }),
        h('div', { class: 'table-wrap' }, h('table', null,
          h('thead', null, h('tr', null,
            ['Name', 'Contact', 'Role', 'Status', ''].map((t) => h('th', { text: t })))),
          h('tbody', null, result.items.map((user) => userRow(user, load))))));
    } catch (err) {
      slot.replaceChildren(notice('error', err.message));
    }
  }

  await load();
}

function userRow(user, reload) {
  const isSelf = store.user && store.user.id === user.id;
  const roleSelect = select(`role_${user.id}`, [
    { value: 'PATIENT', label: 'Patient', selected: user.role === 'PATIENT' },
    { value: 'STAFF', label: 'Staff', selected: user.role === 'STAFF' },
    { value: 'ADMIN', label: 'Administrator', selected: user.role === 'ADMIN' },
  ], { disabled: isSelf });

  const toggle = h('button', {
    class: `btn btn-sm ${user.is_active ? 'btn-ghost' : 'btn-green'}`, type: 'button',
    text: user.is_active ? 'Deactivate' : 'Activate', disabled: isSelf,
    onclick: (event) => save(event.target, { is_active: !user.is_active }),
  });

  const saveRole = h('button', {
    class: 'btn btn-sm', type: 'button', text: 'Save role', disabled: isSelf,
    onclick: (event) => save(event.target, { role: roleSelect.value }),
  });

  async function save(button, patch) {
    await withBusy(button, async () => {
      try {
        await api.adminUpdateUser(user.id, { role: roleSelect.value, is_active: user.is_active, ...patch });
        toast('Account updated.', 'success');
        await reload();
      } catch (err) {
        toast(err.message, 'error');
      }
    });
  }

  return h('tr', null,
    h('td', null, h('div', { text: user.full_name }),
      isSelf ? h('div', { class: 'appt-meta', text: 'this is you' }) : null),
    h('td', null, h('div', { text: user.email }),
      h('div', { class: 'appt-meta', text: user.phone || '' })),
    h('td', null, roleSelect),
    h('td', null, h('span', { class: `badge badge-${user.is_active ? 'CHECKED_IN' : 'NO_SHOW'}`,
      text: user.is_active ? 'Active' : 'Inactive' })),
    h('td', null, h('div', { class: 'btn-row' }, saveRole, toggle)));
}

// ----------------------------------------------------------- clinic setup

export async function renderClinicSetup() {
  const page = shell('Clinic setup', 'Services, clinicians and the weekly availability that slots are generated from.');
  const servicesSlot = h('div');
  const practitionersSlot = h('div');
  const availabilitySlot = h('div');

  page.append(
    h('div', { class: 'grid grid-2' },
      h('div', { class: 'card' }, h('h2', { text: 'Services' }), servicesSlot),
      h('div', { class: 'card' }, h('h2', { text: 'Clinicians' }), practitionersSlot)),
    h('div', { class: 'card' },
      h('h2', { text: 'Weekly availability' }),
      h('p', { class: 'card-sub', text: 'Bookable times are generated from these windows, minus anything already booked.' }),
      availabilitySlot));

  await loadServices(servicesSlot);
  await loadPractitioners(practitionersSlot, availabilitySlot);
}

async function loadServices(slot) {
  slot.replaceChildren(h('p', { class: 'hint', text: 'Loading…' }));
  try {
    const result = await api.adminServices();
    const nameInput = input('svc_name', { type: 'text', required: true });
    const durationInput = input('svc_duration', { type: 'number', min: 5, max: 240, step: 5, value: 30 });
    const submit = h('button', { class: 'btn btn-sm', type: 'submit', text: 'Add service' });

    const form = h('form', { class: 'toolbar', novalidate: true },
      field('Name', nameInput), field('Minutes', durationInput), submit);

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      await withBusy(submit, async () => {
        try {
          await api.adminCreateService({
            name: nameInput.value.trim(), duration_min: Number(durationInput.value), description: '',
          });
          toast('Service added.', 'success');
          await loadServices(slot);
        } catch (err) { toast(err.message, 'error'); }
      });
    });

    const rows = result.items.map((service) => h('tr', null,
      h('td', { text: service.name }),
      h('td', { class: 'num', text: `${service.duration_min} min` }),
      h('td', null, h('span', {
        class: `badge badge-${service.is_active ? 'CHECKED_IN' : 'CANCELLED'}`,
        text: service.is_active ? 'Active' : 'Retired' })),
      h('td', null, h('button', {
        class: 'btn btn-sm btn-ghost', type: 'button',
        text: service.is_active ? 'Retire' : 'Restore',
        onclick: (event) => withBusy(event.target, async () => {
          try {
            await api.adminUpdateService(service.id, { is_active: !service.is_active });
            await loadServices(slot);
          } catch (err) { toast(err.message, 'error'); }
        }),
      }))));

    slot.replaceChildren(form, h('div', { class: 'table-wrap' }, h('table', null,
      h('thead', null, h('tr', null, ['Service', 'Duration', 'Status', ''].map((t) => h('th', { text: t })))),
      h('tbody', null, rows))));
  } catch (err) {
    slot.replaceChildren(notice('error', err.message));
  }
}

async function loadPractitioners(slot, availabilitySlot) {
  slot.replaceChildren(h('p', { class: 'hint', text: 'Loading…' }));
  try {
    const result = await api.adminPractitioners();
    const nameInput = input('prac_name', { type: 'text', required: true });
    const specialtyInput = input('prac_specialty', { type: 'text' });
    const roomInput = input('prac_room', { type: 'text' });
    const submit = h('button', { class: 'btn btn-sm', type: 'submit', text: 'Add' });

    const form = h('form', { class: 'toolbar', novalidate: true },
      field('Name', nameInput), field('Specialty', specialtyInput), field('Room', roomInput), submit);

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      await withBusy(submit, async () => {
        try {
          await api.adminCreatePractitioner({
            full_name: nameInput.value.trim(),
            specialty: specialtyInput.value.trim(),
            room: roomInput.value.trim(),
          });
          toast('Clinician added.', 'success');
          await loadPractitioners(slot, availabilitySlot);
        } catch (err) { toast(err.message, 'error'); }
      });
    });

    const rows = result.items.map((practitioner) => h('tr', null,
      h('td', null, h('div', { text: practitioner.full_name }),
        h('div', { class: 'appt-meta', text: practitioner.specialty || '' })),
      h('td', { text: practitioner.room || '—' }),
      h('td', null, h('span', {
        class: `badge badge-${practitioner.is_active ? 'CHECKED_IN' : 'CANCELLED'}`,
        text: practitioner.is_active ? 'Active' : 'Inactive' })),
      h('td', null, h('button', {
        class: 'btn btn-sm btn-ghost', type: 'button',
        text: practitioner.is_active ? 'Deactivate' : 'Activate',
        onclick: (event) => withBusy(event.target, async () => {
          try {
            await api.adminUpdatePractitioner(practitioner.id, { is_active: !practitioner.is_active });
            await loadPractitioners(slot, availabilitySlot);
          } catch (err) { toast(err.message, 'error'); }
        }),
      }))));

    slot.replaceChildren(form, h('div', { class: 'table-wrap' }, h('table', null,
      h('thead', null, h('tr', null, ['Clinician', 'Room', 'Status', ''].map((t) => h('th', { text: t })))),
      h('tbody', null, rows))));

    await loadAvailability(availabilitySlot, result.items.filter((p) => p.is_active));
  } catch (err) {
    slot.replaceChildren(notice('error', err.message));
  }
}

async function loadAvailability(slot, practitioners) {
  if (!practitioners.length) {
    slot.replaceChildren(empty('Add a clinician first'));
    return;
  }

  const practitionerSelect = select('avail_practitioner',
    practitioners.map((p) => ({ value: p.id, label: p.full_name })));
  const weekdaySelect = select('avail_weekday',
    [0, 1, 2, 3, 4, 5, 6].map((d) => ({ value: d, label: weekdayName(d) })));
  const startInput = input('avail_start', { type: 'time', value: '08:00', step: 900 });
  const endInput = input('avail_end', { type: 'time', value: '12:00', step: 900 });
  const submit = h('button', { class: 'btn btn-sm', type: 'submit', text: 'Add window' });
  const listSlot = h('div');

  const form = h('form', { class: 'toolbar', novalidate: true },
    field('Clinician', practitionerSelect), field('Day', weekdaySelect),
    field('From', startInput), field('To', endInput), submit);

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    await withBusy(submit, async () => {
      try {
        await api.adminCreateAvailability({
          practitioner_id: Number(practitionerSelect.value),
          weekday: Number(weekdaySelect.value),
          start_time: startInput.value,
          end_time: endInput.value,
        });
        toast('Availability added.', 'success');
        await loadList();
      } catch (err) { toast(err.message, 'error'); }
    });
  });

  async function loadList() {
    listSlot.replaceChildren(h('p', { class: 'hint', text: 'Loading…' }));
    try {
      const result = await api.adminAvailability(practitionerSelect.value);
      const active = result.items.filter((r) => r.is_active);
      if (!active.length) {
        listSlot.replaceChildren(notice('warn',
          'This clinician has no availability, so no appointments can be booked with them.'));
        return;
      }
      listSlot.replaceChildren(h('div', { class: 'table-wrap' }, h('table', null,
        h('thead', null, h('tr', null, ['Day', 'From', 'To', ''].map((t) => h('th', { text: t })))),
        h('tbody', null, active.map((rule) => h('tr', null,
          h('td', { text: weekdayName(rule.weekday) }),
          h('td', { text: rule.start_time }),
          h('td', { text: rule.end_time }),
          h('td', null, h('button', {
            class: 'btn btn-sm btn-ghost', type: 'button', text: 'Remove',
            onclick: (event) => withBusy(event.target, async () => {
              try {
                await api.adminDeleteAvailability(rule.id);
                toast('Window removed.', 'success');
                await loadList();
              } catch (err) { toast(err.message, 'error'); }
            }),
          }))))))));
    } catch (err) {
      listSlot.replaceChildren(notice('error', err.message));
    }
  }

  practitionerSelect.addEventListener('change', loadList);
  slot.replaceChildren(form, listSlot);
  await loadList();
}

// -------------------------------------------------------------- audit log

export async function renderAudit() {
  const page = shell('Audit log', 'Every security-relevant and state-changing action, most recent first.');
  const actionInput = input('action', { type: 'search', placeholder: 'e.g. LOGIN_FAILED' });
  const slot = h('div');

  page.append(h('div', { class: 'card' },
    h('form', { class: 'toolbar', novalidate: true,
      onsubmit: (e) => { e.preventDefault(); load(); } },
      field('Action', actionInput),
      h('button', { class: 'btn', type: 'submit', text: 'Filter' }),
      h('button', { class: 'btn btn-ghost', type: 'button', text: 'Clear',
        onclick: () => { actionInput.value = ''; load(); } })),
    slot));

  async function load() {
    slot.replaceChildren(h('p', { class: 'hint', text: 'Loading…' }));
    try {
      const result = await api.adminAudit({ action: actionInput.value.trim(), limit: 50 });
      if (!result.items.length) { slot.replaceChildren(empty('No matching entries')); return; }
      slot.replaceChildren(
        h('p', { class: 'card-sub', text: `${result.total} entries · showing the most recent ${result.items.length}` }),
        h('div', { class: 'table-wrap' }, h('table', null,
          h('thead', null, h('tr', null,
            ['When', 'Who', 'Action', 'Entity', 'Detail', 'IP'].map((t) => h('th', { text: t })))),
          h('tbody', null, result.items.map((entry) => h('tr', null,
            h('td', { text: entry.created_at.replace('T', ' ') }),
            h('td', { text: entry.actor_email || 'anonymous' }),
            h('td', null, h('strong', { text: entry.action })),
            h('td', { text: entry.entity_id ? `${entry.entity} ${entry.entity_id}` : entry.entity }),
            h('td', { text: entry.details || '' }),
            h('td', { class: 'appt-meta', text: entry.ip_address || '' })))))));
    } catch (err) {
      slot.replaceChildren(notice('error', err.message));
    }
  }

  await load();
}
