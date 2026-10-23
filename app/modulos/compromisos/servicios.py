"""Operaciones transaccionales de bloqueo y compromiso de recursos."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.errores import ConflictoDeEstado, RecursoNoEncontrado, ReglaDeNegocioIncumplida
from app.extensiones import db
from app.modulos.compromisos.modelos import (
    Compromiso,
    CompromisoItem,
    EstadoCompromiso,
    NivelGravedad,
    TipoAsignacion,
)
from app.modulos.organizaciones.modelos import (
    EstadoHabilitacion,
    Inventario,
    InventarioItem,
    Item,
    Organizacion,
)


class DisponibilidadInsuficiente(ReglaDeNegocioIncumplida):
    """El stock disponible no alcanza para comprometer la solicitud completa."""


@dataclass(frozen=True)
class AporteSolicitado:
    identificador_nacional: str
    codigo_recurso: str
    cantidad: int
    tipo_asignacion: TipoAsignacion


@dataclass(frozen=True)
class ResultadoCompromiso:
    compromisos: tuple[Compromiso, ...]
    repetido: bool


@dataclass(frozen=True)
class MotivoFallo:
    identificador_nacional: str
    codigo_recurso: str
    cantidad_solicitada: int
    cantidad_disponible: int
    motivo: str


@dataclass(frozen=True)
class ResultadoValidacion:
    valido: bool
    motivos: tuple[MotivoFallo, ...]


@dataclass(frozen=True)
class ResultadoLiberacion:
    compromisos: tuple[Compromiso, ...]
    repetido: bool


@dataclass(frozen=True)
class ResultadoFinalizacion:
    emergencia_externa_id: str
    identificador_nacional: str
    proyecto_cerrado: bool
    organizaciones_finalizadas: int
    organizaciones_participantes: int
    repetido: bool


@contextmanager
def _transaccion_atomica() -> Iterator[None]:
    """Confirma o revierte la operación, incluso si la autenticación ya inició la sesión."""
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _nivel_gravedad(valor: NivelGravedad | str) -> NivelGravedad:
    if isinstance(valor, NivelGravedad):
        return valor
    gravedad_web = {
        "BAJA": NivelGravedad.baja,
        "MEDIA": NivelGravedad.media,
        "ALTA": NivelGravedad.alta,
        "CRITICA": NivelGravedad.critica,
    }
    if valor in gravedad_web:
        return gravedad_web[valor]
    try:
        return NivelGravedad(valor)
    except ValueError as error:
        raise ReglaDeNegocioIncumplida(
            "El nivel de gravedad no es válido.",
            detalle={"nivel_gravedad": valor},
        ) from error


def _tipo_asignacion(valor: TipoAsignacion | str) -> TipoAsignacion:
    if isinstance(valor, TipoAsignacion):
        asignacion = valor
    else:
        try:
            asignacion = TipoAsignacion(valor)
        except ValueError as error:
            raise ReglaDeNegocioIncumplida(
                "El tipo de asignación no es válido.",
                detalle={"tipo_asignacion": valor},
            ) from error

    if asignacion not in (TipoAsignacion.principal, TipoAsignacion.apoyo):
        raise ReglaDeNegocioIncumplida(
            "Solo se pueden comprometer asignaciones principales o de apoyo.",
            detalle={"tipo_asignacion": asignacion.value},
        )
    return asignacion


def _normalizar_aportes(
    aportes: list[AporteSolicitado],
) -> list[AporteSolicitado]:
    if not aportes:
        raise ReglaDeNegocioIncumplida("La adjudicación debe incluir al menos un aporte.")

    normalizados: list[AporteSolicitado] = []
    claves: set[tuple[str, str]] = set()
    for aporte in aportes:
        identificador = aporte.identificador_nacional.strip()
        codigo = aporte.codigo_recurso.strip()
        if not identificador or not codigo:
            raise ReglaDeNegocioIncumplida(
                "Cada aporte debe identificar la organización y el recurso."
            )
        if (
            isinstance(aporte.cantidad, bool)
            or not isinstance(aporte.cantidad, int)
            or aporte.cantidad <= 0
        ):
            raise ReglaDeNegocioIncumplida(
                "La cantidad comprometida debe ser un entero positivo.",
                detalle={
                    "identificador_nacional": identificador,
                    "codigo_recurso": codigo,
                },
            )
        clave = (identificador, codigo)
        if clave in claves:
            raise ReglaDeNegocioIncumplida(
                "La solicitud repite una organización y un recurso.",
                detalle={
                    "identificador_nacional": identificador,
                    "codigo_recurso": codigo,
                },
            )
        claves.add(clave)
        normalizados.append(
            AporteSolicitado(
                identificador_nacional=identificador,
                codigo_recurso=codigo,
                cantidad=aporte.cantidad,
                tipo_asignacion=_tipo_asignacion(aporte.tipo_asignacion),
            )
        )
    return normalizados


def _validar_repeticion(
    compromisos: list[Compromiso],
    aportes: list[AporteSolicitado],
    inventario_por_clave: dict[tuple[str, str], InventarioItem],
    nivel_gravedad: NivelGravedad,
) -> bool:
    if not compromisos:
        return False

    solicitados = {
        (aporte.identificador_nacional, aporte.codigo_recurso): aporte for aporte in aportes
    }
    existentes: dict[tuple[str, str], CompromisoItem] = {}
    for compromiso in compromisos:
        if compromiso.estado is not EstadoCompromiso.comprometido:
            raise ConflictoDeEstado(
                "La emergencia ya tiene compromisos que no están activos.",
                detalle={"emergencia_externa_id": compromiso.emergencia_externa_id},
            )
        if compromiso.nivel_gravedad is not nivel_gravedad:
            raise ConflictoDeEstado(
                "La emergencia ya tiene un compromiso registrado con otra gravedad.",
                detalle={"emergencia_externa_id": compromiso.emergencia_externa_id},
            )
        for item_comprometido in compromiso.items:
            inventario_item = item_comprometido.inventario_item
            clave = (
                inventario_item.inventario.organizacion.identificador_nacional,
                inventario_item.item.codigo_recurso,
            )
            existentes[clave] = item_comprometido

    if set(existentes) != set(solicitados):
        raise ConflictoDeEstado("La emergencia ya tiene un compromiso distinto para esos recursos.")

    for clave, aporte in solicitados.items():
        item_comprometido = existentes[clave]
        if (
            item_comprometido.cantidad_comprometida != aporte.cantidad
            or item_comprometido.tipo_asignacion is not aporte.tipo_asignacion
            or inventario_por_clave.get(clave) is not item_comprometido.inventario_item
        ):
            raise ConflictoDeEstado(
                "La emergencia ya tiene un compromiso distinto para esos recursos.",
                detalle={
                    "identificador_nacional": aporte.identificador_nacional,
                    "codigo_recurso": aporte.codigo_recurso,
                },
            )
    return True


def validar_restricciones(
    *,
    emergencia_externa_id: str,
    nivel_gravedad: NivelGravedad | str,
    aportes: list[AporteSolicitado],
) -> ResultadoValidacion:
    """Valida si los aportes son comprometibles sin modificar el inventario (dry-run).

    Solo verifica disponibilidad en ítems no consumibles. Los consumibles se aprueban
    directamente sin verificación de stock, ya que la API no gestiona inventario dinámico
    para ellos.
    """
    emergencia_id = emergencia_externa_id.strip()
    if not emergencia_id:
        raise ReglaDeNegocioIncumplida("La emergencia externa debe identificarse.")

    _nivel_gravedad(nivel_gravedad)  # Valida el formato sin necesitar el resultado
    solicitud = _normalizar_aportes(aportes)
    identificadores = sorted({aporte.identificador_nacional for aporte in solicitud})
    codigos = sorted({aporte.codigo_recurso for aporte in solicitud})

    organizaciones = db.session.scalars(
        select(Organizacion)
        .where(Organizacion.identificador_nacional.in_(identificadores))
        .order_by(Organizacion.id)
    ).all()
    organizaciones_por_id = {org.identificador_nacional: org for org in organizaciones}
    faltantes = set(identificadores) - set(organizaciones_por_id)
    if faltantes:
        raise RecursoNoEncontrado(
            "No se encontró una organización con el identificador nacional indicado.",
            detalle={"identificadores_nacionales": sorted(faltantes)},
        )

    items = db.session.scalars(select(Item).where(Item.codigo_recurso.in_(codigos))).all()
    items_por_codigo = {item.codigo_recurso: item for item in items}
    codigos_faltantes = set(codigos) - set(items_por_codigo)
    if codigos_faltantes:
        raise RecursoNoEncontrado(
            "No se encontró un recurso con el código indicado.",
            detalle={"codigos_recurso": sorted(codigos_faltantes)},
        )

    ids_organizaciones = [org.id for org in organizaciones]
    filas_inventario = db.session.execute(
        select(
            InventarioItem,
            Organizacion.identificador_nacional,
            Item.codigo_recurso,
        )
        .join(Inventario, Inventario.id == InventarioItem.inventario_id)
        .join(Organizacion, Organizacion.id == Inventario.organizacion_id)
        .join(Item, Item.id == InventarioItem.item_id)
        .where(
            Organizacion.id.in_(ids_organizaciones),
            Item.codigo_recurso.in_(codigos),
        )
        .order_by(InventarioItem.id)
    ).all()
    inventario_por_clave = {
        (identificador, codigo): inventario_item
        for inventario_item, identificador, codigo in filas_inventario
    }

    motivos: list[MotivoFallo] = []

    # Rechazar organizaciones que no estén habilitadas.
    no_habilitadas = [
        org.identificador_nacional
        for org in organizaciones
        if org.estado_habilitacion is not EstadoHabilitacion.habilitada
    ]
    for cuit in no_habilitadas:
        motivos.append(
            MotivoFallo(
                identificador_nacional=cuit,
                codigo_recurso="",
                cantidad_solicitada=0,
                cantidad_disponible=0,
                motivo="organizacion_no_habilitada",
            )
        )

    for aporte in solicitud:
        item = items_por_codigo[aporte.codigo_recurso]
        inventario_item = inventario_por_clave.get(
            (aporte.identificador_nacional, aporte.codigo_recurso)
        )
        # Rechazar si la ONG no declaró este recurso en su inventario.
        if inventario_item is None:
            motivos.append(
                MotivoFallo(
                    identificador_nacional=aporte.identificador_nacional,
                    codigo_recurso=aporte.codigo_recurso,
                    cantidad_solicitada=aporte.cantidad,
                    cantidad_disponible=0,
                    motivo="recurso_no_declarado",
                )
            )
            continue
        # Los consumibles no requieren verificación de stock.
        if item.consumible:
            continue
        disponible = inventario_item.cantidad_disponible
        if disponible < aporte.cantidad:
            motivos.append(
                MotivoFallo(
                    identificador_nacional=aporte.identificador_nacional,
                    codigo_recurso=aporte.codigo_recurso,
                    cantidad_solicitada=aporte.cantidad,
                    cantidad_disponible=disponible,
                    motivo="stock_insuficiente",
                )
            )

    return ResultadoValidacion(valido=not motivos, motivos=tuple(motivos))


def comprometer_recursos(
    *,
    emergencia_externa_id: str,
    nivel_gravedad: NivelGravedad | str,
    aportes: list[AporteSolicitado],
) -> ResultadoCompromiso:
    """Bloquea y compromete todos los aportes o ninguno.

    El inventario se descuenta dentro de la misma transacción en la que se crean los
    compromisos. Las filas de organizaciones e inventario se bloquean en orden estable para
    serializar reintentos y evitar carreras sobre el stock.
    """
    emergencia_id = emergencia_externa_id.strip()
    if not emergencia_id:
        raise ReglaDeNegocioIncumplida("La emergencia externa debe identificarse.")
    if len(emergencia_id) > 255:
        raise ReglaDeNegocioIncumplida("La referencia externa de emergencia es demasiado larga.")

    gravedad = _nivel_gravedad(nivel_gravedad)
    solicitud = _normalizar_aportes(aportes)
    identificadores = sorted({aporte.identificador_nacional for aporte in solicitud})
    codigos = sorted({aporte.codigo_recurso for aporte in solicitud})

    with _transaccion_atomica():
        organizaciones = db.session.scalars(
            select(Organizacion)
            .where(Organizacion.identificador_nacional.in_(identificadores))
            .order_by(Organizacion.id)
            .with_for_update()
        ).all()
        organizaciones_por_id = {org.identificador_nacional: org for org in organizaciones}
        faltantes = set(identificadores) - set(organizaciones_por_id)
        if faltantes:
            raise RecursoNoEncontrado(
                "No se encontró una organización con el identificador nacional indicado.",
                detalle={"identificadores_nacionales": sorted(faltantes)},
            )

        items = db.session.scalars(select(Item).where(Item.codigo_recurso.in_(codigos))).all()
        items_por_codigo = {item.codigo_recurso: item for item in items}
        codigos_faltantes = set(codigos) - set(items_por_codigo)
        if codigos_faltantes:
            raise RecursoNoEncontrado(
                "No se encontró un recurso con el código indicado.",
                detalle={"codigos_recurso": sorted(codigos_faltantes)},
            )

        ids_organizaciones = [org.id for org in organizaciones]
        filas_inventario = db.session.execute(
            select(
                InventarioItem,
                Organizacion.identificador_nacional,
                Item.codigo_recurso,
            )
            .join(Inventario, Inventario.id == InventarioItem.inventario_id)
            .join(Organizacion, Organizacion.id == Inventario.organizacion_id)
            .join(Item, Item.id == InventarioItem.item_id)
            .where(
                Organizacion.id.in_(ids_organizaciones),
                Item.codigo_recurso.in_(codigos),
            )
            .order_by(InventarioItem.id)
            .with_for_update(of=InventarioItem)
        ).all()
        inventario_por_clave = {
            (identificador, codigo): inventario_item
            for inventario_item, identificador, codigo in filas_inventario
        }

        compromisos_existentes = db.session.scalars(
            select(Compromiso)
            .where(Compromiso.emergencia_externa_id == emergencia_id)
            .order_by(Compromiso.organizacion_id)
            .with_for_update()
        ).all()
        if _validar_repeticion(
            compromisos_existentes,
            solicitud,
            inventario_por_clave,
            gravedad,
        ):
            return ResultadoCompromiso(tuple(compromisos_existentes), repetido=True)

        # Rechazar organizaciones que no estén habilitadas.
        no_habilitadas = [
            org.identificador_nacional
            for org in organizaciones
            if org.estado_habilitacion is not EstadoHabilitacion.habilitada
        ]
        if no_habilitadas:
            raise ReglaDeNegocioIncumplida(
                "La organización no está habilitada para comprometer recursos.",
                detalle={"identificadores_nacionales": sorted(no_habilitadas)},
            )

        for aporte in solicitud:
            item = items_por_codigo[aporte.codigo_recurso]
            inventario_item = inventario_por_clave.get(
                (aporte.identificador_nacional, aporte.codigo_recurso)
            )
            # Rechazar si la ONG no declaró este recurso en su inventario.
            if inventario_item is None:
                raise ReglaDeNegocioIncumplida(
                    "La organización no declaró este recurso en su inventario.",
                    detalle={
                        "identificador_nacional": aporte.identificador_nacional,
                        "codigo_recurso": aporte.codigo_recurso,
                    },
                )
            # Los consumibles no requieren verificación de stock.
            if item.consumible:
                continue
            disponible = inventario_item.cantidad_disponible
            if disponible < aporte.cantidad:
                raise DisponibilidadInsuficiente(
                    "La cantidad solicitada supera la disponibilidad.",
                    detalle={
                        "identificador_nacional": aporte.identificador_nacional,
                        "codigo_recurso": aporte.codigo_recurso,
                        "cantidad_solicitada": aporte.cantidad,
                        "cantidad_disponible": disponible,
                    },
                )

        compromisos_nuevos_por_identificador: dict[str, Compromiso] = {}
        for identificador in identificadores:
            compromiso = Compromiso(
                organizacion=organizaciones_por_id[identificador],
                emergencia_externa_id=emergencia_id,
                nivel_gravedad=gravedad,
            )
            db.session.add(compromiso)
            compromisos_nuevos_por_identificador[identificador] = compromiso

        for aporte in solicitud:
            item = items_por_codigo[aporte.codigo_recurso]
            inventario_item = inventario_por_clave[
                (aporte.identificador_nacional, aporte.codigo_recurso)
            ]
            # Solo los no consumibles tienen stock declarado; se descuenta su disponibilidad.
            if not item.consumible:
                inventario_item.cantidad_disponible -= aporte.cantidad
            compromiso = compromisos_nuevos_por_identificador[aporte.identificador_nacional]
            compromiso.items.append(
                CompromisoItem(
                    inventario_item=inventario_item,
                    cantidad_comprometida=aporte.cantidad,
                    tipo_asignacion=aporte.tipo_asignacion,
                )
            )

        db.session.flush()
        return ResultadoCompromiso(
            tuple(compromisos_nuevos_por_identificador.values()),
            repetido=False,
        )


def liberar_recursos(*, emergencia_externa_id: str) -> ResultadoLiberacion:
    """Libera los compromisos de una emergencia y devuelve solo recursos no consumibles."""
    emergencia_id = emergencia_externa_id.strip()
    if not emergencia_id:
        raise ReglaDeNegocioIncumplida("La emergencia externa debe identificarse.")
    if len(emergencia_id) > 255:
        raise ReglaDeNegocioIncumplida("La referencia externa de emergencia es demasiado larga.")

    with _transaccion_atomica():
        compromisos = db.session.scalars(
            select(Compromiso)
            .where(Compromiso.emergencia_externa_id == emergencia_id)
            .order_by(Compromiso.id)
            .with_for_update()
        ).all()
        if not compromisos:
            raise RecursoNoEncontrado(
                "No se encontraron compromisos para la emergencia indicada.",
                detalle={"emergencia_externa_id": emergencia_id},
            )

        if all(compromiso.estado is EstadoCompromiso.liberado for compromiso in compromisos):
            return ResultadoLiberacion(tuple(compromisos), repetido=True)
        if any(
            compromiso.estado is not EstadoCompromiso.comprometido for compromiso in compromisos
        ):
            raise ConflictoDeEstado(
                "La emergencia tiene compromisos que no se pueden liberar.",
                detalle={"emergencia_externa_id": emergencia_id},
            )

        ids_compromisos = [compromiso.id for compromiso in compromisos]
        items_comprometidos = db.session.scalars(
            select(CompromisoItem)
            .where(CompromisoItem.compromiso_id.in_(ids_compromisos))
            .order_by(CompromisoItem.id)
            .with_for_update()
        ).all()
        ids_inventario = sorted(
            {item_comprometido.inventario_item_id for item_comprometido in items_comprometidos}
        )
        inventario_items = db.session.scalars(
            select(InventarioItem)
            .where(InventarioItem.id.in_(ids_inventario))
            .order_by(InventarioItem.id)
            .with_for_update()
        ).all()
        inventario_por_id = {item.id: item for item in inventario_items}

        for item_comprometido in items_comprometidos:
            inventario_item = inventario_por_id.get(item_comprometido.inventario_item_id)
            if inventario_item is None:
                raise RecursoNoEncontrado(
                    "No se encontró una fila de inventario asociada al compromiso.",
                    detalle={"inventario_item_id": item_comprometido.inventario_item_id},
                )
            if not inventario_item.item.consumible:
                inventario_item.cantidad_disponible += item_comprometido.cantidad_comprometida

        fecha_liberacion = datetime.now(UTC)
        for compromiso in compromisos:
            compromiso.estado = EstadoCompromiso.liberado
            compromiso.fecha_liberacion = fecha_liberacion

        db.session.flush()
        return ResultadoLiberacion(tuple(compromisos), repetido=False)


def informar_finalizacion_ong(
    *,
    emergencia_externa_id: str,
    identificador_nacional: str,
) -> ResultadoFinalizacion:
    """Registra el cierre de una ONG y cierra/libera el proyecto al finalizar todas."""
    emergencia_id = emergencia_externa_id.strip()
    identificador = identificador_nacional.strip()
    if not emergencia_id:
        raise ReglaDeNegocioIncumplida("La emergencia externa debe identificarse.")
    if len(emergencia_id) > 255:
        raise ReglaDeNegocioIncumplida("La referencia externa de emergencia es demasiado larga.")
    if not identificador:
        raise ReglaDeNegocioIncumplida("La organización debe identificarse.")
    if len(identificador) > 255:
        raise ReglaDeNegocioIncumplida("El identificador nacional es demasiado largo.")

    with _transaccion_atomica():
        compromisos = db.session.scalars(
            select(Compromiso)
            .where(Compromiso.emergencia_externa_id == emergencia_id)
            .order_by(Compromiso.id)
            .with_for_update()
        ).all()
        if not compromisos:
            raise RecursoNoEncontrado(
                "No se encontraron compromisos para la emergencia indicada.",
                detalle={"emergencia_externa_id": emergencia_id},
            )

        compromiso_por_organizacion = {
            compromiso.organizacion.identificador_nacional: compromiso for compromiso in compromisos
        }
        compromiso_ong = compromiso_por_organizacion.get(identificador)
        if compromiso_ong is None:
            raise RecursoNoEncontrado(
                "La organización no participa en el proyecto indicado.",
                detalle={
                    "emergencia_externa_id": emergencia_id,
                    "identificador_nacional": identificador,
                },
            )

        if all(compromiso.estado is EstadoCompromiso.liberado for compromiso in compromisos):
            return ResultadoFinalizacion(
                emergencia_externa_id=emergencia_id,
                identificador_nacional=identificador,
                proyecto_cerrado=True,
                organizaciones_finalizadas=len(compromisos),
                organizaciones_participantes=len(compromisos),
                repetido=True,
            )
        if any(
            compromiso.estado is not EstadoCompromiso.comprometido for compromiso in compromisos
        ):
            raise ConflictoDeEstado(
                "El proyecto tiene compromisos que no se pueden finalizar.",
                detalle={"emergencia_externa_id": emergencia_id},
            )

        repetido = compromiso_ong.fecha_finalizacion_ong is not None
        if not repetido:
            compromiso_ong.fecha_finalizacion_ong = datetime.now(UTC)

        organizaciones_finalizadas = sum(
            compromiso.fecha_finalizacion_ong is not None for compromiso in compromisos
        )
        organizaciones_participantes = len(compromisos)
        proyecto_cerrado = organizaciones_finalizadas == organizaciones_participantes

        if proyecto_cerrado:
            ids_compromisos = [compromiso.id for compromiso in compromisos]
            items_comprometidos = db.session.scalars(
                select(CompromisoItem)
                .where(CompromisoItem.compromiso_id.in_(ids_compromisos))
                .order_by(CompromisoItem.id)
                .with_for_update()
            ).all()
            ids_inventario = sorted(
                {item_comprometido.inventario_item_id for item_comprometido in items_comprometidos}
            )
            inventario_items = db.session.scalars(
                select(InventarioItem)
                .where(InventarioItem.id.in_(ids_inventario))
                .order_by(InventarioItem.id)
                .with_for_update()
            ).all()
            inventario_por_id = {item.id: item for item in inventario_items}

            for item_comprometido in items_comprometidos:
                inventario_item = inventario_por_id.get(item_comprometido.inventario_item_id)
                if inventario_item is None:
                    raise RecursoNoEncontrado(
                        "No se encontró una fila de inventario asociada al compromiso.",
                        detalle={"inventario_item_id": item_comprometido.inventario_item_id},
                    )
                if not inventario_item.item.consumible:
                    inventario_item.cantidad_disponible += item_comprometido.cantidad_comprometida

            fecha_cierre = datetime.now(UTC)
            for compromiso in compromisos:
                compromiso.estado = EstadoCompromiso.liberado
                compromiso.fecha_liberacion = fecha_cierre
                compromiso.fecha_cierre_proyecto = fecha_cierre

        db.session.flush()
        return ResultadoFinalizacion(
            emergencia_externa_id=emergencia_id,
            identificador_nacional=identificador,
            proyecto_cerrado=proyecto_cerrado,
            organizaciones_finalizadas=organizaciones_finalizadas,
            organizaciones_participantes=organizaciones_participantes,
            repetido=repetido,
        )
