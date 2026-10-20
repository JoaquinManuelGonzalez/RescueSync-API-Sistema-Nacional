from __future__ import annotations

from datetime import UTC, datetime

from app.extensiones import db
from app.modulos.compromisos.modelos import Compromiso, TipoAsignacion
from app.modulos.evaluacion.servicios import evaluar_ofertas
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


def _organizacion(
    *,
    cuit: str,
    nombre: str,
    estado: EstadoHabilitacion = EstadoHabilitacion.habilitada,
) -> Organizacion:
    return Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre=nombre,
        mail_contacto=f"{nombre.lower().replace(' ', '.')}@example.test",
        identificador_nacional=cuit,
        estado_habilitacion=estado,
    )


def test_evaluacion_clasifica_cada_item_y_compromete_no_consumibles(base_de_datos):
    ambulancia = Item(
        codigo_recurso="RSR-AMBULANCIAS",
        nombre="Ambulancias",
        tipo=TipoItem.rescate,
        unidad_medida="unidades",
        consumible=False,
    )
    agua = Item(
        codigo_recurso="RSR-AGUA",
        nombre="Agua",
        tipo=TipoItem.agua,
        unidad_medida="litros",
        consumible=True,
    )
    cert_rescate = Certificacion(nombre="Rescate", tipo=TipoItem.rescate)
    cert_agua = Certificacion(nombre="Agua", tipo=TipoItem.agua)
    organizacion = _organizacion(cuit="30-11111111-1", nombre="ONG Rescate")
    organizacion.inventario = Inventario(
        items=[InventarioItem(item=ambulancia, cantidad_disponible=5)]
    )
    organizacion.certificaciones = [
        OrganizacionCertificacion(
            certificacion=cert_rescate,
            nivel_riesgo_permitido=NivelCertificacion.media,
            fecha_emision=datetime.now(UTC),
        ),
        OrganizacionCertificacion(
            certificacion=cert_agua,
            nivel_riesgo_permitido=NivelCertificacion.alta,
            fecha_emision=datetime.now(UTC),
        ),
    ]
    db.session.add_all([ambulancia, agua, cert_rescate, cert_agua, organizacion])
    db.session.commit()

    resultado = evaluar_ofertas(
        emergencia_id=14,
        nivel_gravedad="ALTA",
        ofertas=[
            {
                "fecha_creacion": datetime.now(UTC),
                "oferta_id": 7,
                "organizaciones": [],
                "version": 2,
                "items": [
                    {
                        "aportes": [
                            {
                                "cantidad": 5,
                                "identificador_nacional": organizacion.identificador_nacional,
                                "organizacion_id": 999,
                            }
                        ],
                        "cantidad_total": 5,
                        "codigo_recurso": ambulancia.codigo_recurso,
                        "lote_item_id": 10,
                        "tipo_recurso": "rescate",
                        "unidad": "unidades",
                    },
                    {
                        "aportes": [
                            {
                                "cantidad": 100,
                                "identificador_nacional": organizacion.identificador_nacional,
                                "organizacion_id": 999,
                            }
                        ],
                        "cantidad_total": 100,
                        "codigo_recurso": agua.codigo_recurso,
                        "lote_item_id": 11,
                        "tipo_recurso": "agua",
                        "unidad": "litros",
                    },
                ],
            }
        ],
    )

    items = resultado["ofertas"][0]["items"]
    assert all("clasificacion" not in item for item in items)
    assert all("motivo" not in item for item in items)
    assert [item["aportes"][0]["clasificacion"] for item in items] == ["apoyo", "principal"]
    assert "compromisos_registrados" not in resultado
    assert "version" not in resultado["ofertas"][0]
    assert "perfil_competencia" not in resultado["ofertas"][0]
    assert items[0]["aportes"][0]["compromiso_registrado"] is True
    assert db.session.query(Compromiso).count() == 1
    assert db.session.query(Compromiso).one().items[0].tipo_asignacion is TipoAsignacion.apoyo


def test_evaluacion_rechaza_sin_certificacion_y_por_stock_insuficiente(base_de_datos):
    ambulancia = Item(
        codigo_recurso="RSR-AMBULANCIAS",
        nombre="Ambulancias",
        tipo=TipoItem.rescate,
        unidad_medida="unidades",
        consumible=False,
    )
    certificacion = Certificacion(nombre="Rescate", tipo=TipoItem.rescate)
    organizacion = _organizacion(cuit="30-22222222-2", nombre="ONG Sin Stock")
    organizacion.inventario = Inventario(
        items=[InventarioItem(item=ambulancia, cantidad_disponible=1)]
    )
    organizacion.certificaciones = [
        OrganizacionCertificacion(
            certificacion=certificacion,
            nivel_riesgo_permitido=NivelCertificacion.baja,
            fecha_emision=datetime.now(UTC),
        )
    ]
    db.session.add_all([ambulancia, certificacion, organizacion])
    db.session.commit()

    resultado = evaluar_ofertas(
        emergencia_id=15,
        nivel_gravedad="BAJA",
        ofertas=[
            {
                "fecha_creacion": datetime.now(UTC),
                "oferta_id": 8,
                "organizaciones": [],
                "version": 1,
                "items": [
                    {
                        "aportes": [
                            {
                                "cantidad": 2,
                                "identificador_nacional": organizacion.identificador_nacional,
                                "organizacion_id": 998,
                            }
                        ],
                        "cantidad_total": 2,
                        "codigo_recurso": ambulancia.codigo_recurso,
                        "lote_item_id": 12,
                        "tipo_recurso": "rescate",
                        "unidad": "unidades",
                    }
                ],
            }
        ],
    )

    item = resultado["ofertas"][0]["items"][0]["aportes"][0]
    assert item["clasificacion"] == "rechazada"
    assert "disponibilidad" in item["motivo"]
