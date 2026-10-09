"""Registro de los modulos de dominio de la API.

Cada modulo de dominio (habilitaciones, reservas, compromisos...) expone su blueprint en
`rutas.py` y sus modelos en `modelos.py`. Este archivo es el unico lugar donde se los enchufa a
la aplicacion y a Alembic. Por ahora no hay ninguno: los agregan las epicas siguientes.
"""

from __future__ import annotations

from flask import Flask

from flask_smorest import Api


def registrar_modulos(app: Flask, api:Api) -> None:  # noqa: ARG001
    """Registra el blueprint de cada modulo de dominio.

    Ejemplo, cuando exista el modulo de compromisos:

        from app.modulos.compromisos.rutas import blueprint_compromisos

        app.register_blueprint(blueprint_compromisos)
    """


def importar_modelos() -> None:
    """Importa los modelos de todos los modulos para que Alembic los vea.

    Alembic solo detecta en `flask db migrate` los modelos que fueron importados: un modelo que
    nadie importa genera una migracion vacia sin avisar. Cada modulo nuevo con `modelos.py`
    agrega aca su import, por ejemplo:

        import app.modulos.compromisos.modelos  # noqa: F401
    """
