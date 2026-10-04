"""Endpoint de salud del servicio.

Lo consumen el healthcheck de docker-compose.yml (via healthcheck.py) y el health check HTTP de
Render (`healthCheckPath: /health` en render.yaml). Render considera sana una instancia que
responde 2xx en menos de 5 segundos: por eso la conexion a la base tiene un timeout de 3
segundos (ver `SEGUNDOS_TIMEOUT_DE_CONEXION` en configuracion.py).
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.errores import construir_envelope
from app.core.logging import registrar_evento
from app.extensiones import db

blueprint_salud = Blueprint("salud", __name__)


@blueprint_salud.get("/health")
def consultar_salud():
    """Responde 200 si la aplicacion y la base de datos estan operativas."""
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        db.session.rollback()
        registrar_evento(
            logging.ERROR,
            "salud_degradada",
            type(error).__name__,
            componente="base_de_datos",
        )

        cuerpo = {
            "status": "error",
            "db": "error",
            **construir_envelope(
                "SERVICIO_NO_DISPONIBLE",
                "La base de datos no responde en este momento.",
                {"componente": "base_de_datos"},
            ),
        }
        return jsonify(cuerpo), 503

    return jsonify({"status": "ok", "db": "ok"}), 200
