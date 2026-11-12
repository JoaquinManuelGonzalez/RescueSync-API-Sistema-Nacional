# Contrato de compromiso de recursos

Endpoints iniciales del módulo de compromisos. La API registra y descuenta los recursos que el
proceso ya seleccionó; no elige ofertas, no adjudica recursos y no valida competencias.

## `POST /recursos/compromisos`

Requiere un token con rol `sistema` (la cuenta usada por Bonita). La autorización ocurre antes de
validar el cuerpo. Usa `X-Correlation-Id` y las cabeceras de trazabilidad de Bonita según los
contratos de [autenticación](autenticacion.md) y [logging](logging.md).

### Cuerpo

```json
{
  "emergencia_externa_id": "emergencia-2026-0042",
  "nivel_gravedad": "MEDIA",
  "aportes": [
    {
      "identificador_nacional": "30-11111111-1",
      "codigo_recurso": "RSR-AGUA_POTABLE",
      "cantidad": 500,
      "tipo_asignacion": "principal"
    }
  ]
}
```

- `emergencia_externa_id`: identificador opaco compartido con el proceso, hasta 255 caracteres.
- `nivel_gravedad`: `BAJA`, `MEDIA`, `ALTA` o `CRITICA`. También se aceptan las variantes
  internas `BAJO`, `MEDIO`, `ALTO` y `CRITICO`.
- `aportes`: uno o más recursos ya seleccionados. Cada uno identifica la ONG por su identificador
  nacional y el recurso por `codigo_recurso`; la cantidad debe ser un entero positivo.
- `tipo_asignacion`: `principal` o `apoyo`.
- No se permite repetir la combinación de organización y recurso dentro de la solicitud.

### Respuesta

`201 Created` en el primer procesamiento. `200 OK` si se repite el mismo cuerpo para la misma
emergencia. En ambos casos se devuelve un resumen de compromisos con su estado e ítems; `repetido`
indica si se reutilizó el resultado anterior.

```json
{
  "emergencia_externa_id": "emergencia-2026-0042",
  "repetido": false,
  "compromisos": [
    {
      "identificador_nacional": "30-11111111-1",
      "nivel_gravedad": "MEDIO",
      "estado": "COMPROMETIDO",
      "items": [
        {
          "codigo_recurso": "RSR-AGUA_POTABLE",
          "cantidad": 500,
          "tipo_asignacion": "principal"
        }
      ]
    }
  ]
}
```

La operación es todo-o-nada: si falta una ONG/recurso, la solicitud ya tiene compromisos
incompatibles o no hay stock suficiente, no se descuenta ningún aporte parcial.

| HTTP | Código | Significado |
|---|---|---|
| 201 | — | Compromiso creado |
| 200 | — | Reintento idéntico; no vuelve a descontar |
| 400 | `SOLICITUD_INVALIDA` | Cuerpo incompleto o inválido |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente/inválido o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | Organización o código de recurso inexistente |
| 409 | `CONFLICTO_DE_ESTADO` | La emergencia ya tiene otro compromiso |
| 422 | `REGLA_DE_NEGOCIO_INCUMPLIDA` | Stock insuficiente o regla de dominio incumplida |

La idempotencia inicial se basa en `emergencia_externa_id` y en la igualdad exacta de los datos
del compromiso. La cabecera estándar `Idempotency-Key` queda pendiente; su estado se describe en
[el contrato de errores](errores.md).

## `POST /recursos/compromisos/{emergencia_externa_id}/liberacion`

Requiere rol `sistema`. No necesita cuerpo. Libera todos los compromisos de la emergencia
indicada y devuelve al inventario los recursos no consumibles. Se usa cuando el proceso decide
reiniciar la convocatoria completa; no registra la finalización de la emergencia.

Responde `200 OK` con los compromisos liberados. El campo `repetido` es `true` si ya estaban
liberados, y los reintentos no vuelven a incrementar el inventario.

| HTTP | Código | Significado |
|---|---|---|
| 200 | — | Recursos liberados o solicitud repetida |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente/inválido o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | No hay compromisos para la emergencia |
| 409 | `CONFLICTO_DE_ESTADO` | El estado actual de los compromisos impide liberar |

## `POST /recursos/compromisos/{emergencia_externa_id}/ongs/{identificador_nacional}/liberacion`

Requiere rol `sistema`. No necesita cuerpo. Libera todos los recursos comprometidos por una ONG
para una emergencia. Se usa cuando se descarta la oferta de esa ONG; en un consorcio el proceso
invoca este endpoint una vez por cada organización participante. Los recursos no consumibles
vuelven al inventario y los consumibles permanecen descontados.

Responde `200 OK` con el compromiso liberado. Las repeticiones son idempotentes (`repetido: true`)
y no reintegran recursos de nuevo.

| HTTP | Código | Significado |
|---|---|---|
| 200 | — | Compromiso liberado o solicitud repetida |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente/inválido o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | No hay un compromiso para esa ONG y emergencia |
| 409 | `CONFLICTO_DE_ESTADO` | El estado del compromiso impide liberarlo |

## `POST /recursos/compromisos/{emergencia_externa_id}/finalizacion`

Requiere rol `sistema`. No necesita cuerpo. Bonita invoca el endpoint cuando ya confirmó que
terminaron todas las tareas de la emergencia. La API cierra la emergencia y libera todos sus
compromisos aún activos en una única transacción. Los compromisos ya liberados individualmente
se incluyen en el cierre sin reintegrar nuevamente su inventario.

La llamada responde `200 OK` con el resultado del cierre:

```json
{
  "emergencia_externa_id": "emergencia-2026-0042",
  "proyecto_cerrado": true,
  "organizaciones_finalizadas": 2,
  "organizaciones_participantes": 2,
  "repetido": false
}
```

La respuesta informa cuántas organizaciones tienen compromisos registrados, todas consideradas
finalizadas por la confirmación global del proceso. Devuelve al inventario solo los recursos no
consumibles; los consumibles permanecen descontados. Una llamada repetida no duplica el reintegro;
`repetido` indica si la emergencia ya había sido cerrada.

| HTTP | Código | Significado |
|---|---|---|
| 200 | — | Emergencia finalizada o repetición idempotente |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente/inválido o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | No hay compromisos para la emergencia |
| 409 | `CONFLICTO_DE_ESTADO` | El estado actual de los compromisos impide completar el cierre |
