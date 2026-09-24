<#
.SYNOPSIS
irm - Install/Run Manager for cli-kpis (Windows PowerShell).

.DESCRIPTION
Downloads cli-kpis at a given version from GitHub Releases, installs the
executable to the standard user PATH location on Windows, copies the
PowerPoint template alongside it, and installs the weekly-kpi-summary skill
into both ~/.agents (Zed) and ~/.claude (Claude Code).

No admin privileges required. Everything lives in user scope.

.PARAMETER Version
The version tag to install (e.g., v0.1.0). Defaults to "latest", which is
resolved via the GitHub Releases API.

.EXAMPLE
irm v0.1.0
irm latest

From the repo:
.\scripts\irm.ps1 -Version v0.1.0
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Version = "latest"
)

# --- Configuration ---
$ErrorActionPreference = "Stop"
$Repo       = "GenLoya/cli-kpis"
$ToolName   = "cli-kpis"
$SkillName  = "weekly-kpi-summary"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\$ToolName"

# --- Pretty-print helpers ---
function Write-Step { param($msg) Write-Host "-> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "OK  $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "!!  $msg" -ForegroundColor Yellow }

# --- 1. Resolve version ---
if ($Version -eq "latest") {
    Write-Step "Resolving latest version from GitHub API..."
    $release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
    $Version = $release.tag_name
}
Write-OK "Target: $ToolName $Version"

# --- 2. Ensure install dir ---
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
}

# --- 3. Download binary ---
$exePath = Join-Path $InstallDir "$ToolName.exe"
Write-Step "Downloading $ToolName.exe..."
Invoke-WebRequest `
    "https://github.com/$Repo/releases/download/$Version/$ToolName.exe" `
    -OutFile $exePath -UseBasicParsing
Write-OK "Binary:  $exePath"

# --- 3.5. Download config.json next to the exe (consumed by the CLI) ---
$configPath = Join-Path $InstallDir "config.json"
Write-Step "Downloading config.json..."
Invoke-WebRequest `
    "https://raw.githubusercontent.com/$Repo/$Version/config.json" `
    -OutFile $configPath -UseBasicParsing
Write-OK "Config:   $configPath"

# --- 4. Download skill zip (once, reused for both ~/.agents and ~/.claude) ---
# GetTempFileName() returns a .tmp path, but Expand-Archive requires a .zip
# extension on Windows PowerShell 5.1, so we rewrite the extension.
$skillZip = [System.IO.Path]::ChangeExtension([System.IO.Path]::GetTempFileName(), ".zip")
Write-Step "Downloading $SkillName.zip..."
Invoke-WebRequest `
    "https://github.com/$Repo/releases/download/$Version/$SkillName.zip" `
    -OutFile $skillZip -UseBasicParsing

# --- 5. Install skill into ~/.agents (Zed) ---
$agentsSkill = Join-Path $HOME ".agents\skills\$SkillName"
if (Test-Path $agentsSkill) { Remove-Item -Recurse -Force $agentsSkill }
New-Item -ItemType Directory -Force -Path $agentsSkill | Out-Null
Expand-Archive -Path $skillZip -DestinationPath $agentsSkill -Force
Write-OK "Skill (Zed):     $agentsSkill"

# --- 6. Install skill into ~/.claude (Claude Code) ---
$claudeSkill = Join-Path $HOME ".claude\skills\$SkillName"
if (Test-Path $claudeSkill) { Remove-Item -Recurse -Force $claudeSkill }
New-Item -ItemType Directory -Force -Path $claudeSkill | Out-Null
Expand-Archive -Path $skillZip -DestinationPath $claudeSkill -Force
Write-OK "Skill (Claude):  $claudeSkill"

# --- 7. Cleanup temp zip ---
Remove-Item $skillZip

# --- 8. Download template.pptx next to the exe ---
$templatePath = Join-Path $InstallDir "template.pptx"
Write-Step "Downloading template.pptx..."
Invoke-WebRequest `
    "https://github.com/$Repo/releases/download/$Version/template.pptx" `
    -OutFile $templatePath -UseBasicParsing
Write-OK "Template:  $templatePath"

# --- 9. Ensure install dir is in user PATH ---
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$userPathDirs = @($userPath -split ';' | Where-Object { $_ -ne '' })
if ($InstallDir -notin $userPathDirs) {
    Write-Step "Adding $InstallDir to user PATH..."
    [Environment]::SetEnvironmentVariable('Path', "$userPath;$InstallDir", 'User')
    $env:Path += ";$InstallDir"
    Write-OK "PATH updated (restart terminal to persist)"
} else {
    Write-OK "$InstallDir already in user PATH"
}

Write-Host ""
Write-Host "Installation complete. Run '$ToolName --help' in a new terminal to verify." -ForegroundColor Green
