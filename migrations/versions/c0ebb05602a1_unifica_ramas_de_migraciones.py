"""unifica ramas de migraciones

Revision ID: c0ebb05602a1
Revises: 9d8e7f6a5b4c, b8e41c7d2f90
Create Date: 2026-10-17 19:12:44.181750

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c0ebb05602a1"
down_revision = ("9d8e7f6a5b4c", "b8e41c7d2f90")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
