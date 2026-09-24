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
