# RescueSync — API del Sistema Nacional

API del Sistema Nacional creada para el proyecto RescueSync de la materia Desarrollo de Software
en Sistemas Distribuidos. Responde la habilitación de ONGs y gestiona la reserva y el compromiso
de recursos. Corre dockerizada, en local con `docker compose` y en la nube en Render.

**URL pública:** `https://rescuesync-sistema-nacional.onrender.com`
(salud: [`/health`](https://rescuesync-sistema-nacional.onrender.com/health))

> **Único consumidor: Bonita.** La aplicación web de RescueSync **nunca** llama a esta API
> directamente: toda interacción pasa por el proceso de Bonita, que la invoca con conectores
> REST.

```
Aplicación web ──► Bonita (proceso BPMN) ──► API del Sistema Nacional ──► PostgreSQL
                    conectores REST            Flask + Gunicorn            (Render Postgres)
```

## Índice

1. [Puesta en marcha](#puesta-en-marcha)
2. [Stack tecnológico](#stack-tecnológico)
3. [Mapa del repositorio](#mapa-del-repositorio)
4. [Variables de entorno](#variables-de-entorno)
5. [Comandos frecuentes](#comandos-frecuentes)
6. [Despliegue en Render](#despliegue-en-render)
7. [Límites del plan Free y runbooks](#límites-del-plan-free-y-runbooks)
8. [Integración con Bonita](#integración-con-bonita)
9. [Problemas conocidos](#problemas-conocidos)
10. [Documentación](#documentación)
11. [Registro de validación](#registro-de-validación)

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
| PostgreSQL | 18 | `docker-compose.yml`, `render.yaml` |
| Ruff (dev) | 0.16.7 | `pyproject.toml` / `uv.lock` |
| pytest (dev) | 9.1.1 | `pyproject.toml` / `uv.lock` |
| Render (PaaS) | plan Free | `render.yaml` |

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
render.yaml             Blueprint de Render: infraestructura de la nube como código
.env.example            plantilla de variables de entorno
```

## Variables de entorno

Detalle completo en [`docs/contratos/configuracion.md`](docs/contratos/configuracion.md).

| Variable | Obligatoria | Ejemplo | Descripción |
|---|---|---|---|
| `SECRET_KEY` | Sí | (cadena aleatoria) | Clave secreta de Flask |
| `DATABASE_URL` | Sí | `postgresql+psycopg://sistema_nacional:clave@db:5432/sistema_nacional` | Conexión a PostgreSQL |
| `APP_ENV` | No | `local` | `local`, `evaluacion` o `produccion` |
| `PORT` | No | `8000` | Puerto de la API (Render inyecta `10000`) |
| `LOG_LEVEL` | No | `DEBUG` | `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `DATABASE_SSLMODE` | No | (vacío) | `require` en Render |
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

La infraestructura está declarada en [`render.yaml`](render.yaml) (Render Blueprint):

| Recurso | Nombre | Plan | Región |
|---|---|---|---|
| Web service (Docker) | `rescuesync-sistema-nacional` | Free | virginia |
| Render Postgres 18 | `rescuesync-sn-db` | Free | virginia |

**Cómo se despliega:** push a la rama vinculada → GitHub Actions corre el CI → si **todos** los
checks pasan, Render construye la imagen desde el `Dockerfile` y la despliega
(`autoDeployTrigger: checksPass`). Al arrancar, el contenedor aplica las migraciones; cuando
`/health` responde 200, Render le pasa el tráfico sin cortar el servicio. Si el CI o el
arranque fallan, sigue corriendo la versión anterior.

- La rama vinculada hoy es `feat/EPIC-SN-01-dockerizacion-y-despliegue` (pasa a `main` al
  integrar la épica; ver `CONTRIBUTING.md`).
- Los cambios solo en `docs/**` o en archivos `.md` no despliegan. Para saltear el deploy de
  otro commit, agregar `[skip render]` al mensaje.
- HTTPS y certificado los gestiona Render. La base no es accesible desde internet
  (`ipAllowList: []`): solo la alcanza el web service por la red privada.
- Los logs están en el dashboard de Render → servicio → **Logs**. El workspace gratuito de
  Render admite un solo miembro: quien administra la cuenta comparte los logs con el equipo.

### Crear el entorno de cero

1. Cuenta en [Render](https://dashboard.render.com) (con "Sign up with GitHub") y la app de
   Render instalada en GitHub con acceso a este repositorio.
2. Dashboard → **New → Blueprint** → conectar este repositorio → rama vinculada → **Deploy
   Blueprint**. Render crea la base, el web service y genera `SECRET_KEY`.
3. Esperar el primer deploy en la pestaña **Events** y verificar `/health`.

## Límites del plan Free y runbooks

Según la documentación de Render:

| Límite | Impacto |
|---|---|
| El servicio **se duerme a los 15 min** sin tráfico y tarda ~1 min en despertar | El primer llamado después de un rato ocioso es lento (ver Bonita abajo) |
| La **base Free expira a los 30 días** de creada (14 días de gracia y después se borra) | Hay que recrearla (runbook abajo). Los datos se pierden |
| 1 base Free por workspace, 1 GB, **sin backups** | No guardar nada que no se pueda regenerar |
| 750 horas de instancia por mes por workspace | Alcanza para un servicio encendido todo el mes |
| Sin pre-deploy command, sin Shell, sin one-off jobs | Por eso las migraciones corren en `entrypoint.sh` |
| Render puede reiniciar o mantener servicios Free sin aviso | Reintentar ante 5xx o timeouts |

### Runbook: la base Free expiró (o está por expirar)

Render avisa por mail antes del vencimiento. Para recrearla:

1. Dashboard → `rescuesync-sn-db` → **Settings** → **Delete Database**.
2. Dashboard → **Blueprints** → el Blueprint de este repo → **Manual Sync**. Render detecta que
   falta la base declarada en `render.yaml` y la crea de nuevo, vacía.
3. Servicio `rescuesync-sistema-nacional` → **Manual Deploy → Deploy latest commit**, para que
   arranque con la nueva `DATABASE_URL`. El `entrypoint.sh` aplica todas las migraciones y el
   esquema queda reconstruido.
4. Verificar `GET /health` → 200 y agendar la nueva fecha de expiración (30 días).

### Runbook: despertar el servicio antes de una demo

```bash
curl https://rescuesync-sistema-nacional.onrender.com/health
```

Repetir hasta recibir `{"db":"ok","status":"ok"}` (el primer intento puede tardar ~1 minuto).

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
5. **La URL pública tarda ~1 minuto en responder.** Es el spin-down del plan Free, no una falla.

## Documentación

| Documento | Contenido |
|---|---|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Convenciones de código, ramas, commits, flujo de épica, pase a `main` y despliegue continuo |
| [`docs/adr/`](docs/adr/README.md) | ADR-001 framework, ADR-002 plataforma cloud (Render), ADR-003 contenedores y migraciones |
| [`docs/contratos/configuracion.md`](docs/contratos/configuracion.md) | Variables de entorno, fail-fast y gestión de secretos |
| [`docs/contratos/errores.md`](docs/contratos/errores.md) | Envelope de error y qué significa cada código para Bonita |
| [`docs/contratos/logging.md`](docs/contratos/logging.md) | Formato JSON de logs e id de correlación |

## Registro de validación

Criterio de la épica: un integrante que no participó del setup levanta la API siguiendo **solo
este README**.

| Fecha | Integrante | Sistema operativo | Resultado | Observaciones |
|---|---|---|---|---|
| | | | | |
