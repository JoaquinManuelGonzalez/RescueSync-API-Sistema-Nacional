"""linea base del esquema

Esta revision no crea ninguna tabla, y eso es deliberado.

El esquema de dominio del Sistema Nacional lo define la epica "Diseno e implementacion de la BD
del Sistema Nacional". Lo que esta revision aporta es la tabla de control `alembic_version`: al
aplicarla, la base queda registrada en esta revision, y eso permite verificar de punta a punta
el pipeline de migraciones (local, CI y Render) antes de que existan los modelos.

La primera revision con tablas se genera cuando existan los modelos, con:

    docker compose exec api flask db migrate -m "descripcion del cambio"

Revision ID: 0001
Revises:
Create Date: 2026-10-03

"""

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Sin cambios de esquema: solo deja la base sellada en esta revision."""
    pass


def downgrade():
    """Sin cambios que revertir."""
    pass
