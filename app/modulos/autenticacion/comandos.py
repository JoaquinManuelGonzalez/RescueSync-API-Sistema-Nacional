"""Comandos `flask cuentas`: alta, baja y listado de las cuentas que pueden pedir tokens.

No hay endpoint para crear cuentas: se crean desde la terminal, contra la base local o contra la
de Supabase (runbook "Crear cuentas en Supabase" del README).

    flask cuentas crear admin-sn --rol administrador          pide la contrasena (oculta)
    flask cuentas crear bonita-rescuesync --rol sistema --generar
    flask cuentas desactivar admin-sn
    flask cuentas listar
"""

from __future__ import annotations

import secrets

import click
from flask.cli import AppGroup

from app.core.acceso import Rol
from app.extensiones import db
from app.modulos.autenticacion.servicios import desactivar_cuenta, guardar_cuenta, listar_cuentas

LARGO_MINIMO_CONTRASENA = 12

grupo_cuentas = AppGroup("cuentas", help="Administra las cuentas que pueden pedir tokens.")


@grupo_cuentas.command("crear")
@click.argument("usuario")
@click.option(
    "--rol",
    type=click.Choice([rol.value for rol in Rol]),
    required=True,
    help="sistema (Bonita) o administrador (operador del Sistema Nacional).",
)
@click.option("--descripcion", default=None, help="Para qué se usa la cuenta.")
@click.option(
    "--generar",
    is_flag=True,
    help="Genera un secreto aleatorio y lo muestra una sola vez (pensado para Bonita).",
)
def crear(usuario: str, rol: str, descripcion: str | None, generar: bool) -> None:
    """Crea la cuenta USUARIO, o le cambia la contraseña y el rol si ya existe."""
    if generar:
        contrasena = secrets.token_urlsafe(32)
    else:
        contrasena = click.prompt("Contraseña", hide_input=True, confirmation_prompt=True)
        if len(contrasena) < LARGO_MINIMO_CONTRASENA:
            raise click.BadParameter(
                f"La contraseña tiene que tener al menos {LARGO_MINIMO_CONTRASENA} caracteres."
            )

    _, creada = guardar_cuenta(usuario, contrasena, Rol(rol), descripcion)
    db.session.commit()

    click.echo(f"Cuenta {usuario} ({rol}) {'creada' if creada else 'actualizada'}.")
    if generar:
        click.echo("Secreto generado (no se vuelve a mostrar; guardalo ahora):")
        click.echo(contrasena)


@grupo_cuentas.command("desactivar")
@click.argument("usuario")
def desactivar(usuario: str) -> None:
    """Desactiva la cuenta USUARIO. Sus tokens vigentes dejan de servir de inmediato."""
    if desactivar_cuenta(usuario) is None:
        raise click.ClickException(f"No existe la cuenta {usuario}.")
    db.session.commit()
    click.echo(f"Cuenta {usuario} desactivada.")


@grupo_cuentas.command("listar")
def listar() -> None:
    """Lista las cuentas con su rol, estado y último ingreso."""
    cuentas = listar_cuentas()
    if not cuentas:
        click.echo("No hay cuentas.")
        return
    for cuenta in cuentas:
        estado = "activa" if cuenta.activa else "desactivada"
        ultimo = cuenta.ultimo_ingreso.isoformat() if cuenta.ultimo_ingreso else "nunca"
        click.echo(f"{cuenta.usuario}\t{cuenta.rol.value}\t{estado}\túltimo ingreso: {ultimo}")
