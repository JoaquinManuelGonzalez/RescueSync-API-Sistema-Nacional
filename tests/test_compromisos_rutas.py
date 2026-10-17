"""Contrato HTTP del endpoint de compromiso de recursos."""

from __future__ import annotations

import pytest

from app.core.acceso import Rol
from app.extensiones import db
from app.modulos.compromisos.modelos import Compromiso
from app.modulos.organizaciones.modelos import (
    EstadoHabilitacion,
    Inventario,
    InventarioItem,
    Item,
    Organizacion,
    TipoItem,
    TipoOrganizacion,
)

PETICION = {
    "emergencia_externa_id": "emergencia-42",
    "nivel_gravedad": "MEDIA",
    "aportes": [
        {
            "identificador_nacional": "30-11111111-1",
            "codigo_recurso": "RSR-AGUA",
            "cantidad": 4,
            "tipo_asignacion": "principal",
        }
    ],
}


@pytest.fixture
def inventario_disponible(base_de_datos):
    organizacion = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="ONG de prueba",
        mail_contacto="ong@example.test",
        identificador_nacional="30-11111111-1",
        estado_habilitacion=EstadoHabilitacion.habilitada,
        inventario=Inventario(
            items=[
                InventarioItem(
                    item=Item(
                        codigo_recurso="RSR-AGUA",
                        nombre="Agua",
                        tipo=TipoItem.agua,
                        unidad_medida="litros",
                        consumible=True,
                    ),
                    cantidad_disponible=10,
                )
            ]
        ),
    )
    db.session.add(organizacion)
    db.session.commit()
    return organizacion


def test_post_compromete_recursos_y_devuelve_el_resumen(
    cliente,
    cabeceras,
    inventario_disponible,
):
    respuesta = cliente.post(
        "/recursos/compromisos",
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 201
    assert respuesta.get_json() == {
        "emergencia_externa_id": "emergencia-42",
        "repetido": False,
        "compromisos": [
            {
                "identificador_nacional": "30-11111111-1",
                "nivel_gravedad": "MEDIO",
                "estado": "COMPROMETIDO",
                "items": [
                    {
                        "codigo_recurso": "RSR-AGUA",
                        "cantidad": 4,
                        "tipo_asignacion": "principal",
                    }
                ],
            }
        ],
    }
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 6
    assert db.session.query(Compromiso).count() == 1


def test_reintento_identico_devuelve_200_sin_descontar_dos_veces(
    cliente,
    cabeceras,
    inventario_disponible,
):
    primera = cliente.post(
        "/recursos/compromisos",
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )
    segunda = cliente.post(
        "/recursos/compromisos",
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )

    assert primera.status_code == 201
    assert segunda.status_code == 200
    assert segunda.get_json()["repetido"] is True
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 6
    assert db.session.query(Compromiso).count() == 1


def test_administrador_no_puede_comprometer_recursos(cliente, cabeceras, inventario_disponible):
    respuesta = cliente.post(
        "/recursos/compromisos",
        json=PETICION,
        headers=cabeceras(Rol.administrador),
    )

    assert respuesta.status_code == 403
    assert db.session.query(Compromiso).count() == 0
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 10


@pytest.mark.parametrize(
    "cambios",
    [
        {"aportes": []},
        {"aportes": [{"identificador_nacional": "30-11111111-1"}]},
        {
            "aportes": [
                {
                    **PETICION["aportes"][0],
                    "cantidad": 0,
                }
            ]
        },
    ],
)
def test_cuerpo_invalido_responde_400(cliente, cabeceras, cambios):
    respuesta = cliente.post(
        "/recursos/compromisos",
        json={**PETICION, **cambios},
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "SOLICITUD_INVALIDA"


def test_stock_insuficiente_responde_422_y_no_guarda_parte_del_compromiso(
    cliente,
    cabeceras,
    inventario_disponible,
):
    peticion = {
        **PETICION,
        "aportes": [{**PETICION["aportes"][0], "cantidad": 11}],
    }

    respuesta = cliente.post(
        "/recursos/compromisos",
        json=peticion,
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == "REGLA_DE_NEGOCIO_INCUMPLIDA"
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 10
    assert db.session.query(Compromiso).count() == 0


def test_finalizacion_ong_cierra_proyecto_y_devuelve_el_estado(
    cliente,
    cabeceras,
    inventario_disponible,
):
    cliente.post(
        "/recursos/compromisos",
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )

    respuesta = cliente.post(
        "/recursos/compromisos/emergencia-42/ongs/30-11111111-1/finalizacion",
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "emergencia_externa_id": "emergencia-42",
        "identificador_nacional": "30-11111111-1",
        "proyecto_cerrado": True,
        "organizaciones_finalizadas": 1,
        "organizaciones_participantes": 1,
        "repetido": False,
    }
    assert db.session.query(Compromiso).one().estado.value == "LIBERADO"
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 6


def test_finalizacion_ong_requiere_rol_sistema(cliente, cabeceras):
    respuesta = cliente.post(
        "/recursos/compromisos/emergencia-42/ongs/30-11111111-1/finalizacion",
        headers=cabeceras(Rol.administrador),
    )

    assert respuesta.status_code == 403


def test_finalizacion_ong_inexistente_responde_404(cliente, cabeceras, inventario_disponible):
    cliente.post(
        "/recursos/compromisos",
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )

    respuesta = cliente.post(
        "/recursos/compromisos/emergencia-42/ongs/30-22222222-2/finalizacion",
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "RECURSO_NO_ENCONTRADO"
