"""Carga y validacion de la configuracion de la aplicacion.

Implementa docs/contratos/configuracion.md. La fuente de verdad de que variable existe, si es
obligatoria y cual es su valor por defecto es la tabla de la seccion 1 de ese documento: este
modulo la refleja y no la reinterpreta.
"""

from __future__ import annotations

import logging
import os
import sys

from sqlalchemy.engine import make_url

from app.core.logging import configurar_logging, registrar_evento

# Variables obligatorias: sin valor por defecto. Si falta una sola, la aplicacion no arranca.
VARIABLES_OBLIGATORIAS: tuple[str, ...] = (
    "SECRET_KEY",
    "DATABASE_URL",
)

VARIABLES_OPCIONALES: dict[str, str] = {
    "APP_ENV": "local",
    # Render inyecta PORT=10000; en local se usa 8000 para no chocar con la aplicacion web.
    "PORT": "8000",
    "LOG_LEVEL": "INFO",
    # Vacio: sin TLS hacia la base (PostgreSQL local de docker compose). En Render se fija en
    # "require" desde render.yaml, porque la conexion a Supabase viaja por internet.
    "DATABASE_SSLMODE": "",
}

VARIABLES_ENTERAS: tuple[str, ...] = ("PORT",)

# Tiempo maximo para abrir una conexion a la base. Render da por fallido un health check que
# no responde en 5 segundos. El pool puede necesitar dos intentos (pre-ping de una conexion
# vieja y una conexion nueva): con 2 segundos por intento, /health contesta 503 antes del limite.
SEGUNDOS_TIMEOUT_DE_CONEXION = 2

MENSAJE_FALTANTE = "Falta la variable de entorno obligatoria: {nombre}"
MENSAJE_NO_ENTERA = "La variable de entorno {nombre} debe ser un numero entero"
MENSAJE_URL_INVALIDA = "La variable de entorno DATABASE_URL no es una URL de base de datos valida"


def _leer(nombre: str) -> str:
    """Lee una variable tratando la cadena vacia y los espacios como ausencia."""
    return (os.environ.get(nombre) or "").strip()


def obtener_faltantes() -> list[str]:
    """Nombres de las variables obligatorias ausentes o vacias, en el orden del contrato."""
    return [nombre for nombre in VARIABLES_OBLIGATORIAS if not _leer(nombre)]


def _terminar(mensajes: list[str]) -> None:
    """Loguea el fallo y corta el proceso con codigo distinto de cero.

    Se emite en dos formatos a proposito:
    - una linea JSON por problema, porque lo exige el contrato de logging;
    - la misma linea en texto plano a stderr, para que sea legible en `docker compose logs`
      y en los logs de Render sin tener que parsear JSON.

    Nunca se loguea el *valor* de ninguna variable: podrian ser secretos a medio completar.
    """
    configurar_logging(_leer("LOG_LEVEL") or "INFO")
    for mensaje in mensajes:
        registrar_evento(logging.ERROR, "configuracion_invalida", mensaje)
        print(mensaje, file=sys.stderr, flush=True)
    sys.exit(1)


def normalizar_url_de_base(url: str, sslmode: str = "") -> str:
    """Adapta la URL de la base al driver que usa el proyecto.

    Supabase entrega la cadena de conexion como `postgresql://...` (y algunos proveedores todavia
    usan el alias `postgres://`). SQLAlchemy interpreta esos esquemas con psycopg2, que no esta
    instalado: el proyecto usa psycopg 3, cuyo dialecto es `postgresql+psycopg`.

    Si `sslmode` tiene valor y la URL no trae uno propio, se agrega como parametro de la URL.
    Las URLs que no son de PostgreSQL (por ejemplo `sqlite://` en los tests) se devuelven igual.

    Levanta `ValueError` si la cadena no se puede interpretar como URL de base de datos.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")

    try:
        parseada = make_url(url)
    except Exception as error:
        raise ValueError(MENSAJE_URL_INVALIDA) from error

    if parseada.get_backend_name() != "postgresql":
        return url

    parseada = parseada.set(drivername="postgresql+psycopg")
    if sslmode and "sslmode" not in parseada.query:
        parseada = parseada.update_query_dict({"sslmode": sslmode})

    return parseada.render_as_string(hide_password=False)


def _opciones_del_engine(url: str) -> dict[str, object]:
    """Opciones del pool de SQLAlchemy segun el motor de la URL ya normalizada."""
    opciones: dict[str, object] = {
        # Descarta conexiones muertas del pool: el contenedor db se reinicia seguido en
        # desarrollo, y el pooler de Supabase puede cortar conexiones ociosas.
        "pool_pre_ping": True,
    }
    if make_url(url).get_backend_name() == "postgresql":
        opciones["connect_args"] = {"connect_timeout": SEGUNDOS_TIMEOUT_DE_CONEXION}
    return opciones


def construir_configuracion() -> dict[str, object]:
    """Arma el diccionario de configuracion listo para `app.config.update()`.

    Asume que la validacion ya paso: llamar siempre despues de `validar_o_terminar()`.
    """
    valores: dict[str, object] = {nombre: _leer(nombre) for nombre in VARIABLES_OBLIGATORIAS}

    for nombre, defecto in VARIABLES_OPCIONALES.items():
        valores[nombre] = _leer(nombre) or defecto

    problemas = []
    for nombre in VARIABLES_ENTERAS:
        try:
            valores[nombre] = int(str(valores[nombre]))
        except ValueError:
            problemas.append(MENSAJE_NO_ENTERA.format(nombre=nombre))

    try:
        url = normalizar_url_de_base(str(valores["DATABASE_URL"]), str(valores["DATABASE_SSLMODE"]))
    except ValueError as error:
        problemas.append(str(error))
        url = ""

    if problemas:
        _terminar(problemas)

    # Claves que Flask-SQLAlchemy lee con nombre propio.
    valores["SQLALCHEMY_DATABASE_URI"] = url
    valores["SQLALCHEMY_ENGINE_OPTIONS"] = _opciones_del_engine(url)
    valores["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    return valores


def validar_o_terminar() -> None:
    """Aplica la politica de fail-fast de la seccion 2 del contrato de configuracion.

    Se invoca una unica vez durante la construccion de la aplicacion (app factory), antes de
    registrar los modulos de dominio, de modo que el proceso muera sin llegar a levantar el
    servidor HTTP si la configuracion esta incompleta.
    """
    faltantes = obtener_faltantes()
    if not faltantes:
        return
    _terminar([MENSAJE_FALTANTE.format(nombre=nombre) for nombre in faltantes])
