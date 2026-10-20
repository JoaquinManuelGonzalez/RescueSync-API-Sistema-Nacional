"""restringe niveles de certificacion

Revision ID: e7f8a9b0c1d2
Revises: d026ce7dc122
Create Date: 2026-10-19 16:05:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = ("d026ce7dc122", "b8e41c7d2f90")
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            """
            UPDATE organizacion_certificaciones
            SET nivel_riesgo_permitido = CASE nivel_riesgo_permitido
                WHEN 'BAJO' THEN 'baja'
                WHEN 'MEDIO' THEN 'media'
                WHEN 'ALTO' THEN 'alta'
                WHEN 'CRITICO' THEN 'crítica'
                ELSE nivel_riesgo_permitido
            END
            """
        )
    )
    op.create_check_constraint(
        "nivel_riesgo_permitido_valido",
        "organizacion_certificaciones",
        "nivel_riesgo_permitido IN ('baja', 'media', 'alta', 'crítica')",
    )


def downgrade():
    op.drop_constraint(
        "nivel_riesgo_permitido_valido",
        "organizacion_certificaciones",
        type_="check",
    )
