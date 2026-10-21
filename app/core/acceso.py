"""Autenticacion y autorizacion transversales.

Implementa docs/contratos/autenticacion.md. Cada modulo protege sus endpoints con el `Blueprint`
de este archivo en lugar del de flask-smorest:

    from app.core.acceso import Blueprint, Rol

    blueprint_compromisos = Blueprint("compromisos", __name__, url_prefix="/compromisos")

    @blueprint_compromisos.route("")
    class Compromisos(MethodView):
        @blueprint_compromisos.requiere_rol(Rol.sistema)   # siempre el primero, arriba de todo
        @blueprint_compromisos.arguments(PeticionCompromiso)
        @blueprint_compromisos.response(201, RespuestaCompromiso)
        def post(self, datos): ...

`requiere_rol` va arriba de todo para que la autenticacion corra antes que la validacion del
cuerpo: un pedido sin token recibe 401, aunque ademas tenga el cuerpo mal formado.

La API autentica clientes, no personas (ADR-005). Bonita usa una cuenta de rol `sistema` y, para
trazabilidad, informa en cabeceras que persona disparo la llamada y en que caso del proceso.
Esas cabeceras solo se aceptan de una cuenta `sistema`: para cualquier otra, el actor es la
cuenta misma.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any

import flask_smorest
from flask import Flask, g, jsonify, request
from flask_jwt_extended import get_current_user, get_jwt, verify_jwt_in_request
from webargs.flaskparser import FlaskParser

from app.core.errores import (
    MENSAJES_POR_CODIGO,
    PermisoDenegado,
    RespuestaError,
    construir_envelope,
)
from app.extensiones import jwt


class Rol(enum.Enum):
    """Roles de las cuentas de la API. El valor viaja en el claim `rol` del token."""

    # Motor de Bonita: el unico consumidor de las operaciones del proceso.
    sistema = "sistema"
    # Operador del Sistema Nacional: administra el padron de ONGs.
    administrador = "administrador"


# Cabeceras de trazabilidad que manda Bonita. La del caso la agrega sola el conector REST cuando
# se tilda "Add Bonita context headers"; la del usuario sale de una variable del proceso.
CABECERA_USUARIO_BONITA = "X-Usuario-Bonita"
CABECERA_CASO_BONITA = "X-Bonita-Process-Instance-Id"
LARGO_MAXIMO_CABECERA = 255

# Nombres de los esquemas declarados en la especificacion (app/core/openapi.py). Cualquiera de
# los dos alcanza: el token es el mismo, cambia como lo consigue Swagger UI.
ESQUEMAS_DE_SEGURIDAD: list[dict[str, list[str]]] = [{"bearerAuth": []}, {"oauth2": []}]

MOTIVOS_NO_AUTENTICADO: dict[str, str] = {
    "token_ausente": "Falta el encabezado Authorization con un token Bearer.",
    "token_invalido": "El token no es válido.",
    "token_expirado": "El token venció. Pedí uno nuevo en /login.",
    "cuenta_inactiva": "La cuenta del token no existe, está desactivada o cambió de rol.",
}
REALM = "sistema-nacional"


@dataclass(frozen=True)
class Actor:
    """Quien hace la solicitud en curso."""

    cuenta: str
    rol: Rol
    # Id de la cuenta en la base, para las claves foraneas de los historiales.
    cuenta_id: int | None = None
    usuario_bonita: str | None = None
    caso_bonita: str | None = None


class ParserDeArgumentos(FlaskParser):
    """Parser de webargs del proyecto: un cuerpo invalido es 400 (contrato de errores), no 422."""

    DEFAULT_VALIDATION_STATUS = 400


class Blueprint(flask_smorest.Blueprint):
    """Blueprint de flask-smorest con validacion en 400 y autorizacion por rol."""

    ARGUMENTS_PARSER = ParserDeArgumentos()
    PAGINATION_ARGUMENTS_PARSER = ParserDeArgumentos()

    def requiere_rol(self, *roles: Rol) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Exige un JWT valido cuyo rol este entre `roles`, y lo documenta en Swagger."""
        if not roles:
            raise ValueError("requiere_rol necesita al menos un rol")
        permitidos = tuple(roles)
        nombres = ", ".join(rol.value for rol in permitidos)

        def decorador(funcion: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(funcion)
            def envoltorio(*args: Any, **kwargs: Any) -> Any:
                verificar_acceso(permitidos)
                return funcion(*args, **kwargs)

            documentado = self.doc(security=ESQUEMAS_DE_SEGURIDAD)(envoltorio)
            documentado = self.alt_response(
                401,
                schema=RespuestaError,
                example={
                    "error": {
                        "codigo": "NO_AUTENTICADO",
                        "detalle": {"motivo": "token_expirado"},
                        "id_correlacion": "e7e3910...",
                        "mensaje": "El token venció. Pedí uno nuevo en /login.",
                        "timestamp": "2026-10-26T20:00:00.000Z",
                    }
                },
                description=(
                    "Falta el token, es inválido, venció o su cuenta está desactivada "
                    "(`detalle.motivo`)."
                ),
            )(documentado)
            return self.alt_response(
                403,
                schema=RespuestaError,
                example={
                    "error": {
                        "codigo": "PERMISO_DENEGADO",
                        "detalle": {
                            "rol": "rol_actual",
                            "roles_permitidos": ["rol_permitido_1", "rol_permitido_2"],
                        },
                        "id_correlacion": "e7e3910...",
                        "mensaje": "Las credenciales no habilitan esta operación.",
                        "timestamp": "2026-10-26T20:00:00.000Z",
                    }
                },
                description=(
                    f"El rol del token no habilita la operación. Roles permitidos: {nombres}."
                ),
            )(documentado)

        return decorador


def verificar_acceso(permitidos: tuple[Rol, ...]) -> Actor:
    """Valida el token de la solicitud y el rol. Deja el actor en `g` para el resto del pedido."""
    verify_jwt_in_request()
    claims = get_jwt()
    rol = claims.get("rol")
    if rol not in {permitido.value for permitido in permitidos}:
        raise PermisoDenegado(
            detalle={"rol": rol, "roles_permitidos": [permitido.value for permitido in permitidos]}
        )

    # La cuenta la carga el user_lookup_loader del modulo de autenticacion en cada pedido.
    cuenta = get_current_user()
    es_bonita = rol == Rol.sistema.value
    actor = Actor(
        cuenta=str(claims["sub"]),
        rol=Rol(rol),
        cuenta_id=getattr(cuenta, "id", None),
        usuario_bonita=_leer_cabecera(CABECERA_USUARIO_BONITA) if es_bonita else None,
        caso_bonita=_leer_cabecera(CABECERA_CASO_BONITA) if es_bonita else None,
    )
    g.actor = actor
    return actor


def actor_actual() -> Actor | None:
    """Actor de la solicitud en curso, o None si el endpoint no pasa por `requiere_rol`."""
    return g.get("actor")


def _leer_cabecera(nombre: str) -> str | None:
    valor = request.headers.get(nombre, "").strip()
    return valor[:LARGO_MAXIMO_CABECERA] or None


def respuesta_no_autenticado(motivo: str, *, token_presente: bool):
    """401 con el envelope del contrato y el desafio `WWW-Authenticate` del RFC 6750."""
    cuerpo = construir_envelope(
        "NO_AUTENTICADO",
        MOTIVOS_NO_AUTENTICADO.get(motivo, MENSAJES_POR_CODIGO["NO_AUTENTICADO"]),
        {"motivo": motivo},
    )
    desafio = f'Bearer realm="{REALM}"'
    if token_presente:
        desafio += ', error="invalid_token"'
    return jsonify(cuerpo), 401, {"WWW-Authenticate": desafio}


# Respuestas de flask-jwt-extended reemplazadas por el envelope. Se registran una vez, al importar
# el modulo, sobre la instancia compartida de `app.extensiones`.
@jwt.unauthorized_loader
def _sin_token(_motivo: str):
    return respuesta_no_autenticado("token_ausente", token_presente=False)


@jwt.invalid_token_loader
def _token_invalido(_motivo: str):
    return respuesta_no_autenticado("token_invalido", token_presente=True)


@jwt.expired_token_loader
def _token_expirado(_cabecera: dict, _datos: dict):
    return respuesta_no_autenticado("token_expirado", token_presente=True)


@jwt.user_lookup_error_loader
def _cuenta_inactiva(_cabecera: dict, _datos: dict):
    return respuesta_no_autenticado("cuenta_inactiva", token_presente=True)


def registrar_acceso(app: Flask) -> None:
    """Inicializa flask-jwt-extended (la carga de la cuenta la registra `autenticacion`)."""
    jwt.init_app(app)
