"""WSGI entry point.

Production:   gunicorn --bind 0.0.0.0:$PORT wsgi:app
Development:  python wsgi.py
"""

from __future__ import annotations

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    debug = os.environ.get("CQ_ENV", "development") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
