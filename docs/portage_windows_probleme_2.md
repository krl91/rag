# Portage Windows — Problème 2 : Podman rootless et conteneurisation

Neo4j 5.x (avec APOC) est démarré via `compose.yml` et Podman.
Ce document décrit les trois options disponibles sur Windows, classées par
simplicité croissante d'installation.

---

## Tableau comparatif des options

| Option | Simplicité | Sans droits admin* | Compatibilité `compose.yml` | Maintenance |
|--------|-----------|--------------------|-----------------------------|-------------|
| **A — Podman Desktop** | ⭐⭐⭐ | Partiel | ✅ Complète | Faible |
| **B — Neo4j Desktop/Server** | ⭐⭐⭐⭐ | ✅ Oui | ❌ Non applicable | Moyenne |
| **C — `podman machine` WSL2** | ⭐⭐ | Partiel | ✅ Complète | Faible |

> *L'installation initiale de WSL2 / Podman Desktop requiert des droits
> administrateur ; l'utilisation courante (démarrer/arrêter les conteneurs)
> ne le requiert pas.

**Recommandation** : **A > C > B**

- Si Podman Desktop est **déjà installé** → utiliser A directement.
- Si WSL2 est **déjà actif** → utiliser C (CLI seule, sans Podman Desktop).
- Si **aucune solution conteneur** n'est disponible ni installable → utiliser B.

---

## Option A — Podman Desktop pour Windows (recommandée)

### Prérequis système

| Prérequis | Vérification |
|-----------|-------------|
| Windows 10 v2004+ (build 19041+) ou Windows 11 | `winver` |
| Virtualisation activée (Intel VT-x / AMD-V) | Gestionnaire des tâches → onglet Performance |
| WSL2 disponible (Windows 10 v2004+) | `wsl --status` |
| Compte avec droits admin (installation uniquement) | |

### Étape 1 — Activer WSL2 (si absent)

```powershell
# En PowerShell Administrateur
wsl --install
# Redémarrer Windows
```

Pour vérifier après redémarrage :

```powershell
wsl --status
# Doit afficher : "Version par défaut : 2"
```

### Étape 2 — Installer Podman Desktop

**Via winget (recommandé, sans navigateur) :**

```powershell
winget install RedHat.Podman-Desktop
```

**Via Chocolatey :**

```powershell
choco install podman-desktop
```

**Via installeur direct :**
Télécharger sur <https://podman-desktop.io/downloads> (fichier `.exe`).

> Podman Desktop installe automatiquement `podman-cli` et `podman-compose`
> en tant que composants inclus.

### Étape 3 — Initialiser la machine Podman

Podman Desktop propose un assistant au premier lancement.
Si vous préférez la ligne de commande :

```powershell
# Créer une machine Podman avec le backend WSL2
podman machine init --provider wsl

# Démarrer la machine (à faire après chaque redémarrage Windows,
# ou configurer le démarrage automatique via Podman Desktop → Settings)
podman machine start
```

> **Note** : Podman Desktop peut configurer le démarrage automatique de la
> machine via *Settings → Resources → Podman Machine → Autostart*.
> La commande `podman machine init` n'est à exécuter qu'**une seule fois**.

### Étape 4 — Vérifier l'installation

```powershell
podman version
podman info
podman run --rm docker.io/library/hello-world
```

### Étape 5 — Démarrer Neo4j

```powershell
# Depuis la racine du dépôt :
.\make.ps1 up

# Équivalent direct :
podman compose up -d
```

Neo4j est accessible après ~60 secondes :

- **Browser** : <http://localhost:7474>
- **Bolt** : `bolt://localhost:7687`

### Compatibilité avec `compose.yml`

Le fichier `compose.yml` existant est **100 % compatible** sans modification.
Podman Desktop (backend WSL2) exécute les conteneurs dans un environnement
Linux identique à macOS/Linux natif.

---

## Option C — `podman machine` en mode WSL2 (CLI seule)

