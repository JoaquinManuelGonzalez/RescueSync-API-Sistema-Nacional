"""agrega codigo compartido a los recursos

Revision ID: 9d8e7f6a5b4c
Revises: a63f9d20bc41
Create Date: 2026-10-16 23:10:00.000000
"""

import re
import unicodedata

from alembic import op
import sqlalchemy as sa


revision = "9d8e7f6a5b4c"
down_revision = "a63f9d20bc41"
branch_labels = None
depends_on = None


def _codigo_recurso(nombre: str) -> str:
    normalizado = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Z0-9]+", "_", normalizado.upper()).strip("_")
    return f"RSR-{slug}"


def upgrade():
    with op.batch_alter_table("items") as batch_op:
        batch_op.add_column(sa.Column("codigo_recurso", sa.String(length=200), nullable=True))

    conexion = op.get_bind()
    items = conexion.execute(sa.text("SELECT id, nombre FROM items")).all()
    for item_id, nombre in items:
        conexion.execute(
            sa.text("UPDATE items SET codigo_recurso = :codigo WHERE id = :item_id"),
            {"codigo": _codigo_recurso(nombre), "item_id": item_id},
        )

    with op.batch_alter_table("items") as batch_op:
        batch_op.alter_column(
            "codigo_recurso",
            existing_type=sa.String(length=200),
            nullable=False,
        )
        batch_op.create_index("ix_items_codigo_recurso", ["codigo_recurso"], unique=True)


def downgrade():
    with op.batch_alter_table("items") as batch_op:
        batch_op.drop_index("ix_items_codigo_recurso")
        batch_op.drop_column("codigo_recurso")
