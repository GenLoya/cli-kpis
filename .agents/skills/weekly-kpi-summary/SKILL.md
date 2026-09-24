---
name: weekly-kpi-summary
description: Generate this week's Weekly Development Summary PPTX by orchestrating the cli-kpis CLI (installed binary preferred; falls back to `uv run main.py` in repo). Resolves the current week's Friday folder under .config/my-kpis/kpi-<YYYY-MM-DD>/, interviews the user for last_week, this_week, roadblocks, and key_objectives (suggesting the previous week's objectives as a default), validates the JSON, writes it, and runs the CLI to produce the .pptx.
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
│       └── kpi-<YYYY-MM-DD>/                       ← carpeta semanal con el JSON (input)
│           └── weekly_summary_<YYYY-MM-DD>.json
├── config.json                                      ← output_dir + output_filename
├── main.py                                          ← CLI
├── template.pptx                                    ← template PowerPoint
└── .agents/skills/weekly-kpi-summary/               ← esta skill
    ├── SKILL.md
    └── template.json                                (JSON de referencia)
```

**Importante**: el `.pptx` **no** se guarda en la carpeta semanal. Va a la ruta definida por `config.json`:

- `output_dir`: ruta absoluta (se expande `~` al home del usuario)
- `output_filename`: soporta el placeholder `{friday}`

El default commiteado apunta a `~/Documents/weekly_summary_<YYYY-MM-DD>.pptx`. El CLI se invoca con `cli-kpis <carpeta-semanal>` si está instalado vía `irm` (preferido); fallback dev/repo: `uv run main.py <carpeta-semanal>`.

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
- Si existe, leer su array `key_objectives` y usarlos como **sugerencias para la próxima semana** (en el JSON anterior eran "lo importante para esta semana" desde esa perspectiva).
- Si no existe, saltear la sugerencia y preguntar directo.

### 4. Cargar JSON existente (si ya hay uno esta semana)

- Si `weekly_summary_<friday>.json` existe, leerlo como punto de partida.
- Preguntar sección por sección si quiere mantener, editar o reiniciar cada bloque.
- Si no existe, partir de un objeto `{}`.

### 5. Entrevistar al usuario (en este orden)

1. **last_week** — Lo que hiciste **esta semana** (la que termina hoy, lunes a viernes).

   **Auto-derivar desde commits**:
   - Cargar `~/.config/cli-kpis/projects.txt` (una carpeta por línea, soporta `~`). Si el archivo no existe o está vacío, preguntar al usuario: "¿En qué carpeta(s) guardás tus proyectos?" (ruta única o varias separadas por coma, ej. `~/Projects, ~/work/clients`). Crear el directorio padre si hace falta y persistir la respuesta.
   - Por cada carpeta listada:
     - Si no existe, saltear con aviso.
     - Buscar recursivamente subcarpetas que contengan `.git` (bash: `find <carpeta> -name .git -type d`).
     - Por cada repo encontrado (`dirname .git`): `cd <repo> && git log --since="<friday - 4 days> 00:00" --until="<friday> 23:59" --no-merges --pretty=format:"- %s"`. Acumular los commits.
   - Mostrar el resumen auto-derivado y preguntar: **"¿Falta algo? ¿Tareas no commiteadas (reuniones, mentoring, deploys, docs)?"** Combinar los bullets auto-derivados con lo que el usuario mencione para formar la sección final.

2. **this_week** — Planes para la **próxima semana** (la que viene). Bullets.
3. **roadblocks** — ¿Algo te está bloqueando? Lista vacía es válida.
4. **key_objectives** — Las prioridades clave para la próxima semana. Mostrar los `key_objectives` de la semana anterior como sugerencias y pedir confirmación: mantener, modificar, agregar o reemplazar.

Aceptar: lista JSON, bullets por línea, o prosa que se splitea. Lista vacía `[]` es válida.

Una sección válida luce así:

```json
[
  "Migré el helper de Oracle a connection pool",
  "Actualicé el modal de order details en Bono"
]
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

Resolver qué binario usar (orden de preferencia):

1. **`cli-kpis`** (instalado por `irm` en el PATH del usuario). Verificar con `command -v cli-kpis` (bash) o `Get-Command cli-kpis` (PowerShell).
2. **Fallback dev/repo**: si lo anterior falla y existen `uv` + `main.py` en el cwd, usar `uv run main.py <carpeta-semanal>`.
3. **Fail**: si ninguno está disponible, mostrar `cli-kpis no instalado. corré 'irm' desde https://github.com/GenLoya/cli-kpis, o cloná el repo y usá uv.` y abortar.

Snippet (bash):

```bash
if command -v cli-kpis >/dev/null 2>&1; then
    cli-kpis <carpeta-semanal>
elif command -v uv >/dev/null 2>&1 && [ -f main.py ]; then
    uv run main.py <carpeta-semanal>
else
    echo "error: ni cli-kpis instalado ni uv/main.py disponibles." >&2
    exit 1
fi
```

Esto regenera el `.pptx` en la ruta definida por `config.json` (default: `~/Documents/weekly_summary_<friday>.pptx`). Reportar la ruta exacta al usuario.

### 9. Listo

Mostrar las rutas finales (carpeta, JSON, PPTX) y ofrecer commit / share / revisión.

## Manejo de errores

- **CLI sale non-zero** (ej. JSON mal editado a mano): mostrar stderr textual y ofrecer reabrir la entrevista.
- **PowerPoint tiene el `.pptx` anterior abierto** (lock file `~$weekly_summary_*.pptx`): avisar antes de sobrescribir.
- **`template.pptx` no se encuentra** (ni en cwd ni al lado del binario): fallar antes de correr el CLI. Después de `irm`, el template vive al lado del exe (`$env:LOCALAPPDATA\Programs\cli-kpis\template.pptx`); en modo dev vive en la raíz del repo.
