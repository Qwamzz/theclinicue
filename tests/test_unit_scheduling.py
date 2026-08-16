"""Unit tests for the slot-generation algorithm (TC-U-08 to TC-U-20).

`generate_slots` is a pure function, so these tests exercise it directly with
no database and no application context. SRS §8.4 identified this as the
highest-risk component; these are the tests that were written first.
"""

from __future__ import annotations

import pytest

from app.domain import to_hhmm, to_minutes
from app.services.scheduling import generate_slots, overlaps


def M(hhmm: str) -> int:
    return to_minutes(hhmm)


def window(start: str, end: str) -> tuple[int, int]:
    return (M(start), M(end))


def as_times(minutes: list[int]) -> list[str]:
    return [to_hhmm(m) for m in minutes]


# --------------------------------------------------------------- overlaps

class TestOverlaps:
    def test_adjacent_intervals_do_not_overlap(self):
        """TC-U-08. Half-open intervals: 09:00-09:30 and 09:30-10:00 are
        neighbours, not a clash. Getting this wrong halves clinic capacity."""
        assert not overlaps(window("09:00", "09:30"), window("09:30", "10:00"))

    def test_partial_overlap_detected(self):
        assert overlaps(window("09:00", "09:30"), window("09:15", "09:45"))

    def test_containment_detected_both_ways(self):
        assert overlaps(window("09:00", "10:00"), window("09:15", "09:30"))
        assert overlaps(window("09:15", "09:30"), window("09:00", "10:00"))

    def test_identical_intervals_overlap(self):
        assert overlaps(window("09:00", "09:30"), window("09:00", "09:30"))

    def test_disjoint_intervals_do_not_overlap(self):
        assert not overlaps(window("08:00", "09:00"), window("14:00", "15:00"))


# -------------------------------------------------------- basic generation

class TestGeneration:
    def test_simple_tiling(self):
        """TC-U-09. A four-hour window at 30 minutes yields eight slots."""
        slots = generate_slots([window("08:00", "12:00")], [], 30)
        assert as_times(slots) == [
            "08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
        ]

    def test_slot_must_fit_entirely_inside_the_window(self):
        """TC-U-10. 08:00-09:50 with a 45-minute service gives 08:00 and 08:45;
        09:30 would run to 10:15 and overrun the clinician's availability."""
        slots = generate_slots([window("08:00", "09:50")], [], 45)
        assert as_times(slots) == ["08:00", "08:45"]

    def test_window_shorter_than_the_service_yields_nothing(self):
        assert generate_slots([window("08:00", "08:20")], [], 30) == []

    def test_multiple_windows_are_combined_and_sorted(self):
        """TC-U-11. Morning and afternoon windows produce one ordered list."""
        slots = generate_slots(
            [window("13:00", "14:00"), window("08:00", "09:00")], [], 30
        )
        assert as_times(slots) == ["08:00", "08:30", "13:00", "13:30"]

    def test_no_windows_yields_nothing(self):
        assert generate_slots([], [], 30) == []

    def test_inverted_window_is_ignored_rather_than_looping(self):
        """Defensive: FR-18 forbids this at the database, but the algorithm
        must not spin if a bad row ever reaches it."""
        assert generate_slots([window("12:00", "08:00")], [], 30) == []

    def test_zero_duration_is_rejected(self):
        with pytest.raises(ValueError):
            generate_slots([window("08:00", "12:00")], [], 0)

    def test_overlapping_windows_do_not_duplicate_slots(self):
        """Two availability rules that overlap must not offer the same time
        twice - the result is a set of start times, not a concatenation."""
        slots = generate_slots(
            [window("08:00", "10:00"), window("09:00", "11:00")], [], 60
        )
        assert as_times(slots) == ["08:00", "09:00", "10:00"]


# ------------------------------------------------------- conflict removal

