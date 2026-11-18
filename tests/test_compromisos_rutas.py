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

# Los ids de emergencia son UUID: la web los genera y no se repiten entre entornos.
EMERGENCIA = "0193f4a2-7c1e-7b5d-9a3f-2e8c4b6d0042"
EMERGENCIA_SIN_COMPROMISOS = "0193f4a2-7c1e-7b5d-9a3f-2e8c4b6d0000"

PETICION = {
    "emergencia_externa_id": EMERGENCIA,
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
                        consumible=False,
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
        "emergencia_externa_id": EMERGENCIA,
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


def test_liberar_recursos_devuelve_inventario_y_es_idempotente(
    cliente,
    cabeceras,
    inventario_disponible,
):
    cliente.post(
        "/recursos/compromisos",
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )

    primera = cliente.post(
        f"/recursos/compromisos/{EMERGENCIA}/liberacion",
        headers=cabeceras(Rol.sistema),
    )
    segunda = cliente.post(
        f"/recursos/compromisos/{EMERGENCIA}/liberacion",
        headers=cabeceras(Rol.sistema),
    )

    assert primera.status_code == 200
    assert primera.get_json() == {
        "emergencia_externa_id": EMERGENCIA,
        "repetido": False,
        "compromisos": [
            {
                "identificador_nacional": "30-11111111-1",
                "nivel_gravedad": "MEDIO",
                "estado": "LIBERADO",
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
    assert segunda.status_code == 200
    assert segunda.get_json()["repetido"] is True
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 10
    assert db.session.query(Compromiso).one().estado.value == "LIBERADO"


def test_reinicio_convocatoria_permite_volver_a_comprometer(
    cliente,
    cabeceras,
    inventario_disponible,
):
    endpoint_compromisos = "/recursos/compromisos"
    endpoint_liberacion = f"/recursos/compromisos/{EMERGENCIA}/liberacion"

    primera = cliente.post(
        endpoint_compromisos,
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )
    liberacion = cliente.post(endpoint_liberacion, headers=cabeceras(Rol.sistema))
    segunda = cliente.post(
        endpoint_compromisos,
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )

    assert primera.status_code == 201
    assert liberacion.status_code == 200
    assert segunda.status_code == 201
    assert segunda.get_json()["repetido"] is False
    assert db.session.query(Compromiso).one().estado.value == "COMPROMETIDO"
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 6


def test_liberar_recursos_requiere_rol_sistema(cliente, cabeceras):
    respuesta = cliente.post(
        f"/recursos/compromisos/{EMERGENCIA}/liberacion",
        headers=cabeceras(Rol.administrador),
    )

    assert respuesta.status_code == 403


def test_liberar_recursos_sin_compromisos_responde_200_vacio(cliente, cabeceras):
    respuesta = cliente.post(
        f"/recursos/compromisos/{EMERGENCIA_SIN_COMPROMISOS}/liberacion",
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "emergencia_externa_id": EMERGENCIA_SIN_COMPROMISOS,
        "repetido": False,
        "compromisos": [],
    }


def test_liberar_recursos_de_ong_es_idempotente(cliente, cabeceras, inventario_disponible):
    cliente.post(
        "/recursos/compromisos",
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )
    endpoint = f"/recursos/compromisos/{EMERGENCIA}/ongs/30-11111111-1/liberacion"

    primera = cliente.post(endpoint, headers=cabeceras(Rol.sistema))
    segunda = cliente.post(endpoint, headers=cabeceras(Rol.sistema))

    assert primera.status_code == segunda.status_code == 200
    assert primera.get_json()["repetido"] is False
    assert primera.get_json()["compromisos"][0]["estado"] == "LIBERADO"
    assert segunda.get_json()["repetido"] is True
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 10


def test_liberar_recursos_de_ong_requiere_rol_sistema(cliente, cabeceras):
    respuesta = cliente.post(
        f"/recursos/compromisos/{EMERGENCIA}/ongs/30-11111111-1/liberacion",
        headers=cabeceras(Rol.administrador),
    )

    assert respuesta.status_code == 403


def test_liberar_recursos_de_ong_sin_compromiso_responde_404(cliente, cabeceras):
    respuesta = cliente.post(
        f"/recursos/compromisos/{EMERGENCIA}/ongs/30-11111111-1/liberacion",
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "RECURSO_NO_ENCONTRADO"


def test_finalizacion_global_cierra_emergencia_y_devuelve_el_estado(
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
        f"/recursos/compromisos/{EMERGENCIA}/finalizacion",
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "emergencia_externa_id": EMERGENCIA,
        "proyecto_cerrado": True,
        "organizaciones_finalizadas": 1,
        "organizaciones_participantes": 1,
        "repetido": False,
    }
    assert db.session.query(Compromiso).one().estado.value == "LIBERADO"
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 10


def test_finalizacion_global_es_idempotente(cliente, cabeceras, inventario_disponible):
    cliente.post(
        "/recursos/compromisos",
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )
    endpoint = f"/recursos/compromisos/{EMERGENCIA}/finalizacion"

    primera = cliente.post(endpoint, headers=cabeceras(Rol.sistema))
    segunda = cliente.post(endpoint, headers=cabeceras(Rol.sistema))

    assert primera.status_code == segunda.status_code == 200
    assert primera.get_json()["repetido"] is False
    assert segunda.get_json()["repetido"] is True
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 10


def test_finalizacion_global_requiere_rol_sistema(cliente, cabeceras):
    respuesta = cliente.post(
        f"/recursos/compromisos/{EMERGENCIA}/finalizacion",
        headers=cabeceras(Rol.administrador),
    )

    assert respuesta.status_code == 403


def test_finalizacion_global_sin_compromisos_responde_404(cliente, cabeceras):
    respuesta = cliente.post(
        f"/recursos/compromisos/{EMERGENCIA}/finalizacion",
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "RECURSO_NO_ENCONTRADO"


def test_validar_recursos_exitoso_dry_run_sin_efectos_colaterales(
    cliente,
    cabeceras,
    inventario_disponible,
):
    respuesta = cliente.post(
        "/recursos/compromisos/validar",
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "valido": True,
        "motivos": [],
    }
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 10
    assert db.session.query(Compromiso).count() == 0


def test_validar_recursos_stock_insuficiente_responde_200_con_valido_false(
    cliente,
    cabeceras,
    inventario_disponible,
):
    peticion = {
        **PETICION,
        "aportes": [{**PETICION["aportes"][0], "cantidad": 15}],
    }

    respuesta = cliente.post(
        "/recursos/compromisos/validar",
        json=peticion,
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["valido"] is False
    assert len(datos["motivos"]) == 1
    assert datos["motivos"][0]["motivo"] == "stock_insuficiente"
    assert datos["motivos"][0]["cantidad_disponible"] == 10
    assert datos["motivos"][0]["cantidad_solicitada"] == 15
    assert inventario_disponible.inventario.items[0].cantidad_disponible == 10
    assert db.session.query(Compromiso).count() == 0


def test_validar_recursos_requiere_rol_sistema(cliente, cabeceras):
    respuesta = cliente.post(
        "/recursos/compromisos/validar",
        json=PETICION,
        headers=cabeceras(Rol.administrador),
    )

    assert respuesta.status_code == 403


def test_post_compromisos_ong_no_habilitada_responde_422(
    cliente,
    cabeceras,
    inventario_disponible,
):
    inventario_disponible.estado_habilitacion = EstadoHabilitacion.suspendida
    db.session.commit()

    respuesta = cliente.post(
        "/recursos/compromisos",
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 422
    datos = respuesta.get_json()
    assert datos["error"]["codigo"] == "REGLA_DE_NEGOCIO_INCUMPLIDA"
    assert datos["error"]["detalle"] == {"identificadores_nacionales": ["30-11111111-1"]}


def test_post_compromisos_recurso_no_declarado_responde_422(
    cliente,
    cabeceras,
    inventario_disponible,
):
    item = Item(
        codigo_recurso="RSR-FRAZADAS",
        nombre="Frazadas",
        tipo=TipoItem.abrigo,
        unidad_medida="unidades",
        consumible=True,
    )
    db.session.add(item)
    db.session.commit()

    peticion = {
        **PETICION,
        "aportes": [
            {
                "identificador_nacional": "30-11111111-1",
                "codigo_recurso": "RSR-FRAZADAS",
                "cantidad": 5,
                "tipo_asignacion": "principal",
            }
        ],
    }

    respuesta = cliente.post(
        "/recursos/compromisos",
        json=peticion,
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 422
    datos = respuesta.get_json()
    assert datos["error"]["codigo"] == "REGLA_DE_NEGOCIO_INCUMPLIDA"
    assert datos["error"]["detalle"] == {
        "identificador_nacional": "30-11111111-1",
        "codigo_recurso": "RSR-FRAZADAS",
    }


def test_validar_recursos_ong_no_habilitada_responde_valido_false(
    cliente,
    cabeceras,
    inventario_disponible,
):
    inventario_disponible.estado_habilitacion = EstadoHabilitacion.suspendida
    db.session.commit()

    respuesta = cliente.post(
        "/recursos/compromisos/validar",
        json=PETICION,
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["valido"] is False
    assert any(m["motivo"] == "organizacion_no_habilitada" for m in datos["motivos"])


def test_validar_recursos_recurso_no_declarado_responde_valido_false(
    cliente,
    cabeceras,
    inventario_disponible,
):
    item = Item(
        codigo_recurso="RSR-FRAZADAS",
        nombre="Frazadas",
        tipo=TipoItem.abrigo,
        unidad_medida="unidades",
        consumible=True,
    )
    db.session.add(item)
    db.session.commit()

    peticion = {
        **PETICION,
        "aportes": [
            {
                "identificador_nacional": "30-11111111-1",
                "codigo_recurso": "RSR-FRAZADAS",
                "cantidad": 5,
                "tipo_asignacion": "principal",
            }
        ],
    }

    respuesta = cliente.post(
        "/recursos/compromisos/validar",
        json=peticion,
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos["valido"] is False
    assert any(m["motivo"] == "recurso_no_declarado" for m in datos["motivos"])


def test_post_rechaza_una_emergencia_que_no_es_uuid(cliente, cabeceras, inventario_disponible):
    # Un id entero o de texto libre puede repetirse entre las webs que usan la misma API.
    respuesta = cliente.post(
        "/recursos/compromisos",
        json={**PETICION, "emergencia_externa_id": "1"},
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["detalle"] == {
        "json": {"emergencia_externa_id": ["Debe ser un UUID válido."]}
    }
    assert db.session.query(Compromiso).count() == 0


@pytest.mark.parametrize("accion", ["liberacion", "finalizacion", "ongs/30-11111111-1/liberacion"])
def test_las_acciones_sobre_una_emergencia_que_no_es_uuid_responden_404(cliente, cabeceras, accion):
    respuesta = cliente.post(
        f"/recursos/compromisos/emergencia-42/{accion}",
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "RECURSO_NO_ENCONTRADO"


def test_el_uuid_de_la_emergencia_se_guarda_en_forma_canonica(
    cliente, cabeceras, inventario_disponible
):
    # Bonita puede mandarlo en mayúsculas; liberar con la forma canónica tiene que encontrarlo.
    alta = cliente.post(
        "/recursos/compromisos",
        json={**PETICION, "emergencia_externa_id": EMERGENCIA.upper()},
        headers=cabeceras(Rol.sistema),
    )
    liberacion = cliente.post(
        f"/recursos/compromisos/{EMERGENCIA}/liberacion",
        headers=cabeceras(Rol.sistema),
    )

    assert alta.status_code == 201
    assert alta.get_json()["emergencia_externa_id"] == EMERGENCIA
    assert db.session.query(Compromiso).one().emergencia_externa_id == EMERGENCIA
    assert liberacion.get_json()["compromisos"][0]["estado"] == "LIBERADO"
