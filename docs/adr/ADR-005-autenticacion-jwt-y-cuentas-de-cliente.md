# ADR-005: Autenticación JWT con cuentas de cliente

- Estado: Aceptado
- Fecha: 2026-10-17
- Reemplaza a: —
- Reemplazado por: —

## Contexto

La consigna pide que la API del Sistema Nacional tenga "autenticación JWT", un inicio de sesión
en `/login` y un servicio de registro/onboarding de ONGs. La épica EPIC-61 agregaba credenciales
distintas para la aplicación local, para el motor de Bonita y para las ONGs registradas.

Para decidir cómo autenticar pesaron estos hechos del sistema:

- **Bonita es el único consumidor de la API.** La aplicación web nunca la llama: toda
  interacción pasa por el proceso (decisión previa del equipo, ver README).
- **No hay una persona en la llamada.** A la API la llaman las tareas de servicio del lane
  *Sistema* (*Enviar ofertas*, *Enviar compromiso*, *Informar finalización*), que ejecuta el
  motor. *Enviar ofertas* corre después de un temporizador. Bonita tampoco tiene las contraseñas
  de los usuarios: la aplicación web entra a Bonita con una contraseña compartida.
- **Los casos duran días o semanas.** Entre dos llamadas del mismo caso puede pasar mucho más
  tiempo que la vida razonable de un token.
- **El conector REST de Bonita (1.5.1) trae OAuth2 client credentials.** Pide el token a un
  endpoint con un POST form-urlencoded (`grant_type`, `client_id`, `client_secret`), lo guarda en
  memoria y pide otro 60 segundos antes de que venza. Se verificó en el código fuente del
  conector (`RESTConnector.acquireOAuth2Token`).
- **Alguien tiene que decidir la habilitación de las ONGs**, y no corresponde que lo haga
  RescueSync: el Sistema Nacional es la autoridad del padrón.
- El profesor evalúa la API desde Swagger y Postman.

## Decisión

La API autentica **clientes, no personas**. Cada cliente tiene una cuenta (`cuentas`) con un rol:
`sistema` para Bonita y `administrador` para el operador del Sistema Nacional. `POST /login`
emite un JWT HS256 de vida corta (60 minutos, configurable) y acepta dos formatos: JSON
(`usuario`, `contrasena`) para Swagger y Postman, y OAuth2 client credentials (RFC 6749 §4.4)
para el conector de Bonita. La persona que disparó cada paso viaja como dato de trazabilidad
(`X-Usuario-Bonita`), aceptado solo de una cuenta `sistema`, y se guarda en los historiales.

Con eso, el vencimiento del token lo resuelve el conector y no el proceso: cada tarea de servicio
obtiene un token válido al ejecutarse, sin refresh tokens, sin variables con el token y sin
Groovy. La diferenciación de la épica se redujo a lo que el sistema usa:

- **Aplicación local**: sin credencial, porque nunca llama a la API.
- **Bonita**: rol `sistema`.
- **ONGs**: sin credencial. Las ONGs no llaman a la API; su identidad en el Sistema Nacional es
  su registro en el padrón (CUIT y estado de habilitación). Se eliminó
  `organizaciones.password_hash`, que nadie usaba.
- **Administrador del Sistema Nacional**: rol nuevo, que la épica no nombraba. Da de alta las
  ONGs y decide su habilitación. Permite mostrar los 403 en los dos sentidos: Bonita no puede
  habilitar ONGs y el administrador no puede comprometer recursos.

### Versión fijada

| Tecnología | Versión | Archivo del repositorio donde se fija |
|---|---|---|
| flask-jwt-extended | 4.7.4 | `pyproject.toml` / `uv.lock` |
| PyJWT (dependencia de la anterior) | 2.15.1 | `uv.lock` |

### Alternativas consideradas

| Alternativa | A favor | En contra | Motivo del descarte |
|---|---|---|---|
| Una cuenta en la API por cada usuario de la aplicación web | El token identifica a la persona | Contraseñas replicadas en tres sistemas; Bonita no tiene las contraseñas; las tareas que dispara el temporizador no tienen persona; un token de usuario vence entre llamadas y no se puede renovar sin la contraseña | No se puede implementar sin guardar contraseñas de usuarios en Bonita |
| Bonita hace login "en nombre de" la persona (claim `actor` en el token) | La persona queda firmada dentro del token | Un conector de login extra por tarea, una variable con el token y el encabezado armado a mano; no usa el modo OAuth2 del conector; la API igual confía en lo que dice Bonita | Más trabajo manual en el proceso para la misma garantía que una cabecera |
| Refresh tokens | Sesiones largas sin reenviar la contraseña | Bonita tendría que guardar y rotar el refresh token en el proceso | Un cliente con credenciales propias pide un token nuevo; el conector ya lo hace solo |
| RS256 (clave pública y privada) | Terceros pueden verificar tokens sin el secreto | Gestión de un par de claves | La API emite y verifica sus propios tokens: no hay terceros |
| PyJWT a mano en lugar de flask-jwt-extended | Menos dependencias | Más código de seguridad propio (lectura del encabezado, vencimiento, errores) | La extensión es estándar en Flask y sus callbacks permiten responder con el envelope del contrato |

## Consecuencias

### Positivas

- El proceso de Bonita no maneja tokens: se configura la autenticación del conector y el token
  se renueva solo, aunque el caso dure semanas.
- Las credenciales viven en un solo lugar por cliente (`cuentas`), con contraseñas hasheadas
  (scrypt de Werkzeug). Desactivar una cuenta invalida sus tokens al instante.
- La trazabilidad por persona se mantiene (historiales con cuenta, usuario de Bonita y caso) sin
  copiar contraseñas.
- Swagger permite autenticarse de las dos formas desde el botón *Authorize*.

### Negativas

- `/login` en modo OAuth2 responde errores con el formato del RFC 6749 y no con el envelope del
  proyecto: es la única excepción del contrato de errores.
- `X-Usuario-Bonita` es una afirmación de Bonita, no una identidad verificada por la API. Se
  acepta porque Bonita es un cliente de confianza (patrón de subsistema de confianza).
- El conector de Bonita guarda el token en memoria hasta que vence: si se rota `JWT_SECRET_KEY`,
  las llamadas fallan con 401 hasta que Bonita pide uno nuevo (como máximo, la vida del token).
- No hay límite de intentos en `/login`. Para un trabajo académico se acepta; en producción
  haría falta rate limiting.

### Qué nos obliga a hacer

- Todo endpoint nuevo usa el `Blueprint` de `app.core.acceso` y `@blp.requiere_rol(...)`.
  `tests/test_rutas_protegidas.py` falla si una ruta responde sin token.
- `JWT_SECRET_KEY` es obligatoria (mínimo 32 caracteres) en todos los entornos.
- Las cuentas se crean con `flask cuentas`, nunca con un endpoint público, y sus credenciales no
  se commitean: las de la entrega van en el documento de la entrega.
- Cada conector REST de Bonita que llame a la API usa el modo OAUTH2 (Client Credentials) con
  los parámetros del proceso (`docs/contratos/autenticacion.md`, sección 7).
