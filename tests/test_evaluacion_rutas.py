"""Contrato HTTP de `POST /ofertas/evaluacion`, con el JSON tal como lo reenvía Bonita."""

from __future__ import annotations

import pytest

from app.core.acceso import Rol
from app.extensiones import db
from app.modulos.compromisos.modelos import Compromiso
from app.modulos.organizaciones.modelos import Item, TipoItem


@pytest.fixture
def ambulancias(base_de_datos):
    item = Item(
        codigo_recurso="RSR-AMBULANCIAS",
        nombre="Ambulancias",
        tipo=TipoItem.rescate,
        unidad_medida="unidades",
        consumible=False,
    )
    db.session.add(item)
    db.session.commit()
    return item


def test_evaluacion_con_cuit_nulo_rechaza_el_aporte_y_responde_200(cliente, cabeceras, ambulancias):
    peticion = {
        "emergencia_id": 30,
        "nivel_gravedad": "ALTA",
        "ofertas": [
            {
                "fecha_creacion": "2026-11-16T12:00:00+00:00",
                "oferta_id": 1,
                "version": 1,
                "organizaciones": [
                    {
                        "id": 7,
                        "identificador_nacional": None,
                        "nombre": "ONG sin CUIT",
                        "rol": "lider",
                    }
                ],
                "items": [
                    {
                        "aportes": [
                            {"cantidad": 1, "identificador_nacional": None, "organizacion_id": 7}
                        ],
                        "cantidad_total": 1,
                        "codigo_recurso": ambulancias.codigo_recurso,
                        "lote_item_id": 10,
                        "tipo_recurso": "rescate",
                        "unidad": "unidades",
                    }
                ],
            }
        ],
    }

    respuesta = cliente.post("/ofertas/evaluacion", json=peticion, headers=cabeceras(Rol.sistema))

    assert respuesta.status_code == 200
    oferta = respuesta.get_json()["ofertas"][0]
    assert oferta["organizaciones"][0]["identificador_nacional"] is None
    aporte = oferta["items"][0]["aportes"][0]
    assert aporte["identificador_nacional"] is None
    assert aporte["clasificacion"] == "rechazada"
    assert aporte["compromiso_registrado"] is False
    assert db.session.query(Compromiso).count() == 0


def test_evaluacion_sin_ofertas_responde_200_sin_comprometer(cliente, cabeceras, base_de_datos):
    respuesta = cliente.post(
        "/ofertas/evaluacion",
        json={"emergencia_id": 31, "nivel_gravedad": "MEDIA", "ofertas": []},
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "emergencia_id": 31,
        "nivel_gravedad": "MEDIA",
        "ofertas": [],
    }
    assert db.session.query(Compromiso).count() == 0


def test_evaluacion_sin_el_campo_ofertas_sigue_respondiendo_400(cliente, cabeceras, base_de_datos):
    respuesta = cliente.post(
        "/ofertas/evaluacion",
        json={"emergencia_id": 31, "nivel_gravedad": "MEDIA"},
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 400
