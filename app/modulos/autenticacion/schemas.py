from marshmallow import Schema, fields

# Prototipo de Schema para la autenticación vía JWT


class PeticionIngreso(Schema):
    usuario = fields.String(required=True)
    contrasena = fields.String(required=True, load_only=True)


class RespuestaIngreso(Schema):
    access_token = fields.String(required=True)
    token_type = fields.String(dump_default="Bearer")
    expires_in = fields.Integer(required=True)
