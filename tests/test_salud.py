from __future__ import annotations

from sqlalchemy.exc import OperationalError

from app.extensiones import db


def test_health_con_base_disponible_responde_200(cliente):
    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"status": "ok", "db": "ok"}


def test_health_sin_base_responde_503_con_envelope(cliente, monkeypatch):
    def _fallar(*_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, Exception("conexion rechazada"))

    monkeypatch.setattr(db.session, "execute", _fallar)

    respuesta = cliente.get("/health")
    cuerpo = respuesta.get_json()

    assert respuesta.status_code == 503
    assert cuerpo["status"] == "error"
    assert cuerpo["db"] == "error"
    assert cuerpo["error"]["codigo"] == "SERVICIO_NO_DISPONIBLE"
    assert cuerpo["error"]["detalle"] == {"componente": "base_de_datos"}
