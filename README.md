# RescueSync — API del Sistema Nacional

API del Sistema Nacional creada para el proyecto RescueSync de la materia Desarrollo de Software
en Sistemas Distribuidos. Responde la habilitación de ONGs y gestiona la reserva y el compromiso
de recursos. Corre dockerizada, en local con `docker compose` y en la nube en Render, con la base
PostgreSQL en Supabase.

**URL pública:** `https://rescuesync-sistema-nacional.onrender.com`
(salud: [`/health`](https://rescuesync-sistema-nacional.onrender.com/health))

> **Único consumidor: Bonita.** La aplicación web de RescueSync **nunca** llama a esta API
> directamente: toda interacción pasa por el proceso de Bonita, que la invoca con conectores
> REST.

```
Aplicación web ──► Bonita (proceso BPMN) ──► API del Sistema Nacional ──► PostgreSQL
                    conectores REST            Flask + Gunicorn            (Supabase)
                                               (Render)
```

## Índice

1. [Puesta en marcha](#puesta-en-marcha)
2. [Stack tecnológico](#stack-tecnológico)
3. [Mapa del repositorio](#mapa-del-repositorio)
4. [Variables de entorno](#variables-de-entorno)
5. [Comandos frecuentes](#comandos-frecuentes)
6. [Despliegue en Render](#despliegue-en-render)
7. [Base de datos: local y nube](#base-de-datos-local-y-nube)
8. [Límites de los planes Free y runbooks](#límites-de-los-planes-free-y-runbooks)
9. [Integración con Bonita](#integración-con-bonita)
10. [Problemas conocidos](#problemas-conocidos)
11. [Documentación](#documentación)
12. [Registro de validación](#registro-de-validación)

## Puesta en marcha

### Requisitos previos

| Herramienta | Versión | Para qué |
|---|---|---|
| [Git](https://git-scm.com/) | cualquiera reciente | Clonar el repositorio |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/macOS) o Docker Engine + Compose v2 (Linux) | Compose 2.20 o superior | Levantar la API y PostgreSQL |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) *(opcional)* | 0.12.13 | Correr Ruff y pytest fuera del contenedor, y para que el editor resuelva los imports |

Instalar uv (opcional):

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/0.12.13/install.ps1 | iex"
# Linux / macOS
curl -LsSf https://astral.sh/uv/0.12.13/install.sh | sh
```

### Levantar la API en tres pasos

```bash
git clone https://github.com/JoaquinManuelGonzalez/RescueSync-API-Sistema-Nacional.git
cd RescueSync-API-Sistema-Nacional
```

1. **Crear el `.env`** a partir de la plantilla y completar los tres valores vacíos:

   ```bash
   cp .env.example .env
   ```

   - `SECRET_KEY`: cualquier cadena larga. Para generar una:
     `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - `POSTGRES_PASSWORD`: cualquier contraseña (es la del PostgreSQL local).
   - En `DATABASE_URL`, reemplazar `CAMBIAR` por esa misma contraseña.

2. **Levantar** (la primera vez descarga imágenes y construye; tarda un par de minutos):

   ```bash
   docker compose up -d --build --wait
   ```

3. **Verificar**:

   ```bash
   curl http://localhost:8000/health
   # {"db":"ok","status":"ok"}
   ```

`docker compose ps` tiene que mostrar `db` y `api` como `healthy`. Las migraciones se aplican
solas al arrancar el contenedor `api`.

### Alternativa: API fuera del contenedor (con uv)

Útil para depurar con el editor. PostgreSQL sigue en Docker, y desde la PC se lo alcanza en
`localhost:5433` (no en `db:5432`, que es el nombre dentro de la red de Docker). La variable se
define en la terminal, para no tocar el `.env` que usa el contenedor; Flask carga el resto del
`.env` solo y no pisa lo que ya está definido.

```bash
uv sync --locked
docker compose up -d db
docker compose stop api        # libera el puerto 8000 si estaba levantada

# bash / Git Bash
export DATABASE_URL="postgresql+psycopg://sistema_nacional:<POSTGRES_PASSWORD>@localhost:5433/sistema_nacional"
# PowerShell
$env:DATABASE_URL = "postgresql+psycopg://sistema_nacional:<POSTGRES_PASSWORD>@localhost:5433/sistema_nacional"

uv run flask --app app.wsgi:app db upgrade
uv run flask --app app.wsgi:app run --debug --port 8000
```

## Stack tecnológico

| Componente | Versión | Dónde se fija |
|---|---|---|
| Python | 3.14 | `.python-version`, `pyproject.toml`, `Dockerfile` |
| uv | 0.12.13 | `Dockerfile`, `.github/workflows/ci.yml` |
| Flask | 3.1.3 | `pyproject.toml` / `uv.lock` |
| Gunicorn | 26.2.0 | `pyproject.toml` / `uv.lock` |
| Flask-SQLAlchemy / SQLAlchemy | 3.1.1 / 2.0.54 | `pyproject.toml` / `uv.lock` |
| Flask-Migrate / Alembic | 4.1.0 / 1.20.0 | `pyproject.toml` / `uv.lock` |
| psycopg (binary) | 3.3.5 | `pyproject.toml` / `uv.lock` |
| python-dotenv | 1.2.3 | `pyproject.toml` / `uv.lock` |
| PostgreSQL | 17 (el mismo major que Supabase) | `docker-compose.yml` |
| Ruff (dev) | 0.16.7 | `pyproject.toml` / `uv.lock` |
| pytest (dev) | 9.1.1 | `pyproject.toml` / `uv.lock` |
| Render (PaaS) | plan Free | `render.yaml` |
| Supabase (base de datos) | plan Free, `us-east-1` | dashboard de Supabase (ADR-004) |

## Mapa del repositorio

```
app/                    código de la API
  __init__.py           app factory create_app()
  wsgi.py               objeto que levantan flask y gunicorn (app.wsgi:app)
  extensiones.py        db y migrate
  core/                 configuracion, errores, logging, salud (/health)
  modulos/              módulos de dominio (los agregan las épicas siguientes)
migrations/             migraciones de Alembic (0001: línea base sin tablas)
tests/                  tests con pytest (SQLite en memoria)
docs/adr/               decisiones de arquitectura
docs/contratos/         contratos de configuración, errores y logging
.github/workflows/ci.yml  CI: calidad (ruff, pytest, render.yaml) + imagen (smoke tests)
Dockerfile              imagen multi-stage: desarrollo / produccion (por defecto)
entrypoint.sh           aplica migraciones y arranca el servidor
healthcheck.py          healthcheck del contenedor para docker compose
docker-compose.yml      entorno local: db + api (+ adminer con --profile herramientas)
render.yaml             Blueprint de Render: web service de la nube como código
.env.example            plantilla de variables de entorno
```

## Variables de entorno

Detalle completo en [`docs/contratos/configuracion.md`](docs/contratos/configuracion.md).

| Variable | Obligatoria | Ejemplo | Descripción |
|---|---|---|---|
| `SECRET_KEY` | Sí | (cadena aleatoria) | Clave secreta de Flask |
| `DATABASE_URL` | Sí | `postgresql+psycopg://sistema_nacional:clave@db:5432/sistema_nacional` | Conexión a PostgreSQL. En local, la base `db`; en Render, la URI del Session pooler de Supabase |
| `APP_ENV` | No | `local` | `local`, `evaluacion` o `produccion` |
| `PORT` | No | `8000` | Puerto de la API (Render inyecta `10000`) |
| `LOG_LEVEL` | No | `DEBUG` | `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `DATABASE_SSLMODE` | No | (vacío) | `require` en la nube (Supabase) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Sí (compose) | `sistema_nacional` | Credenciales del PostgreSQL local |
| `POSTGRES_HOST_PORT` | No | `5433` | Puerto del host para PostgreSQL |

Si falta una variable obligatoria, la API **no arranca** y lo dice en los logs:
`Falta la variable de entorno obligatoria: SECRET_KEY`.

## Comandos frecuentes

```bash
docker compose up -d --build --wait     # levantar (o reconstruir tras cambiar dependencias)
docker compose logs -f api              # logs JSON de la API
docker compose ps                       # estado y healthchecks
docker compose down                     # detener (los datos persisten)
docker compose down -v                  # detener y BORRAR la base local

docker compose exec api flask db upgrade                 # aplicar migraciones a mano
docker compose exec api flask db migrate -m "mensaje"    # generar una migración
docker compose exec api pytest                           # tests dentro del contenedor
docker compose exec api ruff check .                     # linter dentro del contenedor

docker compose --profile herramientas up -d   # Adminer en http://localhost:8081
                                              # (servidor: db, usuario y clave del .env)
```

Con uv instalado, la verificación previa a cada commit es:

```bash
uv run ruff format --check . && uv run ruff check . && uv run pytest
```

## Despliegue en Render

| Recurso | Nombre | Plan | Región | Dónde se configura |
|---|---|---|---|---|
| Web service (Docker) en Render | `rescuesync-sistema-nacional` | Free | virginia | [`render.yaml`](render.yaml) (Render Blueprint) |
| PostgreSQL 17 en Supabase | `rescuesync-sistema-nacional` | Free | East US (North Virginia) | Dashboard de Supabase |

La base está en Supabase y no en Render porque la Render Postgres Free expira a los 30 días; la
de Supabase no expira (decisión en
[`docs/adr/ADR-004-base-de-datos-supabase.md`](docs/adr/ADR-004-base-de-datos-supabase.md)).

**Cómo se despliega:** push a la rama vinculada → GitHub Actions corre el CI → si **todos** los
checks pasan, Render construye la imagen desde el `Dockerfile` y la despliega
(`autoDeployTrigger: checksPass`). Al arrancar, el contenedor aplica las migraciones; cuando
`/health` responde 200, Render le pasa el tráfico sin cortar el servicio. Si el CI o el
arranque fallan, sigue corriendo la versión anterior.

- La rama vinculada es `main`: todo cambio llega por Pull Request (ver `CONTRIBUTING.md`).
- Los cambios solo en `docs/**` o en archivos `.md` no despliegan. Para saltear el deploy de
  otro commit, agregar `[skip render]` al mensaje.
- HTTPS y certificado los gestiona Render. La API llega a Supabase por internet, con TLS
  obligatorio (`DATABASE_SSLMODE=require`) y por el **Session pooler**: la conexión directa de
  Supabase es solo IPv6 y Render solo sale por IPv4.
- La Data API (REST) de Supabase está **deshabilitada**: la base solo la usa esta API.
- Los logs están en el dashboard de Render → servicio → **Logs**. El workspace gratuito de
  Render admite un solo miembro: quien administra la cuenta comparte los logs con el equipo.

### Crear el entorno de cero

**Base en Supabase**

1. Cuenta en [Supabase](https://supabase.com/dashboard) (con "Continue with GitHub").
2. **New project**: nombre `rescuesync-sistema-nacional`, región **East US (North Virginia)**,
   plan Free. Contraseña de la base **alfanumérica y larga** (un carácter especial rompe la
   URL); guardarla en un gestor de contraseñas.
3. Menú **Integrations → Data API** → apagar **Enable Data API**.
4. Botón **Connect** (arriba) → pestaña **Direct** → método **Session pooler** → copiar la URI
   y reemplazar `[YOUR-PASSWORD]` por la contraseña (sin los corchetes). Tiene esta forma:
   `postgresql://postgres.<ref>:<clave>@aws-<n>-us-east-1.pooler.supabase.com:5432/postgres`
   Revisar que diga `us-east-1`, puerto `5432` y usuario `postgres.<ref>`.
5. Guardarla en un archivo `.env.supabase` en la raíz del repo, con una sola línea
   `DATABASE_URL=<URI>` (ver [El archivo `.env.supabase`](#el-archivo-envsupabase)).
6. *(Recomendado)* probarla desde la PC con la imagen de producción, antes de tocar Render:

   ```bash
   docker build -t sistema-nacional:local .
   docker run --rm -p 10000:10000 --env-file .env.supabase -e APP_ENV=produccion -e PORT=10000 \
     -e SECRET_KEY=prueba -e DATABASE_SSLMODE=require sistema-nacional:local
   # en otra terminal:
   curl http://localhost:10000/health   # {"db":"ok","status":"ok"}
   ```

   El contenedor aplica las migraciones en Supabase al arrancar, igual que en Render.

**Web service en Render**

1. Cuenta en [Render](https://dashboard.render.com) (con "Sign up with GitHub") y la app de
   Render instalada en GitHub con acceso a este repositorio.
2. Dashboard → **New → Blueprint** → conectar este repositorio → rama vinculada. Render pide el
   valor de `DATABASE_URL`: pegar la URI de Supabase. **Deploy Blueprint**: Render crea el web
   service y genera `SECRET_KEY`.
3. Esperar el primer deploy en la pestaña **Events** y verificar `/health`. En Supabase,
   **SQL Editor** → `select version_num from alembic_version;` muestra la última migración.

Si el Blueprint ya existía, Render no vuelve a pedir `DATABASE_URL` (ignora `sync: false` al
actualizar): se carga en servicio → **Environment** → **Save and deploy**.

## Base de datos: local y nube

Hay **dos bases con el mismo esquema**, y nunca se mezclan:

| | Local | Nube |
|---|---|---|
| Dónde | Contenedor `db` del `docker-compose.yml` (`postgres:17-trixie`) | Proyecto de Supabase (PostgreSQL 17) |
| Quién la crea | `docker compose up`, en un volumen propio de cada integrante | Se creó una sola vez en el dashboard ([Crear el entorno de cero](#crear-el-entorno-de-cero)) |
| Quién crea las tablas | Las migraciones, al arrancar el contenedor `api` | Las migraciones, al arrancar cada deploy en Render |
| Datos | Descartables (`docker compose down -v` la borra) | Compartidos por todo el equipo y por Bonita. **Sin backups** |
| Cómo se consulta | Adminer o `psql` | SQL Editor o Table Editor de Supabase |

La API **nunca** usa la base de la nube cuando corre en local: el `.env` apunta siempre a `db`.

### Acceso del equipo a Supabase

Quien administra el proyecto (rol **Owner**) invita a cada integrante desde **Organization
settings → Team → Invite** con el rol **Developer**. Un Developer puede usar el SQL Editor y el
Table Editor, pero no ve la contraseña de la base ni cambia la configuración del proyecto. El
plan Free admite miembros ilimitados (roles Owner, Administrator y Developer).

La contraseña de la base (y por lo tanto la URI) la tiene solo quien administra el proyecto.

### Flujo de una migración

El esquema se cambia **solo con migraciones de Alembic**: se generan y prueban en local, y llegan
a Supabase solas con el deploy.

1. Crear o modificar el modelo en `app/modulos/<modulo>/modelos.py`. Si el módulo es nuevo,
   agregar su import en `importar_modelos()` (`app/modulos/__init__.py`): Alembic no ve un
   modelo que nadie importa.
2. Generar la migración contra la base local:
   `docker compose exec api flask db migrate -m "agrega tabla de compromisos"`
3. Revisar el archivo generado en `migrations/versions/`: Alembic no detecta todo (por ejemplo,
   renombres de columnas, que interpreta como borrar y crear).
4. Aplicarla y probar ida y vuelta en local: `docker compose exec api flask db upgrade`, después
   `docker compose exec api flask db downgrade` (sin argumento vuelve una revisión) y de nuevo
   `upgrade`.
5. Commit y push. Con el CI en verde, Render despliega y el `entrypoint.sh` corre
   `flask db upgrade` contra Supabase antes de arrancar la API. Si la migración falla, el deploy
   no pasa y queda la versión anterior.
6. Verificar: en los logs del deploy aparece `Running upgrade <anterior> -> <nueva>`, o en el SQL
   Editor de Supabase `select version_num from alembic_version;` muestra la revisión nueva.

Reglas:

- **Nunca cambiar el esquema de la nube a mano** (Table Editor, o `create` / `alter` / `drop` en
  el SQL Editor). Alembic no se entera, y la próxima migración falla o deja la base distinta de
  los modelos.
- **Nunca correr `flask db upgrade` desde la PC contra Supabase con migraciones que no están
  desplegadas.** La base quedaría en una revisión que el código de Render no conoce, y el
  siguiente arranque falla con `Can't locate revision`.
- **Una migración desplegada no se revierte con `downgrade` en la nube**: se corrige con una
  migración nueva. `downgrade` se usa solo en local.
- **Las migraciones que borran datos** (`drop_table`, `drop_column`) se revisan dos veces:
  Supabase Free no tiene backups.
- Si dos integrantes generan migraciones en paralelo, Alembic queda con dos "heads" y
  `flask db upgrade` falla. Se ve con `docker compose exec api flask db heads` y se resuelve con
  `docker compose exec api flask db merge -m "une migraciones" heads`.

### Consultar la base

**Local:**

```bash
docker compose --profile herramientas up -d    # Adminer en http://localhost:8081
# Sistema: PostgreSQL, servidor: db, usuario / contraseña / base: los del .env

docker compose exec db psql -U sistema_nacional -d sistema_nacional   # consola psql
```

**Nube:** dashboard de Supabase → proyecto → **SQL Editor** (consultas) o **Table Editor** (ver
datos). Las consultas `select` se pueden hacer libremente. Las que modifican datos (`insert`,
`update`, `delete`) se coordinan con el equipo, porque la base es compartida y la usa Bonita. Las
que cambian el esquema no se hacen nunca (ver reglas).

### Comandos puntuales contra la nube

El plan Free de Render no tiene Shell. Quien tiene el `.env.supabase` puede correr un comando
puntual desde su PC con la misma imagen de la API, construida desde el **mismo commit que está
desplegado**:

```bash
docker build -t sistema-nacional:local .

# Revisión de Alembic aplicada en Supabase
docker run --rm --env-file .env.supabase -e SECRET_KEY=x -e DATABASE_SSLMODE=require \
  --entrypoint flask sistema-nacional:local db current

# Historial de migraciones que conoce el código
docker run --rm --env-file .env.supabase -e SECRET_KEY=x -e DATABASE_SSLMODE=require \
  --entrypoint flask sistema-nacional:local db history

# Consola psql contra Supabase (sin instalar nada)
docker run --rm -it --env-file .env.supabase postgres:17-trixie \
  sh -c 'psql "$DATABASE_URL?sslmode=require"'
```

`--entrypoint flask` saltea el `entrypoint.sh`: el comando no aplica migraciones.

### El archivo `.env.supabase`

Archivo local y opcional, solo para quien administra la base. Tiene una sola línea:

```
DATABASE_URL=postgresql://postgres.<ref>:<clave>@aws-<n>-us-east-1.pooler.supabase.com:5432/postgres
```

Git y Docker lo ignoran (`.env.*` está en `.gitignore` y en `.dockerignore`). Usarlo con
`--env-file` evita que la URI, que incluye la contraseña, quede escrita en la historia de la
terminal. **No** reemplaza al `.env`: la API local sigue usando su propia base.

## Límites de los planes Free y runbooks

Web service, según la documentación de Render:

| Límite | Impacto |
|---|---|
| El servicio **se duerme a los 15 min** sin tráfico y tarda ~1 min en despertar | El primer llamado después de un rato ocioso es lento (ver Bonita abajo) |
| 750 horas de instancia por mes por workspace | Alcanza para un servicio encendido todo el mes |
| Sin pre-deploy command, sin Shell, sin one-off jobs | Por eso las migraciones corren en `entrypoint.sh` |
| Render puede reiniciar o mantener servicios Free sin aviso | Reintentar ante 5xx o timeouts |

Base de datos, según la documentación de Supabase:

| Límite | Impacto |
|---|---|
| El proyecto **se pausa tras 7 días sin actividad** | `/health` responde 503 hasta reactivarlo (runbook abajo). Los datos se conservan |
| 500 MB por proyecto, **sin backups** automáticos | No guardar nada que no se pueda regenerar |
| 2 proyectos activos por cuenta | Este proyecto ocupa uno |

### Runbook: Supabase pausó el proyecto

Síntoma: `/health` responde 503 con `"db": "error"` y en los logs de Render aparece
`salud_degradada`.

1. [Dashboard de Supabase](https://supabase.com/dashboard) → proyecto
   `rescuesync-sistema-nacional` → **Restore project**.
2. Esperar a que el proyecto figure activo (puede tardar unos minutos).
3. Verificar `GET /health` → 200. No hace falta redeployar en Render: el pool de conexiones
   descarta las conexiones muertas solo.

### Runbook: rotar la contraseña de la base

1. Supabase → **Database → Settings** → **Reset database password** (alfanumérica y larga).
2. Render → servicio → **Environment** → editar `DATABASE_URL` con la contraseña nueva →
   **Save and deploy**.
3. Verificar `GET /health` → 200.

### Runbook: despertar el servicio antes de una demo

```bash
curl https://rescuesync-sistema-nacional.onrender.com/health
```

Repetir hasta recibir `{"db":"ok","status":"ok"}` (el primer intento puede tardar ~1 minuto).
Si responde 503 con `"db": "error"`, la base está pausada: seguir el runbook de Supabase.

## Integración con Bonita

Bonita es el único cliente de la API. Los conectores REST del proceso usan una URL base
configurable, no escrita a mano en cada conector, para pasar de local a nube sin tocar el
proceso:

| Dónde corre Bonita | Dónde corre la API | URL base |
|---|---|---|
| En la PC (Studio o runtime local) | `docker compose` en la misma PC | `http://localhost:8000` |
| En Docker | `docker compose` en la misma PC | `http://host.docker.internal:8000` |
| Cualquiera | Render | `https://rescuesync-sistema-nacional.onrender.com` |

- Cada respuesta trae el encabezado `X-Correlation-Id`. Si Bonita lo envía (por ejemplo, con el
  id del caso), la API lo reutiliza y aparece en todos sus logs.
- Errores: siempre JSON con el envelope de
  [`docs/contratos/errores.md`](docs/contratos/errores.md). Un 4xx es un rechazo de negocio (no
  reintentar con el mismo cuerpo); un 5xx o un timeout es una falla de disponibilidad
  (reintentar).
- Por el spin-down del plan Free, el primer llamado puede superar el timeout del conector:
  despertar el servicio antes de ejecutar el proceso.
- Los endpoints de negocio que va a consumir Bonita (habilitación, reserva y compromiso de
  recursos) llegan en las épicas siguientes.

## Problemas conocidos

1. **`entrypoint.sh: not found` o `no such file or directory` al arrancar `api` en Windows.**
   El archivo quedó con fin de línea CRLF. `.gitattributes` lo evita en clones nuevos; en un
   clon viejo: `git rm --cached -r . && git reset --hard` (descarta cambios locales sin
   commitear) y `docker compose build api`.
2. **`port is already allocated` al levantar.** Otro proceso usa el 8000 o el 5433. Cambiar
   `PORT` o `POSTGRES_HOST_PORT` en `.env` (si se cambia `PORT`, se cambia también en la URL de
   Bonita).
3. **El contenedor `api` termina enseguida.** Mirar `docker compose logs api`: casi siempre es
   una variable obligatoria faltante (fail-fast) o una contraseña de `DATABASE_URL` que no
   coincide con `POSTGRES_PASSWORD`.
4. **Cambié `POSTGRES_PASSWORD` y ahora la API no conecta.** PostgreSQL solo toma las
   credenciales al crear el volumen. Para empezar de cero: `docker compose down -v`.
   Lo mismo si `db` no arranca después de un cambio de versión de PostgreSQL en
   `docker-compose.yml` (por ejemplo, el paso de 18 a 17 para igualar a Supabase): los datos de
   un major no sirven para otro.
5. **La URL pública tarda ~1 minuto en responder.** Es el spin-down del plan Free, no una falla.
6. **La URL pública responde 503 con `"db": "error"`.** El proyecto de Supabase está pausado
   por inactividad: ver el runbook "Supabase pausó el proyecto".
7. **`password authentication failed` o `DATABASE_URL no es una URL de base de datos valida` en
   los logs de Render.** La contraseña de `DATABASE_URL` no coincide con la de Supabase o tiene
   caracteres especiales sin codificar: rotarla por una alfanumérica (runbook arriba).
8. **El deploy falla con `Can't locate revision` en los logs de Render.** Supabase quedó en una
   revisión de Alembic que el código desplegado no tiene (alguien migró desde su PC con una
   migración sin desplegar). Desplegar el commit que contiene esa migración, o pedir a quien
   administra la base que lo resuelva antes de seguir.

## Documentación

| Documento | Contenido |
|---|---|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Convenciones de código, ramas, commits, flujo de épica, pase a `main` y despliegue continuo |
| [`docs/adr/`](docs/adr/README.md) | ADR-001 framework, ADR-002 plataforma cloud (Render), ADR-003 contenedores y migraciones, ADR-004 base de datos en Supabase |
| [`docs/contratos/configuracion.md`](docs/contratos/configuracion.md) | Variables de entorno, fail-fast y gestión de secretos |
| [`docs/contratos/errores.md`](docs/contratos/errores.md) | Envelope de error y qué significa cada código para Bonita |
| [`docs/contratos/logging.md`](docs/contratos/logging.md) | Formato JSON de logs e id de correlación |

## Registro de validación

Criterio de la épica: un integrante que no participó del setup levanta la API siguiendo **solo
este README**.

| Fecha | Integrante | Sistema operativo | Resultado | Observaciones |
|---|---|---|---|---|
| | | | | |
