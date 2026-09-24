---
name: weekly-kpi-summary
description: Generate this week's Weekly Development Summary PPTX by orchestrating the project's cli-kpis CLI. Resolves the current week's Friday folder under .config/my-kpis/kpi-<YYYY-MM-DD>/, interviews the user for last_week, this_week, roadblocks, and key_objectives (suggesting the previous week's objectives as a default), validates the JSON, writes it, and runs `uv run main.py` to produce the .pptx.
---

# Weekly KPI Summary

Orquesta el CLI `cli-kpis` para producir el PPTX de resumen semanal de la semana actual.

## Cuándo usar esta skill
Cuando el usuario pida crear, actualizar o regenerar el resumen semanal / weekly summary / KPI semanal.

## Estructura del proyecto

```
<project>/
├── .config/
│   └── my-kpis/
│       └── kpi-<YYYY-MM-DD>/                       ← carpeta semanal (una por semana)
│           ├── weekly_summary_<YYYY-MM-DD>.json    (input)
│           └── weekly_summary_<YYYY-MM-DD>.pptx    (output)
├── main.py                                          ← CLI
├── template.pptx                                    ← template PowerPoint
└── .agents/skills/weekly-kpi-summary/               ← esta skill
    ├── SKILL.md
    └── template.json                                (JSON de referencia)
```

El CLI vive en la raíz del proyecto y se invoca con `uv run main.py <carpeta-semanal>`.

## Workflow

### 1. Resolver el viernes de la semana actual (ISO week)
- `today = date.today()`
- `days_ahead = (4 - today.weekday()) % 7` (weekday Python: lunes=0..domingo=6; viernes=4)
- `friday = today + timedelta(days=days_ahead)`
- **Anunciar el `friday` resuelto al usuario antes de seguir.**

### 2. Resolver la carpeta destino
- Carpeta semanal: `<project>/.config/my-kpis/kpi-<friday>/`
- JSON destino: `<carpeta>/weekly_summary_<friday>.json`
- PPTX destino: `<carpeta>/weekly_summary_<friday>.pptx`
- Crear la carpeta si no existe.

### 3. Buscar objetivos de la semana anterior
- `prev_friday = friday - timedelta(days=7)`
- `prev_json = .config/my-kpis/kpi-<prev_friday>/weekly_summary_<prev_friday>.json`
- Si existe, leer su array `key_objectives` y usarlos como **sugerencias** para esta semana.
- Si no existe, saltear la sugerencia y preguntar directo.

### 4. Cargar JSON existente (si ya hay uno esta semana)
- Si `weekly_summary_<friday>.json` existe, leerlo como punto de partida.
- Preguntar sección por sección si quiere mantener, editar o reiniciar cada bloque.
- Si no existe, partir de un objeto `{}`.

### 5. Entrevistar al usuario (en este orden)

1. **last_week** — ¿Qué hiciste / entregaste la semana pasada? (bullets)
2. **this_week** — ¿Qué tenés planeado para el resto de la semana? (planes, bullets)
3. **roadblocks** — ¿Algo te está bloqueando? Lista vacía es válida.
4. **key_objectives** — Mostrar los `key_objectives` de la semana anterior como sugerencias y pedir confirmación: mantener, modificar, agregar o reemplazar.

Aceptar: lista JSON, bullets por línea, o prosa que se splitea. Lista vacía `[]` es válida.

Una sección válida luce así:
```json
["Migré el helper de Oracle a connection pool",
 "Actualicé el modal de order details en Bono"]
```

### 6. Validar antes de escribir
Comprobar que las 4 claves obligatorias existen: `last_week`, `this_week`, `roadblocks`, `key_objectives`. Si falta alguna, el CLI sale con exit 1 — re-preguntar la sección faltante.

### 7. Escribir el JSON
Escribir en `<carpeta>/weekly_summary_<friday>.json` con:
- indentación de 2 espacios
- UTF-8
- newline final

El formato completo se ve en `template.json` (junto a este SKILL.md).

### 8. Correr el CLI
Desde la raíz del proyecto:
```bash
uv run main.py <carpeta-semanal>
```
Esto regenera el `.pptx` al lado del JSON. Reportar la ruta exacta al usuario.

### 9. Listo
Mostrar las rutas finales (carpeta, JSON, PPTX) y ofrecer commit / share / revisión.

## Manejo de errores

- **CLI sale non-zero** (ej. JSON mal editado a mano): mostrar stderr textual y ofrecer reabrir la entrevista.
- **PowerPoint tiene el `.pptx` anterior abierto** (lock file `~$weekly_summary_*.pptx`): avisar antes de sobrescribir.
- **`template.pptx` falta en la raíz del proyecto**: fallar antes de correr el CLI.
