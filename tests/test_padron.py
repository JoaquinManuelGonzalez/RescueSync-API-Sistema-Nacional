"""Padrón nacional de ONGs: onboarding, consulta por CUIT y estado de habilitación."""

from __future__ import annotations

import pytest

from app.core.acceso import Rol
from app.extensiones import db
from app.modulos.organizaciones import servicios
from app.modulos.organizaciones.modelos import (
    EstadoHabilitacion,
    HistorialHabilitacion,
    Organizacion,
    TipoOrganizacion,
)

ALTA = {
    "cuit": "30-71555444-2",
    "nombre": "Red Solidaria Chascomús",
    "mail_contacto": "contacto@redsolidaria.example",
}


@pytest.fixture
def organizacion(base_de_datos):
    """ONG ya registrada en estado `habilitada`, como las que cargan las semillas."""
    registro = Organizacion(
        tipo=TipoOrganizacion.ong,
        nombre="Cruz Solidaria",
        mail_contacto="cruz@solidaria.example",
        identificador_nacional="30-65432198-7",
        estado_habilitacion=EstadoHabilitacion.habilitada,
        historial_habilitacion=[
            HistorialHabilitacion(estado_nuevo=EstadoHabilitacion.habilitada, motivo="Semilla.")
        ],
    )
    db.session.add(registro)
    db.session.commit()
    return registro


def _cambiar(cliente, cabeceras, cuit, estado, motivo=None):
    return cliente.patch(
        f"/ongs/{cuit}/habilitacion",
        json={"estado": estado, "motivo": motivo},
        headers=cabeceras(Rol.administrador),
    )


# --- Onboarding --------------------------------------------------------------------------


def test_alta_registra_la_ong_pendiente_y_su_historial(cliente, cabeceras):
    respuesta = cliente.post(
        "/ongs", json={**ALTA, "cuit": "30715554442"}, headers=cabeceras(Rol.administrador)
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.get_json()
    assert cuerpo["cuit"] == "30-71555444-2"
    assert cuerpo["tipo"] == "ong"
    assert cuerpo["estado_habilitacion"] == "pendiente"
    assert cuerpo["habilitada"] is False
    registros = db.session.query(HistorialHabilitacion).all()
    assert len(registros) == 1
    assert registros[0].estado_anterior is None
    assert registros[0].estado_nuevo is EstadoHabilitacion.pendiente
    assert registros[0].cuenta.usuario == "admin-sn"


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"cuit": "30-65432198-7"}, "cuit"),
        ({"cuit": "30654321987"}, "cuit"),
        ({"nombre": "CRUZ SOLIDARIA"}, "nombre"),
        ({"mail_contacto": "Cruz@Solidaria.example"}, "mail_contacto"),
    ],
)
def test_alta_duplicada_responde_409_con_el_campo(cliente, cabeceras, organizacion, cambios, campo):
    respuesta = cliente.post(
        "/ongs", json={**ALTA, **cambios}, headers=cabeceras(Rol.administrador)
    )

    assert respuesta.status_code == 409
    error = respuesta.get_json()["error"]
    assert error["codigo"] == "CONFLICTO_DE_ESTADO"
    assert error["detalle"]["campo"] == campo
    assert error["detalle"]["estado_habilitacion"] == "habilitada"


@pytest.mark.parametrize("cuit", ["30-1234-5", "abcdefghijk", "301234567890"])
def test_alta_con_cuit_mal_formado_responde_400(cliente, cabeceras, cuit):
    respuesta = cliente.post("/ongs", json={**ALTA, "cuit": cuit}, headers=cabeceras())

    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "SOLICITUD_INVALIDA"


def test_alta_sin_campos_obligatorios_responde_400_con_detalle(cliente, cabeceras):
    respuesta = cliente.post("/ongs", json={"cuit": "30-71555444-2"}, headers=cabeceras())

    assert respuesta.status_code == 400
    detalle = respuesta.get_json()["error"]["detalle"]["json"]
    assert set(detalle) == {"nombre", "mail_contacto"}


# --- Consulta ----------------------------------------------------------------------------


