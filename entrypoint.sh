#!/bin/sh
# Punto de entrada del contenedor de la API (local, CI y Render).
#
# Aplica las migraciones pendientes, carga los datos semilla y despues ejecuta el comando del
# contenedor (CMD). En el plan Free de Render no existe el pre-deploy command ni la Shell, asi que
# este es el unico lugar donde pueden correr (ver docs/adr/ADR-003-contenedores-y-migraciones.md).
#
# "set -e" hace que una migracion fallida termine el contenedor con codigo distinto de cero en
# vez de dejarlo sirviendo peticiones contra un esquema a medias: Render no lo marca sano y
# mantiene la version anterior.
#
# El seed, en cambio, no corta el arranque: es idempotente y corre en una sola transaccion, asi
# que si falla no deja nada a medias y la API sigue sirviendo con los datos que ya tiene la base.
# El CI lo corre aparte y ahi si falla (job imagen de .github/workflows/ci.yml).
set -e

echo "[entrypoint] Aplicando migraciones pendientes..."
flask db upgrade
echo "[entrypoint] Migraciones al dia."

echo "[entrypoint] Cargando datos semilla..."
if flask seed; then
  echo "[entrypoint] Datos semilla al dia. Iniciando la aplicacion..."
else
  echo "[entrypoint] AVISO: flask seed fallo; la API arranca con los datos que ya tiene la base." >&2
fi

# exec reemplaza este shell por el proceso del servidor, para que reciba las senales (SIGTERM)
# directamente y pueda hacer un apagado ordenado.
exec "$@"
