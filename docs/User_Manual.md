# User Manual

## TheClinicue: Outpatient Appointment & Queue Management System

**Version:** 1.0
**For:** Patients, reception staff and clinic administrators
**Last updated:** 13 August 2026

---

## 1. Before You Start

### 1.1 What TheClinicue does

TheClinicue lets you book a clinic appointment before you travel, and gives you a ticket number when you arrive so you can see how long the wait really is. Staff use it to run the day's list and call patients in order. Managers use it to see attendance and waiting times.

### 1.2 What TheClinicue does not do

**TheClinicue holds no medical information.** No diagnoses, no prescriptions, no test results, no notes about your health. It stores only your name, email address and phone number, and the appointments you have booked. Your paper or electronic medical record is entirely separate.

### 1.3 What you need

- A phone, tablet or computer with a web browser (Chrome, Firefox, Safari or Edge).
- An internet connection. A slow connection is fine - the whole application is about the size of one photograph.
- Nothing to install.

### 1.4 Getting in

Open the clinic's TheClinicue address in your browser. You will see the sign-in page.

**Demonstration accounts** (for the assessed demonstration only):

| Role | Email | Password |
|---|---|---|
| Patient | `patient@theclinicue.com` | `Patient#2026` |
| Reception staff | `staff@theclinicue.com` | `Staff#2026` |
| Administrator | `admin@theclinicue.com` | `Admin#2026` |

---

# PART A: For Patients

## 2. Creating Your Account

1. On the sign-in page, choose **Create account**.
2. Fill in:
   - **Full name** - as the clinic knows you.
   - **Email address** - this is how you sign in.
   - **Phone number** - so the clinic can reach you if plans change. Any format works: `0241112222` or `+233 24 111 2222`.
   - **Password** - at least 8 characters, with at least one letter and one number.
3. Choose **Create account**. You are signed in straight away and can book immediately.

> **If it says the email is already registered**, you already have an account. Go back to **Sign in** instead.

## 3. Booking an Appointment

1. Choose **Book** in the menu.
2. **Service** - pick what you are coming for. The length of the appointment is shown next to each one, for example *General Consultation (30 min)*.
3. **Clinician** - pick who you want to see.
4. **Date** - pick a day. You can book up to 60 days ahead.
5. **Available times** - the buttons show every time that is genuinely free. Tap one; it turns solid blue.
6. Choose **Confirm booking**.

You will see a green confirmation with your **booking code**, for example `TC-6S24CU`. Write it down or take a screenshot - the front desk can find you faster with it.

### 3.1 If no times are shown

The message tells you why:

| Message | What it means | What to do |
|---|---|---|
| *"This clinician does not work on Thursdays. They are available on: Monday, Wednesday, Friday."* | You picked a day they are not in. | Pick one of the days listed. |
| *"Every time on this day is taken."* | The clinician is fully booked. | Try the next day, or a different clinician. |
| *"This date has already passed."* | The date is in the past. | Pick today or later. |

### 3.2 If the time is taken while you are booking

If someone else books the same slot a moment before you, you will see:

> *"That time was just booked. Please choose another slot."*

The list refreshes automatically. Pick another time. Nothing was booked in your name - you have not been double-charged or double-booked.

### 3.3 One appointment per clinician per day

You cannot hold two appointments with the same clinician on the same day. If you try, you will see *"You already have an appointment with this practitioner on that day."* Cancel the first one if you want to move it.

## 4. Seeing and Cancelling Your Appointments

Choose **My appointments**.

- **Upcoming** - everything still to come, soonest first. Each card shows the date, time, service, clinician, room, status and booking code.
- **Past** - your history, including anything completed, cancelled or recorded as a no-show.

### 4.1 Cancelling

1. Find the appointment under **Upcoming**.
2. Choose **Cancel**.
3. Confirm when asked.

The time is released immediately for another patient. **Please cancel if you cannot attend** - it is the single most useful thing you can do for other patients, and it takes ten seconds.

You cannot cancel an appointment that has already been completed or that you missed.

## 5. On the Day: Your Ticket and Queue Position

1. Arrive at the clinic a few minutes early.
2. Give your **booking code** or your **name** at the front desk.
3. Reception checks you in and you are given a ticket number, for example **B-07**.

Open **My appointments** on your phone and you will see a yellow card at the top:

```
        YOUR TICKET TODAY
              B-07
      3 patients ahead of you
  Dr Akosua Mensah · Room 2 · now serving B-04
```

- **B-07** is your ticket.
- **3 patients ahead of you** counts only the people still waiting for your clinician.
- **now serving B-04** is who is with the clinician right now.

> **Refresh the page to update it.** The card does not refresh by itself in this version. Pull down on your phone, or reload the page, to see the latest position.

When your ticket is called, the card says *"You are being seen now - please go to the consulting room."*

## 6. Signing Out

