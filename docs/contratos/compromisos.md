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
  "emergencia_externa_id": "0193f4a2-7c1e-7b5d-9a3f-2e8c4b6d1a01",
  "nivel_gravedad": "MEDIA",
  "aportes": [
    {
      "identificador_nacional": "30-65432198-7",
      "codigo_recurso": "RSR-AGUA_POTABLE_ENVASADA",
      "cantidad": 500,
      "tipo_asignacion": "principal"
    }
  ]
}
```

- `emergencia_externa_id`: UUID de la emergencia en la aplicación web, que Bonita reenvía. Tiene
  que ser un UUID porque es la clave de los compromisos y varias webs usan la misma API: un id
  entero (la emergencia `1` de cada entorno) pisaría los compromisos de otro. Otro formato
  responde 400. Se guarda en forma canónica (minúsculas y con guiones), así que mandarlo en
  mayúsculas da lo mismo.
- `nivel_gravedad`: `BAJA`, `MEDIA`, `ALTA` o `CRITICA`. También se aceptan las variantes
  internas `BAJO`, `MEDIO`, `ALTO` y `CRITICO`.
- `aportes`: uno o más recursos ya seleccionados. Cada uno identifica la ONG por su identificador
  nacional (el CUIT, con o sin guiones) y el recurso por `codigo_recurso`; la cantidad debe ser un
  entero positivo.
- `tipo_asignacion`: `principal` o `apoyo`.
- No se permite repetir la combinación de organización y recurso dentro de la solicitud.

### Respuesta

`201 Created` en el primer procesamiento. `200 OK` si se repite el mismo cuerpo para la misma
emergencia. En ambos casos se devuelve un resumen de compromisos con su estado e ítems; `repetido`
indica si se reutilizó el resultado anterior.

```json
{
  "emergencia_externa_id": "0193f4a2-7c1e-7b5d-9a3f-2e8c4b6d1a01",
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
[el contrato de errores](errores.md). Luego de liberar los compromisos para reiniciar la
convocatoria, una nueva solicitud puede registrar los aportes de la nueva vuelta, incluso si
cambiaron las organizaciones o cantidades. Los compromisos liberados existentes se reutilizan;
una emergencia finalizada globalmente no admite nuevos compromisos.

En los endpoints que siguen, `{emergencia_externa_id}` también es un UUID: con otro formato la
ruta no existe y la API responde 404. Los compromisos registrados antes de pasar a UUID (con ids
como `14` o `emergencia-postman-01`) quedaron cerrados por la migración `8c3f1e5a7b20`: figuran
como `LIBERADO` y no cuentan como comprometidos en la disponibilidad.

## `POST /recursos/compromisos/{emergencia_externa_id}/liberacion`

Requiere rol `sistema`. No necesita cuerpo. Libera todos los compromisos de la emergencia
indicada y devuelve al inventario los recursos no consumibles. Se usa cuando el proceso decide
reiniciar la convocatoria completa; no registra la finalización de la emergencia.

Responde `200 OK` con los compromisos liberados. El campo `repetido` es `true` si ya estaban
liberados, y los reintentos no vuelven a incrementar el inventario. Si ya hubo liberaciones
selectivas, libera los compromisos activos restantes sin volver a reintegrar los ya liberados.

Si la emergencia no tiene compromisos, también responde `200 OK`, con `"compromisos": []` y
`"repetido": false`. Es el caso habitual al reiniciar tras una vuelta que no comprometió nada
(solo hubo consumibles, se rechazó todo o no hubo ofertas): el proceso usa esta llamada para
asegurarse de que no quede nada reservado, y el conector de Bonita falla ante cualquier 4xx.

| HTTP | Código | Significado |
|---|---|---|
| 200 | — | Recursos liberados, solicitud repetida o nada que liberar |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente/inválido o rol distinto de `sistema` |
| 409 | `CONFLICTO_DE_ESTADO` | El estado actual de los compromisos impide liberar |

## `POST /recursos/compromisos/{emergencia_externa_id}/ongs/{identificador_nacional}/liberacion`

Requiere rol `sistema`. No necesita cuerpo. Libera todos los recursos comprometidos por una ONG
para una emergencia. Los recursos no consumibles vuelven al inventario y los consumibles
permanecen descontados. `{identificador_nacional}` es el CUIT de la ONG, con o sin guiones
(`30-65432198-7` o `30654321987`).

La liberación es **por ONG, no por ítem**: abarca todo lo que la evaluación le comprometió a esa
ONG en la emergencia. Por eso, al confirmar la selección, el proceso la invoca solo para las ONG
que el Sistema Nacional evaluó y no tienen ninguna línea seleccionada (la web arma esa lista,
`ongsNoSeleccionadas`). En un consorcio, la invoca una vez por cada una de esas organizaciones.
Una ONG con al menos una línea seleccionada no se libera, aunque tenga otras sin seleccionar o
una oferta rechazada: perdería lo adjudicado.

> **Limitación aceptada.** Si una ONG tiene algunas líneas seleccionadas y otras no, los recursos
> no consumibles de las líneas no seleccionadas siguen comprometidos hasta la finalización de la
> emergencia (`POST /recursos/compromisos/{emergencia_externa_id}/finalizacion`). Hasta entonces
> no figuran como disponibles para otras emergencias. Liberarlos antes requeriría una liberación
> por ítem, que la API no ofrece.

Responde `200 OK` con el compromiso liberado. Las repeticiones son idempotentes (`repetido: true`)
y no reintegran recursos de nuevo. Una ONG evaluada puede no tener compromiso, porque todos sus
aportes eran consumibles o fueron rechazados. En ese caso responde 404, y el script de Bonita lo
cuenta como "sin compromisos" y sigue con la ONG siguiente.

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
  "emergencia_externa_id": "0193f4a2-7c1e-7b5d-9a3f-2e8c4b6d1a01",
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

Si todos los compromisos ya estaban liberados (se descartaron todas las ONG con no consumibles, o
hubo un reinicio y la vuelta nueva no comprometió nada), la emergencia también se cierra con
`200 OK` y `repetido: false`, sin mover inventario. Desde ese momento no admite nuevos
compromisos.

| HTTP | Código | Significado |
|---|---|---|
| 200 | — | Emergencia finalizada o repetición idempotente |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente/inválido o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | No hay compromisos para la emergencia |
| 409 | `CONFLICTO_DE_ESTADO` | El estado actual de los compromisos impide completar el cierre |
