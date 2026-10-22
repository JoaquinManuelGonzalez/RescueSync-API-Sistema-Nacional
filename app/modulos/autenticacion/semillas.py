"""Datos semilla de las cuentas de la API.

Crean en cada deploy las dos cuentas de la entrega si todavia no existen, con la contrasena que
se carga en una variable de entorno (en Render, Service -> Environment). Sin la variable, la
cuenta se omite: en local y en los tests las cuentas se siguen creando con `flask cuentas`.

Una cuenta que ya existe no se toca: ni la contrasena ni el estado. Asi un deploy nunca deshace
una rotacion o una desactivacion hecha con `flask cuentas` (docs/contratos/autenticacion.md).
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import select

from app.core.acceso import Rol
from app.core.logging import registrar_evento
from app.core.semillas import ResultadoSemilla, registrar
from app.extensiones import db
from app.modulos.autenticacion.comandos import LARGO_MINIMO_CONTRASENA
from app.modulos.autenticacion.modelos import Cuenta
from app.modulos.autenticacion.servicios import guardar_cuenta

# (usuario, rol, variable con la contrasena, descripcion)
CUENTAS_DE_DEMOSTRACION: tuple[tuple[str, Rol, str, str], ...] = (
    ("admin-sn", Rol.administrador, "SEMILLA_CONTRASENA_ADMIN", "Operador del Sistema Nacional"),
    ("bonita-rescuesync", Rol.sistema, "SEMILLA_SECRETO_BONITA", "Motor Bonita de RescueSync"),
)


@registrar("cuentas")
def sembrar_cuentas() -> list[ResultadoSemilla]:
    resultado = ResultadoSemilla("cuentas")
    for usuario, rol, variable, descripcion in CUENTAS_DE_DEMOSTRACION:
        # Se lee del entorno y no de app.config, para que el secreto no quede en la configuracion.
        contrasena = (os.environ.get(variable) or "").strip()
        if not contrasena:
            continue
        if len(contrasena) < LARGO_MINIMO_CONTRASENA:
            # Nunca se loguea el valor: solo que variable no alcanza el largo minimo.
            registrar_evento(
                logging.WARNING,
                "semilla_omitida",
                f"{variable} tiene menos de {LARGO_MINIMO_CONTRASENA} caracteres.",
                cuenta=usuario,
            )
            continue

        existente = db.session.scalar(select(Cuenta).where(Cuenta.usuario == usuario))
        if existente is None:
            guardar_cuenta(usuario, contrasena, rol, descripcion)
        resultado.contar(existente is None)
    return [resultado]
