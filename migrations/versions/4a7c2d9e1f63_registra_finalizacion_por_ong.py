"""registra finalización de actividades y cierre de proyecto

Revision ID: 4a7c2d9e1f63
Revises: c0ebb05602a1
Create Date: 2026-10-17 20:42:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4a7c2d9e1f63"
down_revision = "c0ebb05602a1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("compromisos") as batch_op:
        batch_op.add_column(
            sa.Column("fecha_finalizacion_ong", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("fecha_cierre_proyecto", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("compromisos") as batch_op:
        batch_op.drop_column("fecha_cierre_proyecto")
        batch_op.drop_column("fecha_finalizacion_ong")
