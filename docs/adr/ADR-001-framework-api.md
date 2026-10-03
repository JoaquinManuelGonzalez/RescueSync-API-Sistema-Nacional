# ADR-001: Framework de la API

- Estado: Aceptado
- Fecha: 2026-10-03
- Reemplaza a: —
- Reemplazado por: —

## Contexto

La API del Sistema Nacional es un servicio REST sin interfaz. Su único consumidor es el motor
de Bonita, que la invoca mediante conectores REST desde el proceso de gestión de emergencias;
la aplicación web nunca la llama directamente. Tiene que responder habilitaciones de ONGs,
reservar y comprometer recursos con control de concurrencia en PostgreSQL, y quedar
dockerizada y desplegada en un PaaS.

El equipo ya construyó la aplicación web en Flask (ADR-002 de ese repositorio) y tiene código
transversal probado (configuración fail-fast, logging JSON con correlación, envelope de
errores, endpoint de salud, migraciones con Flask-Migrate). La guía de la cátedra para el
trabajo de cloud usa Flask + Gunicorn como ejemplo de servicio web desplegado en Render. El
ADR-002 de la aplicación web menciona FastAPI como una opción natural para una API pura.

## Decisión

Se usa **Flask 3.1.3** servido con **Gunicorn 26.2.0**, con el mismo stack de persistencia que
la aplicación web (Flask-SQLAlchemy, SQLAlchemy 2, Alembic vía Flask-Migrate, psycopg 3).

El motivo principal es la reutilización: los módulos `core` de la aplicación web se copian casi
sin cambios, el equipo no aprende un segundo framework en mitad del cuatrimestre, y las dos
piezas Python del sistema comparten convenciones, contratos y herramientas. El ejemplo de la
cátedra (Flask + Gunicorn en Render) queda cubierto tal cual.

### Versión fijada

| Tecnología | Versión | Archivo del repositorio donde se fija |
|---|---|---|
| Flask | 3.1.3 | `pyproject.toml` / `uv.lock` |
| Gunicorn | 26.2.0 | `pyproject.toml` / `uv.lock` |
| Flask-SQLAlchemy | 3.1.1 | `pyproject.toml` / `uv.lock` |
| Flask-Migrate | 4.1.0 | `pyproject.toml` / `uv.lock` |

### Alternativas consideradas

| Alternativa | A favor | En contra | Motivo del descarte |
|---|---|---|---|
| FastAPI + Uvicorn | OpenAPI/Swagger automático, validación con Pydantic, async | Hay que reescribir configuración, logging, errores y salud; Alembic sin la integración de Flask-Migrate; segundo framework para el equipo | El beneficio no compensa perder la reutilización ni el costo de aprendizaje en la entrega |
| Django + DRF | Admin y ORM integrados | Pesado para un servicio chico; ORM distinto al de la aplicación web | Rompe la homogeneidad del stack |

## Consecuencias

### Positivas

- Configuración, logs, errores y salud idénticos en la aplicación web y en la API.
- Mismo flujo de migraciones (`flask db migrate` / `flask db upgrade`) en los dos repositorios.
- Alineado con la guía de la cátedra.

### Negativas

- No hay documentación OpenAPI automática; si Bonita o la cátedra la necesitan, se escribe a
  mano (o con una extensión) en una épica posterior.
- La validación de los cuerpos JSON se hace a mano o con una librería que se agregue después.

### Qué nos obliga a hacer

- Toda respuesta de error usa el envelope del contrato (`docs/contratos/errores.md`).
- Los módulos de dominio siguen el esqueleto `rutas.py` / `servicios.py` / `modelos.py`.
