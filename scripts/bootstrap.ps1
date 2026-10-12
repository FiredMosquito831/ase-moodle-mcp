# Instalare completa pe o masina noua (Windows):
#   1. instaleaza pachetul ase-moodle (editabil, din clona)
#   2. te logheaza in Moodle (browser; o singura data cu Google)
#   3. configureaza pluginul in Claude Code, Codex, opencode si Antigravity
#   4. verifica starea
#
# Utilizare (din radacina clonei):
#   powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1 -SkipLogin -Targets claude,codex

param(
    [string]$Source = "FiredMosquito831/ase-moodle-mcp",
    [string[]]$Targets = @("all"),
    [ValidateSet("global", "project")][string]$Scope = "global",
    [switch]$SkipLogin
)

$ErrorActionPreference = "Stop"
$callerDir = (Get-Location).Path   # folderul de unde rulezi scriptul: folosit pentru --scope project
$root = Split-Path -Parent $PSScriptRoot

Write-Host "==> Pachet ase-moodle" -ForegroundColor Cyan
Push-Location $root
python -m pip install -e . --quiet
$pipExit = $LASTEXITCODE
Pop-Location
if ($pipExit -ne 0) { throw "pip install a esuat (inchide procesele ase-moodle-mcp care folosesc executabilul si ruleaza din nou)" }

if (-not $SkipLogin) {
    Write-Host "==> Login Moodle (se deschide browserul; logheaza-te cu Google daca ti se cere)" -ForegroundColor Cyan
    python -m ase_moodle.cli login
    if ($LASTEXITCODE -ne 0) { throw "login esuat; ruleaza: ase-moodle login --method manual" }
}

Write-Host "==> Instalare in CLI-uri: $($Targets -join ', ')" -ForegroundColor Cyan
python -m ase_moodle.cli install @Targets --source $Source --scope $Scope --project-dir $callerDir

Write-Host "==> Verificare" -ForegroundColor Cyan
python -m ase_moodle.cli doctor
exit $LASTEXITCODE
