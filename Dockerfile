# syntax=docker/dockerfile:1.9
# Imagen de la API del Sistema Nacional de RescueSync.
#
# Dos targets:
#   desarrollo -> incluye el grupo dev (ruff, pytest) y arranca el servidor de Flask con recarga.
#                 Lo usa docker-compose.yml con el codigo montado como volumen.
#   produccion -> sin dependencias de desarrollo, arranca gunicorn. Es la ULTIMA etapa del
#                 archivo a proposito: es el target por defecto de `docker build`, que es lo
#                 que hace Render (el Blueprint no tiene campo para elegir target).
#
# Ningun ARG lleva secretos: Render convierte las variables de entorno del servicio en build
# args, y un secreto usado en el build quedaria grabado en una capa de la imagen.

ARG PYTHON_IMAGE=python:3.14-slim-trixie

FROM ${PYTHON_IMAGE} AS base

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /bin/

# UV_PROJECT_ENVIRONMENT apunta FUERA de /app a proposito: en desarrollo /app es un bind mount
# y un entorno virtual creado ahi dentro quedaria tapado por la carpeta del host.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=app.wsgi:app

# Usuario sin privilegios. UID/GID 1000 coincide con el usuario habitual de Linux/WSL, para
# que los archivos que la app cree en el bind mount de desarrollo no queden como root.
ARG UID=1000
ARG GID=1000
RUN groupadd --gid "${GID}" sistema \
    && useradd --uid "${UID}" --gid "${GID}" --create-home sistema

WORKDIR /app

# --- Dependencias ------------------------------------------------------------
# Se instalan antes de copiar el codigo para que un cambio en app/ no invalide esta capa.

FROM base AS dependencias-desarrollo
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-install-project

FROM base AS dependencias-produccion
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-install-project --no-dev

# --- Targets finales -----------------------------------------------------------

FROM dependencias-desarrollo AS desarrollo
COPY --chown=sistema:sistema --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --chown=sistema:sistema . /app
USER sistema
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sh", "-c", "flask run --debug --host 0.0.0.0 --port ${PORT:-8000}"]

FROM dependencias-produccion AS produccion
COPY --chown=sistema:sistema --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --chown=sistema:sistema . /app
USER sistema
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# Render inyecta PORT (10000) y WEB_CONCURRENCY (workers segun el plan); gunicorn lee
# WEB_CONCURRENCY por su cuenta. "exec" deja a gunicorn como PID 1 del shell: recibe el SIGTERM
# de Render en cada deploy y termina las solicitudes en curso antes de salir. Sin access log
# de gunicorn: cada solicitud ya queda registrada en JSON por el middleware de la app.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8000} app.wsgi:app"]
