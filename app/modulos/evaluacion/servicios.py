"""Reglas de competencia para ofertas consolidadas."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from sqlalchemy import select

from app.core.errores import RecursoNoEncontrado, SolicitudInvalida
from app.extensiones import db
from app.modulos.compromisos.modelos import NivelGravedad, TipoAsignacion
from app.modulos.compromisos.servicios import AporteSolicitado, comprometer_recursos
from app.modulos.organizaciones.modelos import (
    EstadoHabilitacion,
    Item,
    NivelCertificacion,
    Organizacion,
    TipoOrganizacion,
)
from app.modulos.organizaciones.servicios import normalizar_identificador

CLASIFICACION_PRINCIPAL = "principal"
CLASIFICACION_APOYO = "apoyo"
CLASIFICACION_RECHAZADA = "rechazada"

MOTIVO_SIN_IDENTIFICADOR = "La organización no informó su identificador nacional (CUIT)."
MOTIVO_NO_REGISTRADA = "La organización no está registrada en el padrón nacional."

_ORDEN_NIVELES = {
    NivelCertificacion.baja: 1,
    NivelCertificacion.media: 2,
    NivelCertificacion.alta: 3,
    NivelCertificacion.critica: 4,
}
_GRAVEDAD_A_NIVEL = {
    "BAJA": NivelCertificacion.baja,
    "BAJO": NivelCertificacion.baja,
    "MEDIA": NivelCertificacion.media,
    "MEDIO": NivelCertificacion.media,
    "ALTA": NivelCertificacion.alta,
    "ALTO": NivelCertificacion.alta,
    "CRITICA": NivelCertificacion.critica,
    "CRITICO": NivelCertificacion.critica,
}
_GRAVEDAD_A_COMPROMISO = {
    "BAJA": NivelGravedad.baja,
    "BAJO": NivelGravedad.baja,
    "MEDIA": NivelGravedad.media,
    "MEDIO": NivelGravedad.media,
    "ALTA": NivelGravedad.alta,
    "ALTO": NivelGravedad.alta,
    "CRITICA": NivelGravedad.critica,
    "CRITICO": NivelGravedad.critica,
}


def _nivel_requerido(valor: str) -> NivelCertificacion:
    try:
        return _GRAVEDAD_A_NIVEL[valor.strip().upper()]
    except (AttributeError, KeyError) as error:
        raise SolicitudInvalida(
            "El nivel de gravedad no es válido.",
            detalle={"nivel_gravedad": valor},
        ) from error


def _clasificar(nivel: NivelCertificacion | None, requerido: NivelCertificacion) -> str:
    if nivel is None:
        return CLASIFICACION_RECHAZADA
    if _ORDEN_NIVELES[nivel] < _ORDEN_NIVELES[requerido]:
        return CLASIFICACION_APOYO
    return CLASIFICACION_PRINCIPAL


def _nivel_por_tipo(organizacion: Organizacion, tipo) -> NivelCertificacion | None:
    niveles = [
        asignacion.nivel_riesgo_permitido
        for asignacion in organizacion.certificaciones
        if asignacion.certificacion.tipo is tipo
    ]
    return max(niveles, key=_ORDEN_NIVELES.get) if niveles else None


def _aporte_rechazado(aporte: dict, identificador: str | None, motivo: str) -> dict:
    return {
        **aporte,
        "identificador_nacional": identificador,
        "certificacion_encontrada": False,
        "nivel_riesgo_permitido": None,
        "clasificacion": CLASIFICACION_RECHAZADA,
        "motivo": motivo,
        "compromiso_registrado": False,
    }


def _evaluar_aporte(
    aporte: dict,
    recurso: Item,
    requerido: NivelCertificacion,
    reservado: defaultdict[int, int],
) -> tuple[dict, AporteSolicitado | None]:
    """Clasifica un aporte. `reservado` acumula, por fila de inventario, lo ya aceptado en esta
    evaluación: la misma ONG puede ofrecer el mismo recurso en varias líneas (un ítem pedido en
    dos lotes) y entre todas no pueden superar su stock."""
    # La respuesta repite el identificador tal como llegó (recortado), porque la web cruza el
    # resultado por ese dato; para buscar en el padrón se usa la forma normalizada.
    recibido = aporte["identificador_nacional"]
    identificador = recibido.strip() if recibido is not None else None
    if not identificador:
        return _aporte_rechazado(aporte, identificador, MOTIVO_SIN_IDENTIFICADOR), None

    organizacion = db.session.scalar(
        select(Organizacion).where(
            Organizacion.identificador_nacional == normalizar_identificador(identificador)
        )
    )
    if organizacion is None:
        return _aporte_rechazado(aporte, identificador, MOTIVO_NO_REGISTRADA), None

    habilitada = (
        organizacion.estado_habilitacion is EstadoHabilitacion.habilitada
        and organizacion.tipo is TipoOrganizacion.ong
    )
    nivel = _nivel_por_tipo(organizacion, recurso.tipo) if habilitada else None
    clasificacion = _clasificar(nivel, requerido) if habilitada else CLASIFICACION_RECHAZADA
    motivo = (
        "La organización está registrada pero no está habilitada para ofertar."
        if not habilitada
        else (
            "No existe certificación para la capacidad del ítem."
            if nivel is None
            else (
                "La certificación tiene un nivel menor al requerido; se asigna como apoyo."
                if clasificacion == CLASIFICACION_APOYO
                else "La certificación alcanza el nivel de gravedad requerido."
            )
        )
    )

    if clasificacion != CLASIFICACION_RECHAZADA and not recurso.consumible:
        inventario_item = next(
            (
                fila
                for fila in (organizacion.inventario.items if organizacion.inventario else [])
                if fila.item_id == recurso.id
            ),
            None,
        )
        disponible = (
            inventario_item.cantidad_disponible - reservado[inventario_item.id]
            if inventario_item
            else 0
        )
        if disponible < aporte["cantidad"]:
            clasificacion = CLASIFICACION_RECHAZADA
            motivo = (
                "La disponibilidad del ítem no alcanza la cantidad ofertada "
                f"({disponible} disponible)."
            )
        else:
            reservado[inventario_item.id] += aporte["cantidad"]

    compromiso = clasificacion != CLASIFICACION_RECHAZADA and not recurso.consumible
    aporte_evaluado = {
        **aporte,
        "identificador_nacional": identificador,
        "certificacion_encontrada": nivel is not None,
        "nivel_riesgo_permitido": nivel,
        "clasificacion": clasificacion,
        "motivo": motivo,
        "compromiso_registrado": compromiso,
    }
    aporte_comprometido = (
        AporteSolicitado(
            identificador_nacional=organizacion.identificador_nacional,
            codigo_recurso=recurso.codigo_recurso,
            cantidad=aporte["cantidad"],
            tipo_asignacion=TipoAsignacion(clasificacion),
        )
        if compromiso
        else None
    )
    return aporte_evaluado, aporte_comprometido


def _evaluar_item(
    item_oferta: dict,
    requerido: NivelCertificacion,
    reservado: defaultdict[int, int],
) -> tuple[dict, list[AporteSolicitado]]:
    codigo = item_oferta["codigo_recurso"].strip()
    recurso = db.session.scalar(select(Item).where(Item.codigo_recurso == codigo))
    if recurso is None:
        raise RecursoNoEncontrado(
            "No se encontró un recurso con el código indicado.",
            detalle={"codigo_recurso": codigo},
        )

    aportes_evaluados = []
    aportes_comprometidos = []
    for aporte in item_oferta["aportes"]:
        evaluado, comprometido = _evaluar_aporte(aporte, recurso, requerido, reservado)
        aportes_evaluados.append(evaluado)
        if comprometido is not None:
            aportes_comprometidos.append(comprometido)

    return (
        {
            **item_oferta,
            "codigo_recurso": codigo,
            "consumible": recurso.consumible,
            "aportes": aportes_evaluados,
        },
        aportes_comprometidos,
    )


def _sumar_por_organizacion_y_recurso(
    aportes: list[AporteSolicitado],
) -> list[AporteSolicitado]:
    """Une en un solo aporte lo aceptado de una misma ONG y recurso en líneas distintas.

    En el Sistema Nacional hay un ítem de compromiso por ONG y recurso, y
    `comprometer_recursos` rechaza la repetición. La clasificación de esas líneas coincide
    siempre (misma ONG, mismo tipo de recurso, misma gravedad), así que se conserva la primera.
    """
    sumados: dict[tuple[str, str], AporteSolicitado] = {}
    for aporte in aportes:
        clave = (aporte.identificador_nacional, aporte.codigo_recurso)
        previo = sumados.get(clave)
        sumados[clave] = (
            aporte
            if previo is None
            else replace(previo, cantidad=previo.cantidad + aporte.cantidad)
        )
    return list(sumados.values())


def evaluar_ofertas(
    *,
    emergencia_id: int,
    nivel_gravedad: str,
    ofertas: list[dict],
) -> dict:
    """Evalúa aportes por ítem y compromete los recursos no consumibles aceptados."""
    gravedad = nivel_gravedad.strip().upper()
    requerido = _nivel_requerido(gravedad)
    try:
        nivel_compromiso = _GRAVEDAD_A_COMPROMISO[gravedad]
    except KeyError as error:
        raise SolicitudInvalida(
            "El nivel de gravedad no es válido.",
            detalle={"nivel_gravedad": nivel_gravedad},
        ) from error

    evaluadas = []
    aportes_comprometidos = []
    reservado: defaultdict[int, int] = defaultdict(int)
    for oferta in ofertas:
        items_evaluados = []
        for item in oferta["items"]:
            evaluado, comprometidos = _evaluar_item(item, requerido, reservado)
            items_evaluados.append(evaluado)
            aportes_comprometidos.extend(comprometidos)

        evaluadas.append(
            {
                "fecha_creacion": oferta["fecha_creacion"],
                "oferta_id": oferta["oferta_id"],
                "organizaciones": oferta["organizaciones"],
                "items": items_evaluados,
            }
        )

    if aportes_comprometidos:
        comprometer_recursos(
            emergencia_externa_id=str(emergencia_id),
            nivel_gravedad=nivel_compromiso,
            aportes=_sumar_por_organizacion_y_recurso(aportes_comprometidos),
        )
    return {
        "emergencia_id": emergencia_id,
        "nivel_gravedad": gravedad,
        "ofertas": evaluadas,
    }
