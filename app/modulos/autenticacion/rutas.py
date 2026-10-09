from flask.views import MethodView
from flask_smorest import Blueprint, error_handler

from app.modulos.autenticacion.schemas import PeticionIngreso, RespuestaIngreso

blueprint_autenticacion = Blueprint(
    "autenticacion",
    __name__,
    url_prefix="/autenticacion",
    description="Autenticación y gestión de cuentas",
)


@blueprint_autenticacion.route("/login")
class Login(MethodView):
    @blueprint_autenticacion.arguments(
        PeticionIngreso,
        example={
            "usuario": "ong_ejemplo",
            "contrasena": "secreto123",
        },
    )
    @blueprint_autenticacion.response(
        200,
        RespuestaIngreso,
        example={
            "access_token": "eyJhbGciOiJIUzI1NiIs...",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )
    # ErrorSchema por defecto de flask_smorest por ahora
    @blueprint_autenticacion.alt_response(
        401,
        schema=error_handler.ErrorSchema,
        description="Credenciales inválidas",
        example={
            "usuario": "ong_ejemplo",
            "contrasena": "incorrecta321",
        },
    )
    def post(self, credenciales):
        """Iniciar sesión

        Devuelve un JWT válido para consumir el resto de la API.
        """
        # TODO: Implementar realmente la autenticación y generación del token
        #  usuario = autenticar(credenciales["usuario"], credenciales["contrasena"])
        # if not usuario:
        #     abort(401, code="AUTH_INVALID", message="Credenciales inválidas")
        # return generar_jwt(usuario)
