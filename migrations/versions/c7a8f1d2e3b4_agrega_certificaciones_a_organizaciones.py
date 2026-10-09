"""agrega certificaciones a organizaciones

Revision ID: c7a8f1d2e3b4
Revises: f5b04d297d15
Create Date: 2026-10-09 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c7a8f1d2e3b4"
down_revision = "f5b04d297d15"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "certificaciones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "organizacion_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            nullable=False,
        ),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "personal_medico",
                "rescate",
                "alimentos",
                "agua",
                "abrigo",
                "medicamentos",
                "maquinaria",
                "otro",
                name="tipo_certificacion_enum",
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organizacion_id"],
            ["organizaciones.id"],
            name=op.f("fk_certificaciones_organizacion_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_certificaciones")),
    )


def downgrade():
    op.drop_table("certificaciones")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE tipo_certificacion_enum")
