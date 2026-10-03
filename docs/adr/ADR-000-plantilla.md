# ADR-XXX: Título de la decisión

- Estado: Propuesto | Aceptado | Reemplazado por ADR-XXX | Obsoleto
- Fecha: AAAA-MM-DD
- Reemplaza a: — (o `ADR-XXX`)
- Reemplazado por: — (o `ADR-XXX`)

Esta es la plantilla base para redactar cualquier Architecture Decision Record
(ADR) en la API del Sistema Nacional de RescueSync. Copiarla como punto de partida al abrir una decisión
nueva y completar cada sección; no dejar secciones vacías ni cambiar el orden.
El número de ADR se pide en `docs/adr/README.md` antes de nombrar el archivo,
para evitar colisiones entre integrantes que trabajan en paralelo.

## Contexto

Qué problema o disyuntiva motiva esta decisión. Qué fuerzas están en juego
(requisitos del enunciado, restricciones de tiempo, tamaño del equipo,
conocimiento previo, integraciones externas). Qué pasa si no se decide nada.
Esta sección describe la situación, no la solución: alguien que no participó
de la discusión tiene que poder entender por qué hizo falta este ADR.

## Decisión

Qué se decidió, en una o dos oraciones directas, seguido del razonamiento
que la sostiene. Si la decisión involucra una o más tecnologías concretas,
nombrarlas acá con su versión exacta y completar la tabla de abajo.

### Versión fijada

| Tecnología | Versión | Archivo del repositorio donde se fija |
|---|---|---|
| `<nombre>` | `<version>` | `<ruta/al/archivo>` |

### Alternativas consideradas

| Alternativa | A favor | En contra | Motivo del descarte |
|---|---|---|---|
| `<opcion>` | `<ventajas>` | `<desventajas>` | `<por que no se eligio>` |

## Consecuencias

### Positivas

- Qué gana el equipo o el proyecto con esta decisión.

### Negativas

- Qué costo, riesgo o limitación se acepta a cambio.

### Qué nos obliga a hacer

- Qué práctica, convención o chequeo queda obligatorio de ahora en más
  como resultado directo de esta decisión.

---

Recordatorio de uso: una vez que un ADR pasa a `Aceptado` es inmutable.
Si la decisión cambia más adelante, no se edita este documento: se escribe
un ADR nuevo y en este solo se actualiza el campo `Estado` (a
`Reemplazado por ADR-XXX`) y el campo `Reemplazado por`. El detalle completo
del procedimiento está en `docs/adr/README.md`.