def test_consulta_por_cuit_con_o_sin_guiones(cliente, cabeceras, organizacion):
    for cuit in ("30-65432198-7", "30654321987"):
        respuesta = cliente.get(f"/ongs/{cuit}", headers=cabeceras(Rol.sistema))

        assert respuesta.status_code == 200
        assert respuesta.get_json()["nombre"] == "Cruz Solidaria"
        assert respuesta.get_json()["habilitada"] is True


def test_consulta_de_cuit_no_registrado_responde_404(cliente, cabeceras):
    respuesta = cliente.get("/ongs/30-11111111-1", headers=cabeceras(Rol.sistema))

    assert respuesta.status_code == 404
    assert respuesta.get_json()["error"]["codigo"] == "RECURSO_NO_ENCONTRADO"


def test_estado_de_informa_none_si_no_esta_en_el_padron(organizacion):
    assert servicios.estado_de("30-65432198-7") is EstadoHabilitacion.habilitada
    assert servicios.estado_de("30-11111111-1") is None


# --- Estado de habilitación ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("inicial", "pedido", "estado_http"),
    [
        (EstadoHabilitacion.pendiente, EstadoHabilitacion.habilitada, 200),
        (EstadoHabilitacion.pendiente, EstadoHabilitacion.suspendida, 200),
        (EstadoHabilitacion.habilitada, EstadoHabilitacion.suspendida, 200),
        (EstadoHabilitacion.suspendida, EstadoHabilitacion.habilitada, 200),
        (EstadoHabilitacion.habilitada, EstadoHabilitacion.habilitada, 409),
        (EstadoHabilitacion.suspendida, EstadoHabilitacion.suspendida, 409),
        (EstadoHabilitacion.habilitada, EstadoHabilitacion.pendiente, 409),
        (EstadoHabilitacion.suspendida, EstadoHabilitacion.pendiente, 409),
    ],
)
def test_transiciones_de_habilitacion(
    cliente, cabeceras, organizacion, inicial, pedido, estado_http
):
    organizacion.estado_habilitacion = inicial
    db.session.commit()

    respuesta = _cambiar(cliente, cabeceras, "30-65432198-7", pedido.value, "Motivo de prueba.")

    assert respuesta.status_code == estado_http
    if estado_http == 409:
        detalle = respuesta.get_json()["error"]["detalle"]
        assert detalle["estado_actual"] == inicial.value
        assert detalle["transiciones_permitidas"]
    else:
        assert respuesta.get_json()["estado_habilitacion"] == pedido.value


def test_suspender_exige_motivo(cliente, cabeceras, organizacion):
    respuesta = _cambiar(cliente, cabeceras, "30-65432198-7", "suspendida")

    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["detalle"]["json"] == {
        "motivo": ["Obligatorio al suspender una organización."]
    }


def test_suspension_queda_en_el_historial_y_en_la_ficha(cliente, cabeceras, organizacion):
    _cambiar(cliente, cabeceras, "30-65432198-7", "suspendida", "Certificación vencida.")
    _cambiar(cliente, cabeceras, "30-65432198-7", "habilitada", "Certificación renovada.")

    ficha = cliente.get("/ongs/30-65432198-7", headers=cabeceras()).get_json()
    historial = cliente.get(
        "/ongs/30-65432198-7/habilitacion/historial", headers=cabeceras(Rol.sistema)
    ).get_json()

    assert ficha["motivo_estado"] == "Certificación renovada."
    assert historial["estado_actual"] == "habilitada"
    assert [(r["estado_anterior"], r["estado_nuevo"]) for r in historial["registros"]] == [
        (None, "habilitada"),
        ("habilitada", "suspendida"),
        ("suspendida", "habilitada"),
    ]
    assert historial["registros"][1]["cuenta"] == "admin-sn"


def test_cambio_de_estado_de_cuit_no_registrado_responde_404(cliente, cabeceras):
    respuesta = _cambiar(cliente, cabeceras, "30-11111111-1", "habilitada")

    assert respuesta.status_code == 404


def test_bonita_no_puede_cambiar_el_estado(cliente, cabeceras, organizacion):
    respuesta = cliente.patch(
        "/ongs/30-65432198-7/habilitacion",
        json={"estado": "suspendida", "motivo": "x"},
        headers=cabeceras(Rol.sistema),
    )

    assert respuesta.status_code == 403
