"""Schemas de consulta para certificaciones, organizaciones y recursos."""

from marshmallow import Schema, fields, validate

from app.modulos.organizaciones.modelos import NivelCertificacion


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
    nivel_certificacion = fields.Enum(
        NivelCertificacion,
        by_value=True,
        load_default=None,
        allow_none=True,
    )


class OrganizacionCertificacionSchema(Schema):
    id = fields.Integer(required=True)
    nombre = fields.String(required=True)
    nivel_certificacion = fields.Enum(NivelCertificacion, by_value=True, required=True)


class OrganizacionConsultaSchema(Schema):
    id = fields.Integer(required=True)
    cuit = fields.String(required=True, allow_none=True)
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
    consumible = fields.Boolean(required=True)
    total = fields.Integer(required=True)
    comprometido = fields.Integer(required=True)
    disponible = fields.Integer(required=True)


class DisponibilidadPaginadaSchema(Schema):
    elementos = fields.List(fields.Nested(DisponibilidadRecursoSchema), required=True)
    pagina = fields.Integer(required=True)
    por_pagina = fields.Integer(required=True)
    total = fields.Integer(required=True)


class PeticionCargaInventarioSchema(Schema):
    item_id = fields.Integer(required=True, validate=validate.Range(min=1))
    cantidad_disponible = fields.Integer(required=True, validate=validate.Range(min=0))


class InventarioCargadoSchema(Schema):
    id = fields.Integer(required=True)
    item_id = fields.Integer(required=True)
    item_nombre = fields.String(required=True)
    cantidad_disponible = fields.Integer(required=True)


class PeticionCargaCertificacionSchema(Schema):
    certificacion_id = fields.Integer(required=True, validate=validate.Range(min=1))
    nivel_certificacion = fields.Enum(NivelCertificacion, by_value=True, required=True)


class CertificacionCargadaSchema(Schema):
    id = fields.Integer(required=True)
    certificacion_id = fields.Integer(required=True)
    certificacion_nombre = fields.String(required=True)
    nivel_certificacion = fields.Enum(NivelCertificacion, by_value=True, required=True)
    fecha_emision = fields.DateTime(required=True)
