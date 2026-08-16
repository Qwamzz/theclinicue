"""Unit tests for the validation layer (TC-U-30 to TC-U-36 / FR-53)."""

from __future__ import annotations

import pytest

from app.errors import ValidationError
from app.validators import Validator


def invalid(payload, run):
    v = Validator(payload)
    run(v)
    with pytest.raises(ValidationError) as excinfo:
        v.raise_if_invalid()
    return excinfo.value.fields


class TestStrings:
    def test_whitespace_is_trimmed(self):
        v = Validator({"name": "  Kofi Boateng  "})
        assert v.string("name") == "Kofi Boateng"
        v.raise_if_invalid()

    def test_whitespace_only_counts_as_missing(self):
        """A field of spaces is not a value; treating it as one is how blank
        names reach the database."""
        fields = invalid({"name": "   "}, lambda v: v.string("name"))
        assert "name" in fields

    def test_length_limits_enforced(self):
        assert "name" in invalid({"name": "x"}, lambda v: v.string("name", min_len=2))
        assert "name" in invalid({"name": "x" * 300}, lambda v: v.string("name", max_len=80))

    def test_optional_string_returns_default(self):
        v = Validator({})
        assert v.string("notes", required=False, default="") == ""
        v.raise_if_invalid()

    def test_non_string_rejected(self):
        assert "name" in invalid({"name": 42}, lambda v: v.string("name"))


class TestIntegers:
    def test_numeric_string_is_accepted(self):
        """Query-string parameters always arrive as text."""
        v = Validator({"practitioner_id": "3"})
        assert v.integer("practitioner_id", minimum=1) == 3
        v.raise_if_invalid()

    def test_bounds_enforced(self):
        assert "n" in invalid({"n": 0}, lambda v: v.integer("n", minimum=1))
        assert "n" in invalid({"n": 500}, lambda v: v.integer("n", maximum=100))

    def test_boolean_is_not_an_integer(self):
        """bool subclasses int in Python; accepting True as 1 would let a JSON
        `true` become a record id."""
        assert "n" in invalid({"n": True}, lambda v: v.integer("n"))

    @pytest.mark.parametrize("bad", ["abc", "3.7", "", None, [1]])
    def test_non_numeric_rejected(self, bad):
        assert "n" in invalid({"n": bad}, lambda v: v.integer("n"))


class TestFormats:
    @pytest.mark.parametrize("good", ["a@b.co", "kofi.boateng@example.com", "x+tag@mail.co.uk"])
    def test_valid_emails(self, good):
        v = Validator({"email": good})
        assert v.email() == good.lower()
        v.raise_if_invalid()

    @pytest.mark.parametrize("bad", ["notanemail", "@nope.com", "a@b", "a b@c.com", "a@@b.com"])
    def test_invalid_emails(self, bad):
        assert "email" in invalid({"email": bad}, lambda v: v.email())

    def test_email_is_lowercased(self):
        v = Validator({"email": "Kofi@Example.COM"})
        assert v.email() == "kofi@example.com"

    @pytest.mark.parametrize("good", ["+233241112222", "0241112222", "+233 24 111 2222"])
    def test_valid_phones(self, good):
        v = Validator({"phone": good})
        v.phone()
        v.raise_if_invalid()

    @pytest.mark.parametrize("bad", ["123", "abcdefgh", "++2332411", "24111222233445566778899"])
    def test_invalid_phones(self, bad):
        assert "phone" in invalid({"phone": bad}, lambda v: v.phone())

    def test_date_format(self):
        v = Validator({"date": "2026-08-12"})
        assert v.date("date") == "2026-08-12"
        v.raise_if_invalid()
        assert "date" in invalid({"date": "12/08/2026"}, lambda v: v.date("date"))
        assert "date" in invalid({"date": "2026-02-30"}, lambda v: v.date("date"))

    def test_time_format(self):
        v = Validator({"t": "09:30"})
        assert v.time("t") == "09:30"
        v.raise_if_invalid()
        assert "t" in invalid({"t": "9:30"}, lambda v: v.time("t"))

    def test_choice_restricts_to_allowed_values(self):
        v = Validator({"role": "STAFF"})
        assert v.choice("role", ["PATIENT", "STAFF", "ADMIN"]) == "STAFF"
        v.raise_if_invalid()
        assert "role" in invalid({"role": "ROOT"},
                                 lambda v: v.choice("role", ["PATIENT", "STAFF", "ADMIN"]))


class TestPasswords:
    def test_compliant_password_accepted(self):
        v = Validator({"password": "Passw0rd1"})
        assert v.password() == "Passw0rd1"
        v.raise_if_invalid()

    @pytest.mark.parametrize(
        "bad,reason",
        [("short1", "too short"), ("alllettersnodigit", "no digit"), ("12345678", "no letter")],
    )
    def test_weak_passwords_rejected(self, bad, reason):
        """FR-03."""
        assert "password" in invalid({"password": bad}, lambda v: v.password())

    def test_password_is_not_trimmed(self):
        """Silently stripping spaces would lock the user out at next login,
        because they would type the password they actually chose."""
        v = Validator({"password": " Passw0rd1 "})
        assert v.password() == " Passw0rd1 "

    def test_overlong_password_rejected(self):
        assert "password" in invalid({"password": "a1" * 100}, lambda v: v.password())


class TestErrorCollection:
    def test_all_errors_are_reported_together(self):
        """One round trip must surface every bad field: on a slow connection,
        one-at-a-time validation is a miserable experience."""
        fields = invalid(
            {"email": "nope", "password": "short", "phone": "1"},
            lambda v: (v.email(), v.password(), v.phone()),
        )
        assert set(fields) == {"email", "password", "phone"}

    def test_a_non_object_body_is_reported(self):
        v = Validator(["not", "an", "object"])
        with pytest.raises(ValidationError):
            v.raise_if_invalid()

    def test_valid_payload_raises_nothing(self):
        v = Validator({"email": "a@b.co", "password": "Passw0rd1"})
        v.email()
        v.password()
        v.raise_if_invalid()
