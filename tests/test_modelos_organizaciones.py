from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensiones import db
from app.modulos.organizaciones.modelos import (
    Certificacion,
    Inventario,
    InventarioItem,
    Item,
    Organizacion,
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
                cantidad_total=1000,
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
        certificacion.organizacion is organizacion
        for certificacion in organizacion.certificaciones
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


@pytest.mark.parametrize(
    ("cantidad_total", "cantidad_disponible"),
    [(-1, 0), (5, -1), (5, 6)],
)
def test_inventario_rechaza_cantidades_invalidas(
    base_de_datos,
    cantidad_total,
    cantidad_disponible,
):
    organizacion = Organizacion(
        nombre="Rescate Solidario",
        email_contacto="contacto@rescate.example",
        inventario=Inventario(
            items=[
                InventarioItem(
                    item=Item(
                        nombre="Agua potable",
                        tipo=TipoItem.agua,
                        unidad_medida="litros",
                    ),
                    cantidad_total=cantidad_total,
                    cantidad_disponible=cantidad_disponible,
                )
            ]
        ),
    )
    db.session.add(organizacion)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()
