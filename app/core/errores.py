"""Envelope unico de error y manejadores globales.

Implementa docs/contratos/errores.md. Todo error de la API, sin excepcion, sale con la
estructura `{"error": {codigo, mensaje, detalle, timestamp, id_correlacion}}`. A diferencia de
la aplicacion web, aca no hay navegador: el unico cliente es Bonita (conectores REST), asi que
la respuesta es siempre JSON.

Para Bonita la distincion importante es la del codigo HTTP: un 4xx es un rechazo de negocio
(no tiene sentido reintentar con el mismo cuerpo) y un 5xx es una falla de disponibilidad
(se puede reintentar).
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify
from marshmallow import Schema, fields
from werkzeug.exceptions import HTTPException

from app.core.logging import id_correlacion_actual, marca_de_tiempo, registrar_evento

# Seccion 2 del contrato: correspondencia entre codigo HTTP y codigo interno.
CODIGOS_POR_ESTADO: dict[int, str] = {
    400: "SOLICITUD_INVALIDA",
    401: "NO_AUTENTICADO",
    403: "PERMISO_DENEGADO",
    404: "RECURSO_NO_ENCONTRADO",
    405: "METODO_NO_PERMITIDO",
    409: "CONFLICTO_DE_ESTADO",
    415: "TIPO_DE_CONTENIDO_NO_SOPORTADO",
    422: "REGLA_DE_NEGOCIO_INCUMPLIDA",
    500: "ERROR_INTERNO",
    503: "SERVICIO_NO_DISPONIBLE",
}

# Mensajes por defecto, en espanol y sin detalle tecnico interno.
MENSAJES_POR_CODIGO: dict[str, str] = {
    "SOLICITUD_INVALIDA": "La solicitud tiene campos inválidos o incompletos.",
    "NO_AUTENTICADO": "La solicitud no trae credenciales válidas.",
    "PERMISO_DENEGADO": "Las credenciales no habilitan esta operación.",
    "RECURSO_NO_ENCONTRADO": "El recurso solicitado no existe.",
    "METODO_NO_PERMITIDO": "El método HTTP no está permitido para este recurso.",
    "CONFLICTO_DE_ESTADO": "La operación no se puede realizar en el estado actual.",
    "TIPO_DE_CONTENIDO_NO_SOPORTADO": "El cuerpo de la solicitud tiene que ser JSON.",
    "REGLA_DE_NEGOCIO_INCUMPLIDA": "La operación no cumple una regla de negocio.",
    "ERROR_INTERNO": "Ocurrió un error inesperado. Reintentá en unos minutos.",
    "SERVICIO_NO_DISPONIBLE": "El servicio no está disponible en este momento. Reintentá en unos "
    "minutos.",
}


class ErrorDeAplicacion(Exception):
    """Error de negocio o transversal que se devuelve con el envelope del contrato.

    Los modulos de dominio la subclasifican fijando `codigo` y `estado_http`, por ejemplo:

        class RecursoInsuficiente(ErrorDeAplicacion):
            codigo = "RECURSO_INSUFICIENTE"
            estado_http = 422
    """

    codigo: str = "ERROR_INTERNO"
    estado_http: int = 500

    def __init__(
        self,
        mensaje: str | None = None,
        *,
        detalle: Any = None,
        codigo: str | None = None,
        estado_http: int | None = None,
    ) -> None:
        if codigo is not None:
            self.codigo = codigo
        if estado_http is not None:
            self.estado_http = estado_http
        generico = MENSAJES_POR_CODIGO["ERROR_INTERNO"]
        self.mensaje = mensaje or MENSAJES_POR_CODIGO.get(self.codigo, generico)
        self.detalle = detalle
        super().__init__(self.mensaje)


class SolicitudInvalida(ErrorDeAplicacion):
    codigo = "SOLICITUD_INVALIDA"
    estado_http = 400


class NoAutenticado(ErrorDeAplicacion):
    codigo = "NO_AUTENTICADO"
    estado_http = 401


class PermisoDenegado(ErrorDeAplicacion):
    codigo = "PERMISO_DENEGADO"
    estado_http = 403


class RecursoNoEncontrado(ErrorDeAplicacion):
    codigo = "RECURSO_NO_ENCONTRADO"
    estado_http = 404


class ConflictoDeEstado(ErrorDeAplicacion):
    codigo = "CONFLICTO_DE_ESTADO"
    estado_http = 409


class ReglaDeNegocioIncumplida(ErrorDeAplicacion):
    codigo = "REGLA_DE_NEGOCIO_INCUMPLIDA"
    estado_http = 422


class ServicioNoDisponible(ErrorDeAplicacion):
    """Una dependencia propia (por ejemplo, la base) no responde. Invita a reintentar."""

    codigo = "SERVICIO_NO_DISPONIBLE"
    estado_http = 503


class CuerpoError(Schema):
    """Contenido de `error` en el envelope. Solo documenta: las respuestas se arman a mano."""

    codigo = fields.String(
        required=True, metadata={"description": "Código interno estable (contrato de errores)."}
    )
    mensaje = fields.String(required=True, metadata={"description": "Mensaje en español."})
    detalle = fields.Raw(
        allow_none=True,
        metadata={"description": "Información adicional: campos inválidos, motivo, etc."},
    )
    timestamp = fields.String(required=True, metadata={"description": "ISO-8601 UTC."})
    id_correlacion = fields.String(
        required=True, metadata={"description": "X-Correlation-Id recibido o generado."}
    )


class RespuestaError(Schema):
    """Envelope único de error. flask-smorest lo usa para documentar los errores 4xx/5xx."""

    error = fields.Nested(CuerpoError, required=True)


# Traduccion de los mensajes de validacion de marshmallow que mas aparecen. El resto se devuelve
# tal cual: el `mensaje` del envelope ya esta en espanol y el detalle es orientativo.
MENSAJES_DE_VALIDACION: dict[str, str] = {
    "Missing data for required field.": "Campo obligatorio.",
    "Unknown field.": "Campo desconocido.",
    "Field may not be null.": "No puede ser nulo.",
    "Not a valid string.": "Debe ser un texto.",
    "Not a valid integer.": "Debe ser un número entero.",
    "Not a valid email address.": "No es un correo electrónico válido.",
    "Invalid input type.": "Tipo de dato inválido.",
}


def traducir_mensajes(mensajes: Any) -> Any:
    """Recorre los mensajes de validacion (anidados por ubicacion y campo) y los traduce."""
    if isinstance(mensajes, dict):
        return {clave: traducir_mensajes(valor) for clave, valor in mensajes.items()}
    if isinstance(mensajes, list):
        return [traducir_mensajes(valor) for valor in mensajes]
    if isinstance(mensajes, str):
        return MENSAJES_DE_VALIDACION.get(mensajes, mensajes)
    return mensajes


def construir_envelope(codigo: str, mensaje: str, detalle: Any = None) -> dict[str, Any]:
    """Arma el cuerpo de error del contrato, con timestamp y correlacion ya resueltos."""
    return {
        "error": {
            "codigo": codigo,
            "mensaje": mensaje,
            "detalle": detalle,
            "timestamp": marca_de_tiempo(),
            "id_correlacion": id_correlacion_actual(),
        }
    }


def registrar_manejadores(app: Flask) -> None:
    """Engancha los manejadores globales para que ninguna excepcion escape del envelope."""

    @app.errorhandler(ErrorDeAplicacion)
    def _error_de_aplicacion(error: ErrorDeAplicacion):
        cuerpo = construir_envelope(error.codigo, error.mensaje, error.detalle)
        return jsonify(cuerpo), error.estado_http

    @app.errorhandler(HTTPException)
    def _error_http(error: HTTPException):
        # webargs (detras de @blp.arguments) aborta con los mensajes por campo en `error.data`.
        # Para el contrato es un cuerpo invalido: 400 con el detalle, nunca un 422 sin datos.
        mensajes = (getattr(error, "data", None) or {}).get("messages")
        if mensajes:
            cuerpo = construir_envelope(
                "SOLICITUD_INVALIDA",
                MENSAJES_POR_CODIGO["SOLICITUD_INVALIDA"],
                traducir_mensajes(mensajes),
            )
            return jsonify(cuerpo), 400

        estado = error.code or 500
        codigo = CODIGOS_POR_ESTADO.get(estado, "ERROR_INTERNO")
        mensaje = MENSAJES_POR_CODIGO.get(codigo, error.name)
        return jsonify(construir_envelope(codigo, mensaje)), estado

    @app.errorhandler(Exception)
    def _error_no_contemplado(error: Exception):
        # El detalle tecnico queda en el log, nunca en la respuesta: el cliente solo ve el
        # mensaje generico y el id de correlacion para buscarlo.
        registrar_evento(
            logging.ERROR,
            "excepcion_no_contemplada",
            type(error).__name__,
            id_correlacion=id_correlacion_actual(),
        )
        app.logger.exception("excepcion_no_contemplada")
        mensaje = MENSAJES_POR_CODIGO["ERROR_INTERNO"]
        return jsonify(construir_envelope("ERROR_INTERNO", mensaje)), 500
