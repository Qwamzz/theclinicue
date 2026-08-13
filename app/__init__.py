"""Application factory.

Building the app in a function rather than at import time is what lets the
test suite create an isolated instance per test with its own database
(NFR-MNT-01, NFR-MNT-02).
"""

from __future__ import annotations

import itertools
import logging
import os
import sqlite3
import sys
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from .config import Config, load_config
from .db import _connect, close_db, get_db, init_schema, is_memory, memory_uri
from .errors import ApiError, InternalError, NotFound, ServiceBusy
from .security import security_headers, verify_csrf

__version__ = "1.0.0"

_memory_counter = itertools.count(1)


def create_app(config: Config | None = None, **overrides: Any) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    settings = config or load_config(**overrides)

    # An in-memory database must be shared between the per-request connections,
    # and must be kept alive by at least one open handle for as long as the app
    # exists. Each app instance gets its own database so parallel tests do not
    # collide.
    if settings.database_path == ":memory:":
        settings = Config(**{**settings.__dict__,
                             "database_path": memory_uri(str(next(_memory_counter)))})

    app.config["TC"] = settings
    app.config["TC_VERSION"] = __version__
    app.config["SECRET_KEY"] = settings.secret_key
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024      # no endpoint needs a large body

    _configure_logging(app)
    _register_lifecycle(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_client_routes(app)

    if is_memory(settings.database_path):
        # Holding this handle open is what stops the shared in-memory database
        # being destroyed between requests.
        app.extensions["tc_keepalive"] = _connect(settings.database_path)

    with app.app_context():
        init_schema(get_db())
        get_db().commit()
        close_db()

    return app


# ---------------------------------------------------------------------------

def _configure_logging(app: Flask) -> None:
    """Log to stdout: containers collect stdout, and a log file on an ephemeral
    filesystem would be lost on every restart."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    level = logging.WARNING if app.config["TC"].is_testing else logging.INFO
    app.logger.handlers = [handler]
    app.logger.setLevel(level)


def _register_lifecycle(app: Flask) -> None:
    app.teardown_appcontext(close_db)

    @app.before_request
    def _csrf_gate():
        """CSRF is enforced centrally, not per route, so a new endpoint cannot
        forget it (FR-07)."""
        if request.path.startswith("/api/"):
            verify_csrf()
        return None

    @app.after_request
    def _headers(response):
        return security_headers(response)


def _register_blueprints(app: Flask) -> None:
    from .api import admin, appointments, auth, catalog, health
    from .api import queue as queue_api

    for module in (health, auth, catalog, appointments, queue_api, admin):
        app.register_blueprint(module.bp)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(exc: ApiError):
        return jsonify(exc.to_dict()), exc.status

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        """Translate Werkzeug's own errors into the single envelope (FR-54)."""
        if not request.path.startswith("/api/"):
            return exc
        code = {
            400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN",
            404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 413: "PAYLOAD_TOO_LARGE",
            429: "RATE_LIMITED",
        }.get(exc.code or 500, "HTTP_ERROR")
        return jsonify({"error": code, "message": exc.description}), exc.code or 500

    @app.errorhandler(sqlite3.OperationalError)
    def _db_busy(exc: sqlite3.OperationalError):
        """Write-lock contention is transient, so report it as such (503) and
        let the client retry, rather than as a fault (500)."""
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            app.logger.warning("Datastore contention on %s %s: %s",
                               request.method, request.path, exc)
            error = ServiceBusy()
            response = jsonify(error.to_dict())
            response.headers["Retry-After"] = "1"
            return response, error.status
        return _unexpected(exc)

    @app.errorhandler(Exception)
    def _unexpected(exc: Exception):
        """FR-55 and NFR-REL-01: the detail is logged, never returned, and the
        worker stays alive."""
        app.logger.exception("Unhandled exception on %s %s", request.method, request.path)
        if not request.path.startswith("/api/"):
            raise exc
        error = InternalError()
        return jsonify(error.to_dict()), error.status


def _register_client_routes(app: Flask) -> None:
    """Serve the single-page client.

    Any non-API path falls through to index.html so that a deep link such as
    /staff works on a hard refresh, without needing a rewrite rule in front of
    the process.
    """
    static_dir = os.path.join(app.root_path, "static")

    @app.get("/")
    def index():
        return send_from_directory(static_dir, "index.html")

    @app.get("/<path:filename>")
    def client(filename: str):
        if filename.startswith("api/"):
            raise NotFound()
        candidate = os.path.join(static_dir, filename)
        if os.path.isfile(candidate):
            return send_from_directory(static_dir, filename)
        return send_from_directory(static_dir, "index.html")
