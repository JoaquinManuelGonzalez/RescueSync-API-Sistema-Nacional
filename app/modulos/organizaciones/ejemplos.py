EJEMPLO_ONGS_HABILITADAS = {
    "elementos": [
        {
            "certificaciones": [
                {
                    "id": 0,
                    "nivel_certificacion": "alta",
                    "nombre": "Certificación de atención sanitaria",
                },
                {
                    "id": 1,
                    "nivel_certificacion": "alta",
                    "nombre": "Certificación de abastecimiento de agua",
                },
            ],
            "cuit": "30-99999999-7",
            "id": 6,
            "mail_contacto": "solidaria@rescuesync.ej",
            "nombre": "La Solidaria",
        },
        {
            "certificaciones": [
                {
                    "id": 2,
                    "nivel_certificacion": "alta",
                    "nombre": "Certificación de distribución de alimentos",
                },
            ],
            "cuit": "30-88888888-6",
            "id": 10,
            "mail_contacto": "federada@rescuesync.ej",
            "nombre": "La Federada",
        },
    ],
    "pagina": 1,
    "por_pagina": 20,
    "total": 2,
}

EJEMPLO_CATALOGO_CERTIFICACIONES = {
    "elementos": [
        {"id": 0, "nombre": "Certificación de abastecimiento de agua", "tipo": "agua"},
        {
            "id": 1,
            "nombre": "Habilitación nacional para el transporte de productos alimenticios",
            "tipo": "alimentos",
        },
    ],
    "pagina": 1,
    "por_pagina": 20,
    "total": 2,
}

EJEMPLO_RECURSOS_DISPONIBLES = {
    "elementos": [
        {
            "comprometido": 0,
            "consumible": True,
            "disponible": 100,
            "id": 0,
            "nombre": "Botellas de agua",
            "tipo": "agua",
            "total": 100,
            "unidad_medida": "unidades",
        },
        {
            "comprometido": 1,
            "consumible": False,
            "disponible": 19,
            "id": 1,
            "nombre": "Enfermeros",
            "tipo": "personal_medico",
            "total": 20,
            "unidad_medida": "personas",
        },
    ],
    "pagina": 1,
    "por_pagina": 20,
    "total": 2,
}

EJEMPLO_DISPONIBILIDAD_ONG = {
    "elementos": [
        {
            "comprometido": 0,
            "consumible": False,
            "disponible": 10,
            "id": 2,
            "nombre": "Paramédicos",
            "tipo": "personal_medico",
            "total": 10,
            "unidad_medida": "personas",
        },
        {
            "comprometido": 0,
            "consumible": True,
            "disponible": 100,
            "id": 18,
            "nombre": "Raciones de alimento no perecedero",
            "tipo": "alimentos",
            "total": 100,
            "unidad_medida": "raciones",
        },
    ],
    "pagina": 1,
    "por_pagina": 20,
    "total": 2,
}

EJEMPLO_CARGA_DE_INVENTARIO = {
    "cantidad_disponible": 1,
    "id": 29,
    "item_id": 13,
    "item_nombre": "Pañales para adulto",
}

EJEMPLO_CARGA_DE_CERTIFICACION = {
    "certificacion_id": 6,
    "certificacion_nombre": "Certificación de respuesta ante emergencias",
    "fecha_emision": "2026-10-26T20:00:00.000+00:00",
    "id": 14,
    "nivel_certificacion": "baja",
}

