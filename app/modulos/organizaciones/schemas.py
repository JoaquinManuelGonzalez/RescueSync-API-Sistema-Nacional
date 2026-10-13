"""Schemas de consulta para certificaciones, organizaciones y recursos."""

from marshmallow import Schema, fields, validate


class PaginacionQuerySchema(Schema):
    """Parámetros comunes de paginación."""

    pagina = fields.Integer(load_default=1, validate=validate.Range(min=1))
    por_pagina = fields.Integer(load_default=20, validate=validate.Range(min=1, max=100))


class CertificacionSchema(Schema):
    id = fields.Integer(dump_only=True)
    nombre = fields.String(required=True)
    tipo = fields.String(required=True)


class CatalogoCertificacionesSchema(Schema):
    elementos = fields.List(fields.Nested(CertificacionSchema), required=True)
    pagina = fields.Integer(required=True)
    por_pagina = fields.Integer(required=True)
    total = fields.Integer(required=True)


class ConsultaOrganizacionesQuerySchema(PaginacionQuerySchema):
    certificacion_id = fields.Integer(
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=1),
    )
    nivel_certificacion = fields.String(load_default=None, allow_none=True)


class OrganizacionCertificacionSchema(Schema):
    id = fields.Integer(required=True)
    nombre = fields.String(required=True)
    nivel_certificacion = fields.String(required=True)


class OrganizacionConsultaSchema(Schema):
    id = fields.Integer(required=True)
    nombre = fields.String(required=True)
    mail_contacto = fields.String(required=True)
    certificaciones = fields.List(
        fields.Nested(OrganizacionCertificacionSchema),
        required=True,
    )


class OrganizacionesPaginadasSchema(Schema):
    elementos = fields.List(fields.Nested(OrganizacionConsultaSchema), required=True)
    pagina = fields.Integer(required=True)
    por_pagina = fields.Integer(required=True)
    total = fields.Integer(required=True)


class ConsultaDisponibilidadQuerySchema(PaginacionQuerySchema):
    tipo = fields.String(load_default=None, allow_none=True)


class DisponibilidadRecursoSchema(Schema):
    id = fields.Integer(required=True)
    nombre = fields.String(required=True)
    tipo = fields.String(required=True)
    unidad_medida = fields.String(required=True)
    total = fields.Integer(required=True)
    comprometido = fields.Integer(required=True)
    disponible = fields.Integer(required=True)


class DisponibilidadPaginadaSchema(Schema):
    elementos = fields.List(fields.Nested(DisponibilidadRecursoSchema), required=True)
    pagina = fields.Integer(required=True)
    por_pagina = fields.Integer(required=True)
    total = fields.Integer(required=True)
