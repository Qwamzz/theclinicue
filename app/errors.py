"""The single error vocabulary of the application.

Every failure the API can express is an ApiError subclass. Handlers convert
them to one JSON envelope (FR-54). Nothing internal - stack traces, SQL
fragments, file paths - ever reaches a response body (FR-55).
"""

from __future__ import annotations

from typing import Any, Mapping


class ApiError(Exception):
    """Base class for every expected, reportable failure."""

    status = 400
    code = "BAD_REQUEST"
    default_message = "The request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        fields: Mapping[str, str] | None = None,
        code: str | None = None,
        status: int | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.fields = dict(fields) if fields else None
        if code is not None:
            self.code = code
        if status is not None:
            self.status = status
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error": self.code, "message": self.message}
        if self.fields:
            payload["fields"] = self.fields
        return payload


class ValidationError(ApiError):
    status = 400
    code = "VALIDATION_ERROR"
    default_message = "Please check the highlighted fields and try again."


class Unauthenticated(ApiError):
    status = 401
    code = "UNAUTHENTICATED"
    default_message = "Please sign in to continue."


class Forbidden(ApiError):
    status = 403
    code = "FORBIDDEN"
    default_message = "You do not have permission to do that."


class CsrfInvalid(ApiError):
    status = 403
    code = "CSRF_INVALID"
    default_message = "Your session token did not match. Please refresh and try again."


class NotFound(ApiError):
    """Also returned when a resource exists but does not belong to the caller.

    Returning 404 rather than 403 for another patient's appointment is
    deliberate: a 403 would confirm the id exists and turn the endpoint into an
    enumeration oracle (FR-30).
    """

    status = 404
    code = "NOT_FOUND"
    default_message = "We could not find that."


class Conflict(ApiError):
    status = 409
    code = "CONFLICT"
    default_message = "That action conflicts with the current state."


class SlotUnavailable(Conflict):
    code = "SLOT_TAKEN"
    default_message = "That time was just booked. Please choose another slot."


class InvalidTransition(Conflict):
    code = "INVALID_TRANSITION"
    default_message = "That change is not allowed from the current status."


class DuplicateBooking(Conflict):
    code = "DUPLICATE_BOOKING"
    default_message = "You already have an appointment with this practitioner on that day."


class AlreadyCheckedIn(Conflict):
    code = "ALREADY_CHECKED_IN"
    default_message = "This patient has already been checked in."


class RateLimited(ApiError):
    status = 429
    code = "RATE_LIMITED"
    default_message = "Too many attempts. Please wait a few minutes and try again."


class ServiceBusy(ApiError):
    """The datastore refused a write because another writer holds the lock.

    SQLite serialises writers. Under contention that is a transient condition,
    not a fault: the honest answer is 503 with a retry hint rather than a 500
    that suggests the request was malformed. Removing this condition entirely
    is the point of TD-01 (migrating to PostgreSQL).
    """

    status = 503
    code = "SERVICE_BUSY"
    default_message = "The system is busy right now. Please try again in a moment."


class InternalError(ApiError):
    status = 500
    code = "INTERNAL_ERROR"
    default_message = "Something went wrong on our side. Please try again."
