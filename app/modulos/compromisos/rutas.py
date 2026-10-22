"""Endpoints para comprometer recursos indicados por el proceso."""

from __future__ import annotations

from flask.views import MethodView

from app.core.acceso import Blueprint, Rol
from app.core.errores import RespuestaError
from app.modulos.compromisos import servicios
from app.modulos.compromisos.schemas import (
    PeticionCompromiso,
    RespuestaCompromiso,
    RespuestaFinalizacion,
    RespuestaValidacion,
)
from app.modulos.compromisos.servicios import AporteSolicitado

blueprint_compromisos = Blueprint(
    "compromisos",
    __name__,
    url_prefix="/recursos/compromisos",
    description="Compromiso de los recursos seleccionados por el proceso de emergencia.",
)

EJEMPLO_COMPROMISO = {
    "emergencia_externa_id": "emergencia-demo-01",
    "nivel_gravedad": "MEDIA",
    "aportes": [
        {
            "identificador_nacional": "30-65432198-7",
            "codigo_recurso": "RSR-PARAMEDICOS",
            "cantidad": 2,
            "tipo_asignacion": "principal",
        },
        {
            "identificador_nacional": "30-65432198-7",
            "codigo_recurso": "RSR-AGUA_POTABLE_ENVASADA",
            "cantidad": 100,
            "tipo_asignacion": "principal",
        },
    ],
}


@blueprint_compromisos.route("")
class CompromisoDeRecursos(MethodView):
    @blueprint_compromisos.requiere_rol(Rol.sistema)
    @blueprint_compromisos.arguments(PeticionCompromiso, example=EJEMPLO_COMPROMISO)
    @blueprint_compromisos.response(
        201,
        RespuestaCompromiso,
        description="Los recursos quedaron comprometidos; una repetición idéntica devuelve 200.",
    )
    @blueprint_compromisos.alt_response(
        200,
        schema=RespuestaCompromiso,
        description=(
            "La solicitud idéntica ya se había procesado; el inventario no se descuenta otra vez."
        ),
    )
    @blueprint_compromisos.alt_response(
        400,
        schema=RespuestaError,
        description="El JSON está incompleto o contiene campos inválidos.",
    )
    @blueprint_compromisos.alt_response(
        404,
        schema=RespuestaError,
        description="No existe una organización o un código de recurso indicado.",
    )
    @blueprint_compromisos.alt_response(
        409,
        schema=RespuestaError,
        description="La emergencia ya tiene compromisos distintos o en otro estado.",
    )
    @blueprint_compromisos.alt_response(
        422,
        schema=RespuestaError,
        description="El stock disponible no alcanza para completar todos los aportes.",
    )
    def post(self, datos):
        """Comprometer todos los recursos indicados, o ninguno.

        La lista ya debe venir seleccionada por el proceso. Este endpoint no adjudica ofertas
        ni evalúa competencias.
        """
        resultado = servicios.comprometer_recursos(
            emergencia_externa_id=datos["emergencia_externa_id"],
            nivel_gravedad=datos["nivel_gravedad"],
            aportes=[
                AporteSolicitado(
                    identificador_nacional=aporte["identificador_nacional"],
                    codigo_recurso=aporte["codigo_recurso"],
                    cantidad=aporte["cantidad"],
                    tipo_asignacion=aporte["tipo_asignacion"],
                )
                for aporte in datos["aportes"]
            ],
        )
        cuerpo = {
            "emergencia_externa_id": datos["emergencia_externa_id"].strip(),
            "repetido": resultado.repetido,
            "compromisos": [
                {
                    "identificador_nacional": compromiso.organizacion.identificador_nacional,
                    "nivel_gravedad": compromiso.nivel_gravedad,
                    "estado": compromiso.estado,
                    "items": [
                        {
                            "codigo_recurso": item.inventario_item.item.codigo_recurso,
                            "cantidad": item.cantidad_comprometida,
                            "tipo_asignacion": item.tipo_asignacion,
                        }
                        for item in compromiso.items
                    ],
                }
                for compromiso in resultado.compromisos
            ],
        }
        return cuerpo, 200 if resultado.repetido else 201

