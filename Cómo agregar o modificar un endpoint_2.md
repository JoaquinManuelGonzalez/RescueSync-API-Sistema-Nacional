# Cómo agregar o modificar un endpoint

La API va a usar `flask-smorest`: la especificación de OpenAPI se genera a partir del código. Si un endpoint no está decorado correctamente, no aparece en `/docs`.

Documentación:

* [Marshmallow](https://marshmallow.readthedocs.io/en/latest/index.html)
* [Flask-smorest](https://flask-smorest.readthedocs.io/en/stable/quickstart.html)

---

1. Definir los schemas

En `app/modulos/ejemplos/schemas.py`, definí las clases de Marshmallow que describen request y response:

```py
import marshmallow

class EjemploSchema(marshmallow.Schema):
    id = marshmallow.fields.Int(dump_only=True)
    nombre = marshmallow.fields.String(required=True)

class EjemploQueryArgsSchema(marshmallow.Schema):
    nombre = marshmallow.fields.String(required=False)
```

Notas:

* `dump_only=True` para campos que solo aparecen en la respuesta (ej. id).
* `load_only=True` para campos que solo se envían en el request (ej. password).
* `required=True` para campos obligatorios.

---

2. Crear el Blueprint y las vistas

En `app/modulos/ejemplos/rutas.py`:

```py
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from app.modulos.ejemplo.schemas import EjemploSchema, EjemploQueryArgsSchema

blueprint_ejemplo = Blueprint(
    "ejemplo",
    __name__,
    url_prefix="/ejemplos",
    description="Recurso de ejemplo.",
)

@blueprint_ejemplo.route("/")
class Ejemplos(MethodView):

    @blueprint_ejemplo.arguments(EjemploQueryArgsSchema, location="query")
    @blueprint_ejemplo.response(200, EjemploSchema(many=True))
    def get(self, args):
        """Listar ejemplos"""
        return []
```
Notas:

* Importá Blueprint de `flask_smorest`, no de `flask`.
* El `url_prefix` va acá, no en el registro.
* El docstring del método se convierte en summary y description en Swagger.
* Usá `abort(404, message="...")` de `flask_smorest` para errores.

    * De la documentación de [flask-smorest](https://flask-smorest.readthedocs.io/en/stable/quickstart.html):

```py
    @blp.arguments(PetSchema)
    @blp.response(200, PetSchema)
    def put(self, update_data, pet_id):
        """Update existing pet"""
        try:
            item = Pet.get_by_id(pet_id)
        except ItemNotFoundError:
            abort(404, message="Item not found.")
        item.update(update_data)
        item.commit()
        return item
```

---

3. Registrar el Blueprint

En `app/modulos/__init__.py`, agregá el blueprint a la Api:

```py
def registrar_modulos(app: Flask, api: Api) -> None:
    from app.modulos.ejemplo.rutas import blueprint_ejemplo
    api.register_blueprint(blueprint_ejemplo)
```

**Importante:** usá `api.register_blueprint`, no `app.register_blueprint`. La api en sí se crea en create_app y se pasa como parámetro.

---

4. Verificar en Swagger

    * docker compose up
    * Abrí http://localhost:5000/docs
    * Confirmá que tu endpoint aparece bajo el tag del módulo, con sus parámetros, request body y responses.