Si WSL2 est déjà actif et que vous préférez une installation minimale
(sans l'interface graphique Podman Desktop) :

### Installation de podman-cli via winget

```powershell
winget install RedHat.Podman
```

### Configuration

```powershell
# Initialiser avec le provider WSL2
podman machine init --provider wsl

# Démarrer
podman machine start

# Vérifier
podman info
```

### Installer podman-compose

```powershell
pip install podman-compose
# ou
uv tool install podman-compose
```

### Démarrer Neo4j

```powershell
podman compose up -d
```

> **Compatibilité `compose.yml`** : Complète. Aucune modification requise.
> La commande `.\make.ps1 up` fonctionne sans changement.

---

## Option B — Neo4j standalone sans conteneur

À utiliser uniquement si aucune solution de conteneurisation n'est disponible
ni installable.

### B.1 — Neo4j Desktop (recommandé — interface graphique)

1. Télécharger **Neo4j Desktop** sur <https://neo4j.com/download/>
2. Installer (installeur Windows standard, sans droits admin sur certaines
   versions)
3. Créer un nouveau projet → *Add* → *Local DBMS*
4. Choisir **Neo4j 5.x** et définir un mot de passe
5. Démarrer la base

**Installer le plugin APOC** :
Dans Neo4j Desktop → onglet *Plugins* de la base de données → *APOC* → *Install*.

### B.2 — Neo4j Community Server (service Windows)

Pour un environnement sans GUI :

1. Télécharger Neo4j Community Server 5.x sur
   <https://neo4j.com/download-center/#community>
2. Extraire dans `C:\neo4j`
3. Télécharger le plugin APOC correspondant à la version Neo4j :
   <https://github.com/neo4j/apoc/releases>
   — Fichier : `apoc-<version>-core.jar`
4. Copier le fichier `.jar` dans `C:\neo4j\plugins\`

### Mapping `compose.yml` → `neo4j.conf`

| Variable `compose.yml` | Paramètre `neo4j.conf` (Neo4j 5.x) |
|------------------------|-------------------------------------|
| `NEO4J_AUTH: neo4j/monmotdepasse` | Mot de passe défini à l'installation ; `dbms.security.auth_enabled=true` |
| `NEO4J_PLUGINS: '["apoc"]'` | Copier `apoc-*-core.jar` dans `plugins/` |
| `NEO4J_dbms_security_procedures_unrestricted: "apoc.*"` | `dbms.security.procedures.unrestricted=apoc.*` |
| `NEO4J_dbms_security_procedures_allowlist: "apoc.*"` | `dbms.security.procedures.allowlist=apoc.*` |
| `NEO4J_server_memory_heap_initial__size: "512m"` | `server.memory.heap.initial_size=512m` |
| `NEO4J_server_memory_heap_max__size: "1G"` | `server.memory.heap.max_size=1G` |

Exemple de section `neo4j.conf` complète :

```ini
# Sécurité
dbms.security.auth_enabled=true
dbms.security.procedures.unrestricted=apoc.*
dbms.security.procedures.allowlist=apoc.*

# Mémoire
server.memory.heap.initial_size=512m
server.memory.heap.max_size=1G

# Ports (valeurs par défaut, identiques à compose.yml)
server.http.listen_address=:7474
server.bolt.listen_address=:7687
```

**Démarrer Neo4j** :

```powershell
# Installation en service Windows
C:\neo4j\bin\neo4j install-service
Start-Service neo4j

# Ou démarrage manuel (sans service)
C:\neo4j\bin\neo4j console
```

> **Limitation** : L'authentification initiale via le driver Python doit
> utiliser le mot de passe défini à l'installation (pas de variable
> `NEO4J_AUTH` automatique).

---

## Ports exposés et vérification de connectivité

Neo4j expose deux ports :

| Port | Protocole | Usage |
|------|-----------|-------|
| 7474 | HTTP | Neo4j Browser, API HTTP |
| 7687 | Bolt | Driver Python/Java/etc. |

### Vérification depuis Python

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "changeme")  # valeur de NEO4J_PASSWORD dans .env
)

with driver.session() as session:
    result = session.run("RETURN 1 AS n")
    print(result.single()["n"])  # Doit afficher : 1

driver.close()
```

### Script PowerShell de vérification

Un script `scripts/verify-neo4j.ps1` est fourni dans le dépôt :

```powershell
.\scripts\verify-neo4j.ps1
```

---

## Surcharge du moteur de conteneurs (dernier recours)

Si Docker Desktop est installé et que Podman n'est pas disponible,
la variable `CONTAINER_ENGINE` permet de basculer **sans modifier** le
`compose.yml` ni le `Makefile` :

```powershell
$env:CONTAINER_ENGINE = "docker"
.\make.ps1 up
```

> **Avertissement** : Docker Desktop est interdit par la contrainte projet
> sur les environnements officiels. Cette option ne doit être utilisée qu'en
> dernier recours sur un poste de développement personnel, et documentée
> comme exception dans le journal de bord du projet.

---

## Références

- [Podman Desktop — Windows](https://podman-desktop.io/docs/installation/windows-install)
- [Podman machine — WSL2 provider](https://docs.podman.io/en/latest/markdown/podman-machine-init.1.html)
- [Neo4j Download Center](https://neo4j.com/download-center/)
- [APOC releases (GitHub)](https://github.com/neo4j/apoc/releases)
