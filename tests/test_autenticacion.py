"""POST /login en sus dos modos (JSON y OAuth2 client credentials) y GET /cuentas/yo."""

from __future__ import annotations

import base64
from datetime import timedelta

import jwt as pyjwt
import pytest

from app.core.acceso import Rol
from app.core.configuracion import AUDIENCIA_JWT, EMISOR_JWT
from app.extensiones import db
from app.modulos.autenticacion.modelos import Cuenta
from tests.conftest import CONTRASENA_DE_PRUEBA, ENTORNO_MINIMO


def _claims(token: str) -> dict:
    return pyjwt.decode(
        token,
        ENTORNO_MINIMO["JWT_SECRET_KEY"],
        algorithms=["HS256"],
        audience=AUDIENCIA_JWT,
        issuer=EMISOR_JWT,
    )


def _basic(usuario: str, contrasena: str) -> dict[str, str]:
    credenciales = base64.b64encode(f"{usuario}:{contrasena}".encode()).decode()
    return {"Authorization": f"Basic {credenciales}"}


# --- Modo JSON ---------------------------------------------------------------------------


def test_login_json_devuelve_token_firmado_con_los_claims_del_contrato(cliente, crear_cuenta):
    crear_cuenta("admin-sn", Rol.administrador)

    respuesta = cliente.post(
        "/login", json={"usuario": "admin-sn", "contrasena": CONTRASENA_DE_PRUEBA}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["token_type"] == "Bearer"
    assert cuerpo["expires_in"] == 3600
    claims = _claims(cuerpo["access_token"])
    assert claims["sub"] == "admin-sn"
    assert claims["rol"] == "administrador"
    assert claims["exp"] - claims["iat"] == 3600
    assert respuesta.headers["Cache-Control"] == "no-store"


def test_login_respeta_la_expiracion_configurada(app, cliente, crear_cuenta):
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=5)
    crear_cuenta("admin-sn", Rol.administrador)

    cuerpo = cliente.post(
        "/login", json={"usuario": "admin-sn", "contrasena": CONTRASENA_DE_PRUEBA}
    ).get_json()

    assert cuerpo["expires_in"] == 300


def test_login_registra_el_ultimo_ingreso(cliente, crear_cuenta):
    crear_cuenta("admin-sn", Rol.administrador)

    cliente.post("/login", json={"usuario": "admin-sn", "contrasena": CONTRASENA_DE_PRUEBA})

    cuenta = db.session.query(Cuenta).filter_by(usuario="admin-sn").one()
    db.session.refresh(cuenta)
    assert cuenta.ultimo_ingreso is not None


@pytest.mark.parametrize(
    ("usuario", "contrasena"),
    [("admin-sn", "incorrecta"), ("no-existe", CONTRASENA_DE_PRUEBA)],
)
def test_login_json_rechaza_credenciales_con_el_mismo_mensaje(
    cliente, crear_cuenta, usuario, contrasena
):
    crear_cuenta("admin-sn", Rol.administrador)

    respuesta = cliente.post("/login", json={"usuario": usuario, "contrasena": contrasena})

    assert respuesta.status_code == 401
    error = respuesta.get_json()["error"]
    assert error["codigo"] == "NO_AUTENTICADO"
    assert error["mensaje"] == "Usuario o contraseña incorrectos."
    assert error["detalle"] == {"motivo": "credenciales_invalidas"}


def test_login_json_rechaza_cuenta_desactivada(cliente, crear_cuenta):
    crear_cuenta("admin-sn", Rol.administrador, activa=False)

    respuesta = cliente.post(
        "/login", json={"usuario": "admin-sn", "contrasena": CONTRASENA_DE_PRUEBA}
    )

    assert respuesta.status_code == 401
    assert respuesta.get_json()["error"]["mensaje"] == "Usuario o contraseña incorrectos."


def test_login_json_incompleto_responde_400_con_el_campo(cliente, base_de_datos):
    respuesta = cliente.post("/login", json={"usuario": "admin-sn"})

    assert respuesta.status_code == 400
    error = respuesta.get_json()["error"]
    assert error["codigo"] == "SOLICITUD_INVALIDA"
    assert error["detalle"] == {"json": {"contrasena": ["Campo obligatorio."]}}


