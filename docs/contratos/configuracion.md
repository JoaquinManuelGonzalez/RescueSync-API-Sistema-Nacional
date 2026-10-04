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
| `DATABASE_URL` | S | — | Cadena de conexión a PostgreSQL. Acepta `postgres://`, `postgresql://` o `postgresql+psycopg://`; la aplicación la normaliza al driver psycopg 3 | Tomada de la base (`fromDatabase`, URL interna) |
| `APP_ENV` | N | `local` | Entorno de ejecución (`local`, `evaluacion`, `produccion`). En `produccion` se activa `ProxyFix` para el balanceador de Render | `produccion` |
| `PORT` | N | `8000` | Puerto en el que escucha la aplicación dentro del contenedor | Lo inyecta Render (`10000`) |
| `LOG_LEVEL` | N | `INFO` | Nivel mínimo de log (`DEBUG`, `INFO`, `WARN`, `ERROR`) | `INFO` |
| `DATABASE_SSLMODE` | N | (vacío) | Si tiene valor, se agrega como `sslmode` a la URL de la base. Vacío para el PostgreSQL local | `require` |

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
solicitudes. Si falta una, está vacía, o `PORT` / `DATABASE_URL` tienen un formato inválido:

1. Registra un evento `configuracion_invalida` de nivel `ERROR` por cada problema, sin loguear
   el valor de ninguna variable, y repite el mensaje en texto plano en `stderr`.
2. Termina el proceso con código de salida `1`, sin levantar el servidor HTTP.

En Docker esto se ve como un contenedor que termina enseguida; en Render, como un deploy que
falla y deja corriendo la versión anterior. Se verifica quitando `SECRET_KEY` del `.env` y
corriendo `docker compose up api`.

## 3. Entornos

| Aspecto | Local (`docker compose`) | Nube (Render) |
|---|---|---|
| `APP_ENV` | `local` | `produccion` |
| Origen de las variables | `.env` propio de cada integrante, nunca versionado | `render.yaml` + valores generados o cargados en el dashboard |
| Base de datos | Contenedor `postgres:18-trixie`, datos descartables | Render Postgres 18 (Free), accesible solo por la red privada |
| TLS hacia la base | No | Sí (`DATABASE_SSLMODE=require`) |
| Consumidor | Bonita local apuntando a `http://localhost:8000` | Bonita apuntando a la URL pública HTTPS |

## 4. Gestión de secretos

- **Ningún secreto se versiona.** `.env` y cualquier `.env.*` (salvo `.env.example`) están en
  `.gitignore`. `render.yaml` no contiene valores secretos: `SECRET_KEY` la genera Render y
  `DATABASE_URL` sale de la base.
- **Secretos futuros** (credenciales de Bonita, claves JWT) se declaran en `render.yaml` con
  `sync: false`. Render los pide solo al crear el Blueprint por primera vez; si se agregan
  después, se cargan a mano en **Service → Environment** del dashboard.
- **No se usan como `ARG` en el Dockerfile.** Render convierte las variables de entorno en build
  args, y un `ARG` con un secreto quedaría grabado en la imagen.
- **Si un secreto se filtra**, se rota de inmediato en el sistema correspondiente (Render,
  PostgreSQL, Bonita), se avisa al equipo y se considera comprometido aunque se limpie el
  historial de git.

Verificación de que `.env` no llega al remoto:

```bash
git check-ignore -v .env      # debe mostrar la línea de .gitignore que lo ignora
git status --ignored          # .env debe aparecer solo bajo "Ignored files"
```
