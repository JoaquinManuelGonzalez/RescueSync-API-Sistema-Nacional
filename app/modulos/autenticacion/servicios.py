"""Servicios de autenticacion: validar credenciales, emitir tokens y administrar cuentas."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from functools import cache

from flask import current_app
from flask_jwt_extended import create_access_token, get_current_user
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from app.core.acceso import Rol
from app.core.logging import registrar_evento
from app.extensiones import db, jwt
from app.modulos.autenticacion.modelos import Cuenta


@cache
def _hash_ficticio() -> str:
    """Hash contra el que se compara cuando el usuario no existe.

    Asi un usuario inexistente tarda lo mismo que una contrasena incorrecta, y el tiempo de
    respuesta no revela que cuentas existen.
    """
    return generate_password_hash("contrasena-ficticia-para-igualar-tiempos")


def autenticar(usuario: str, contrasena: str, *, modo: str) -> Cuenta | None:
    """Devuelve la cuenta si las credenciales son validas y esta activa; si no, None.

    El motivo del rechazo queda en el log y nunca en la respuesta, para no orientar a quien
    prueba credenciales. El usuario tampoco se loguea: puede ser lo que alguien tipeo mal.
    """
    cuenta = db.session.scalar(select(Cuenta).where(Cuenta.usuario == usuario))
    if cuenta is None:
        check_password_hash(_hash_ficticio(), contrasena)
        motivo = "credenciales_invalidas"
    elif not check_password_hash(cuenta.password_hash, contrasena):
        motivo = "credenciales_invalidas"
    elif not cuenta.activa:
        motivo = "cuenta_inactiva"
    else:
        cuenta.ultimo_ingreso = datetime.now(UTC)
        db.session.commit()
        registrar_evento(
            logging.INFO, "ingreso_exitoso", cuenta=cuenta.usuario, rol=cuenta.rol.value, modo=modo
        )
        return cuenta

    registrar_evento(logging.WARNING, "ingreso_fallido", motivo=motivo, modo=modo)
    return None


def emitir_token(cuenta: Cuenta) -> dict[str, object]:
    """Firma un access token para la cuenta. El cuerpo sirve para los dos modos de /login."""
    duracion: timedelta = current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    token = create_access_token(
        identity=cuenta.usuario,
        additional_claims={"rol": cuenta.rol.value},
    )
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": int(duracion.total_seconds()),
    }


@jwt.user_lookup_loader
def _cargar_cuenta(_cabecera: dict, datos: dict) -> Cuenta | None:
    """Corre en cada pedido protegido. Devuelve None (y la API responde 401) si la cuenta ya no
    existe, se desactivo o tiene otro rol que el del token: esos tokens dejan de servir al
    instante, sin esperar a que venzan."""
    try:
        rol = Rol(datos.get("rol"))
    except ValueError:
        return None
    return db.session.scalar(
        select(Cuenta).where(
            Cuenta.usuario == datos["sub"], Cuenta.activa.is_(True), Cuenta.rol == rol
        )
    )


def cuenta_actual() -> Cuenta:
    """Cuenta del token de la solicitud en curso (solo dentro de un endpoint protegido)."""
    return get_current_user()


def guardar_cuenta(
    usuario: str, contrasena: str, rol: Rol, descripcion: str | None = None
) -> tuple[Cuenta, bool]:
    """Crea la cuenta o, si ya existe, le cambia la contrasena y el rol y la reactiva.

    Devuelve la cuenta y si fue creada. No hace commit: lo hace quien llama.
    """
    cuenta = db.session.scalar(select(Cuenta).where(Cuenta.usuario == usuario))
    creada = cuenta is None
    if cuenta is None:
        cuenta = Cuenta(usuario=usuario)
        db.session.add(cuenta)
    cuenta.password_hash = generate_password_hash(contrasena)
    cuenta.rol = rol
    cuenta.activa = True
    if descripcion is not None:
        cuenta.descripcion = descripcion
    db.session.flush()
    return cuenta, creada


def desactivar_cuenta(usuario: str) -> Cuenta | None:
    """Desactiva la cuenta: sus tokens vigentes dejan de servir. No hace commit."""
    cuenta = db.session.scalar(select(Cuenta).where(Cuenta.usuario == usuario))
    if cuenta is not None:
        cuenta.activa = False
        db.session.flush()
    return cuenta


def listar_cuentas() -> list[Cuenta]:
    return list(db.session.scalars(select(Cuenta).order_by(Cuenta.usuario)))
