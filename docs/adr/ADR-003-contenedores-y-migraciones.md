# ADR-003: Contenedores y ejecución de migraciones

- Estado: Reemplazado parcialmente por ADR-004
- Fecha: 2026-10-03
- Reemplaza a: —
- Reemplazado por: ADR-004 (solo la versión local de PostgreSQL)

## Contexto

La API tiene que poder levantarse con un solo comando en cualquier máquina del equipo y
desplegarse en Render desde el mismo Dockerfile. Las migraciones de Alembic tienen que
aplicarse solas en cada despliegue. En el plan Free de Render no existe el pre-deploy command,
ni Shell, ni one-off jobs (ADR-002), así que no hay otro lugar donde ejecutarlas que el propio
contenedor de la aplicación.

## Decisión

1. **Un Dockerfile multi-stage** (`python:3.14-slim-trixie` + uv 0.12.13) con dos targets:
   - `desarrollo`: incluye el grupo dev (Ruff, pytest) y arranca `flask run --debug` con
     recarga; lo usa `docker-compose.yml` con el código montado como volumen.
   - `produccion`: sin dependencias de desarrollo, arranca Gunicorn ligado a
     `0.0.0.0:${PORT}`. Es la **última etapa del archivo**, para que sea el target por defecto:
     el Blueprint de Render no permite elegir target.
2. **Las migraciones corren en `entrypoint.sh`** antes de arrancar el servidor
   (`flask db upgrade` y después `exec "$@"`). Con `set -e`, una migración fallida termina el
   contenedor con código distinto de cero: Render no lo marca sano y mantiene la versión
   anterior, sin servir tráfico contra un esquema a medias.
3. **`docker-compose.yml` local** con dos servicios, `db` (PostgreSQL 18, el mismo major que
   Render) y `api`, con healthchecks y `depends_on: service_healthy`. Un `adminer` opcional
   queda detrás del perfil `herramientas`.

### Versión fijada

| Tecnología | Versión | Archivo del repositorio donde se fija |
|---|---|---|
| Imagen base | `python:3.14-slim-trixie` | `Dockerfile` |
| uv | 0.12.13 | `Dockerfile`, `.github/workflows/ci.yml` |
| PostgreSQL (local) | `postgres:18-trixie` | `docker-compose.yml` |

### Alternativas consideradas

| Alternativa | A favor | En contra | Motivo del descarte |
|---|---|---|---|
| `preDeployCommand: flask db upgrade` en Render | Separa migración de arranque | Solo existe en planes pagos | No disponible en Free |
| Migrar a mano desde la máquina de un integrante con la URL externa | Control total | Paso manual que se olvida; exige abrir la base a internet | Contradice el despliegue automático y el `ipAllowList: []` |
| Dockerfile de una sola etapa | Más simple | Mete Ruff y pytest en la imagen de producción | Imagen más pesada y superficie innecesaria |

## Consecuencias

### Positivas

- El mismo artefacto (imagen) corre en local, en el CI y en Render.
- El esquema siempre está al día con el código desplegado, sin pasos manuales.
- Recrear la base desde cero (por ejemplo, cuando expira la free) es solo volver a arrancar el
  servicio.

### Negativas

- Con más de una instancia, cada una intentaría migrar al arrancar. Hoy no aplica: el plan Free
  corre una sola instancia. Si se escala, se pasa a `preDeployCommand` en un ADR nuevo.
- Una migración lenta demora el arranque; Render cancela el deploy si el health check no pasa
  en 15 minutos.

### Qué nos obliga a hacer

- `entrypoint.sh` con fin de línea LF (lo garantiza `.gitattributes`).
- Toda migración nueva se prueba contra PostgreSQL (`docker compose`), no solo contra SQLite.
- Nunca declarar secretos como `ARG` en el Dockerfile.
