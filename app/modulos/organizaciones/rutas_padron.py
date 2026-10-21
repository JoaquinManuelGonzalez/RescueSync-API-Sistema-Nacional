"""Padrón nacional de ONGs: onboarding y estado de habilitación.

Las organizaciones que usa RescueSync ya vienen cargadas (semillas con los mismos CUIT que la
aplicación web). Estos endpoints simulan cómo el Sistema Nacional da de alta una organización
nueva y cómo la habilita o la suspende con el tiempo.
"""

from __future__ import annotations

from flask.views import MethodView

from app.core.acceso import Blueprint, Rol, actor_actual
from app.core.errores import RespuestaError
from app.modulos.organizaciones import servicios
from app.modulos.organizaciones.modelos import EstadoHabilitacion, Organizacion
from app.modulos.organizaciones.schemas_padron import (
    EJEMPLO_CUIT,
    HistorialHabilitacionRespuesta,
    OrganizacionPadron,
    PeticionAltaOrganizacion,
    PeticionCambioHabilitacion,
)

blueprint_padron = Blueprint(
    "padron",
    __name__,
    url_prefix="/ongs",
    description=(
        "Padrón nacional de ONGs: alta (onboarding), consulta por CUIT y estado de habilitación."
    ),
)

DESCRIPCION_404 = "No hay ninguna organización con ese CUIT en el padrón."

EJEMPLO_ALTA_ONG = {
    "id": 0,
    "cuit": "30-71555444-2",
    "nombre": "Red Solidaria Chascomús",
    "tipo": "ong",
    "mail_contacto": "contacto@redsolidaria.example",
    "telefono_contacto": "+54 2241 555-000",
    "estado_habilitacion": "pendiente",
    "habilitada": True,
    "motivo_estado": "string",
    "actualizada_en": "2026-10-21T21:43:42.744Z",
}

