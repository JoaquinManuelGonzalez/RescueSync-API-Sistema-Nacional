# Contrato de logging

Formato de los logs de la API del Sistema Nacional. Es el mismo que el de la aplicación web de
RescueSync, para que las trazas de los componentes se puedan leer con las mismas herramientas.

## 1. Formato

Cada evento es **una línea JSON** (JSON Lines) en la salida estándar del contenedor. No se
escriben archivos de log. En local se leen con `docker compose logs -f api`; en la nube, en la
pestaña **Logs** del servicio en Render.

Campos presentes en todo evento:

| Campo | Tipo | Ejemplo |
|---|---|---|
| `timestamp` | string, ISO-8601 UTC con milisegundos | `"2026-10-05T18:04:09.112Z"` |
| `nivel` | `DEBUG`, `INFO`, `WARN` o `ERROR` | `"INFO"` |
| `evento` | string, nombre del evento | `"solicitud_completada"` |

## 2. Eventos

| Evento | Nivel | Campos adicionales |
|---|---|---|
| `solicitud_entrante` | `INFO` | `metodo`, `endpoint`, `id_correlacion` |
| `solicitud_completada` | `INFO` (2xx/3xx), `WARN` (4xx), `ERROR` (5xx) | `metodo`, `endpoint`, `codigo_estado`, `duracion_ms`, `id_correlacion`; en endpoints protegidos, también `cuenta`, `rol` y, si Bonita lo mandó, `caso_bonita` |
| `ingreso_exitoso` | `INFO` | `cuenta`, `rol`, `modo` (`json` o `client_credentials`) |
| `ingreso_fallido` | `WARN` | `motivo` (`credenciales_invalidas` o `cuenta_inactiva`), `modo`. Sin el usuario: puede ser cualquier cosa que alguien tipeó |
| `excepcion_no_contemplada` | `ERROR` | `mensaje` (tipo de la excepción), `id_correlacion` |
| `salud_degradada` | `ERROR` | `mensaje` (tipo del error), `componente` |
| `configuracion_invalida` | `ERROR` | `mensaje` (qué variable falta o es inválida) |

`GET /health` no genera eventos: lo consultan el healthcheck de Docker y el de Render cada pocos
segundos.

```json
{"timestamp": "2026-10-06T11:46:58.001Z", "nivel": "INFO", "evento": "solicitud_entrante", "metodo": "POST", "endpoint": "/recursos/compromisos", "id_correlacion": "caso-1042-tarea-7"}
{"timestamp": "2026-10-06T11:46:58.120Z", "nivel": "INFO", "evento": "solicitud_completada", "metodo": "POST", "endpoint": "/recursos/compromisos", "codigo_estado": 201, "duracion_ms": 119, "id_correlacion": "caso-1042-tarea-7"}
```

## 3. Datos que nunca se registran

Ningún log puede contener el encabezado `Authorization`, tokens, contraseñas, cookies, DNI o
CUIT, nombres y apellidos, correos, teléfonos ni direcciones. Tampoco la cabecera
`X-Usuario-Bonita`, que es el email del usuario web: se guarda en los historiales de la base, no
en los logs. `app/core/logging.py` provee
`redactar()` y `redactar_cabeceras()`, que reemplazan esos campos por `"***"` (incluso anidados)
antes de loguear cualquier cuerpo o encabezado. El cuerpo de las solicitudes no se loguea por
defecto.

## 4. Identificador de correlación

- Se lee del encabezado `X-Correlation-Id` de la solicitud. Bonita puede mandar, por ejemplo,
  el id del caso del proceso, y así una operación se rastrea desde el proceso hasta la API.
- Si no viene, la API genera un UUID.
- Se devuelve siempre en el encabezado `X-Correlation-Id` de la respuesta, aparece en todos los
  eventos de esa solicitud y en el campo `id_correlacion` de cualquier error.

## 5. Niveles

El nivel mínimo se configura con `LOG_LEVEL` (ver `configuracion.md`). En la nube se usa
`INFO`; `DEBUG` queda para el desarrollo local.
