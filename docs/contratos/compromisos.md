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

## `POST /recursos/compromisos/{emergencia_externa_id}/ongs/{identificador_nacional}/finalizacion`

Requiere rol `sistema`. No necesita cuerpo. Registra la finalización de las actividades de una ONG
que participa en esa emergencia. El proyecto permanece abierto hasta que todas las ONGs con
compromisos registrados hayan informado su finalización.

La llamada responde `200 OK` con el estado de avance:

```json
{
  "emergencia_externa_id": "emergencia-2026-0042",
  "identificador_nacional": "30-11111111-1",
  "proyecto_cerrado": false,
  "organizaciones_finalizadas": 1,
  "organizaciones_participantes": 2,
  "repetido": false
}
```

Cuando finaliza la última ONG, el servicio cierra el proyecto en la misma transacción en que marca
los compromisos como liberados. Devuelve al inventario solo los recursos no consumibles; los
consumibles permanecen descontados. Una notificación repetida no cuenta dos veces ni duplica el
reintegro. El campo `repetido` indica si esa ONG ya había notificado la finalización.

| HTTP | Código | Significado |
|---|---|---|
| 200 | — | Finalización registrada o repetición idempotente |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente/inválido o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | No hay compromisos para la emergencia o la ONG no participa |
| 409 | `CONFLICTO_DE_ESTADO` | El estado actual de los compromisos impide completar el cierre |
