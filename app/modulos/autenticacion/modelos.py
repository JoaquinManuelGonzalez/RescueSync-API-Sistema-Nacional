"""Cuentas de los clientes de la API."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.acceso import Rol
from app.extensiones import db


class Cuenta(db.Model):
    """Cliente autorizado a pedir tokens en /login: el motor de Bonita o un administrador.

    La API autentica clientes, no personas (ADR-005): las ONGs y los usuarios de la aplicacion
    web no tienen cuenta aca. `usuario` es tambien el `client_id` del modo OAuth2.
    """

    __tablename__ = "cuentas"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
    )
    usuario: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    rol: Mapped[Rol] = mapped_column(
        Enum(
            Rol,
            name="rol_enum",
            native_enum=False,
            create_constraint=False,
            length=50,
            values_callable=lambda tipo: [miembro.value for miembro in tipo],
        ),
        nullable=False,
    )
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    activa: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    ultimo_ingreso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
