# make.ps1 — Équivalent du Makefile pour Windows (PowerShell natif)
#
# Usage :
#   .\make.ps1 setup
#   .\make.ps1 up
#   .\make.ps1 down
#   .\make.ps1 test
#   .\make.ps1 lint
#
# Prérequis : Python 3.11+ (via `py`).
# `uv` est OPTIONNEL : s'il est détecté sur le PATH, il est utilisé (uv sync,
# uv run). S'il est absent — cas typique d'une machine Windows où seuls `py`
# et `pip` sont disponibles — bascule automatiquement sur un environnement
# virtuel classique (py -m venv .venv) + pip. Aucune dépendance à Node.js.
# Podman Desktop (ou podman-cli) pour les cibles up/down.
#
# Surcharge du moteur de conteneurs (optionnel) :
#   $env:CONTAINER_ENGINE = "docker"; .\make.ps1 up

param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("setup", "up", "down", "test", "lint")]
    [string]$Target
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Moteur de conteneurs (podman par défaut, surchargeable via variable d'env)
$ContainerEngine = if ($env:CONTAINER_ENGINE) { $env:CONTAINER_ENGINE } else { "podman" }

# uv optionnel : détecté une fois, utilisé partout où c'est pertinent.
$UseUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)
$VenvPython = Join-Path ".venv" "Scripts\python.exe"

function Invoke-Setup {
    if ($UseUv) {
        Write-Host "==> uv détecté — installation via uv sync..." -ForegroundColor Cyan
        uv sync --all-extras
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        Write-Host "==> Initialisation du fichier .env..." -ForegroundColor Cyan
        uv run python scripts/setup.py
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        return
    }

    Write-Host "==> uv absent — installation via py + pip (environnement .venv)..." -ForegroundColor Cyan
    py -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    # Torch CPU d'abord : pip installerait sinon la variante CUDA (~2 Go)
    # par défaut, même sans GPU présent (voir pyproject.toml [tool.uv.sources],
    # config équivalente pour uv uniquement — pip a besoin de cette étape
    # manuelle).
    Write-Host "==> Installation de PyTorch (variante CPU)..." -ForegroundColor Cyan
    & $VenvPython -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Installation des dépendances du projet..." -ForegroundColor Cyan
    & $VenvPython -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Initialisation du fichier .env..." -ForegroundColor Cyan
    & $VenvPython scripts/setup.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-Up {
    Write-Host "==> Démarrage des conteneurs ($ContainerEngine)..." -ForegroundColor Cyan
    & $ContainerEngine compose up -d
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-Down {
    Write-Host "==> Arrêt des conteneurs ($ContainerEngine)..." -ForegroundColor Cyan
    & $ContainerEngine compose down
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-Test {
    Write-Host "==> Lancement des tests pytest..." -ForegroundColor Cyan
    if ($UseUv) {
        uv run pytest
    } else {
        & $VenvPython -m pytest
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-Lint {
    Write-Host "==> Vérification du style (ruff)..." -ForegroundColor Cyan
    if ($UseUv) {
        uv run ruff check src tests
    } else {
        & $VenvPython -m ruff check src tests
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "==> Vérification des types (mypy)..." -ForegroundColor Cyan
    if ($UseUv) {
        uv run mypy src
    } else {
        & $VenvPython -m mypy src
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

switch ($Target) {
    "setup" { Invoke-Setup }
    "up"    { Invoke-Up }
    "down"  { Invoke-Down }
    "test"  { Invoke-Test }
    "lint"  { Invoke-Lint }
}
