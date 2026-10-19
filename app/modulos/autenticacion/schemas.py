"""Esquemas de /login y de /cuentas/yo."""

from __future__ import annotations

from marshmallow import Schema, fields, validate


class PeticionIngreso(Schema):
    """Login en JSON: lo usan Swagger, Postman y las personas."""

    usuario = fields.String(required=True, validate=validate.Length(min=1, max=100))
    contrasena = fields.String(
        required=True, load_only=True, validate=validate.Length(min=1, max=200)
    )


class PeticionClientCredentials(Schema):
    """Login OAuth2 client credentials (RFC 6749 §4.4), en application/x-www-form-urlencoded.

    Es el formato que manda el conector REST de Bonita en el modo "OAUTH2 (Client Credentials)".
    `client_id` y `client_secret` tambien pueden llegar en HTTP Basic. Solo documenta: el cuerpo
    se valida a mano para responder los errores del RFC.
    """

    grant_type = fields.String(
        required=True,
        validate=validate.OneOf(["client_credentials"]),
        metadata={"description": "Siempre `client_credentials`."},
    )
    client_id = fields.String(metadata={"description": "Usuario de la cuenta."})
    client_secret = fields.String(metadata={"description": "Contraseña o secreto de la cuenta."})
    scope = fields.String(metadata={"description": "Se ignora."})
    audience = fields.String(metadata={"description": "Se ignora."})


class RespuestaIngreso(Schema):
    access_token = fields.String(required=True, metadata={"description": "JWT firmado (HS256)."})
    token_type = fields.String(required=True, metadata={"description": "Siempre `Bearer`."})
    expires_in = fields.Integer(
        required=True, metadata={"description": "Segundos hasta que el token vence."}
    )


class TokenActual(Schema):
    emitido_en = fields.DateTime(required=True)
    expira_en = fields.DateTime(required=True)
    segundos_restantes = fields.Integer(required=True)


class TrazabilidadActual(Schema):
    usuario_bonita = fields.String(
        allow_none=True,
        metadata={"description": "X-Usuario-Bonita recibido. Solo se acepta del rol sistema."},
    )
    caso_bonita = fields.String(
        allow_none=True,
        metadata={"description": "X-Bonita-Process-Instance-Id recibido (rol sistema)."},
    )


class CuentaActual(Schema):
    usuario = fields.String(required=True)
    rol = fields.String(required=True)
    descripcion = fields.String(allow_none=True)
    token = fields.Nested(TokenActual, required=True)
    trazabilidad = fields.Nested(TrazabilidadActual, required=True)
