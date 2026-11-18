# Contrato de compromiso de recursos

Endpoints del módulo `app/modulos/compromisos`. La API registra y descuenta los recursos que el
proceso ya seleccionó: no elige ofertas ni adjudica. Todos requieren un token de rol `sistema`
(la cuenta de Bonita); la autorización se evalúa antes que el cuerpo. Usan `X-Correlation-Id` y
las cabeceras de trazabilidad de Bonita ([autenticación](autenticacion.md),
[logging](logging.md)).

| Método | Ruta | Qué hace | Lo llama Bonita |
|---|---|---|---|
| `POST` | `/recursos/compromisos` | Compromete todos los aportes indicados, o ninguno | No (ver abajo) |
| `POST` | `/recursos/compromisos/validar` | Dice si esos aportes se podrían comprometer, sin tocar nada | No |
| `POST` | `/recursos/compromisos/{emergencia_externa_id}/liberacion` | Libera todo lo comprometido de la emergencia | *Solicitar liberación de recursos reservados* (reinicio) |
| `POST` | `/recursos/compromisos/{emergencia_externa_id}/ongs/{identificador_nacional}/liberacion` | Libera lo comprometido de una ONG | *Liberar ofertas no seleccionadas* (script Groovy) |
| `POST` | `/recursos/compromisos/{emergencia_externa_id}/finalizacion` | Cierra la emergencia y libera lo que quede | *Informar finalización* |

**Quién compromete en el flujo actual.** El proceso no llama a `POST /recursos/compromisos`: la
evaluación de ofertas ([`POST /ofertas/evaluacion`](evaluacion-ofertas.md)) ya compromete los
aportes no consumibles aceptados con el mismo servicio transaccional, bajo
`emergencia_externa_id = emergencia_id`. `POST /recursos/compromisos` sigue disponible para
pruebas (Swagger, Postman) y para un proceso que separe la evaluación del compromiso. Llamarlo
después de evaluar la misma emergencia con otros aportes responde 409.

## Reglas comunes

- **Emergencia.** `emergencia_externa_id` es el UUID de la emergencia en la aplicación web, que
  Bonita reenvía ([ADR-006](../adr/ADR-006-claves-uuid.md)). Tiene que ser un UUID porque es la
  clave de los compromisos y varias webs usan la misma API: con ids enteros, la emergencia `1` de
  un entorno pisaba los compromisos de la de otro. Se guarda en forma canónica (minúsculas y con
  guiones). En el cuerpo se acepta también en mayúsculas o sin guiones, y otro formato responde
  400. En la ruta tiene que ir con guiones (mayúsculas o minúsculas); con otro formato la ruta no
  existe y responde 404.
- **Organización.** Se identifica por `identificador_nacional`, el CUIT, con o sin guiones
  (`30-65432198-7` o `30654321987`).
- **Recurso.** Se identifica por `codigo_recurso`, el código compartido con la aplicación web
  (`RSR-PARAMEDICOS`, `RSR-AGUA_POTABLE_ENVASADA`, ...).
- **Consumibles y no consumibles.** Solo los recursos no consumibles tienen stock en la API:
  comprometerlos descuenta `cantidad_disponible` y liberarlos la devuelve. Un consumible se
  registra en el compromiso, pero no se valida ni se descuenta stock.
- **Estados.** Un compromiso (uno por emergencia y ONG) nace `COMPROMETIDO`. Al liberarse o al
  finalizar la emergencia pasa a `LIBERADO`. La finalización además le pone fecha de cierre a
  todos los compromisos de la emergencia, y desde ahí la emergencia no admite compromisos nuevos.
- **Compromisos anteriores a UUID.** Los registrados con ids como `14` o
  `emergencia-postman-01` quedaron cerrados por la migración `8c3f1e5a7b20`: figuran como
  `LIBERADO` y no cuentan como comprometidos en la disponibilidad.

## `POST /recursos/compromisos`

```json
{
  "emergencia_externa_id": "0193f4a2-7c1e-7b5d-9a3f-2e8c4b6d1a01",
  "nivel_gravedad": "MEDIA",
  "aportes": [
    {
      "identificador_nacional": "30-65432198-7",
      "codigo_recurso": "RSR-PARAMEDICOS",
      "cantidad": 2,
      "tipo_asignacion": "principal"
    },
    {
      "identificador_nacional": "30-65432198-7",
      "codigo_recurso": "RSR-AGUA_POTABLE_ENVASADA",
      "cantidad": 500,
      "tipo_asignacion": "apoyo"
    }
  ]
}
```

