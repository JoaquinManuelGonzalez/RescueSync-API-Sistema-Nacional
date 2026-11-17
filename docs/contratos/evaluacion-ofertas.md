# Evaluación de ofertas por competencia

Bonita envía las ofertas consolidadas a `POST /ofertas/evaluacion` con un token de rol
`sistema`. La evaluación se hace por ítem, no por oferta completa. Una oferta puede ser
individual o un consorcio; en el segundo caso cada miembro se evalúa de manera independiente.

```json
{
  "emergencia_id": "0193f4a2-7c1e-7e00-9e00-000000000014",
  "nivel_gravedad": "MEDIA",
  "ofertas": [
    {
      "fecha_creacion": "2026-10-16T14:40:44Z",
      "oferta_id": "0193f4a2-7c1e-7f00-9f00-000000000007",
      "organizaciones": [
        {
          "id": "0193f4a2-7c1e-7c00-9c00-000000000008",
          "identificador_nacional": "30-99999999-4",
          "nombre": "Cruz Roja Argentina - Filial Bahía Blanca",
          "rol": "lider"
        }
      ],
      "version": 2,
      "items": [
        {
          "aportes": [
            {
              "cantidad": 2,
              "identificador_nacional": "30-65432198-7",
              "organizacion_id": "0193f4a2-7c1e-7c00-9c00-000000000006"
            }
          ],
          "cantidad_total": 2,
          "codigo_recurso": "RSR-ENFERMEROS",
          "lote_item_id": "0193f4a2-7c1e-7a00-9a00-000000000010",
          "tipo_recurso": "personal_medico",
          "unidad": "personas"
        }
      ]
    }
  ]
}
```

`ofertas` puede ser una lista vacía: pasa cuando la convocatoria cerró sin ofertas presentadas.
En ese caso la API responde `200 OK` con `"ofertas": []` y no compromete nada, para que el proceso
siga y pueda reiniciar la convocatoria. Omitir el campo sigue siendo un 400.

Todos los ids que manda la web son UUID: `emergencia_id`, `oferta_id`, `lote_item_id`,
`organizacion_id` y el `id` de cada organización. Un entero responde 400. `emergencia_id` es la
clave con la que quedan los compromisos, en forma canónica (minúsculas y con guiones), y es la
misma que después usan la liberación y la finalización de
[compromisos](compromisos.md). Que sea un UUID evita que la emergencia `1` de una web local pise
los compromisos de la emergencia `1` de otra que usa la misma API.

Cada ítem consolidado puede tener aportes de varias organizaciones. Para cruzar con el padrón
nacional se usa exclusivamente `identificador_nacional`; `organizacion_id` pertenece al sistema
origen y es únicamente informativo.

El CUIT se busca con o sin guiones: `30654321987` encuentra a `30-65432198-7`. Si un aporte llega
con `identificador_nacional` vacío o en `null` (en la web el dato es opcional), la evaluación no
responde 400: ese aporte sale `rechazada` con el motivo "La organización no informó su
identificador nacional (CUIT)." y el resto se evalúa normalmente. La respuesta repite el
identificador tal como llegó, porque la web cruza el resultado por ese dato. En `organizaciones`
también se acepta `null`.

`version` se recibe como metadato de la oferta de origen, pero no forma parte del resultado de
evaluación. La API tampoco devuelve una clasificación general de la oferta ni del ítem, ni un indicador
global de compromisos. La decisión y el motivo se informan únicamente dentro de cada aporte.

Para cada aporte de cada ítem se busca una certificación cuyo tipo coincida con el tipo del recurso:

| Resultado | Regla |
|---|---|
| `rechazada` | No existe certificación, la organización no informó su CUIT, no está registrada o no está habilitada, o el stock no consumible es insuficiente |
| `apoyo` | Existe certificación, pero su nivel es menor que la gravedad |
| `principal` | La certificación alcanza el nivel de gravedad |

Los recursos consumibles no validan stock en esta etapa. Para los recursos no consumibles,
la cantidad disponible se valida contra el inventario de la organización. Cada ítem no consumible
aceptado (`principal` o `apoyo`) se registra mediante el mismo servicio transaccional que usa
`POST /recursos/compromisos`; por eso el descuento de stock es atómico e idempotente por
emergencia.

Una misma ONG puede ofrecer el mismo recurso en varias líneas de la convocatoria, por ejemplo si
el ítem se pidió en dos lotes. Cada línea se evalúa contra el stock que queda después de las
anteriores, en el orden en que llegan, y la que ya no entra sale `rechazada` con el disponible
restante en el motivo. Lo aceptado se compromete sumado en un único ítem por ONG y recurso.
