"""Endpoint de evaluación de ofertas para el proceso de Bonita."""

from __future__ import annotations

from flask.views import MethodView

from app.core.acceso import Blueprint, Rol
from app.core.errores import RespuestaError
from app.modulos.evaluacion import servicios
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
    @blueprint_evaluacion.arguments(EvaluacionOfertasSchema)
    @blueprint_evaluacion.response(200, RespuestaEvaluacionSchema)
    @blueprint_evaluacion.alt_response(400, schema=RespuestaError)
    @blueprint_evaluacion.alt_response(404, schema=RespuestaError)
    @blueprint_evaluacion.alt_response(422, schema=RespuestaError)
    def post(self, datos):
        """Evalúa ofertas y registra los compromisos de recursos no consumibles aceptados."""
        return servicios.evaluar_ofertas(
            emergencia_id=datos["emergencia_id"],
            nivel_gravedad=datos["nivel_gravedad"],
            ofertas=datos["ofertas"],
        )
