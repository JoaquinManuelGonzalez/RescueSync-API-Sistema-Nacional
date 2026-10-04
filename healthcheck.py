"""Healthcheck del contenedor de la API, usado por docker-compose.yml.

Vive como script y no como un one-liner dentro del YAML para que se pueda leer y probar. Usa
solo la biblioteca estandar: la imagen no trae curl. En Render no se usa: ahi el health check lo
hace la plataforma contra `healthCheckPath: /health`.
"""

from __future__ import annotations

import os
import sys
import urllib.request

PUERTO = os.environ.get("PORT", "8000")
URL = f"http://127.0.0.1:{PUERTO}/health"

try:
    with urllib.request.urlopen(URL, timeout=4) as respuesta:
        sys.exit(0 if respuesta.status == 200 else 1)
except Exception:
    sys.exit(1)
