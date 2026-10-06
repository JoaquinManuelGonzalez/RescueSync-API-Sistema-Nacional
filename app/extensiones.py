"""Extensiones de Flask, instanciadas sin aplicacion.

Viven aca y no en la app factory para que cualquier modulo pueda importarlas sin caer en
importaciones circulares. La aplicacion las inicializa con `init_app()` en `app/__init__.py`.
"""

from __future__ import annotations

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Convencion de nombres de indices y restricciones de CONTRIBUTING.md seccion 2.
# Declararla aca hace que Alembic genere los nombres correctos solo, sin que cada quien
# tenga que acordarse del prefijo al escribir un modelo.
CONVENCION_DE_NOMBRES = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Clase base de todos los modelos del proyecto."""

    metadata = MetaData(naming_convention=CONVENCION_DE_NOMBRES)


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
