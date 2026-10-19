"""Guardián: ninguna ruta de la API queda abierta sin querer.

Recorre todas las rutas registradas y exige 401 sin token, salvo las de RUTAS_PUBLICAS. Un
endpoint nuevo que se olvide de `@blp.requiere_rol(...)` hace fallar este test en el CI.
Para publicar una ruta a propósito hay que agregarla a la lista y justificarlo en el PR.
"""

from __future__ import annotations

import re

from app.core.acceso import ESQUEMAS_DE_SEGURIDAD

RUTAS_PUBLICAS = frozenset(
    {
        "/health",  # healthcheck de Docker y de Render
        "/login",  # emite los tokens
        "/openapi.json",  # especificación
        "/docs",  # Swagger UI
        "/docs/",
        "/static/<path:filename>",
        "/docs/<path:filename>",
    }
)
METODOS_IGNORADOS = frozenset({"HEAD", "OPTIONS"})


def _rutas_privadas(app):
    for regla in app.url_map.iter_rules():
        if regla.rule in RUTAS_PUBLICAS:
            continue
        for metodo in sorted(regla.methods - METODOS_IGNORADOS):
            # Los parámetros se completan con un valor cualquiera: sin token no se llega a usarlos.
            yield metodo, re.sub(r"<(?:[^:>]+:)?[^>]+>", "1", regla.rule)


def test_todas_las_rutas_privadas_exigen_token(app, cliente, base_de_datos):
    privadas = list(_rutas_privadas(app))
    assert privadas, "No se encontraron rutas privadas: revisar el recorrido del url_map."

    abiertas = []
    for metodo, ruta in privadas:
        respuesta = cliente.open(ruta, method=metodo, json={})
        if respuesta.status_code != 401:
            abiertas.append((metodo, ruta, respuesta.status_code))

    assert not abiertas, f"Rutas sin @requiere_rol: {abiertas}"


def test_todas_las_operaciones_privadas_documentan_seguridad(cliente):
    especificacion = cliente.get("/openapi.json").get_json()

    sin_seguridad = [
        (metodo.upper(), ruta)
        for ruta, operaciones in especificacion["paths"].items()
        for metodo, operacion in operaciones.items()
        if ruta not in RUTAS_PUBLICAS
        and isinstance(operacion, dict)
        and operacion.get("security") != ESQUEMAS_DE_SEGURIDAD
    ]

    assert not sin_seguridad, f"Operaciones sin security en OpenAPI: {sin_seguridad}"
