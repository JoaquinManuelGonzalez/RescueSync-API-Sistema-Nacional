# Contrato del padrón de ONGs y las organizaciones

Endpoints del módulo `app/modulos/organizaciones`: el padrón nacional (alta y estado de
habilitación), los catálogos, la disponibilidad de recursos y la carga de inventario y
certificaciones. La autenticación y los roles están en [autenticación](autenticacion.md); los
errores usan el envelope de [errores](errores.md).

| Método | Ruta | Rol | Qué hace |
|---|---|---|---|
| `POST` | `/ongs` | `administrador` | Da de alta una organización en el padrón (nace `pendiente`) |
| `GET` | `/ongs/{cuit}` | `sistema`, `administrador` | Consulta una organización por CUIT y su estado |
| `PATCH` | `/ongs/{cuit}/habilitacion` | `administrador` | Habilita o suspende una organización |
| `GET` | `/ongs/{cuit}/habilitacion/historial` | `sistema`, `administrador` | Todos los cambios de estado, con quién los hizo |
| `GET` | `/ongs` | `sistema`, `administrador` | ONGs habilitadas, con filtros por certificación |
| `GET` | `/certificaciones` | `sistema`, `administrador` | Catálogo de certificaciones |
| `GET` | `/recursos/disponibilidad` | `sistema`, `administrador` | Disponibilidad de recursos no consumibles, sumada entre todas las organizaciones |
| `GET` | `/ongs/{cuit}/recursos/disponibilidad` | `sistema`, `administrador` | Disponibilidad de recursos no consumibles de una organización |
| `POST` | `/ongs/{cuit}/inventario` | `administrador` | Agrega un ítem y su cantidad al inventario de una organización |
| `POST` | `/ongs/{cuit}/certificaciones` | `administrador` | Asigna una certificación y su nivel a una organización |

## 1. Reglas comunes

- **CUIT.** `{cuit}` y el campo `cuit` aceptan 11 dígitos con o sin guiones (`30-65432198-7` o
  `30654321987`) y se guardan como `NN-NNNNNNNN-N`. No se valida el dígito verificador: los CUIT
  de demostración son ficticios y son la clave con la que la aplicación web cruza sus
  organizaciones. Un CUIT que no tiene 11 dígitos responde 400; uno con formato válido que no
  está en el padrón, 404.
- **Ids.** Todos los `id` son UUID ([ADR-006](../adr/ADR-006-claves-uuid.md)). Los de ítems y
  certificaciones del catálogo son fijos (UUIDv5 de su clave natural) y valen en cualquier base;
  los de organizaciones, inventarios y asignaciones dependen de cada base. Un `item_id` o
  `certificacion_id` que no es UUID responde 400 con `"Debe ser un UUID válido."`.
- **Paginación.** Las consultas de listado reciben `pagina` (desde 1, por defecto 1) y
  `por_pagina` (1 a 100, por defecto 20), y responden
  `{"elementos": [...], "pagina": 1, "por_pagina": 20, "total": 37}`.
- **Tipos de organización.** `ong` u `organismo_rescate` (municipios y centros coordinadores).
  Solo una `ong` `habilitada` puede ofertar y comprometer recursos.
- **Niveles de certificación**, de menor a mayor: `baja`, `media`, `alta`, `crítica` (con tilde,
  tal como se escribe en el JSON).
- **Tipos de recurso y de certificación:** `personal_medico`, `rescate`, `alimentos`, `agua`,
  `abrigo`, `medicamentos`, `maquinaria` y `otro`. Una certificación habilita los recursos de su
  mismo tipo.

## 2. Padrón

### `POST /ongs` — alta (onboarding)

```json
{
  "cuit": "30-71555444-2",
  "nombre": "Red Solidaria Chascomús",
  "tipo": "ong",
  "mail_contacto": "contacto@redsolidaria.ej",
  "telefono_contacto": "+54 2241 555-444"
}
```

`tipo` es opcional (por defecto `ong`) y `telefono_contacto` también. La organización nace
`pendiente`: no puede ofertar hasta que un administrador la habilite. El alta queda en el
historial con el motivo "Alta en el padrón nacional.".

