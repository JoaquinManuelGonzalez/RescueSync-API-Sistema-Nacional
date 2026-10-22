"""Ejemplos de request y respuestas para evaluar ofertas desde Swagger."""

EJEMPLO_EVALUACION_PRINCIPAL_Y_APOYO = {
    "emergencia_id": 14,
    "nivel_gravedad": "ALTA",
    "ofertas": [
        {
            "fecha_creacion": "2026-10-16T14:40:44Z",
            "items": [
                {
                    "aportes": [
                        {
                            "cantidad": 2,
                            "identificador_nacional": "30-65432198-7",
                            "organizacion_id": 6,
                        }
                    ],
                    "cantidad_total": 2,
                    "codigo_recurso": "RSR-PARAMEDICOS",
                    "lote_item_id": 10,
                    "tipo_recurso": "personal_medico",
                    "unidad": "personas",
                },
                {
                    "aportes": [
                        {
                            "cantidad": 2,
                            "identificador_nacional": "30-65432199-5",
                            "organizacion_id": 7,
                        }
                    ],
                    "cantidad_total": 2,
                    "codigo_recurso": "RSR-FRAZADAS",
                    "lote_item_id": 11,
                    "tipo_recurso": "abrigo",
                    "unidad": "unidades",
                },
            ],
            "oferta_id": 7,
            "organizaciones": [
                {
                    "id": 6,
                    "identificador_nacional": "30-65432198-7",
                    "nombre": "Cruz Solidaria",
                    "rol": "aportante",
                },
                {
                    "id": 7,
                    "identificador_nacional": "30-65432199-5",
                    "nombre": "Manos Unidas",
                    "rol": "aportante",
                },
            ],
            "version": 2,
        }
    ],
}

EJEMPLO_RESPUESTA_PRINCIPAL_Y_APOYO = {
    "emergencia_id": 14,
    "nivel_gravedad": "ALTA",
    "ofertas": [
        {
            "fecha_creacion": "2026-10-16T14:40:44+00:00",
            "oferta_id": 7,
            "organizaciones": EJEMPLO_EVALUACION_PRINCIPAL_Y_APOYO["ofertas"][0][
                "organizaciones"
            ],
            "items": [
                {
                    "aportes": [
                        {
                            "cantidad": 2,
                            "identificador_nacional": "30-65432198-7",
                            "organizacion_id": 6,
                            "certificacion_encontrada": True,
                            "nivel_riesgo_permitido": "alta",
                            "clasificacion": "principal",
                            "motivo": "La certificación alcanza el nivel de gravedad requerido.",
                            "compromiso_registrado": True,
                        }
                    ],
                    "cantidad_total": 2,
                    "codigo_recurso": "RSR-PARAMEDICOS",
                    "lote_item_id": 10,
                    "tipo_recurso": "personal_medico",
                    "unidad": "personas",
                    "consumible": False,
                },
                {
                    "aportes": [
                        {
                            "cantidad": 2,
                            "identificador_nacional": "30-65432199-5",
                            "organizacion_id": 7,
                            "certificacion_encontrada": True,
                            "nivel_riesgo_permitido": "media",
                            "clasificacion": "apoyo",
                            "motivo": (
                                "La certificación tiene un nivel menor al requerido; "
                                "se asigna como apoyo."
                            ),
                            "compromiso_registrado": True,
                        }
                    ],
                    "cantidad_total": 2,
                    "codigo_recurso": "RSR-FRAZADAS",
                    "lote_item_id": 11,
                    "tipo_recurso": "abrigo",
                    "unidad": "unidades",
                    "consumible": True,
                },
            ],
        }
    ],
}

