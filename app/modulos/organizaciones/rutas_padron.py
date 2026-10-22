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
from app.modulos.organizaciones.ejemplos import (
    EJEMPLO_ALTA_ONG,
    EJEMPLO_CAMBIO_HABILITACION,
    EJEMPLO_ERROR_400,
    EJEMPLO_ERROR_404_ONG,
    EJEMPLO_ERROR_409_HABILITACION,
    EJEMPLO_ERROR_409_ONG,
    EJEMPLO_HABILITACION_ONG,
    EJEMPLO_HISTORIAL_HABILITACIONES,
)
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
        example=EJEMPLO_ERROR_409_ONG,
        description="Ya hay una organización con ese CUIT, nombre o mail (`detalle.campo`).",
    )
    @blueprint_padron.alt_response(
        400,
        schema=RespuestaError,
        example=EJEMPLO_ERROR_400,
        description="El JSON está incompleto o contiene campos inválidos.",
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
        example=EJEMPLO_ERROR_400,
        description="El JSON está incompleto o contiene campos inválidos.",
    )
    @blueprint_padron.alt_response(
        409,
        schema=RespuestaError,
        description="La transición no está permitida desde el estado actual.",
        example=EJEMPLO_ERROR_409_HABILITACION,
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
