"""Validacion del token y autorizacion por rol en los endpoints protegidos."""

from __future__ import annotations

from datetime import timedelta

import jwt as pyjwt
import pytest
from flask_jwt_extended import create_access_token

from app.core.acceso import Rol
from app.extensiones import db
from app.modulos.autenticacion.modelos import Cuenta
from tests.conftest import ENTORNO_MINIMO


def _motivo(respuesta) -> str:
    return respuesta.get_json()["error"]["detalle"]["motivo"]


def test_sin_token_responde_401_token_ausente(cliente, base_de_datos):
    respuesta = cliente.get("/cuentas/yo")

    assert respuesta.status_code == 401
    assert respuesta.get_json()["error"]["codigo"] == "NO_AUTENTICADO"
    assert _motivo(respuesta) == "token_ausente"
    assert respuesta.headers["WWW-Authenticate"] == 'Bearer realm="sistema-nacional"'


def test_otro_esquema_de_autorizacion_cuenta_como_token_ausente(cliente, base_de_datos):
    respuesta = cliente.get("/cuentas/yo", headers={"Authorization": "Basic YWRtaW46YWRtaW4="})

    assert respuesta.status_code == 401
    assert _motivo(respuesta) == "token_ausente"


@pytest.mark.parametrize("autorizacion", ["Bearer basura", "Bearer a.b.c", "Bearer"])
def test_token_mal_formado_responde_401_token_invalido(cliente, base_de_datos, autorizacion):
    respuesta = cliente.get("/cuentas/yo", headers={"Authorization": autorizacion})

    assert respuesta.status_code == 401
    assert _motivo(respuesta) == "token_invalido"


def test_token_con_firma_alterada_responde_401(cliente, cabeceras):
    autorizacion = cabeceras(Rol.administrador)["Authorization"]
    encabezado, datos, _firma = autorizacion.removeprefix("Bearer ").split(".")
    adulterado = pyjwt.encode(
        {"sub": "admin-sn", "rol": "administrador"}, "otra-clave-de-al-menos-32-caracteres!!"
    ).split(".")[2]

    respuesta = cliente.get(
        "/cuentas/yo", headers={"Authorization": f"Bearer {encabezado}.{datos}.{adulterado}"}
    )

    assert respuesta.status_code == 401
    assert _motivo(respuesta) == "token_invalido"
    assert 'error="invalid_token"' in respuesta.headers["WWW-Authenticate"]


def test_token_para_otra_audiencia_responde_401(cliente, crear_cuenta):
    crear_cuenta("admin-sn")
    token = pyjwt.encode(
        {
            "sub": "admin-sn",
            "rol": "administrador",
            "type": "access",
            "iss": "sistema-nacional",
            "aud": "otra-api",
            "jti": "x",
            "fresh": False,
        },
        ENTORNO_MINIMO["JWT_SECRET_KEY"],
        algorithm="HS256",
    )

    respuesta = cliente.get("/cuentas/yo", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401
    assert _motivo(respuesta) == "token_invalido"


def test_token_vencido_responde_401_token_expirado(cliente, crear_cuenta):
    crear_cuenta("admin-sn")
    token = create_access_token(
        identity="admin-sn",
        additional_claims={"rol": "administrador"},
        expires_delta=timedelta(seconds=-1),
    )

    respuesta = cliente.get("/cuentas/yo", headers={"Authorization": f"Bearer {token}"})

    assert respuesta.status_code == 401
    assert _motivo(respuesta) == "token_expirado"
    assert respuesta.get_json()["error"]["mensaje"] == "El token venció. Pedí uno nuevo en /login."


def test_cuenta_desactivada_invalida_sus_tokens_vigentes(cliente, cabeceras):
    autorizacion = cabeceras(Rol.administrador)
    cuenta = db.session.query(Cuenta).filter_by(usuario="admin-sn").one()
    cuenta.activa = False
    db.session.commit()

    respuesta = cliente.get("/cuentas/yo", headers=autorizacion)

    assert respuesta.status_code == 401
    assert _motivo(respuesta) == "cuenta_inactiva"


def test_cambiar_el_rol_de_la_cuenta_invalida_sus_tokens(cliente, cabeceras):
    autorizacion = cabeceras(Rol.administrador)
    cuenta = db.session.query(Cuenta).filter_by(usuario="admin-sn").one()
    cuenta.rol = Rol.sistema
    db.session.commit()

    respuesta = cliente.get("/cuentas/yo", headers=autorizacion)

    assert respuesta.status_code == 401
    assert _motivo(respuesta) == "cuenta_inactiva"


def test_rol_sin_permiso_responde_403_con_los_roles_permitidos(cliente, cabeceras):
    respuesta = cliente.post(
        "/ongs",
        json={"cuit": "30-71555444-2", "nombre": "X", "mail_contacto": "x@x.example"},
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 403
    error = respuesta.get_json()["error"]
    assert error["codigo"] == "PERMISO_DENEGADO"
    assert error["detalle"] == {"rol": "sistema", "roles_permitidos": ["administrador"]}


def test_la_autenticacion_corre_antes_que_la_validacion_del_cuerpo(cliente, base_de_datos):
    respuesta = cliente.post("/ongs", json={"cuerpo": "invalido"})

    assert respuesta.status_code == 401


def test_cabeceras_de_bonita_se_aceptan_del_rol_sistema(cliente, cabeceras):
    extra = {"X-Usuario-Bonita": "operador@chascomus.test", "X-Bonita-Process-Instance-Id": "4021"}

    respuesta = cliente.get("/cuentas/yo", headers=cabeceras(Rol.sistema, extra))

    assert respuesta.get_json()["trazabilidad"] == {
        "usuario_bonita": "operador@chascomus.test",
        "caso_bonita": "4021",
    }


def test_cabeceras_de_bonita_se_ignoran_de_otros_roles(cliente, cabeceras):
    extra = {"X-Usuario-Bonita": "alguien@x.test", "X-Bonita-Process-Instance-Id": "1"}

    respuesta = cliente.get("/cuentas/yo", headers=cabeceras(Rol.administrador, extra))

    assert respuesta.get_json()["trazabilidad"] == {"usuario_bonita": None, "caso_bonita": None}
