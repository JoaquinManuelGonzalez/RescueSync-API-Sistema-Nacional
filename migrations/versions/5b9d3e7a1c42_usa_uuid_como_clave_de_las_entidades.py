"""usa UUID como clave primaria de todas las entidades

Revision ID: 5b9d3e7a1c42
Revises: f1a2b3c4d5e6
Create Date: 2026-11-16 18:00:00.000000

Los ids enteros de cada base chocaban entre entornos: cada aplicación web local numera sus
emergencias desde 1 y todas usan la misma API (ver app/core/identificadores.py). Esta migración
pasa a UUID la clave primaria de cada tabla y todas las claves foráneas que la apuntan, sin
perder datos:

1. Suelta las claves foráneas que apuntan a las tablas convertidas.
2. Agrega a cada tabla una columna UUID y la llena: UUIDv7 en el orden de los ids viejos (así
   ordenar por id sigue dando el orden de alta), o el UUIDv5 fijo de los ítems y certificaciones
   del catálogo, el mismo que les da `flask seed`.
3. Agrega una columna UUID por cada clave foránea y la llena cruzando con el id viejo del padre.
4. Borra las columnas enteras (PostgreSQL arrastra la clave primaria, los únicos, los índices y
   las secuencias que dependen de ellas) y renombra las nuevas.
5. Vuelve a crear la clave primaria, los únicos, los índices y las foráneas con el mismo nombre,
   el mismo ON DELETE y la misma nulabilidad que tenían.

El downgrade hace el camino inverso: numera las filas desde 1 en el orden de su UUID y les vuelve
a poner una secuencia. Los ids enteros que salen no son los originales.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Callable

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5b9d3e7a1c42"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None

# Copia congelada de app/core/identificadores.py: una migración no importa código de la app,
# que puede cambiar después. Si cambiara allá, esta migración tiene que seguir igual.
ESPACIO_SISTEMA_NACIONAL = uuid.UUID("6f1c2a4e-8d3b-5a97-b0e4-3c2d1f9a8b70")

SUFIJO = "__nuevo"


def _id_de_item(fila, _orden: int) -> uuid.UUID:
    return uuid.uuid5(ESPACIO_SISTEMA_NACIONAL, f"item:{fila.codigo_recurso}")


def _id_de_certificacion(fila, _orden: int) -> uuid.UUID:
    return uuid.uuid5(ESPACIO_SISTEMA_NACIONAL, f"certificacion:{fila.tipo}:{fila.nombre}")


def _uuid7(_fila, _orden: int) -> uuid.UUID:
    return uuid.uuid7()


def _entero(_fila, orden: int) -> int:
    return orden


# Tabla -> cómo se calcula el UUID de cada fila.
GENERADORES_UUID: dict[str, Callable] = {
    "organizaciones": _uuid7,
    "cuentas": _uuid7,
    "historial_habilitaciones": _uuid7,
    "certificaciones": _id_de_certificacion,
    "items": _id_de_item,
    "inventarios": _uuid7,
    "inventario_items": _uuid7,
    "organizacion_certificaciones": _uuid7,
    "compromisos": _uuid7,
    "compromiso_items": _uuid7,
}

# Tipo entero que tenía cada clave antes de esta migración, para el downgrade. Las foráneas
# toman el tipo de la tabla a la que apuntan.
TIPOS_ENTEROS = {
    "organizaciones": sa.BigInteger(),
    "cuentas": sa.BigInteger(),
    "historial_habilitaciones": sa.BigInteger(),
}


def _tipo_entero(tabla: str) -> sa.types.TypeEngine:
    return TIPOS_ENTEROS.get(tabla, sa.Integer())


def _cambiar_claves(
    generadores: dict[str, Callable],
    tipo_de: Callable[[str], sa.types.TypeEngine],
) -> None:
    """Cambia el tipo de `id` de cada tabla de `generadores` y de las foráneas que lo apuntan."""
    conexion = op.get_bind()
    if conexion.dialect.name != "postgresql":
        raise RuntimeError("Esta migración solo corre sobre PostgreSQL.")
    inspector = sa.inspect(conexion)
    tablas = set(generadores)

    foraneas = []
    for tabla in inspector.get_table_names():
        for foranea in inspector.get_foreign_keys(tabla):
            if foranea["referred_table"] not in tablas:
                continue
            if foranea["referred_columns"] != ["id"] or len(foranea["constrained_columns"]) != 1:
                raise RuntimeError(f"Clave foránea no soportada en {tabla}: {foranea['name']}")
            foraneas.append((tabla, foranea))

    afectadas: dict[str, set[str]] = defaultdict(set)
    for tabla in tablas:
        afectadas[tabla].add("id")
    for tabla, foranea in foraneas:
        afectadas[tabla].add(foranea["constrained_columns"][0])

    columnas = {
        tabla: {columna["name"]: columna for columna in inspector.get_columns(tabla)}
        for tabla in afectadas
    }
    primarias, unicos, indices = {}, [], []
    for tabla, nombres in afectadas.items():
        primaria = inspector.get_pk_constraint(tabla)
        if set(primaria["constrained_columns"]) & nombres:
            primarias[tabla] = primaria
        for unico in inspector.get_unique_constraints(tabla):
            if set(unico["column_names"]) & nombres:
                unicos.append((tabla, unico))
        for indice in inspector.get_indexes(tabla):
            if not indice.get("duplicates_constraint") and set(indice["column_names"]) & nombres:
                indices.append((tabla, indice))

    # 1. Foráneas afuera, para poder cambiar las columnas de los dos lados.
    for tabla, foranea in foraneas:
        op.drop_constraint(foranea["name"], tabla, type_="foreignkey")

    # 2. Clave primaria nueva de cada tabla, en el orden de la clave vieja.
    for tabla, generar in generadores.items():
        op.add_column(tabla, sa.Column(f"id{SUFIJO}", tipo_de(tabla), nullable=True))
        filas = conexion.execute(sa.text(f'SELECT * FROM "{tabla}" ORDER BY id')).all()
        valores = [
            {"viejo": fila.id, "nuevo": generar(fila, orden)}
            for orden, fila in enumerate(filas, start=1)
        ]
        if valores:
            conexion.execute(
                sa.text(f'UPDATE "{tabla}" SET "id{SUFIJO}" = :nuevo WHERE id = :viejo'),
                valores,
            )

    # 3. Foránea nueva de cada hija, cruzando con la clave vieja del padre.
    for tabla, foranea in foraneas:
        columna = foranea["constrained_columns"][0]
        padre = foranea["referred_table"]
        op.add_column(tabla, sa.Column(f"{columna}{SUFIJO}", tipo_de(padre), nullable=True))
        conexion.execute(
            sa.text(
                f'UPDATE "{tabla}" AS hija SET "{columna}{SUFIJO}" = padre."id{SUFIJO}" '
                f'FROM "{padre}" AS padre WHERE padre.id = hija."{columna}"'
            )
        )

    # 4. Columnas viejas afuera (se llevan la clave primaria, los únicos, los índices y las
    # secuencias que dependen de ellas) y las nuevas toman su nombre.
    for tabla, nombres in afectadas.items():
        for nombre in sorted(nombres):
            op.drop_column(tabla, nombre)
        for nombre in sorted(nombres):
            original = columnas[tabla][nombre]
            op.alter_column(
                tabla,
                f"{nombre}{SUFIJO}",
                new_column_name=nombre,
                nullable=original["nullable"],
            )
            if original.get("comment"):
                op.alter_column(tabla, nombre, comment=original["comment"])

    # 5. Restricciones de vuelta, con el mismo nombre que tenían.
    for tabla, primaria in primarias.items():
        op.create_primary_key(primaria["name"], tabla, primaria["constrained_columns"])
    for tabla, unico in unicos:
        op.create_unique_constraint(unico["name"], tabla, unico["column_names"])
    for tabla, indice in indices:
        op.create_index(indice["name"], tabla, indice["column_names"], unique=indice["unique"])
    for tabla, foranea in foraneas:
        opciones = foranea.get("options") or {}
        op.create_foreign_key(
            foranea["name"],
            tabla,
            foranea["referred_table"],
            foranea["constrained_columns"],
            foranea["referred_columns"],
            ondelete=opciones.get("ondelete"),
            onupdate=opciones.get("onupdate"),
        )


def upgrade():
    _cambiar_claves(GENERADORES_UUID, lambda _tabla: sa.Uuid())


def downgrade():
    _cambiar_claves(dict.fromkeys(GENERADORES_UUID, _entero), _tipo_entero)
    conexion = op.get_bind()
    for tabla in GENERADORES_UUID:
        secuencia = f"{tabla}_id_seq"
        tipo = "bigint" if tabla in TIPOS_ENTEROS else "integer"
        conexion.execute(sa.text(f'CREATE SEQUENCE "{secuencia}" AS {tipo} OWNED BY "{tabla}".id'))
        conexion.execute(
            sa.text(f"ALTER TABLE \"{tabla}\" ALTER COLUMN id SET DEFAULT nextval('{secuencia}')")
        )
        conexion.execute(
            sa.text(
                f"SELECT setval('{secuencia}', COALESCE((SELECT max(id) FROM \"{tabla}\"), 0) + 1,"
                " false)"
            )
        )
