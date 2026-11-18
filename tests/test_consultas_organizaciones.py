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
from app.modulos.compromisos.servicios import (
    AporteSolicitado,
    comprometer_recursos,
    liberar_recursos,
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
    primeros_auxilios = Certificacion(nombre="Primeros auxilios", tipo=TipoItem.personal_medico)
    db.session.add_all([Certificacion(nombre="Brigada", tipo=TipoItem.rescate), primeros_auxilios])
    db.session.commit()

    respuesta = cliente.get(
        "/certificaciones?pagina=2&por_pagina=1",
        headers=cabeceras(),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "elementos": [
            {
                "id": str(primeros_auxilios.id),
                "nombre": "Primeros auxilios",
                "tipo": "personal_medico",
            }
        ],
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
            "id": str(certificacion.id),
            "nombre": "Rescate",
            "nivel_certificacion": "alta",
        }
    ]


@pytest.mark.parametrize("valor", ["6", "no-es-un-uuid"])
def test_consulta_ongs_rechaza_una_certificacion_que_no_es_uuid(
    base_de_datos, cliente, cabeceras, valor
):
    respuesta = cliente.get(f"/ongs?certificacion_id={valor}", headers=cabeceras())

    assert respuesta.status_code == 400
    error = respuesta.get_json()["error"]
    assert error["codigo"] == "SOLICITUD_INVALIDA"
    assert error["detalle"] == {"query": {"certificacion_id": ["Debe ser un UUID válido."]}}


def test_disponibilidad_expone_inventario_y_compromisos_activos(base_de_datos, cliente, cabeceras):
    organizacion = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="ONG de recursos",
        mail_contacto="recursos@example.com",
        identificador_nacional="30-12345678-9",
    )
    item = Item(
        codigo_recurso="RSR-GENERADOR-CONSULTA",
        nombre="Generador",
        tipo=TipoItem.maquinaria,
        unidad_medida="unidades",
        consumible=False,
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
        "/recursos/disponibilidad?tipo=maquinaria",
        headers=cabeceras(),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["elementos"] == [
        {
            "id": str(item.id),
            "nombre": "Generador",
            "tipo": "maquinaria",
            "unidad_medida": "unidades",
            "consumible": False,
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
        consumible=False,
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


def _ong_con_agua_y_voluntarios() -> Organizacion:
    organizacion = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="ONG mixta",
        mail_contacto="mixta@example.com",
        identificador_nacional="30-12345678-9",
        estado_habilitacion=EstadoHabilitacion.habilitada,
    )
    agua = Item(
        codigo_recurso="RSR-AGUA-MIXTA",
        nombre="Agua",
        tipo=TipoItem.agua,
        unidad_medida="litros",
        consumible=True,
    )
    voluntarios = Item(
        codigo_recurso="RSR-VOLUNTARIOS-MIXTA",
        nombre="Voluntarios",
        tipo=TipoItem.otro,
        unidad_medida="personas",
        consumible=False,
    )
    organizacion.inventario = Inventario(
        items=[
            InventarioItem(item=agua, cantidad_disponible=1000),
            InventarioItem(item=voluntarios, cantidad_disponible=40),
        ]
    )
    db.session.add(organizacion)
    db.session.commit()
    return organizacion


def _voluntarios(total: int, comprometido: int, disponible: int) -> dict:
    return {
        "nombre": "Voluntarios",
        "consumible": False,
        "total": total,
        "comprometido": comprometido,
        "disponible": disponible,
    }


def _resumen(respuesta) -> list[dict]:
    claves = ("nombre", "consumible", "total", "comprometido", "disponible")
    return [{clave: fila[clave] for clave in claves} for fila in respuesta.get_json()["elementos"]]


def test_disponibilidad_lista_solo_no_consumibles_y_sigue_un_compromiso(
    base_de_datos, cliente, cabeceras
):
    _ong_con_agua_y_voluntarios()
    comprometer_recursos(
        emergencia_externa_id="emergencia-mixta",
        nivel_gravedad="ALTA",
        aportes=[
            AporteSolicitado(
                "30-12345678-9", "RSR-VOLUNTARIOS-MIXTA", 21, TipoAsignacion.principal
            ),
            AporteSolicitado("30-12345678-9", "RSR-AGUA-MIXTA", 100, TipoAsignacion.principal),
        ],
    )

    global_ = cliente.get("/recursos/disponibilidad", headers=cabeceras())
    de_la_ong = cliente.get("/ongs/30-12345678-9/recursos/disponibilidad", headers=cabeceras())

    # El agua es consumible: no aparece, aunque tenga 100 L comprometidos.
    assert _resumen(global_) == [_voluntarios(40, 21, 19)]
    assert global_.get_json()["total"] == 1
    assert _resumen(de_la_ong) == [_voluntarios(40, 21, 19)]
    assert de_la_ong.get_json()["total"] == 1

    liberar_recursos(emergencia_externa_id="emergencia-mixta")

    despues = cliente.get("/recursos/disponibilidad", headers=cabeceras())
    assert _resumen(despues) == [_voluntarios(40, 0, 40)]


def test_disponibilidad_filtrada_por_un_tipo_consumible_queda_vacia(
    base_de_datos, cliente, cabeceras
):
    _ong_con_agua_y_voluntarios()

    respuesta = cliente.get("/recursos/disponibilidad?tipo=agua", headers=cabeceras())

    assert respuesta.status_code == 200
    assert respuesta.get_json()["elementos"] == []
    assert respuesta.get_json()["total"] == 0
