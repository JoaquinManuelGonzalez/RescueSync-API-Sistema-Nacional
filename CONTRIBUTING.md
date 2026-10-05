# Guía de contribución — API del Sistema Nacional (RescueSync)

Esta guía define cómo se escribe código, cómo se nombran ramas y commits, y cómo se integran
los cambios en este repositorio. Hereda las convenciones de la aplicación web de RescueSync
(Entrega 2) y las adapta a una API sin interfaz. Es de lectura obligatoria antes del primer
commit.

## Índice

1. Idioma del código
2. Nomenclatura por capa
3. Estructura de carpetas
4. Entorno local, formato y verificación (uv + Ruff)
5. Nomenclatura de ramas
6. Commits y vínculo con el backlog
7. Flujo de trabajo actual: rama de épica
8. Pase a `main` y revisión obligatoria
9. Despliegue continuo

## 1. Idioma del código

Todo el código se escribe en español: nombres de paquetes, módulos, clases, funciones,
variables, tablas, columnas, rutas, mensajes de commit y comentarios.

Los identificadores se escriben **sin tildes ni `ñ`** (`habilitacion`, `anio`). La ortografía
completa se reserva para comentarios, docstrings, documentación (`.md`), mensajes de log
legibles por humanos y mensajes de error al cliente.

Las excepciones se nombran con la palabra adelante: `ErrorDeAplicacion`, no
`AplicacionError` (por eso `app/core/errores.py` ignora la regla `N818` de Ruff).

## 2. Nomenclatura por capa

| Elemento | Convención | Ejemplo |
|---|---|---|
| Paquetes / módulos | `snake_case` | `habilitaciones` |
| Clases y modelos | `PascalCase` singular | `CompromisoDeRecurso` |
| Funciones y métodos | `snake_case`, empiezan con verbo | `registrar_compromiso`, `obtener_ong_por_id` |
| Variables | `snake_case` | `cantidad_reservada` |
| Constantes | `MAYUSCULAS_CON_GUION_BAJO` | `ESTADOS_DE_RESERVA` |
| Blueprints / endpoints | `modulo.accion` | `compromisos.crear` |
| Rutas URL | minúsculas con guion medio | `/recursos/compromisos`, `/ongs/{id}/habilitacion` |
| Tablas | `snake_case` plural | `compromisos_de_recursos` |
| Columnas | `snake_case` singular | `tipo_de_recurso` |
| Clave primaria | siempre `id` | `id` |
| Clave foránea | `<tabla_en_singular>_id` | `ong_id` |
| Booleanos | prefijo `es_` / `tiene_` | `es_habilitada` |
| Fechas | prefijo `fecha_` | `fecha_creacion` |
| Índices y restricciones | `ix_`/`uq_`/`fk_`/`ck_` + tabla + columnas | `ix_compromisos_de_recursos_ong_id` |
| Tests | `test_<unidad>.py` / `test_<caso>_<resultado>` | `test_health_sin_base_responde_503` |

La convención de nombres de índices y restricciones está declarada en `app/extensiones.py`:
Alembic genera esos nombres solo, sin que haya que escribirlos a mano.

## 3. Estructura de carpetas

```
app/
  __init__.py        app factory: create_app()
  wsgi.py            objeto que levantan flask y gunicorn (app.wsgi:app)
  extensiones.py     db, migrate
  core/              transversal: configuracion, errores, logging, salud
  modulos/
    __init__.py      registrar_modulos() e importar_modelos()
    <modulo>/
      rutas.py       blueprint Flask: define los endpoints HTTP
      servicios.py   logica de negocio (unico punto de entrada para otros modulos)
      modelos.py     modelos SQLAlchemy y consultas propias del modulo
migrations/          migraciones de Alembic (Flask-Migrate)
tests/
docs/
  adr/               decisiones de arquitectura
  contratos/         contratos de configuracion, errores y logging
```

- Una entidad de dominio nueva va en `modelos.py` del módulo dueño, y se agrega a
  `importar_modelos()` para que Alembic la vea.
- Un módulo pide datos de otro solo a través de su `servicios.py`, nunca importando sus modelos.
- Lo transversal (configuración, errores, logging, salud) va en `core/`.

## 4. Entorno local, formato y verificación (uv + Ruff)

Las dependencias se gestionan con **uv 0.12.13**: se declaran con versión exacta en
`pyproject.toml` y el árbol completo queda fijado en `uv.lock`, que se versiona.

```bash
uv sync --locked          # crea .venv con las mismas versiones que la imagen de Docker
```

Reglas al tocar dependencias:

- Se agregan con `uv add "paquete==1.2.3"`, **siempre con versión exacta**.
- Las de desarrollo (linters, tests) van con `uv add --dev`, para que no entren en la imagen
  de producción.
- `uv.lock` **no se edita a mano**. Ante un conflicto de merge se regenera con `uv lock`.
- `pyproject.toml` y `uv.lock` se commitean **juntos**, y la dependencia nueva se agrega a la
  tabla de stack del README en el mismo cambio.
- Después de cambiar dependencias: `docker compose build api && docker compose up -d api`.

Formato y verificación con **Ruff 0.16.7**, antes de cada commit:

```bash
uv run ruff format .           # formatea
uv run ruff format --check .   # verifica sin modificar
uv run ruff check .            # linter
uv run pytest                  # tests
```

