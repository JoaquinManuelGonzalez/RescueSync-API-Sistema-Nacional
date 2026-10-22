"""Endpoints de consulta del catálogo nacional."""

from __future__ import annotations

from flask.views import MethodView
from flask_smorest.error_handler import ErrorSchema
from sqlalchemy import func, select

from app.core.acceso import Blueprint, Rol
from app.core.errores import RespuestaError
from app.extensiones import db
from app.modulos.compromisos.modelos import Compromiso, CompromisoItem, EstadoCompromiso
from app.modulos.organizaciones import servicios
from app.modulos.organizaciones.ejemplos import (
    EJEMPLO_CARGA_DE_CERTIFICACION,
    EJEMPLO_CARGA_DE_INVENTARIO,
    EJEMPLO_CATALOGO_CERTIFICACIONES,
    EJEMPLO_DISPONIBILIDAD_ONG,
    EJEMPLO_ERROR_400_CAMPOS_INVALIDOS,
    EJEMPLO_ERROR_400_CUIT,
    EJEMPLO_ERROR_400_INVALID_JSON,
    EJEMPLO_ERROR_404_ONG,
    EJEMPLO_ERROR_409_CERTIFICACION,
    EJEMPLO_ERROR_409_ITEM,
    EJEMPLO_ONGS_HABILITADAS,
    EJEMPLO_RECURSOS_DISPONIBLES,
)
from app.modulos.organizaciones.modelos import (
    Certificacion,
    EstadoHabilitacion,
    InventarioItem,
    Item,
    Organizacion,
    OrganizacionCertificacion,
    TipoOrganizacion,
)
from app.modulos.organizaciones.schemas import (
    CatalogoCertificacionesSchema,
    CertificacionCargadaSchema,
    ConsultaDisponibilidadQuerySchema,
    ConsultaOrganizacionesQuerySchema,
    DisponibilidadPaginadaSchema,
    InventarioCargadoSchema,
    OrganizacionesPaginadasSchema,
    PaginacionQuerySchema,
    PeticionCargaCertificacionSchema,
    PeticionCargaInventarioSchema,
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
    @blueprint_organizaciones.requiere_rol(
        Rol.sistema,
        Rol.administrador,
    )
    @blueprint_organizaciones.arguments(
        PaginacionQuerySchema,
        location="query",
    )
    @blueprint_organizaciones.response(
        200,
        CatalogoCertificacionesSchema,
        example=EJEMPLO_CATALOGO_CERTIFICACIONES,
        description="Muestra todas las certificaciones registradas en el Sistema Nacional "
        "(sin filtros).",
    )
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
    @blueprint_organizaciones.requiere_rol(
        Rol.sistema,
        Rol.administrador,
    )
    @blueprint_organizaciones.response(
        200,
        OrganizacionesPaginadasSchema,
        example=EJEMPLO_ONGS_HABILITADAS,
        description="Muestra todas las ONGs (con filtro por `nivel_certificacion == alto`).",
    )
    @blueprint_organizaciones.alt_response(
        400,
        schema=ErrorSchema,
        example=EJEMPLO_ERROR_400_CAMPOS_INVALIDOS,
        description="El JSON está incompleto o contiene campos inválidos.",
    )
    @blueprint_organizaciones.arguments(
        ConsultaOrganizacionesQuerySchema,
        location="query",
    )
    def get(self, args):
        """Listar ONGs habilitadas con filtros de certificación."""
        pagina = args["pagina"]
        por_pagina = args["por_pagina"]
        consulta = select(Organizacion).where(
            Organizacion.estado_habilitacion == EstadoHabilitacion.habilitada,
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
                "cuit": organizacion.identificador_nacional,
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
    @blueprint_organizaciones.requiere_rol(Rol.sistema, Rol.administrador)
    @blueprint_organizaciones.arguments(
        ConsultaDisponibilidadQuerySchema,
        location="query",
    )
    @blueprint_organizaciones.response(
        200,
        DisponibilidadPaginadaSchema,
        example=EJEMPLO_RECURSOS_DISPONIBLES,
        description="Sin aplicar filtro, muestra todos los recursos disponibles de todas las ONGs.",
    )
    def get(self, args):
        """Consultar la disponibilidad global de recursos con filtro por tipo."""
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
                Item.consumible,
                (
                    total_subconsulta.c.total
                    + func.coalesce(comprometido_subconsulta.c.comprometido, 0)
                ).label("total"),
                total_subconsulta.c.total.label("disponible"),
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
                "consumible": fila.consumible,
                "total": fila.total,
                "comprometido": fila.comprometido,
                "disponible": fila.disponible,
            }
            for fila in filas
        ]
        return _datos_paginados(elementos, pagina, por_pagina, total)


