## HU que resuelve

<!-- Ejemplo: HU-SN-03 — Dockerización de la API -->

## Qué cambia y por qué

<!-- Descripción breve del cambio y la motivación / problema que resuelve. -->

## Cómo probarlo

<!-- Pasos concretos para que quien revisa pueda verificar el cambio localmente. -->

1.
2.
3.

## Checklist

- [ ] `uv run ruff format --check .`, `uv run ruff check .` y `uv run pytest` pasan sin errores.
- [ ] El CI de GitHub Actions (jobs `calidad` e `imagen`) está en verde.
- [ ] `docker compose up -d --build` levanta y `GET /health` responde 200.
- [ ] Se respeta la convención de nombres de `CONTRIBUTING.md` (paquetes, clases, funciones,
      tablas, columnas, rutas, ramas).
- [ ] Los commits siguen Conventional Commits y referencian la HU (`(HU-XX)`).
- [ ] Si se agregó una migración, se probó `flask db upgrade` y `downgrade` contra PostgreSQL (no
      solo SQLite) y `flask db check` no encuentra diferencias. Si transforma o borra datos, se
      probó con una copia de Supabase y se aclara en el PR: Supabase Free no tiene backups.
- [ ] Las tablas y foráneas nuevas usan UUID (`Uuid`, `default=nuevo_id`); las rutas con ids,
      `<uuid:...>` (CONTRIBUTING, "Identificadores").
- [ ] Si se agregó una variable de entorno: está en `.env.example`, en
      `docs/contratos/configuracion.md`, en la tabla del README y, si aplica, en `render.yaml`.
- [ ] Si cambia un endpoint: están al día su contrato en `docs/contratos/`, los ejemplos de
      Swagger, la tabla de endpoints del README y la matriz de permisos. Si cambia la colección
      Postman, se corrió dos veces seguidas sobre la misma base y se regeneró el manual.
- [ ] Si el cambio es incompatible con la web o con Bonita, los commits llevan `BREAKING CHANGE:`
      y el PR enlaza los de los otros repositorios, para mergearlos juntos.
- [ ] La documentación relacionada (README, ADR, contratos) está actualizada si el cambio la
      afecta.
- [ ] No se commitean secretos, archivos `.env` ni credenciales.
