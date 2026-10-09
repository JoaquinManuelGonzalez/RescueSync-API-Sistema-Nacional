"""Modelos base de organizaciones proveedoras e inventario del Sistema Nacional."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensiones import db


class TipoOrganizacion(enum.Enum):
    """Tipos de entidad proveedora que pueden declarar recursos."""

    ong = "ong"
    organismo_rescate = "organismo_rescate"


class TipoItem(enum.Enum):
    """Categorías iniciales del catálogo de recursos y suministros."""

    personal_medico = "personal_medico"
    rescate = "rescate"
    alimentos = "alimentos"
    agua = "agua"
    abrigo = "abrigo"
    medicamentos = "medicamentos"
    maquinaria = "maquinaria"
    otro = "otro"


class Organizacion(db.Model):
    """ONG u organismo de rescate registrado en el Sistema Nacional."""

    __tablename__ = "organizaciones"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
    )
    tipo: Mapped[TipoOrganizacion] = mapped_column(
        Enum(TipoOrganizacion, name="tipo_organizacion_enum"),
        nullable=False,
        default=TipoOrganizacion.ong,
        server_default=TipoOrganizacion.ong.value,
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    email_contacto: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    telefono_contacto: Mapped[str | None] = mapped_column(String(50), nullable=True)
    identificador_nacional: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        comment="CUIT u otro identificador oficial.",
    )
    activa: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    inventario: Mapped[Inventario | None] = relationship(
        back_populates="organizacion",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Item(db.Model):
    """Tipo de recurso o suministro que puede formar parte de un inventario."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    tipo: Mapped[TipoItem] = mapped_column(
        Enum(TipoItem, name="tipo_item_enum"),
        nullable=False,
    )
    unidad_medida: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)

    inventario_items: Mapped[list[InventarioItem]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
    )


class Inventario(db.Model):
    """Inventario nacional asociado a una organización proveedora."""

    __tablename__ = "inventarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("organizaciones.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    organizacion: Mapped[Organizacion] = relationship(back_populates="inventario")
    items: Mapped[list[InventarioItem]] = relationship(
        back_populates="inventario",
        cascade="all, delete-orphan",
    )


class InventarioItem(db.Model):
    """Existencias totales y disponibles de un ítem en un inventario."""

    __tablename__ = "inventario_items"
    __table_args__ = (
        UniqueConstraint("inventario_id", "item_id"),
        CheckConstraint("cantidad_total >= 0", name="cantidad_total_no_negativa"),
        CheckConstraint("cantidad_disponible >= 0", name="cantidad_disponible_no_negativa"),
        CheckConstraint(
            "cantidad_disponible <= cantidad_total",
            name="cantidad_disponible_no_supera_total",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventario_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("inventarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("items.id"),
        nullable=False,
    )
    cantidad_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cantidad_disponible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    inventario: Mapped[Inventario] = relationship(back_populates="items")
    item: Mapped[Item] = relationship(back_populates="inventario_items")