EJEMPLO_RESPUESTA_ORGANIZACION_NO_REGISTRADA = {
    "emergencia_id": 15,
    "nivel_gravedad": "ALTA",
    "ofertas": [
        {
            "fecha_creacion": "2026-10-20T12:00:00+00:00",
            "oferta_id": 8,
            "organizaciones": [
                {
                    "id": 6,
                    "identificador_nacional": "30-65432198-7",
                    "nombre": "Cruz Solidaria",
                    "rol": "aportante",
                }
            ],
            "items": [
                {
                    "aportes": [
                        {
                            "cantidad": 1,
                            "identificador_nacional": "30-00000000-0",
                            "organizacion_id": 999,
                            "certificacion_encontrada": False,
                            "nivel_riesgo_permitido": None,
                            "clasificacion": "rechazada",
                            "motivo": "La organización no está registrada en el padrón nacional.",
                            "compromiso_registrado": False,
                        }
                    ],
                    "cantidad_total": 1,
                    "codigo_recurso": "RSR-ENFERMEROS",
                    "lote_item_id": 11,
                    "tipo_recurso": "personal_medico",
                    "unidad": "personas",
                    "consumible": False,
                }
            ],
        }
    ],
}

EJEMPLO_RESPUESTA_STOCK_INSUFICIENTE = {
    "emergencia_id": 16,
    "nivel_gravedad": "ALTA",
    "ofertas": [
        {
            "fecha_creacion": "2026-10-20T17:00:00+00:00",
            "oferta_id": 9,
            "organizaciones": [
                {
                    "id": 6,
                    "identificador_nacional": "30-65432198-7",
                    "nombre": "Cruz Solidaria",
                    "rol": "aportante",
                }
            ],
            "items": [
                {
                    "aportes": [
                        {
                            "cantidad": 11,
                            "identificador_nacional": "30-65432198-7",
                            "organizacion_id": 6,
                            "certificacion_encontrada": True,
                            "nivel_riesgo_permitido": "alta",
                            "clasificacion": "rechazada",
                            "motivo": (
                                "La disponibilidad del ítem no alcanza la cantidad ofertada "
                                "(10 disponible)."
                            ),
                            "compromiso_registrado": False,
                        }
                    ],
                    "cantidad_total": 11,
                    "codigo_recurso": "RSR-PARAMEDICOS",
                    "lote_item_id": 12,
                    "tipo_recurso": "personal_medico",
                    "unidad": "personas",
                    "consumible": False,
                }
            ],
        }
    ],
}

EJEMPLO_RESPUESTA_SIN_CERTIFICACION = {
    "emergencia_id": 17,
    "nivel_gravedad": "ALTA",
    "ofertas": [
        {
            "fecha_creacion": "2026-10-20T17:00:00+00:00",
            "oferta_id": 10,
            "organizaciones": [
                {
                    "id": 6,
                    "identificador_nacional": "30-65432198-7",
                    "nombre": "Cruz Solidaria",
                    "rol": "aportante",
                }
            ],
            "items": [
                {
                    "aportes": [
                        {
                            "cantidad": 1,
                            "identificador_nacional": "30-65432198-7",
                            "organizacion_id": 6,
                            "certificacion_encontrada": False,
                            "nivel_riesgo_permitido": None,
                            "clasificacion": "rechazada",
                            "motivo": "No existe certificación para la capacidad del ítem.",
                            "compromiso_registrado": False,
                        }
                    ],
                    "cantidad_total": 1,
                    "codigo_recurso": "RSR-FRAZADAS",
                    "lote_item_id": 13,
                    "tipo_recurso": "abrigo",
                    "unidad": "unidades",
                    "consumible": True,
                }
            ],
        }
    ],
}

EJEMPLOS_RESPUESTA_EVALUACION = {
    "ok_principal_y_apoyo": {
        "summary": "OK: caso principal y apoyo",
        "value": EJEMPLO_RESPUESTA_PRINCIPAL_Y_APOYO,
    },
    "rechazo_organizacion_no_registrada": {
        "summary": "Rechazo: organización no registrada",
        "value": EJEMPLO_RESPUESTA_ORGANIZACION_NO_REGISTRADA,
    },
    "rechazo_stock_insuficiente": {
        "summary": "Rechazo: cantidad insuficiente",
        "value": EJEMPLO_RESPUESTA_STOCK_INSUFICIENTE,
    },
    "rechazo_sin_certificacion": {
        "summary": "Rechazo: falta de certificación",
        "value": EJEMPLO_RESPUESTA_SIN_CERTIFICACION,
    },
}
