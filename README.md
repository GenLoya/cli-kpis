# cli-kpis

Fill the Weekly Development Summary PPTX from a JSON file.

## Install

```powershell
irm https://raw.githubusercontent.com/GenLoya/cli-kpis/master/scripts/irm.ps1 | iex
```

That's it. The script handles the rest.

## Usage

```powershell
cli-kpis <folder-with-weekly-summary.json>
```

The PPTX lands in `~/Documents/` (override with `-o` or `config.json`).

## Skill

The installer drops the `weekly-kpi-summary` skill into both `~/.agents/skills/` (Zed) and `~/.claude/skills/` (Claude Code). Invoke it with:

```
/weekly-kpi-summary
```

The agent interviews you for last week / this week / roadblocks / key objectives (suggesting the previous week's objectives), writes the JSON to `.config/my-kpis/kpi-<YYYY-MM-DD>/`, and runs `cli-kpis.exe` to produce the PPTX in `~/Documents/`.
