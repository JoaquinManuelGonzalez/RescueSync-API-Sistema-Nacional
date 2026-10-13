"""Endpoints de consulta del catálogo nacional."""

from __future__ import annotations

from flask.views import MethodView
from flask_smorest import Blueprint
from sqlalchemy import func, select

from app.extensiones import db
from app.modulos.organizaciones.modelos import (
    Certificacion,
    Compromiso,
    CompromisoItem,
    EstadoCompromiso,
    InventarioItem,
    Item,
    Organizacion,
    OrganizacionCertificacion,
    TipoOrganizacion,
)
from app.modulos.organizaciones.schemas import (
    CatalogoCertificacionesSchema,
    ConsultaDisponibilidadQuerySchema,
    ConsultaOrganizacionesQuerySchema,
    DisponibilidadPaginadaSchema,
    OrganizacionesPaginadasSchema,
    PaginacionQuerySchema,
)

blueprint_organizaciones = Blueprint(
    "organizaciones",
    __name__,
    description="Consultas sobre organizaciones, certificaciones y recursos.",
)


def _datos_paginados(elementos: list, pagina: int, por_pagina: int, total: int) -> dict:
    return {
        "elementos": elementos,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total": total,
    }


@blueprint_organizaciones.route("/certificaciones")
class CatalogoCertificaciones(MethodView):
    @blueprint_organizaciones.arguments(PaginacionQuerySchema, location="query")
    @blueprint_organizaciones.response(200, CatalogoCertificacionesSchema)
    def get(self, args):
        """Consultar el catálogo de certificaciones."""
        pagina = args["pagina"]
        por_pagina = args["por_pagina"]
        total = db.session.scalar(select(func.count()).select_from(Certificacion)) or 0
        certificaciones = db.session.scalars(
            select(Certificacion)
            .order_by(Certificacion.nombre, Certificacion.id)
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        ).all()
        elementos = [
            {
                "id": certificacion.id,
                "nombre": certificacion.nombre,
                "tipo": certificacion.tipo.value,
            }
            for certificacion in certificaciones
        ]
        return _datos_paginados(elementos, pagina, por_pagina, total)


@blueprint_organizaciones.route("/ongs")
class OrganizacionesHabilitadas(MethodView):
    @blueprint_organizaciones.arguments(
        ConsultaOrganizacionesQuerySchema,
        location="query",
    )
    @blueprint_organizaciones.response(200, OrganizacionesPaginadasSchema)
    def get(self, args):
        """Listar ONGs habilitadas con filtros de certificación."""
        pagina = args["pagina"]
        por_pagina = args["por_pagina"]
        consulta = select(Organizacion).where(
            Organizacion.activa.is_(True),
            Organizacion.tipo == TipoOrganizacion.ong,
        )
        if args["certificacion_id"] is not None:
            consulta = consulta.where(
                Organizacion.certificaciones.any(
                    OrganizacionCertificacion.certificacion_id == args["certificacion_id"]
                )
            )
        if args["nivel_certificacion"] is not None:
            consulta = consulta.where(
                Organizacion.certificaciones.any(
                    OrganizacionCertificacion.nivel_riesgo_permitido == args["nivel_certificacion"]
                )
            )

        total = db.session.scalar(select(func.count()).select_from(consulta.subquery())) or 0
        organizaciones = db.session.scalars(
            consulta.order_by(Organizacion.nombre, Organizacion.id)
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        ).all()
        elementos = [
            {
                "id": organizacion.id,
                "nombre": organizacion.nombre,
                "mail_contacto": organizacion.mail_contacto,
                "certificaciones": [
                    {
                        "id": asignacion.certificacion.id,
                        "nombre": asignacion.certificacion.nombre,
                        "nivel_certificacion": asignacion.nivel_riesgo_permitido,
                    }
                    for asignacion in organizacion.certificaciones
                ],
            }
            for organizacion in organizaciones
        ]
        return _datos_paginados(elementos, pagina, por_pagina, total)


@blueprint_organizaciones.route("/recursos/disponibilidad")
class DisponibilidadGlobal(MethodView):
    @blueprint_organizaciones.arguments(
        ConsultaDisponibilidadQuerySchema,
        location="query",
    )
    @blueprint_organizaciones.response(200, DisponibilidadPaginadaSchema)
    def get(self, args):
        """Consultar la disponibilidad global de recursos."""
        pagina = args["pagina"]
        por_pagina = args["por_pagina"]
        total_subconsulta = (
            select(
                InventarioItem.item_id,
                func.sum(InventarioItem.cantidad_disponible).label("total"),
            )
            .group_by(InventarioItem.item_id)
            .subquery()
        )
        comprometido_subconsulta = (
            select(
                InventarioItem.item_id,
                func.sum(CompromisoItem.cantidad_comprometida).label("comprometido"),
            )
            .join(CompromisoItem, CompromisoItem.inventario_item_id == InventarioItem.id)
            .join(
                Compromiso,
                (Compromiso.id == CompromisoItem.compromiso_id)
                & (Compromiso.estado == EstadoCompromiso.comprometido),
            )
            .group_by(InventarioItem.item_id)
            .subquery()
        )
        consulta = (
            select(
                Item.id,
                Item.nombre,
                Item.tipo,
                Item.unidad_medida,
                total_subconsulta.c.total,
                func.coalesce(comprometido_subconsulta.c.comprometido, 0).label("comprometido"),
            )
            .join(total_subconsulta, total_subconsulta.c.item_id == Item.id)
            .outerjoin(
                comprometido_subconsulta,
                comprometido_subconsulta.c.item_id == Item.id,
            )
        )
        if args["tipo"] is not None:
            consulta = consulta.where(Item.tipo == args["tipo"])

        total = (
            db.session.scalar(
                select(func.count()).select_from(
                    select(Item.id)
                    .join(InventarioItem, InventarioItem.item_id == Item.id)
                    .where(args["tipo"] is None or Item.tipo == args["tipo"])
                    .group_by(Item.id)
                    .subquery()
                )
            )
            or 0
        )
        filas = db.session.execute(
            consulta.order_by(Item.nombre, Item.id)
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        ).all()
        elementos = [
            {
                "id": fila.id,
                "nombre": fila.nombre,
                "tipo": fila.tipo.value,
                "unidad_medida": fila.unidad_medida,
                "total": fila.total,
                "comprometido": fila.comprometido,
                "disponible": max(fila.total - fila.comprometido, 0),
            }
            for fila in filas
        ]
        return _datos_paginados(elementos, pagina, por_pagina, total)
