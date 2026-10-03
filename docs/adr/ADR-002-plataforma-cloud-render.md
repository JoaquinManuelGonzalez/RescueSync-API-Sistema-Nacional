# ADR-002: Plataforma de despliegue en la nube

- Estado: Aceptado
- Fecha: 2026-10-03
- Reemplaza a: —
- Reemplazado por: —

## Contexto

La épica "Dockerización y despliegue en la nube" exige que la API quede publicada en una URL
pública por HTTPS, con su base PostgreSQL administrada, secretos fuera del repositorio,
migraciones automáticas y despliegue automático desde la rama de trabajo. El consumidor es el
motor de Bonita, que corre en las máquinas del equipo y llega a la API por internet.

La guía de la cátedra propone fly.io o Render como PaaS. El equipo no tiene presupuesto, por
lo que se busca un plan gratuito, aceptando sus limitaciones mientras sean manejables para un
trabajo académico.

## Decisión

Se despliega en **Render**, plan **Free**, con toda la infraestructura declarada como código
en `render.yaml` (Render Blueprint):

- Un **web service** con `runtime: docker`, construido desde el `Dockerfile` del repositorio.
- Una **Render Postgres 18** administrada, conectada por la URL interna (red privada).
- Región `virginia` para los dos recursos (la URL interna exige la misma región).
- `autoDeployTrigger: checksPass`: solo se despliega un commit si pasa el CI de GitHub Actions.
- `healthCheckPath: /health` para los deploys sin downtime y el reinicio ante fallas.
- `SECRET_KEY` generada por Render (`generateValue`), `DATABASE_URL` tomada de la base
  (`fromDatabase`), y cualquier secreto futuro con `sync: false` cargado en el dashboard.

Render construye la imagen directo desde el Dockerfile (ventaja que destaca la cátedra), emite
y renueva el certificado TLS, y la URL `*.onrender.com` queda publicada por HTTPS sin
configuración extra.

### Versión fijada

| Tecnología | Versión | Archivo del repositorio donde se fija |
|---|---|---|
| Render Postgres | 18 (`postgresMajorVersion: "18"`) | `render.yaml` |
| Plan de cómputo | `free` (web y base) | `render.yaml` |
| Región | `virginia` | `render.yaml` |

### Alternativas consideradas

| Alternativa | A favor | En contra | Motivo del descarte |
|---|---|---|---|
| fly.io | Propuesto por la cátedra; CLI completa | Flujo centrado en la CLI (`flyctl launch/deploy`) en vez de declarativo desde el repo | Render ofrece web + Postgres gratis declarados en un solo `render.yaml` y despliegue directo desde el Dockerfile |
| Render web + Supabase (Postgres) | La base gratuita de Supabase no expira a los 30 días | Una cuenta y un proveedor más; conexión por internet en vez de red privada | **Queda abierta para charlar con el equipo** si la expiración de la base free de Render molesta |
| Plan pago de Render | Sin spin-down ni expiración, pre-deploy command | Costo mensual | Sin presupuesto |

## Consecuencias

### Positivas

- La infraestructura es reproducible y versionada: crear el entorno de cero es
  "New → Blueprint" sobre este repositorio.
- HTTPS, certificados y deploys sin downtime gestionados por la plataforma.
- El CI actúa como compuerta: un commit roto nunca llega a producción.

### Negativas (límites del plan Free, según la documentación de Render)

- El web service **se duerme a los 15 minutos sin tráfico** y tarda alrededor de un minuto en
  despertar. El primer llamado de Bonita después de un período ocioso puede superar el timeout
  de su conector.
- La **Postgres free expira a los 30 días** de creada (con 14 días de gracia antes de ser
  borrada), tiene 1 GB, no tiene backups y solo puede haber una por workspace.
- Sin pre-deploy command, sin Shell y sin one-off jobs: las migraciones tienen que correr dentro
  del propio contenedor (ver ADR-003).
- El workspace Hobby admite un solo miembro: la cuenta de Render queda a nombre de un
  integrante, que comparte los logs con el resto.
- 750 horas de instancia gratuita por mes por workspace.

### Qué nos obliga a hacer

- Mantener `render.yaml` como única fuente de verdad de la infraestructura.
- Mantener el runbook de recreación de la base en el README y agendar su expiración.
- Despertar el servicio (`GET /health`) antes de cada demo con Bonita.
- No referenciar secretos como `ARG` en el Dockerfile: Render convierte las variables de
  entorno en build args.
