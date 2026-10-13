from datetime import UTC, datetime

import pytest

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


def test_consulta_certificaciones_admite_paginacion(base_de_datos, cliente):
    db.session.add_all(
        [
            Certificacion(nombre="Brigada", tipo=TipoItem.rescate),
            Certificacion(nombre="Primeros auxilios", tipo=TipoItem.personal_medico),
        ]
    )
    db.session.commit()

    respuesta = cliente.get("/certificaciones?pagina=2&por_pagina=1")

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "elementos": [{"id": 2, "nombre": "Primeros auxilios", "tipo": "personal_medico"}],
        "pagina": 2,
        "por_pagina": 1,
        "total": 2,
    }


def test_consulta_ongs_filtra_por_certificacion_y_nivel(base_de_datos, cliente):
    certificacion = Certificacion(nombre="Rescate", tipo=TipoItem.rescate)
    habilitada = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="ONG habilitada",
        mail_contacto="habilitada@example.com",
        password_hash="hash",
        certificaciones=[
            OrganizacionCertificacion(
                certificacion=certificacion,
                nivel_riesgo_permitido="ALTO",
                fecha_emision=datetime.now(UTC),
            )
        ],
    )
    no_habilitada = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="ONG inactiva",
        mail_contacto="inactiva@example.com",
        password_hash="hash",
        activa=False,
    )
    db.session.add_all([habilitada, no_habilitada])
    db.session.commit()

    respuesta = cliente.get(f"/ongs?certificacion_id={certificacion.id}&nivel_certificacion=ALTO")

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["total"] == 1
    assert cuerpo["elementos"][0]["nombre"] == "ONG habilitada"
    assert cuerpo["elementos"][0]["certificaciones"] == [
        {
            "id": certificacion.id,
            "nombre": "Rescate",
            "nivel_certificacion": "ALTO",
        }
    ]


def test_disponibilidad_descuenta_solo_compromisos_activos(base_de_datos, cliente):
    organizacion = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="ONG de recursos",
        mail_contacto="recursos@example.com",
        password_hash="hash",
    )
    item = Item(nombre="Agua", tipo=TipoItem.agua, unidad_medida="litros")
    inventario_item = InventarioItem(cantidad_disponible=10, item=item)
    organizacion.inventario = Inventario(items=[inventario_item])
    compromiso_activo = Compromiso(
        organizacion=organizacion,
        emergencia_externa_id="emergencia-activa",
        nivel_gravedad=NivelGravedad.alta,
        estado=EstadoCompromiso.comprometido,
        items=[
            CompromisoItem(
                inventario_item=inventario_item,
                cantidad_comprometida=3,
                tipo_asignacion=TipoAsignacion.principal,
            )
        ],
    )
    compromiso_liberado = Compromiso(
        organizacion=organizacion,
        emergencia_externa_id="emergencia-liberada",
        nivel_gravedad=NivelGravedad.baja,
        estado=EstadoCompromiso.liberado,
        items=[
            CompromisoItem(
                inventario_item=inventario_item,
                cantidad_comprometida=4,
                tipo_asignacion=TipoAsignacion.apoyo,
            )
        ],
    )
    db.session.add_all([organizacion, compromiso_activo, compromiso_liberado])
    db.session.commit()

    respuesta = cliente.get("/recursos/disponibilidad?tipo=agua")

    assert respuesta.status_code == 200
    assert respuesta.get_json()["elementos"] == [
        {
            "id": item.id,
            "nombre": "Agua",
            "tipo": "agua",
            "unidad_medida": "litros",
            "total": 10,
            "comprometido": 3,
            "disponible": 7,
        }
    ]
