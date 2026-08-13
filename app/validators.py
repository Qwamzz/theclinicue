"""Declarative request validation (FR-53).

Every field crossing the API boundary is checked for presence, type, length,
format and permitted range *before* it reaches business logic. Failures are
collected rather than raised one at a time, so the client can highlight every
bad field in a single round trip — which matters on the slow connections this
system targets.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .domain import is_date, is_time
from .errors import ValidationError

# Deliberately permissive: the goal is to catch typos and obvious rubbish, not
# to adjudicate RFC 5322. Over-strict email regexes reject valid addresses.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-()]{6,19}$")


class Validator:
    """Collects field errors, then raises them together."""

    def __init__(self, payload: Mapping[str, Any] | None) -> None:
        self.raw: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}
        self.errors: dict[str, str] = {}
        if payload is not None and not isinstance(payload, Mapping):
            self.errors["_body"] = "Expected a JSON object."

    # -- primitives --------------------------------------------------------

    def _present(self, field: str, required: bool) -> Any:
        value = self.raw.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                self.errors[field] = "This is required."
            return None
        return value

    def string(
        self,
        field: str,
        *,
        required: bool = True,
        min_len: int = 1,
        max_len: int = 255,
        default: str = "",
    ) -> str:
        value = self._present(field, required)
        if value is None:
            return default
        if not isinstance(value, str):
            self.errors[field] = "Must be text."
            return default
        cleaned = value.strip()
        if len(cleaned) < min_len:
            self.errors[field] = f"Must be at least {min_len} characters."
        elif len(cleaned) > max_len:
            self.errors[field] = f"Must be {max_len} characters or fewer."
        return cleaned

    def integer(
        self,
        field: str,
        *,
        required: bool = True,
        minimum: int | None = None,
        maximum: int | None = None,
        default: int | None = None,
    ) -> int | None:
        value = self._present(field, required)
        if value is None:
            return default
        if isinstance(value, bool):          # bool is a subclass of int; reject it
            self.errors[field] = "Must be a whole number."
            return default
        try:
            number = int(value)
        except (TypeError, ValueError):
            self.errors[field] = "Must be a whole number."
            return default
        if minimum is not None and number < minimum:
            self.errors[field] = f"Must be {minimum} or more."
        elif maximum is not None and number > maximum:
            self.errors[field] = f"Must be {maximum} or less."
        return number

    def boolean(self, field: str, *, required: bool = True, default: bool | None = None) -> bool | None:
        value = self.raw.get(field)
        if value is None:
            if required:
                self.errors[field] = "This is required."
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.strip().lower() in {"true", "false", "1", "0"}:
            return value.strip().lower() in {"true", "1"}
        self.errors[field] = "Must be true or false."
        return default

    # -- formats -----------------------------------------------------------

    def email(self, field: str = "email", *, required: bool = True) -> str:
        value = self.string(field, required=required, min_len=3, max_len=254)
        if value and not _EMAIL_RE.match(value):
            self.errors[field] = "Enter a valid email address."
        return value.lower()

    def phone(self, field: str = "phone", *, required: bool = True) -> str:
        value = self.string(field, required=required, min_len=7, max_len=20)
        if value and not _PHONE_RE.match(value):
            self.errors[field] = "Enter a valid phone number."
        return value

    def password(self, field: str = "password", *, min_length: int = 8) -> str:
        value = self.raw.get(field)
        if not isinstance(value, str) or not value:
            self.errors[field] = "This is required."
            return ""
        # Not stripped: leading and trailing spaces are legitimate password
        # characters and silently removing them would lock users out later.
        if len(value) < min_length:
            self.errors[field] = f"Use at least {min_length} characters."
        elif len(value) > 128:
            self.errors[field] = "Use 128 characters or fewer."
        elif not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
            self.errors[field] = "Include at least one letter and one number."
        return value

    def date(self, field: str, *, required: bool = True, default: str = "") -> str:
        value = self.string(field, required=required, min_len=10, max_len=10, default=default)
        if value and not is_date(value):
            self.errors[field] = "Use the date format YYYY-MM-DD."
        return value

    def time(self, field: str, *, required: bool = True, default: str = "") -> str:
        value = self.string(field, required=required, min_len=5, max_len=5, default=default)
        if value and not is_time(value):
            self.errors[field] = "Use the 24-hour time format HH:MM."
        return value

    def choice(self, field: str, options: Iterable[str], *, required: bool = True, default: str = "") -> str:
        allowed = tuple(options)
        value = self.string(field, required=required, default=default)
        if value and value not in allowed:
            self.errors[field] = f"Choose one of: {', '.join(allowed)}."
            return default
        return value or default

    # -- termination -------------------------------------------------------

    def add_error(self, field: str, message: str) -> None:
        self.errors.setdefault(field, message)

    def raise_if_invalid(self) -> None:
        if self.errors:
            raise ValidationError(fields=self.errors)
