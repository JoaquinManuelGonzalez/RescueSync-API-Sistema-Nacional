"""App factory de la API del Sistema Nacional.

El orden de esta funcion es parte del contrato de configuracion: la validacion fail-fast
corre una unica vez, antes de registrar los modulos de dominio, para que el proceso muera sin
llegar a levantar el servidor HTTP si falta una variable obligatoria.
"""

from __future__ import annotations

from typing import Any

import click
from flask import Flask
from flask_smorest import Api
from werkzeug.middleware.proxy_fix import ProxyFix

from app.core.configuracion import construir_configuracion, validar_o_terminar
from app.core.errores import registrar_manejadores
from app.core.logging import configurar_logging, registrar_middleware
from app.core.salud import blueprint_salud
from app.extensiones import db, migrate
from app.modulos import registrar_modulos

ENTORNO_PRODUCCION = "produccion"


def create_app(overrides: dict[str, Any] | None = None) -> Flask:
    """Construye la aplicacion. `overrides` es solo para los tests."""
    validar_o_terminar()

    configuracion = construir_configuracion()
    configurar_logging(str(configuracion["LOG_LEVEL"]))

    app = Flask(__name__)
    app.config.update(configuracion)
    if overrides:
        app.config.update(overrides)

    if app.config["APP_ENV"] == ENTORNO_PRODUCCION:
        # Render termina el TLS en su balanceador y reenvia la solicitud por HTTP. ProxyFix
        # toma el esquema y la IP real de las cabeceras X-Forwarded-* que agrega ese unico
        # proxy, para que request.scheme sea "https" y los logs muestren la IP del cliente.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Configuración de la API
    app.config.update(
        API_TITLE="Sistema Nacional de Gestión de Recursos y Riesgos",
        API_VERSION="v0.1.0",
        OPENAPI_VERSION="3.1.0",
        OPENAPI_URL_PREFIX="/",
        OPENAPI_SWAGGER_UI_PATH="/docs",
        OPENAPI_SWAGGER_UI_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist/",
    )

    # Crea la API
    api = Api(app)

    # Hace aparecer un botón "Authorize" en Swagger UI
    # Falta implementar
    api.spec.components.security_scheme(
        "bearerAuth",
        {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
    )

    db.init_app(app)
    migrate.init_app(app, db)

    registrar_middleware(app)
    registrar_manejadores(app)

    app.register_blueprint(blueprint_salud)

    # Los modulos de dominio se registran al final, ya con la configuracion validada.
    registrar_modulos(app, api)
    _registrar_comando_seed(app)

    return app


def _registrar_comando_seed(app: Flask) -> None:
    """Registra `flask seed`, que ejecuta todos los seeders en una transacción."""

    @app.cli.command("seed")
    def seed() -> None:
        from app.core.semillas import SEEDERS, importar_seeders

        importar_seeders()
        try:
            with db.session.begin():
                for seeder in SEEDERS:
                    for resultado in seeder.funcion():
                        click.echo(
                            f"{seeder.nombre}/{resultado.entidad}: "
                            f"{resultado.creados} creados, "
                            f"{resultado.existentes} existentes"
                        )
        except Exception:
            db.session.rollback()
            raise
