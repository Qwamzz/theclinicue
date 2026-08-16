import { api } from '../api.js';
import {
  addDays, badge, confirmDialog, empty, field, formatDate, h, input, mount,
  notice, relativeDay, select, todayISO, toast, withBusy,
} from '../ui.js';

const STATUSES = ['', 'BOOKED', 'CHECKED_IN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'NO_SHOW'];

export async function renderStaffConsole() {
  const page = h('div');
  mount(page);
  page.append(h('div', { class: 'page-head' },
    h('h1', { text: 'Front desk' }),
    h('p', { text: 'Check patients in, run the queue and register walk-ins.' })));

  let practitioners = [];
  try {
    practitioners = (await api.practitioners()).items;
  } catch (err) {
    page.append(notice('error', err.message));
    return;
  }
  if (!practitioners.length) {
    page.append(empty('No clinicians configured', 'An administrator needs to add practitioners first.'));
    return;
  }

  const dateInput = input('date', { type: 'date', value: todayISO() });
  const practitionerSelect = select('practitioner_id',
    [{ value: '', label: 'All clinicians' },
      ...practitioners.map((p) => ({ value: p.id, label: p.full_name }))]);
  const statusSelect = select('status',
    STATUSES.map((s) => ({ value: s, label: s ? s.replace(/_/g, ' ') : 'All statuses' })));
  const searchInput = input('q', { type: 'search', placeholder: 'Name, code or phone' });

  const queueSelect = select('queue_practitioner',
    practitioners.map((p) => ({ value: p.id, label: p.full_name })));

  const sheetSlot = h('div');
  const queueSlot = h('div');

  const toolbar = h('form', { class: 'toolbar', novalidate: true,
    onsubmit: (event) => { event.preventDefault(); reloadSheet(); } },
    field('Date', dateInput),
    field('Clinician', practitionerSelect),
    field('Status', statusSelect),
    field('Search', searchInput),
    h('button', { class: 'btn', type: 'submit', text: 'Apply' }),
    h('button', {
      class: 'btn btn-ghost', type: 'button', text: 'Today',
      onclick: () => { dateInput.value = todayISO(); reloadSheet(); },
    }));

  const layout = h('div', { class: 'grid grid-3' },
    h('div', null, h('div', { class: 'card' }, toolbar, sheetSlot)),
    h('div', null, h('div', { class: 'card' },
      h('h2', { text: 'Live queue' }),
      field('Clinician', queueSelect),
      queueSlot),
      walkInCard(() => reloadSheet())));

  page.append(layout);

  async function reloadSheet() {
    sheetSlot.replaceChildren(h('p', { class: 'hint', text: 'Loading...' }));
    try {
      const result = await api.daySheet({
        date: dateInput.value || todayISO(),
        practitioner_id: practitionerSelect.value,
        status: statusSelect.value,
        q: searchInput.value.trim(),
      });
      sheetSlot.replaceChildren(daySheetTable(result, reloadSheet, reloadQueue));
    } catch (err) {
      sheetSlot.replaceChildren(notice('error', err.message));
    }
  }

  async function reloadQueue() {
    queueSlot.replaceChildren(h('p', { class: 'hint', text: 'Loading...' }));
    try {
      const queue = await api.liveQueue(queueSelect.value, todayISO());
      queueSlot.replaceChildren(queuePanel(queue, reloadSheet, reloadQueue));
    } catch (err) {
      queueSlot.replaceChildren(notice('error', err.message));
    }
  }

  queueSelect.addEventListener('change', reloadQueue);
  dateInput.addEventListener('change', reloadSheet);
  practitionerSelect.addEventListener('change', reloadSheet);
  statusSelect.addEventListener('change', reloadSheet);

  await reloadSheet();
  await reloadQueue();
}

// ------------------------------------------------------------- day sheet

function daySheetTable(result, reloadSheet, reloadQueue) {
  if (!result.items.length) {
    return empty('No appointments match',
      'Try clearing the filters, or choose a different date.');
  }

  const rows = result.items.map((appointment) => {
    const actions = h('div', { class: 'btn-row' });

    if (appointment.status === 'BOOKED') {
      actions.append(h('button', {
        class: 'btn btn-sm', type: 'button', text: 'Check in',
        onclick: (event) => act(event.target, () => api.checkIn(appointment.id),
          'Checked in.', reloadSheet, reloadQueue),
      }));
    }
    if (appointment.status === 'IN_PROGRESS') {
      actions.append(h('button', {
        class: 'btn btn-sm btn-green', type: 'button', text: 'Complete',
        onclick: (event) => act(event.target, () => api.complete(appointment.id),
          'Consultation completed.', reloadSheet, reloadQueue),
      }));
    }
    if (['BOOKED', 'CHECKED_IN'].includes(appointment.status)) {
      actions.append(h('button', {
        class: 'btn btn-sm btn-ghost', type: 'button', text: 'No-show',
        onclick: async (event) => {
          const ok = await confirmDialog('Mark as no-show?',
            `${appointment.patient_name} at ${appointment.start_time}. This is recorded in the daily report.`,
            'Mark no-show');
          if (ok) await act(event.target, () => api.noShow(appointment.id),
            'Recorded as a no-show.', reloadSheet, reloadQueue);
        },
      }));
    }
    if (!actions.childElementCount) actions.append(h('span', { class: 'hint', text: '-' }));

    return h('tr', null,
      h('td', null, h('strong', { text: appointment.start_time })),
      h('td', null,
        h('div', { text: appointment.patient_name }),
        h('div', { class: 'appt-meta', text: appointment.patient_phone || '' })),
      h('td', null,
        h('div', { text: appointment.service_name }),
        h('div', { class: 'appt-meta', text: appointment.practitioner_name })),
      h('td', null, h('span', { class: 'appt-code', text: appointment.code })),
      h('td', null, badge(appointment.status),
        appointment.ticket_no ? h('div', { class: 'appt-meta', text: `Ticket ${appointment.ticket_no}` }) : null),
      h('td', null, actions));
  });

  return h('div', null,
    h('p', { class: 'card-sub',
      text: `${result.total} appointment${result.total === 1 ? '' : 's'} on ${formatDate(result.date)}` }),
    h('div', { class: 'table-wrap' },
      h('table', null,
        h('thead', null, h('tr', null,
          ['Time', 'Patient', 'Service', 'Code', 'Status', 'Action']
            .map((label) => h('th', { text: label })))),
        h('tbody', null, rows))));
}

async function act(button, action, successMessage, reloadSheet, reloadQueue) {
  await withBusy(button, async () => {
    try {
      await action();
      toast(successMessage, 'success');
      await reloadSheet();
      await reloadQueue();
    } catch (err) {
      toast(err.message, 'error');
      // A conflict usually means someone else already changed this row, so a
      // refresh is more useful than leaving stale buttons on screen.
      if (err.status === 409) await reloadSheet();
    }
  });
}

// ------------------------------------------------------------ queue panel

function queuePanel(queue, reloadSheet, reloadQueue) {
  const parts = [];

  parts.push(queue.now_serving
    ? h('div', { class: 'now-serving' },
      h('span', { text: 'Now serving' }),
      h('strong', { text: queue.now_serving.ticket }))
    : h('div', { class: 'now-serving' },
      h('span', { text: 'Now serving' }), h('strong', { text: '-' })));

  if (queue.waiting.length) {
    parts.push(h('ul', { class: 'queue-list' }, queue.waiting.map((entry) =>
      h('li', null,
        h('span', { class: 'tk', text: entry.ticket }),
        h('span', { text: entry.name }),
        h('span', { class: 'wait',
          text: entry.waiting_minutes === null ? '' : `waiting ${entry.waiting_minutes} min` })))));
  } else {
    parts.push(h('p', { class: 'hint', text: 'Nobody is waiting.' }));
  }

  parts.push(h('button', {
    class: 'btn btn-green btn-block', type: 'button', text: 'Call next patient',
    disabled: queue.waiting.length === 0,
    onclick: async (event) => {
      await withBusy(event.target, async () => {
        try {
          const result = await api.callNext(queue.practitioner_id);
          toast(result.called ? `Calling ${result.called.ticket} - ${result.called.patient_name}.`
            : result.message, result.called ? 'success' : '');
          await reloadQueue();
          await reloadSheet();
        } catch (err) {
          toast(err.message, 'error');
        }
      });
    },
  }));

  parts.push(h('p', { class: 'hint',
    text: 'Patient names are shortened here because this panel may be visible to others.' }));

  return h('div', null, ...parts);
}

// ---------------------------------------------------------------- walk-in

function walkInCard(onBooked) {
  const searchInput = input('walk_q', { type: 'search', placeholder: 'Search patient name or phone' });
  const resultSlot = h('div');
  const formSlot = h('div');

  const card = h('div', { class: 'card' },
    h('h2', { text: 'Walk-in / book for a patient' }),
    h('p', { class: 'card-sub', text: 'For patients who arrive without an appointment.' }),
    field('Find the patient', searchInput),
    h('button', {
      class: 'btn btn-ghost btn-sm', type: 'button', text: 'Search',
      onclick: async (event) => {
        const needle = searchInput.value.trim();
        if (needle.length < 2) { toast('Enter at least two characters.', 'error'); return; }
        await withBusy(event.target, async () => {
          try {
            const result = await api.findPatients(needle);
            resultSlot.replaceChildren(result.items.length
              ? h('ul', { class: 'queue-list' }, result.items.map((patient) =>
                h('li', null,
                  h('span', { text: patient.full_name }),
                  h('button', {
                    class: 'btn btn-sm btn-ghost', type: 'button', text: 'Select',
                    style: { marginLeft: 'auto' },
                    onclick: () => showWalkInForm(patient, formSlot, onBooked),
                  }))))
              : h('p', { class: 'hint', text: 'No patient found. Ask them to register, or check the spelling.' }));
          } catch (err) {
            resultSlot.replaceChildren(notice('error', err.message));
          }
        });
      },
    }),
    resultSlot, formSlot);

  return card;
}

async function showWalkInForm(patient, slot, onBooked) {
  slot.replaceChildren(h('p', { class: 'hint', text: 'Loading options...' }));
  try {
    const [services, practitioners] = await Promise.all([
      api.services().then((r) => r.items),
      api.practitioners().then((r) => r.items),
    ]);

    const serviceSelect = select('walk_service',
      services.map((s) => ({ value: s.id, label: `${s.name} (${s.duration_min} min)` })));
    const practitionerSelect = select('walk_practitioner',
      practitioners.map((p) => ({ value: p.id, label: p.full_name })));
    const dateInput = input('walk_date', { type: 'date', value: todayISO(), min: todayISO(), max: addDays(todayISO(), 60) });
    const slotSelect = select('walk_slot', [{ value: '', label: 'Choose a time' }]);
    const submit = h('button', { class: 'btn btn-block', type: 'submit', text: `Book for ${patient.full_name}` });

    async function loadTimes() {
      slotSelect.replaceChildren(h('option', { value: '', text: 'Loading...' }));
      try {
        const result = await api.slots(practitionerSelect.value, serviceSelect.value, dateInput.value);
        slotSelect.replaceChildren(
          h('option', { value: '', text: result.slots.length ? 'Choose a time' : 'No times available' }),
          ...result.slots.map((s) => h('option', { value: s.start_time, text: s.start_time })));
      } catch (err) {
        slotSelect.replaceChildren(h('option', { value: '', text: err.message }));
      }
    }

    const form = h('form', { novalidate: true, style: { marginTop: '.75rem' } },
      field('Service', serviceSelect),
      field('Clinician', practitionerSelect),
      field('Date', dateInput),
      field('Time', slotSelect),
      submit);

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!slotSelect.value) { toast('Choose a time.', 'error'); return; }
      await withBusy(submit, async () => {
        try {
          const booking = await api.book({
            patient_id: patient.id,
            practitioner_id: Number(practitionerSelect.value),
            service_id: Number(serviceSelect.value),
            date: dateInput.value,
            start_time: slotSelect.value,
            walk_in: dateInput.value === todayISO(),
          });
          toast(`Booked ${booking.code} for ${patient.full_name}.`, 'success');
          slot.replaceChildren(notice('success',
            `${patient.full_name} - ${relativeDay(booking.date)} at ${booking.start_time}, code ${booking.code}.`));
          await onBooked();
        } catch (err) {
          toast(err.message, 'error');
          await loadTimes();
        }
      });
    });

    [serviceSelect, practitionerSelect, dateInput].forEach((el) =>
      el.addEventListener('change', loadTimes));

    slot.replaceChildren(form);
    await loadTimes();
  } catch (err) {
    slot.replaceChildren(notice('error', err.message));
  }
}
