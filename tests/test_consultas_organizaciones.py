from datetime import UTC, datetime

import pytest

from app.extensiones import db
from app.modulos.compromisos.modelos import (
    Compromiso,
    CompromisoItem,
    EstadoCompromiso,
    NivelGravedad,
    TipoAsignacion,
)
from app.modulos.organizaciones.modelos import (
    Certificacion,
    EstadoHabilitacion,
    Inventario,
    InventarioItem,
    Item,
    NivelCertificacion,
    Organizacion,
    OrganizacionCertificacion,
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


def test_consulta_certificaciones_admite_paginacion(base_de_datos, cliente, cabeceras):
    db.session.add_all(
        [
            Certificacion(nombre="Brigada", tipo=TipoItem.rescate),
            Certificacion(nombre="Primeros auxilios", tipo=TipoItem.personal_medico),
        ]
    )
    db.session.commit()

    respuesta = cliente.get(
        "/certificaciones?pagina=2&por_pagina=1",
        headers=cabeceras(),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "elementos": [{"id": 2, "nombre": "Primeros auxilios", "tipo": "personal_medico"}],
        "pagina": 2,
        "por_pagina": 1,
        "total": 2,
    }


def test_consulta_ongs_filtra_por_certificacion_y_nivel(base_de_datos, cliente, cabeceras):
    certificacion = Certificacion(nombre="Rescate", tipo=TipoItem.rescate)
    habilitada = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="ONG habilitada",
        mail_contacto="habilitada@example.com",
        identificador_nacional="30-12345678-9",
        estado_habilitacion=EstadoHabilitacion.habilitada,
        certificaciones=[
            OrganizacionCertificacion(
                certificacion=certificacion,
                nivel_riesgo_permitido=NivelCertificacion.alta,
                fecha_emision=datetime.now(UTC),
            )
        ],
    )
    no_habilitada = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="ONG suspendida",
        mail_contacto="inactiva@example.com",
        estado_habilitacion=EstadoHabilitacion.suspendida,
    )
    db.session.add_all([habilitada, no_habilitada])
    db.session.commit()

    respuesta = cliente.get(
        f"/ongs?certificacion_id={certificacion.id}&nivel_certificacion=alta",
        headers=cabeceras(),
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["total"] == 1
    assert cuerpo["elementos"][0]["nombre"] == "ONG habilitada"
    assert cuerpo["elementos"][0]["cuit"] == "30-12345678-9"
    assert cuerpo["elementos"][0]["certificaciones"] == [
        {
            "id": certificacion.id,
            "nombre": "Rescate",
            "nivel_certificacion": "alta",
        }
    ]


def test_disponibilidad_expone_inventario_y_compromisos_activos(base_de_datos, cliente, cabeceras):
    organizacion = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="ONG de recursos",
        mail_contacto="recursos@example.com",
        identificador_nacional="30-12345678-9",
    )
    item = Item(
        codigo_recurso="RSR-AGUA-CONSULTA",
        nombre="Agua",
        tipo=TipoItem.agua,
        unidad_medida="litros",
    )
    inventario_item = InventarioItem(cantidad_disponible=7, item=item)
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

    respuesta = cliente.get(
        "/recursos/disponibilidad?tipo=agua",
        headers=cabeceras(),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["elementos"] == [
        {
            "id": item.id,
            "nombre": "Agua",
            "tipo": "agua",
            "unidad_medida": "litros",
            "consumible": True,
            "total": 10,
            "comprometido": 3,
            "disponible": 7,
        }
    ]


def test_disponibilidad_de_una_organizacion_filtra_sus_recursos(base_de_datos, cliente, cabeceras):
    organizacion = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="ONG específica",
        mail_contacto="especifica@example.com",
        identificador_nacional="30-12345678-9",
    )
    otro_organizacion = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="Otra ONG",
        mail_contacto="otra@example.com",
        identificador_nacional="30-98765432-1",
    )
    item = Item(
        codigo_recurso="RSR-GENERADOR-ESP",
        nombre="Generador",
        tipo=TipoItem.maquinaria,
        unidad_medida="unidades",
    )
    organizacion.inventario = Inventario(items=[InventarioItem(cantidad_disponible=4, item=item)])
    otro_item = Item(
        codigo_recurso="RSR-AGUA-OTRA",
        nombre="Agua de otra ONG",
        tipo=TipoItem.agua,
        unidad_medida="litros",
    )
    otro_organizacion.inventario = Inventario(
        items=[InventarioItem(cantidad_disponible=20, item=otro_item)]
    )
    db.session.add_all([organizacion, otro_organizacion])
    db.session.commit()

    respuesta = cliente.get(
        "/ongs/30-12345678-9/recursos/disponibilidad?tipo=maquinaria",
        headers=cabeceras(),
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["total"] == 1
    assert cuerpo["elementos"][0]["nombre"] == "Generador"
    assert cuerpo["elementos"][0]["total"] == 4
    assert cuerpo["elementos"][0]["disponible"] == 4


def test_disponibilidad_de_organizacion_inexistente_responde_404(base_de_datos, cliente, cabeceras):
    respuesta = cliente.get(
        "/ongs/30-11111111-1/recursos/disponibilidad",
        headers=cabeceras(),
    )

    assert respuesta.status_code == 404
