"""Fixtures compartidas de los tests.

Los tests corren contra SQLite en memoria: no necesitan el contenedor de PostgreSQL. Lo que
depende de PostgreSQL de verdad (migraciones, conexion real) lo verifica el job `imagen` del CI
levantando el docker-compose completo.
"""

from __future__ import annotations

import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy import select

from app import create_app
from app.core.acceso import Rol
from app.extensiones import db
from app.modulos.autenticacion.modelos import Cuenta
from app.modulos.autenticacion.servicios import guardar_cuenta

ENTORNO_MINIMO = {
    "SECRET_KEY": "clave-de-prueba",
    "DATABASE_URL": "sqlite://",
    "JWT_SECRET_KEY": "clave-jwt-de-prueba-de-al-menos-32-caracteres",
}

CONTRASENA_DE_PRUEBA = "contrasena-de-prueba-123"
USUARIO_POR_ROL = {Rol.administrador: "admin-sn", Rol.sistema: "bonita-rescuesync"}


@pytest.fixture
def entorno_completo(monkeypatch):
    """Deja seteadas todas las variables obligatorias y limpia las opcionales."""
    for nombre, valor in ENTORNO_MINIMO.items():
        monkeypatch.setenv(nombre, valor)
    for nombre in ("APP_ENV", "PORT", "LOG_LEVEL", "DATABASE_SSLMODE", "JWT_EXPIRACION_MINUTOS"):
        monkeypatch.delenv(nombre, raising=False)
    return monkeypatch


@pytest.fixture
def app(entorno_completo):
    aplicacion = create_app({"TESTING": True})
    yield aplicacion


@pytest.fixture
def cliente(app):
    return app.test_client()


@pytest.fixture
def base_de_datos(app):
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


@pytest.fixture
def crear_cuenta(base_de_datos):
    """Crea (o actualiza) una cuenta y la devuelve."""

    def _crear(
        usuario: str = "admin-sn",
        rol: Rol = Rol.administrador,
        contrasena: str = CONTRASENA_DE_PRUEBA,
        activa: bool = True,
    ) -> Cuenta:
        cuenta, _ = guardar_cuenta(usuario, contrasena, rol)
        cuenta.activa = activa
        db.session.commit()
        return cuenta

    return _crear


@pytest.fixture
def cabeceras(crear_cuenta):
    """Cabeceras con un token valido del rol pedido; crea la cuenta del rol si hace falta."""

    def _cabeceras(
        rol: Rol = Rol.administrador, extra: dict[str, str] | None = None
    ) -> dict[str, str]:
        usuario = USUARIO_POR_ROL[rol]
        if db.session.scalar(select(Cuenta).where(Cuenta.usuario == usuario)) is None:
            crear_cuenta(usuario, rol)
        token = create_access_token(identity=usuario, additional_claims={"rol": rol.value})
        return {"Authorization": f"Bearer {token}", **(extra or {})}

    return _cabeceras
