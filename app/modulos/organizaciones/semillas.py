"""Datos semilla de organizaciones, certificaciones e inventarios."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.semillas import ResultadoSemilla, obtener_o_crear, registrar
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
    TipoOrganizacion,
)

ORGANIZACIONES_DE_DEMOSTRACION: tuple[tuple[str, TipoOrganizacion, str], ...] = (
    ("Municipio de Chascomús", TipoOrganizacion.organismo_rescate, "30-71234567-9"),
    ("Municipalidad de Bahía Blanca", TipoOrganizacion.organismo_rescate, "30-99999999-1"),
    ("Municipalidad de La Plata", TipoOrganizacion.organismo_rescate, "30-99999999-2"),
    ("Municipalidad de Pergamino", TipoOrganizacion.organismo_rescate, "30-99999999-3"),
    (
        "Centro Coordinador Regional Buenos Aires",
        TipoOrganizacion.organismo_rescate,
        "30-70987654-3",
    ),
    ("Cruz Solidaria", TipoOrganizacion.ong, "30-65432198-7"),
    ("Manos Unidas", TipoOrganizacion.ong, "30-65432199-5"),
    ("Cruz Roja Argentina - Filial Bahía Blanca", TipoOrganizacion.ong, "30-99999999-4"),
    ("Bomberos Voluntarios de La Plata", TipoOrganizacion.organismo_rescate, "30-99999999-5"),
    ("Grupo Scouts de Pergamino", TipoOrganizacion.ong, "30-99999999-6"),
)

# Mismos CUIT que las semillas de la aplicacion web: es la clave con la que se cruzan las
# organizaciones de los dos sistemas. Todas arrancan habilitadas salvo las de esta tabla, que
# muestran el caso de una ONG registrada que con el tiempo quedo inhabilitada.
SUSPENDIDAS_DE_DEMOSTRACION: dict[str, str] = {
    "Cruz Roja Argentina - Filial Bahía Blanca": (
        "Certificación sanitaria vencida (dato de demostración)."
    ),
}
MOTIVO_SEMILLA = "Estado inicial del padrón (datos de demostración)."

CERTIFICACIONES: dict[str, tuple[tuple[str, TipoItem], ...]] = {
    "Cruz Solidaria": (
        ("Certificación de atención sanitaria", TipoItem.personal_medico),
        ("Certificación de distribución de alimentos", TipoItem.alimentos),
        ("Certificación de abastecimiento de agua", TipoItem.agua),
    ),
    "Manos Unidas": (
        ("Certificación de asistencia humanitaria", TipoItem.abrigo),
        ("Certificación de distribución de medicamentos", TipoItem.medicamentos),
    ),
    "Cruz Roja Argentina - Filial Bahía Blanca": (
        ("Certificación de atención sanitaria", TipoItem.personal_medico),
        ("Certificación de respuesta ante emergencias", TipoItem.rescate),
        ("Certificación de logística de maquinaria", TipoItem.maquinaria),
    ),
    "Bomberos Voluntarios de La Plata": (
        ("Certificación de operaciones de rescate", TipoItem.rescate),
        ("Certificación de maquinaria pesada", TipoItem.maquinaria),
        ("Certificación de atención sanitaria", TipoItem.personal_medico),
    ),
    "Grupo Scouts de Pergamino": (
        ("Certificación de apoyo alimentario", TipoItem.alimentos),
        ("Certificación de apoyo logístico", TipoItem.otro),
    ),
}

ITEMS: dict[str, tuple[TipoItem, str, str]] = {
    "Agua potable envasada": (TipoItem.agua, "litros", "Agua potable para consumo."),
    "Paramédicos": (TipoItem.personal_medico, "personas", "Personal paramédico."),
    "Enfermeros": (TipoItem.personal_medico, "personas", "Personal de enfermería."),
    "Rescatistas": (TipoItem.rescate, "personas", "Personal especializado en rescate."),
    "Voluntarios generales": (TipoItem.personal_medico, "personas", "Voluntariado disponible."),
    "Perros de búsqueda": (TipoItem.rescate, "animales", "Perros entrenados para búsqueda."),
    "Frazadas": (TipoItem.abrigo, "unidades", "Frazadas para personas evacuadas."),
    "Colchones": (TipoItem.abrigo, "unidades", "Colchones para refugios temporales."),
    "Carpas familiares": (TipoItem.abrigo, "unidades", "Carpas para alojamiento temporal."),
    "Antibióticos": (TipoItem.medicamentos, "dosis", "Antibióticos."),
    "Analgésicos": (TipoItem.medicamentos, "dosis", "Analgésicos."),
    "Botiquines de primeros auxilios": (
        TipoItem.medicamentos,
        "kits",
        "Botiquines de primeros auxilios.",
    ),
    "Pañales para adulto": (TipoItem.otro, "unidades", "Pañales para adulto."),
    "Pañales para bebes": (TipoItem.otro, "unidades", "Pañales para bebés."),
    "Toallas jabonosas": (TipoItem.otro, "unidades", "Toallas jabonosas."),
    "Kit higiene bucal": (TipoItem.otro, "kits", "Kits de higiene bucal."),
    "Suplemento alimenticio": (TipoItem.alimentos, "unidades", "Suplementos alimenticios."),
    "Raciones de alimento no perecedero": (
        TipoItem.alimentos,
        "raciones",
        "Raciones de alimento no perecedero.",
    ),
    "Leche en polvo": (TipoItem.alimentos, "kilogramos", "Leche en polvo."),
    "Yerba": (TipoItem.alimentos, "kilogramos", "Yerba mate."),
    "Lentejas": (TipoItem.alimentos, "kilogramos", "Lentejas."),
    "Harina de trigo": (TipoItem.alimentos, "kilogramos", "Harina de trigo."),
    "Fideos": (TipoItem.alimentos, "kilogramos", "Fideos secos."),
    "Arroz": (TipoItem.alimentos, "kilogramos", "Arroz."),
    "Café": (TipoItem.alimentos, "kilogramos", "Café."),
    "Latas de arvejas": (TipoItem.alimentos, "latas", "Arvejas enlatadas."),
    "Ambulancias": (TipoItem.maquinaria, "vehículos", "Ambulancias."),
    "Camiones de carga": (TipoItem.maquinaria, "vehículos", "Camiones de carga."),
    "Retroexcavadoras": (TipoItem.maquinaria, "vehículos", "Retroexcavadoras."),
    "Generadores eléctricos": (TipoItem.maquinaria, "unidades", "Generadores eléctricos."),
    "Tanques de agua": (TipoItem.maquinaria, "unidades", "Tanques de agua."),
}

INVENTARIOS: dict[str, tuple[str, str, dict[str, int]]] = {
    "Cruz Solidaria": (
        "Depósito Cruz Solidaria",
        "Stock demo para ofertas de ayuda.",
        {
            "Agua potable envasada": 1000,
            "Paramédicos": 10,
            "Raciones de alimento no perecedero": 600,
        },
    ),
    "Manos Unidas": (
        "Depósito Manos Unidas",
        "Inventario demo para gestionar recursos disponibles.",
        {},
    ),
    "Cruz Roja Argentina - Filial Bahía Blanca": (
        "Depósito Cruz Roja Bahía Blanca",
        "Centro logístico de la filial.",
        {
            "Paramédicos": 15,
            "Enfermeros": 8,
            "Botiquines de primeros auxilios": 40,
            "Frazadas": 200,
            "Agua potable envasada": 1000,
            "Antibióticos": 30000,
            "Ambulancias": 5,
            "Camiones de carga": 1,
        },
    ),
    "Bomberos Voluntarios de La Plata": (
        "Cuartel central La Plata",
        "Stock del cuartel de bomberos voluntarios.",
        {
            "Rescatistas": 25,
            "Perros de búsqueda": 3,
            "Retroexcavadoras": 1,
            "Camiones de carga": 2,
            "Ambulancias": 1,
            "Frazadas": 100,
            "Generadores eléctricos": 4,
            "Tanques de agua": 12,
        },
    ),
    "Grupo Scouts de Pergamino": (
        "Depósito Scouts Pergamino",
        "Acopio de campaña del grupo scout.",
        {
            "Voluntarios generales": 40,
            "Carpas familiares": 10,
            "Colchones": 30,
            "Leche en polvo": 80,
            "Frazadas": 800,
            "Agua potable envasada": 5000,
            "Raciones de alimento no perecedero": 1200,
            "Kit higiene bucal": 250,
        },
    ),
}


@registrar("organizaciones")
def sembrar_organizaciones() -> list[ResultadoSemilla]:
    resultado = ResultadoSemilla("organizaciones")
    for nombre, tipo, identificador in ORGANIZACIONES_DE_DEMOSTRACION:
        motivo_suspension = SUSPENDIDAS_DE_DEMOSTRACION.get(nombre)
        estado = (
            EstadoHabilitacion.suspendida if motivo_suspension else EstadoHabilitacion.habilitada
        )
        organizacion, creado = obtener_o_crear(
            Organizacion,
            claves={"nombre": nombre},
            valores={
                "tipo": tipo,
                "mail_contacto": f"semillas+{identificador.replace('-', '')}@rescuesync.example",
                "identificador_nacional": identificador,
                "estado_habilitacion": estado,
            },
        )
        # El historial solo se escribe al crear: una organizacion que ya existia conserva su
        # estado operativo (por ejemplo, la que un administrador habilito a mano).
        if creado:
            organizacion.historial_habilitacion.append(
                HistorialHabilitacion(
                    estado_anterior=None,
                    estado_nuevo=estado,
                    motivo=motivo_suspension or MOTIVO_SEMILLA,
                )
            )
        resultado.contar(creado)
    return [resultado]


@registrar("items")
def sembrar_items() -> list[ResultadoSemilla]:
    resultado = ResultadoSemilla("items")
    for nombre, (tipo, unidad, descripcion) in ITEMS.items():
        _, creado = obtener_o_crear(
            Item,
            claves={"nombre": nombre},
            valores={"tipo": tipo, "unidad_medida": unidad, "descripcion": descripcion},
        )
        resultado.contar(creado)
    return [resultado]


@registrar("certificaciones")
def sembrar_certificaciones() -> list[ResultadoSemilla]:
    resultado = ResultadoSemilla("certificaciones")
    for nombre_org, certificaciones in CERTIFICACIONES.items():
        organizacion = Organizacion.query.filter_by(nombre=nombre_org).one()
        for nombre, tipo in certificaciones:
            certificacion, creada = obtener_o_crear(
                Certificacion,
                claves={"nombre": nombre, "tipo": tipo},
            )
            _, asignada = obtener_o_crear(
                OrganizacionCertificacion,
                claves={
                    "organizacion_id": organizacion.id,
                    "certificacion_id": certificacion.id,
                },
                valores={
                    "nivel_riesgo_permitido": "ALTO",
                    "fecha_emision": datetime.now(UTC),
                },
            )
            resultado.contar(creada or asignada)
    return [resultado]


@registrar("inventarios")
def sembrar_inventarios() -> list[ResultadoSemilla]:
    resultado_inventarios = ResultadoSemilla("inventarios")
    resultado_items = ResultadoSemilla("inventario_items")
    for nombre_org, (_nombre, _descripcion, stock) in INVENTARIOS.items():
        organizacion = Organizacion.query.filter_by(nombre=nombre_org).one()
        inventario, creado = obtener_o_crear(
            Inventario,
            claves={"organizacion_id": organizacion.id},
        )
        resultado_inventarios.contar(creado)

        for nombre_item, cantidad in stock.items():
            item = Item.query.filter_by(nombre=nombre_item).one()
            _, creado = obtener_o_crear(
                InventarioItem,
                claves={"inventario_id": inventario.id, "item_id": item.id},
                valores={"cantidad_disponible": cantidad},
            )
            resultado_items.contar(creado)
    return [resultado_inventarios, resultado_items]
