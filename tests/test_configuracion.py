from __future__ import annotations

from datetime import timedelta

import pytest

from app import create_app
from app.core.configuracion import construir_configuracion, normalizar_url_de_base


@pytest.mark.parametrize("variable", ["SECRET_KEY", "DATABASE_URL", "JWT_SECRET_KEY"])
def test_falta_variable_obligatoria_termina_el_proceso(entorno_completo, capsys, variable):
    entorno_completo.delenv(variable)

    with pytest.raises(SystemExit) as salida:
        create_app()

    assert salida.value.code == 1
    assert f"Falta la variable de entorno obligatoria: {variable}" in capsys.readouterr().err


def test_variable_obligatoria_vacia_cuenta_como_faltante(entorno_completo):
    entorno_completo.setenv("SECRET_KEY", "   ")

    with pytest.raises(SystemExit):
        create_app()


def test_puerto_no_entero_termina_el_proceso(entorno_completo, capsys):
    entorno_completo.setenv("PORT", "ochomil")

    with pytest.raises(SystemExit):
        construir_configuracion()

    assert "PORT debe ser un numero entero" in capsys.readouterr().err


def test_valores_por_defecto_de_las_opcionales(entorno_completo):
    configuracion = construir_configuracion()

    assert configuracion["APP_ENV"] == "local"
    assert configuracion["PORT"] == 8000
    assert configuracion["LOG_LEVEL"] == "INFO"
    assert configuracion["JWT_EXPIRACION_MINUTOS"] == 60
    assert configuracion["JWT_ACCESS_TOKEN_EXPIRES"] == timedelta(minutes=60)


def test_configuracion_jwt_fija_algoritmo_emisor_y_audiencia(entorno_completo):
    configuracion = construir_configuracion()

    assert configuracion["JWT_ALGORITHM"] == "HS256"
    assert configuracion["JWT_TOKEN_LOCATION"] == ["headers"]
    assert configuracion["JWT_ENCODE_ISSUER"] == configuracion["JWT_DECODE_ISSUER"]
    assert configuracion["JWT_ENCODE_AUDIENCE"] == configuracion["JWT_DECODE_AUDIENCE"]


def test_clave_jwt_corta_termina_el_proceso(entorno_completo, capsys):
    entorno_completo.setenv("JWT_SECRET_KEY", "corta")

    with pytest.raises(SystemExit):
        construir_configuracion()

    assert "JWT_SECRET_KEY debe tener al menos 32 caracteres" in capsys.readouterr().err


@pytest.mark.parametrize("valor", ["0", "1441", "una hora"])
def test_expiracion_jwt_invalida_termina_el_proceso(entorno_completo, valor):
    entorno_completo.setenv("JWT_EXPIRACION_MINUTOS", valor)

    with pytest.raises(SystemExit):
        construir_configuracion()


def test_expiracion_jwt_configurable(entorno_completo):
    entorno_completo.setenv("JWT_EXPIRACION_MINUTOS", "15")

    assert construir_configuracion()["JWT_ACCESS_TOKEN_EXPIRES"] == timedelta(minutes=15)


@pytest.mark.parametrize(
    "original",
    [
        "postgres://usuario:clave@servidor:5432/base",
        "postgresql://usuario:clave@servidor:5432/base",
        "postgresql+psycopg://usuario:clave@servidor:5432/base",
    ],
)
def test_normalizar_url_usa_el_driver_psycopg(original):
    assert (
        normalizar_url_de_base(original) == "postgresql+psycopg://usuario:clave@servidor:5432/base"
    )


def test_normalizar_url_agrega_sslmode_si_se_pide():
    url = normalizar_url_de_base("postgresql://u:c@servidor/base", "require")

    assert url == "postgresql+psycopg://u:c@servidor/base?sslmode=require"


def test_normalizar_url_acepta_la_uri_del_pooler_de_supabase():
    # El usuario del Session pooler lleva el ref del proyecto despues de un punto.
    url = normalizar_url_de_base(
        "postgresql://postgres.abcdref:clave@aws-0-us-east-1.pooler.supabase.com:5432/postgres",
        "require",
    )

    assert url == (
        "postgresql+psycopg://postgres.abcdref:clave@aws-0-us-east-1.pooler.supabase.com:5432"
        "/postgres?sslmode=require"
    )


def test_normalizar_url_respeta_sslmode_propio_de_la_url():
    url = normalizar_url_de_base("postgresql://u:c@servidor/base?sslmode=disable", "require")

    assert url.endswith("?sslmode=disable")


def test_normalizar_url_no_toca_otros_motores():
    assert normalizar_url_de_base("sqlite://", "require") == "sqlite://"


def test_url_de_base_invalida_termina_el_proceso(entorno_completo, capsys):
    entorno_completo.setenv("DATABASE_URL", "esto no es una url")

    with pytest.raises(SystemExit):
        construir_configuracion()

    assert "DATABASE_URL no es una URL de base de datos valida" in capsys.readouterr().err


def test_postgres_tiene_timeout_de_conexion(entorno_completo):
    entorno_completo.setenv("DATABASE_URL", "postgresql://u:c@servidor/base")

    opciones = construir_configuracion()["SQLALCHEMY_ENGINE_OPTIONS"]

    assert opciones["pool_pre_ping"] is True
    assert opciones["connect_args"] == {"connect_timeout": 2}
