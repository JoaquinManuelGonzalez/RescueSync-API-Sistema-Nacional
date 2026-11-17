"""Endpoint de evaluación de ofertas para el proceso de Bonita."""

from __future__ import annotations

from flask.views import MethodView

from app.core.acceso import Blueprint, Rol
from app.core.errores import RespuestaError
from app.modulos.evaluacion import servicios
from app.modulos.evaluacion.ejemplos import (
    EJEMPLO_EVALUACION_PRINCIPAL_Y_APOYO,
    EJEMPLOS_RESPUESTA_EVALUACION,
)
from app.modulos.evaluacion.schemas import EvaluacionOfertasSchema, RespuestaEvaluacionSchema

blueprint_evaluacion = Blueprint(
    "evaluacion",
    __name__,
    url_prefix="/ofertas",
    description="Evaluación de ofertas por niveles de competencia.",
)


@blueprint_evaluacion.route("/evaluacion")
class EvaluacionDeOfertas(MethodView):
    @blueprint_evaluacion.requiere_rol(Rol.sistema)
    @blueprint_evaluacion.arguments(
        EvaluacionOfertasSchema,
        example=EJEMPLO_EVALUACION_PRINCIPAL_Y_APOYO,
    )
    @blueprint_evaluacion.response(
        200,
        RespuestaEvaluacionSchema,
        examples=EJEMPLOS_RESPUESTA_EVALUACION,
    )
    @blueprint_evaluacion.alt_response(
        400,
        schema=RespuestaError,
        description="Cuerpo inválido, un id que no es UUID o un nivel de gravedad desconocido.",
    )
    @blueprint_evaluacion.alt_response(
        404,
        schema=RespuestaError,
        description="Un `codigo_recurso` no existe en el catálogo: no se evalúa nada.",
    )
    @blueprint_evaluacion.alt_response(
        409,
        schema=RespuestaError,
        description=(
            "La emergencia ya fue finalizada, o ya tiene compromisos distintos de los que acepta "
            "esta evaluación. Para volver a probar, usar otro `emergencia_id`."
        ),
    )
    @blueprint_evaluacion.alt_response(
        422,
        schema=RespuestaError,
        description="Otro pedido se llevó el stock entre la clasificación y el compromiso.",
    )
    def post(self, datos):
        """Evalúa ofertas y registra los compromisos de recursos no consumibles aceptados.

        La evaluación **modifica datos**: los aportes no consumibles `principal` o `apoyo` quedan
        comprometidos bajo `emergencia_id` y descuentan stock, que vuelve con la liberación o la
        finalización de la emergencia. Repetir el mismo pedido es idempotente mientras el stock
        que queda alcance para lo pedido.
        """
        return servicios.evaluar_ofertas(
            emergencia_id=datos["emergencia_id"],
            nivel_gravedad=datos["nivel_gravedad"],
            ofertas=datos["ofertas"],
        )