def test_login_con_otro_tipo_de_contenido_responde_415(cliente, base_de_datos):
    respuesta = cliente.post("/login", data="usuario=admin", content_type="text/plain")

    assert respuesta.status_code == 415
    assert respuesta.get_json()["error"]["codigo"] == "TIPO_DE_CONTENIDO_NO_SOPORTADO"


# --- Modo OAuth2 client credentials (conector de Bonita) ----------------------------------


def test_client_credentials_en_el_cuerpo_devuelve_token(cliente, crear_cuenta):
    crear_cuenta("bonita-rescuesync", Rol.sistema)

    respuesta = cliente.post(
        "/login",
        data={
            "grant_type": "client_credentials",
            "client_id": "bonita-rescuesync",
            "client_secret": CONTRASENA_DE_PRUEBA,
        },
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["token_type"] == "Bearer"
    assert isinstance(cuerpo["expires_in"], int)
    assert _claims(cuerpo["access_token"])["rol"] == "sistema"
    assert respuesta.headers["Cache-Control"] == "no-store"


def test_client_credentials_por_http_basic_devuelve_token(cliente, crear_cuenta):
    crear_cuenta("bonita-rescuesync", Rol.sistema)

    respuesta = cliente.post(
        "/login",
        data={"grant_type": "client_credentials"},
        headers=_basic("bonita-rescuesync", CONTRASENA_DE_PRUEBA),
    )

    assert respuesta.status_code == 200
    assert _claims(respuesta.get_json()["access_token"])["sub"] == "bonita-rescuesync"


def test_client_credentials_invalidas_responden_el_error_del_rfc(cliente, crear_cuenta):
    crear_cuenta("bonita-rescuesync", Rol.sistema)

    respuesta = cliente.post(
        "/login",
        data={
            "grant_type": "client_credentials",
            "client_id": "bonita-rescuesync",
            "client_secret": "incorrecto",
        },
    )

    # El conector de Bonita lee `error` como texto: el envelope del proyecto no sirve aca.
    assert respuesta.status_code == 401
    assert respuesta.get_json()["error"] == "invalid_client"
    assert "error_description" in respuesta.get_json()


def test_client_credentials_por_basic_invalidas_piden_basic(cliente, crear_cuenta):
    crear_cuenta("bonita-rescuesync", Rol.sistema)

    respuesta = cliente.post(
        "/login",
        data={"grant_type": "client_credentials"},
        headers=_basic("bonita-rescuesync", "incorrecto"),
    )

    assert respuesta.status_code == 401
    assert respuesta.headers["WWW-Authenticate"].startswith("Basic")


@pytest.mark.parametrize(
    ("formulario", "estado", "error"),
    [
        ({"client_id": "x", "client_secret": "y"}, 400, "invalid_request"),
        (
            {"grant_type": "password", "client_id": "x", "client_secret": "y"},
            400,
            "unsupported_grant_type",
        ),
        ({"grant_type": "client_credentials"}, 401, "invalid_client"),
    ],
)
def test_client_credentials_mal_formado(cliente, base_de_datos, formulario, estado, error):
    respuesta = cliente.post("/login", data=formulario)

    assert respuesta.status_code == estado
    assert respuesta.get_json()["error"] == error


# --- GET /cuentas/yo ------------------------------------------------------------------------


def test_cuenta_propia_muestra_rol_y_vencimiento(cliente, cabeceras):
    respuesta = cliente.get("/cuentas/yo", headers=cabeceras(Rol.administrador))

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["usuario"] == "admin-sn"
    assert cuerpo["rol"] == "administrador"
    assert 0 < cuerpo["token"]["segundos_restantes"] <= 3600
    assert cuerpo["trazabilidad"] == {"usuario_bonita": None, "caso_bonita": None}


def test_token_obtenido_en_login_sirve_para_los_endpoints_protegidos(cliente, crear_cuenta):
    crear_cuenta("bonita-rescuesync", Rol.sistema)
    token = cliente.post(
        "/login",
        data={
            "grant_type": "client_credentials",
            "client_id": "bonita-rescuesync",
            "client_secret": CONTRASENA_DE_PRUEBA,
        },
    ).get_json()["access_token"]

    respuesta = cliente.get("/cuentas/yo", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 200
    assert respuesta.get_json()["rol"] == "sistema"
