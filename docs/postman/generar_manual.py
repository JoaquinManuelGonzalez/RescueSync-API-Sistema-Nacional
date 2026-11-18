"""Genera docs/postman/Manual_de_Pruebas_Postman.pdf a partir de este archivo.

El manual describe la colección `sistema-nacional.postman_collection.json`: si cambia la
colección (carpetas, requests, aserciones o variables), se actualiza este archivo y se regenera
el PDF. ReportLab no es dependencia de la API, así que se trae solo para correrlo:

    uv run --no-project --with reportlab==5.1.0 python docs/postman/generar_manual.py

La tabla de credenciales (sección 3.3) tiene las de la nube, para la evaluación.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DESTINO = Path(__file__).with_name("Manual_de_Pruebas_Postman.pdf")
URL_RENDER = "https://rescuesync-sistema-nacional.onrender.com"
FECHA = "noviembre de 2026"

NEGRO = colors.HexColor("#111111")
GRIS_LINEA = colors.HexColor("#d0d0d0")
GRIS_FILA = colors.HexColor("#f3f3f3")
FONDO_AVISO = colors.HexColor("#fff7e6")
BORDE_AVISO = colors.HexColor("#e0b252")

_base = getSampleStyleSheet()
ESTILOS = {
    "titulo": ParagraphStyle(
        "titulo", parent=_base["Title"], fontSize=30, leading=36, alignment=0, spaceAfter=10
    ),
    "subtitulo": ParagraphStyle(
        "subtitulo",
        parent=_base["Normal"],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#333333"),
    ),
    "portada": ParagraphStyle(
        "portada",
        parent=_base["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#555555"),
    ),
    "h1": ParagraphStyle(
        "h1", parent=_base["Heading1"], fontSize=15, leading=19, spaceBefore=14, spaceAfter=8
    ),
    "h2": ParagraphStyle(
        "h2", parent=_base["Heading2"], fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=5
    ),
    "cuerpo": ParagraphStyle(
        "cuerpo",
        parent=_base["BodyText"],
        fontSize=9.5,
        leading=13.5,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    ),
    "celda": ParagraphStyle("celda", parent=_base["BodyText"], fontSize=8.5, leading=11),
    "celda_titulo": ParagraphStyle(
        "celda_titulo",
        parent=_base["BodyText"],
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        fontName="Helvetica-Bold",
    ),
    "aviso": ParagraphStyle("aviso", parent=_base["BodyText"], fontSize=9, leading=12.5),
    "codigo": ParagraphStyle(
        "codigo", parent=_base["Code"], fontSize=7.8, leading=10.5, leftIndent=0
    ),
}


def parrafo(texto: str, estilo: str = "cuerpo") -> Paragraph:
    return Paragraph(texto, ESTILOS[estilo])


def tabla(encabezado: list[str], filas: list[list[str]], anchos: list[float]) -> Table:
    datos = [[parrafo(celda, "celda_titulo") for celda in encabezado]]
    datos += [[parrafo(celda, "celda") for celda in fila] for fila in filas]
    resultado = Table(datos, colWidths=[ancho * cm for ancho in anchos], repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), NEGRO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    estilo += [("BACKGROUND", (0, i), (-1, i), GRIS_FILA) for i in range(2, len(datos), 2)]
    resultado.setStyle(TableStyle(estilo))
    return resultado


def aviso(texto: str) -> Table:
    caja = Table([[parrafo(texto, "aviso")]], colWidths=[17 * cm])
    caja.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), FONDO_AVISO),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDE_AVISO),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return caja


def lista(items: list[str], numerada: bool = False) -> ListFlowable:
    return ListFlowable(
        [ListItem(parrafo(item), leftIndent=12) for item in items],
        bulletType="1" if numerada else "bullet",
        start="1" if numerada else None,
        bulletFormat="%s." if numerada else None,
        leftIndent=14,
        bulletFontSize=8.5,
    )


def codigo(texto: str) -> Table:
    caja = Table([[Preformatted(texto, ESTILOS["codigo"])]], colWidths=[17 * cm])
    caja.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), GRIS_FILA),
                ("BOX", (0, 0), (-1, -1), 0.4, GRIS_LINEA),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return caja


def carpeta(titulo: str, descripcion: str, filas: list[list[str]]) -> KeepTogether:
    return KeepTogether(
        [
            parrafo(titulo, "h2"),
            parrafo(descripcion),
            tabla(["Solicitud", "Rol", "Resultado esperado"], filas, [5.2, 2.6, 9.2]),
        ]
    )


def portada() -> list:
    return [
        Spacer(1, 5 * cm),
        Table([[""]], colWidths=[17 * cm], style=[("LINEABOVE", (0, 0), (-1, 0), 2, NEGRO)]),
        Spacer(1, 0.6 * cm),
        parrafo("RescueSync", "titulo"),
        parrafo("API del Sistema Nacional", "subtitulo"),
        Spacer(1, 0.8 * cm),
        Table([[""]], colWidths=[17 * cm], style=[("LINEABOVE", (0, 0), (-1, 0), 0.5, GRIS_LINEA)]),
        Spacer(1, 0.3 * cm),
        parrafo(f"Manual de pruebas — Colección Postman · {FECHA}", "portada"),
        PageBreak(),
    ]


def introduccion() -> list:
    return [
        parrafo("1. Introducción", "h1"),
        parrafo(
            "Este manual explica cómo importar, configurar y correr la colección Postman "
            "<b>RescueSync - API del Sistema Nacional</b>. La colección tiene <b>7 carpetas, 40 "
            "requests y 55 aserciones</b> que cubren la autenticación JWT y la protección por rol, "
            "las consultas de catálogo y disponibilidad, el padrón de ONGs, la carga de "
            "inventario y certificaciones, el compromiso, la validación, la liberación y la "
            "finalización de recursos (con una prueba de control de concurrencia) y la "
            "evaluación de ofertas."
        ),
        parrafo(
            "Se corre completa con el <i>Collection Runner</i> de Postman. Cada request verifica "
            "el código de estado y el contenido de la respuesta, y varias encadenan datos entre "
            "sí con variables. La colección se puede volver a correr sobre la misma base: lo que "
            "modifica se deshace en la misma corrida o queda acotado (sección 7)."
        ),
        parrafo("2. Archivos y accesos", "h1"),
        tabla(
            ["Recurso", "Descripción"],
            [
                ["Swagger UI", f"{URL_RENDER}/docs (documentación interactiva de cada endpoint)"],
                [
                    "sistema-nacional.postman_collection.json",
                    "La colección: 40 requests con sus tests",
                ],
                [
                    "local.postman_environment.json",
                    "Entorno local: baseUrl = http://localhost:8000",
                ],
                ["render.postman_environment.json", f"Entorno de la nube: baseUrl = {URL_RENDER}"],
                [
                    "Manual_de_Pruebas_Postman.pdf y generar_manual.py",
                    "Este manual y el script que lo genera (carpeta docs/postman del repositorio)",
                ],
            ],
            [6.5, 10.5],
        ),
        parrafo("3. Prerrequisitos e importación", "h1"),
        parrafo("3.1 Software", "h2"),
        parrafo("Postman Desktop (versión 10 o posterior) o Postman Web. Nada más."),
        parrafo("3.2 Importación", "h2"),
        lista(
            [
                "Postman › <b>Import</b> › elegir <b>sistema-nacional.postman_collection.json</b>.",
                "Importar también el entorno: <b>local.postman_environment.json</b> o "
                "<b>render.postman_environment.json</b>.",
                "Activar el entorno en el selector de la esquina superior derecha.",
            ],
            numerada=True,
        ),
        parrafo("3.3 Credenciales del entorno", "h2"),
        parrafo(
            "Antes de la primera corrida se completan dos variables del entorno. Con el entorno "
            "render se usan los valores de esta tabla."
        ),
        tabla(
            ["Variable", "Valor", "De dónde sale"],
            [
                ["usuarioAdmin", "admin-sn", "Fijo, viene completo"],
                [
                    "contrasenaAdmin",
                    "RescueSync.2026",
                    "Credencial del administrador en producción (Render). En local: "
                    "SEMILLA_CONTRASENA_ADMIN del .env",
                ],
                ["clientIdBonita", "bonita-rescuesync", "Fijo, viene completo"],
                [
                    "clientSecretBonita",
                    "RescueSync.2026",
                    "Clave secreta de Bonita en producción (Render). En local: "
                    "SEMILLA_SECRETO_BONITA del .env",
                ],
            ],
            [3.6, 3.2, 10.2],
        ),
        Spacer(1, 6),
        aviso(
            "En local, si las variables SEMILLA_* del .env están vacías, las cuentas se crean "
            "con <b>flask cuentas crear</b> (ver README de la API). Las demás variables "
            "(tokens, CUIT, ids) se completan solas durante la corrida."
        ),
    ]


def variables_y_orden() -> list:
    return [
        parrafo("4. Variables que se completan solas", "h1"),
        parrafo(
            "La colección guarda datos de una respuesta para usarlos en requests posteriores. Por "
            "eso se corre en orden y completa."
        ),
        tabla(
            ["Variable", "Se genera en", "Se usa en", "Qué guarda"],
            [
                [
                    "tokenAdmin",
                    "1 › Login administrador",
                    "Requests de rol administrador",
                    "JWT de la cuenta admin-sn",
                ],
                [
                    "tokenBonita",
                    "1 › Login Bonita",
                    "Requests de rol sistema",
                    "JWT de bonita-rescuesync (OAuth2 client credentials)",
                ],
                [
                    "tokenAdulterado",
                    "2 › Token adulterado",
                    "El mismo request",
                    "El token de Bonita con la firma alterada",
                ],
                [
                    "certificacionId",
                    "3 › Catálogo de certificaciones",
                    "4 › Cargar certificación",
                    "UUID de una certificación del catálogo",
                ],
                [
                    "itemId",
                    "3 › Disponibilidad global de personal médico",
                    "4 › Cargar ítem al inventario",
                    "UUID de un ítem no consumible del catálogo",
                ],
                [
                    "cuitNueva",
                    "5 › Alta de ONG",
                    "5 (habilitación) y 4 (gestión)",
                    "CUIT aleatorio de la ONG de prueba de esta corrida",
                ],
                [
                    "emergenciaPostmanId",
                    "6 › Compromiso",
                    "6 › Liberación y finalización",
                    "UUID nuevo de la emergencia de esta corrida",
                ],
                [
                    "cantidadInsuficiente",
                    "7 › Caso rechazo por cantidad insuficiente",
                    "El mismo request",
                    "Paramédicos disponibles de Cruz Solidaria más uno",
                ],
            ],
            [3.9, 4.2, 4.0, 4.9],
        ),
        parrafo("5. Orden de ejecución", "h1"),
        parrafo(
            "Se corre <b>toda la colección de una vez, sin reordenar</b>. El resultado esperado es "
            "<b>55 aserciones aprobadas</b>. La carpeta 4 está después de la 5 a propósito: usa la "
            "ONG que da de alta el padrón."
        ),
        tabla(
            ["Paso", "Carpeta", "Qué hace"],
            [
                [
                    "1",
                    "1. Autenticación",
                    "Logins del administrador y de Bonita; guarda los tokens",
                ],
                [
                    "2",
                    "2. Protección de los endpoints",
                    "401 sin token o con token adulterado; 403 por rol",
                ],
                [
                    "3",
                    "3. Consultas de catálogo",
                    "Certificaciones, ONGs habilitadas y disponibilidad (solo lectura)",
                ],
                [
                    "4",
                    "5. Padrón de ONGs",
                    "Alta y habilitación de una ONG nueva; Cruz Roja se "
                    "rehabilita y vuelve a quedar suspendida",
                ],
                ["5", "4. Gestión de organizaciones", "Inventario y certificación de la ONG nueva"],
                [
                    "6",
                    "6. Compromiso/Liberacion",
                    "Compromiso, validación, idempotencia, "
                    "liberación por ONG, finalización y concurrencia",
                ],
                [
                    "7",
                    "7. Evaluación de ofertas",
                    "Clasificación de aportes: principal o apoyo, "
                    "no registrada, cantidad insuficiente y sin certificación",
                ],
            ],
            [1.3, 5.2, 10.5],
        ),
        parrafo("Cómo lanzar el Collection Runner", "h2"),
        lista(
            [
                "Clic derecho sobre la colección › <b>Run collection</b>.",
                "Verificar el entorno en el desplegable <i>Environment</i>.",
                "No reordenar: dejar el <i>Run order</i> como viene.",
                "<b>Run RescueSync - API del Sistema Nacional</b>.",
                "Al terminar, el runner muestra las 55 aserciones aprobadas.",
            ],
            numerada=True,
        ),
        parrafo(
            "Desde una terminal, con Docker y sin instalar nada, se puede correr con Newman. Con "
            "la API local, agregar <font face='Courier'>--env-var "
            "baseUrl=http://host.docker.internal:8000</font>:"
        ),
        codigo(
            "\n".join(
                [
                    'docker run --rm -v "$PWD/docs/postman:/etc/newman" postman/newman:6-alpine \\',
                    "  run sistema-nacional.postman_collection.json \\",
                    "  -e local.postman_environment.json \\",
                    "  --env-var contrasenaAdmin=... --env-var clientSecretBonita=...",
                ]
            )
        ),
    ]


def detalle_por_carpeta() -> list:
    return [
        parrafo("6. Detalle por carpeta", "h1"),
        parrafo(
            "Cada request indica el rol que exige el endpoint: público, administrador "
            "(admin-sn) o sistema (Bonita). Todos los ids son UUID."
        ),
        carpeta(
            "6.1 Autenticación (6 requests, 7 aserciones)",
            "POST /login en sus dos modos y GET /cuentas/yo. Va primero: los logins guardan los "
            "tokens que usan las demás carpetas.",
            [
                [
                    "Login administrador (JSON)",
                    "Público",
                    "200 con un token Bearer; la respuesta no se cachea",
                ],
                ["Login Bonita (OAuth2 client credentials)", "Público", "200 con un token Bearer"],
                ["Login con contraseña incorrecta", "Público", "401 NO_AUTENTICADO"],
                [
                    "Login OAuth2 con secreto incorrecto",
                    "Público",
                    "401 invalid_client (formato del RFC 6749)",
                ],
                ["Cuenta del token (administrador)", "administrador", "Rol administrador"],
                [
                    "Cuenta del token (Bonita, con trazabilidad)",
                    "sistema",
                    "Rol sistema y las cabeceras de trazabilidad recibidas",
                ],
            ],
        ),
        carpeta(
            "6.2 Protección de los endpoints (4 requests, 6 aserciones)",
            "Pedidos que la API tiene que rechazar.",
            [
                ["Sin token", "Ninguno", "401 NO_AUTENTICADO, motivo token_ausente"],
                ["Token adulterado", "Firma inválida", "401 NO_AUTENTICADO, motivo token_invalido"],
                [
                    "Bonita intenta dar de alta una ONG",
                    "sistema",
                    "403 PERMISO_DENEGADO: es de administrador",
                ],
                [
                    "Bonita intenta suspender una ONG",
                    "sistema",
                    "403 PERMISO_DENEGADO: es de administrador",
                ],
            ],
        ),
        carpeta(
            "6.3 Consultas de catálogo (5 requests, 11 aserciones)",
            "Solo lectura. Guardan un ítem y una certificación del catálogo para la carpeta 4.",
            [
                [
                    "Catálogo de certificaciones",
                    "admin o sistema",
                    "200 paginado; guarda certificacionId",
                ],
                [
                    "ONGs habilitadas",
                    "admin o sistema",
                    "200 paginado; cada organización trae su CUIT y un id UUID",
                ],
                [
                    "Disponibilidad global de personal médico",
                    "admin o sistema",
                    "200; solo no consumibles del tipo pedido y total = disponible + comprometido; "
                    "guarda itemId",
                ],
                [
                    "Disponibilidad de agua (consumible): no se lista",
                    "admin o sistema",
                    "200 sin recursos: la API no lleva stock de los consumibles",
                ],
                [
                    "Disponibilidad de una ONG (Cruz Solidaria)",
                    "admin o sistema",
                    "200; solo no consumibles, con total = disponible + comprometido",
                ],
            ],
        ),
        carpeta(
            "6.4 Padrón de ONGs (10 requests, 11 aserciones)",
            "Alta y habilitación de una ONG con un CUIT aleatorio por corrida, y el ciclo de Cruz "
            "Roja (30-99999999-4), que arranca y termina suspendida.",
            [
                [
                    "Consultar ONG suspendida (Bonita)",
                    "admin o sistema",
                    "Cruz Roja suspendida y no habilitada. Antes, un pre-request la vuelve a "
                    "suspender si alguien la habilitó en la base",
                ],
                ["Alta de ONG (onboarding)", "administrador", "201, nace pendiente"],
                [
                    "Alta duplicada (mismo CUIT)",
                    "administrador",
                    "409 CONFLICTO_DE_ESTADO; el campo duplicado es el CUIT",
                ],
                ["Alta con CUIT inválido", "administrador", "400 SOLICITUD_INVALIDA"],
                ["Habilitar la ONG nueva", "administrador", "200, queda habilitada"],
                ["Habilitarla otra vez", "administrador", "409: ya estaba habilitada"],
                ["Suspender sin motivo", "administrador", "400: el motivo es obligatorio"],
                ["Rehabilitar Cruz Roja", "administrador", "200, queda habilitada"],
                ["Volver a suspender Cruz Roja", "administrador", "200, queda suspendida"],
                [
                    "Historial de habilitación de Cruz Roja",
                    "admin o sistema",
                    "Más de dos registros; el último es la suspensión",
                ],
            ],
        ),
        carpeta(
            "6.5 Gestión de organizaciones (3 requests, 3 aserciones)",
            "Sobre la ONG creada en la carpeta 5, con el ítem y la certificación guardados en "
            "la carpeta 3.",
            [
                ["Cargar ítem al inventario", "administrador", "201 con 100 unidades del ítem"],
                ["Cargar certificación y nivel", "administrador", "201 con nivel alta"],
                [
                    "Nivel de certificación inválido",
                    "administrador",
                    "400: ALTO no es un nivel (son baja, media, alta y crítica)",
                ],
            ],
        ),
        carpeta(
            "6.6 Compromiso, liberación y concurrencia (8 requests, 13 aserciones)",
            "Usa una emergencia nueva (UUID) en cada corrida, sobre Cruz Solidaria (30-65432198-7) "
            "y los Scouts (30-99999999-6). Se corre completa: el compromiso crea lo que liberan "
            "los requests siguientes.",
            [
                [
                    "Compromiso",
                    "sistema",
                    "201: 100 L de agua (consumible) y 2 paramédicos comprometidos",
                ],
                ["Validar restricciones - OK", "sistema", "200 con valido = true, sin tocar nada"],
                [
                    "Validar restricciones - Stock insuficiente",
                    "sistema",
                    "200 con valido = false y motivo stock_insuficiente",
                ],
                [
                    "Validar restricciones - Consumible cantidad extrema",
                    "sistema",
                    "200 con valido = true: los consumibles no validan stock",
                ],
                [
                    "Reintento de compromiso (idempotencia)",
                    "sistema",
                    "200 con repetido = true; no descuenta otra vez",
                ],
                [
                    "Liberación por ONG",
                    "sistema",
                    "200; el compromiso de Cruz Solidaria queda LIBERADO y los paramédicos vuelven",
                ],
                [
                    "Finalización global",
                    "sistema",
                    "200 y la emergencia queda cerrada (proyecto_cerrado = true)",
                ],
                [
                    "Concurrencia",
                    "sistema",
                    "Dos compromisos simultáneos por más de la mitad de los voluntarios: uno gana "
                    "(201) y el otro se rechaza (422); después se libera el ganador",
                ],
            ],
        ),
        carpeta(
            "6.7 Evaluación de ofertas (4 requests, 4 aserciones)",
            "Evalúa ofertas consolidadas como las que manda Bonita. La evaluación <b>modifica "
            "datos</b>: compromete los aportes no consumibles aceptados (sección 7).",
            [
                [
                    "Caso principal o apoyo",
                    "sistema",
                    "Paramédicos de Cruz Solidaria: principal y comprometidos. Frazadas de Manos "
                    "Unidas: apoyo (consumible, no se compromete)",
                ],
                [
                    "Caso organización no registrada",
                    "sistema",
                    "rechazada: el CUIT no está en el padrón",
                ],
                [
                    "Caso rechazo por cantidad insuficiente",
                    "sistema",
                    "rechazada con el disponible en el motivo. Un pre-request lee el stock real y "
                    "pide uno más",
                ],
                [
                    "Caso rechazo por falta de certificación",
                    "sistema",
                    "rechazada: Cruz Solidaria no tiene certificación de abrigo",
                ],
            ],
        ),
    ]


def estado_y_datos() -> list:
    return [
        parrafo("7. Qué queda en la base después de una corrida", "h1"),
        parrafo(
            "La colección se puede correr muchas veces sobre la misma base. Esto es lo que "
            "modifica y cómo queda:"
        ),
        tabla(
            ["Qué modifica", "Cómo queda"],
            [
                [
                    "Estado de Cruz Roja",
                    "Se rehabilita y se vuelve a suspender: termina "
                    "suspendida, como en los datos de demostración",
                ],
                [
                    "ONG nueva (carpetas 5 y 4)",
                    "Queda una ONG de prueba por corrida, con CUIT "
                    "aleatorio, habilitada, con 100 unidades de un ítem y una certificación",
                ],
                [
                    "Compromiso de la carpeta 6",
                    "Se libera por ONG y se finaliza: los paramédicos vuelven al inventario",
                ],
                [
                    "Prueba de concurrencia",
                    "El compromiso ganador se libera al final: los "
                    "voluntarios de los Scouts vuelven a su cantidad",
                ],
                ["Validaciones (dry-run)", "No modifican nada"],
                [
                    "Evaluación (carpeta 7)",
                    "La primera corrida deja comprometidos 2 paramédicos "
                    "de Cruz Solidaria en la emergencia fija …000000000014; las siguientes repiten "
                    "ese compromiso sin sumar otro. Los otros tres casos no comprometen nada",
                ],
            ],
            [5.0, 12.0],
        ),
        parrafo("8. Datos de demostración que usan las pruebas", "h1"),
        parrafo(
            "Los carga flask seed en cada arranque de la API (también en cada deploy de Render). "
            "El seed repone el stock que quedó por debajo de su cantidad inicial, pero nunca lo "
            "baja ni cambia el estado de una organización que ya existía: la base compartida "
            "puede tener otros valores, y la colección no depende de ellos."
        ),
        tabla(
            ["CUIT", "Organización", "Estado inicial", "Uso en las pruebas"],
            [
                [
                    "30-65432198-7",
                    "Cruz Solidaria",
                    "habilitada",
                    "Compromiso, liberación por ONG y evaluación (10 paramédicos, 1000 L de agua, "
                    "certificación sanitaria alta)",
                ],
                [
                    "30-65432199-5",
                    "Manos Unidas",
                    "habilitada",
                    "Evaluación: frazadas como apoyo (certificación de abrigo media)",
                ],
                [
                    "30-99999999-4",
                    "Cruz Roja Argentina - Filial Bahía Blanca",
                    "suspendida",
                    "Consulta de una ONG suspendida, habilitación e historial",
                ],
                [
                    "30-99999999-6",
                    "Grupo Scouts de Pergamino",
                    "habilitada",
                    "Concurrencia (40 voluntarios generales)",
                ],
                ["30-00000000-0", "(no existe)", "—", "Evaluación: organización no registrada"],
            ],
            [2.8, 4.4, 2.4, 7.4],
        ),
        Spacer(1, 6),
        tabla(
            ["Código", "Recurso", "Consumible", "Dónde aparece"],
            [
                ["RSR-PARAMEDICOS", "Paramédicos", "No", "Compromiso, validación y evaluación"],
                ["RSR-VOLUNTARIOS_GENERALES", "Voluntarios generales", "No", "Concurrencia"],
                [
                    "RSR-AGUA_POTABLE_ENVASADA",
                    "Agua potable envasada",
                    "Sí",
                    "Compromiso y validación con cantidad extrema",
                ],
                ["RSR-FRAZADAS", "Frazadas", "Sí", "Evaluación (apoyo y sin certificación)"],
                ["RSR-ENFERMEROS", "Enfermeros", "No", "Evaluación (organización no registrada)"],
            ],
            [5.4, 3.6, 2.5, 5.5],
        ),
        parrafo(
            "El catálogo completo tiene los mismos 46 ítems que la aplicación web. Sus ids y los "
            "de las certificaciones son fijos (UUIDv5 de su código o de su nombre y tipo), así que "
            "valen en cualquier base. Los niveles de certificación son baja, media, alta y crítica."
        ),
    ]


def problemas() -> list:
    items = [
        "<b>El primer request tarda o da timeout (Render).</b> El plan gratuito duerme el "
        "servicio a los 15 minutos sin uso y tarda cerca de un minuto en despertar. Abrir "
        f"{URL_RENDER}/health hasta que responda y volver a correr.",
        "<b>/health responde 503.</b> La base de Supabase se pausó por inactividad: hay que "
        "reactivarla desde su dashboard (runbook en el README).",
        "<b>Los logins dan 401.</b> Las credenciales del entorno no son las de esa base. "
        "Revisar contrasenaAdmin y clientSecretBonita (sección 3.3).",
        "<b>Token vencido.</b> Los tokens duran 60 minutos; si la corrida se interrumpe mucho "
        "tiempo, volver a correr desde el principio.",
        "<b>Una carpeta suelta falla.</b> Depende de variables que generan las anteriores. Correr "
        "siempre la colección completa.",
        "<b>La evaluación responde 409.</b> Alguien finalizó la emergencia fija de esos ejemplos "
        "(…000000000014). Cambiar el emergencia_id de esos requests por un UUID nuevo.",
        "<b>La prueba de concurrencia no es de carga.</b> Manda dos pedidos simultáneos para "
        "mostrar que nunca se compromete más stock del que hay.",
    ]
    return [parrafo("9. Consideraciones y problemas frecuentes", "h1"), lista(items)]


def numerar_pagina(lienzo, documento) -> None:
    if documento.page == 1:
        return
    lienzo.saveState()
    lienzo.setStrokeColor(GRIS_LINEA)
    lienzo.line(2 * cm, 1.6 * cm, A4[0] - 2 * cm, 1.6 * cm)
    lienzo.setFont("Helvetica", 8)
    lienzo.setFillColor(colors.HexColor("#666666"))
    lienzo.drawCentredString(A4[0] / 2, 1.1 * cm, f"Pág. {documento.page}")
    lienzo.restoreState()


def generar() -> None:
    documento = SimpleDocTemplate(
        str(DESTINO),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.2 * cm,
        title="Manual de pruebas - Colección Postman",
        author="RescueSync",
        subject="API del Sistema Nacional",
    )
    contenido = (
        portada()
        + introduccion()
        + variables_y_orden()
        + detalle_por_carpeta()
        + estado_y_datos()
        + problemas()
    )
    documento.build(contenido, onFirstPage=numerar_pagina, onLaterPages=numerar_pagina)
    print(f"Manual generado en {DESTINO}")


if __name__ == "__main__":
    generar()