class TestConflictExclusion:
    def test_exact_match_is_excluded(self):
        """TC-U-12 / FR-21."""
        slots = generate_slots([window("08:00", "10:00")], [window("09:00", "09:30")], 30)
        assert "09:00" not in as_times(slots)
        assert as_times(slots) == ["08:00", "08:30", "09:30"]

    def test_partial_overlap_excludes_the_slot(self):
        """TC-U-13. A 20-minute booking straddling 09:00 must remove the whole
        09:00 slot - offering it would produce a real double-booking."""
        slots = generate_slots([window("08:00", "10:00")], [window("08:50", "09:10")], 30)
        assert as_times(slots) == ["08:00", "09:30"]

    def test_a_long_booking_can_clear_several_slots(self):
        slots = generate_slots([window("08:00", "12:00")], [window("09:00", "11:00")], 30)
        assert as_times(slots) == ["08:00", "08:30", "11:00", "11:30"]

    def test_adjacent_booking_does_not_block(self):
        """TC-U-14. The regression guard for the half-open interval rule."""
        slots = generate_slots([window("08:00", "09:30")], [window("08:00", "08:30")], 30)
        assert as_times(slots) == ["08:30", "09:00"]

    def test_booking_outside_the_window_is_irrelevant(self):
        slots = generate_slots([window("08:00", "09:00")], [window("15:00", "15:30")], 30)
        assert as_times(slots) == ["08:00", "08:30"]

    def test_fully_booked_window_yields_nothing(self):
        slots = generate_slots(
            [window("08:00", "09:00")],
            [window("08:00", "08:30"), window("08:30", "09:00")],
            30,
        )
        assert slots == []


# ------------------------------------------------------------- min_start

class TestElapsedSlots:
    def test_slots_before_min_start_are_dropped(self):
        """TC-U-15 / FR-22. At 09:45 today, 08:00 and 09:00 are gone."""
        slots = generate_slots([window("08:00", "12:00")], [], 60, min_start=M("09:45"))
        assert as_times(slots) == ["10:00", "11:00"]

    def test_min_start_is_inclusive(self):
        """A slot starting exactly now is still offerable."""
        slots = generate_slots([window("08:00", "10:00")], [], 60, min_start=M("09:00"))
        assert as_times(slots) == ["09:00"]

    def test_min_start_after_the_window_clears_everything(self):
        assert generate_slots([window("08:00", "12:00")], [], 30, min_start=M("18:00")) == []

    def test_min_start_none_keeps_all_slots(self):
        slots = generate_slots([window("08:00", "09:00")], [], 30, min_start=None)
        assert len(slots) == 2


# ----------------------------------------------------------- durations

class TestDurations:
    @pytest.mark.parametrize(
        "duration,expected",
        [
            (15, 16),   # 08:00-12:00 at 15 min
            (20, 12),
            (30, 8),
            (45, 5),    # 11:45 would end at 12:30, so it is not offered
            (60, 4),
            (240, 1),
        ],
    )
    def test_slot_count_by_service_duration(self, duration, expected):
        """TC-U-16. The service's duration is what sets the slot width, so the
        same window yields different grids for different services."""
        slots = generate_slots([window("08:00", "12:00")], [], duration)
        assert len(slots) == expected

    def test_different_durations_produce_different_grids(self):
        """A 45-minute service does not land on the 30-minute grid; this is why
        conflict checking must compare intervals rather than start times."""
        thirty = set(as_times(generate_slots([window("08:00", "12:00")], [], 30)))
        forty_five = set(as_times(generate_slots([window("08:00", "12:00")], [], 45)))
        # 09:30 and 11:00 fall on both grids; 08:45 and 10:15 exist only on the
        # 45-minute one.
        assert forty_five - thirty == {"08:45", "10:15"}
        assert forty_five & thirty == {"08:00", "09:30", "11:00"}

    def test_a_booked_45_minute_appointment_blocks_two_30_minute_slots(self):
        """TC-U-17. The cross-duration case that a start-time-equality check
        would silently get wrong."""
        slots = generate_slots([window("08:00", "10:00")], [window("08:45", "09:30")], 30)
        assert as_times(slots) == ["08:00", "09:30"]