- `nivel_gravedad`: `BAJA`, `MEDIA`, `ALTA` o `CRITICA`. También se aceptan las variantes
  internas `BAJO`, `MEDIO`, `ALTO` y `CRITICO`.
- `aportes`: uno o más. `cantidad` es un entero positivo y `tipo_asignacion` es `principal` o
  `apoyo`. No se puede repetir la combinación de organización y recurso dentro de la solicitud.

La operación es **todo o nada**: bloquea las filas de organizaciones e inventario en un orden
estable (dos pedidos simultáneos se serializan) y, si un aporte falla, no descuenta ninguno.

Responde `201 Created` la primera vez y `200 OK` si se repite exactamente el mismo cuerpo para la
misma emergencia (`repetido: true`, sin descontar otra vez):

```json
{
  "emergencia_externa_id": "0193f4a2-7c1e-7b5d-9a3f-2e8c4b6d1a01",
  "repetido": false,
  "compromisos": [
    {
      "identificador_nacional": "30-65432198-7",
      "nivel_gravedad": "MEDIO",
      "estado": "COMPROMETIDO",
      "items": [
        {"codigo_recurso": "RSR-PARAMEDICOS", "cantidad": 2, "tipo_asignacion": "principal"},
        {"codigo_recurso": "RSR-AGUA_POTABLE_ENVASADA", "cantidad": 500, "tipo_asignacion": "apoyo"}
      ]
    }
  ]
}
```

La respuesta devuelve `nivel_gravedad` con su valor interno (`MEDIO`).

| HTTP | Código | Cuándo |
|---|---|---|
| 201 | — | Compromiso creado |
| 200 | — | Reintento idéntico: no vuelve a descontar |
| 400 | `SOLICITUD_INVALIDA` | Cuerpo incompleto o inválido (por ejemplo, sin aportes o con una cantidad no positiva), o `emergencia_externa_id` que no es UUID |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente o inválido, o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | Organización o código de recurso inexistente |
| 409 | `CONFLICTO_DE_ESTADO` | La emergencia ya tiene un compromiso distinto, con otra gravedad, en otro estado o ya fue finalizada |
| 422 | `REGLA_DE_NEGOCIO_INCUMPLIDA` | Organización no habilitada, recurso no declarado en su inventario, stock insuficiente u organización y recurso repetidos en la solicitud |

La idempotencia se basa en `emergencia_externa_id` y en la igualdad exacta de los aportes. La
cabecera estándar `Idempotency-Key` no está implementada ([errores](errores.md)). Después de
liberar los compromisos para reiniciar la convocatoria, una solicitud nueva puede registrar los
aportes de la nueva vuelta, aunque cambien las organizaciones o las cantidades: los compromisos
liberados se reutilizan.

## `POST /recursos/compromisos/validar`

Mismo cuerpo que `POST /recursos/compromisos`. Verifica si los aportes se podrían comprometer
**sin modificar nada** (ni stock ni compromisos). No valida contra los compromisos existentes de
la emergencia.

```json
{
  "valido": false,
  "motivos": [
    {
      "identificador_nacional": "30-65432198-7",
      "codigo_recurso": "RSR-PARAMEDICOS",
      "cantidad_solicitada": 999,
      "cantidad_disponible": 8,
      "motivo": "stock_insuficiente"
    }
  ]
}
```

`motivo` es `organizacion_no_habilitada` (con `codigo_recurso` vacío), `recurso_no_declarado` o
`stock_insuficiente`. Los consumibles nunca dan `stock_insuficiente`.

| HTTP | Código | Cuándo |
|---|---|---|
| 200 | — | Validación hecha: `valido` dice el resultado y `motivos` los problemas |
| 400 | `SOLICITUD_INVALIDA` | Cuerpo incompleto o inválido |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente o inválido, o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | Organización o código de recurso inexistente |
| 422 | `REGLA_DE_NEGOCIO_INCUMPLIDA` | Organización y recurso repetidos en la solicitud |

## `POST /recursos/compromisos/{emergencia_externa_id}/liberacion`

No necesita cuerpo. Libera todos los compromisos activos de la emergencia y devuelve al inventario
los recursos no consumibles. Bonita la llama cuando se decide **reiniciar la convocatoria**: no
cierra la emergencia, que puede volver a comprometer en la vuelta siguiente.

