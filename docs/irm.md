# Cómo: Instalar `cli-kpis` con `irm`

> **irm** (Install/Run Manager) es el instalador oficial de `cli-kpis` para Windows.
> Recibe una **versión** como argumento, descarga los artefactos del release correspondiente
> desde GitHub, y los deja listos en los lugares correctos para que `cli-kpis` funcione
> sin configuración adicional.

---

## Qué hace `irm`

Cuando ejecutás `irm v0.1.0` (o `irm latest`), el script hace, **en orden**:

1. **Resuelve la versión**. Si le pasás `latest`, consulta la API de GitHub Releases con `Invoke-RestMethod` (`irm`) para obtener la última. Si le pasás un tag específico (ej: `v0.1.0`), lo usa tal cual.
2. **Crea el directorio de instalación**: `%LOCALAPPDATA%\Programs\cli-kpis\` (la ubicación estándar de Windows para programas del usuario; **no requiere permisos de administrador**).
3. **Descarga el binario** `cli-kpis.exe` desde el release correspondiente de GitHub con `Invoke-WebRequest` (`iwr`).
4. **Descarga la skill** `weekly-kpi-summary.zip` desde el mismo release.
5. **Instala la skill en `~/.agents/skills/weekly-kpi-summary/`** — para que Zed la descubra automáticamente.
6. **Instala la skill en `~/.claude/skills/weekly-kpi-summary/`** — para que Claude Code la descubra automáticamente.
7. **Descarga `template.pptx`** y lo coloca al lado del binario (mismo directorio).
8. **Asegura que `%LOCALAPPDATA%\Programs\cli-kpis\` esté en el `PATH` del usuario.** Si no está, lo agrega con `[Environment]::SetEnvironmentVariable`.

---

## Ubicaciones de instalación

| Componente | Path |
|---|---|
| Binario | `%LOCALAPPDATA%\Programs\cli-kpis\cli-kpis.exe` |
| Template | `%LOCALAPPDATA%\Programs\cli-kpis\template.pptx` |
| Skill (Zed) | `%USERPROFILE%\.agents\skills\weekly-kpi-summary\` |
| Skill (Claude Code) | `%USERPROFILE%\.claude\skills\weekly-kpi-summary\` |

---

## Uso

### Desde el repo (modo script)

```powershell
# Última versión (default)
.\scripts\irm.ps1

# Versión específica
.\scripts\irm.ps1 -Version v0.1.0
```

### Como atajo `irm` (después de invocar el script una vez)

Para que el comando `irm` esté disponible globalmente, agregá una función en tu perfil de PowerShell (`$PROFILE`):

```powershell
function irm { & "<ruta-al-repo>\scripts\irm.ps1" @args }
```

Después de eso, podés correr `irm v0.1.0` desde cualquier terminal.

> **Nota**: el alias nativo `irm` (de `Invoke-RestMethod`) queda sombreado por esta función.
> Si necesitás `Invoke-RestMethod`, llamalo por nombre completo o usá otro alias (`iwr` también está disponible).

---

## Por qué `%LOCALAPPDATA%\Programs\cli-kpis\`

Es la **ubicación estándar para programas instalados por usuario en Windows modernos** (similar a `/usr/local/bin` en Unix). No requiere permisos de administrador y está pensada específicamente para binarios que el usuario quiere invocar desde el `PATH`.

Otras ubicaciones posibles (y por qué no las usamos):

- `C:\Windows\System32` — requiere admin,污染a el system dir.
- `C:\Program Files\` — requiere admin.
- `C:\Users\<user>\bin\` — Unix-style; requiere que el usuario la agregue manualmente al `PATH`.

---

## Workflow típico post-instalación

Después de correr `irm v0.1.0`:

1. **Abrí un terminal nuevo** (para que tome el `PATH` actualizado).
2. **Verificá**: `cli-kpis --help` debería mostrar la ayuda del CLI.
3. **Usá la skill**: en Zed o Claude Code, escribí `/weekly-kpi-summary`. El agente sabe cómo orquestar el CLI.
4. **Generá un PPTX**: con un folder semanal válido (ej: `.config/my-kpis/kpi-2026-09-25/` con `weekly_summary_2026-09-25.json` adentro), corré `cli-kpis.exe <folder>` y el `.pptx` aparece en `~/Documents/`.

---

## Prerrequisitos

- Windows 10 u 11.
- PowerShell 5.1 o superior (incluido por defecto en Windows 10+).
- Conexión a internet.
- **Sin permisos de administrador** — todo se instala en scope del usuario (`%LOCALAPPDATA%` y `%USERPROFILE%`).

---

## Troubleshooting

| Problema | Causa probable | Solución |
|---|---|---|
| `'cli-kpis' is not recognized as a command` | El `PATH` no se actualizó en el terminal actual | Abrí uno nuevo, o corré `[Environment]::SetEnvironmentVariable` manualmente |
| `Permission denied` al sobrescribir el `.exe` | PowerPoint u otro proceso tiene lockeado el archivo | Cerrá PowerPoint y volvé a correr `irm` |
| GitHub API rate limit (60 req/hour sin auth) | Demasiadas llamadas a `latest` en poco tiempo | Pasale un tag específico: `irm v0.2.0` en lugar de `irm latest` |
| Skill no aparece en Zed / Claude Code | La herramienta no escanea skills en runtime | Reiniciá la herramienta después de instalar |

---

## Cómo actualizar a una versión nueva

Simplemente corré `irm` de nuevo con la versión nueva (o `latest`):

```powershell
irm latest
```

El script es **idempotente**: sobrescribe binario, skill y template sin dejar archivos viejos. Si tenés PowerPoint lockeando el binario, cerralo primero.

---

## Estructura de los assets del release

Cada release de `cli-kpis` en GitHub publica tres artefactos que `irm` espera:

| Asset | Qué es | Dónde lo pone `irm` |
|---|---|---|
| `cli-kpis.exe` | Binario standalone (PyInstaller) | `%LOCALAPPDATA%\Programs\cli-kpis\` |
| `weekly-kpi-summary.zip` | La skill Zed/Claude Code comprimida | `~/.agents/skills/weekly-kpi-summary/` y `~/.claude/skills/weekly-kpi-summary/` |
| `template.pptx` | El template PowerPoint base | `%LOCALAPPDATA%\Programs\cli-kpis\` (junto al `.exe`) |
