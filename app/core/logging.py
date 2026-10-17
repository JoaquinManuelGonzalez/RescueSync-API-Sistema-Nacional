"""Logging estructurado de la API del Sistema Nacional.

Implementa docs/contratos/logging.md: una linea JSON por evento hacia stdout, sin archivos de
log dentro del contenedor. Es el mismo formato que usa la aplicacion web de RescueSync, para
que los logs de los componentes se puedan leer y cruzar con las mismas herramientas.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from flask import Flask, Response, g, has_request_context, request

NOMBRE_LOGGER = "sistema_nacional"

# El contrato nombra el nivel "WARN"; Python lo llama "WARNING".
NIVELES_CONTRATO: dict[int, str] = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARN",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "ERROR",
}
NIVELES_ACEPTADOS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

VALOR_REDACTADO = "***"

# Seccion 3 del contrato: que nunca se registra.
CABECERAS_SENSIBLES = frozenset({"authorization", "cookie", "set-cookie"})
CAMPOS_SENSIBLES = frozenset(
    {
        "password",
        "contrasena",
        "clave",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "client_secret",
        "dni",
        "cuit",
        "nombre",
        "apellido",
        "email",
        "correo",
        "telefono",
        "direccion",
    }
)

# El healthcheck del contenedor y el de Render golpean /health cada pocos segundos; loguearlo
# ahogaria la salida.
RUTAS_SIN_LOG = frozenset({"/health"})

CABECERA_CORRELACION = "X-Correlation-Id"


def marca_de_tiempo() -> str:
    """Devuelve el instante actual en ISO-8601 UTC con milisegundos, como pide el contrato."""
    ahora = datetime.now(UTC)
    return f"{ahora:%Y-%m-%dT%H:%M:%S}.{ahora.microsecond // 1000:03d}Z"


class FormateadorJsonLines(logging.Formatter):
    """Serializa cada registro como un unico objeto JSON en una sola linea."""

    def format(self, record: logging.LogRecord) -> str:
        evento: dict[str, Any] = {
            "timestamp": marca_de_tiempo(),
            "nivel": NIVELES_CONTRATO.get(record.levelno, record.levelname),
            "evento": getattr(record, "evento", "mensaje"),
        }

        mensaje = record.getMessage()
        if mensaje:
            evento["mensaje"] = mensaje

        campos = getattr(record, "campos", None)
        if campos:
            evento.update(campos)

        if record.exc_info:
            # El texto de la excepcion trae saltos de linea y romperia el formato JSON Lines.
            evento["excepcion"] = self.formatException(record.exc_info).replace("\n", " | ")

        return json.dumps(evento, ensure_ascii=False, default=str)


def redactar(valor: Any) -> Any:
    """Reemplaza por "***" todo campo sensible, incluso anidado dentro de listas o diccionarios."""
    if isinstance(valor, Mapping):
        return {
            clave: (
                VALOR_REDACTADO if str(clave).lower() in CAMPOS_SENSIBLES else redactar(contenido)
            )
            for clave, contenido in valor.items()
        }
    if isinstance(valor, list | tuple):
        return [redactar(elemento) for elemento in valor]
    return valor


def redactar_cabeceras(cabeceras: Mapping[str, str]) -> dict[str, str]:
    """Reemplaza enteras las cabeceras sensibles, sin dejar ni un prefijo del valor."""
    return {
        nombre: (VALOR_REDACTADO if nombre.lower() in CABECERAS_SENSIBLES else valor)
        for nombre, valor in cabeceras.items()
    }


def obtener_logger() -> logging.Logger:
    return logging.getLogger(NOMBRE_LOGGER)


def configurar_logging(nivel: str = "INFO") -> logging.Logger:
    """Deja stdout como unico destino, con el formateador JSON Lines.

    Se puede llamar antes de que exista la aplicacion: la validacion fail-fast de la
    configuracion necesita loguear aunque la app todavia no se haya construido.
    """
    numero = NIVELES_ACEPTADOS.get(str(nivel).upper(), logging.INFO)

    manejador = logging.StreamHandler(sys.stdout)
    manejador.setFormatter(FormateadorJsonLines())

    raiz = logging.getLogger()
    for existente in list(raiz.handlers):
        raiz.removeHandler(existente)
    raiz.addHandler(manejador)
    raiz.setLevel(numero)

    # El log de acceso de Werkzeug duplicaria "solicitud_completada" en texto plano.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    return obtener_logger()


def id_correlacion_actual() -> str:
    """Identificador de la solicitud en curso. Fuera de una solicitud, genera uno nuevo."""
    if has_request_context():
        existente = g.get("id_correlacion")
        if existente:
            return str(existente)
    return str(uuid.uuid4())


def registrar_evento(nivel: int, evento: str, mensaje: str = "", **campos: Any) -> None:
    """Emite un evento del contrato. Los campos van tal cual al objeto JSON."""
    obtener_logger().log(nivel, mensaje, extra={"evento": evento, "campos": campos})


def _nivel_por_estado(codigo_estado: int) -> int:
    if codigo_estado >= 500:
        return logging.ERROR
    if codigo_estado >= 400:
        return logging.WARNING
    return logging.INFO


def registrar_middleware(app: Flask) -> None:
    """Engancha la correlacion y los eventos de ciclo de vida de cada solicitud.

    El id de correlacion lo puede mandar Bonita en `X-Correlation-Id`; si no viene, se genera
    uno. En los dos casos se devuelve en la respuesta y aparece en todos los logs y errores.
    """

    @app.before_request
    def _abrir_solicitud() -> None:
        g.id_correlacion = request.headers.get(CABECERA_CORRELACION) or str(uuid.uuid4())
        g.inicio_monotonico = time.perf_counter()

        if request.path in RUTAS_SIN_LOG:
            return

        registrar_evento(
            logging.INFO,
            "solicitud_entrante",
            metodo=request.method,
            endpoint=request.path,
            id_correlacion=g.id_correlacion,
        )

    @app.after_request
    def _cerrar_solicitud(respuesta: Response) -> Response:
        respuesta.headers[CABECERA_CORRELACION] = id_correlacion_actual()

        if request.path in RUTAS_SIN_LOG:
            return respuesta

        inicio = g.get("inicio_monotonico")
        duracion_ms = int((time.perf_counter() - inicio) * 1000) if inicio else 0

        registrar_evento(
            _nivel_por_estado(respuesta.status_code),
            "solicitud_completada",
            metodo=request.method,
            endpoint=request.path,
            codigo_estado=respuesta.status_code,
            duracion_ms=duracion_ms,
            id_correlacion=id_correlacion_actual(),
            **_campos_del_actor(),
        )
        return respuesta


def _campos_del_actor() -> dict[str, Any]:
    """Cuenta, rol y caso de Bonita de la solicitud, si paso por `requiere_rol`.

    El actor lo deja app/core/acceso.py en `g.actor`; se lee por atributos para no importar ese
    modulo desde aca. `usuario_bonita` no se loguea: es un email (seccion 3 del contrato).
    """
    actor = g.get("actor")
    if actor is None:
        return {}
    campos: dict[str, Any] = {"cuenta": actor.cuenta, "rol": actor.rol.value}
    if actor.caso_bonita:
        campos["caso_bonita"] = actor.caso_bonita
    return campos
