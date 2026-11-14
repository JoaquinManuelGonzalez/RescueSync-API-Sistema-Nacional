"""Contrato del catálogo de recursos compartido con la aplicación web.

Bonita reenvía a `POST /ofertas/evaluacion` los `codigo_recurso` que arma la web, sin traducirlos.
Si la web tiene un ítem que la API no, la evaluación entera falla con 404; si el tipo o el
consumible difieren, la API exige otra certificación o compromete stock que la web no espera.

`CATALOGO_COMPARTIDO` es una copia literal de la misma constante en
`backend/tests/test_catalogo_compartido.py` del repo RescueSync-Web-App, que la compara con las
semillas de la web. Si cambia el catálogo, se actualizan las dos copias y las dos semillas.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.extensiones import db
from app.modulos.evaluacion.servicios import evaluar_ofertas
from app.modulos.organizaciones import semillas

# codigo_recurso -> (tipo, unidad de medida, consumible), en el orden de las semillas de la web.
CATALOGO_COMPARTIDO: dict[str, tuple[str, str, bool]] = {
    "RSR-PARAMEDICOS": ("personal_medico", "personas", False),
    "RSR-MEDICOS_DE_URGENCIA": ("personal_medico", "personas", False),
    "RSR-ENFERMEROS": ("personal_medico", "personas", False),
    "RSR-RESCATISTAS": ("rescate", "personas", False),
    "RSR-PERROS_DE_BUSQUEDA": ("rescate", "unidades", False),
    "RSR-BOMBEROS": ("rescate", "personas", False),
    "RSR-BRIGADISTAS": ("rescate", "personas", False),
    "RSR-RACIONES_DE_ALIMENTO_NO_PERECEDERO": ("alimentos", "raciones", True),
    "RSR-LATAS_DE_ARVEJAS": ("alimentos", "kg", True),
    "RSR-POLENTA": ("alimentos", "kg", True),
    "RSR-FIDEOS": ("alimentos", "kg", True),
    "RSR-ARROZ": ("alimentos", "kg", True),
    "RSR-ACEITE": ("alimentos", "raciones", True),
    "RSR-GALLETITAS_DE_AGUA": ("alimentos", "unidades", True),
    "RSR-GALLETITAS_DULCES": ("alimentos", "unidades", True),
    "RSR-HARINA_DE_TRIGO": ("alimentos", "kg", True),
    "RSR-AZUCAR": ("alimentos", "kg", True),
    "RSR-LENTEJAS": ("alimentos", "kg", True),
    "RSR-CAFE": ("alimentos", "kg", True),
    "RSR-YERBA": ("alimentos", "kg", True),
    "RSR-LECHE_EN_POLVO": ("alimentos", "kg", True),
    "RSR-AGUA_POTABLE_ENVASADA": ("agua", "litros", True),
    "RSR-TANQUES_DE_AGUA": ("agua", "unidades", True),
    "RSR-FRAZADAS": ("abrigo", "unidades", True),
    "RSR-COLCHONES": ("abrigo", "unidades", True),
    "RSR-CARPAS_FAMILIARES": ("abrigo", "unidades", True),
    "RSR-ROPA_DE_INVIERNO": ("abrigo", "unidades", True),
    "RSR-ROPA_DE_VERANO": ("abrigo", "unidades", True),
    "RSR-BOTIQUINES_DE_PRIMEROS_AUXILIOS": ("medicamentos", "unidades", True),
    "RSR-ANALGESICOS": ("medicamentos", "unidades", True),
    "RSR-PARACETAMOL": ("medicamentos", "unidades", True),
    "RSR-IBUPROFENO": ("medicamentos", "unidades", True),
    "RSR-ANTIBIOTICOS": ("medicamentos", "unidades", True),
    "RSR-PANALES_PARA_ADULTO": ("medicamentos", "unidades", True),
    "RSR-SUPLEMENTO_ALIMENTICIO": ("medicamentos", "unidades", True),
    "RSR-SUERO_FISIOLOGICO": ("medicamentos", "unidades", True),
    "RSR-RETROEXCAVADORAS": ("maquinaria", "unidades", False),
    "RSR-CAMIONES_DE_CARGA": ("maquinaria", "unidades", False),
    "RSR-GENERADORES_ELECTRICOS": ("maquinaria", "unidades", False),
    "RSR-AMBULANCIAS": ("maquinaria", "unidades", False),
    "RSR-VOLUNTARIOS_GENERALES": ("otro", "personas", False),
    "RSR-TOALLITAS_FEMENINAS": ("otro", "unidades", True),
    "RSR-JABON": ("otro", "unidades", True),
    "RSR-TOALLAS_JABONOSAS": ("otro", "unidades", True),
    "RSR-KIT_HIGIENE_BUCAL": ("otro", "unidades", True),
    "RSR-PANALES_PARA_BEBES": ("otro", "unidades", True),
}

CRUZ_SOLIDARIA = "30-65432198-7"
BOMBEROS_LA_PLATA = "30-99999999-5"


def _catalogo_de_las_semillas() -> dict[str, tuple[str, str, bool]]:
    return {
        semillas._codigo_recurso(nombre): (
            tipo.value,
            unidad,
            nombre not in semillas.ITEMS_NO_CONSUMIBLES,
        )
        for nombre, (tipo, unidad, _descripcion) in semillas.ITEMS.items()
    }


def test_catalogo_de_la_api_es_igual_al_de_la_web():
    catalogo = _catalogo_de_las_semillas()

    faltan = sorted(CATALOGO_COMPARTIDO.keys() - catalogo.keys())
    sobran = sorted(catalogo.keys() - CATALOGO_COMPARTIDO.keys())
    distintos = {
        codigo: {"api": catalogo[codigo], "web": esperado}
        for codigo, esperado in CATALOGO_COMPARTIDO.items()
        if codigo in catalogo and catalogo[codigo] != esperado
    }
    assert not (faltan or sobran or distintos), (
        "El catálogo de app/modulos/organizaciones/semillas.py no coincide con el de la web. "
        f"Faltan: {faltan}. Sobran: {sobran}. Distintos: {distintos}."
    )
    # Un nombre mal escrito en ITEMS_NO_CONSUMIBLES dejaría consumible al ítem sin avisar.
    assert semillas.ITEMS_NO_CONSUMIBLES <= semillas.ITEMS.keys()


@pytest.fixture
def base_sembrada(base_de_datos):
    from app.core.semillas import SEEDERS, importar_seeders

    importar_seeders()
    for seeder in SEEDERS:
        seeder.funcion()
    db.session.commit()


def _aporte(codigo: str, cuit: str, cantidad: int, lote_item_id: int) -> dict:
    tipo, unidad, _consumible = CATALOGO_COMPARTIDO[codigo]
    return {
        "aportes": [{"cantidad": cantidad, "identificador_nacional": cuit, "organizacion_id": 1}],
        "cantidad_total": cantidad,
        "codigo_recurso": codigo,
        "lote_item_id": lote_item_id,
        "tipo_recurso": tipo,
        "unidad": unidad,
    }


def test_evaluacion_resuelve_items_que_antes_solo_tenia_la_web(base_sembrada):
    # Paracetamol no existía en la API: la evaluación entera respondía 404.
    resultado = evaluar_ofertas(
        emergencia_id=1,
        nivel_gravedad="ALTA",
        ofertas=[
            {
                "fecha_creacion": datetime.now(UTC),
                "oferta_id": 1,
                "organizaciones": [],
                "version": 1,
                "items": [
                    _aporte("RSR-PARACETAMOL", CRUZ_SOLIDARIA, 100, 1),
                    _aporte("RSR-RESCATISTAS", BOMBEROS_LA_PLATA, 5, 2),
                ],
            }
        ],
    )

    paracetamol, rescatistas = (item["aportes"][0] for item in resultado["ofertas"][0]["items"])
    # Cruz Solidaria no tiene certificación de medicamentos: es una regla de negocio, no un 404.
    assert paracetamol["clasificacion"] == "rechazada"
    assert paracetamol["motivo"] == "No existe certificación para la capacidad del ítem."
    # Bomberos es una ONG, como en la web, y tiene certificación de rescate y stock.
    assert rescatistas["clasificacion"] == "principal"
    assert rescatistas["compromiso_registrado"] is True
