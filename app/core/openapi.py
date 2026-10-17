"""Documentacion OpenAPI (Swagger) de la API.

Reune lo que antes vivia suelto en la app factory: los datos de la especificacion, la
configuracion de Swagger UI y los esquemas de seguridad. La especificacion se sirve en
`/openapi.json` y Swagger UI en `/docs`.
"""

from __future__ import annotations

import flask_smorest
from flask import Flask

from app.core.errores import RespuestaError

TITULO = "Sistema Nacional de Gestión de Recursos y Riesgos"
VERSION = "v0.2.0"

DESCRIPCION = """
API del Sistema Nacional de RescueSync. Su cliente es el motor de **Bonita**; un
**administrador** del Sistema Nacional gestiona el padrón de ONGs.

## Cómo autenticarse

1. Pedí un token en `POST /login`, de cualquiera de estas dos formas:
   - **JSON** con `usuario` y `contrasena`.
   - **OAuth2 client credentials**: formulario `application/x-www-form-urlencoded` con
     `grant_type=client_credentials`. Es lo que usa el conector REST de Bonita.
2. Tocá **Authorize** y elegí una opción:
   - `bearerAuth`: pegá el `access_token` (sin la palabra `Bearer`).
   - `oauth2`: escribí el usuario como *client_id* y la contraseña como *client_secret*;
     Swagger pide el token solo.
3. Cada token dura `expires_in` segundos. Cuando vence, la API responde **401** con
   `detalle.motivo = "token_expirado"` y hay que pedir otro.

## Roles

| Rol | Quién lo usa | Qué puede hacer |
|---|---|---|
| `sistema` | Motor de Bonita | Consultar el padrón y operar el proceso |
| `administrador` | Operador del Sistema Nacional | Dar de alta ONGs y cambiar su estado |

Un rol sin permiso para la operación recibe **403** `PERMISO_DENEGADO`.

## Errores

Todos los errores usan el envelope `{"error": {codigo, mensaje, detalle, timestamp,
id_correlacion}}`. La única excepción es `POST /login` en modo OAuth2, que responde los errores
del RFC 6749 (`{"error": "invalid_client"}`) porque así los espera el conector de Bonita.
"""


class Api(flask_smorest.Api):
    """Api de flask-smorest que documenta los errores con el envelope del proyecto."""

    ERROR_SCHEMA = RespuestaError


def configurar_openapi(app: Flask) -> None:
    """Datos de la especificacion y de Swagger UI. Va antes de construir `Api(app)`."""
    app.config.update(
        API_TITLE=TITULO,
        API_VERSION=VERSION,
        OPENAPI_VERSION="3.1.0",
        OPENAPI_URL_PREFIX="/",
        OPENAPI_SWAGGER_UI_PATH="/docs",
        OPENAPI_SWAGGER_UI_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist/",
        # El token pegado en "Authorize" sobrevive a recargar la pagina.
        OPENAPI_SWAGGER_UI_CONFIG={"persistAuthorization": True},
        API_SPEC_OPTIONS={"info": {"description": DESCRIPCION.strip()}},
    )


def registrar_esquemas_de_seguridad(api: Api) -> None:
    """Declara los dos esquemas que muestra el boton "Authorize" de Swagger UI.

    Los nombres tienen que coincidir con `ESQUEMAS_DE_SEGURIDAD` de app/core/acceso.py.
    """
    api.spec.components.security_scheme(
        "bearerAuth",
        {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Token obtenido en POST /login.",
        },
    )
    api.spec.components.security_scheme(
        "oauth2",
        {
            "type": "oauth2",
            "description": (
                "Client credentials (RFC 6749 §4.4): client_id = usuario, "
                "client_secret = contraseña. Es el modo que usa el conector REST de Bonita."
            ),
            "flows": {"clientCredentials": {"tokenUrl": "/login", "scopes": {}}},
        },
    )
