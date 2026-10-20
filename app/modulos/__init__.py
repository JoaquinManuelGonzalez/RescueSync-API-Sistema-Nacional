"""Registro de los modulos de dominio de la API.

Cada modulo de dominio (habilitaciones, reservas, compromisos...) expone su blueprint en
`rutas.py` y sus modelos en `modelos.py`. Este archivo es el unico lugar donde se los enchufa a
la aplicacion y a Alembic.
"""

from __future__ import annotations

from flask import Flask

from app.core.openapi import Api
from app.modulos.autenticacion.comandos import grupo_cuentas
from app.modulos.autenticacion.rutas import blueprint_autenticacion
from app.modulos.compromisos.rutas import blueprint_compromisos
from app.modulos.evaluacion.rutas import blueprint_evaluacion as blueprint_evaluacion
from app.modulos.organizaciones.rutas import blueprint_organizaciones
from app.modulos.organizaciones.rutas_padron import blueprint_padron


def registrar_modulos(app: Flask, api: Api) -> None:  # noqa: ARG001
    """Registra el blueprint de cada modulo de dominio.

    Los blueprints son los de `app.core.acceso` (flask-smorest con autorizacion por rol) y se
    registran con `api.register_blueprint`, NO con `app.register_blueprint`: asi aparecen en
    la documentacion OpenAPI. La api se crea en create_app y llega como parametro. Ejemplo:

        from app.modulos.compromisos.rutas import blueprint_compromisos

        api.register_blueprint(blueprint_compromisos)
    """

    api.register_blueprint(blueprint_autenticacion)
    api.register_blueprint(blueprint_padron)
    api.register_blueprint(blueprint_organizaciones)
    api.register_blueprint(blueprint_compromisos)
    api.register_blueprint(blueprint_evaluacion)


def registrar_comandos(app: Flask) -> None:
    """Registra los comandos de consola de los modulos (`flask <grupo> <comando>`)."""
    app.cli.add_command(grupo_cuentas)


def importar_modelos() -> None:
    """Importa los modelos de todos los modulos para que Alembic los vea.

    Alembic solo detecta en `flask db migrate` los modelos que fueron importados: un modelo que
    nadie importa genera una migracion vacia sin avisar. Cada modulo nuevo con `modelos.py`
    agrega aca su import, por ejemplo:
        import app.modulos.compromisos.modelos  # noqa: F401
        import app.modulos.compromisos.modelos  # noqa: F401
    """
    import app.modulos.autenticacion.modelos  # noqa: F401
    import app.modulos.compromisos.modelos  # noqa: F401
    import app.modulos.organizaciones.modelos  # noqa: F401
