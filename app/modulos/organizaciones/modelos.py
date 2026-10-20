"""Modelos base de organizaciones proveedoras e inventario del Sistema Nacional."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensiones import db

if TYPE_CHECKING:
    from app.modulos.autenticacion.modelos import Cuenta
    from app.modulos.compromisos.modelos import Compromiso, CompromisoItem


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


class NivelCertificacion(enum.Enum):
    """Nivel de certificación que habilita una organización para ofrecer recursos."""

    baja = "baja"
    media = "media"
    alta = "alta"
    critica = "crítica"


class EstadoHabilitacion(enum.Enum):
    """Estado de una organización en el padrón nacional.

    Solo una organización `habilitada` puede comprometer recursos. Las transiciones permitidas
    están en `organizaciones/servicios.py` y cada cambio queda en `HistorialHabilitacion`.
    """

    pendiente = "pendiente"
    habilitada = "habilitada"
    suspendida = "suspendida"


def _valores_enum(tipo_enum: type[enum.Enum]) -> list[str]:
    return [miembro.value for miembro in tipo_enum]


class Organizacion(db.Model):
    """ONG u organismo de rescate registrado en el Sistema Nacional."""

    __tablename__ = "organizaciones"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
    )
    tipo: Mapped[TipoOrganizacion] = mapped_column(
        Enum(
            TipoOrganizacion,
            name="tipo_organizacion_enum",
            native_enum=False,
            create_constraint=False,
            length=255,
            values_callable=_valores_enum,
        ),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    mail_contacto: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    telefono_contacto: Mapped[str | None] = mapped_column(Text, nullable=True)
    identificador_nacional: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        unique=True,
        comment="CUIT con formato NN-NNNNNNNN-N. Es la clave compartida con la aplicación web.",
    )
    estado_habilitacion: Mapped[EstadoHabilitacion] = mapped_column(
        Enum(
            EstadoHabilitacion,
            name="estado_habilitacion_enum",
            native_enum=False,
            create_constraint=False,
            length=50,
            values_callable=_valores_enum,
        ),
        nullable=False,
        default=EstadoHabilitacion.pendiente,
        server_default=EstadoHabilitacion.pendiente.value,
    )
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

    inventario: Mapped[Inventario | None] = relationship(
        back_populates="organizacion",
        cascade="all, delete-orphan",
        uselist=False,
    )
    certificaciones: Mapped[list[OrganizacionCertificacion]] = relationship(
        back_populates="organizacion",
        cascade="all, delete-orphan",
    )
    compromisos: Mapped[list[Compromiso]] = relationship(
        "Compromiso",
        back_populates="organizacion",
    )
    historial_habilitacion: Mapped[list[HistorialHabilitacion]] = relationship(
        back_populates="organizacion",
        cascade="all, delete-orphan",
        order_by="HistorialHabilitacion.id",
    )


class HistorialHabilitacion(db.Model):
    """Cada cambio de estado de habilitación de una organización, incluida el alta."""

    __tablename__ = "historial_habilitaciones"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
    )
    organizacion_id: Mapped[int] = mapped_column(
        "id_organizacion",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("organizaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    estado_anterior: Mapped[EstadoHabilitacion | None] = mapped_column(
        Enum(
            EstadoHabilitacion,
            name="estado_habilitacion_enum",
            native_enum=False,
            create_constraint=False,
            length=50,
            values_callable=_valores_enum,
        ),
        nullable=True,
        comment="Null en el alta.",
    )
    estado_nuevo: Mapped[EstadoHabilitacion] = mapped_column(
        Enum(
            EstadoHabilitacion,
            name="estado_habilitacion_enum",
            native_enum=False,
            create_constraint=False,
            length=50,
            values_callable=_valores_enum,
        ),
        nullable=False,
    )
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    cuenta_id: Mapped[int | None] = mapped_column(
        "id_cuenta",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("cuentas.id", ondelete="SET NULL"),
        nullable=True,
        comment="Cuenta de la API que hizo el cambio. Null en semillas y migraciones.",
    )
    usuario_bonita: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="X-Usuario-Bonita: persona que disparó el cambio desde el proceso.",
    )
    caso_bonita: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="X-Bonita-Process-Instance-Id: caso del proceso que hizo el cambio.",
    )
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    organizacion: Mapped[Organizacion] = relationship(back_populates="historial_habilitacion")
    cuenta: Mapped[Cuenta | None] = relationship()


class Certificacion(db.Model):
    """Catálogo de certificaciones del Sistema Nacional."""

    __tablename__ = "certificaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[TipoItem] = mapped_column(
        Enum(
            TipoItem,
            name="tipo_certificacion_enum",
            native_enum=False,
            create_constraint=False,
            length=255,
            values_callable=_valores_enum,
        ),
        nullable=False,
    )

    organizaciones: Mapped[list[OrganizacionCertificacion]] = relationship(
        back_populates="certificacion",
        cascade="all, delete-orphan",
    )


class Item(db.Model):
    """Tipo de recurso o suministro que puede formar parte de un inventario."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_recurso: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    tipo: Mapped[TipoItem] = mapped_column(
        Enum(
            TipoItem,
            name="tipo_item_enum",
            native_enum=False,
            create_constraint=False,
            length=255,
            values_callable=_valores_enum,
        ),
        nullable=False,
    )
    unidad_medida: Mapped[str] = mapped_column(String(50), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consumible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    inventario_items: Mapped[list[InventarioItem]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
    )


class Inventario(db.Model):
    """Inventario nacional asociado a una organización proveedora."""

    __tablename__ = "inventarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(
        "id_organizacion",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("organizaciones.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        "updated_at",
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
    """Disponibilidad de un ítem dentro de un inventario."""

    __tablename__ = "inventario_items"
    __table_args__ = (
        UniqueConstraint(
            "id_inventario",
            "id_item",
            name="uq_invitem_inv_item",
        ),
        CheckConstraint("cantidad_disponible >= 0", name="cantidad_disponible_no_negativa"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventario_id: Mapped[int] = mapped_column(
        "id_inventario",
        Integer,
        ForeignKey("inventarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id: Mapped[int] = mapped_column(
        "id_item",
        Integer,
        ForeignKey("items.id"),
        nullable=False,
    )
    cantidad_disponible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    inventario: Mapped[Inventario] = relationship(back_populates="items")
    item: Mapped[Item] = relationship(back_populates="inventario_items")
    compromisos: Mapped[list[CompromisoItem]] = relationship(
        "CompromisoItem",
        back_populates="inventario_item",
    )


class OrganizacionCertificacion(db.Model):
    """Certificación asignada a una organización, con riesgo y vigencia."""

    __tablename__ = "organizacion_certificaciones"
    __table_args__ = (
        UniqueConstraint(
            "id_organizacion",
            "id_certificacion",
            name="uq_orgcert_org_cert",
        ),
        CheckConstraint(
            "nivel_riesgo_permitido IN ('baja', 'media', 'alta', 'crítica')",
            name="nivel_riesgo_permitido_valido",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organizacion_id: Mapped[int] = mapped_column(
        "id_organizacion",
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("organizaciones.id", ondelete="CASCADE"),
        nullable=False,
    )
    certificacion_id: Mapped[int] = mapped_column(
        "id_certificacion",
        Integer,
        ForeignKey("certificaciones.id", ondelete="CASCADE"),
        nullable=False,
    )
    nivel_riesgo_permitido: Mapped[NivelCertificacion] = mapped_column(
        Enum(
            NivelCertificacion,
            name="nivel_certificacion_enum",
            native_enum=False,
            create_constraint=False,
            length=50,
            values_callable=_valores_enum,
        ),
        nullable=False,
    )
    fecha_emision: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_vencimiento: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    organizacion: Mapped[Organizacion] = relationship(back_populates="certificaciones")
    certificacion: Mapped[Certificacion] = relationship(back_populates="organizaciones")
