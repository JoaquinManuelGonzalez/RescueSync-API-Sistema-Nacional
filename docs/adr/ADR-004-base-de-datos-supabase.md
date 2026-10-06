# ADR-004: Base de datos administrada en Supabase

- Estado: Aceptado
- Fecha: 2026-10-05
- Reemplaza a: ADR-002 (solo la base de datos) y ADR-003 (solo la versión local de PostgreSQL)
- Reemplazado por: —

## Contexto

ADR-002 dejó la API y su base en Render, plan Free. Con el servicio ya desplegado se confirmó
que la **Render Postgres Free expira a los 30 días** de creada (14 días de gracia y después se
borra), no tiene backups y solo puede haber una por workspace. Eso obliga a recrear la base
todos los meses durante el resto de la cursada y a perder lo que tenga cargado, justo cuando
Bonita empieza a integrarse contra el servicio real. ADR-002 ya había dejado abierta la
alternativa de Supabase para este caso.

Fuerzas en juego:

- Sin presupuesto: tiene que ser un plan gratuito.
- No sumar complejidad a la API: el código, el Dockerfile, el `entrypoint.sh` y las migraciones
  no deberían cambiar.
- Render solo sale a internet por **IPv4** (su documentación: "Render does not support IPv6
  addresses yet").
- El web service sigue en Render (ADR-002 no cambia en eso).

## Decisión

La base PostgreSQL pasa a un proyecto de **Supabase**, plan **Free**, en la región
**East US (North Virginia)** (`us-east-1`, la misma zona que el web service de Render). De
Supabase se usa **solo PostgreSQL**: ni Auth, ni Storage, ni su API REST. Para la API es una
URL de PostgreSQL más.

- La API se conecta por el **Session pooler** (Supavisor) de Supabase, puerto 5432, con el
  usuario `postgres.<ref-del-proyecto>`. Es IPv4 en todos los planes y se comporta como una
  conexión común: admite prepared statements y el DDL de Alembic. La conexión directa
  (`db.<ref>.supabase.co`) es solo IPv6 y no se alcanza desde Render.
- TLS obligatorio: `DATABASE_SSLMODE=require` (ya declarado en `render.yaml`).
- `DATABASE_URL` deja de salir de `fromDatabase` y pasa a ser un secreto `sync: false` de
  `render.yaml`, cargado a mano en **Service → Environment** de Render.
- La **Data API de Supabase queda deshabilitada** (Integrations → Data API). Si quedara activa,
  toda tabla que Alembic cree en el esquema `public` sería legible y escribible por REST con la
  clave anónima del proyecto.
- Las migraciones siguen corriendo en `entrypoint.sh` (ADR-003), ahora contra Supabase.
- El PostgreSQL local de `docker-compose.yml` usa el **mismo major que Supabase** en lugar del de
  Render.

`normalizar_url_de_base()` ya convertía `postgresql://` al driver psycopg 3 y agregaba
`sslmode`: no hizo falta cambiar código, solo configuración.

### Versión fijada

| Tecnología | Versión | Archivo del repositorio donde se fija |
|---|---|---|
| Supabase | plan Free, región `us-east-1` | — (dashboard de Supabase; ver README) |
| PostgreSQL (Supabase) | 17 | `docker-compose.yml` (imagen local con el mismo major) |
| Conexión | Session pooler, puerto 5432, `sslmode=require` | `render.yaml` (`DATABASE_URL`, `DATABASE_SSLMODE`) |

### Alternativas consideradas

| Alternativa | A favor | En contra | Motivo del descarte |
|---|---|---|---|
| Seguir con Render Postgres Free | Red privada, todo en un proveedor y en `render.yaml` | Expira a los 30 días, sin backups | Recrear la base cada mes no es sostenible durante la integración con Bonita |
| Conexión directa a Supabase | Sin pooler en el medio | Solo IPv6 (IPv4 es un add-on pago) | Render no tiene salida IPv6 |
| Transaction pooler de Supabase (puerto 6543) | Pensado para muchas conexiones cortas | No admite prepared statements (psycopg 3 los usa) | Pensado para serverless; la API es un servidor persistente |
| Neon (PostgreSQL serverless) | Plan gratuito sin expiración | Otro modelo (cómputo que se suspende sin uso) que el equipo no evaluó | Supabase es la opción que el equipo ya había evaluado en ADR-002 |
| Plan pago de Render Postgres | Sin expiración, red privada, backups | Costo mensual | Sin presupuesto |

## Consecuencias

### Positivas

- La base **no expira**: se termina el runbook mensual de recreación y los datos se conservan.
- La API no cambió: mismo código, misma imagen, mismas migraciones.
- El dashboard de Supabase permite inspeccionar la base (editor de tablas y de SQL) sin abrir
  puertos ni instalar nada.

### Negativas

- El proyecto Free **se pausa tras 7 días sin actividad**. Se reactiva con un clic desde el
  dashboard y los datos se conservan, pero mientras está pausado `/health` responde 503. Como
  el web service también se duerme a los 15 minutos, una semana sin uso pausa la base.
- 500 MB por proyecto y sin backups automáticos.
- La base es alcanzable desde internet (protegida por contraseña y TLS), en lugar de quedar
  solo en la red privada de Render como con `ipAllowList: []`.
- Un proveedor y una cuenta más. La configuración de Supabase vive en su dashboard, no en el
  repositorio.
- La conexión viaja por internet entre dos proveedores en la misma región: un poco más de
  latencia que la red privada.

### Qué nos obliga a hacer

- Mantener en el README el runbook de reactivación del proyecto pausado y reactivarlo antes de
  cada demo con Bonita.
- Usar el Session pooler (puerto 5432, usuario `postgres.<ref>`), nunca la conexión directa ni el
  puerto 6543.
- Contraseña de la base alfanumérica y larga: un carácter especial sin codificar rompe la URL.
- Mantener la Data API deshabilitada mientras la API sea el único cliente de la base.
- Si Supabase cambia el major de PostgreSQL del proyecto, actualizar la imagen de
  `docker-compose.yml`.
