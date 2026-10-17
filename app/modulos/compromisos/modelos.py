"""Modelos del ciclo de vida de los compromisos de recursos."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensiones import db
from app.modulos.organizaciones.modelos import InventarioItem, Organizacion


class NivelGravedad(enum.Enum):
    """Nivel de gravedad de la emergencia al reservar recursos."""

    baja = "BAJO"
    media = "MEDIO"
    alta = "ALTO"
    critica = "CRITICO"


class EstadoCompromiso(enum.Enum):
    """Estados posibles del compromiso de recursos."""

    comprometido = "COMPROMETIDO"
    liberado = "LIBERADO"
    cancelado = "CANCELADO"


class TipoAsignacion(enum.Enum):
    """Uso de la capacidad validada para la organización en una emergencia."""

    pendiente = "pendiente"
    principal = "principal"
    apoyo = "apoyo"
    rechazada = "rechazada"


def _valores_enum(tipo_enum: type[enum.Enum]) -> list[str]:
    return [miembro.value for miembro in tipo_enum]


class Compromiso(db.Model):
    """Reserva de recursos de una organización para una emergencia externa."""

    __tablename__ = "compromisos"
    __table_args__ = (
        UniqueConstraint(
            "id_emergencia_externa",
            "id_organizacion",
            name="uq_compromiso_org_emergencia",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(
        "id_organizacion",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("organizaciones.id"),
        nullable=False,
    )
    emergencia_externa_id: Mapped[str] = mapped_column(
        "id_emergencia_externa",
        String(255),
        nullable=False,
        comment="Identificador opaco de la emergencia en RescueSync o Bonita.",
    )
    nivel_gravedad: Mapped[NivelGravedad] = mapped_column(
        Enum(
            NivelGravedad,
            name="nivel_gravedad_enum",
            native_enum=False,
            create_constraint=False,
            length=50,
            values_callable=_valores_enum,
        ),
        nullable=False,
    )
    estado: Mapped[EstadoCompromiso] = mapped_column(
        Enum(
            EstadoCompromiso,
            name="estado_compromiso_enum",
            native_enum=False,
            create_constraint=False,
            length=50,
            values_callable=_valores_enum,
        ),
        nullable=False,
        default=EstadoCompromiso.comprometido,
        server_default=EstadoCompromiso.comprometido.value,
    )
    fecha_compromiso: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    fecha_liberacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    fecha_finalizacion_ong: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Momento en que la ONG informó que terminó sus actividades.",
    )
    fecha_cierre_proyecto: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Se establece para todos los compromisos cuando finalizaron todas las ONGs.",
    )

    organizacion: Mapped[Organizacion] = relationship(
        "Organizacion",
        back_populates="compromisos",
    )
    items: Mapped[list[CompromisoItem]] = relationship(
        "CompromisoItem",
        back_populates="compromiso",
        cascade="all, delete-orphan",
    )


class CompromisoItem(db.Model):
    """Cantidad comprometida de una fila de inventario para una emergencia."""

    __tablename__ = "compromiso_items"
    __table_args__ = (
        UniqueConstraint(
            "id_compromiso",
            "id_inventario_item",
            name="uq_compitem_comp_invitem",
        ),
        CheckConstraint("cantidad_comprometida > 0", name="cantidad_comprometida_positiva"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    compromiso_id: Mapped[int] = mapped_column(
        "id_compromiso",
        Integer,
        ForeignKey("compromisos.id", ondelete="CASCADE"),
        nullable=False,
    )
    inventario_item_id: Mapped[int] = mapped_column(
        "id_inventario_item",
        Integer,
        ForeignKey("inventario_items.id"),
        nullable=False,
    )
    cantidad_comprometida: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_asignacion: Mapped[TipoAsignacion] = mapped_column(
        Enum(
            TipoAsignacion,
            name="tipo_asignacion_enum",
            native_enum=False,
            create_constraint=False,
            length=50,
            values_callable=_valores_enum,
        ),
        nullable=False,
    )

    compromiso: Mapped[Compromiso] = relationship("Compromiso", back_populates="items")
    inventario_item: Mapped[InventarioItem] = relationship(
        "InventarioItem",
        back_populates="compromisos",
    )