Choose **Sign out**, top right. Always sign out on a shared or clinic computer.

---

# PART B: For Reception Staff

## 7. The Front Desk Screen

Sign in and choose **Front desk**. The screen has three areas:

- **Left** - the day sheet: every appointment for the chosen date.
- **Top right** - the live queue for one clinician.
- **Bottom right** - walk-in booking.

### 7.1 Finding a patient quickly

Use the toolbar above the day sheet:

| Control | Use |
|---|---|
| **Date** | Which day to show. **Today** jumps back to today. |
| **Clinician** | Show one clinician, or all of them. |
| **Status** | Show only, say, everyone still *Booked*. |
| **Search** | Type part of a name, a booking code, or a phone number. |

The fastest route is to type the booking code into **Search**.

## 8. Checking a Patient In

1. Find their row on the day sheet.
2. Choose **Check in**.

The patient is given the next ticket number for that clinician and joins the queue. Their status changes to *Checked in*.

**Common messages:**

| Message | Meaning | What to do |
|---|---|---|
| *"This patient has already been checked in."* | Someone checked them in already. | Nothing - they are in the queue. |
| *"Only appointments scheduled for today can be checked in. This one is for 2026-08-24."* | The appointment is for a different day. | If they have come on the wrong day, book them a walk-in slot instead (Section 10). |

## 9. Running the Queue

The **Live queue** panel on the right shows one clinician at a time. Change clinician with the dropdown.

- **Now serving** - the ticket currently with the clinician.
- **The list** - everyone still waiting, in order, with how long they have been waiting.

### 9.1 Calling the next patient

When the clinician is ready, choose **Call next patient**. The longest-waiting patient is called and the panel updates.

If nobody is waiting you will see *"Nobody is waiting for this practitioner."* - that is normal, not an error.

### 9.2 Finishing a consultation

When the patient leaves the room, find their row (now showing *In progress*) and choose **Complete**. This records the finish time and feeds the day's report.

### 9.3 Recording a no-show

If a patient never arrives, or leaves before being called, choose **No-show** on their row and confirm.

This matters more than it looks: the no-show rate is the main number the clinic manager uses to plan staffing. Recording it accurately is part of the job.

> **Note on names.** The queue panel shows shortened names such as `Y. D****`. This is deliberate - the panel may be visible to other patients, and full names should not be.

## 10. Walk-in Patients and Booking on Someone's Behalf

For a patient who arrives without an appointment, or who has no phone:

1. In the **Walk-in / book for a patient** panel, type part of their name or phone number and choose **Search**.
2. Choose **Select** next to the right person.
3. Pick the service, clinician, date and time.
4. Choose **Book for [name]**.

They now have a normal appointment and can be checked in.

> **If the patient is not found**, they have no account yet. Ask them to register on their phone, or register on their behalf using their details.

---

# PART C: For Administrators

## 11. Reports

Choose **Reports**.

### 11.1 Daily summary

Pick a date and choose **Show**:

| Figure | Meaning |
|---|---|
| **Total booked** | All appointments for the day, in any state. |
| **Completed** | Consultations that actually happened. |
| **No-show rate** | No-shows as a percentage of patients who were *expected*. Cancellations are excluded from the denominator - a patient who cancelled was not expected to attend, and counting them would flatter the figure. |
| **Mean wait** | Average minutes between check-in and being called. Shows `-` when nobody has been called yet. |
| **Cancelled** | Appointments cancelled in advance. |
| **Still waiting** | Patients checked in but not yet called. |

Below is a per-clinician count of consultations completed.

### 11.2 Clinician utilisation

Pick a date range. For each clinician you see slots offered, appointments made, utilisation as a bar, and no-show percentage.

Utilisation bars are green above 75%, amber 50-75%, red below 50%. A persistently red clinician has more capacity than demand; a persistently green one may need more hours.

> **Please read this figure as approximate.** Slots offered are calculated from each clinician's *current* weekly availability applied across the whole period. If you changed someone's hours during the range, their figure will be off for the earlier part. This is recorded as technical debt item TD-11 and is scheduled to be corrected in v1.1.

## 12. Clinic Setup

Choose **Clinic setup**. This page controls what patients can book.

### 12.1 Services

A service is a type of appointment with a fixed length. The length sets how the day is divided into slots - a 30-minute service produces 09:00, 09:30, 10:00; a 45-minute one produces 09:00, 09:45, 10:30.

- **To add:** type a name and a length in minutes, then choose **Add service**.
- **To withdraw:** choose **Retire**. It disappears from patient booking but old appointments keep their history. Choose **Restore** to bring it back.

Names must be unique, and length must be between 5 and 240 minutes.

### 12.2 Clinicians

- **To add:** enter name, specialty and room, then choose **Add**.
- **To remove:** choose **Deactivate**. They disappear from booking; their past appointments are preserved.

