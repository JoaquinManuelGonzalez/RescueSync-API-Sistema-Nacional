# Contrato de errores

Formato único de error de la API del Sistema Nacional. Es el mismo envelope que usa la
aplicación web de RescueSync. El único consumidor de la API es el motor de Bonita, mediante
conectores REST; la aplicación web nunca la llama directamente.

## 1. Envelope único de error

Todo error, sin excepción, se devuelve con esta estructura JSON:

| Campo | Tipo | Descripción |
|---|---|---|
| `codigo` | string | Código interno estable, en mayúsculas con guion bajo (tabla de la sección 2) |
| `mensaje` | string | Mensaje en español, sin detalles técnicos internos |
| `detalle` | array, objeto o `null` | Información adicional estructurada: campos inválidos, motivo del rechazo, etc. |
| `timestamp` | string, ISO-8601 UTC | Momento en que se generó el error |
| `id_correlacion` | string | El `X-Correlation-Id` recibido, o uno generado por la API (ver `logging.md`) |

```json
{
  "error": {
    "codigo": "REGLA_DE_NEGOCIO_INCUMPLIDA",
    "mensaje": "La ONG no está habilitada para el tipo de recurso ofrecido.",
    "detalle": {"ong_id": 7, "tipo_recurso": "agua_potable"},
    "timestamp": "2026-10-05T18:04:11.482Z",
    "id_correlacion": "8f3a1c22-5d6e-4f19-a0b1-2c3d4e5f6a7b"
  }
}
```

## 2. Tabla de códigos HTTP y códigos internos

| HTTP | Código interno | Cuándo se usa |
|---|---|---|
| 400 | `SOLICITUD_INVALIDA` | El JSON recibido está mal formado o incompleto |
| 401 | `NO_AUTENTICADO` | Faltan credenciales o son inválidas |
| 403 | `PERMISO_DENEGADO` | Las credenciales no habilitan la operación |
| 404 | `RECURSO_NO_ENCONTRADO` | La entidad referenciada no existe, o la ruta no existe |
| 405 | `METODO_NO_PERMITIDO` | El método HTTP no aplica a la ruta |
| 409 | `CONFLICTO_DE_ESTADO` | La entidad no admite la transición pedida (por ejemplo, un recurso ya comprometido) |
| 415 | `TIPO_DE_CONTENIDO_NO_SOPORTADO` | El cuerpo no es JSON |
| 422 | `REGLA_DE_NEGOCIO_INCUMPLIDA` | Falla una validación de dominio (ONG no habilitada, recurso insuficiente) |
| 500 | `ERROR_INTERNO` | Excepción no contemplada |
| 503 | `SERVICIO_NO_DISPONIBLE` | Una dependencia propia (la base de datos) no responde |

Los módulos de dominio pueden definir códigos más específicos subclasificando
`ErrorDeAplicacion` (`app/core/errores.py`), siempre con uno de estos códigos HTTP.

## 3. Qué significa cada familia para Bonita

| Respuesta | Significado | Qué debería hacer el conector de Bonita |
|---|---|---|
| 2xx | Operación realizada | Continuar el flujo |
| 4xx | La API evaluó la solicitud y **la rechazó por su contenido** | **No reintentar** con el mismo cuerpo; tomar el camino de rechazo del proceso |
| 5xx | Falla de disponibilidad | Reintentar con backoff; si persiste, camino de error técnico |
| 503 `SERVICIO_NO_DISPONIBLE` sostenido | La base no responde; en la nube, casi siempre el proyecto de Supabase pausado por inactividad | Camino de error técnico y avisar al equipo: se resuelve reactivando el proyecto (runbook del README), no reintentando |
| Sin respuesta / timeout | El servicio puede estar despertando (plan Free de Render, ~1 minuto) | Reintentar; antes de una demo, despertar con `GET /health` |

Las operaciones que comprometan recursos aceptarán una clave de idempotencia (encabezado
`Idempotency-Key`), para que Bonita pueda reintentar ante un timeout sin comprometer dos veces el
mismo recurso. Se implementa junto con esos endpoints, en una épica posterior.

## 4. Endpoint de salud

`GET /health` no usa el envelope en el caso feliz:

- `200 {"status": "ok", "db": "ok"}` si la aplicación y la base responden.
- `503` con `{"status": "error", "db": "error", "error": {...envelope...}}` si la base no
  responde en 2 segundos.
