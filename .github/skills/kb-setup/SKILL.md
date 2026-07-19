---
name: kb-setup
description: "Installation et configuration initiale de kb-smart-metering. Utiliser pour : première installation sur macOS, Linux ou Windows (avec uv, ou avec py+pip seul si uv/Ollama/Node ne sont pas disponibles), configuration du fichier .env (Jira, Confluence, Neo4j, LLM), démarrage de Neo4j via Podman, téléchargement des modèles d'embeddings BGE-M3, vérification que le CLI fonctionne. Également : diagnostiquer une installation cassée, reconfigurer après rotation de tokens."
argument-hint: "Plateforme cible (macOS/Linux avec uv | Windows avec py+pip)"
---

# Skill — Installation initiale kb-smart-metering

## Quand utiliser ce skill

- Première mise en place du système sur une machine
- Reconfiguration après rotation de tokens Jira/Confluence
- Diagnostic d'une installation qui ne démarre plus
- Onboarding d'un nouveau membre de l'équipe

---

## Deux profils d'installation

| | macOS / Linux (dev) | Windows (poste cible typique) |
|---|---|---|
| Gestionnaire Python | `uv` | **`py` + `pip`** (pas de `uv`) |
| Conteneurs | Podman | Podman (si autorisé par l'IT), sinon Neo4j sans conteneur |
| LLM | Ollama local | **Aucun serveur LLM** — voir "Étape 5" ci-dessous |
| Extension VS Code (Node.js) | Non nécessaire | **Non nécessaire** (le flux par défaut ne l'utilise pas) |

Détecter le profil en Étape 0 avant de continuer.

---

## Étape 0 — Détecter l'environnement

```bash
python --version 2>nul || python3 --version   # ≥ 3.11
uv --version                                    # présent ? → profil macOS/Linux
py --version                                    # présent (Windows) ? → profil Windows py+pip
ollama --version                                # présent ? → LLM local disponible
podman --version                                # présent ? → conteneurs disponibles
```

---

## Profil macOS / Linux (uv)

### 1 — Prérequis et VM Podman (macOS uniquement)

```bash
podman machine init
podman machine start
```

### 2 — Installer l'environnement Python

```bash
git clone <url-du-depot>
cd base-de-connaisances_projet-augmentee
uv sync --all-extras
uv run python scripts/setup.py   # crée .env depuis .env.example
```

### 3 — Configurer `.env`

Ouvrir `.env` et renseigner :

```dotenv
JIRA_URL=https://monorg.atlassian.net
JIRA_TOKEN=votre_token
CONFLUENCE_URL=https://monorg.atlassian.net/wiki
CONFLUENCE_TOKEN=votre_token
NEO4J_PASSWORD=motdepasse_fort

# LLM local (Ollama)
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=mistral:7b

EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

### 4 — Démarrer Neo4j et Ollama

```bash
podman compose up -d
# Attendre ~60s (plugin APOC téléchargé au premier démarrage)
# Browser : http://localhost:7474  login: neo4j / <NEO4J_PASSWORD>

ollama serve &
ollama pull mistral:7b      # ~4 Go — qualité correcte, rapide
# ou : ollama pull qwen2.5:14b  # ~9 Go — meilleure qualité
```

### 5 — Pré-télécharger les modèles d'embeddings

```bash
uv run python -c "
from sentence_transformers import SentenceTransformer, CrossEncoder
SentenceTransformer('BAAI/bge-m3')
CrossEncoder('BAAI/bge-reranker-v2-m3')
print('Modèles HuggingFace prêts.')
"
```

### 6 — Vérifier l'installation

```bash
uv run kb version
uv run pytest -m "not integration"
```

Avec Ollama actif, `kb ingest` et `kb ask` fonctionnent en pipeline complet
automatique (extraction + LLM en une commande).

---

## Profil Windows (py + pip, sans uv, sans Ollama, sans serveur)

C'est le profil de la machine cible typique : IT bloque l'installation
d'Ollama, pas de `uv` ni de `Node.js` disponibles. **Aucun serveur local
n'est démarré, aucun port ouvert.** Le LLM, c'est l'agent choisi dans
Copilot Chat, directement dans la conversation.

### 1 — Créer l'environnement virtuel et installer les dépendances

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1

# Torch CPU d'abord (pip installerait sinon la variante CUDA ~2 Go par défaut)
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install -e ".[dev]"
# Ajouter [revengine] si l'analyse de code source est nécessaire :
#   pip install -e ".[dev,revengine]"
```

### 2 — Créer et configurer `.env`

```powershell
Copy-Item .env.example .env
```

Ouvrir `.env` et renseigner :

```dotenv
JIRA_URL=https://monorg.atlassian.net
JIRA_TOKEN=votre_token
CONFLUENCE_URL=https://monorg.atlassian.net/wiki
CONFLUENCE_TOKEN=votre_token
NEO4J_PASSWORD=motdepasse_fort

# Aucun LLM réseau configuré — normal sur ce profil.
# OLLAMA_BASE_URL / OLLAMA_MODEL peuvent rester aux valeurs par défaut :
# elles ne sont utilisées QUE par kb ingest / kb ask (pipeline auto, non
# utilisé ici). kb extract / kb search / kb ingest-extraction n'appellent
# jamais cet endpoint.

EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

### 3 — Démarrer Neo4j

Si Podman est autorisé par l'IT :

```powershell
podman compose up -d
```

Si Podman n'est pas disponible (WSL2/virtualisation bloquée), installer
Neo4j Desktop ou Neo4j Server directement (sans conteneur) — voir
`.github/prompts/portage_windows_probleme_2.prompt.md` pour la procédure
de repli complète.

### 4 — Pré-télécharger les modèles d'embeddings

```powershell
python -c "
from sentence_transformers import SentenceTransformer, CrossEncoder
SentenceTransformer('BAAI/bge-m3')
CrossEncoder('BAAI/bge-reranker-v2-m3')
print('Modèles HuggingFace prêts.')
"
```
(~5 Go, une seule fois — définir `HF_HOME` dans `.env` si le nom
d'utilisateur Windows contient des espaces, voir `.env.example`.)

### 5 — Le LLM, c'est cette conversation

Rien à démarrer. Utiliser :
- `/kb-ingest` pour construire/mettre à jour la base — Python extrait les
  sources, **toi** (l'agent) fais l'extraction d'entités/relations dans
  cette conversation, Python écrit dans Neo4j.
- `/kb-ask` (ou l'agent `kb-chercheur`) pour interroger la base — Python
  fait le retrieval, **toi** rédiges la réponse à partir du contexte.

Voir ces deux skills pour le détail du flux.

> **Si un endpoint LLM réseau est disponible malgré tout** (Ollama
> accessible, ou serveur d'inférence approuvé par l'IT) : configurer
> `OLLAMA_BASE_URL`/`OLLAMA_MODEL` dans `.env`, et `kb ingest`/`kb ask`
> retrouvent leur comportement automatique en une commande. Le pont
> Copilot (`copilot-bridge/`, extension VS Code avec serveur HTTP local)
> reste disponible en dernier recours — voir
> [kb-copilot-bridge](../kb-copilot-bridge/SKILL.md) — mais n'est **pas**
> recommandé par défaut : il ouvre un port local, ce que le flux
> conversationnel ci-dessus évite entièrement.

### 6 — Vérifier l'installation

```powershell
kb version
# ou si "kb" n'est pas sur le PATH : python -m kb_smart_metering.cli version

python -m pytest -m "not integration"
```

---

## Diagnostics courants

| Symptôme | Cause probable | Solution |
|---|---|---|
| `NEO4J_PASSWORD` manquant | `.env` non créé | `uv run python scripts/setup.py` (ou `Copy-Item .env.example .env` sur le profil py+pip) |
| Neo4j inaccessible | APOC pas encore chargé | Attendre 60s, vérifier `podman logs kb_neo4j` |
| Timeout embeddings | Première exécution, ~5 Go à télécharger | Patience, ou pré-télécharger l'étape dédiée |
| PyTorch installe la variante CUDA (~2 Go) sur Windows | `pip install -e .` sans forcer l'index CPU d'abord | Réinstaller : `pip install torch --index-url https://download.pytorch.org/whl/cpu --force-reinstall` |
| `kb : commande introuvable` (PowerShell) | venv non activé, ou `pip install -e .` non fait | `.venv\Scripts\Activate.ps1` puis `pip install -e ".[dev]"` ; sinon `python -m kb_smart_metering.cli <commande>` |
| `RuntimeError: git not found` | git absent du PATH (Windows) | `winget install Git.Git` ou `GIT_PYTHON_GIT_EXECUTABLE=C:\...\git.exe` dans `.env` |
| `kb ingest`/`kb ask` échoue avec une erreur de connexion | Aucun LLM réseau joignable (normal sur le profil Windows par défaut) | Utiliser `kb extract` + `kb ingest-extraction` (skill `kb-ingest`) et `kb search` (skill `kb-ask`) à la place |
