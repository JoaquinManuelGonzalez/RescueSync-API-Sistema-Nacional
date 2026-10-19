"""Cuentas de la API y estado de habilitación de las organizaciones (EPIC-61).

- Crea `cuentas`: los clientes que pueden pedir tokens en /login (Bonita y administradores).
- Reemplaza `organizaciones.activa` por `estado_habilitacion` (pendiente, habilitada, suspendida):
  las activas pasan a habilitadas y las inactivas a suspendidas.
- Elimina `organizaciones.password_hash`: las ONGs no inician sesión en la API (ADR-005).
- Crea `historial_habilitaciones` con una fila inicial por organización existente.

Revision ID: b8e41c7d2f90
Revises: a63f9d20bc41
Create Date: 2026-10-17 12:00:00.000000

"""

from secrets import token_urlsafe

import sqlalchemy as sa
from alembic import op
from werkzeug.security import generate_password_hash


# revision identifiers, used by Alembic.
revision = "b8e41c7d2f90"
down_revision = "a63f9d20bc41"
branch_labels = None
depends_on = None

COMENTARIO_CUIT_ANTERIOR = "CUIT u otro identificador oficial."
COMENTARIO_CUIT = "CUIT con formato NN-NNNNNNNN-N. Es la clave compartida con la aplicación web."


def _estado_habilitacion():
    return sa.Enum(
        "pendiente",
        "habilitada",
        "suspendida",
        name="estado_habilitacion_enum",
        native_enum=False,
        create_constraint=False,
        length=50,
    )


def upgrade():
    op.create_table(
        "cuentas",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("usuario", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "rol",
            sa.Enum(
                "sistema",
                "administrador",
                name="rol_enum",
                native_enum=False,
                create_constraint=False,
                length=50,
            ),
            nullable=False,
        ),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("activa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("ultimo_ingreso", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cuentas")),
        sa.UniqueConstraint("usuario", name=op.f("uq_cuentas_usuario")),
    )

    # activa -> estado_habilitacion. Se completa antes de exigir NOT NULL.
    op.add_column(
        "organizaciones",
        sa.Column("estado_habilitacion", _estado_habilitacion(), nullable=True),
    )
    op.execute(
        "UPDATE organizaciones SET estado_habilitacion = "
        "CASE WHEN activa THEN 'habilitada' ELSE 'suspendida' END"
    )
    op.alter_column(
        "organizaciones",
        "estado_habilitacion",
        existing_type=_estado_habilitacion(),
        nullable=False,
        server_default="pendiente",
    )
    op.drop_column("organizaciones", "activa")
    op.drop_column("organizaciones", "password_hash")
    op.alter_column(
        "organizaciones",
        "identificador_nacional",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment=COMENTARIO_CUIT,
        existing_comment=COMENTARIO_CUIT_ANTERIOR,
    )

    op.create_table(
        "historial_habilitaciones",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("id_organizacion", sa.BigInteger(), nullable=False),
        sa.Column(
            "estado_anterior",
            _estado_habilitacion(),
            nullable=True,
            comment="Null en el alta.",
        ),
        sa.Column("estado_nuevo", _estado_habilitacion(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column(
            "id_cuenta",
            sa.BigInteger(),
            nullable=True,
            comment="Cuenta de la API que hizo el cambio. Null en semillas y migraciones.",
        ),
        sa.Column(
            "usuario_bonita",
            sa.String(length=255),
            nullable=True,
            comment="X-Usuario-Bonita: persona que disparó el cambio desde el proceso.",
        ),
        sa.Column(
            "caso_bonita",
            sa.String(length=255),
            nullable=True,
            comment="X-Bonita-Process-Instance-Id: caso del proceso que hizo el cambio.",
        ),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["id_cuenta"],
            ["cuentas.id"],
            name=op.f("fk_historial_habilitaciones_id_cuenta"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["id_organizacion"],
            ["organizaciones.id"],
            name=op.f("fk_historial_habilitaciones_id_organizacion"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_historial_habilitaciones")),
    )
    op.create_index(
        op.f("ix_historial_habilitaciones_id_organizacion"),
        "historial_habilitaciones",
        ["id_organizacion"],
        unique=False,
    )
    # Punto de partida del historial: el estado con el que cada organización llega al padrón.
    op.execute(
        "INSERT INTO historial_habilitaciones (id_organizacion, estado_anterior, estado_nuevo, motivo) "
        "SELECT id, NULL, estado_habilitacion, 'Estado inicial del padrón (migración).' "
        "FROM organizaciones"
    )


def downgrade():
    op.drop_index(
        op.f("ix_historial_habilitaciones_id_organizacion"),
        table_name="historial_habilitaciones",
    )
    op.drop_table("historial_habilitaciones")

    op.alter_column(
        "organizaciones",
        "identificador_nacional",
        existing_type=sa.Text(),
        existing_nullable=True,
        comment=COMENTARIO_CUIT_ANTERIOR,
        existing_comment=COMENTARIO_CUIT,
    )

    # Igual que en a63f9d20bc41: hashes de contraseñas aleatorias desconocidas, para que las
    # organizaciones no queden autenticables.
    bind = op.get_bind()
    op.add_column("organizaciones", sa.Column("password_hash", sa.Text(), nullable=True))
    for (organizacion_id,) in bind.execute(sa.text("SELECT id FROM organizaciones")):
        bind.execute(
            sa.text("UPDATE organizaciones SET password_hash = :password_hash WHERE id = :id"),
            {"id": organizacion_id, "password_hash": generate_password_hash(token_urlsafe(32))},
        )
    op.alter_column("organizaciones", "password_hash", nullable=False)

    op.add_column(
        "organizaciones",
        sa.Column("activa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.execute("UPDATE organizaciones SET activa = (estado_habilitacion = 'habilitada')")
    op.drop_column("organizaciones", "estado_habilitacion")

    op.drop_table("cuentas")
