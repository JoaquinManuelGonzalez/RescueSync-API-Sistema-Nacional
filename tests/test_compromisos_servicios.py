from __future__ import annotations

import pytest

from app.core.errores import ConflictoDeEstado, RecursoNoEncontrado
from app.extensiones import db
from app.modulos.compromisos.modelos import Compromiso, EstadoCompromiso, TipoAsignacion
from app.modulos.compromisos.servicios import (
    AporteSolicitado,
    DisponibilidadInsuficiente,
    comprometer_recursos,
    informar_finalizacion_ong,
    liberar_recursos,
)
from app.modulos.organizaciones.modelos import (
    Inventario,
    InventarioItem,
    Item,
    Organizacion,
    TipoItem,
    TipoOrganizacion,
)


@pytest.fixture
def base_de_datos(app):
    with app.app_context():
        db.create_all()
        item = Item(
            codigo_recurso="RSR-ENFERMEROS",
            nombre="Enfermeros",
            tipo=TipoItem.personal_medico,
            unidad_medida="personas",
        )
        organizaciones = []
        for numero, (identificador, cantidad) in enumerate(
            [("30-11111111-1", 10), ("30-22222222-2", 8)],
            start=1,
        ):
            inventario = Inventario(
                items=[
                    InventarioItem(
                        item=item,
                        cantidad_disponible=cantidad,
                    )
                ]
            )
            organizacion = Organizacion(
                tipo=TipoOrganizacion.ong,
                nombre=f"ONG {numero}",
                mail_contacto=f"ong{numero}@example.test",
                identificador_nacional=identificador,
                inventario=inventario,
            )
            organizaciones.append(organizacion)
        db.session.add_all([item, *organizaciones])
        db.session.commit()
        yield
        db.session.remove()
        db.drop_all()


def aportes_validos() -> list[AporteSolicitado]:
    return [
        AporteSolicitado(
            identificador_nacional="30-11111111-1",
            codigo_recurso="RSR-ENFERMEROS",
            cantidad=4,
            tipo_asignacion=TipoAsignacion.principal,
        ),
        AporteSolicitado(
            identificador_nacional="30-22222222-2",
            codigo_recurso="RSR-ENFERMEROS",
            cantidad=3,
            tipo_asignacion=TipoAsignacion.apoyo,
        ),
    ]


def test_comprometer_recursos_descuenta_stock_y_registra_aportes(base_de_datos):
    resultado = comprometer_recursos(
        emergencia_externa_id="13",
        nivel_gravedad="MEDIA",
        aportes=aportes_validos(),
    )

    assert resultado.repetido is False
    assert len(resultado.compromisos) == 2
    assert {compromiso.nivel_gravedad.value for compromiso in resultado.compromisos} == {"MEDIO"}
    assert sum(len(compromiso.items) for compromiso in resultado.compromisos) == 2

    inventarios = db.session.query(InventarioItem).order_by(InventarioItem.id).all()
    assert [fila.cantidad_disponible for fila in inventarios] == [6, 5]


def test_reintento_identico_es_idempotente(base_de_datos):
    primera = comprometer_recursos(
        emergencia_externa_id="13",
        nivel_gravedad="MEDIA",
        aportes=aportes_validos(),
    )
    segunda = comprometer_recursos(
        emergencia_externa_id="13",
        nivel_gravedad="MEDIA",
        aportes=aportes_validos(),
    )

    assert primera.repetido is False
    assert segunda.repetido is True
    assert {compromiso.id for compromiso in primera.compromisos} == {
        compromiso.id for compromiso in segunda.compromisos
    }
    assert db.session.query(Compromiso).count() == 2
    cantidades = [
        fila.cantidad_disponible
        for fila in db.session.query(InventarioItem).order_by(InventarioItem.id)
    ]
    assert cantidades == [
        6,
        5,
    ]


def test_reintento_con_payload_distinto_se_rechaza(base_de_datos):
    comprometer_recursos(
        emergencia_externa_id="13",
        nivel_gravedad="MEDIA",
        aportes=aportes_validos(),
    )
    aportes = aportes_validos()
    aportes[0] = AporteSolicitado(
        identificador_nacional="30-11111111-1",
        codigo_recurso="RSR-ENFERMEROS",
        cantidad=5,
        tipo_asignacion=TipoAsignacion.principal,
    )

    with pytest.raises(ConflictoDeEstado):
        comprometer_recursos(
            emergencia_externa_id="13",
            nivel_gravedad="MEDIA",
            aportes=aportes,
        )


