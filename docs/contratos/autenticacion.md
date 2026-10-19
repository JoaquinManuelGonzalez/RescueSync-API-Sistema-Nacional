# Contrato de autenticación y autorización

Cómo se autentican los clientes de la API del Sistema Nacional, qué puede hacer cada rol y cómo
lo configura Bonita. La decisión y sus alternativas están en
[ADR-005](../adr/ADR-005-autenticacion-jwt-y-cuentas-de-cliente.md). El código vive en
`app/core/acceso.py` (validación y roles) y `app/modulos/autenticacion/` (login y cuentas).

## 1. Quién se autentica

La API autentica **clientes**, no personas. Las ONGs y los usuarios de la aplicación web no
tienen cuenta acá: se autentican en la aplicación web y en Bonita.

| Rol | Cuenta típica | Quién la usa | Qué puede hacer |
|---|---|---|---|
| `sistema` | `bonita-rescuesync` | Motor de Bonita (conectores REST) | Consultar el padrón y operar el proceso: evaluación, reserva, compromiso y liberación de recursos |
| `administrador` | `admin-sn` | Operador del Sistema Nacional (Swagger, Postman) | Dar de alta ONGs en el padrón y cambiar su estado de habilitación |

La persona que disparó cada paso del proceso no se autentica, pero queda registrada: Bonita la
informa en una cabecera de trazabilidad ([sección 6](#6-trazabilidad)).

## 2. Obtener un token: `POST /login`

`/login` acepta dos formatos y responde lo mismo en los dos:

```json
{"access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "Bearer", "expires_in": 3600}
```

La respuesta lleva `Cache-Control: no-store`.

### 2.1 JSON (Swagger, Postman, personas)

```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"usuario": "admin-sn", "contrasena": "<contraseña>"}'
```

| Respuesta | Cuándo |
|---|---|
| 200 | Credenciales válidas y cuenta activa |
| 400 `SOLICITUD_INVALIDA` | Falta `usuario` o `contrasena` (`detalle` dice cuál) |
| 401 `NO_AUTENTICADO` | Usuario inexistente, contraseña incorrecta o cuenta desactivada. El mensaje es siempre el mismo, para no revelar qué cuentas existen |
| 415 `TIPO_DE_CONTENIDO_NO_SOPORTADO` | El cuerpo no es JSON ni formulario |

### 2.2 OAuth2 client credentials (conector de Bonita)

Es el flujo del RFC 6749 §4.4, que el conector REST de Bonita (1.5.x) implementa en su modo
**OAUTH2 (Client Credentials)**. `client_id` es el usuario de la cuenta y `client_secret` su
contraseña. Pueden ir en el cuerpo o en HTTP Basic.

```bash
curl -X POST http://localhost:8000/login \
  -d grant_type=client_credentials \
  -d client_id=bonita-rescuesync \
  -d client_secret=<secreto>

# o con HTTP Basic, como lo hace Swagger UI por defecto
curl -X POST http://localhost:8000/login -u bonita-rescuesync:<secreto> \
  -d grant_type=client_credentials
```

En este formato los errores **no** usan el envelope del proyecto sino el del RFC 6749 §5.2,
porque el conector de Bonita lee el campo `error` como texto:

| Respuesta | Cuándo |
|---|---|
| 400 `{"error": "invalid_request"}` | Falta `grant_type` |
| 400 `{"error": "unsupported_grant_type"}` | `grant_type` no es `client_credentials` |
| 401 `{"error": "invalid_client"}` | Faltan las credenciales, son incorrectas o la cuenta está desactivada |

## 3. El token

JWT firmado con HS256 y la clave `JWT_SECRET_KEY` ([configuración](configuracion.md)).

| Claim | Valor | Significado (RFC 7519) |
|---|---|---|
| `iss` | `sistema-nacional` | Quién emitió el token: esta API |
| `aud` | `sistema-nacional-api` | Para quién es: esta API. Un token con otra audiencia se rechaza |
| `sub` | `bonita-rescuesync` | La cuenta dueña del token |
| `rol` | `sistema` / `administrador` | Rol de la cuenta (claim propio) |
| `iat`, `nbf`, `exp` | segundos Unix | Emisión, inicio de validez y vencimiento |
| `jti`, `type`, `fresh` | — | Agregados por flask-jwt-extended |

La vida del token es `JWT_EXPIRACION_MINUTOS` (60 por defecto). No hay refresh tokens: un cliente
con credenciales propias pide un token nuevo cuando el anterior vence, y el conector de Bonita lo
hace solo (sección 7).

> La diapositiva de la cátedra describe `iss` como "quien hace el request" y `sub` como "el motivo
> del request". La API sigue el RFC 7519: `iss` es el emisor del token y `sub` el sujeto (la
> cuenta). El usuario del pedido es `sub`.

## 4. Usar el token

Todo endpoint, salvo `/login`, `/health`, `/docs` y `/openapi.json`, exige el encabezado:

```
Authorization: Bearer <access_token>
```

La API verifica la firma, el vencimiento, el emisor y la audiencia, y que la cuenta siga
existiendo, activa y con el mismo rol. Desactivar una cuenta o cambiarle el rol invalida al
instante todos sus tokens, aunque no hayan vencido.

| Respuesta | `detalle` | Cuándo |
|---|---|---|
| 401 `NO_AUTENTICADO` | `{"motivo": "token_ausente"}` | No hay encabezado `Authorization: Bearer ...` |
| 401 `NO_AUTENTICADO` | `{"motivo": "token_invalido"}` | Token mal formado, firma alterada, otra audiencia u otro emisor |
| 401 `NO_AUTENTICADO` | `{"motivo": "token_expirado"}` | Venció: pedir uno nuevo en `/login` |
| 401 `NO_AUTENTICADO` | `{"motivo": "cuenta_inactiva"}` | La cuenta del token se desactivó, se borró o cambió de rol |
| 403 `PERMISO_DENEGADO` | `{"rol": "sistema", "roles_permitidos": ["administrador"]}` | El rol del token no habilita la operación |

Las respuestas 401 llevan `WWW-Authenticate: Bearer realm="sistema-nacional"` (RFC 6750), con
`error="invalid_token"` cuando había un token pero no sirvió. La autenticación se evalúa antes
que el cuerpo: un pedido sin token recibe 401 aunque además tenga el cuerpo mal formado.

## 5. Matriz de permisos

| Endpoint | `sistema` | `administrador` |
|---|---|---|
| `POST /login` | público | público |
| `GET /cuentas/yo` | ✓ | ✓ |
| `POST /ongs` (alta en el padrón, nace `pendiente`) | 403 | ✓ |
| `GET /ongs/{cuit}` | ✓ | ✓ |
| `PATCH /ongs/{cuit}/habilitacion` | 403 | ✓ |
| `GET /ongs/{cuit}/habilitacion/historial` | ✓ | ✓ |
| Consultas de catálogo (certificaciones, ONGs habilitadas, disponibilidad) | ✓ | ✓ |
| Evaluación, reserva, compromiso y liberación de recursos | ✓ | 403 |

`GET /cuentas/yo` devuelve la cuenta y el rol del token, cuándo vence y las cabeceras de
trazabilidad que la API aceptó: sirve para probar un token o la configuración del conector.

## 6. Trazabilidad

Bonita autentica con su propia cuenta, pero informa en cada llamada quién y desde qué caso:

| Cabecera | Quién la pone | Qué contiene |
|---|---|---|
| `X-Usuario-Bonita` | El conector, desde la variable de proceso `ultimoUsuario` | Usuario de Bonita (el email del usuario web) que completó la tarea humana que disparó la llamada |
| `X-Bonita-Process-Instance-Id` | El conector solo, con *Add Bonita context headers* | Id del caso del proceso |
| `X-Correlation-Id` | Opcional | Id para cruzar los logs ([logging](logging.md)) |

- La API solo toma `X-Usuario-Bonita` y `X-Bonita-Process-Instance-Id` de un token de rol
  `sistema`. Si las manda otro rol, se ignoran: su actor es la cuenta misma.
- Se guardan en los historiales (por ejemplo, `historial_habilitaciones.usuario_bonita` y
  `caso_bonita`) junto con la cuenta de la API.
- Los logs registran la cuenta, el rol y el caso, **nunca** `X-Usuario-Bonita`, porque es un
  email (sección 3 de [logging](logging.md)).

## 7. Guía para Bonita

Lo que se configura en Bonita Studio. No hace falta un conector extra ni Groovy para el token.

### 7.1 Parámetros del proceso (una vez)

En *Configure → Parameters*, para cada entorno:

| Parámetro | Tipo | Valor local | Valor en la nube |
|---|---|---|---|
| `urlSistemaNacional` | Text | `http://localhost:8000` | `https://rescuesync-sistema-nacional.onrender.com` |
| `snClientId` | Text | `bonita-rescuesync` | `bonita-rescuesync` |
| `snClientSecret` | Text | el secreto de la cuenta local | el secreto de la cuenta de Supabase |

El `.conf` con los valores ya está en el `.gitignore` del proyecto de Bonita: el secreto no se
commitea. El secreto lo genera `flask cuentas crear ... --generar` ([sección 8](#8-cuentas)).

### 7.2 Cada conector REST que llame a la API

En el asistente del conector (REST 1.5.x: GET, POST, PUT, PATCH o DELETE):

1. **Authentication settings**: elegir **OAUTH2 (Client Credentials)** y completar:
   - *Token Endpoint URL*: `urlSistemaNacional + "/login"`
   - *Client ID*: `snClientId`
   - *Client Secret*: `snClientSecret`
   - *Scope* y *Audience*: vacíos.
2. **Optional advanced settings**:
   - Tildar **Add Bonita context headers** (manda `X-Bonita-Process-Instance-Id` y otros ids).
   - *Socket timeout*: unos `90000` ms. El plan Free de Render tarda hasta un minuto en
     despertar, y el pedido del token usa los mismos timeouts.
3. **REST request configuration → Headers** (opcional, para saber qué persona disparó la
   llamada): `X-Usuario-Bonita` = variable `ultimoUsuario` (7.3).

El conector pide el token a `/login`, lo guarda en memoria y pide uno nuevo 60 segundos antes de
que venza. Por eso no importa cuánto dure el caso: cada tarea de servicio tiene un token válido
al ejecutarse. El token nunca se guarda en una variable del proceso. Si Bonita se reinicia, pide
uno nuevo.

### 7.3 Opcional: `ultimoUsuario`

En una tarea de servicio no hay usuario asignado (el conector manda
`X-Bonita-Task-Assignee-Id: 0`), así que la persona sale de la tarea humana anterior:

1. Variable de proceso `ultimoUsuario` (Text).
2. En la tarea humana previa a cada llamada a la API, una operación:
   `ultimoUsuario` ← *takes value of* script
   `apiAccessor.identityAPI.getUser(taskAssigneeId).userName`.

| Llamada a la API | Tarea humana previa |
|---|---|
| *Enviar ofertas a Sistema Nacional* (después del timer) | *Gestionar emergencia y publicar convocatoria* |
| *Enviar compromiso* | *Seleccionar ofertas* |
| *Informar finalización* | La última tarea de ejecución de las ONGs |

Para que el valor sea la persona real, los actores del proceso tienen que estar mapeados a los
usuarios de la aplicación web (hoy los tres actores están mapeados solo a `walter.bates`).

### 7.4 Si algo falla

- **Credenciales mal cargadas**: el conector falla con `OAuth2 token request failed. Error:
  invalid_client` y la tarea queda en estado *Failed*. Corregir el parámetro y reintentar la
  tarea desde el Portal de Bonita (perfil Administrador).
- **Timeout**: la API estaba dormida. Despertarla (`/health`) y reintentar.
- **Probar la configuración**: un conector REST GET a `urlSistemaNacional + "/cuentas/yo"` con la
  misma autenticación devuelve `"rol": "sistema"` y, en `trazabilidad`, el caso y el usuario que
  la API recibió.

## 8. Cuentas

No hay endpoint para crear cuentas: se crean con la consola de Flask, contra la base local o la
de Supabase.

```bash
# Local (dentro del contenedor)
docker compose exec api flask cuentas crear admin-sn --rol administrador \
  --descripcion "Operador del Sistema Nacional"          # pide la contraseña (mínimo 12)
docker compose exec api flask cuentas crear bonita-rescuesync --rol sistema \
  --descripcion "Motor Bonita de RescueSync" --generar   # genera el secreto y lo muestra una vez
docker compose exec api flask cuentas listar
docker compose exec api flask cuentas desactivar admin-sn
```

Contra Supabase, con el runbook "Crear cuentas en Supabase" del README. `crear` sobre una cuenta
existente le cambia la contraseña y el rol y la reactiva: así se rota un secreto. Al rotar el de
Bonita, actualizar el parámetro `snClientSecret`.

> En Windows, `flask cuentas crear` sin `--generar` hay que correrlo dentro del contenedor (o en
> una terminal interactiva): la contraseña se lee de la consola, no de un pipe.

## 9. Proteger un endpoint nuevo

Los módulos usan el `Blueprint` de `app.core.acceso` en lugar del de flask-smorest, y cada
método lleva `requiere_rol` **arriba de todo**:

```python
from app.core.acceso import Blueprint, Rol, actor_actual

blueprint_compromisos = Blueprint("compromisos", __name__, url_prefix="/compromisos")


@blueprint_compromisos.route("")
class Compromisos(MethodView):
    @blueprint_compromisos.requiere_rol(Rol.sistema)
    @blueprint_compromisos.arguments(PeticionCompromiso)
    @blueprint_compromisos.response(201, RespuestaCompromiso)
    def post(self, datos):
        actor = actor_actual()  # cuenta, rol, usuario_bonita y caso_bonita para el historial
        ...
```

- `requiere_rol` valida el token y el rol, y documenta en Swagger el candado y las respuestas
  401 y 403.
- El mismo `Blueprint` responde 400 `SOLICITUD_INVALIDA` (no 422) ante un cuerpo inválido.
- `tests/test_rutas_protegidas.py` recorre todas las rutas y falla si alguna responde sin token.
  Publicar una ruta a propósito exige agregarla a `RUTAS_PUBLICAS` y justificarlo en el PR.
- Para saber si una ONG puede comprometer recursos, usar
  `app.modulos.organizaciones.servicios.estado_de(cuit)`: solo `habilitada` puede.

## 10. Swagger y Postman

- **Swagger** (`/docs`): *Authorize* ofrece `bearerAuth` (pegar el `access_token`) y `oauth2`
  (client id y secret; Swagger pide el token solo). El token sobrevive a recargar la página.
- **Postman**: `docs/postman/` tiene la colección y los entornos `local` y `render`. Completar
  las credenciales en el entorno y correr la colección en orden: los logins guardan los tokens en
  variables que usan los demás pedidos.
