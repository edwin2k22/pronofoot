# ════════════════════════════════════════════════════════════════════
#  PronoFoot — lancement Windows PowerShell (live auto + serveur web)
#  Equivalent de start.sh pour Windows PowerShell
#
#  Usage :
#    .\start.ps1                  # defaut : poll 30s, port 8077
#    .\start.ps1 -LivePoll 20 -Port 8080
#    .\start.ps1 -ServerOnly      # serveur web seul (sans refresh ni scheduler)
#    .\start.ps1 -Status          # diagnostic du calendrier
# ════════════════════════════════════════════════════════════════════
param(
    [int]$LivePoll = 30,
    [int]$Port = 8077,
    [switch]$ServerOnly,
    [switch]$Status
)

$ErrorActionPreference = "Continue"

# ── Encodage UTF-8 pour les emojis Python (Windows) ──────────────────────
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Aller dans le dossier du script
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "  PronoFoot - demarrage intelligent - Windows PowerShell" -ForegroundColor Cyan
Write-Host "    * Scheduler live : poll ${LivePoll}s en match" -ForegroundColor White
Write-Host "    * App web        : http://localhost:${Port}/index.html" -ForegroundColor White
Write-Host "    * Ctrl+C pour tout arreter" -ForegroundColor Yellow
Write-Host ""

# ── Mode diagnostic ──────────────────────────────────────────────────
if ($Status) {
    Write-Host "  Diagnostic du calendrier..." -ForegroundColor Cyan
    python -m collector.smart_live --status
    exit 0
}

# ── Mode serveur seul ─────────────────────────────────────────────────
if ($ServerOnly) {
    Write-Host "  Serveur web seul sur le port $Port" -ForegroundColor Cyan
    Write-Host "  Ouvrez : http://localhost:${Port}/index.html" -ForegroundColor Green
    python -m collector.server $Port
    exit 0
}

# ── 0) Refresh complet au demarrage ──────────────────────────────────
Write-Host "  Initialisation (refresh complet)..." -ForegroundColor Cyan
try {
    python -m collector.refresh
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  AVERTISSEMENT : refresh partiel (verifiez la connexion internet)" -ForegroundColor Yellow
        Write-Host "  Le serveur va demarrer avec les donnees existantes." -ForegroundColor Yellow
    } else {
        Write-Host "  Pret." -ForegroundColor Green
    }
} catch {
    Write-Host "  ERREUR refresh : $_" -ForegroundColor Red
}
Write-Host ""

# ── 1) Scheduler live en arriere-plan ────────────────────────────────
Write-Host "  Demarrage du scheduler live..." -ForegroundColor Cyan
$schedulerJob = Start-Job -ScriptBlock {
    param($dir, $poll)
    Set-Location $dir
    python -m collector.smart_live --live-poll $poll
} -ArgumentList $PSScriptRoot, $LivePoll

Write-Host "  Scheduler demarre (Job ID: $($schedulerJob.Id))" -ForegroundColor Green
Write-Host ""

# ── 2) Serveur web (bloquant) ─────────────────────────────────────────
Write-Host "  Serveur web sur le port $Port..." -ForegroundColor Cyan
Write-Host "  Ouvrez votre navigateur sur : http://localhost:${Port}/index.html" -ForegroundColor Green
Write-Host ""

try {
    python -m collector.server $Port
} finally {
    # Nettoyage : arreter le scheduler quand on quitte
    Write-Host ""
    Write-Host "  Arret du scheduler live..." -ForegroundColor Yellow
    Stop-Job $schedulerJob -ErrorAction SilentlyContinue
    Remove-Job $schedulerJob -ErrorAction SilentlyContinue
    Write-Host "  PronoFoot arrete." -ForegroundColor Cyan
}
