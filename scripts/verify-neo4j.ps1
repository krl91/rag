<#
.SYNOPSIS
    Vérifie la connectivité Neo4j sur les ports 7474 (HTTP) et 7687 (Bolt).

.DESCRIPTION
    Ce script teste :
      1. Le port TCP 7474 (Neo4j Browser / API HTTP)
      2. Le port TCP 7687 (Bolt — utilisé par le driver Python)
      3. Une requête HTTP GET sur http://localhost:7474 (réponse JSON attendue)
      4. (Optionnel) Une connexion via le driver neo4j Python

.PARAMETER Host
    Adresse de Neo4j. Défaut : localhost

.PARAMETER HttpPort
    Port HTTP Neo4j. Défaut : 7474

.PARAMETER BoltPort
    Port Bolt Neo4j. Défaut : 7687

.PARAMETER TimeoutSec
    Délai d'attente en secondes pour chaque test TCP. Défaut : 5

.PARAMETER TestPython
    Si précisé, tente une connexion via le driver neo4j Python (nécessite
    que l'environnement virtuel soit activé ou que neo4j soit installé).

.EXAMPLE
    .\scripts\verify-neo4j.ps1

.EXAMPLE
    .\scripts\verify-neo4j.ps1 -TestPython

.EXAMPLE
    .\scripts\verify-neo4j.ps1 -Host 192.168.1.10 -TimeoutSec 10
#>

param(
    [string]$TargetHost = "localhost",
    [int]$HttpPort = 7474,
    [int]$BoltPort = 7687,
    [int]$TimeoutSec = 5,
    [switch]$TestPython
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ─── Helpers ────────────────────────────────────────────────────────────────

function Write-OK([string]$msg) {
    Write-Host "  [OK]  $msg" -ForegroundColor Green
}

function Write-FAIL([string]$msg) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
}

function Write-INFO([string]$msg) {
    Write-Host "  [INFO] $msg" -ForegroundColor Cyan
}

function Test-TcpPort {
    param([string]$Hostname, [int]$Port, [int]$Timeout)
    try {
        $tcp = [System.Net.Sockets.TcpClient]::new()
        $connect = $tcp.BeginConnect($Hostname, $Port, $null, $null)
        $ok = $connect.AsyncWaitHandle.WaitOne($Timeout * 1000, $false)
        if ($ok -and $tcp.Connected) {
            $tcp.Close()
            return $true
        }
        $tcp.Close()
        return $false
    }
    catch {
        return $false
    }
}

# ─── Début des tests ────────────────────────────────────────────────────────

Write-Host ""
Write-Host "=== Vérification de la connectivité Neo4j ===" -ForegroundColor Yellow
Write-Host "    Cible   : $TargetHost"
Write-Host "    HTTP    : $HttpPort"
Write-Host "    Bolt    : $BoltPort"
Write-Host "    Timeout : ${TimeoutSec}s"
Write-Host ""

$allOk = $true

# ── Test 1 : Port TCP 7474 (HTTP) ────────────────────────────────────────────
Write-Host "[ Test 1 ] Port TCP $HttpPort (HTTP Neo4j Browser)..."
if (Test-TcpPort -Hostname $TargetHost -Port $HttpPort -Timeout $TimeoutSec) {
    Write-OK "Port $HttpPort accessible"
}
else {
    Write-FAIL "Port $HttpPort inaccessible (Neo4j démarré ? Podman machine démarrée ?)"
    $allOk = $false
}

# ── Test 2 : Port TCP 7687 (Bolt) ────────────────────────────────────────────
Write-Host ""
Write-Host "[ Test 2 ] Port TCP $BoltPort (Bolt)..."
if (Test-TcpPort -Hostname $TargetHost -Port $BoltPort -Timeout $TimeoutSec) {
    Write-OK "Port $BoltPort accessible"
}
else {
    Write-FAIL "Port $BoltPort inaccessible"
    $allOk = $false
}

# ── Test 3 : Requête HTTP GET sur l'API Neo4j ─────────────────────────────────
Write-Host ""
Write-Host "[ Test 3 ] Requête HTTP GET http://${TargetHost}:${HttpPort} ..."
try {
    $response = Invoke-WebRequest `
        -Uri "http://${TargetHost}:${HttpPort}" `
        -UseBasicParsing `
        -TimeoutSec $TimeoutSec `
        -ErrorAction Stop

    if ($response.StatusCode -eq 200) {
        Write-OK "HTTP 200 reçu"
        # Vérifier que la réponse ressemble à une API Neo4j
        if ($response.Content -match '"neo4j_version"' -or
            $response.Content -match '"data"' -or
            $response.Content -match 'neo4j') {
            Write-OK "Réponse Neo4j confirmée"
        }
        else {
            Write-INFO "Réponse HTTP reçue mais contenu inattendu (Neo4j encore en cours de démarrage ?)"
        }
    }
    else {
        Write-FAIL "Code HTTP inattendu : $($response.StatusCode)"
        $allOk = $false
    }
}
catch {
    Write-FAIL "Échec de la requête HTTP : $_"
    $allOk = $false
}

# ── Test 4 (optionnel) : Driver Python neo4j ─────────────────────────────────
if ($TestPython) {
    Write-Host ""
    Write-Host "[ Test 4 ] Connexion via le driver Python neo4j..."

    # Charger le mot de passe depuis .env si présent
    $neo4jPassword = "changeme"
    $envFile = Join-Path $PSScriptRoot ".." ".env"
    if (Test-Path $envFile) {
        $envContent = Get-Content $envFile -ErrorAction SilentlyContinue
        $pwdLine = $envContent | Where-Object { $_ -match "^NEO4J_PASSWORD\s*=" }
        if ($pwdLine) {
            $neo4jPassword = ($pwdLine -split "=", 2)[1].Trim().Trim('"').Trim("'")
            Write-INFO "Mot de passe chargé depuis .env"
        }
    }

    $pythonScript = @"
import sys
try:
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        'bolt://${TargetHost}:${BoltPort}',
        auth=('neo4j', '$neo4jPassword')
    )
    with driver.session() as session:
        result = session.run('RETURN 1 AS n')
        value = result.single()['n']
        assert value == 1, f'Valeur inattendue : {value}'
    driver.close()
    print('OK')
except ImportError:
    print('IMPORT_ERROR: neo4j non installé (pip install neo4j)')
    sys.exit(2)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
"@

    # Chercher python dans l'environnement virtuel uv ou dans le PATH
    $pythonExe = $null
    $uvVenvPython = Join-Path $PSScriptRoot ".." ".venv" "Scripts" "python.exe"
    if (Test-Path $uvVenvPython) {
        $pythonExe = $uvVenvPython
        Write-INFO "Utilisation du venv uv : $pythonExe"
    }
    elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
        $pythonExe = "python"
    }
    elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
        $pythonExe = "python3"
    }

    if ($null -eq $pythonExe) {
        Write-FAIL "Python introuvable. Activer le venv ou installer Python."
        $allOk = $false
    }
    else {
        $output = & $pythonExe -c $pythonScript 2>&1
        if ($LASTEXITCODE -eq 0 -and $output -eq "OK") {
            Write-OK "Connexion Bolt réussie via le driver Python neo4j"
        }
        elseif ($LASTEXITCODE -eq 2) {
            Write-FAIL $output
            Write-INFO "Installer le driver : uv pip install neo4j"
            $allOk = $false
        }
        else {
            Write-FAIL "Connexion Python échouée : $output"
            Write-INFO "Vérifier NEO4J_PASSWORD dans .env (actuel : $neo4jPassword)"
            $allOk = $false
        }
    }
}

# ── Résumé ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Résumé ===" -ForegroundColor Yellow
if ($allOk) {
    Write-Host "  Neo4j est accessible et opérationnel." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Browser : http://${TargetHost}:${HttpPort}"
    Write-Host "  Bolt    : bolt://${TargetHost}:${BoltPort}"
    exit 0
}
else {
    Write-Host "  Un ou plusieurs tests ont échoué." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Diagnostics :"
    Write-Host "    - Vérifier que Neo4j est démarré : .\make.ps1 up"
    Write-Host "    - Vérifier que la machine Podman est démarrée : podman machine start"
    Write-Host "    - Consulter les logs : podman compose logs neo4j"
    Write-Host "    - Attendre 60 secondes (démarrage initial + téléchargement APOC)"
    exit 1
}
