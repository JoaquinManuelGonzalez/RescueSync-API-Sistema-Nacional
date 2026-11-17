# Evaluación de ofertas por competencia

Bonita envía las ofertas consolidadas a `POST /ofertas/evaluacion` con un token de rol
`sistema`. La evaluación se hace por ítem, no por oferta completa. Una oferta puede ser
individual o un consorcio; en el segundo caso cada miembro se evalúa de manera independiente.

```json
{
  "emergencia_id": 14,
  "nivel_gravedad": "MEDIA",
  "ofertas": [
    {
      "fecha_creacion": "2026-10-16T14:40:44Z",
      "oferta_id": 7,
      "organizaciones": [
        {
          "id": 8,
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
              "organizacion_id": 6
            }
          ],
          "cantidad_total": 2,
          "codigo_recurso": "RSR-ENFERMEROS",
          "lote_item_id": 10,
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
