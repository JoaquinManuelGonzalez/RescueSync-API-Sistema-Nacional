"""Alinear organizaciones, certificaciones e inventarios con el diagrama.

Revision ID: a63f9d20bc41
Revises: 462daf0d4c41
Create Date: 2026-10-11 17:00:00.000000

"""
from datetime import UTC, datetime
from secrets import token_urlsafe

import sqlalchemy as sa
from alembic import op
from werkzeug.security import generate_password_hash


# revision identifiers, used by Alembic.
revision = "a63f9d20bc41"
down_revision = "462daf0d4c41"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    certificaciones_anteriores = list(
        bind.execute(
            sa.text("SELECT organizacion_id, nombre, tipo FROM certificaciones")
        )
    )
    fecha_migracion = datetime.now(UTC)

    # La versión anterior no tenía credenciales. Se asignan hashes de contraseñas
    # aleatorias desconocidas para que las cuentas existentes no queden autenticables.
    op.add_column("organizaciones", sa.Column("password_hash", sa.Text(), nullable=True))
    for (organizacion_id,) in bind.execute(sa.text("SELECT id FROM organizaciones")):
        bind.execute(
            sa.text(
                "UPDATE organizaciones SET password_hash = :password_hash WHERE id = :id"
            ),
            {
                "id": organizacion_id,
                "password_hash": generate_password_hash(token_urlsafe(32)),
            },
        )
    op.alter_column("organizaciones", "password_hash", nullable=False)

    op.alter_column("organizaciones", "tipo", server_default=None)
    op.execute("ALTER TABLE organizaciones ALTER COLUMN tipo TYPE VARCHAR(255) USING tipo::text")
    op.alter_column("organizaciones", "email_contacto", new_column_name="mail_contacto")
    op.alter_column(
        "organizaciones",
        "mail_contacto",
        existing_type=sa.String(length=254),
        type_=sa.Text(),
    )
    op.alter_column(
        "organizaciones",
        "nombre",
        existing_type=sa.String(length=200),
        type_=sa.Text(),
    )
    op.drop_constraint("uq_organizaciones_email_contacto", "organizaciones", type_="unique")
    op.create_unique_constraint(
        "uq_organizaciones_mail_contacto",
        "organizaciones",
        ["mail_contacto"],
    )
    op.alter_column(
        "organizaciones",
        "telefono_contacto",
        existing_type=sa.String(length=50),
        type_=sa.Text(),
    )
    op.alter_column(
        "organizaciones",
        "identificador_nacional",
        existing_type=sa.String(length=50),
        type_=sa.Text(),
    )
    op.alter_column("organizaciones", "creada_en", new_column_name="created_at")
    op.alter_column("organizaciones", "actualizada_en", new_column_name="updated_at")

    op.execute("ALTER TABLE items ALTER COLUMN tipo TYPE VARCHAR(255) USING tipo::text")
    op.alter_column(
        "items",
        "nombre",
        existing_type=sa.String(length=150),
        type_=sa.Text(),
    )

    op.drop_constraint("fk_inventarios_organizacion_id", "inventarios", type_="foreignkey")
    op.drop_constraint("uq_inventarios_organizacion_id", "inventarios", type_="unique")
    op.alter_column("inventarios", "organizacion_id", new_column_name="id_organizacion")
    op.alter_column("inventarios", "actualizado_en", new_column_name="updated_at")
    op.create_foreign_key(
        "fk_inventarios_id_organizacion",
        "inventarios",
        "organizaciones",
        ["id_organizacion"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_inventarios_id_organizacion",
        "inventarios",
        ["id_organizacion"],
    )

    op.drop_constraint("fk_inventario_items_inventario_id", "inventario_items", type_="foreignkey")
    op.drop_constraint("fk_inventario_items_item_id", "inventario_items", type_="foreignkey")
    op.drop_constraint(
        "uq_inventario_items_inventario_id_item_id",
        "inventario_items",
        type_="unique",
    )
    op.alter_column("inventario_items", "inventario_id", new_column_name="id_inventario")
    op.alter_column("inventario_items", "item_id", new_column_name="id_item")
    op.create_foreign_key(
        "fk_inventario_items_id_inventario",
        "inventario_items",
        "inventarios",
        ["id_inventario"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_inventario_items_id_item",
        "inventario_items",
        "items",
        ["id_item"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_invitem_inv_item",
        "inventario_items",
        ["id_inventario", "id_item"],
    )

    op.drop_constraint("fk_compromisos_organizacion_id", "compromisos", type_="foreignkey")
    op.drop_constraint(
        "uq_compromisos_emergencia_externa_id_organizacion_id",
        "compromisos",
        type_="unique",
    )
    op.alter_column("compromisos", "organizacion_id", new_column_name="id_organizacion")
    op.alter_column(
        "compromisos",
        "emergencia_externa_id",
        new_column_name="id_emergencia_externa",
    )
    op.alter_column("compromisos", "estado", server_default=None)
    op.execute(
        "ALTER TABLE compromisos ALTER COLUMN nivel_gravedad "
        "TYPE VARCHAR(50) USING nivel_gravedad::text"
    )
    op.execute(
        """
        UPDATE compromisos
        SET nivel_gravedad = CASE nivel_gravedad
            WHEN 'baja' THEN 'BAJO'
            WHEN 'media' THEN 'MEDIO'
            WHEN 'alta' THEN 'ALTO'
            WHEN 'critica' THEN 'CRITICO'
            ELSE nivel_gravedad
        END
        """
    )
    op.execute("ALTER TABLE compromisos ALTER COLUMN estado TYPE VARCHAR(50) USING estado::text")
    op.execute(
        """
        UPDATE compromisos
        SET estado = CASE estado
            WHEN 'comprometido' THEN 'COMPROMETIDO'
            WHEN 'liberado' THEN 'LIBERADO'
            WHEN 'cancelado' THEN 'CANCELADO'
            ELSE estado
        END
        """
    )
    op.alter_column(
        "compromisos",
        "estado",
        server_default="COMPROMETIDO",
    )
    op.create_foreign_key(
        "fk_compromisos_id_organizacion",
        "compromisos",
        "organizaciones",
        ["id_organizacion"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_compromiso_org_emergencia",
        "compromisos",
        ["id_emergencia_externa", "id_organizacion"],
    )

    op.drop_constraint(
        "fk_compromiso_items_compromiso_id",
        "compromiso_items",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_compromiso_items_inventario_item_id",
        "compromiso_items",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_compromiso_items_compromiso_id_inventario_item_id",
        "compromiso_items",
        type_="unique",
    )
    op.alter_column("compromiso_items", "compromiso_id", new_column_name="id_compromiso")
    op.alter_column(
        "compromiso_items",
        "inventario_item_id",
        new_column_name="id_inventario_item",
    )
    op.execute(
        "ALTER TABLE compromiso_items ALTER COLUMN tipo_asignacion "
        "TYPE VARCHAR(50) USING tipo_asignacion::text"
    )
    op.create_foreign_key(
        "fk_compromiso_items_id_compromiso",
        "compromiso_items",
        "compromisos",
        ["id_compromiso"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_compromiso_items_id_inventario_item",
        "compromiso_items",
        "inventario_items",
        ["id_inventario_item"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_compitem_comp_invitem",
        "compromiso_items",
        ["id_compromiso", "id_inventario_item"],
    )

    op.drop_table("certificaciones")
    op.create_table(
        "certificaciones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("tipo", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_certificaciones"),
    )
    op.create_table(
        "organizacion_certificaciones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("id_organizacion", sa.BigInteger(), nullable=False),
        sa.Column("id_certificacion", sa.Integer(), nullable=False),
        sa.Column("nivel_riesgo_permitido", sa.String(length=50), nullable=False),
        sa.Column("fecha_emision", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fecha_vencimiento", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["id_organizacion"],
            ["organizaciones.id"],
            name="fk_organizacion_certificaciones_id_organizacion",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_certificacion"],
            ["certificaciones.id"],
            name="fk_organizacion_certificaciones_id_certificacion",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organizacion_certificaciones"),
        sa.UniqueConstraint(
            "id_organizacion",
            "id_certificacion",
            name="uq_orgcert_org_cert",
        ),
    )

    ids_certificaciones = {}
    for nombre, tipo in sorted(
        {(fila.nombre, fila.tipo) for fila in certificaciones_anteriores}
    ):
        certificacion_id = bind.execute(
            sa.text(
                "INSERT INTO certificaciones (nombre, tipo) "
                "VALUES (:nombre, :tipo) RETURNING id"
            ),
            {"nombre": nombre, "tipo": tipo},
        ).scalar_one()
        ids_certificaciones[(nombre, tipo)] = certificacion_id

    asignaciones = {
        (fila.organizacion_id, fila.nombre, fila.tipo) for fila in certificaciones_anteriores
    }
    for organizacion_id, nombre, tipo in sorted(asignaciones):
        bind.execute(
            sa.text(
                """
                INSERT INTO organizacion_certificaciones
                    (id_organizacion, id_certificacion, nivel_riesgo_permitido, fecha_emision)
                VALUES (:organizacion_id, :certificacion_id, 'BAJO', :fecha_emision)
                """
            ),
            {
                "organizacion_id": organizacion_id,
                "certificacion_id": ids_certificaciones[(nombre, tipo)],
                "fecha_emision": fecha_migracion,
            },
        )

    op.execute("DROP TYPE tipo_organizacion_enum")
    op.execute("DROP TYPE tipo_item_enum")
    op.execute("DROP TYPE tipo_certificacion_enum")
    op.execute("DROP TYPE nivel_gravedad_enum")
    op.execute("DROP TYPE estado_compromiso_enum")
    op.execute("DROP TYPE tipo_asignacion_enum")


def downgrade():
    raise NotImplementedError(
        "La migración transforma certificaciones existentes y convierte enums a VARCHAR; "
        "el downgrade requiere una restauración controlada desde respaldo."
    )
