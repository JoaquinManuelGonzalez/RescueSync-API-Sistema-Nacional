from __future__ import annotations

import pytest
from sqlalchemy import select
from werkzeug.security import check_password_hash

from app.core.acceso import Rol
from app.extensiones import db
from app.modulos.autenticacion.modelos import Cuenta
from app.modulos.autenticacion.servicios import autenticar
from app.modulos.organizaciones import semillas
from app.modulos.organizaciones.modelos import (
    Certificacion,
    EstadoHabilitacion,
    HistorialHabilitacion,
    Inventario,
    InventarioItem,
    Item,
    Organizacion,
    OrganizacionCertificacion,
    TipoItem,
)

CONTRASENA_ADMIN = "contrasena-admin-de-prueba"
SECRETO_BONITA = "secreto-bonita-de-prueba-123"


@pytest.fixture
def base_de_datos(app):
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


def _sembrar() -> dict:
    """Corre todos los seeders, confirma y devuelve los resultados por entidad."""
    from app.core.semillas import SEEDERS, importar_seeders

    importar_seeders()
    resultados = {
        resultado.entidad: resultado for seeder in SEEDERS for resultado in seeder.funcion()
    }
    db.session.commit()
    return resultados


def _stock(organizacion: str, item: str) -> InventarioItem:
    return db.session.scalar(
        select(InventarioItem)
        .join(Inventario, Inventario.id == InventarioItem.inventario_id)
        .join(Organizacion, Organizacion.id == Inventario.organizacion_id)
        .join(Item, Item.id == InventarioItem.item_id)
        .where(Organizacion.nombre == organizacion, Item.nombre == item)
    )


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
    assert all(item.codigo_recurso for item in db.session.query(Item).all())
    assert db.session.query(Item.codigo_recurso).distinct().count() == len(semillas.ITEMS)
    assert (
        db.session.query(Item).filter_by(nombre="Enfermeros").one().codigo_recurso
        == "RSR-ENFERMEROS"
    )
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


def test_semillas_reponen_el_stock_sin_bajarlo(base_de_datos):
    _sembrar()
    agua = _stock("Cruz Solidaria", "Agua potable envasada")
    paramedicos = _stock("Cruz Solidaria", "Paramédicos")
    agua.cantidad_disponible = 0
    paramedicos.cantidad_disponible = 50
    db.session.commit()

    resultados = _sembrar()

    stock_semilla = semillas.INVENTARIOS["Cruz Solidaria"][2]
    assert agua.cantidad_disponible == stock_semilla["Agua potable envasada"]
    assert paramedicos.cantidad_disponible == 50
    assert resultados["inventario_items"].actualizados == 1
    assert resultados["inventario_items"].creados == 0


def test_comando_flask_seed_informa_el_stock_repuesto(app):
    with app.app_context():
        db.create_all()
        runner = app.test_cli_runner()
        assert runner.invoke(args=["seed"]).exit_code == 0
        _stock("Cruz Solidaria", "Agua potable envasada").cantidad_disponible = 0
        db.session.commit()

        resultado = runner.invoke(args=["seed"])

        assert resultado.exit_code == 0, resultado.output
        assert "inventarios/inventario_items: 0 creados" in resultado.output
        assert "1 repuestos" in resultado.output
        assert "organizaciones/organizaciones: 0 creados" in resultado.output

        db.session.remove()
        db.drop_all()


def test_semillas_crean_las_cuentas_desde_el_entorno(base_de_datos, monkeypatch):
    monkeypatch.setenv("SEMILLA_CONTRASENA_ADMIN", CONTRASENA_ADMIN)
    monkeypatch.setenv("SEMILLA_SECRETO_BONITA", SECRETO_BONITA)

    resultados = _sembrar()

    assert resultados["cuentas"].creados == 2
    admin = autenticar("admin-sn", CONTRASENA_ADMIN, modo="json")
    bonita = autenticar("bonita-rescuesync", SECRETO_BONITA, modo="client_credentials")
    assert admin is not None and admin.rol is Rol.administrador
    assert bonita is not None and bonita.rol is Rol.sistema
    assert _sembrar()["cuentas"].existentes == 2


@pytest.mark.parametrize("valor", ["", "   ", "muy-corta"])
def test_semillas_omiten_cuentas_sin_contrasena_valida(base_de_datos, monkeypatch, valor):
    monkeypatch.setenv("SEMILLA_CONTRASENA_ADMIN", valor)

    resultados = _sembrar()

    assert resultados["cuentas"].creados == 0
    assert db.session.query(Cuenta).count() == 0


def test_semillas_no_tocan_una_cuenta_existente(base_de_datos, monkeypatch, crear_cuenta):
    crear_cuenta("admin-sn", Rol.administrador, contrasena="rotada-a-mano-con-flask", activa=False)
    monkeypatch.setenv("SEMILLA_CONTRASENA_ADMIN", CONTRASENA_ADMIN)

    resultados = _sembrar()

    cuenta = db.session.scalar(select(Cuenta).where(Cuenta.usuario == "admin-sn"))
    assert resultados["cuentas"].existentes == 1
    assert cuenta.activa is False
    assert check_password_hash(cuenta.password_hash, "rotada-a-mano-con-flask")