| HTTP | Código | Cuándo |
|---|---|---|
| 201 | — | Organización creada, con el formato de `GET /ongs/{cuit}` |
| 400 | `SOLICITUD_INVALIDA` | Falta un campo, el CUIT no tiene 11 dígitos o el mail no es válido |
| 409 | `CONFLICTO_DE_ESTADO` | Ya hay una organización con ese CUIT, nombre o mail (sin distinguir mayúsculas). `detalle.campo` dice cuál |

### `GET /ongs/{cuit}` — consulta

```json
{
  "id": "0193f4a2-7c1e-7b5d-9a3f-2e8c4b6d1a06",
  "cuit": "30-99999999-4",
  "nombre": "Cruz Roja Argentina - Filial Bahía Blanca",
  "tipo": "ong",
  "mail_contacto": "semillas+30999999994@rescuesync.example",
  "telefono_contacto": null,
  "estado_habilitacion": "suspendida",
  "habilitada": false,
  "motivo_estado": "Certificación sanitaria vencida (dato de demostración).",
  "actualizada_en": "2026-11-17T20:00:00+00:00"
}
```

`habilitada` es `true` solo si la organización puede ofrecer y comprometer recursos.
`motivo_estado` es el motivo del último cambio de estado.

### `PATCH /ongs/{cuit}/habilitacion` — cambio de estado

```json
{"estado": "suspendida", "motivo": "Certificación sanitaria vencida."}
```

`motivo` es obligatorio al suspender (hasta 500 caracteres) y queda en el historial. Las
transiciones permitidas son:

| Desde | Hacia |
|---|---|
| `pendiente` | `habilitada` o `suspendida` |
| `habilitada` | `suspendida` |
| `suspendida` | `habilitada` |

Nunca se vuelve a `pendiente`. La fila se bloquea durante el cambio, así que dos pedidos
simultáneos se ordenan y cada uno valida contra el estado real.

| HTTP | Código | Cuándo |
|---|---|---|
| 200 | — | Estado cambiado. Responde la organización actualizada |
| 400 | `SOLICITUD_INVALIDA` | Estado desconocido, suspensión sin motivo o CUIT mal formado |
| 404 | `RECURSO_NO_ENCONTRADO` | El CUIT no está en el padrón |
| 409 | `CONFLICTO_DE_ESTADO` | La organización ya está en ese estado o la transición no está permitida. `detalle` trae `estado_actual`, `estado_pedido` y `transiciones_permitidas` |

### `GET /ongs/{cuit}/habilitacion/historial`

