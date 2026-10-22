"""Endpoints de autenticacion: POST /login y GET /cuentas/yo."""

from __future__ import annotations

from datetime import UTC, datetime

from flask import jsonify, request
from flask.views import MethodView
from flask_jwt_extended import get_jwt
from marshmallow import ValidationError

from app.core.acceso import Blueprint, Rol, actor_actual
from app.core.errores import (
    ErrorDeAplicacion,
    NoAutenticado,
    RespuestaError,
    SolicitudInvalida,
    traducir_mensajes,
)
from app.modulos.autenticacion.schemas import (
    CuentaActual,
    PeticionClientCredentials,
    PeticionIngreso,
    RespuestaIngreso,
)
from app.modulos.autenticacion.servicios import autenticar, cuenta_actual, emitir_token

blueprint_autenticacion = Blueprint(
    "autenticacion",
    __name__,
    description="Autenticación: obtención de tokens JWT y datos de la cuenta del token.",
)

TIPO_FORMULARIO = "application/x-www-form-urlencoded"
# RFC 6749 §5.1: la respuesta con el token no se cachea en ningun intermediario.
CABECERAS_SIN_CACHE = {"Cache-Control": "no-store", "Pragma": "no-cache"}

CUERPO_LOGIN = {
    "required": True,
    "description": (
        "JSON para Swagger y Postman, o formulario OAuth2 client credentials para el conector "
        "de Bonita. En el formulario, `client_id` y `client_secret` pueden ir en HTTP Basic."
    ),
    "content": {
        "application/json": {
            "schema": PeticionIngreso,
            "example": {"usuario": "admin-sn", "contrasena": "una-contrasena-larga"},
        },
        TIPO_FORMULARIO: {
            "schema": PeticionClientCredentials,
            "example": {
                "grant_type": "client_credentials",
                "client_id": "bonita-rescuesync",
                "client_secret": "secreto-generado-por-flask-cuentas",
            },
        },
    },
}

