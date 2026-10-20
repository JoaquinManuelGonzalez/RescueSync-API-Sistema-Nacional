"""Esquemas HTTP para el compromiso de recursos."""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.modulos.compromisos.modelos import EstadoCompromiso, NivelGravedad, TipoAsignacion

NIVELES_GRAVEDAD_ACEPTADOS = (
    "BAJA",
    "MEDIA",
    "ALTA",
    "CRITICA",
    "BAJO",
    "MEDIO",
    "ALTO",
    "CRITICO",
)


class AporteCompromiso(Schema):
    identificador_nacional = fields.String(required=True, validate=validate.Length(min=1, max=255))
    codigo_recurso = fields.String(required=True, validate=validate.Length(min=1, max=200))
    cantidad = fields.Integer(required=True, strict=True, validate=validate.Range(min=1))
    tipo_asignacion = fields.String(
        required=True,
        validate=validate.OneOf(
            [TipoAsignacion.principal.value, TipoAsignacion.apoyo.value],
        ),
    )


class PeticionCompromiso(Schema):
    emergencia_externa_id = fields.String(required=True, validate=validate.Length(min=1, max=255))
    nivel_gravedad = fields.String(
        required=True,
        validate=validate.OneOf(NIVELES_GRAVEDAD_ACEPTADOS),
        metadata={
            "description": "Gravedad de la emergencia; acepta las variantes del contrato web y API."
        },
    )
    aportes = fields.List(
        fields.Nested(AporteCompromiso),
        required=True,
        validate=validate.Length(min=1),
    )

    @validates_schema
    def _aportes_sin_duplicados(self, datos: dict, **_kwargs) -> None:
        claves = [
            (aporte["identificador_nacional"].strip(), aporte["codigo_recurso"].strip())
            for aporte in datos.get("aportes", [])
        ]
        if len(claves) != len(set(claves)):
            raise ValidationError(
                "No se puede repetir una combinación de organización y recurso.",
                "aportes",
            )


class ItemComprometidoRespuesta(Schema):
    codigo_recurso = fields.String(required=True)
    cantidad = fields.Integer(required=True)
    tipo_asignacion = fields.Enum(TipoAsignacion, by_value=True, required=True)


class CompromisoRespuesta(Schema):
    identificador_nacional = fields.String(required=True)
    nivel_gravedad = fields.Enum(NivelGravedad, by_value=True, required=True)
    estado = fields.Enum(EstadoCompromiso, by_value=True, required=True)
    items = fields.List(fields.Nested(ItemComprometidoRespuesta), required=True)


class RespuestaCompromiso(Schema):
    emergencia_externa_id = fields.String(required=True)
    repetido = fields.Boolean(required=True)
    compromisos = fields.List(fields.Nested(CompromisoRespuesta), required=True)


class RespuestaFinalizacion(Schema):
    emergencia_externa_id = fields.String(required=True)
    identificador_nacional = fields.String(required=True)
    proyecto_cerrado = fields.Boolean(required=True)
    organizaciones_finalizadas = fields.Integer(required=True)
    organizaciones_participantes = fields.Integer(required=True)
    repetido = fields.Boolean(required=True)