Devuelve `{"cuit": ..., "estado_actual": ..., "registros": [...]}`, con cada cambio en orden de
alta. Cada registro tiene
`estado_anterior` (`null` en el alta), `estado_nuevo`, `motivo`, `cuenta` (la cuenta de la API que
hizo el cambio, `null` en semillas y migraciones), `usuario_bonita`, `caso_bonita` (si el cambio
llegó desde Bonita con las cabeceras de [trazabilidad](autenticacion.md#6-trazabilidad)) y
`fecha`.

## 3. Catálogos y consultas

### `GET /ongs` — ONGs habilitadas

Lista las organizaciones de tipo `ong` en estado `habilitada`, ordenadas por nombre, con sus
certificaciones (`id`, `nombre`, `nivel_certificacion`). Filtros opcionales:

- `certificacion_id` (UUID): solo las que tienen esa certificación.
- `nivel_certificacion`: solo las que tienen alguna certificación con ese nivel.

Los dos filtros se aplican por separado: con los dos, la ONG tiene que tener esa certificación y,
además, alguna certificación con ese nivel (no necesariamente la misma).

### `GET /certificaciones` — catálogo

Devuelve las certificaciones del Sistema Nacional (`id`, `nombre`, `tipo`), paginadas. Los ids
son fijos: sirven para `POST /ongs/{cuit}/certificaciones` y para el filtro de `GET /ongs`.

### Disponibilidad de recursos

`GET /recursos/disponibilidad` suma el inventario de todas las organizaciones por recurso;
`GET /ongs/{cuit}/recursos/disponibilidad` muestra el de una sola. Los dos aceptan el filtro
`tipo` y la paginación, y listan **solo recursos no consumibles**: la API no lleva el stock de los
consumibles (comprometerlos no descuenta inventario), así que no tienen disponibilidad. Filtrar
por un tipo consumible, como `agua`, devuelve la lista vacía.

```json
{
  "id": "…UUIDv5 del ítem…",
  "nombre": "Paramédicos",
  "tipo": "personal_medico",
  "unidad_medida": "personas",
  "consumible": false,
  "disponible": 8,
  "comprometido": 2,
  "total": 10
}
```

`disponible` es lo que queda para comprometer, `comprometido` lo que tienen reservado los
compromisos activos (estado `COMPROMETIDO`) y siempre vale `total = disponible + comprometido`.

## 4. Carga de inventario y certificaciones

### `POST /ongs/{cuit}/inventario`

```json
{"item_id": "…UUIDv5 del ítem…", "cantidad_disponible": 5}
```

Agrega un ítem del catálogo al inventario de la organización (lo crea si no tenía).
`cantidad_disponible` es un entero mayor o igual a 0. Responde 201 con `id`, `item_id`,
`item_nombre` y `cantidad_disponible`. El ítem tiene que existir (404) y no estar cargado ya en esa
organización (409). Para cambiar la cantidad de un ítem ya cargado no hay endpoint.

### `POST /ongs/{cuit}/certificaciones`

```json
{"certificacion_id": "…UUIDv5 de la certificación…", "nivel_certificacion": "alta"}
```

Asigna la certificación con su nivel y la fecha de emisión actual. Responde 201 con `id`,
`certificacion_id`, `certificacion_nombre`, `nivel_certificacion` y `fecha_emision`. La
certificación tiene que existir (404) y no estar asignada ya (409). Un nivel que no es `baja`,
`media`, `alta` ni `crítica` responde 400.

## 5. Datos de demostración

`flask seed` (en cada arranque del contenedor y en cada deploy de Render) carga el padrón con las
mismas organizaciones, CUIT y tipo que la aplicación web:

| Organización | CUIT | Tipo | Estado inicial |
|---|---|---|---|
| Cruz Solidaria | `30-65432198-7` | `ong` | `habilitada` |
| Manos Unidas | `30-65432199-5` | `ong` | `habilitada` |
| Cruz Roja Argentina - Filial Bahía Blanca | `30-99999999-4` | `ong` | `suspendida` (a propósito) |
| Bomberos Voluntarios de La Plata | `30-99999999-5` | `ong` | `habilitada` |
| Grupo Scouts de Pergamino | `30-99999999-6` | `ong` | `habilitada` |
| Municipio de Chascomús | `30-71234567-9` | `organismo_rescate` | `habilitada` |
| Municipalidad de Bahía Blanca | `30-99999999-1` | `organismo_rescate` | `habilitada` |
| Municipalidad de La Plata | `30-99999999-2` | `organismo_rescate` | `habilitada` |
| Municipalidad de Pergamino | `30-99999999-3` | `organismo_rescate` | `habilitada` |
| Centro Coordinador Regional Buenos Aires | `30-70987654-3` | `organismo_rescate` | `habilitada` |

Cruz Roja arranca suspendida para mostrar el caso de una ONG que oferta en la web y el Sistema
Nacional rechaza. Certificaciones e inventarios más usados en las pruebas:

| ONG | Certificaciones (nivel) | Inventario no consumible |
|---|---|---|
| Cruz Solidaria | atención sanitaria, distribución de alimentos, abastecimiento de agua (alta) | 10 paramédicos |
| Manos Unidas | asistencia humanitaria (abrigo), distribución de medicamentos (media) | — |
| Cruz Roja | atención sanitaria, respuesta ante emergencias, logística de maquinaria (alta) | 15 paramédicos, 8 enfermeros, 5 ambulancias, 1 camión |
| Bomberos Voluntarios | respuesta ante emergencias, logística de maquinaria, atención sanitaria (alta) | 25 rescatistas, 3 perros, 1 retroexcavadora, 2 camiones, 1 ambulancia, 4 generadores |
| Scouts | distribución de alimentos, apoyo logístico (alta) | 40 voluntarios generales, 10 carpas, 30 colchones |

El seed crea lo que falta sin duplicar, corrige los datos de referencia del catálogo y el tipo de
las organizaciones, y **repone** el stock de demostración que quedó por debajo de su cantidad
inicial. Nunca baja una cantidad ni cambia el estado de habilitación de una organización que ya
existía. Por eso la base compartida de Supabase puede diferir de esta tabla (por ejemplo, si
alguien habilitó a Cruz Roja o subió un stock); la colección Postman no depende de esos valores.