Responde `200 OK` con los compromisos de la emergencia. `repetido` es `true` si ya estaban todos
liberados; los reintentos no vuelven a sumar inventario. Si hubo liberaciones por ONG, libera los
activos que quedan sin reintegrar dos veces los ya liberados.

Si la emergencia **no tiene compromisos**, también responde `200 OK`, con `"compromisos": []` y
`"repetido": false`. Es el caso habitual al reiniciar una vuelta que no comprometió nada (solo
hubo consumibles, se rechazó todo o no hubo ofertas): el conector de Bonita falla ante cualquier
4xx, y el proceso usa esta llamada para asegurarse de que no quede nada reservado.

| HTTP | Código | Cuándo |
|---|---|---|
| 200 | — | Recursos liberados, repetición o nada que liberar |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente o inválido, o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | `{emergencia_externa_id}` no es un UUID (la ruta no existe) |
| 409 | `CONFLICTO_DE_ESTADO` | Hay compromisos en un estado que no se puede liberar |

## `POST /recursos/compromisos/{emergencia_externa_id}/ongs/{identificador_nacional}/liberacion`

No necesita cuerpo. Libera el compromiso de una ONG en la emergencia: los no consumibles vuelven
al inventario. Responde `200 OK` con ese compromiso; las repeticiones son idempotentes
(`repetido: true`) y no reintegran de nuevo.

La liberación es **por ONG, no por ítem**: abarca todo lo que la evaluación le comprometió a esa
ONG en la emergencia. Por eso, al confirmar la selección, el proceso la invoca solo para las ONG
que el Sistema Nacional evaluó y que no tienen ninguna línea seleccionada (la web arma esa lista,
`ongsNoSeleccionadas`), una vez por cada una. Una ONG con al menos una línea seleccionada no se
libera, aunque tenga otras sin seleccionar o una oferta rechazada: perdería lo adjudicado.

> **Limitación aceptada.** Si una ONG tiene algunas líneas seleccionadas y otras no, los recursos
> no consumibles de las no seleccionadas siguen comprometidos hasta la finalización de la
> emergencia y, mientras tanto, no figuran como disponibles para otras emergencias. Liberarlos
> antes requeriría una liberación por ítem, que la API no ofrece.

Una ONG evaluada puede no tener compromiso, porque todos sus aportes eran consumibles o fueron
rechazados. En ese caso responde 404, y el script de Bonita lo cuenta como "sin compromisos" y
sigue con la ONG siguiente.

| HTTP | Código | Cuándo |
|---|---|---|
| 200 | — | Compromiso liberado o repetición |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente o inválido, o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | No hay compromiso para esa ONG y emergencia, o la emergencia no es un UUID |
| 409 | `CONFLICTO_DE_ESTADO` | El estado del compromiso impide liberarlo |

## `POST /recursos/compromisos/{emergencia_externa_id}/finalizacion`

No necesita cuerpo. Bonita la llama cuando terminaron todas las tareas de la emergencia. Cierra la
emergencia y libera sus compromisos activos en una sola transacción; los ya liberados se incluyen
en el cierre sin reintegrar otra vez su inventario.

```json
{
  "emergencia_externa_id": "0193f4a2-7c1e-7b5d-9a3f-2e8c4b6d1a01",
  "proyecto_cerrado": true,
  "organizaciones_finalizadas": 2,
  "organizaciones_participantes": 2,
  "repetido": false
}
```

`organizaciones_participantes` cuenta las ONG con compromiso en la emergencia; todas quedan
finalizadas con la confirmación del proceso. Una llamada repetida no duplica el reintegro y
responde `repetido: true`.

Si todos los compromisos ya estaban liberados (se descartaron todas las ONG con no consumibles, o
hubo un reinicio y la vuelta nueva no comprometió nada), la emergencia también se cierra con
`200 OK` y `repetido: false`, sin mover inventario.

| HTTP | Código | Cuándo |
|---|---|---|
| 200 | — | Emergencia finalizada o repetición |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente o inválido, o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | La emergencia no tiene compromisos (por ejemplo, solo hubo consumibles), o no es un UUID |
| 409 | `CONFLICTO_DE_ESTADO` | Hay compromisos en un estado incompatible o un cierre parcial |

El conector *Finalizar emergencia en Sistema Nacional* no falla ante 4xx ni 5xx: un 404 (nada que
cerrar) no traba el proceso.
