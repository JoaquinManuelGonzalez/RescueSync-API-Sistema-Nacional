from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensiones import db
from app.modulos.organizaciones.modelos import (
    Certificacion,
    Compromiso,
    CompromisoItem,
    EstadoCompromiso,
    EstadoHabilitacion,
    HistorialHabilitacion,
    Inventario,
    InventarioItem,
    Item,
    NivelCertificacion,
    NivelGravedad,
    Organizacion,
    OrganizacionCertificacion,
    TipoAsignacion,
    TipoItem,
    TipoOrganizacion,
)


@pytest.fixture
def base_de_datos(app):
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def crear_organizacion(**valores):
    datos = {
        "tipo": TipoOrganizacion.ong,
        "nombre": "Rescate Solidario",
        "mail_contacto": "contacto@rescate.example",
    }
    datos.update(valores)
    return Organizacion(**datos)


def test_organizacion_puede_tener_inventario_con_items(base_de_datos):
    organizacion = crear_organizacion()
    item = Item(
        nombre="Agua potable",
        tipo=TipoItem.agua,
        unidad_medida="litros",
    )
    organizacion.inventario = Inventario(
        items=[
            InventarioItem(
                item=item,
                cantidad_disponible=750,
            )
        ]
    )
    db.session.add(organizacion)
    db.session.commit()

    assert organizacion.inventario is not None
    assert organizacion.inventario.items[0].item.tipo is TipoItem.agua
    assert organizacion.inventario.items[0].cantidad_disponible == 750


def test_organizacion_puede_tener_multiples_certificaciones(base_de_datos):
    certificaciones = [
        Certificacion(nombre="ISO 9001", tipo=TipoItem.otro),
        Certificacion(nombre="IRAM 3546", tipo=TipoItem.rescate),
    ]
    organizacion = crear_organizacion(
        certificaciones=[
            OrganizacionCertificacion(
                certificacion=certificacion,
                nivel_riesgo_permitido=NivelCertificacion.alta,
                fecha_emision=datetime.now(UTC),
            )
            for certificacion in certificaciones
        ]
    )
    db.session.add(organizacion)
    db.session.commit()

    assert [asignacion.certificacion.nombre for asignacion in organizacion.certificaciones] == [
        "ISO 9001",
        "IRAM 3546",
    ]
    assert all(
        asignacion.organizacion is organizacion for asignacion in organizacion.certificaciones
    )


def test_al_eliminar_una_organizacion_se_eliminan_sus_certificaciones(base_de_datos):
    certificacion = Certificacion(nombre="ISO 9001", tipo=TipoItem.otro)
    organizacion = crear_organizacion(
        certificaciones=[
            OrganizacionCertificacion(
                certificacion=certificacion,
                nivel_riesgo_permitido=NivelCertificacion.alta,
                fecha_emision=datetime.now(UTC),
            )
        ]
    )
    db.session.add(organizacion)
    db.session.commit()

    db.session.delete(organizacion)
    db.session.commit()

    assert db.session.query(OrganizacionCertificacion).count() == 0
    assert db.session.query(Certificacion).count() == 1


def test_compromiso_registra_recursos_de_una_emergencia_externa(base_de_datos):
    organizacion = crear_organizacion()
    inventario_item = InventarioItem(
        item=Item(
            nombre="Agua potable",
            tipo=TipoItem.agua,
            unidad_medida="litros",
        ),
        cantidad_disponible=750,
    )
    organizacion.inventario = Inventario(items=[inventario_item])
    compromiso = Compromiso(
        organizacion=organizacion,
        emergencia_externa_id="bonita-case-123",
        nivel_gravedad=NivelGravedad.alta,
        items=[
            CompromisoItem(
                inventario_item=inventario_item,
                cantidad_comprometida=250,
                tipo_asignacion=TipoAsignacion.principal,
            )
        ],
    )
    db.session.add(compromiso)
    db.session.commit()

    assert compromiso.estado is EstadoCompromiso.comprometido
    assert compromiso.items[0].inventario_item is inventario_item
    assert compromiso.items[0].cantidad_comprometida == 250
    assert compromiso.items[0].tipo_asignacion is TipoAsignacion.principal
    assert compromiso.fecha_compromiso is not None
    assert compromiso.fecha_liberacion is None


def test_compromiso_rechaza_cantidad_no_positiva(base_de_datos):
    inventario_item = InventarioItem(
        item=Item(nombre="Agua potable", tipo=TipoItem.agua, unidad_medida="litros"),
        cantidad_disponible=1000,
    )
    compromiso = Compromiso(
        organizacion=crear_organizacion(
            inventario=Inventario(items=[inventario_item]),
        ),
        emergencia_externa_id="bonita-case-123",
        nivel_gravedad=NivelGravedad.alta,
        items=[
            CompromisoItem(
                inventario_item=inventario_item,
                cantidad_comprometida=0,
                tipo_asignacion=TipoAsignacion.apoyo,
            )
        ],
    )
    db.session.add(compromiso)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()


@pytest.mark.parametrize(
    "cantidad_disponible",
    [-1],
)
def test_inventario_rechaza_cantidades_invalidas(
    base_de_datos,
    cantidad_disponible,
):
    organizacion = crear_organizacion(
        inventario=Inventario(
            items=[
                InventarioItem(
                    item=Item(
                        nombre="Agua potable",
                        tipo=TipoItem.agua,
                        unidad_medida="litros",
                    ),
                    cantidad_disponible=cantidad_disponible,
                )
            ]
        ),
    )
    db.session.add(organizacion)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()


def test_organizacion_nueva_queda_pendiente(base_de_datos):
    organizacion = crear_organizacion()
    db.session.add(organizacion)
    db.session.commit()

    assert organizacion.estado_habilitacion is EstadoHabilitacion.pendiente


def test_al_eliminar_una_organizacion_se_elimina_su_historial(base_de_datos):
    organizacion = crear_organizacion(
        historial_habilitacion=[
            HistorialHabilitacion(estado_nuevo=EstadoHabilitacion.pendiente, motivo="Alta.")
        ]
    )
    db.session.add(organizacion)
    db.session.commit()

    db.session.delete(organizacion)
    db.session.commit()

    assert db.session.query(HistorialHabilitacion).count() == 0
