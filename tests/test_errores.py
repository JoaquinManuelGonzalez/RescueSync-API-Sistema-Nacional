from __future__ import annotations

from app.core.errores import ReglaDeNegocioIncumplida

CAMPOS_DEL_ENVELOPE = {"codigo", "mensaje", "detalle", "timestamp", "id_correlacion"}


def test_ruta_inexistente_responde_404_con_envelope(cliente):
    respuesta = cliente.get("/no-existe")
    error = respuesta.get_json()["error"]

    assert respuesta.status_code == 404
    assert set(error) == CAMPOS_DEL_ENVELOPE
    assert error["codigo"] == "RECURSO_NO_ENCONTRADO"


def test_metodo_no_permitido_responde_405_con_envelope(cliente):
    respuesta = cliente.post("/health")

    assert respuesta.status_code == 405
    assert respuesta.get_json()["error"]["codigo"] == "METODO_NO_PERMITIDO"


def test_error_de_aplicacion_usa_su_codigo_y_estado(app, cliente):
    @app.get("/prueba/regla")
    def _regla():
        raise ReglaDeNegocioIncumplida(
            "La ONG no está habilitada.", detalle={"ong_id": 7, "motivo": "vencida"}
        )

    respuesta = cliente.get("/prueba/regla")
    error = respuesta.get_json()["error"]

    assert respuesta.status_code == 422
    assert error["codigo"] == "REGLA_DE_NEGOCIO_INCUMPLIDA"
    assert error["mensaje"] == "La ONG no está habilitada."
    assert error["detalle"] == {"ong_id": 7, "motivo": "vencida"}


def test_excepcion_no_contemplada_responde_500_sin_detalle_tecnico(app, cliente):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/prueba/explota")
    def _explota():
        raise RuntimeError("detalle interno que no tiene que salir")

    respuesta = cliente.get("/prueba/explota")
    error = respuesta.get_json()["error"]

    assert respuesta.status_code == 500
    assert error["codigo"] == "ERROR_INTERNO"
    assert "detalle interno" not in respuesta.get_data(as_text=True)
