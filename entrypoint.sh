#!/bin/sh
# Punto de entrada del contenedor de la API (local, CI y Render).
#
# Aplica las migraciones pendientes y despues ejecuta el comando del contenedor (CMD).
# En el plan Free de Render no existe el pre-deploy command, asi que este es el unico lugar
# donde pueden correr (ver docs/adr/ADR-003-contenedores-y-migraciones.md).
#
# "set -e" hace que una migracion fallida termine el contenedor con codigo distinto de cero en
# vez de dejarlo sirviendo peticiones contra un esquema a medias: Render no lo marca sano y
# mantiene la version anterior.
set -e

echo "[entrypoint] Aplicando migraciones pendientes..."
flask db upgrade
echo "[entrypoint] Migraciones al dia. Iniciando la aplicacion..."

# exec reemplaza este shell por el proceso del servidor, para que reciba las senales (SIGTERM)
# directamente y pueda hacer un apagado ordenado.
exec "$@"
