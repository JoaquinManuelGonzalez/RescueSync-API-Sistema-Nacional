"""Datos semilla de organizaciones, certificaciones e inventarios."""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime

from app.core.semillas import ResultadoSemilla, obtener_o_crear, registrar
from app.modulos.organizaciones.modelos import (
    Certificacion,
    EstadoHabilitacion,
    HistorialHabilitacion,
    Inventario,
    InventarioItem,
    Item,
    NivelCertificacion,
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
    ("Bomberos Voluntarios de La Plata", TipoOrganizacion.ong, "30-99999999-5"),
    ("Grupo Scouts de Pergamino", TipoOrganizacion.ong, "30-99999999-6"),
)

# Mismos nombres, CUIT y tipo que las semillas de la aplicacion web (sus municipios y su centro
# coordinador son `organismo_rescate` aca): el CUIT es la clave con la que se cruzan las
# organizaciones de los dos sistemas. Todas arrancan habilitadas salvo las de esta tabla, que
# muestran el caso de una ONG registrada que con el tiempo quedo inhabilitada: en la web oferta
# sin problemas y el Sistema Nacional rechaza sus aportes.
SUSPENDIDAS_DE_DEMOSTRACION: dict[str, str] = {
    "Cruz Roja Argentina - Filial Bahía Blanca": (
        "Certificación sanitaria vencida (dato de demostración)."
    ),
}
MOTIVO_SEMILLA = "Estado inicial del padrón (datos de demostración)."
NIVELES_CERTIFICACION_DE_DEMOSTRACION = {
    "Manos Unidas": NivelCertificacion.media,
}

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
        ("Certificación de respuesta ante emergencias", TipoItem.rescate),
        ("Certificación de logística de maquinaria", TipoItem.maquinaria),
        ("Certificación de atención sanitaria", TipoItem.personal_medico),
    ),
    "Grupo Scouts de Pergamino": (
        ("Certificación de distribución de alimentos", TipoItem.alimentos),
        ("Certificación de apoyo logístico", TipoItem.otro),
    ),
}