def test_stock_insuficiente_revierte_toda_la_adjudicacion(base_de_datos):
    aportes = aportes_validos()
    aportes[0] = AporteSolicitado(
        identificador_nacional="30-11111111-1",
        codigo_recurso="RSR-ENFERMEROS",
        cantidad=11,
        tipo_asignacion=TipoAsignacion.principal,
    )

    with pytest.raises(DisponibilidadInsuficiente):
        comprometer_recursos(
            emergencia_externa_id="13",
            nivel_gravedad="MEDIA",
            aportes=aportes,
        )

    assert db.session.query(Compromiso).count() == 0
    cantidades = [
        fila.cantidad_disponible
        for fila in db.session.query(InventarioItem).order_by(InventarioItem.id)
    ]
    assert cantidades == [
        10,
        8,
    ]


def test_liberar_recursos_devuelve_solo_los_no_consumibles(base_de_datos):
    item_reutilizable = Item(
        codigo_recurso="RSR-CAMILLAS",
        nombre="Camillas",
        tipo=TipoItem.maquinaria,
        unidad_medida="unidades",
        consumible=False,
    )
    organizaciones = db.session.query(Organizacion).order_by(Organizacion.id).all()
    for organizacion, cantidad in zip(organizaciones, (5, 4), strict=True):
        organizacion.inventario.items.append(
            InventarioItem(item=item_reutilizable, cantidad_disponible=cantidad)
        )
    db.session.add(item_reutilizable)
    db.session.commit()

    aportes = [
        AporteSolicitado(
            identificador_nacional="30-11111111-1",
            codigo_recurso="RSR-ENFERMEROS",
            cantidad=4,
            tipo_asignacion=TipoAsignacion.principal,
        ),
        AporteSolicitado(
            identificador_nacional="30-11111111-1",
            codigo_recurso="RSR-CAMILLAS",
            cantidad=2,
            tipo_asignacion=TipoAsignacion.principal,
        ),
    ]
    comprometer_recursos(
        emergencia_externa_id="13",
        nivel_gravedad="MEDIA",
        aportes=aportes,
    )

    resultado = liberar_recursos(emergencia_externa_id="13")

    assert resultado.repetido is False
    assert len(resultado.compromisos) == 1
    assert resultado.compromisos[0].estado is EstadoCompromiso.liberado
    assert resultado.compromisos[0].fecha_liberacion is not None
    cantidades = {
        (
            fila.inventario.organizacion.identificador_nacional,
            fila.item.codigo_recurso,
        ): fila.cantidad_disponible
        for fila in db.session.query(InventarioItem).all()
    }
    assert cantidades == {
        ("30-11111111-1", "RSR-ENFERMEROS"): 6,
        ("30-11111111-1", "RSR-CAMILLAS"): 5,
        ("30-22222222-2", "RSR-ENFERMEROS"): 8,
        ("30-22222222-2", "RSR-CAMILLAS"): 4,
    }

    db.session.commit()
    reintento = liberar_recursos(emergencia_externa_id="13")

    assert reintento.repetido is True
    assert {
        (
            fila.inventario.organizacion.identificador_nacional,
            fila.item.codigo_recurso,
        ): fila.cantidad_disponible
        for fila in db.session.query(InventarioItem).all()
    } == cantidades


def test_liberar_recursos_falla_si_no_hay_compromisos(base_de_datos):
    with pytest.raises(RecursoNoEncontrado):
        liberar_recursos(emergencia_externa_id="inexistente")


def test_finalizacion_de_una_ong_no_cierra_el_proyecto_antes_que_las_demas(base_de_datos):
    comprometer_recursos(
        emergencia_externa_id="13",
        nivel_gravedad="MEDIA",
        aportes=aportes_validos(),
    )

    resultado = informar_finalizacion_ong(
        emergencia_externa_id="13",
        identificador_nacional="30-11111111-1",
    )

    assert resultado.proyecto_cerrado is False
    assert resultado.organizaciones_finalizadas == 1
    assert resultado.organizaciones_participantes == 2
    compromisos = db.session.query(Compromiso).order_by(Compromiso.id).all()
    assert compromisos[0].fecha_finalizacion_ong is not None
    assert compromisos[0].estado is EstadoCompromiso.comprometido
    assert compromisos[0].fecha_cierre_proyecto is None
    assert compromisos[1].fecha_finalizacion_ong is None
    assert [fila.cantidad_disponible for fila in db.session.query(InventarioItem)] == [6, 5]