EJEMPLO_ERROR_400_AUTH = {
    "error": {
        "codigo": "SOLICITUD_INVALIDA",
        "detalle": {"json": {"_schema": ["Tipo de dato inválido."]}},
        "id_correlacion": "e7e3910...",
        "mensaje": "La solicitud tiene campos inválidos o incompletos.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_ERROR_401_AUTH = {
    "error": {
        "codigo": "NO_AUTENTICADO",
        "detalle": {"motivo": "credenciales_invalidas"},
        "id_correlacion": "e7e3910...",
        "mensaje": "Usuario o contraseña incorrectos.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_CUENTA_PROPIA = {
    "descripcion": "Operador del Sistema Nacional",
    "rol": "administrador",
    "token": {
        "emitido_en": "2026-10-21T23:06:44+00:00",
        "expira_en": "2026-10-22T00:06:44+00:00",
        "segundos_restantes": 3292,
    },
    "trazabilidad": {"caso_bonita": None, "usuario_bonita": None},
    "usuario": "admin-sn",
}


@blueprint_autenticacion.route("/login")
class Login(MethodView):
    @blueprint_autenticacion.doc(requestBody=CUERPO_LOGIN)
    @blueprint_autenticacion.response(
        200,
        RespuestaIngreso,
        description="Token emitido.",
        example={
            "access_token": "eyJhbGciOiJIUzI1NiIs...",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )
    @blueprint_autenticacion.alt_response(
        400,
        schema=RespuestaError,
        description=(
            'JSON: faltan campos (`SOLICITUD_INVALIDA`). Formulario: `{"error": '
            '"invalid_request"}` o `{"error": "unsupported_grant_type"}` (RFC 6749 §5.2).'
        ),
        example=EJEMPLO_ERROR_400_AUTH,
    )
    @blueprint_autenticacion.alt_response(
        401,
        schema=RespuestaError,
        description=(
            "Credenciales inválidas o cuenta desactivada. JSON: `NO_AUTENTICADO`. "
            'Formulario: `{"error": "invalid_client"}` (RFC 6749 §5.2).'
        ),
        example=EJEMPLO_ERROR_401_AUTH,
    )
    @blueprint_autenticacion.alt_response(
        415, schema=RespuestaError, description="El cuerpo no es JSON ni formulario."
    )
    def post(self):
        """Iniciar sesión

        Valida las credenciales de una cuenta y devuelve un JWT para el resto de la API.
        """
        if request.mimetype == TIPO_FORMULARIO:
            return _ingreso_client_credentials()
        if request.is_json:
            return _ingreso_json()
        raise ErrorDeAplicacion(
            "El cuerpo tiene que ser JSON o application/x-www-form-urlencoded.",
            codigo="TIPO_DE_CONTENIDO_NO_SOPORTADO",
            estado_http=415,
        )


def _ingreso_json():
    try:
        credenciales = PeticionIngreso().load(request.get_json(silent=True))
    except ValidationError as error:
        raise SolicitudInvalida(detalle=traducir_mensajes({"json": error.messages})) from error

    cuenta = autenticar(credenciales["usuario"], credenciales["contrasena"], modo="json")
    if cuenta is None:
        raise NoAutenticado(
            "Usuario o contraseña incorrectos.", detalle={"motivo": "credenciales_invalidas"}
        )
    return emitir_token(cuenta), 200, CABECERAS_SIN_CACHE


def _ingreso_client_credentials():
    """RFC 6749 §4.4. Los errores siguen el §5.2 porque el conector de Bonita lee `error`
    como texto: con el envelope del proyecto fallaria con un error de tipos en vez de informar
    el motivo."""
    formulario = request.form
    autorizacion = request.authorization
    basic = autorizacion if autorizacion is not None and autorizacion.type == "basic" else None
    if basic is not None:
        client_id, client_secret = basic.username, basic.password
    else:
        client_id, client_secret = formulario.get("client_id"), formulario.get("client_secret")

    tipo = formulario.get("grant_type")
    if not tipo:
        return _error_oauth2(400, "invalid_request", "Falta grant_type.")
    if tipo != "client_credentials":
        return _error_oauth2(
            400, "unsupported_grant_type", "Solo se admite grant_type=client_credentials."
        )
    if not client_id or not client_secret:
        return _error_oauth2(
            401, "invalid_client", "Faltan client_id y client_secret.", basic=basic is not None
        )

    cuenta = autenticar(client_id, client_secret, modo="client_credentials")
    if cuenta is None:
        return _error_oauth2(
            401, "invalid_client", "Credenciales del cliente inválidas.", basic=basic is not None
        )
    return emitir_token(cuenta), 200, CABECERAS_SIN_CACHE


def _error_oauth2(estado: int, error: str, descripcion: str, *, basic: bool = False):
    respuesta = jsonify({"error": error, "error_description": descripcion})
    respuesta.status_code = estado
    respuesta.headers.update(CABECERAS_SIN_CACHE)
    if basic:
        # RFC 6749 §5.2: si el cliente intento autenticarse por el encabezado, se le responde
        # con el desafio del mismo esquema.
        respuesta.headers["WWW-Authenticate"] = 'Basic realm="sistema-nacional"'
    return respuesta


@blueprint_autenticacion.route("/cuentas/yo")
class CuentaPropia(MethodView):
    @blueprint_autenticacion.requiere_rol(Rol.sistema, Rol.administrador)
    @blueprint_autenticacion.response(
        200,
        CuentaActual,
        example=EJEMPLO_CUENTA_PROPIA,
    )
    def get(self):
        """Ver la cuenta del token

        Devuelve la cuenta y el rol del token, cuándo vence y las cabeceras de trazabilidad que
        la API tomó del pedido. Sirve para probar un token o la configuración del conector de
        Bonita.
        """
        cuenta = cuenta_actual()
        claims = get_jwt()
        actor = actor_actual()
        expira_en = datetime.fromtimestamp(claims["exp"], UTC)
        return {
            "usuario": cuenta.usuario,
            "rol": cuenta.rol.value,
            "descripcion": cuenta.descripcion,
            "token": {
                "emitido_en": datetime.fromtimestamp(claims["iat"], UTC),
                "expira_en": expira_en,
                "segundos_restantes": max(0, int((expira_en - datetime.now(UTC)).total_seconds())),
            },
            "trazabilidad": {
                "usuario_bonita": actor.usuario_bonita if actor else None,
                "caso_bonita": actor.caso_bonita if actor else None,
            },
        }
