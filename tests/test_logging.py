from __future__ import annotations

import json
import logging
import uuid

from app.core.logging import FormateadorJsonLines, redactar, redactar_cabeceras


def test_correlacion_recibida_se_devuelve_igual(cliente):
    respuesta = cliente.get("/health", headers={"X-Correlation-Id": "caso-bonita-123"})

    assert respuesta.headers["X-Correlation-Id"] == "caso-bonita-123"


def test_sin_correlacion_se_genera_un_uuid(cliente):
    respuesta = cliente.get("/health")

    uuid.UUID(respuesta.headers["X-Correlation-Id"])


def test_el_envelope_lleva_la_misma_correlacion_que_la_cabecera(cliente):
    respuesta = cliente.get("/no-existe", headers={"X-Correlation-Id": "abc-123"})

    assert respuesta.get_json()["error"]["id_correlacion"] == "abc-123"


def test_cada_solicitud_emite_eventos_con_correlacion(cliente, caplog):
    cliente.get("/no-existe", headers={"X-Correlation-Id": "traza-1"})

    eventos = {registro.evento: registro.campos for registro in caplog.records}

    assert eventos["solicitud_entrante"]["id_correlacion"] == "traza-1"
    assert eventos["solicitud_completada"]["codigo_estado"] == 404
    assert eventos["solicitud_completada"]["id_correlacion"] == "traza-1"


def test_health_no_se_loguea(cliente, caplog):
    cliente.get("/health")

    assert caplog.records == []


def test_formateador_emite_una_linea_json_con_los_campos_del_contrato():
    registro = logging.LogRecord("sistema_nacional", logging.WARNING, "", 0, "", None, None)
    registro.evento = "solicitud_completada"
    registro.campos = {"codigo_estado": 404, "id_correlacion": "x"}

    linea = FormateadorJsonLines().format(registro)
    evento = json.loads(linea)

    assert "\n" not in linea
    assert evento["nivel"] == "WARN"
    assert evento["evento"] == "solicitud_completada"
    assert evento["codigo_estado"] == 404
    assert evento["timestamp"].endswith("Z")


def test_redactar_oculta_campos_sensibles_anidados():
    cuerpo = {"ong": {"nombre": "Cruz", "cuit": "30-1"}, "items": [{"email": "a@b"}], "id": 3}

    assert redactar(cuerpo) == {
        "ong": {"nombre": "***", "cuit": "***"},
        "items": [{"email": "***"}],
        "id": 3,
    }


def test_redactar_cabeceras_oculta_authorization_entera():
    cabeceras = redactar_cabeceras({"Authorization": "Bearer xyz", "Accept": "application/json"})

    assert cabeceras == {"Authorization": "***", "Accept": "application/json"}
