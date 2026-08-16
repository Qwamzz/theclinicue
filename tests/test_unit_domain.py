"""Unit tests for domain helpers and the appointment state machine
(TC-U-01 to TC-U-07, TC-U-21 to TC-U-26)."""

from __future__ import annotations

import pytest

from app.domain import (
    BOOKED,
    CANCELLED,
    CHECKED_IN,
    COMPLETED,
    IN_PROGRESS,
    NO_SHOW,
    TRANSITIONS,
    add_days,
    can_transition,
    is_date,
    is_time,
    mask_name,
    new_appointment_code,
    ticket_label,
    to_hhmm,
    to_minutes,
    weekday_of,
)


class TestTimeConversion:
    @pytest.mark.parametrize(
        "text,minutes",
        [("00:00", 0), ("08:00", 480), ("09:30", 570), ("12:00", 720), ("23:59", 1439)],
    )
    def test_round_trip(self, text, minutes):
        assert to_minutes(text) == minutes
        assert to_hhmm(minutes) == text

    @pytest.mark.parametrize("bad", ["9:30", "24:00", "08:60", "0800", "", "abc", "08:0a"])
    def test_malformed_times_are_rejected(self, bad):
        """TC-U-02. Rejecting rather than coercing is what stops a bad string
        silently becoming a valid-looking appointment."""
        with pytest.raises(ValueError):
            to_minutes(bad)

    def test_hhmm_rejects_out_of_range_minutes(self):
        with pytest.raises(ValueError):
            to_hhmm(-1)
        with pytest.raises(ValueError):
            to_hhmm(24 * 60 + 1)


class TestDateHelpers:
    def test_valid_dates_accepted(self):
        assert is_date("2026-08-12")
        assert is_date("2024-02-29")            # a real leap day

    @pytest.mark.parametrize("bad", ["2026-02-30", "2026-13-01", "12-08-2026", "2026/08/12", "", "2026-8-1"])
    def test_invalid_dates_rejected(self, bad):
        assert not is_date(bad)

    def test_add_days_crosses_month_and_year_boundaries(self):
        assert add_days("2026-08-31", 1) == "2026-09-01"
        assert add_days("2026-12-31", 1) == "2027-01-01"
        assert add_days("2026-01-01", -1) == "2025-12-31"

    def test_weekday_uses_monday_as_zero(self):
        """The availability table stores 0 = Monday; an off-by-one here would
        offer every appointment on the wrong day."""
        assert weekday_of("2026-08-10") == 0   # Monday
        assert weekday_of("2026-08-12") == 2   # Wednesday
        assert weekday_of("2026-08-16") == 6   # Sunday

    def test_time_format_validator(self):
        assert is_time("08:00")
        assert not is_time("8:00")
        assert not is_time("25:00")


class TestStateMachine:
    """TC-U-21 to TC-U-24 / FR-43."""

    @pytest.mark.parametrize(
        "current,target",
        [
            (BOOKED, CHECKED_IN),
            (BOOKED, CANCELLED),
            (BOOKED, NO_SHOW),
            (CHECKED_IN, IN_PROGRESS),
            (CHECKED_IN, NO_SHOW),
            (IN_PROGRESS, COMPLETED),
        ],
    )
    def test_permitted_transitions(self, current, target):
        assert can_transition(current, target)

    @pytest.mark.parametrize(
        "current,target",
        [
            (BOOKED, IN_PROGRESS),        # must be checked in first
            (BOOKED, COMPLETED),
            (CHECKED_IN, BOOKED),         # no going back
            (CHECKED_IN, CANCELLED),      # cancel after arrival is a no-show
            (COMPLETED, CANCELLED),       # FR-31
            (CANCELLED, CHECKED_IN),
            (CANCELLED, BOOKED),
            (NO_SHOW, CHECKED_IN),
            (COMPLETED, COMPLETED),
            (IN_PROGRESS, CHECKED_IN),
        ],
    )
    def test_forbidden_transitions(self, current, target):
        assert not can_transition(current, target)

    def test_terminal_states_have_no_exits(self):
        for terminal in (COMPLETED, CANCELLED, NO_SHOW):
            assert TRANSITIONS[terminal] == frozenset()

    def test_unknown_status_is_refused_rather_than_crashing(self):
        assert not can_transition("NOT_A_STATUS", COMPLETED)

    def test_every_state_is_reachable_from_booked(self):
        """A state nothing can reach is dead code in the schema."""
        reachable, frontier = {BOOKED}, [BOOKED]
        while frontier:
            for nxt in TRANSITIONS[frontier.pop()]:
                if nxt not in reachable:
                    reachable.add(nxt)
                    frontier.append(nxt)
        assert reachable == set(TRANSITIONS)


class TestPresentationHelpers:
    def test_mask_name_hides_the_surname(self):
        """TC-U-25 / NFR-LEG-03."""
        assert mask_name("Yaw Darko") == "Y. D****"
        assert mask_name("Ama Serwaa Boateng") == "A. B****"

    def test_mask_name_handles_a_single_name(self):
        assert mask_name("Kofi") == "K.****"

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_mask_name_degrades_safely(self, value):
        assert mask_name(value) == "Patient"

    def test_mask_never_returns_the_full_surname(self):
        for name in ["Yaw Darko", "Efua Nyarko", "Kwame Asante"]:
            surname = name.split()[-1]
            assert surname not in mask_name(name)

    def test_ticket_labels_are_per_practitioner(self):
        """TC-U-26. Practitioner 1 issues A-, practitioner 2 issues B-."""
        assert ticket_label(1, 7) == "A-07"
        assert ticket_label(2, 12) == "B-12"
        assert ticket_label(3, 1) == "C-01"

    def test_booking_codes_are_well_formed_and_unambiguous(self):
        """TC-U-03. The alphabet excludes I, O, 0 and 1 because staff read
        these codes aloud at the desk."""
        codes = {new_appointment_code() for _ in range(500)}
        assert len(codes) > 490          # collisions should be vanishingly rare
        for code in codes:
            assert code.startswith("TC-")
            assert len(code) == 9
            assert not set(code[3:]) & set("IO01")