EJEMPLO_VALIDACION = {
    "emergencia_externa_id": "emergencia-demo-01",
    "nivel_gravedad": "MEDIA",
    "aportes": [
        {
            "identificador_nacional": "30-65432198-7",
            "codigo_recurso": "RSR-PARAMEDICOS",
            "cantidad": 2,
            "tipo_asignacion": "principal",
        },
        {
            "identificador_nacional": "30-65432198-7",
            "codigo_recurso": "RSR-AGUA_POTABLE_ENVASADA",
            "cantidad": 100,
            "tipo_asignacion": "principal",
        },
    ],
}


@blueprint_compromisos.route("/validar")
class ValidacionDeRestricciones(MethodView):
    @blueprint_compromisos.requiere_rol(Rol.sistema)
    @blueprint_compromisos.arguments(PeticionCompromiso, example=EJEMPLO_VALIDACION)
    @blueprint_compromisos.response(
        200,
        RespuestaValidacion,
        description=(
            "Resultado de la validaci\u00f3n sin efecto colateral. "
            "`valido: true` indica que el compromiso puede ejecutarse; "
            "`valido: false` incluye los motivos de fallo."
        ),
    )
    @blueprint_compromisos.alt_response(
        400,
        schema=RespuestaError,
        description="El JSON est\u00e1 incompleto o contiene campos inv\u00e1lidos.",
    )
    @blueprint_compromisos.alt_response(
        404,
        schema=RespuestaError,
        description="No existe una organizaci\u00f3n o un c\u00f3digo de recurso indicado.",
    )
    def post(self, datos):
        """Verificar si los aportes pueden comprometerse sin modificar el inventario.

        Solo valida disponibilidad en \u00edtems no consumibles. Los consumibles se aprueban
        sin verificaci\u00f3n de stock.
        """
        resultado = servicios.validar_restricciones(
            emergencia_externa_id=datos["emergencia_externa_id"],
            nivel_gravedad=datos["nivel_gravedad"],
            aportes=[
                AporteSolicitado(
                    identificador_nacional=aporte["identificador_nacional"],
                    codigo_recurso=aporte["codigo_recurso"],
                    cantidad=aporte["cantidad"],
                    tipo_asignacion=aporte["tipo_asignacion"],
                )
                for aporte in datos["aportes"]
            ],
        )
        return {
            "valido": resultado.valido,
            "motivos": [
                {
                    "identificador_nacional": m.identificador_nacional,
                    "codigo_recurso": m.codigo_recurso,
                    "cantidad_solicitada": m.cantidad_solicitada,
                    "cantidad_disponible": m.cantidad_disponible,
                    "motivo": m.motivo,
                }
                for m in resultado.motivos
            ],
        }


@blueprint_compromisos.route(
    "/<string:emergencia_externa_id>/ongs/<string:identificador_nacional>/finalizacion"
)
class FinalizacionDeActividades(MethodView):
    @blueprint_compromisos.requiere_rol(Rol.sistema)
    @blueprint_compromisos.response(
        200,
        RespuestaFinalizacion,
        description=(
            "Registra el cierre de la ONG; libera los recursos al finalizar todas "
            "las participantes."
        ),
    )
    @blueprint_compromisos.alt_response(
        404,
        schema=RespuestaError,
        description="La emergencia o la ONG participante no tiene compromisos registrados.",
    )
    @blueprint_compromisos.alt_response(
        409,
        schema=RespuestaError,
        description="El proyecto tiene compromisos en un estado que impide finalizarlo.",
    )
    def post(self, emergencia_externa_id: str, identificador_nacional: str):
        """Informar la finalización de una ONG y cerrar el proyecto cuando todas terminen."""
        resultado = servicios.informar_finalizacion_ong(
            emergencia_externa_id=emergencia_externa_id,
            identificador_nacional=identificador_nacional,
        )
        return {
            "emergencia_externa_id": resultado.emergencia_externa_id,
            "identificador_nacional": resultado.identificador_nacional,
            "proyecto_cerrado": resultado.proyecto_cerrado,
            "organizaciones_finalizadas": resultado.organizaciones_finalizadas,
            "organizaciones_participantes": resultado.organizaciones_participantes,
            "repetido": resultado.repetido,
        }