def test_ultima_finalizacion_cierra_proyecto_y_devuelve_solo_no_consumibles(base_de_datos):
    item_reutilizable = Item(
        codigo_recurso="RSR-CAMILLAS",
        nombre="Camillas",
        tipo=TipoItem.maquinaria,
        unidad_medida="unidades",
        consumible=False,
    )
    for organizacion, cantidad in zip(
        db.session.query(Organizacion).order_by(Organizacion.id).all(),
        (5, 4),
        strict=True,
    ):
        organizacion.inventario.items.append(
            InventarioItem(item=item_reutilizable, cantidad_disponible=cantidad)
        )
    db.session.add(item_reutilizable)
    db.session.commit()

    aportes = aportes_validos() + [
        AporteSolicitado(
            identificador_nacional="30-11111111-1",
            codigo_recurso="RSR-CAMILLAS",
            cantidad=2,
            tipo_asignacion=TipoAsignacion.principal,
        ),
        AporteSolicitado(
            identificador_nacional="30-22222222-2",
            codigo_recurso="RSR-CAMILLAS",
            cantidad=1,
            tipo_asignacion=TipoAsignacion.apoyo,
        ),
    ]
    comprometer_recursos(
        emergencia_externa_id="13",
        nivel_gravedad="MEDIA",
        aportes=aportes,
    )
    informar_finalizacion_ong(
        emergencia_externa_id="13",
        identificador_nacional="30-11111111-1",
    )
    db.session.commit()

    resultado = informar_finalizacion_ong(
        emergencia_externa_id="13",
        identificador_nacional="30-22222222-2",
    )

    assert resultado.proyecto_cerrado is True
    assert resultado.organizaciones_finalizadas == 2
    compromisos = db.session.query(Compromiso).order_by(Compromiso.id).all()
    assert all(compromiso.estado is EstadoCompromiso.liberado for compromiso in compromisos)
    assert all(compromiso.fecha_liberacion is not None for compromiso in compromisos)
    assert all(compromiso.fecha_cierre_proyecto is not None for compromiso in compromisos)
    cantidades = {
        (
            fila.inventario.organizacion.identificador_nacional,
            fila.item.codigo_recurso,
        ): fila.cantidad_disponible
        for fila in db.session.query(InventarioItem).all()
    }
    assert cantidades == {
        ("30-11111111-1", "RSR-ENFERMEROS"): 6,
        ("30-11111111-1", "RSR-CAMILLAS"): 5,
        ("30-22222222-2", "RSR-ENFERMEROS"): 5,
        ("30-22222222-2", "RSR-CAMILLAS"): 4,
    }


def test_finalizacion_de_ong_es_idempotente(base_de_datos):
    comprometer_recursos(
        emergencia_externa_id="13",
        nivel_gravedad="MEDIA",
        aportes=aportes_validos(),
    )
    primera = informar_finalizacion_ong(
        emergencia_externa_id="13",
        identificador_nacional="30-11111111-1",
    )
    db.session.commit()

    reintento = informar_finalizacion_ong(
        emergencia_externa_id="13",
        identificador_nacional="30-11111111-1",
    )

    assert primera.repetido is False
    assert reintento.repetido is True
    assert reintento.proyecto_cerrado is False
    assert reintento.organizaciones_finalizadas == 1
    assert [fila.cantidad_disponible for fila in db.session.query(InventarioItem)] == [6, 5]


def test_finalizacion_rechaza_ong_que_no_participa(base_de_datos):
    comprometer_recursos(
        emergencia_externa_id="13",
        nivel_gravedad="MEDIA",
        aportes=aportes_validos(),
    )

    with pytest.raises(RecursoNoEncontrado):
        informar_finalizacion_ong(
            emergencia_externa_id="13",
            identificador_nacional="30-33333333-3",
        )
