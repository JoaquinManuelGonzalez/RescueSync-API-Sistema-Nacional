# Contrato de configuración

La API del Sistema Nacional se configura en un 100 % por variables de entorno. Este documento
describe cada variable, la política de arranque ante configuración faltante y la gestión de
secretos. La plantilla con todas las variables, sin valores reales, es `.env.example`; la
configuración de la nube está en `render.yaml`. Sigue el mismo contrato que la aplicación web de
RescueSync, reducido a lo que usa la API.

## 1. Tabla de variables

### Leídas por la aplicación (`app/core/configuracion.py`)

| Variable | Obligatoria (S/N) | Valor por defecto | Descripción | En Render |
|---|---|---|---|---|
| `SECRET_KEY` | S | — | Clave secreta de Flask | Generada por Render (`generateValue: true`) |
| `JWT_SECRET_KEY` | S | — | Clave con la que se firman los JWT (HS256). Mínimo 32 caracteres y distinta de `SECRET_KEY`. Rotarla invalida los tokens vigentes ([autenticación](autenticacion.md)) | Generada por Render (`generateValue: true`) |
| `DATABASE_URL` | S | — | Cadena de conexión a PostgreSQL. Acepta `postgres://`, `postgresql://` o `postgresql+psycopg://`; la aplicación la normaliza al driver psycopg 3 | URI del Session pooler de Supabase, cargada a mano en el dashboard (`sync: false`) |
| `APP_ENV` | N | `local` | Entorno de ejecución (`local`, `evaluacion`, `produccion`). En `produccion` se activa `ProxyFix` para el balanceador de Render | `produccion` |
| `PORT` | N | `8000` | Puerto en el que escucha la aplicación dentro del contenedor | Lo inyecta Render (`10000`) |
| `LOG_LEVEL` | N | `INFO` | Nivel mínimo de log (`DEBUG`, `INFO`, `WARN`, `ERROR`) | `INFO` |
| `JWT_EXPIRACION_MINUTOS` | N | `60` | Vida de los tokens que emite `/login`, entre 1 y 1440 minutos. El conector de Bonita pide uno nuevo antes del vencimiento | `60` |
| `DATABASE_SSLMODE` | N | (vacío) | Si tiene valor, se agrega como `sslmode` a la URL de la base. Vacío para el PostgreSQL local | `require` (la conexión a Supabase viaja por internet) |

### Leídas por la infraestructura (nunca por la aplicación)

| Variable | Quién la usa | Valor por defecto | Descripción |
|---|---|---|---|
| `POSTGRES_USER` | `docker-compose.yml` (servicio `db`) | — | Usuario del PostgreSQL local |
| `POSTGRES_PASSWORD` | `docker-compose.yml` (servicio `db`) | — | Contraseña del PostgreSQL local |
| `POSTGRES_DB` | `docker-compose.yml` (servicio `db`) | `sistema_nacional` | Nombre de la base local |
| `POSTGRES_HOST_PORT` | `docker-compose.yml` | `5433` | Puerto del host donde se publica PostgreSQL. No es 5432 para convivir con la base de la aplicación web |
| `WEB_CONCURRENCY` | Gunicorn | (Render lo fija según el plan) | Cantidad de workers de Gunicorn. En local, opcional |

## 2. Arranque en modo "fail fast"

La aplicación valida las variables obligatorias al construirse (app factory), antes de aceptar
solicitudes. Si falta una, está vacía, `PORT` / `JWT_EXPIRACION_MINUTOS` / `DATABASE_URL` tienen
un formato inválido o `JWT_SECRET_KEY` tiene menos de 32 caracteres:

1. Registra un evento `configuracion_invalida` de nivel `ERROR` por cada problema, sin loguear
   el valor de ninguna variable, y repite el mensaje en texto plano en `stderr`.
2. Termina el proceso con código de salida `1`, sin levantar el servidor HTTP.

En Docker esto se ve como un contenedor que termina enseguida; en Render, como un deploy que
falla y deja corriendo la versión anterior. Se verifica quitando `SECRET_KEY` del `.env` y
corriendo `docker compose up api`.

## 3. Entornos

| Aspecto | Local (`docker compose`) | Nube (Render + Supabase) |
|---|---|---|
| `APP_ENV` | `local` | `produccion` |
| Origen de las variables | `.env` propio de cada integrante, nunca versionado | `render.yaml` + valores generados o cargados en el dashboard |
| Base de datos | Contenedor `postgres:17-trixie`, datos descartables | Supabase PostgreSQL 17 (Free), por el Session pooler (ver ADR-004) |
| TLS hacia la base | No | Sí (`DATABASE_SSLMODE=require`) |
| Consumidor | Bonita local apuntando a `http://localhost:8000` | Bonita apuntando a la URL pública HTTPS |

## 4. Gestión de secretos

- **Ningún secreto se versiona.** `.env` y cualquier `.env.*` (salvo `.env.example`) están en
  `.gitignore`. `render.yaml` no contiene valores secretos: `SECRET_KEY` y `JWT_SECRET_KEY` las
  genera Render y
  `DATABASE_URL` (que incluye la contraseña de la base de Supabase) se carga a mano en
  **Service → Environment** del dashboard de Render.
- **Secretos que no se pueden generar** se declaran en `render.yaml` con `sync: false`. Render
  los pide solo al crear el Blueprint por primera vez; si se agregan después, se cargan a mano en
  **Service → Environment** del dashboard. Una variable nueva con `generateValue: true` (como
  `JWT_SECRET_KEY`) la crea Render al sincronizar el Blueprint, si todavía no existe.
- **Credenciales de las cuentas de la API** (la de Bonita y la del administrador) no son
  variables de entorno: viven hasheadas en la tabla `cuentas` y se crean con `flask cuentas`
  ([autenticación](autenticacion.md), sección 8). El secreto de Bonita se carga en el parámetro
  `snClientSecret` del proceso.
- **`.env.supabase`** (opcional, solo para quien administra la base): archivo local con la
  `DATABASE_URL` de Supabase, para comandos puntuales contra la nube con `docker run
  --env-file`. Lo ignoran git y Docker (`.env.*`). No reemplaza al `.env`.
- **No se usan como `ARG` en el Dockerfile.** Render convierte las variables de entorno en build
  args, y un `ARG` con un secreto quedaría grabado en la imagen.
- **Si un secreto se filtra**, se rota de inmediato en el sistema correspondiente (Render,
  Supabase, Bonita), se avisa al equipo y se considera comprometido aunque se limpie el
  historial de git. La contraseña de la base se rota con el runbook "Rotar la contraseña de la
  base" del README.

Verificación de que `.env` no llega al remoto:

```bash
git check-ignore -v .env      # debe mostrar la línea de .gitignore que lo ignora
git status --ignored          # .env debe aparecer solo bajo "Ignored files"
```
