"""Contratos HTTP para la evaluación de ofertas consolidadas de Bonita."""

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.modulos.organizaciones.modelos import NivelCertificacion


class AporteOfertaSchema(Schema):
    cantidad = fields.Integer(required=True, strict=True, validate=validate.Range(min=1))
    identificador_nacional = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255),
    )
    # Es informativo: nunca se usa para cruzar con la base del Sistema Nacional.
    organizacion_id = fields.Integer(required=True, validate=validate.Range(min=1))


class ItemOfertaSchema(Schema):
    aportes = fields.List(
        fields.Nested(AporteOfertaSchema),
        required=True,
        validate=validate.Length(min=1),
    )
    cantidad_total = fields.Integer(required=True, strict=True, validate=validate.Range(min=1))
    codigo_recurso = fields.String(required=True, validate=validate.Length(min=1, max=200))
    lote_item_id = fields.Integer(required=True, validate=validate.Range(min=1))
    tipo_recurso = fields.String(required=True, validate=validate.Length(min=1, max=255))
    unidad = fields.String(required=True, validate=validate.Length(min=1, max=50))

    @validates_schema
    def _cantidad_total_coincide(self, datos: dict, **_kwargs) -> None:
        cantidad_aportes = sum(aporte["cantidad"] for aporte in datos["aportes"])
        if cantidad_aportes != datos["cantidad_total"]:
            raise ValidationError(
                "La cantidad total debe coincidir con la suma de los aportes.",
                "cantidad_total",
            )


class OrganizacionOfertaSchema(Schema):
    id = fields.Integer(required=True, validate=validate.Range(min=1))
    identificador_nacional = fields.String(
        required=True,
        validate=validate.Length(min=1, max=255),
    )
    nombre = fields.String(required=True)
    rol = fields.String(required=True)


class OfertaConsolidadaSchema(Schema):
    fecha_creacion = fields.DateTime(required=True)
    items = fields.List(
        fields.Nested(ItemOfertaSchema),
        required=True,
        validate=validate.Length(min=1),
    )
    oferta_id = fields.Integer(required=True, validate=validate.Range(min=1))
    organizaciones = fields.List(
        fields.Nested(OrganizacionOfertaSchema),
        required=True,
        validate=validate.Length(min=1),
    )
    version = fields.Integer(required=True, validate=validate.Range(min=1))


class EvaluacionOfertasSchema(Schema):
    emergencia_id = fields.Integer(required=True, validate=validate.Range(min=1))
    nivel_gravedad = fields.String(required=True)
    ofertas = fields.List(
        fields.Nested(OfertaConsolidadaSchema),
        required=True,
        validate=validate.Length(min=1),
    )


class EvaluacionAporteSchema(Schema):
    cantidad = fields.Integer(required=True)
    identificador_nacional = fields.String(required=True)
    organizacion_id = fields.Integer(required=True)
    certificacion_encontrada = fields.Boolean(required=True)
    nivel_riesgo_permitido = fields.Enum(
        NivelCertificacion,
        by_value=True,
        allow_none=True,
        required=True,
    )
    clasificacion = fields.String(required=True)
    motivo = fields.String(required=True)
    compromiso_registrado = fields.Boolean(required=True)


class ItemEvaluadoSchema(Schema):
    aportes = fields.List(fields.Nested(EvaluacionAporteSchema), required=True)
    cantidad_total = fields.Integer(required=True)
    codigo_recurso = fields.String(required=True)
    lote_item_id = fields.Integer(required=True)
    tipo_recurso = fields.String(required=True)
    unidad = fields.String(required=True)
    consumible = fields.Boolean(required=True)


class OfertaEvaluadaSchema(Schema):
    fecha_creacion = fields.DateTime(required=True)
    items = fields.List(fields.Nested(ItemEvaluadoSchema), required=True)
    oferta_id = fields.Integer(required=True)
    organizaciones = fields.List(fields.Nested(OrganizacionOfertaSchema), required=True)


class RespuestaEvaluacionSchema(Schema):
    emergencia_id = fields.Integer(required=True)
    nivel_gravedad = fields.String(required=True)
    ofertas = fields.List(fields.Nested(OfertaEvaluadaSchema), required=True)
