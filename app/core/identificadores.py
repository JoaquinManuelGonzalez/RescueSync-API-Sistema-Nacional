"""Identificadores de las entidades del Sistema Nacional.

Todas las claves primarias son UUID. Los ids enteros de cada base chocaban entre entornos: cada
aplicación web local numera sus emergencias desde 1 y todas usan la misma API, así que la
emergencia 1 de un integrante pisaba los compromisos de la de otro.

- Las filas nuevas usan UUIDv7: llevan la hora al principio, así que ordenar por `id` sigue
  siendo ordenar por fecha de alta, y los índices crecen al final como con un entero.
- Los ítems y las certificaciones del catálogo usan UUIDv5, que sale de su clave natural. Así el
  mismo recurso tiene el mismo id en todas las bases, y los ejemplos de Swagger y la colección
  Postman sirven en cualquiera. La migración que pasó las claves a UUID usa las mismas fórmulas.
"""

from __future__ import annotations

import uuid

# Espacio de nombres de los UUIDv5. No se cambia: cambiaría el id de todo el catálogo.
ESPACIO_SISTEMA_NACIONAL = uuid.UUID("6f1c2a4e-8d3b-5a97-b0e4-3c2d1f9a8b70")


def nuevo_id() -> uuid.UUID:
    """Id para una fila nueva: UUIDv7, ordenable por fecha de alta."""
    return uuid.uuid7()


def id_de_item(codigo_recurso: str) -> uuid.UUID:
    """Id fijo de un ítem del catálogo, a partir de su código compartido con la web."""
    return uuid.uuid5(ESPACIO_SISTEMA_NACIONAL, f"item:{codigo_recurso}")


def id_de_certificacion(nombre: str, tipo: str) -> uuid.UUID:
    """Id fijo de una certificación del catálogo, a partir de su nombre y su tipo."""
    return uuid.uuid5(ESPACIO_SISTEMA_NACIONAL, f"certificacion:{tipo}:{nombre}")