EJEMPLO_CONFLICTO_ALTA_ONG = {
    "error": {
        "codigo": "CONFLICTO_DE_ESTADO",
        "detalle": {
            "campo": "cuit",
            "cuit": "30-71555444-2",
            "estado_habilitacion": "pendiente",
        },
        "id_correlacion": "e7e3910...",
        "mensaje": "Ya existe una organización en el padrón con ese CUIT.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_HABILITACION_ONG = {
    "actualizada_en": "2026-10-26T20:00:00.00+00:00",
    "cuit": "30-99999999-5",
    "estado_habilitacion": "habilitada",
    "habilitada": True,
    "id": 0,
    "mail_contacto": "ongsolidaria@rescuesync.ej",
    "motivo_estado": "Estado inicial del padrón (datos de demostración).",
    "nombre": "La Solidaria",
    "telefono_contacto": None,
    "tipo": "ong",
}

EJEMPLO_CONFLICTO_HABILITACION = {
    "error": {
        "codigo": "CONFLICTO_DE_ESTADO",
        "detalle": {
            "estado_actual": "suspendida",
            "estado_pedido": "suspendida",
            "transiciones_permitidas": ["habilitada"],
        },
        "id_correlacion": "e7e3910...",
        "mensaje": "La organización ya está suspendida.",
        "timestamp": "2026-10-21T21:57:34.164Z",
    }
}

EJEMPLO_CAMBIO_HABILITACION = {
    "actualizada_en": "2026-10-26T20:00:00.00+00:00",
    "cuit": "30-99999999-7",
    "estado_habilitacion": "suspendida",
    "habilitada": False,
    "id": 0,
    "mail_contacto": "ongsolidaria@rescuesync.ej",
    "motivo_estado": "Certificación sanitaria vencida.",
    "nombre": "La Solidaria",
    "telefono_contacto": None,
    "tipo": "ong",
}

EJEMPLO_ERROR_400_HABILITACION = {
    "error": {
        "codigo": "SOLICITUD_INVALIDA",
        "detalle": {"json": {"estado": ["Must be one of: pendiente, habilitada, suspendida."]}},
        "id_correlacion": "e7e3910...",
        "mensaje": "La solicitud tiene campos inválidos o incompletos.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_ERROR_400_ALTA_ONG = {
    "error": {
        "codigo": "SOLICITUD_INVALIDA",
        "detalle": {"json": ["Invalid JSON body."]},
        "id_correlacion": "e7e3910...",
        "mensaje": "La solicitud tiene campos inválidos o incompletos.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_ERROR_404_ONG = {
    "error": {
        "codigo": "RECURSO_NO_ENCONTRADO",
        "detalle": {"cuit": "30-11111111-9"},
        "id_correlacion": "e7e3910...",
        "mensaje": "No hay ninguna organización con ese CUIT en el padrón nacional.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_HISTORIAL_HABILITACIONES = {
    "cuit": "30-99999999-7",
    "estado_actual": "habilitada",
    "registros": [
        {
            "caso_bonita": None,
            "cuenta": None,
            "estado_anterior": None,
            "estado_nuevo": "habilitada",
            "fecha": "2026-10-26T20:00:00.000000+00:00",
            "motivo": "Certificación sanitaria aprobada.",
            "usuario_bonita": None,
        },
        {
            "caso_bonita": None,
            "cuenta": None,
            "estado_anterior": "habilitada",
            "estado_nuevo": "suspendida",
            "fecha": "2026-11-26T20:00:00.000000+00:00",
            "motivo": "Certificación sanitaria vencida.",
            "usuario_bonita": None,
        },
        {
            "caso_bonita": None,
            "cuenta": None,
            "estado_anterior": "suspendida",
            "estado_nuevo": "habilitada",
            "fecha": "2026-12-26T20:00:00.000000+00:00",
            "motivo": "Certificación sanitaria renovada.",
            "usuario_bonita": None,
        },
    ],
}


def _ficha(organizacion: Organizacion) -> dict:
    return {
        "id": organizacion.id,
        "identificador_nacional": organizacion.identificador_nacional,
        "nombre": organizacion.nombre,
        "tipo": organizacion.tipo,
        "mail_contacto": organizacion.mail_contacto,
        "telefono_contacto": organizacion.telefono_contacto,
        "estado_habilitacion": organizacion.estado_habilitacion,
        "habilitada": organizacion.estado_habilitacion is EstadoHabilitacion.habilitada,
        "motivo_estado": servicios.ultimo_motivo(organizacion),
        "updated_at": organizacion.updated_at,
    }


@blueprint_padron.route("")
class AltaDeOrganizacion(MethodView):
    @blueprint_padron.requiere_rol(Rol.administrador)
    @blueprint_padron.arguments(
        PeticionAltaOrganizacion,
        example={
            "cuit": EJEMPLO_CUIT,
            "nombre": "Red Solidaria Chascomús",
            "tipo": "ong",
            "mail_contacto": "contacto@redsolidaria.example",
            "telefono_contacto": "+54 2241 555-000",
        },
    )
    @blueprint_padron.response(
        201,
        OrganizacionPadron,
        description="ONG registrada (pendiente).",
        example=EJEMPLO_ALTA_ONG,
    )
    @blueprint_padron.alt_response(
        409,
        schema=RespuestaError,
        example=EJEMPLO_CONFLICTO_ALTA_ONG,
        description="Ya hay una organización con ese CUIT, nombre o mail (`detalle.campo`).",
    )
    @blueprint_padron.alt_response(
        400,
        schema=RespuestaError,
        example=EJEMPLO_ERROR_400_ALTA_ONG,
        description="Formato de petición JSON inválido.",
    )
    def post(self, datos):
        """Dar de alta una ONG (onboarding)

        Registra la organización en el padrón en estado `pendiente`. No puede ofrecer recursos
        hasta que un administrador la habilite.
        """
        organizacion = servicios.registrar_organizacion(datos, actor_actual())
        return _ficha(organizacion)


@blueprint_padron.route("/<string:cuit>")
class OrganizacionPorCuit(MethodView):
    @blueprint_padron.requiere_rol(Rol.sistema, Rol.administrador)
    @blueprint_padron.response(
        200,
        OrganizacionPadron,
        example=EJEMPLO_HABILITACION_ONG,
    )
    @blueprint_padron.alt_response(
        404,
        schema=RespuestaError,
        description=DESCRIPCION_404,
        example=EJEMPLO_ERROR_404_ONG,
    )
    def get(self, cuit):
        """Consultar una ONG por CUIT

        Devuelve la ficha y el estado de habilitación. `habilitada` es true solo si la
        organización puede ofrecer y comprometer recursos.
        """
        return _ficha(servicios.obtener_por_cuit(cuit))


@blueprint_padron.route("/<string:cuit>/habilitacion")
class Habilitacion(MethodView):
    @blueprint_padron.requiere_rol(Rol.administrador)
    @blueprint_padron.arguments(
        PeticionCambioHabilitacion,
        example={"estado": "suspendida", "motivo": "Certificación sanitaria vencida."},
    )
    @blueprint_padron.response(
        200,
        OrganizacionPadron,
        example=EJEMPLO_CAMBIO_HABILITACION,
    )
    @blueprint_padron.alt_response(
        404,
        schema=RespuestaError,
        description=DESCRIPCION_404,
        example=EJEMPLO_ERROR_404_ONG,
    )
    @blueprint_padron.alt_response(
        400,
        schema=RespuestaError,
        example=EJEMPLO_ERROR_400_HABILITACION,
    )
    @blueprint_padron.alt_response(
        409,
        schema=RespuestaError,
        description="La transición no está permitida desde el estado actual.",
        example=EJEMPLO_CONFLICTO_HABILITACION,
    )
    def patch(self, datos, cuit):
        """Cambiar el estado de habilitación

        Transiciones permitidas: `pendiente` → `habilitada` o `suspendida`, `habilitada` →
        `suspendida` y `suspendida` → `habilitada`. Suspender exige un motivo. Cada cambio queda
        en el historial.
        """
        organizacion = servicios.cambiar_estado_habilitacion(
            cuit, datos["estado"], datos.get("motivo"), actor_actual()
        )
        return _ficha(organizacion)


@blueprint_padron.route("/<string:cuit>/habilitacion/historial")
class HistorialDeHabilitacion(MethodView):
    @blueprint_padron.requiere_rol(Rol.sistema, Rol.administrador)
    @blueprint_padron.response(
        200,
        HistorialHabilitacionRespuesta,
        example=EJEMPLO_HISTORIAL_HABILITACIONES,
    )
    @blueprint_padron.alt_response(
        404,
        schema=RespuestaError,
        description=DESCRIPCION_404,
        example=EJEMPLO_ERROR_404_ONG,
    )
    def get(self, cuit):
        """Ver el historial de habilitación

        Lista los cambios de estado de la organización, del más viejo al más nuevo, con quién
        hizo cada uno.
        """
        organizacion = servicios.obtener_por_cuit(cuit)
        return {
            "cuit": organizacion.identificador_nacional,
            "estado_actual": organizacion.estado_habilitacion,
            "registros": organizacion.historial_habilitacion,
        }