@blueprint_organizaciones.route("/ongs/<string:cuit>/recursos/disponibilidad")
class DisponibilidadDeOrganizacion(MethodView):
    @blueprint_organizaciones.requiere_rol(Rol.sistema, Rol.administrador)
    @blueprint_organizaciones.arguments(ConsultaDisponibilidadQuerySchema, location="query")
    @blueprint_organizaciones.response(
        200,
        DisponibilidadPaginadaSchema,
        example=EJEMPLO_DISPONIBILIDAD_ONG,
        description="Sin filtro por tipo, muestra todos los recursos disponibles de una ONG.",
    )
    @blueprint_organizaciones.alt_response(
        404,
        schema=RespuestaError,
        example=EJEMPLO_ERROR_404_ONG,
        description="No existe una organización o un código de recurso indicado.",
    )
    @blueprint_organizaciones.alt_response(
        400,
        schema=RespuestaError,
        example=EJEMPLO_ERROR_400_CUIT,
    )
    def get(self, args, cuit):
        """Consultar la disponibilidad de recursos de una organización con filtro por tipo."""
        organizacion = servicios.obtener_por_cuit(cuit)
        pagina = args["pagina"]
        por_pagina = args["por_pagina"]
        total_subconsulta = (
            select(
                InventarioItem.item_id,
                func.sum(InventarioItem.cantidad_disponible).label("total"),
            )
            .where(InventarioItem.inventario.has(organizacion_id=organizacion.id))
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
            .where(Compromiso.organizacion_id == organizacion.id)
            .group_by(InventarioItem.item_id)
            .subquery()
        )
        consulta = (
            select(
                Item.id,
                Item.nombre,
                Item.tipo,
                Item.unidad_medida,
                Item.consumible,
                (
                    total_subconsulta.c.total
                    + func.coalesce(comprometido_subconsulta.c.comprometido, 0)
                ).label("total"),
                total_subconsulta.c.total.label("disponible"),
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
            db.session.scalar(select(func.count()).select_from(consulta.order_by(None).subquery()))
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
                "consumible": fila.consumible,
                "total": fila.total,
                "comprometido": fila.comprometido,
                "disponible": fila.disponible,
            }
            for fila in filas
        ]
        return _datos_paginados(elementos, pagina, por_pagina, total)


@blueprint_organizaciones.route("/ongs/<string:cuit>/inventario")
class CargaDeInventario(MethodView):
    @blueprint_organizaciones.requiere_rol(Rol.administrador)
    @blueprint_organizaciones.arguments(PeticionCargaInventarioSchema)
    @blueprint_organizaciones.response(
        201,
        InventarioCargadoSchema,
        example=EJEMPLO_CARGA_DE_INVENTARIO,
        description="Cargar un item que la ONG no posea en su inventario.",
    )
    @blueprint_organizaciones.alt_response(
        404,
        schema=RespuestaError,
        example=EJEMPLO_ERROR_404_ONG,
        description="No existe una organización o un código de recurso indicado.",
    )
    @blueprint_organizaciones.alt_response(
        409,
        schema=RespuestaError,
        example=EJEMPLO_ERROR_409_ITEM,
        description="El recurso ingresado ya existe en el inventario.",
    )
    @blueprint_organizaciones.alt_response(
        400,
        schema=ErrorSchema,
        example=EJEMPLO_ERROR_400_INVALID_JSON,
        description="El JSON está incompleto o contiene campos inválidos.",
    )
    def post(self, datos, cuit):
        """Cargar un ítem y su cantidad disponible en el inventario de una ONG."""
        registro = servicios.cargar_item(cuit, datos["item_id"], datos["cantidad_disponible"])
        return {
            "id": registro.id,
            "item_id": registro.item_id,
            "item_nombre": registro.item.nombre,
            "cantidad_disponible": registro.cantidad_disponible,
        }


@blueprint_organizaciones.route("/ongs/<string:cuit>/certificaciones")
class CargaDeCertificacion(MethodView):
    @blueprint_organizaciones.requiere_rol(Rol.administrador)
    @blueprint_organizaciones.arguments(PeticionCargaCertificacionSchema)
    @blueprint_organizaciones.response(
        201,
        CertificacionCargadaSchema,
        example=EJEMPLO_CARGA_DE_CERTIFICACION,
        description="Cargar una certificación que la ONG no posea.",
    )
    @blueprint_organizaciones.alt_response(
        404,
        schema=RespuestaError,
        example=EJEMPLO_ERROR_404_ONG,
        description="No existe una organización o un código de recurso indicado.",
    )
    @blueprint_organizaciones.alt_response(
        409,
        schema=RespuestaError,
        example=EJEMPLO_ERROR_409_CERTIFICACION,
        description="La organización ya tiene cargada esa certificación.",
    )
    @blueprint_organizaciones.alt_response(
        400,
        schema=RespuestaError,
        example=EJEMPLO_ERROR_400_INVALID_JSON,
        description="El JSON está incompleto o contiene campos inválidos.",
    )
    def post(self, datos, cuit):
        """Asignar una certificación y su nivel a una ONG."""
        asignacion = servicios.cargar_certificacion(
            cuit,
            datos["certificacion_id"],
            datos["nivel_certificacion"],
        )
        return {
            "id": asignacion.id,
            "certificacion_id": asignacion.certificacion_id,
            "certificacion_nombre": asignacion.certificacion.nombre,
            "nivel_certificacion": asignacion.nivel_riesgo_permitido,
            "fecha_emision": asignacion.fecha_emision,
        }
