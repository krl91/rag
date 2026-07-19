# kb-smart-metering

Système de gestion des connaissances projet pour architectes solution
dans l'industrie smart metering.

**Sources** : Jira, Confluence, Git, documents Word/Excel/PDF, diagrammes
(drawio/PlantUML/Mermaid), transcriptions de réunions, notes Obsidian.  
**Mémoire centrale** : Graphiti (graphe de connaissances temporel sur Neo4j).  
**Export** : Word/PowerPoint/Excel (`kb export`) et diagrammes Mermaid
(`kb reveng --diagram-out`, section auto-générée de `kb docgen`) —
déterministe, aucun appel LLM. Méthodes d'organisation (PARA, Zettelkasten,
GTD, Eisenhower) disponibles à la demande, voir skill `kb-organize`.  
**LLM** : optionnel. Par défaut, aucun LLM réseau n'est requis — le flux
conversationnel (`kb extract`/`kb ingest-extraction`, `kb search`) fonctionne
entièrement depuis la conversation VS Code (Copilot Chat en mode Agent),
sans serveur ni port ouvert. Si un LLM réseau est disponible (Ollama local,
3B–14B, endpoint OpenAI-compatible), `kb ingest`/`kb ask` offrent en plus un
pipeline automatique en une commande. Voir
[docs/guide_utilisation.md](docs/guide_utilisation.md).

---

## Prérequis

