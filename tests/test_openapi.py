"""La especificación OpenAPI documenta la autenticación como la ve el profesor en Swagger."""

from __future__ import annotations

import pytest


@pytest.fixture
def especificacion(cliente):
    return cliente.get("/openapi.json").get_json()


def test_declara_los_dos_esquemas_de_seguridad(especificacion):
    esquemas = especificacion["components"]["securitySchemes"]

    assert esquemas["bearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Token obtenido en POST /login.",
    }
    assert esquemas["oauth2"]["flows"]["clientCredentials"]["tokenUrl"] == "/login"


def test_login_documenta_json_y_formulario_oauth2(especificacion):
    operacion = especificacion["paths"]["/login"]["post"]

    assert set(operacion["requestBody"]["content"]) == {
        "application/json",
        "application/x-www-form-urlencoded",
    }
    assert {"200", "400", "401", "415"} <= set(operacion["responses"])
    assert "security" not in operacion


def test_operaciones_protegidas_documentan_401_y_403_con_el_envelope(especificacion):
    operacion = especificacion["paths"]["/ongs/{cuit}/habilitacion"]["patch"]

    for estado in ("401", "403"):
        esquema = operacion["responses"][estado]["content"]["application/json"]["schema"]
        assert esquema == {"$ref": "#/components/schemas/RespuestaError"}
    assert "administrador" in operacion["responses"]["403"]["description"]


def test_errores_de_validacion_se_documentan_como_400(especificacion):
    operacion = especificacion["paths"]["/ongs"]["post"]

    assert "400" in operacion["responses"]
    assert "422" not in operacion["responses"]


def test_swagger_ui_conserva_el_token_al_recargar(app):
    assert app.config["OPENAPI_SWAGGER_UI_CONFIG"] == {"persistAuthorization": True}