# Catalogo compartido con la aplicacion web: mismos nombres (de los que sale `codigo_recurso`),
# mismo tipo, unidad y consumible que `backend/app/modulos/emergencias/semillas_items.py` del
# repo RescueSync-Web-App. Bonita reenvia los codigos de la web sin traducirlos, asi que un item
# que falte aca hace fallar la evaluacion de ofertas con 404. `tests/test_catalogo_compartido.py`
# compara este catalogo con la copia de la web. Los items nuevos van al final para no cambiar los
# ids de una base nueva (los ejemplos de Swagger usan algunos).
ITEMS: dict[str, tuple[TipoItem, str, str]] = {
    "Agua potable envasada": (
        TipoItem.agua,
        "litros",
        "Botellas selladas aptas para consumo humano.",
    ),
    "Paramédicos": (
        TipoItem.personal_medico,
        "personas",
        "Personal de atención prehospitalaria con certificación vigente.",
    ),
    "Enfermeros": (
        TipoItem.personal_medico,
        "personas",
        "Personal de enfermería para primeros auxilios y cuidados básicos.",
    ),
    "Rescatistas": (
        TipoItem.rescate,
        "personas",
        "Personal entrenado en búsqueda y rescate urbano.",
    ),
    "Voluntarios generales": (
        TipoItem.otro,
        "personas",
        "Personal de apoyo voluntario no especializado.",
    ),
    "Perros de búsqueda": (
        TipoItem.rescate,
        "unidades",
        "Caninos entrenados para detección de personas.",
    ),
    "Frazadas": (TipoItem.abrigo, "unidades", "Frazadas para personas evacuadas."),
    "Colchones": (
        TipoItem.abrigo,
        "unidades",
        "Colchones de goma espuma para refugios temporales.",
    ),
    "Carpas familiares": (TipoItem.abrigo, "unidades", "Carpas para 4-6 personas."),
    "Antibióticos": (TipoItem.medicamentos, "unidades", "Comprimidos de uso general."),
    "Analgésicos": (TipoItem.medicamentos, "unidades", "Comprimidos de uso general."),
    "Botiquines de primeros auxilios": (
        TipoItem.medicamentos,
        "unidades",
        "Kit básico de primeros auxilios.",
    ),
    "Pañales para adulto": (TipoItem.medicamentos, "unidades", "Pañales para adulto."),
    "Pañales para bebes": (TipoItem.otro, "unidades", "Pañales descartables."),
    "Toallas jabonosas": (
        TipoItem.otro,
        "unidades",
        "Toallas jabonosas desechables y sin enjuague. De aseo para adultos, bebés y niños.",
    ),
    "Kit higiene bucal": (
        TipoItem.otro,
        "unidades",
        "Kit individual de cepillo de dientes y pasta dental.",
    ),
    "Suplemento alimenticio": (
        TipoItem.medicamentos,
        "unidades",
        "Fuente adicional de nutrientes para personas en situaciones críticas.",
    ),
    "Raciones de alimento no perecedero": (
        TipoItem.alimentos,
        "raciones",
        "Raciones individuales instantáneas, listas para consumo.",
    ),
    "Leche en polvo": (TipoItem.alimentos, "kg", "Leche en polvo."),
    "Yerba": (TipoItem.alimentos, "kg", "Yerba mate."),
    "Lentejas": (TipoItem.alimentos, "kg", "Lentejas."),
    "Harina de trigo": (TipoItem.alimentos, "kg", "Harina de trigo."),
    "Fideos": (TipoItem.alimentos, "kg", "Fideos secos."),
    "Arroz": (TipoItem.alimentos, "kg", "Arroz."),
    "Café": (TipoItem.alimentos, "kg", "Café."),
    "Latas de arvejas": (TipoItem.alimentos, "kg", "Arvejas enlatadas."),
    "Ambulancias": (TipoItem.maquinaria, "unidades", "Unidades de traslado medicalizado."),
    "Camiones de carga": (TipoItem.maquinaria, "unidades", "Capacidad mínima 5 toneladas."),
    "Retroexcavadoras": (TipoItem.maquinaria, "unidades", "Para remoción de escombros."),
    "Generadores eléctricos": (TipoItem.maquinaria, "unidades", "Generadores portátiles 5 kVA."),
    "Tanques de agua": (
        TipoItem.agua,
        "unidades",
        "Tanques de 1000 L para distribución comunitaria.",
    ),
    "Médicos de urgencia": (
        TipoItem.personal_medico,
        "personas",
        "Médicos con especialidad en emergencias.",
    ),
    "Bomberos": (TipoItem.rescate, "personas", "Personal civil de bomberos voluntarios."),
    "Brigadistas": (
        TipoItem.rescate,
        "personas",
        "Bomberos civiles voluntarios especializados en incendios forestales.",
    ),
    "Polenta": (TipoItem.alimentos, "kg", "Polenta."),
    "Aceite": (TipoItem.alimentos, "raciones", "Aceite."),
    "Galletitas de agua": (TipoItem.alimentos, "unidades", "Galletitas de agua."),
    "Galletitas dulces": (TipoItem.alimentos, "unidades", "Galletitas dulces."),
    "Azúcar": (TipoItem.alimentos, "kg", "Azúcar."),
    "Ropa de invierno": (
        TipoItem.abrigo,
        "unidades",
        "Donaciones de ropa apta para temperaturas por debajo de los 15°.",
    ),
    "Ropa de verano": (
        TipoItem.abrigo,
        "unidades",
        "Donaciones de ropa apta para temperaturas por encima de los 15°.",
    ),
    "Paracetamol": (
        TipoItem.medicamentos,
        "unidades",
        "Genérico. Comprimidos de 200, 600, 800 o 1000 mgr.",
    ),
    "Ibuprofeno": (
        TipoItem.medicamentos,
        "unidades",
        "Genérico. Comprimidos de 200, 600 o 800 mgr.",
    ),
    "Suero fisiológico": (
        TipoItem.medicamentos,
        "unidades",
        "Para reponer líquidos, limpiar ojos, lavar heridas y quemaduras, y diluir medicamentos.",
    ),
    "Toallitas femeninas": (TipoItem.otro, "unidades", "Para higiene menstrual."),
    "Jabón": (TipoItem.otro, "unidades", "Barras de jabón para aseo personal."),
}