Lo mismo se puede correr dentro del contenedor: `docker compose exec api ruff check .`. El CI
corre exactamente estos comandos (ver sección 9).

## 5. Nomenclatura de ramas

Patrón: `<tipo>/HU-<id>-<descripcion-en-kebab>`

Tipos permitidos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.

Para una épica completa trabajada en una sola rama se usa el identificador de la épica:
`feat/EPIC-SN-01-dockerizacion-y-despliegue`.

| Ejemplo | Válido / Inválido | Motivo |
|---|---|---|
| `feat/HU-SN-08-alta-compromiso` | Válido | tipo correcto, HU identificada, kebab-case |
| `feat/EPIC-SN-01-dockerizacion-y-despliegue` | Válido | rama de épica |
| `fix/HU-SN-12-reserva-duplicada` | Válido | corrige un defecto de la HU-SN-12 |
| `feat/compromisos` | Inválido | falta el identificador de HU o épica |
| `joaquin/pruebas` | Inválido | nombre personal, no describe el cambio |

## 6. Commits y vínculo con el backlog

Conventional Commits en español, siempre con el identificador de la HU:

```
<tipo>(<alcance>): <descripcion en minuscula> (HU-XX)
```

Ejemplos:

```
chore(repo): agrega pyproject y configuracion de ruff (HU-SN-01)
feat(salud): agrega endpoint /health con chequeo de base (HU-SN-02)
docs(readme): documenta runbook de pausa de supabase [skip render] (HU-SN-07)
```

Los commits que solo tocan documentación llevan `[skip render]` en el mensaje para que Render
no dispare un deploy innecesario (ver sección 9).

## 7. Flujo de trabajo actual: rama de épica

Durante la épica **EPIC-SN-01 (Dockerización y despliegue en la nube)** el equipo trabaja en
una única rama, sin Pull Requests contra `main`:

```bash
git checkout feat/EPIC-SN-01-dockerizacion-y-despliegue
git pull

# ... cambios ...
uv run ruff format --check . && uv run ruff check . && uv run pytest

git add <archivos>
git commit -m "feat(docker): agrega docker-compose con api y postgres (HU-SN-03)"
git push
```

Render está vinculado a esta rama mientras dure la épica: cada push con el CI en verde se
despliega solo (sección 9).

## 8. Pase a `main` y revisión obligatoria

Cuando el equipo decida integrar la épica a `main`, se aplican las reglas de la aplicación web:

- `main` está reservada a código entregable: **no se hace push directo**.
- Todo cambio entra por Pull Request, usando la plantilla de `.github/pull_request_template.md`.
- Mínimo **1 aprobación** de otro integrante; prohibido auto-aprobarse.
- Merge siempre por **squash**, con la rama al día con `main`.
- Las ramas se borran apenas se mergean.

Pasos del pase a `main`:

1. Abrir el PR de la rama de épica contra `main` con `gh pr create --base main`.
2. En el mismo PR, cambiar el campo `branch:` del servicio en `render.yaml` a `main`.
3. Después del merge, en Render: **Blueprint → Settings**, cambiar la rama vinculada a `main`
   y hacer **Manual Sync**.
4. Activar la protección de `main` (una sola vez, requiere permisos de admin del repo):

```bash
# Solo squash merge, y borrar la rama al mergear
gh api -X PATCH repos/JoaquinManuelGonzalez/RescueSync-API-Sistema-Nacional \
  -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true

# Proteccion: CI obligatorio, 1 aprobacion, rama al dia, sin push directo
gh api -X PUT repos/JoaquinManuelGonzalez/RescueSync-API-Sistema-Nacional/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["calidad", "imagen"] },
  "enforce_admins": true,
  "required_pull_request_reviews": { "required_approving_review_count": 1 },
  "restrictions": null
}
JSON
```

A partir de ahí el flujo por HU es el de la aplicación web: rama corta desde `main`
actualizada, PR con la plantilla, aprobación, squash.

## 9. Despliegue continuo

- La infraestructura de Render está declarada como código en `render.yaml` (Blueprint). Un
  cambio de infraestructura se hace editando ese archivo, no desde el dashboard: un cambio
  hecho a mano que contradiga el Blueprint se pisa en el siguiente sync.
- El servicio usa `autoDeployTrigger: checksPass`: Render despliega un commit de la rama
  vinculada **solo si todos los checks de GitHub Actions pasan**. Si el CI falla, no hay
  deploy y sigue corriendo la versión anterior.
- Los cambios que solo tocan `docs/**` o archivos `.md` no disparan deploy (`buildFilter`).
  Para otros commits sin impacto se puede usar `[skip render]` en el mensaje.
- Las migraciones de Alembic corren solas al arrancar el contenedor (`entrypoint.sh`), también
  contra Supabase en cada deploy. Una migración que falla aborta el arranque y Render mantiene
  la versión anterior. El esquema de la nube se cambia **solo** con migraciones: nunca a mano
  desde el dashboard de Supabase (flujo completo y reglas en el README, "Base de datos: local y
  nube").
- La base de datos no está en Render sino en Supabase (ADR-004): su configuración se hace en el
  dashboard de Supabase, y `DATABASE_URL` se carga a mano en el dashboard de Render.
- Nunca se commitean secretos: los valores sensibles viven en Render (variables generadas o
  cargadas en el dashboard), en Supabase y en el `.env` local de cada integrante.
