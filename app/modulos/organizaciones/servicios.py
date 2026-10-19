"""Servicios del padrón nacional de organizaciones.

Es la API pública del módulo: otros módulos (por ejemplo, la evaluación de ofertas) consultan el
padrón a través de estas funciones y no de los modelos. La aplicación web y el Sistema Nacional
identifican a una organización por su CUIT (`identificador_nacional`), no por su id.
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.acceso import Actor
from app.core.errores import ConflictoDeEstado, RecursoNoEncontrado, SolicitudInvalida
from app.extensiones import db
from app.modulos.organizaciones.modelos import (
    EstadoHabilitacion,
    HistorialHabilitacion,
    Organizacion,
    TipoOrganizacion,
)

# A qué estados se puede pasar desde cada estado. Nunca se vuelve a `pendiente`: ese estado
# solo existe entre el alta y la primera decisión del administrador.
TRANSICIONES: dict[EstadoHabilitacion, frozenset[EstadoHabilitacion]] = {
    EstadoHabilitacion.pendiente: frozenset(
        {EstadoHabilitacion.habilitada, EstadoHabilitacion.suspendida}
    ),
    EstadoHabilitacion.habilitada: frozenset({EstadoHabilitacion.suspendida}),
    EstadoHabilitacion.suspendida: frozenset({EstadoHabilitacion.habilitada}),
}

MOTIVO_ALTA = "Alta en el padrón nacional."


def normalizar_cuit(valor: str) -> str:
    """Acepta 11 dígitos con o sin guiones y devuelve el formato NN-NNNNNNNN-N.

    No se valida el dígito verificador: los CUIT de demostración son ficticios y los comparte la
    aplicación web, que los usa como clave para cruzar sus organizaciones con el padrón.
    """
    digitos = re.sub(r"[\s-]", "", valor or "")
    if not re.fullmatch(r"\d{11}", digitos):
        raise SolicitudInvalida(
            "El CUIT tiene que tener 11 dígitos, con o sin guiones (por ejemplo 30-12345678-9).",
            detalle={"cuit": valor},
        )
    return f"{digitos[:2]}-{digitos[2:10]}-{digitos[10]}"


def obtener_por_cuit(cuit: str) -> Organizacion:
    """La organización del padrón con ese CUIT. 404 si no está registrada."""
    normalizado = normalizar_cuit(cuit)
    organizacion = db.session.scalar(
        select(Organizacion).where(Organizacion.identificador_nacional == normalizado)
    )
    if organizacion is None:
        raise RecursoNoEncontrado(
            "No hay ninguna organización con ese CUIT en el padrón nacional.",
            detalle={"cuit": normalizado},
        )
    return organizacion


def estado_de(cuit: str) -> EstadoHabilitacion | None:
    """Estado de habilitación de una organización, o None si no está en el padrón.

    Pensada para la evaluación de ofertas: una organización que no esté `habilitada` no puede
    comprometer recursos, y la evaluación lo informa con su motivo en lugar de rechazar a ciegas.
    """
    try:
        return obtener_por_cuit(cuit).estado_habilitacion
    except RecursoNoEncontrado:
        return None


def ultimo_motivo(organizacion: Organizacion) -> str | None:
    """Motivo del último cambio de estado (por ejemplo, por qué está suspendida)."""
    if not organizacion.historial_habilitacion:
        return None
    return organizacion.historial_habilitacion[-1].motivo


def registrar_organizacion(datos: dict, actor: Actor | None) -> Organizacion:
    """Onboarding: da de alta la organización en estado `pendiente` y registra el alta."""
    cuit = normalizar_cuit(datos["cuit"])
    nombre = datos["nombre"].strip()
    mail = datos["mail_contacto"].strip()
    _rechazar_duplicado(cuit, nombre, mail)

    organizacion = Organizacion(
        tipo=datos.get("tipo") or TipoOrganizacion.ong,
        nombre=nombre,
        mail_contacto=mail,
        telefono_contacto=datos.get("telefono_contacto"),
        identificador_nacional=cuit,
        estado_habilitacion=EstadoHabilitacion.pendiente,
    )
    organizacion.historial_habilitacion.append(
        _nuevo_registro(None, EstadoHabilitacion.pendiente, MOTIVO_ALTA, actor)
    )
    db.session.add(organizacion)
    try:
        db.session.commit()
    except IntegrityError:
        # Dos altas simultáneas con el mismo CUIT: la restricción única de la base frena la
        # segunda. Se informa igual que el duplicado detectado antes de insertar.
        db.session.rollback()
        _rechazar_duplicado(cuit, nombre, mail)
        raise
    return organizacion


def cambiar_estado_habilitacion(
    cuit: str, estado_nuevo: EstadoHabilitacion, motivo: str | None, actor: Actor | None
) -> Organizacion:
    """Aplica una transición de estado y la registra en el historial.

    La fila se bloquea (SELECT ... FOR UPDATE) para que dos cambios simultáneos sobre la misma
    organización se ordenen y cada uno valide la transición contra el estado real.
    """
    normalizado = normalizar_cuit(cuit)
    organizacion = db.session.scalar(
        select(Organizacion)
        .where(Organizacion.identificador_nacional == normalizado)
        .with_for_update()
    )
    if organizacion is None:
        raise RecursoNoEncontrado(
            "No hay ninguna organización con ese CUIT en el padrón nacional.",
            detalle={"cuit": normalizado},
        )

    actual = organizacion.estado_habilitacion
    permitidas = TRANSICIONES[actual]
    if estado_nuevo not in permitidas:
        mensaje = (
            f"La organización ya está {actual.value}."
            if estado_nuevo is actual
            else f"No se puede pasar de {actual.value} a {estado_nuevo.value}."
        )
        raise ConflictoDeEstado(
            mensaje,
            detalle={
                "estado_actual": actual.value,
                "estado_pedido": estado_nuevo.value,
                "transiciones_permitidas": sorted(estado.value for estado in permitidas),
            },
        )

    organizacion.estado_habilitacion = estado_nuevo
    organizacion.historial_habilitacion.append(_nuevo_registro(actual, estado_nuevo, motivo, actor))
    db.session.commit()
    return organizacion


def _rechazar_duplicado(cuit: str, nombre: str, mail: str) -> None:
    """409 si ya hay una organización con ese CUIT, nombre o mail (sin mirar mayúsculas)."""
    criterios = (
        ("cuit", Organizacion.identificador_nacional == cuit),
        ("nombre", func.lower(Organizacion.nombre) == nombre.lower()),
        ("mail_contacto", func.lower(Organizacion.mail_contacto) == mail.lower()),
    )
    for campo, condicion in criterios:
        existente = db.session.scalar(select(Organizacion).where(condicion))
        if existente is not None:
            raise ConflictoDeEstado(
                "Ya existe una organización en el padrón con ese "
                f"{'CUIT' if campo == 'cuit' else campo.replace('_', ' ')}.",
                detalle={
                    "campo": campo,
                    "cuit": existente.identificador_nacional,
                    "estado_habilitacion": existente.estado_habilitacion.value,
                },
            )


def _nuevo_registro(
    anterior: EstadoHabilitacion | None,
    nuevo: EstadoHabilitacion,
    motivo: str | None,
    actor: Actor | None,
) -> HistorialHabilitacion:
    return HistorialHabilitacion(
        estado_anterior=anterior,
        estado_nuevo=nuevo,
        motivo=motivo,
        cuenta_id=actor.cuenta_id if actor else None,
        usuario_bonita=actor.usuario_bonita if actor else None,
        caso_bonita=actor.caso_bonita if actor else None,
    )
