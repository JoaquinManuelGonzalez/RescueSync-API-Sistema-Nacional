from __future__ import annotations

import pytest

from app.extensiones import db
from app.modulos.organizaciones import semillas
from app.modulos.organizaciones.modelos import (
    Certificacion,
    EstadoHabilitacion,
    HistorialHabilitacion,
    InventarioItem,
    Item,
    Organizacion,
    OrganizacionCertificacion,
    TipoItem,
)


@pytest.fixture
def base_de_datos(app):
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def test_sembrar_carga_datos_y_es_idempotente(base_de_datos):
    from app.core.semillas import SEEDERS, importar_seeders

    importar_seeders()
    primera_carga = [resultado for seeder in SEEDERS for resultado in seeder.funcion()]
    db.session.commit()
    segunda_carga = [resultado for seeder in SEEDERS for resultado in seeder.funcion()]
    db.session.commit()

    assert primera_carga[0].creados == len(semillas.ORGANIZACIONES_DE_DEMOSTRACION)
    assert sum(resultado.creados for resultado in primera_carga) > 0
    assert sum(resultado.creados for resultado in segunda_carga) == 0
    assert db.session.query(Organizacion).count() == len(semillas.ORGANIZACIONES_DE_DEMOSTRACION)
    assert db.session.query(Item).count() == len(semillas.ITEMS)
    assert db.session.query(OrganizacionCertificacion).count() == sum(
        len(certificaciones) for certificaciones in semillas.CERTIFICACIONES.values()
    )
    assert db.session.query(Certificacion).count() == len(
        {
            (nombre, tipo)
            for certificaciones in semillas.CERTIFICACIONES.values()
            for nombre, tipo in certificaciones
        }
    )


def test_tipos_de_certificacion_son_categorias_de_items(base_de_datos):
    from app.core.semillas import SEEDERS, importar_seeders

    importar_seeders()
    for seeder in SEEDERS:
        seeder.funcion()
    db.session.commit()

    tipos_de_items = {item.tipo for item in db.session.query(Item).all()}
    tipos_de_certificaciones = {
        certificacion.tipo for certificacion in db.session.query(Certificacion).all()
    }

    assert tipos_de_certificaciones <= set(TipoItem)
    assert tipos_de_certificaciones <= tipos_de_items
    assert db.session.query(InventarioItem).count() > 0


def test_semillas_tienen_una_certificacion_por_tipo(base_de_datos):
    from app.core.semillas import SEEDERS, importar_seeders

    importar_seeders()
    for seeder in SEEDERS:
        seeder.funcion()
    db.session.commit()

    certificaciones = db.session.query(Certificacion).all()
    tipos = [certificacion.tipo for certificacion in certificaciones]

    assert len(tipos) == len(set(tipos))
    assert set(tipos) == set(TipoItem)


def test_semillas_clasifican_recursos_consumibles_y_reutilizables(base_de_datos):
    from app.core.semillas import SEEDERS, importar_seeders

    importar_seeders()
    for seeder in SEEDERS:
        seeder.funcion()
    db.session.commit()

    items = {item.nombre: item.consumible for item in db.session.query(Item).all()}

    assert items["Paramédicos"] is False
    assert items["Enfermeros"] is False
    assert items["Rescatistas"] is False
    assert items["Ambulancias"] is False
    assert items["Generadores eléctricos"] is False
    assert items["Frazadas"] is True
    assert items["Colchones"] is True
    assert items["Tanques de agua"] is True
    assert items["Agua potable envasada"] is True
    assert items["Antibióticos"] is True
    assert items["Raciones de alimento no perecedero"] is True


def test_semillas_corrigen_consumible_al_reejecutarse(base_de_datos):
    from app.core.semillas import SEEDERS, importar_seeders

    importar_seeders()
    for seeder in SEEDERS:
        seeder.funcion()
    db.session.query(Item).filter_by(nombre="Paramédicos").one().consumible = True
    db.session.commit()

    semillas.sembrar_items()
    db.session.commit()

    assert db.session.query(Item).filter_by(nombre="Paramédicos").one().consumible is False


def test_comando_flask_seed_carga_los_datos(app):
    with app.app_context():
        db.create_all()
        resultado = app.test_cli_runner().invoke(args=["seed"])

        assert resultado.exit_code == 0, resultado.output
        assert "organizaciones/organizaciones:" in resultado.output
        assert db.session.query(Organizacion).count() == len(
            semillas.ORGANIZACIONES_DE_DEMOSTRACION
        )

        db.session.remove()
        db.drop_all()


def test_semillas_dejan_estado_e_historial_de_habilitacion(base_de_datos):
    from app.core.semillas import SEEDERS, importar_seeders

    importar_seeders()
    for seeder in SEEDERS:
        seeder.funcion()
    db.session.commit()

    estados = {
        organizacion.nombre: organizacion.estado_habilitacion
        for organizacion in db.session.query(Organizacion).all()
    }
    suspendidas = {
        nombre for nombre, estado in estados.items() if estado is EstadoHabilitacion.suspendida
    }
    assert suspendidas == set(semillas.SUSPENDIDAS_DE_DEMOSTRACION)
    assert all(
        estado is EstadoHabilitacion.habilitada
        for nombre, estado in estados.items()
        if nombre not in suspendidas
    )
    assert db.session.query(HistorialHabilitacion).count() == len(estados)