EJEMPLO_ERROR_400_CAMPOS_INVALIDOS = {
    "error": {
        "codigo": "SOLICITUD_INVALIDA",
        "detalle": {"query": {"certificacion_id": ["Debe ser un número entero."]}},
        "id_correlacion": "e7e3910...",
        "mensaje": "La solicitud tiene campos inválidos o incompletos.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_ERROR_400_INVALID_JSON = {
    "error": {
        "codigo": "SOLICITUD_INVALIDA",
        "detalle": {"json": ["Invalid JSON body."]},
        "id_correlacion": "e7e3910...",
        "mensaje": "La solicitud tiene campos inválidos o incompletos.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_ERROR_400_CUIT = {
    "error": {
        "codigo": "SOLICITUD_INVALIDA",
        "detalle": {"cuit": "00000"},
        "id_correlacion": "e7e3910...",
        "mensaje": "El CUIT tiene que tener 11 dígitos,\
        con o sin guiones (por ejemplo 30-12345678-9).",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_ERROR_409_ITEM = {
    "error": {
        "codigo": "CONFLICTO_DE_ESTADO",
        "detalle": {"cuit": "30-99999999-7", "item_id": 0},
        "id_correlacion": "e7e3910...",
        "mensaje": "La organización ya tiene cargado ese ítem.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_ERROR_409_CERTIFICACION = {
    "error": {
        "codigo": "CONFLICTO_DE_ESTADO",
        "detalle": {"certificacion_id": 0, "cuit": "30-99999999-7"},
        "id_correlacion": "e7e3910...",
        "mensaje": "La organización ya tiene cargada esa certificación.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}


EJEMPLO_ALTA_ONG = {
    "id": 0,
    "cuit": "30-71555444-2",
    "nombre": "Red Solidaria Chascomús",
    "tipo": "ong",
    "mail_contacto": "contacto@redsolidaria.example",
    "telefono_contacto": "+54 2241 555-000",
    "estado_habilitacion": "pendiente",
    "habilitada": True,
    "motivo_estado": "string",
    "actualizada_en": "2026-10-21T21:43:42.744Z",
}

EJEMPLO_ERROR_409_ONG = {
    "error": {
        "codigo": "CONFLICTO_DE_ESTADO",
        "detalle": {
            "campo": "cuit",
            "cuit": "30-71555444-2",
            "estado_habilitacion": "pendiente",
        },
        "id_correlacion": "e7e3910...",
        "mensaje": "Ya existe una organización en el padrón con ese CUIT.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_HABILITACION_ONG = {
    "actualizada_en": "2026-10-26T20:00:00.00+00:00",
    "cuit": "30-99999999-5",
    "estado_habilitacion": "habilitada",
    "habilitada": True,
    "id": 0,
    "mail_contacto": "ongsolidaria@rescuesync.ej",
    "motivo_estado": "Estado inicial del padrón (datos de demostración).",
    "nombre": "La Solidaria",
    "telefono_contacto": None,
    "tipo": "ong",
}

EJEMPLO_ERROR_409_HABILITACION = {
    "error": {
        "codigo": "CONFLICTO_DE_ESTADO",
        "detalle": {
            "estado_actual": "suspendida",
            "estado_pedido": "suspendida",
            "transiciones_permitidas": ["habilitada"],
        },
        "id_correlacion": "e7e3910...",
        "mensaje": "La organización ya está suspendida.",
        "timestamp": "2026-10-21T21:57:34.164Z",
    }
}

EJEMPLO_CAMBIO_HABILITACION = {
    "actualizada_en": "2026-10-26T20:00:00.00+00:00",
    "cuit": "30-99999999-7",
    "estado_habilitacion": "suspendida",
    "habilitada": False,
    "id": 0,
    "mail_contacto": "ongsolidaria@rescuesync.ej",
    "motivo_estado": "Certificación sanitaria vencida.",
    "nombre": "La Solidaria",
    "telefono_contacto": None,
    "tipo": "ong",
}

EJEMPLO_ERROR_400 = {
    "error": {
        "codigo": "SOLICITUD_INVALIDA",
        "detalle": {"json": {"estado": ["Must be one of: pendiente, habilitada, suspendida."]}},
        "id_correlacion": "e7e3910...",
        "mensaje": "La solicitud tiene campos inválidos o incompletos.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}

EJEMPLO_ERROR_404_ONG = {
    "error": {
        "codigo": "RECURSO_NO_ENCONTRADO",
        "detalle": {"cuit": "30-11111111-9"},
        "id_correlacion": "e7e3910...",
        "mensaje": "No hay ninguna organización con ese CUIT en el padrón nacional.",
        "timestamp": "2026-10-26T20:00:00.000Z",
    }
}


EJEMPLO_HISTORIAL_HABILITACIONES = {
    "cuit": "30-99999999-7",
    "estado_actual": "habilitada",
    "registros": [
        {
            "caso_bonita": None,
            "cuenta": None,
            "estado_anterior": None,
            "estado_nuevo": "habilitada",
            "fecha": "2026-10-26T20:00:00.000000+00:00",
            "motivo": "Certificación sanitaria aprobada.",
            "usuario_bonita": None,
        },
        {
            "caso_bonita": None,
            "cuenta": None,
            "estado_anterior": "habilitada",
            "estado_nuevo": "suspendida",
            "fecha": "2026-11-26T20:00:00.000000+00:00",
            "motivo": "Certificación sanitaria vencida.",
            "usuario_bonita": None,
        },
        {
            "caso_bonita": None,
            "cuenta": None,
            "estado_anterior": "suspendida",
            "estado_nuevo": "habilitada",
            "fecha": "2026-12-26T20:00:00.000000+00:00",
            "motivo": "Certificación sanitaria renovada.",
            "usuario_bonita": None,
        },
    ],
}
