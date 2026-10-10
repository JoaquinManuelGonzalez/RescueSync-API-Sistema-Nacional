"""Infraestructura para cargar datos semilla mediante `flask seed`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.extensiones import db


@dataclass
class ResultadoSemilla:
    """Resumen de operaciones realizadas por un seeder."""

    entidad: str
    creados: int = 0
    existentes: int = 0

    def contar(self, fue_creado: bool) -> None:
        if fue_creado:
            self.creados += 1
        else:
            self.existentes += 1


@dataclass(frozen=True)
class Seeder:
    nombre: str
    funcion: Callable[[], list[ResultadoSemilla]]


SEEDERS: list[Seeder] = []


def registrar(nombre: str) -> Callable[..., Any]:
    """Registra una función para que sea ejecutada por `flask seed`."""

    def envoltorio(funcion: Callable[[], list[ResultadoSemilla]]):
        SEEDERS.append(Seeder(nombre=nombre, funcion=funcion))
        return funcion

    return envoltorio


def obtener_o_crear(
    modelo: type,
    *,
    claves: dict[str, Any],
    valores: dict[str, Any] | None = None,
) -> tuple[Any, bool]:
    """Obtiene una fila por su clave natural o la crea sin hacer commit."""
    instancia = db.session.execute(select(modelo).filter_by(**claves)).scalar_one_or_none()
    if instancia is not None:
        return instancia, False

    instancia = modelo(**claves, **(valores or {}))
    db.session.add(instancia)
    db.session.flush()
    return instancia, True


def importar_seeders() -> None:
    """Importa los módulos que aportan datos semilla, en orden de dependencia."""
    from app.modulos.organizaciones import semillas as _organizaciones  # noqa: F401
