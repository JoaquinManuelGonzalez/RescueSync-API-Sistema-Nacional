"""Fixtures compartidas de los tests.

Los tests corren contra SQLite en memoria: no necesitan el contenedor de PostgreSQL. Lo que
depende de PostgreSQL de verdad (migraciones, conexion real) lo verifica el job `imagen` del CI
levantando el docker-compose completo.
"""

from __future__ import annotations

import pytest

from app import create_app

ENTORNO_MINIMO = {
    "SECRET_KEY": "clave-de-prueba",
    "DATABASE_URL": "sqlite://",
}


@pytest.fixture
def entorno_completo(monkeypatch):
    """Deja seteadas todas las variables obligatorias y limpia las opcionales."""
    for nombre, valor in ENTORNO_MINIMO.items():
        monkeypatch.setenv(nombre, valor)
    for nombre in ("APP_ENV", "PORT", "LOG_LEVEL", "DATABASE_SSLMODE"):
        monkeypatch.delenv(nombre, raising=False)
    return monkeypatch


@pytest.fixture
def app(entorno_completo):
    aplicacion = create_app({"TESTING": True})
    yield aplicacion


@pytest.fixture
def cliente(app):
    return app.test_client()
