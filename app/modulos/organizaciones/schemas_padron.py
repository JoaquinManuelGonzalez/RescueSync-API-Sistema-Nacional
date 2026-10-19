"""Esquemas del padrón nacional de ONGs (onboarding y estado de habilitación)."""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.modulos.organizaciones.modelos import EstadoHabilitacion, TipoOrganizacion

EJEMPLO_CUIT = "30-71555444-2"


class PeticionAltaOrganizacion(Schema):
    cuit = fields.String(
        required=True,
        metadata={"description": "11 dígitos, con o sin guiones.", "example": EJEMPLO_CUIT},
    )
    nombre = fields.String(required=True, validate=validate.Length(min=1, max=200))
    tipo = fields.Enum(
        TipoOrganizacion,
        by_value=True,
        load_default=TipoOrganizacion.ong,
        metadata={"description": "Por defecto, `ong`."},
    )
    mail_contacto = fields.Email(required=True, validate=validate.Length(max=200))
    telefono_contacto = fields.String(load_default=None, validate=validate.Length(max=50))


class PeticionCambioHabilitacion(Schema):
    estado = fields.Enum(
        EstadoHabilitacion,
        by_value=True,
        required=True,
        metadata={"description": "`habilitada` o `suspendida`."},
    )
    motivo = fields.String(
        load_default=None,
        validate=validate.Length(max=500),
        metadata={"description": "Obligatorio al suspender. Queda en el historial."},
    )

    @validates_schema
    def _motivo_al_suspender(self, datos: dict, **_kwargs) -> None:
        if (
            datos.get("estado") is EstadoHabilitacion.suspendida
            and not (datos.get("motivo") or "").strip()
        ):
            raise ValidationError("Obligatorio al suspender una organización.", "motivo")


class OrganizacionPadron(Schema):
    id = fields.Integer(required=True)
    cuit = fields.String(attribute="identificador_nacional", required=True)
    nombre = fields.String(required=True)
    tipo = fields.Enum(TipoOrganizacion, by_value=True, required=True)
    mail_contacto = fields.String(required=True)
    telefono_contacto = fields.String(allow_none=True)
    estado_habilitacion = fields.Enum(EstadoHabilitacion, by_value=True, required=True)
    habilitada = fields.Boolean(
        required=True,
        metadata={"description": "True solo si puede ofrecer y comprometer recursos."},
    )
    motivo_estado = fields.String(
        allow_none=True, metadata={"description": "Motivo del último cambio de estado."}
    )
    actualizada_en = fields.DateTime(attribute="updated_at", required=True)


class RegistroHabilitacion(Schema):
    estado_anterior = fields.Enum(EstadoHabilitacion, by_value=True, allow_none=True)
    estado_nuevo = fields.Enum(EstadoHabilitacion, by_value=True, required=True)
    motivo = fields.String(allow_none=True)
    cuenta = fields.Function(
        lambda registro: registro.cuenta.usuario if registro.cuenta else None,
        metadata={"description": "Cuenta de la API que hizo el cambio."},
    )
    usuario_bonita = fields.String(allow_none=True)
    caso_bonita = fields.String(allow_none=True)
    fecha = fields.DateTime(required=True)


class HistorialHabilitacionRespuesta(Schema):
    cuit = fields.String(required=True)
    estado_actual = fields.Enum(EstadoHabilitacion, by_value=True, required=True)
    registros = fields.List(fields.Nested(RegistroHabilitacion), required=True)
