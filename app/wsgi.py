"""Punto de entrada WSGI.

Es lo que apuntan FLASK_APP y gunicorn (`app.wsgi:app`).
"""

from __future__ import annotations

from app import create_app

app = create_app()
