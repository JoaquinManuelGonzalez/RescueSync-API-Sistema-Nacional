"""cierra los compromisos de emergencias que no tienen un UUID

Revision ID: 8c3f1e5a7b20
Revises: 5b9d3e7a1c42
Create Date: 2026-11-17 20:30:00.000000

Desde 5b9d3e7a1c42 la API solo acepta emergencias identificadas por un UUID, y lo guarda en su
forma canónica (minúsculas y con guiones). Los compromisos anteriores tienen ids enteros ("14",
"22") o textos libres ("emergencia-postman-01"), que ya no se pueden liberar ni finalizar por la
API: las rutas exigen un UUID y las webs renumeraron sus emergencias. Los que seguían
COMPROMETIDO quedaban trabados para siempre y la disponibilidad los contaba como comprometidos,
inflando el total de cada recurso.

Esta migración los pasa a LIBERADO con fecha de liberación y de cierre, igual que una
finalización, pero **sin devolver stock**: `flask seed` ya repuso el depósito de demostración en
cada deploy (sube a su stock inicial lo que estuviera por debajo), así que sumar lo comprometido
lo dejaría por encima. Lo que no repone el seed son inventarios de ONGs creadas en pruebas.

También deja en la base los comentarios de columna que el modelo ya tenía y la base no (las
fechas de finalización y cierre los perdieron en 4a7c2d9e1f63), para que `flask db check` no
encuentre diferencias.

El downgrade restaura los comentarios. Los compromisos cerrados no vuelven a COMPROMETIDO: no
hay forma de distinguirlos de los liberados por el proceso, y volver a reservarlos dejaría el
stock trabado otra vez.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "8c3f1e5a7b20"
down_revision = "5b9d3e7a1c42"
branch_labels = None
depends_on = None

UUID_CANONICO = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

COMENTARIO_EMERGENCIA = (
    "UUID canónico de la emergencia en la aplicación web. Los compromisos anteriores a "
    "5b9d3e7a1c42 pueden tener otro formato."
)
COMENTARIO_EMERGENCIA_ANTERIOR = "Identificador opaco de la emergencia en RescueSync o Bonita."
COMENTARIO_FINALIZACION_ONG = "Momento en que la ONG informó que terminó sus actividades."
COMENTARIO_CIERRE_PROYECTO = (
    "Se establece para todos los compromisos cuando finalizaron todas las ONGs."
)


# Columna -> (tipo, nulable), para que alter_column no cambie nada más que el comentario.
COLUMNAS = {
    "id_emergencia_externa": (sa.String(255), False),
    "fecha_finalizacion_ong": (sa.DateTime(timezone=True), True),
    "fecha_cierre_proyecto": (sa.DateTime(timezone=True), True),
}


def _comentar(columna: str, comentario: str | None) -> None:
    tipo, nulable = COLUMNAS[columna]
    op.alter_column(
        "compromisos",
        columna,
        existing_type=tipo,
        existing_nullable=nulable,
        comment=comentario,
    )


def upgrade():
    conexion = op.get_bind()
    if conexion.dialect.name != "postgresql":
        raise RuntimeError("Esta migración solo corre sobre PostgreSQL.")

    conexion.execute(
        sa.text(
            "UPDATE compromisos "
            "SET estado = 'LIBERADO', fecha_liberacion = now(), fecha_cierre_proyecto = now() "
            "WHERE estado = 'COMPROMETIDO' AND id_emergencia_externa !~ :uuid"
        ),
        {"uuid": UUID_CANONICO},
    )

    _comentar("id_emergencia_externa", COMENTARIO_EMERGENCIA)
    _comentar("fecha_finalizacion_ong", COMENTARIO_FINALIZACION_ONG)
    _comentar("fecha_cierre_proyecto", COMENTARIO_CIERRE_PROYECTO)


def downgrade():
    _comentar("id_emergencia_externa", COMENTARIO_EMERGENCIA_ANTERIOR)
    _comentar("fecha_finalizacion_ong", None)
    _comentar("fecha_cierre_proyecto", None)