def _codigo_recurso(nombre: str) -> str:
    normalizado = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Z0-9]+", "_", normalizado.upper()).strip("_")
    return f"RSR-{slug}"


ITEMS_NO_CONSUMIBLES = frozenset(
    {
        "Paramédicos",
        "Médicos de urgencia",
        "Enfermeros",
        "Rescatistas",
        "Perros de búsqueda",
        "Bomberos",
        "Brigadistas",
        "Voluntarios generales",
        "Ambulancias",
        "Camiones de carga",
        "Retroexcavadoras",
        "Generadores eléctricos",
    }
)

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
        # El tipo, en cambio, es dato de referencia: ningun endpoint lo modifica y tiene que
        # coincidir con la web para que la evaluacion de ofertas acepte a sus ONG.
        elif organizacion.tipo is not tipo:
            organizacion.tipo = tipo
            resultado.actualizados += 1
        resultado.contar(creado)
    return [resultado]


@registrar("items")
def sembrar_items() -> list[ResultadoSemilla]:
    resultado = ResultadoSemilla("items")
    for nombre, (tipo, unidad, descripcion) in ITEMS.items():
        atributos = {
            "tipo": tipo,
            "unidad_medida": unidad,
            "descripcion": descripcion,
            "consumible": nombre not in ITEMS_NO_CONSUMIBLES,
        }
        item, creado = obtener_o_crear(
            Item,
            claves={"nombre": nombre},
            valores={"codigo_recurso": _codigo_recurso(nombre), **atributos},
        )
        # El catalogo solo lo define este seed (ningun endpoint crea ni edita items): en cada
        # deploy se corrigen los atributos de los items que ya existian para que la base
        # compartida siga igual a la web. El codigo no se toca porque sale del nombre.
        cambios = {
            campo: valor for campo, valor in atributos.items() if getattr(item, campo) != valor
        }
        if not creado and cambios:
            for campo, valor in cambios.items():
                setattr(item, campo, valor)
            resultado.actualizados += 1
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
            asignacion, asignada = obtener_o_crear(
                OrganizacionCertificacion,
                claves={
                    "organizacion_id": organizacion.id,
                    "certificacion_id": certificacion.id,
                },
                valores={
                    "nivel_riesgo_permitido": NivelCertificacion.alta,
                    "fecha_emision": datetime.now(UTC),
                },
            )
            asignacion.nivel_riesgo_permitido = NIVELES_CERTIFICACION_DE_DEMOSTRACION.get(
                nombre_org,
                NivelCertificacion.alta,
            )
            resultado.contar(creada or asignada)
    return [resultado]


@registrar("inventarios")
def sembrar_inventarios() -> list[ResultadoSemilla]:
    resultado_inventarios = ResultadoSemilla("inventarios")
    resultado_items = ResultadoSemilla("inventario_items", etiqueta_actualizados="repuestos")
    for nombre_org, (_nombre, _descripcion, stock) in INVENTARIOS.items():
        organizacion = Organizacion.query.filter_by(nombre=nombre_org).one()
        inventario, creado = obtener_o_crear(
            Inventario,
            claves={"organizacion_id": organizacion.id},
        )
        resultado_inventarios.contar(creado)

        for nombre_item, cantidad in stock.items():
            item = Item.query.filter_by(nombre=nombre_item).one()
            inventario_item, creado = obtener_o_crear(
                InventarioItem,
                claves={"inventario_id": inventario.id, "item_id": item.id},
                valores={"cantidad_disponible": cantidad},
            )
            resultado_items.contar(creado)
            # Reposicion: el seed corre en cada deploy y deja el deposito de demostracion al menos
            # con su stock inicial, para que las pruebas no lo agoten. Nunca baja una cantidad ni
            # toca los compromisos, que ya descontaron lo suyo al registrarse.
            if inventario_item.cantidad_disponible < cantidad:
                inventario_item.cantidad_disponible = cantidad
                resultado_items.actualizados += 1
    return [resultado_inventarios, resultado_items]
