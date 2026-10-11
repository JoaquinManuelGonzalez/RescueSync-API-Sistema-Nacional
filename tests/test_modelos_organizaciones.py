from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensiones import db
from app.modulos.organizaciones.modelos import (
    Certificacion,
    Compromiso,
    CompromisoItem,
    EstadoCompromiso,
    Inventario,
    InventarioItem,
    Item,
    NivelGravedad,
    Organizacion,
    TipoAsignacion,
    TipoItem,
)


@pytest.fixture
def base_de_datos(app):
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def test_organizacion_puede_tener_inventario_con_items(base_de_datos):
    organizacion = Organizacion(
        nombre="Rescate Solidario",
        email_contacto="contacto@rescate.example",
    )
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
    organizacion = Organizacion(
        nombre="Rescate Solidario",
        email_contacto="contacto@rescate.example",
        certificaciones=[
            Certificacion(nombre="ISO 9001", tipo=TipoItem.otro),
            Certificacion(nombre="IRAM 3546", tipo=TipoItem.rescate),
        ],
    )
    db.session.add(organizacion)
    db.session.commit()

    assert [certificacion.nombre for certificacion in organizacion.certificaciones] == [
        "ISO 9001",
        "IRAM 3546",
    ]
    assert all(
        certificacion.organizacion is organizacion for certificacion in organizacion.certificaciones
    )


def test_al_eliminar_una_organizacion_se_eliminan_sus_certificaciones(base_de_datos):
    organizacion = Organizacion(
        nombre="Rescate Solidario",
        email_contacto="contacto@rescate.example",
        certificaciones=[Certificacion(nombre="ISO 9001", tipo=TipoItem.otro)],
    )
    db.session.add(organizacion)
    db.session.commit()

    db.session.delete(organizacion)
    db.session.commit()

    assert db.session.query(Certificacion).count() == 0


def test_compromiso_registra_recursos_de_una_emergencia_externa(base_de_datos):
    organizacion = Organizacion(
        nombre="Rescate Solidario",
        email_contacto="contacto@rescate.example",
    )
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
        organizacion=Organizacion(
            nombre="Rescate Solidario",
            email_contacto="contacto@rescate.example",
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