| Outil | Version minimale | Notes |
|-------|-----------------|-------|
| Python | 3.11+ | |
| [uv](https://docs.astral.sh/uv/) | dernière stable | gestionnaire de dépendances. **Absent sur Windows ?** utiliser `py` + `pip` directement, voir [Windows](#windows) |
| [Podman](https://podman.io/) | 4.x+ | conteneurs rootless (sinon Neo4j sans conteneur, voir Windows) |
| Ollama | dernière stable | LLM local, **optionnel** — sans lui, le flux conversationnel (voir Windows) fonctionne sans rien installer de plus |

> **Windows** : `make` n'est pas requis. Utiliser `.\make.ps1 <cible>`
> (PowerShell natif). Voir la section [Windows](#windows) ci-dessous.

### macOS — initialisation de la machine Podman

Podman nécessite une machine virtuelle Linux sur macOS. À faire **une seule fois** :

```bash
podman machine init
podman machine start
```

Vérifier que Podman fonctionne :

```bash
podman info
```

---

## Installation

```bash
# 1. Cloner le dépôt
git clone <url-du-depot>
cd base-de-connaisances_projet-augmentee

# 2. Installer l'environnement et copier la configuration
make setup

# 3. Renseigner les variables dans .env
#    (fichier créé automatiquement par make setup depuis .env.example)
$EDITOR .env
```

---

## Démarrage de Neo4j

```bash
make up
```

Neo4j est disponible après environ 60 secondes (le plugin APOC est téléchargé
au premier démarrage) :

- **Browser** : [http://localhost:7474](http://localhost:7474)
- **Bolt** : `bolt://localhost:7687`
- Identifiants par défaut : `neo4j` / valeur de `NEO4J_PASSWORD` dans `.env`

Pour arrêter les conteneurs :

```bash
make down
```

---

## Développement

```bash
# Tests
make test

# Lint (ruff) + types (mypy)
make lint
```

---

## Arborescence

```
src/kb_smart_metering/
├── config.py          # Pydantic Settings (chargement .env)
├── cli.py             # Point d'entrée CLI (`kb`)
├── models/            # Entités Pydantic du domaine
├── extractors/        # Collecte des données sources (dont diagrams.py :
│                      # drawio/PlantUML/Mermaid, stdlib uniquement)
├── ingestion/         # graphiti.py (auto, si LLM) + graph_writer.py/
│                       # extraction_schema.py (écriture déterministe, sans LLM)
├── retrieval/          # Graphe + vecteurs + reranking (toujours local)
├── assistant/          # chain.py (build_context, sans LLM) + llm.py (si LLM dispo)
├── revengine/           # AST (tree-sitter) + diagram_export.py (Mermaid, sans LLM)
├── export/              # office_writer.py : Word/PowerPoint/Excel, sans LLM
└── api/                 # FastAPI (/health, /search, /ask)
tests/
copilot-bridge/         # Extension VS Code — option avancée, déconseillée par défaut
.vscode/mcp.json.example # Serveurs MCP optionnels (drawio, plantuml)
compose.yml             # Neo4j via Podman
Makefile / make.ps1
pyproject.toml
```

---

## Variables d'environnement

Voir [.env.example](.env.example) pour la liste complète et la documentation
de chaque variable.

---

## Windows

> Prérequis : **Python 3.11+** (via `py`). `uv` est **optionnel** — `make.ps1`
> détecte automatiquement son absence et bascule sur `py -m venv` + `pip`
> (aucun `Node.js` requis pour ce chemin par défaut : voir
> [Variables d'environnement](#variables-denvironnement), le LLM est
> optionnel). `make` (l'outil Unix) n'est **pas** nécessaire : un script
> PowerShell équivalent est fourni.

### Bootstrap en une commande (PowerShell)

Ouvrir PowerShell en tant qu'utilisateur normal (pas Administrateur) :

```powershell
# Autoriser l'exécution de scripts locaux (une seule fois par machine)
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Cloner le dépôt et démarrer
git clone <url-du-depot>
cd base-de-connaisances_projet-augmentee
.\make.ps1 setup
```

### Équivalences des commandes

| macOS / Linux   | Windows (PowerShell)    |
|-----------------|-------------------------|
| `make setup`    | `.\make.ps1 setup`      |
| `make up`       | `.\make.ps1 up`         |
| `make down`     | `.\make.ps1 down`       |
| `make test`     | `.\make.ps1 test`       |
| `make lint`     | `.\make.ps1 lint`       |

### Surcharge du moteur de conteneurs

```powershell
$env:CONTAINER_ENGINE = "docker"
.\make.ps1 up
```

### Neo4j sur Windows — options d'installation

Trois options sont disponibles, de la plus simple à la plus manuelle :

| Option | Prérequis | Compatible `compose.yml` |
|--------|-----------|--------------------------|
| **A — Podman Desktop** (recommandée) | WSL2 + droits admin (installation) | ✅ Oui |
| **C — `podman machine` WSL2** (CLI seule) | WSL2 + droits admin (installation) | ✅ Oui |
| **B — Neo4j Desktop/Server** (sans conteneur) | Aucun | ❌ Config manuelle |

**Option A — Installation rapide de Podman Desktop :**

```powershell
# 1. Activer WSL2 (PowerShell Administrateur, puis redémarrer)
wsl --install

# 2. Installer Podman Desktop
winget install RedHat.Podman-Desktop

# 3. Initialiser et démarrer la machine Podman (une seule fois)
podman machine init --provider wsl
podman machine start

# 4. Démarrer Neo4j
.\make.ps1 up
```

Pour les options B et C, ainsi que le mapping `compose.yml` → `neo4j.conf`
et les détails APOC, voir [docs/portage_windows_probleme_2.md](docs/portage_windows_probleme_2.md).

**Vérification de la connectivité Neo4j :**

```powershell
.\scripts\verify-neo4j.ps1
# Avec test du driver Python :
.\scripts\verify-neo4j.ps1 -TestPython
```

**Ajustement du `compose.yml` pour Windows (si healthcheck échoue) :**

```powershell
# Activer l'override Windows (healthcheck HTTP à la place de "neo4j status")
Copy-Item compose.override.yml.windows compose.override.yml
.\make.ps1 down
.\make.ps1 up
```

**Surcharge vers Docker (dernier recours) :**

```powershell
$env:CONTAINER_ENGINE = "docker"
.\make.ps1 up
```

### Pourquoi pas `make` sous Windows ?

- `make` n'est pas préinstallé sur Windows.
- Même avec GNU Make pour Windows (GnuWin32), les commandes POSIX (`cp -n`,
  `||`, etc.) ne fonctionnent pas dans `cmd.exe` ou PowerShell natif.
- Le script `make.ps1` est **natif PowerShell**, sans dépendance externe,
  et reproduit fidèlement le comportement de chaque cible du Makefile.
- Le script Python `scripts/setup.py` (appelé par `make setup` et
  `.\make.ps1 setup`) gère la copie de `.env.example` → `.env` de façon
  100 % cross-platform.

### Windows — Encodage UTF-8

Les messages de log et les réponses du CLI contiennent des caractères accentués
(é, è, ê, à, ç, etc.). Sur Windows, la console (`cmd.exe`, PowerShell) utilise
par défaut l'encodage `cp1252`, ce qui provoque l'affichage de `?` ou de
caractères corrompus.

**Solution automatique (intégrée dans le code) :**
`cli.py` appelle `sys.stdout.reconfigure(encoding='utf-8')` et
`sys.stderr.reconfigure(encoding='utf-8')` au démarrage — aucune action
requise de votre part pour les commandes `kb`.

**Solution complémentaire (recommandée, couvre également uvicorn / autres outils) :**
Ajouter `PYTHONUTF8=1` en variable d'environnement utilisateur Windows
(Paramètres système → Variables d'environnement) ou dans le profil PowerShell :

```powershell
# Ajouter dans $PROFILE (persistant à travers les sessions)
$env:PYTHONUTF8 = "1"
```

Cette variable doit être définie **avant** le démarrage de Python (elle est
ignoré si chargée depuis `.env` via python-dotenv, car `sys.stderr` est déjà
initialisé à ce moment).

**Alternative ponctuelle :** passer la console en mode UTF-8 pour la session
en cours :

```powershell
chcp 65001
```

### GitPython — dépendance à `git` dans le PATH

`GitPython` encapsule des appels au **binaire `git`** via des sous-processus.
`git` n'est **pas préinstallé sur Windows** : son absence provoque une erreur
`RuntimeError` avec un message explicite dès l'instanciation de `GitExtractor`.

**Installation recommandée :**

```powershell
winget install Git.Git
# ou
choco install git
```

Téléchargement direct : <https://git-scm.com/download/win>

**Alternative (installation non standard ou portable) :** définir la variable
`GIT_PYTHON_GIT_EXECUTABLE` dans `.env` pour pointer directement vers
l'exécutable :

```dotenv
GIT_PYTHON_GIT_EXECUTABLE=C:\Program Files\Git\bin\git.exe
```

Cette variable est documentée dans [.env.example](.env.example). Elle
court-circuite la détection automatique via `PATH` — utile si `git` est
installé dans un répertoire non standard.

> La source `git` est **optionnelle** : si vous n'extrayez pas de dépôts Git,
> l'absence de `git` n'impacte pas les autres fonctionnalités du projet.

### Module `revengine` (analyse statique de code)

Le module `revengine` (rétro-ingénierie Java/Python/C# via `tree-sitter`) est
une **dépendance optionnelle**. Il n'est pas nécessaire pour l'ingestion,
le retrieval ni l'API.

#### Disponibilité des wheels Windows (sans compilateur C)

| Paquet | `win_amd64` | `win_arm64` | Python |
|--------|-------------|-------------|--------|
| `tree-sitter>=0.22.0` | ✅ dès v0.22.2 | ✅ dès v0.23.0 | 3.11, 3.12, 3.13 |
| `tree-sitter-language-pack>=0.3.0` | ✅ dès v0.3.0 (abi3) | ✅ dès v1.8.0 | 3.9+ |

> **Aucun Visual Studio Build Tools** ni compilateur C n'est requis sur
> Windows x64 ou ARM64 : `pip` / `uv` téléchargent directement les wheels
> binaires pré-compilés.

#### Installation

**Avec `uv` :**
```powershell
uv sync --extra revengine              # module revengine seul
uv sync --extra revengine --extra dev  # + dépendances dev
```

**Sans `uv` (pip) :**
```powershell
pip install -e ".[dev,revengine]"
```

#### Vérification

```powershell
uv run python -c "import tree_sitter_language_pack; print('revengine OK')"
# ou, sans uv :
python -c "import tree_sitter_language_pack; print('revengine OK')"
```

#### Compilation depuis les sources (cas exceptionnel)

Si, pour une raison inhabituelle (plateforme non supportée), aucun wheel
binaire n'est disponible et que pip tente une compilation :

| Outil | Installation | Droits admin |
|-------|--------------|--------------|
| **Visual Studio Build Tools** (MSVC) | `winget install Microsoft.VisualStudio.2022.BuildTools` | Oui |
| **MinGW-w64** (via MSYS2) | `winget install MSYS2.MSYS2` | Non |

> `uv sync` délègue la compilation à `pip`/`setuptools` ; si MSVC est
> détecté dans le PATH, la compilation s'effectue automatiquement.

### API uvicorn — comportement et performances sur Windows

#### Installation : aucun problème

La dépendance `uvicorn[standard]>=0.29.0` (déclarée dans `pyproject.toml`)
s'installe correctement sur Windows. Les composants de l'extra `[standard]`
disposent tous de wheels pré-compilés pour `win_amd64` sur PyPI :

| Composant | Rôle | Wheels `win_amd64` |
|-----------|------|---------------------|
| `httptools` | Parser HTTP (C extension) | ✅ toutes versions |
| `watchfiles` | Rechargement automatique | ✅ toutes versions |
| `websockets` | Support WebSockets | ✅ pure Python |
| `python-dotenv` | Chargement `.env` | ✅ pure Python |
| `uvloop` | Boucle événements haute perf. | **auto-exclu** sur Windows |

`uvloop` est exclu automatiquement via le marker PEP 508 dans les métadonnées
d'uvicorn (`uvloop ; sys_platform != "win32"`). Aucune modification du
`pyproject.toml` n'est nécessaire.

#### Différence de performances Windows vs Linux/macOS

| Plateforme | Boucle événements | Impact |
|------------|-------------------|--------|
| Linux / macOS | `uvloop` (libuv C) | boucle haute performance |
| Windows | asyncio standard (Python) | légère hausse de latence |

En pratique, pour ce projet (usage interne, quelques utilisateurs simultanés,
réponses bornées par le temps d'inférence du LLM local), **l'absence d'`uvloop`
n'est pas perceptible** : le goulet d'étranglement est le LLM, pas la boucle
I/O.

#### Démarrage explicite avec la boucle asyncio (optionnel)

Pour forcer explicitement la boucle standard (utile en débogage ou si un
message d'avertissement uvicorn apparaît) :

```powershell
uv run uvicorn --loop asyncio src.kb_smart_metering.api.app:app --reload
```

Sans `--loop asyncio`, uvicorn sélectionne automatiquement la meilleure
boucle disponible : `asyncio` sur Windows, `uvloop` sur Linux/macOS.

### PyTorch et `sentence-transformers` sous Windows

#### Variante PyTorch installée par défaut

Le projet utilise `sentence-transformers` pour les embeddings (BGE-M3) et le
reranking (BGE-reranker-v2-m3). `sentence-transformers` dépend de **PyTorch**.

Sur PyPI standard, `uv sync` installe la variante **CUDA** de PyTorch (~2 Go)
même si aucun GPU NVIDIA n'est présent. Le `pyproject.toml` de ce projet
configure `uv` pour installer automatiquement la variante **CPU** (~200 Mo)
sur Windows :

```toml
[tool.uv.sources]
torch = [
    { index = "pytorch-cpu", marker = "sys_platform == 'win32'" },
]
```

Cette configuration est transparente : `uv sync` l'applique automatiquement.

> **Si vous disposez d'un GPU NVIDIA sous Windows**, commentez le bloc
> `[tool.uv.sources]` dans `pyproject.toml` et relancez `uv sync` pour
> bénéficier de l'accélération CUDA.

**Sans `uv` (pip seul)** : `[tool.uv.sources]` ne s'applique qu'à `uv` —
avec `pip`, installer explicitement la variante CPU **avant** le reste des
dépendances, sous peine de télécharger CUDA (~2 Go) par défaut :

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev]"
```
(déjà fait automatiquement par `.\make.ps1 setup` si `uv` est absent.)

#### Téléchargement des modèles HuggingFace

Les modèles sont téléchargés depuis HuggingFace Hub au **premier lancement**
de l'embedder ou du reranker (lazy loading) :

| Modèle | Taille | Usage |
|--------|--------|-------|
| `BAAI/bge-m3` | ~2,3 Go | Embeddings (ingestion + retrieval) |
| `BAAI/bge-reranker-v2-m3` | ~2,3 Go | Reranking des résultats |

Ils sont mis en cache dans `~/.cache/huggingface/` (ou `C:\Users\<user>\.cache\huggingface\`
sous Windows). **Prévoir ~5 Go de disque disponible.**

#### Cache HuggingFace — chemins avec espaces (Windows)

Si votre nom d'utilisateur Windows contient des espaces (ex. `C:\Users\Jean Dupont`),
certaines bibliothèques peuvent échouer lors de l'appel de sous-processus
internes. Rediriger le cache via `HF_HOME` dans `.env` :

```dotenv
HF_HOME=C:\kb-cache\huggingface
```

Créer le répertoire avant le premier lancement :

```powershell
New-Item -ItemType Directory -Force -Path C:\kb-cache\huggingface
```

`sentence-transformers` (via `huggingface_hub`) respecte `HF_HOME`. Cette
variable est documentée dans [.env.example](.env.example).
