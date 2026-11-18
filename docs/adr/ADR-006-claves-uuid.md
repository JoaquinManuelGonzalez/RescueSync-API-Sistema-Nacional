# ADR-006: Claves UUID en todas las entidades

- Estado: Propuesto
- Fecha: 2026-11-17
- Reemplaza a: —
- Reemplazado por: —

## Contexto

Todas las tablas de la API usaban claves enteras autoincrementales, y lo mismo pasaba en la
aplicación web. Mientras cada sistema tenía su propia base, no era un problema. Pero la API
del Sistema Nacional es **una sola** (Render + Supabase) y la usan varias aplicaciones web
locales, una por integrante del equipo, más la del profesor, que arranca de `flask seed`.

La clave de un compromiso de recursos es la emergencia de la web (`emergencia_externa_id`, que
Bonita reenvía) junto con la ONG. Cada web numera sus emergencias desde 1, así que la
emergencia `1` de un integrante y la `1` de otro eran, para la API, la misma emergencia:

- la segunda evaluación chocaba con el compromiso de la primera (409);
- liberar o finalizar la emergencia de un integrante devolvía el stock comprometido por otro;
- una emergencia ya finalizada por alguien dejaba la misma numeración inutilizable para todos.

Limpiar la base antes de cada prueba solo esconde el problema, y no sirve cuando varias
personas prueban a la vez contra la misma API.

## Decisión

Todas las claves primarias y foráneas de la API son UUID (tipo `uuid` de PostgreSQL, `Uuid` de
SQLAlchemy), y la API exige un UUID para identificar una emergencia. La aplicación web hizo el
mismo cambio en todas sus tablas (su ADR-011), así que el id que viaja a Bonita y a la API no se repite entre
entornos.

- **Filas nuevas: UUIDv7** (`app/core/identificadores.py:nuevo_id`, `uuid.uuid7()` de
  Python 3.14). Lleva la hora al principio: ordenar por `id` sigue siendo ordenar por fecha de
  alta y el índice crece al final, como con un entero.
- **Catálogo: UUIDv5** de su clave natural (`id_de_item(codigo_recurso)`,
  `id_de_certificacion(nombre, tipo)`). El mismo recurso tiene el mismo id en todas las bases,
  así que los ejemplos de Swagger y la colección Postman valen en cualquiera. El espacio de
  nombres (`ESPACIO_SISTEMA_NACIONAL`) no se cambia nunca.
- **`emergencia_externa_id` sigue siendo una columna de texto.** Es un id de otro sistema, no
  una clave de esta base: se guarda el UUID en forma canónica (minúsculas y con guiones), que es
  la misma que usan la evaluación, la liberación y la finalización. Un UUID mal formado en el
  cuerpo responde 400; en la ruta (`<uuid:...>`), 404.
- **Migración sin pérdida de datos** (`5b9d3e7a1c42`): convierte cada clave y sus foráneas,
  rehace las restricciones e índices con el mismo nombre y tiene downgrade. Se probó con una
  copia de la base de Supabase en los dos sentidos. La migración `8c3f1e5a7b20` cierra los
  compromisos viejos con ids que no son UUID, que ya no se podían liberar.

### Versión fijada

| Tecnología | Versión | Archivo del repositorio donde se fija |
|---|---|---|
| Python (`uuid.uuid7`) | 3.14 | `pyproject.toml`, `.python-version`, `Dockerfile` |
| SQLAlchemy (`Uuid`) | 2.0.54 | `pyproject.toml` |

### Alternativas consideradas

| Alternativa | A favor | En contra | Motivo del descarte |
|---|---|---|---|
| Limpiar la base antes de la evaluación | Sin cambios de código | No evita el choque entre integrantes que prueban a la vez; hay que acordarse cada vez | Mitiga, no resuelve |
| Prefijar el id de emergencia con el entorno (`juan-1`) | Cambio chico | Depende de que cada web se configure bien; el profesor no tiene prefijo propio | Frágil |
| Columna UUID aparte y claves enteras | Menos migración | Dos identificadores por entidad; el entero sigue tentando a usarse entre sistemas | Duplica sin ganar nada |
| UUIDv4 para todo | Estándar, sin dependencias | Inserciones al azar en el índice; ordenar por id ya no es orden de alta; el catálogo cambia de id en cada base | v7 y v5 resuelven las dos cosas |

## Consecuencias

### Positivas

- Varias webs pueden usar la misma API a la vez sin pisarse los compromisos.
- Los ids del catálogo son estables: los ejemplos de Swagger y Postman funcionan en cualquier
  base.
- `order_by(id)` conserva su significado, así que ninguna consulta tuvo que cambiar de orden.

### Negativas

- **Cambio incompatible:** las webs y el proceso de Bonita anteriores a este cambio dejan de
  funcionar contra la API (mandan enteros, que responden 400 o 404). Los tres repositorios se
  despliegan juntos.
- Los ids son largos para leer y escribir a mano en Swagger. Se copian de una respuesta
  anterior.
- Los compromisos viejos quedan en la base como `LIBERADO`, sin poder asociarse a ninguna
  emergencia actual.

### Qué nos obliga a hacer

- Toda tabla nueva usa `Uuid` con `default=nuevo_id`. Las rutas con ids usan `<uuid:...>` y los
  schemas, `fields.UUID`.
- Un ítem o certificación nuevo del catálogo toma su id de `id_de_item` / `id_de_certificacion`
  en la semilla, nunca de `nuevo_id`.
- El CI corre `flask db check` para que las migraciones y los modelos no se separen.
