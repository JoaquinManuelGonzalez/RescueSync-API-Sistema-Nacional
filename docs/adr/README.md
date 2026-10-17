# Registro de decisiones de arquitectura (ADR)

Un ADR (Architecture Decision Record) deja por escrito una decisión de arquitectura: qué se
decidió, en qué contexto, qué alternativas se descartaron y qué consecuencias trae. Este
repositorio sigue exactamente el mismo procedimiento que la aplicación web de RescueSync
(`RescueSync-Web-App/docs/adr/README.md`): plantilla obligatoria, numeración correlativa que
nunca se reutiliza, y regla de inmutabilidad de los ADRs aceptados.

Las decisiones que esta API hereda sin cambios de la aplicación web (Python 3.14, SQLAlchemy 2
con Flask-SQLAlchemy y Alembic, PostgreSQL, contrato de errores, logs y configuración, gestión
de dependencias con uv) **no se vuelven a escribir acá**: rigen los ADR-002, 003, 004, 006 y
008 de la aplicación web. Este registro solo contiene lo que es propio de la API.

Todo ADR nuevo parte de la plantilla [`ADR-000-plantilla.md`](./ADR-000-plantilla.md).

## Índice de ADRs

| # | Título | Estado | Fecha | Documento |
|---|---|---|---|---|
| 000 | Plantilla de ADR | — | — | [ADR-000-plantilla.md](./ADR-000-plantilla.md) |
| 001 | Framework de la API | Aceptado | 2026-10-03 | [ADR-001-framework-api.md](./ADR-001-framework-api.md) |
| 002 | Plataforma de despliegue en la nube | Reemplazado parcialmente por ADR-004 | 2026-10-03 | [ADR-002-plataforma-cloud-render.md](./ADR-002-plataforma-cloud-render.md) |
| 003 | Contenedores y ejecución de migraciones | Reemplazado parcialmente por ADR-004 | 2026-10-03 | [ADR-003-contenedores-y-migraciones.md](./ADR-003-contenedores-y-migraciones.md) |
| 004 | Base de datos administrada en Supabase | Aceptado | 2026-10-05 | [ADR-004-base-de-datos-supabase.md](./ADR-004-base-de-datos-supabase.md) |
| 005 | Autenticación JWT con cuentas de cliente | Aceptado | 2026-10-17 | [ADR-005-autenticacion-jwt-y-cuentas-de-cliente.md](./ADR-005-autenticacion-jwt-y-cuentas-de-cliente.md) |

El siguiente ADR usa el número `006`.

## Ciclo de vida

```
Propuesto → Aceptado → Reemplazado por ADR-XXX
                     └→ Obsoleto
```

Un ADR `Aceptado` **nunca se edita**: si la decisión cambia se escribe un ADR nuevo y en el
anterior solo se actualizan los campos `Estado` y `Reemplazado por`. El detalle del
procedimiento (incluida la enmienda parcial) está en el README de ADRs de la aplicación web.
