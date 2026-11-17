# Contrato de evaluación de ofertas por competencia

`POST /ofertas/evaluacion` recibe las ofertas consolidadas de una convocatoria y clasifica cada
aporte como `principal`, `apoyo` o `rechazada`. Lo llama la tarea *Enviar ofertas a Sistema
Nacional* del proceso de Bonita, con un token de rol `sistema`, después de leer las ofertas
consolidadas de la aplicación web.

> **La evaluación modifica datos.** Además de clasificar, **compromete** los aportes no
> consumibles aceptados: descuenta su stock y crea los compromisos de la emergencia, con el mismo
> servicio transaccional que `POST /recursos/compromisos` ([compromisos](compromisos.md)). Ese
> stock vuelve con la liberación (por ONG o de toda la emergencia) o con la finalización.

## Cuerpo

```json
{
  "emergencia_id": "0193f4a2-7c1e-7e00-9e00-000000000014",
  "nivel_gravedad": "ALTA",
  "ofertas": [
    {
      "fecha_creacion": "2026-10-16T14:40:44Z",
      "oferta_id": "0193f4a2-7c1e-7f00-9f00-000000000007",
      "version": 2,
      "organizaciones": [
        {
          "id": "0193f4a2-7c1e-7c00-9c00-000000000006",
          "identificador_nacional": "30-65432198-7",
          "nombre": "Cruz Solidaria",
          "rol": "aportante"
        }
      ],
      "items": [
        {
          "lote_item_id": "0193f4a2-7c1e-7a00-9a00-000000000010",
          "codigo_recurso": "RSR-PARAMEDICOS",
          "tipo_recurso": "personal_medico",
          "unidad": "personas",
          "cantidad_total": 2,
          "aportes": [
            {
              "cantidad": 2,
              "identificador_nacional": "30-65432198-7",
              "organizacion_id": "0193f4a2-7c1e-7c00-9c00-000000000006"
            }
          ]
        }
      ]
    }
  ]
}
```

| Campo | Qué es |
|---|---|
| `emergencia_id` | UUID de la emergencia en la web. Es la clave de los compromisos que crea la evaluación (en forma canónica) y la misma que usan después la liberación y la finalización |
| `nivel_gravedad` | `BAJA`, `MEDIA`, `ALTA` o `CRITICA` (también `BAJO`, `MEDIO`, `ALTO`, `CRITICO`), sin distinguir mayúsculas. Define el nivel de certificación requerido |
| `ofertas` | Ofertas presentadas. **Puede ser una lista vacía** (convocatoria que cerró sin ofertas): responde 200 con `"ofertas": []` y no compromete nada, para que el proceso siga y pueda reiniciar. Omitir el campo es un 400 |
| `oferta_id`, `lote_item_id`, `organizacion_id`, `organizaciones[].id` | UUID de la web. Son informativos: la API los devuelve tal cual, sin cruzarlos con su base |
| `version`, `fecha_creacion`, `organizaciones[].rol`, `nombre` | Metadatos de la oferta de origen. `version` no vuelve en la respuesta |
| `codigo_recurso` | Código compartido con la web. Si no existe en el catálogo de la API, **toda** la evaluación responde 404 |
| `tipo_recurso`, `unidad` | Informativos: para la certificación se usa el tipo del ítem en el catálogo de la API |
| `aportes[].identificador_nacional` | CUIT de la ONG, con o sin guiones. Es lo único que se cruza con el padrón. Puede llegar vacío o `null` (en la web el dato es opcional): ese aporte sale `rechazada` y el resto se evalúa igual. En `organizaciones` también se acepta `null` |
| `aportes[].cantidad`, `cantidad_total` | Enteros positivos |

Un consorcio es una oferta con varias organizaciones; cada aporte se evalúa por separado.

## Reglas

Para cada aporte de cada ítem:

1. **Organización.** Se busca en el padrón por CUIT (con o sin guiones). Tiene que estar
   registrada, ser de tipo `ong` y estar `habilitada`.
2. **Certificación.** Se busca una certificación de la ONG del mismo tipo que el recurso (si tiene
   varias, la de mayor nivel). Los niveles van de `baja` a `crítica`, y la gravedad pide `BAJA` →
   `baja`, `MEDIA` → `media`, `ALTA` → `alta` y `CRITICA` → `crítica`.
3. **Stock.** Si la clasificación no es `rechazada` y el recurso **no es consumible**, la cantidad
   tiene que entrar en el inventario de la ONG. Una misma ONG puede ofrecer el mismo recurso en
   varias líneas (por ejemplo, si el ítem se pidió en dos lotes): cada línea se controla contra lo
   que dejan las anteriores, en el orden en que llegan. Los consumibles no validan stock.

