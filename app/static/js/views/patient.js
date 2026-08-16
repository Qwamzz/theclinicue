import { api, ApiError } from '../api.js';
import {
  addDays, badge, confirmDialog, empty, field, formatDate, h, input, mount,
  notice, relativeDay, select, todayISO, toast, weekdayName, withBusy,
} from '../ui.js';

// ---------------------------------------------------------------- booking

export async function renderBooking() {
  const page = h('div');
  mount(page);
  page.append(h('div', { class: 'page-head' },
    h('h1', { text: 'Book an appointment' }),
    h('p', { text: 'Pick a service, a clinician and a time. You will get a booking code straight away.' })));

  let services = [];
  let practitioners = [];
  try {
    [services, practitioners] = await Promise.all([
      api.services().then((r) => r.items),
      api.practitioners().then((r) => r.items),
    ]);
  } catch (err) {
    page.append(notice('error', err.message));
    return;
  }

  if (!services.length || !practitioners.length) {
    page.append(empty('Booking is not available yet',
      'The clinic has not finished setting up its services. Please try later.'));
    return;
  }

  const serviceSelect = select('service_id',
    services.map((s) => ({ value: s.id, label: `${s.name} (${s.duration_min} min)` })));
  const practitionerSelect = select('practitioner_id',
    practitioners.map((p) => ({ value: p.id, label: `${p.full_name} - ${p.specialty || 'Clinician'}` })));
  const dateInput = input('date', {
    type: 'date', min: todayISO(), max: addDays(todayISO(), 60), value: addDays(todayISO(), 1),
  });

  const slotArea = h('div');
  const resultArea = h('div');
  let chosenSlot = null;
  let workingDays = [];

  const form = h('form', { class: 'card', novalidate: true },
    h('h2', { text: 'Choose your appointment' }),
    field('Service', serviceSelect),
    field('Clinician', practitionerSelect),
    field('Date', dateInput),
    slotArea);

  page.append(resultArea, form);

  async function loadWorkingDays() {
    try {
      const result = await api.availability(practitionerSelect.value);
      workingDays = result.weekdays || [];
    } catch {
      workingDays = [];
    }
  }

  async function loadSlots() {
    chosenSlot = null;
    slotArea.replaceChildren(h('p', { class: 'hint', text: 'Looking for free times...' }));

    const date = dateInput.value;
    if (!date) {
      slotArea.replaceChildren(notice('warn', 'Choose a date to see available times.'));
      return;
    }

    // Explain an empty result before asking the server, so the user gets a
    // useful reason rather than a bare "no times".
    const weekday = (new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7;
    if (workingDays.length && !workingDays.includes(weekday)) {
      const names = workingDays.map(weekdayName).join(', ');
      slotArea.replaceChildren(notice('warn',
        `This clinician does not work on ${weekdayName(weekday)}s. They are available on: ${names}.`));
      return;
    }

    try {
      const result = await api.slots(practitionerSelect.value, serviceSelect.value, date);
      if (!result.slots.length) {
        slotArea.replaceChildren(notice('warn',
          'Every time on this day is taken. Try the next day, or another clinician.'));
        return;
      }
      const grid = h('div', { class: 'slots' });
      for (const slot of result.slots) {
        const button = h('button', {
          type: 'button', class: 'slot', 'aria-pressed': 'false',
          text: slot.start_time,
          onclick: () => {
            grid.querySelectorAll('.slot').forEach((b) => b.setAttribute('aria-pressed', 'false'));
            button.setAttribute('aria-pressed', 'true');
            chosenSlot = slot.start_time;
            confirmButton.disabled = false;
          },
        });
        grid.append(button);
      }
      slotArea.replaceChildren(
        h('label', { text: `Available times - ${formatDate(date)}` }),
        grid,
        h('p', { class: 'hint', text: `Each appointment lasts ${result.duration_min} minutes.` }),
        confirmButton);
    } catch (err) {
      slotArea.replaceChildren(notice('error', err.message));
    }
  }

  const confirmButton = h('button', {
    type: 'submit', class: 'btn btn-green btn-block', text: 'Confirm booking', disabled: true,
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!chosenSlot) {
      toast('Choose a time first.', 'error');
      return;
    }
    await withBusy(confirmButton, async () => {
      try {
        const booking = await api.book({
          practitioner_id: Number(practitionerSelect.value),
          service_id: Number(serviceSelect.value),
          date: dateInput.value,
          start_time: chosenSlot,
        });
        resultArea.replaceChildren(bookingReceipt(booking));
        toast('Appointment booked.', 'success');
        await loadSlots();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      } catch (err) {
        resultArea.replaceChildren(notice('error', err.message));
        if (err instanceof ApiError && err.code === 'SLOT_TAKEN') await loadSlots();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  });

  practitionerSelect.addEventListener('change', async () => {
    await loadWorkingDays();
    await loadSlots();
  });
  serviceSelect.addEventListener('change', loadSlots);
  dateInput.addEventListener('change', loadSlots);

  await loadWorkingDays();
  await loadSlots();
}

function bookingReceipt(booking) {
  return h('div', { class: 'card', style: { borderLeft: '4px solid var(--green)' } },
    h('h2', { text: 'Appointment confirmed' }),
    h('p', { class: 'appt-when', text: `${relativeDay(booking.date)} at ${booking.start_time}` }),
    h('p', { class: 'appt-meta', text: `${booking.service_name} with ${booking.practitioner_name}${booking.room ? ` · ${booking.room}` : ''}` }),
    h('p', null, 'Your booking code is ', h('strong', { text: booking.code })),
    h('p', { class: 'hint', text: 'Please arrive 10 minutes early and give this code at the front desk.' }));
}

// -------------------------------------------------------- my appointments

export async function renderMyAppointments() {
  const page = h('div');
  mount(page);
  page.append(h('div', { class: 'page-head' },
    h('h1', { text: 'My appointments' }),
    h('p', { text: 'Everything you have booked, and your place in today's queue.' })));

  const queueSlot = h('div');
  const listSlot = h('div');
  page.append(queueSlot, listSlot);

  await refreshQueue(queueSlot);
  await refreshList(listSlot);
}

async function refreshQueue(slot) {
  try {
    const { position } = await api.myPosition();
    if (!position) {
      slot.replaceChildren();
      return;
    }
    const ahead = position.ahead;
    const aheadText = position.status === 'CALLED'
      ? 'You are being seen now - please go to the consulting room.'
      : ahead === 0 ? 'You are next.' : `${ahead} ${ahead === 1 ? 'patient is' : 'patients are'} ahead of you.`;

    slot.replaceChildren(h('div', { class: 'card' },
      h('div', { class: 'ticket-card' },
        h('div', { class: 'ticket-label', text: 'YOUR TICKET TODAY' }),
        h('div', { class: 'ticket-no', text: position.ticket }),
        h('div', { class: 'ticket-note', text: aheadText }),
        h('div', { class: 'ticket-sub',
          text: `${position.practitioner_name}${position.room ? ` · ${position.room}` : ''}`
            + (position.now_serving ? ` · now serving ${position.now_serving}` : '') })),
      h('p', { class: 'hint', text: 'This updates when you refresh the page.' })));
  } catch {
    slot.replaceChildren();     // a queue lookup failure must not block the list
  }
}

async function refreshList(slot) {
  slot.replaceChildren(h('p', { class: 'hint', text: 'Loading...' }));
  try {
    const [upcoming, past] = await Promise.all([
      api.myAppointments('upcoming'),
      api.myAppointments('past'),
    ]);

    const children = [h('div', { class: 'card' },
      h('h2', { text: 'Upcoming' }),
      upcoming.items.length
        ? h('ul', { class: 'appt-list' }, upcoming.items.map((a) => appointmentCard(a, slot)))
        : empty('Nothing booked yet', 'Use "Book an appointment" to reserve a time.'))];

    if (past.items.length) {
      children.push(h('div', { class: 'card' },
        h('h2', { text: 'Past' }),
        h('ul', { class: 'appt-list' }, past.items.slice(0, 12).map((a) => appointmentCard(a, slot)))));
    }
    slot.replaceChildren(...children);
  } catch (err) {
    slot.replaceChildren(notice('error', err.message));
  }
}

function appointmentCard(appointment, listSlot) {
  const cancellable = appointment.status === 'BOOKED';
  const classes = ['appt'];
  if (['COMPLETED', 'NO_SHOW'].includes(appointment.status)) classes.push('done');
  if (appointment.status === 'CANCELLED') classes.push('cancelled');

  const actions = h('div', { class: 'appt-actions' });
  if (cancellable) {
    actions.append(h('button', {
      class: 'btn btn-ghost btn-sm', type: 'button', text: 'Cancel',
      onclick: async (event) => {
        const ok = await confirmDialog(
          'Cancel this appointment?',
          `${relativeDay(appointment.date)} at ${appointment.start_time} with ${appointment.practitioner_name}. `
          + 'The time will be offered to another patient.',
          'Yes, cancel it');
        if (!ok) return;
        await withBusy(event.target, async () => {
          try {
            await api.cancel(appointment.id);
            toast('Appointment cancelled.', 'success');
            await refreshList(listSlot);
          } catch (err) {
            toast(err.message, 'error');
          }
        });
      },
    }));
  }

  return h('li', { class: classes.join(' ') },
    h('div', { class: 'appt-when', text: `${relativeDay(appointment.date)} · ${appointment.start_time}` }),
    h('div', { class: 'appt-meta', text: appointment.service_name }),
    h('div', { class: 'appt-meta',
      text: `${appointment.practitioner_name}${appointment.room ? ` · ${appointment.room}` : ''}` }),
    h('div', { style: { marginTop: '.35rem' } },
      badge(appointment.status), ' ',
      h('span', { class: 'appt-code', text: appointment.code }),
      appointment.ticket_no ? h('span', { class: 'appt-code', text: ` · ticket ${appointment.ticket_no}` }) : null),
    cancellable ? actions : null);
}