### 12.3 Weekly availability: the important one

**No availability means no appointments.** This is the most common setup mistake: a clinician is added, nobody sets their hours, and patients see "no times available" with no explanation.

To add a working window:

1. Choose the clinician.
2. Choose the day of the week.
3. Set **From** and **To**.
4. Choose **Add window**.

**Example.** Dr Mensah works 08:00-12:00 Monday to Friday, and also 13:00-16:00 on Monday, Wednesday and Friday. That is eight windows: five mornings plus three afternoons. Add the morning and afternoon as *separate* windows so the lunch break is genuinely unbookable.

Rules the system enforces:

- The end time must be after the start time.
- Windows for the same clinician and day may not overlap.
- Windows may touch: 08:00-12:00 and 12:00-16:00 is fine and means no lunch break.

Choose **Remove** to withdraw a window. Appointments already booked under it are not disturbed.

## 13. User Accounts

Choose **Users**.

- **To change a role:** pick the new role in the dropdown and choose **Save role**.
- **To disable an account:** choose **Deactivate**. They are signed out immediately, on their very next action, and cannot sign back in. Their records are kept.

| Role | Can do |
|---|---|
| **Patient** | Book and cancel their own appointments; see their own queue position. |
| **Staff** | Everything a patient can, plus the whole front desk. |
| **Administrator** | Everything, plus setup, users, audit and reports. |

> **You cannot change your own role or deactivate your own account.** This is deliberate: it prevents the last administrator from accidentally locking everyone out of the clinic's configuration, which cannot be undone from inside the application. Ask another administrator.

### 13.1 When someone leaves

Deactivate their account immediately. Do not delete it - deletion would orphan the appointments they created. Deactivation takes effect on their next request, even if they are signed in at that moment.

## 14. Audit Log

Choose **Audit log** to see every significant action: who did it, what they did, to what, when and from which address. Newest first.

Useful entries to look for:

| Action | Meaning |
|---|---|
| `LOGIN_FAILED` | A failed sign-in. A burst against one account may mean someone is guessing passwords. |
| `ACCESS_DENIED` | Someone tried to reach a page their role does not allow. |
| `BOOK_APPOINTMENT`, `CANCEL_APPOINTMENT` | Who made or cancelled a booking. |
| `CHECK_IN`, `CALL_NEXT`, `COMPLETE_CONSULTATION`, `MARK_NO_SHOW` | Front-desk activity. |
| `UPDATE_USER` | A role or account status was changed. |

Filter by typing an action name, for example `LOGIN_FAILED`, and choosing **Filter**.

---

# PART D: Reference

## 15. Appointment Statuses

| Status | Meaning |
|---|---|
| **Booked** | Reserved. The patient has not arrived. |
| **Checked in** | Arrived, in the queue with a ticket. |
| **In progress** | Called; with the clinician now. |
| **Completed** | Finished. |
| **Cancelled** | Called off in advance. The time was released. |
| **No show** | Did not attend. The time was not released. |

Statuses only move forwards: Booked → Checked in → In progress → Completed. Anything else is refused. That is why you cannot complete an appointment without checking the patient in first - the sequence is what keeps the reports honest.

## 16. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| *"Please sign in to continue."* | Your session expired (after 8 hours) or you signed out elsewhere. | Sign in again. |
| *"You do not have permission to do that."* | Your role does not allow it. | Ask an administrator if you need the access. |
| *"Your session token did not match. Please refresh and try again."* | The page has been open a very long time. | Reload the page and retry. |
| *"No connection to the clinic server."* | Your internet dropped, or the server is down. | Check your connection, then reload. Nothing you submitted was half-saved. |
| *"The system is busy right now. Please try again in a moment."* | Two people wrote at the same instant. | Wait a second and retry. |
| Queue position looks stale | The queue does not refresh by itself in this version. | Reload the page (TD-14, being fixed in v1.1). |
| No times available at all for a clinician | They have no availability set. | Administrator: add weekly availability (Section 12.3). |
| Patient not found in walk-in search | They have no account. | Register them, or ask them to register. |

## 17. Privacy and Your Data

- TheClinicue stores your **name, email address, phone number and appointments**. Nothing else.
- It stores **no medical information** of any kind.
- Your password is stored only as a one-way cryptographic hash. Nobody (including clinic staff and the developer) can read it. If you forget it, an administrator must reset it; they cannot tell you what it was.
- On the shared queue display your name is shortened, for example `Y. D****`.
- Every action on your record is logged with who did it and when.
- Only reception staff and administrators can see your appointments. Other patients cannot.

## 18. Getting Help

1. Check Section 16 above - most messages explain themselves.
2. Ask the clinic's TheClinicue administrator.
3. For faults, the administrator should record what was on screen, what was being attempted, the time, and the exact wording of any message, and check the audit log for the matching entry.

*End of User Manual v1.0.*