| Clasificación | Cuándo |
|---|---|
| `principal` | La certificación alcanza el nivel requerido (y hay stock, si es no consumible) |
| `apoyo` | Hay certificación, pero de un nivel menor al requerido (y hay stock, si es no consumible) |
| `rechazada` | Falta el CUIT, la organización no está en el padrón, no es una ONG habilitada, no tiene certificación del tipo, o el stock no alcanza |

Al final, los aportes no consumibles `principal` o `apoyo` se comprometen todos juntos, sumados en
un único ítem por ONG y recurso, en una transacción de todo o nada.

## Respuesta

`200 OK` con la misma estructura de ofertas e ítems, y el resultado dentro de cada aporte:

```json
{
  "emergencia_id": "0193f4a2-7c1e-7e00-9e00-000000000014",
  "nivel_gravedad": "ALTA",
  "ofertas": [
    {
      "fecha_creacion": "2026-10-16T14:40:44+00:00",
      "oferta_id": "0193f4a2-7c1e-7f00-9f00-000000000007",
      "organizaciones": ["…las mismas que llegaron…"],
      "items": [
        {
          "lote_item_id": "0193f4a2-7c1e-7a00-9a00-000000000010",
          "codigo_recurso": "RSR-PARAMEDICOS",
          "tipo_recurso": "personal_medico",
          "unidad": "personas",
          "cantidad_total": 2,
          "consumible": false,
          "aportes": [
            {
              "cantidad": 2,
              "identificador_nacional": "30-65432198-7",
              "organizacion_id": "0193f4a2-7c1e-7c00-9c00-000000000006",
              "certificacion_encontrada": true,
              "nivel_riesgo_permitido": "alta",
              "clasificacion": "principal",
              "motivo": "La certificación alcanza el nivel de gravedad requerido.",
              "compromiso_registrado": true
            }
          ]
        }
      ]
    }
  ]
}
```

- `identificador_nacional` se devuelve tal como llegó (recortado), porque la web cruza el
  resultado por ese dato.
- `compromiso_registrado` es `true` si el aporte quedó comprometido (no consumible y aceptado).
- `consumible` sale del catálogo de la API.
- No hay una clasificación general de la oferta ni del ítem: la decisión está en cada aporte.

Los motivos posibles son:

| Motivo | Clasificación |
|---|---|
| La certificación alcanza el nivel de gravedad requerido. | `principal` |
| La certificación tiene un nivel menor al requerido; se asigna como apoyo. | `apoyo` |
| La organización no informó su identificador nacional (CUIT). | `rechazada` |
| La organización no está registrada en el padrón nacional. | `rechazada` |
| La organización está registrada pero no está habilitada para ofertar. | `rechazada` |
| No existe certificación para la capacidad del ítem. | `rechazada` |
| La disponibilidad del ítem no alcanza la cantidad ofertada (N disponible). | `rechazada` |

## Errores

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `SOLICITUD_INVALIDA` | Cuerpo incompleto o inválido, un id que no es UUID, o `nivel_gravedad` desconocido |
| 401 / 403 | `NO_AUTENTICADO` / `PERMISO_DENEGADO` | Token ausente o inválido, o rol distinto de `sistema` |
| 404 | `RECURSO_NO_ENCONTRADO` | Un `codigo_recurso` no existe en el catálogo |
| 409 | `CONFLICTO_DE_ESTADO` | La emergencia ya fue finalizada, o ya tiene compromisos distintos de los que acepta esta evaluación (ver reevaluación) |
| 422 | `REGLA_DE_NEGOCIO_INCUMPLIDA` | Otro pedido se llevó el stock entre la clasificación y el compromiso |

El conector *Enviar ofertas* falla ante cualquier 4xx o 5xx, y la tarea queda en *Failed*.

## Reevaluar la misma emergencia

Evaluar de nuevo una emergencia con el mismo cuerpo (un reintento de Bonita tras un timeout, o
el mismo ejemplo repetido en Swagger) es idempotente **mientras el stock que queda alcance para
lo pedido**: los mismos aportes salen aceptados, el compromiso coincide con el existente y no se
descuenta otra vez.

> **Limitación conocida.** La reevaluación compara lo pedido contra el stock disponible, al que
> ya se le descontó lo que esa misma emergencia comprometió. Si lo que queda no alcanza, el aporte
> sale `rechazada` aunque su compromiso siga vigente; y si otros aportes siguen aceptados, la
> evaluación responde 409 porque el conjunto ya no coincide con el comprometido.

Una emergencia finalizada no admite otra evaluación que comprometa (409). Para probar desde
Swagger o Postman más de una vez sin depender de lo anterior, conviene usar un `emergencia_id`
nuevo. Los ejemplos de Swagger y la carpeta de evaluación de la colección Postman usan UUID fijos:
la primera vez comprometen 2 paramédicos de Cruz Solidaria en la emergencia `…000000000014`, y
las siguientes repiten ese compromiso.
