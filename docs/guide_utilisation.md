# Guide d'utilisation — kb-smart-metering

Système de gestion des connaissances projet pour architectes solution.

---

## ⚡ Quick Start — option A : agent automatique (recommandé)

**Si vous êtes dans VS Code avec GitHub Copilot :**

1. Ouvrir le chat Copilot en mode **Agent** (`⌘⌥I` / `Ctrl+Alt+I`)
2. Sélectionner l'agent **kb-configurateur** dans le sélecteur d'agent
3. L'agent pose les questions, configure `.env`, démarre Neo4j et vérifie tout

> **LLM : optionnel, aucun par défaut.** Le flux normal (`kb-ingest` /
> `kb-ask`) se déroule entièrement dans cette conversation — c'est l'agent
> choisi dans Copilot Chat qui fait le travail d'extraction et de rédaction,
> sans qu'aucun serveur ne tourne et sans qu'aucun port ne soit ouvert.
> Si Ollama est disponible sur la machine, `kb ingest`/`kb ask` proposent en
> plus un pipeline entièrement automatique en une commande — l'agent vous le
> propose s'il détecte Ollama. Un pont Copilot (extension VS Code avec
> serveur HTTP local) existe aussi en option avancée mais n'est **pas**
> recommandé par défaut (voir section 7) : préférer le flux conversationnel.

---

## Quick Start — option B : manuel

### 1. Installer

**Avec `uv` (macOS/Linux, ou Windows si `uv` est disponible) :**
```bash
git clone <url-du-depot> && cd base-de-connaisances_projet-augmentee
uv sync --all-extras
uv run python scripts/setup.py   # crée .env depuis .env.example
```

**Sans `uv` (Windows typique — `py` + `pip` seulement) :**
```powershell
git clone <url-du-depot>
cd base-de-connaisances_projet-augmentee
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev]"
Copy-Item .env.example .env
```

### 2. Configurer `.env`

Ouvrir `.env` et renseigner :

```dotenv
JIRA_URL=https://monorg.atlassian.net
JIRA_TOKEN=votre_token_jira

CONFLUENCE_URL=https://monorg.atlassian.net/wiki
CONFLUENCE_TOKEN=votre_token_confluence

NEO4J_PASSWORD=motdepasse_fort

# LLM : optionnel — laisser les valeurs par défaut si aucun LLM réseau
# n'est disponible (flux conversationnel, voir étapes 4/5 ci-dessous).
# Renseigner uniquement si Ollama est installé sur cette machine :
# OLLAMA_BASE_URL=http://localhost:11434/v1
# OLLAMA_MODEL=mistral:7b
```

### 3. Démarrer Neo4j

```bash
podman compose up -d          # attendre ~60s
```

### 4. Première ingestion

**Sans LLM réseau (flux par défaut — voir skill `kb-ingest` pour le détail) :**
```bash
kb extract --source jira --project SMART --out data/raw/
# Puis, en conversation : lire chaque fichier, extraire entités/relations,
# et écrire avec :
kb ingest-extraction data/raw/extraction_SMART-xxx.json
```

**Avec Ollama configuré (pipeline automatique en une commande) :**
```bash
uv run kb ingest --source jira --project SMART --dry-run  # tester
uv run kb ingest --source jira --project SMART            # ingérer
```

### 5. Poser une question

**Sans LLM réseau (flux par défaut — voir skill `kb-ask`) :**
```bash
kb search "Quelles décisions d'architecture ont été prises ce sprint ?"
# Puis rédiger la réponse en conversation, à partir du contexte affiché.
```

**Avec Ollama configuré :**
```bash
uv run kb ask "Quelles décisions d'architecture ont été prises ce sprint ?"
```

---

## Sommaire

0. [Utiliser les skills Copilot (raccourcis VS Code)](#0-utiliser-les-skills-copilot-raccourcis-vs-code)
1. [Comment ça marche](#1-comment-ça-marche)
2. [Tâches en amont — installation initiale](#2-tâches-en-amont--installation-initiale)
3. [Tâches régulières — maintenir la base à jour](#3-tâches-régulières--maintenir-la-base-à-jour)
4. [Interroger la base — recherche d'information](#4-interroger-la-base--recherche-dinformation)
5. [Module revengine — analyser du code source](#5-module-revengine--analyser-du-code-source)
6. [API HTTP](#6-api-http)
7. [Windows — LLM via le pont Copilot (option avancée, sans Ollama)](#windows--llm-via-le-pont-copilot-option-avancée-sans-ollama)
8. [Résumé des commandes](#8-résumé-des-commandes)

---

## 0. Utiliser les skills Copilot (raccourcis VS Code)

Chaque tâche de ce guide est encodée dans un **skill Copilot** :
un fichier d'instructions que GitHub Copilot charge à la demande pour vous
guider pas à pas, en exécutant les commandes dans votre terminal.

### Comment ouvrir un skill

**Étape 1 — Ouvrir le chat Copilot en mode Agent**

- Raccourci : `⌘⌥I` (macOS) / `Ctrl+Alt+I` (Windows/Linux)
- Ou : icône Copilot dans la barre latérale → sélectionner **"Agent"** dans
  le menu déroulant de mode (pas "Ask" ni "Edit")

**Étape 2 — Choisir un agent ou un skill**

Deux façons d'accéder aux automatisations :

- **Agent** (icône personne dans le sélecteur de mode) → trois agents disponibles :
  - **kb-configurateur** — installation et configuration complète interactive
  - **kb-updater** — mise à jour de la base (demande les sources à ingérer)
  - **kb-chercheur** — recherche d'information dans la base
- **Skill** (taper `/` dans le chat) → accès direct à une tâche précise :

```
/kb-setup          → installation initiale pas à pas
/kb-ingest         → ingestion d'une ou plusieurs sources
/kb-ask            → interroger la base de connaissances
/kb-reveng         → analyser un dépôt de code
/kb-copilot-bridge → configurer le pont Copilot (Windows sans Ollama)
/kb-api-call       → générer un appel API curl/Python
```

**Étape 3 — Ajouter un argument (optionnel) et valider**

L'argument précise le contexte. Exemples ci-dessous.

---

### Exemples concrets par skill

#### `/kb-setup` — première installation

```
Vous tapez :
  /kb-setup macOS

Copilot répond :
  "Je vais vous guider pour l'installation sur macOS.
   Étape 1 — Vérifiez les prérequis..."
  → exécute : python --version, uv --version, podman --version
  → exécute : podman machine init && podman machine start
  → exécute : uv sync --all-extras
  → ouvre .env pour configuration
  → exécute : podman compose up -d
  → exécute : uv run kb version  ← vérification finale
```

Autre exemple : `/kb-setup Windows+GitHub-Models` → guide adapté sans Ollama.

---

#### `/kb-ingest` — ingestion d'une source

```
Vous tapez :
  /kb-ingest fin de sprint

Copilot répond :
  "Pipeline fin de sprint — je vais ingérer Jira, Confluence et la réunion.
   Quel est le projet Jira ? (ex: SMART)"

Vous répondez :
  SMART

Copilot exécute :
  uv run kb ingest --source jira       --project SMART
  uv run kb ingest --source confluence --space ARCH
  uv run kb ingest --source meeting    --path /transcriptions/
  → Résumé : 47 épisodes (45 ingérés, 2 ignorés), 312 entités, 891 relations.
```

Autres exemples :
- `/kb-ingest --source file /docs/livrables/` → ingère un répertoire de PDF/Word
- `/kb-ingest dry-run jira SMART` → teste sans écrire dans Neo4j
- `/kb-ingest onboarding nouveau projet` → pipeline complet d'onboarding

---

#### `/kb-ask` — interroger la base

```
Vous tapez :
  /kb-ask décisions architecture en PR2

Copilot répond :
  "Je vais interroger le graphe avec un filtre temporel PR2 (déc 2023)..."
  → exécute : uv run kb ask "Quelles décisions d'architecture ont été prises en PR2 ?"

  Résultat :
  {
    "resume": "En PR2, trois décisions majeures ont été prises...",
    "decisions": [
      "Adoption de Kafka pour le bus d'événements (réunion du 12/11/2023)",
      "Séparation MDM / concentrateur en deux microservices distincts"
    ],
    "sources": ["reunion_2023-11-12.vtt", "SMART-203", "ARCH/Architecture-PR2"]
  }
```

Autres exemples :
- `/kb-ask actions ouvertes sprint 3` → liste les actions non clôturées
- `/kb-ask risques intégration MDM` → risques identifiés sur ce composant
- `/kb-ask qui a décidé le protocole DLMS` → traçabilité d'une décision

---

#### `/kb-reveng` — analyser un dépôt de code

```
Vous tapez :
  /kb-reveng /repos/compteur-service java

Copilot répond :
  "Je vais analyser le dépôt Java et ingérer l'architecture dans le graphe..."
  → exécute : uv sync --extra revengine
  → exécute : uv run kb reveng --repo /repos/compteur-service --lang java
  → exécute : uv run kb docgen --repo /repos/compteur-service --lang java --out docs/

  "Architecture ingérée. Vous pouvez maintenant interroger le code :"
  → uv run kb ask "Quels composants publient l'événement MeterReadingReceived ?"
```

---

#### `/kb-copilot-bridge` — configurer le pont Copilot (Windows sans Ollama)

```
Vous tapez :
  /kb-copilot-bridge gpt-4o

Copilot répond :
  "Je vais configurer le pont Copilot comme LLM (extension VS Code
   copilot-bridge/, aucun token à créer).
   Étape 1 — cd copilot-bridge && npm install && npm run compile
   Étape 2 — Charger l'extension (F5, ou vsce package + install)
   Étape 3 — Palette de commandes → 'KB Bridge: Démarrer le pont Copilot'"

Copilot continue :
  "Mettez à jour votre .env :"
  OLLAMA_BASE_URL=http://127.0.0.1:4141/v1
  OLLAMA_MODEL=gpt-4o
  LLM_API_KEY=

  → vérifie la connexion : GET http://127.0.0.1:4141/health
```

---

#### `/kb-api-call` — générer un appel API

```
Vous tapez :
  /kb-api-call risques sur le module Export, filtré Decision et Risk

Copilot génère (endpoint /search par défaut — sans LLM réseau) :
  # curl
  curl -X POST http://localhost:8000/search \
    -H "Content-Type: application/json" \
    -d '{
      "question": "Quels sont les risques sur le module Export ?",
      "entity_types": ["Decision", "Risk"]
    }'

  # Python (httpx)
  import httpx
  r = httpx.post("http://localhost:8000/search", json={
      "question": "Quels sont les risques sur le module Export ?",
      "entity_types": ["Decision", "Risk"],
  })
  data = r.json()
  print(data["contexte"])   # à rédiger en réponse structurée, voir skill kb-ask

  # Avec Ollama configuré, remplacer /search par /ask pour une réponse déjà
  # générée : data["reponse"]["risks"] et data["markdown"]
```

---

### Chargement automatique

Copilot peut charger un skill **sans slash command** si la conversation
est clairement dans son domaine. Exemples de phrases qui déclenchent le chargement :

| Ce que vous écrivez | Skill chargé automatiquement |
|---|---|
| "je veux ingérer les tickets Jira" | `kb-ingest` |
| "comment installer le projet sur Windows ?" | `kb-setup` (flux conversationnel par défaut ; `kb-copilot-bridge` seulement en option avancée) |
| "quelles décisions ont été prises en PR3 ?" | `kb-ask` |
| "analyser le dépôt Java du concentrateur" | `kb-reveng` |

---

### Architecture du pipeline

```
Sources                    Ingestion                    Stockage
──────                     ─────────                    ────────
Jira           ──┐
Confluence     ──┤
Git            ──┤──► RawDocument ──► IngestionPipeline ──► Graphiti ──► Neo4j
Word/PDF/Excel ──┤                         (idempotent)      (graphe        (graphe
Réunions       ──┘                                           temporel)      + vecteurs)

                    Requête
                    ───────
                    kb ask "question"
                         │
                         ▼
                  Retrieval hybride        ← Neo4j (graphe + vecteurs BGE-M3)
                  (sémantique + BM25       ← Filtres temporels (as_of_date)
                   + traversée graphe)     ← Filtres par type d'entité
                         │
                    top 20 candidats
                         │
                         ▼
                  Reranker BGE-reranker-v2-m3
                         │
                    top 8 candidats
                         │
                         ▼
                  Contexte minimal assemblé
                         │
                         ▼
                  LLM local (Ollama, 3–14B)
                         │
                         ▼
                  Réponse structurée JSON
                  {resume, facts, decisions,
                   actions, risks, sources}
```

### Principe clé : connaissance temporelle

Chaque fait conserve `valid_from` et `valid_to`.
Cela permet de poser des questions datées :
> "Quelle était l'architecture en PR2 ?" — le système filtre automatiquement
> les faits valides à cette date.

### Idempotence

Une base SQLite locale (`data/ingestion_tracking.db`) conserve le hash de
chaque document ingéré. Réexécuter une ingestion ne crée pas de doublons :
seuls les documents **modifiés** sont ré-ingérés.

### Entités du domaine reconnues

| Entité       | Exemples d'extraction automatique                            |
|--------------|--------------------------------------------------------------|
| Person       | Participants d'une réunion, assignees Jira                   |
| Application  | Systèmes cités dans Confluence ou les commits                |
| Component    | Microservices, modules identifiés dans le code               |
| Document     | Pages Confluence, fichiers PDF/Word                          |
| Ticket       | Issues Jira (key, summary, status)                           |
| Meeting      | Transcriptions de réunions                                   |
| Decision     | Décisions extraites du texte par le LLM                      |
| Action       | Actions à réaliser identifiées                               |
| BusinessRule | Règles métier extraites                                      |

---

## 2. Tâches en amont — installation initiale

### Étape 1 — Prérequis

Vérifier que ces outils sont installés :

```bash
python --version    # 3.11+
uv --version        # dernière stable
podman --version    # 4.x+  (ou podman machine start sur macOS)
ollama --version    # dernière stable
```

Sur macOS, initialiser la machine Podman **une seule fois** :

```bash
podman machine init
podman machine start
```

### Étape 2 — Installer l'environnement Python

```bash
# Clone du dépôt
git clone <url-du-depot>
cd base-de-connaisances_projet-augmentee

# Installe toutes les dépendances (core + dev + revengine)
make setup
# Équivalent Windows : .\make.ps1 setup
```

`make setup` fait deux choses :
- `uv sync --all-extras` — installe les dépendances Python
- `uv run python scripts/setup.py` — copie `.env.example` → `.env`

### Étape 3 — Configurer `.env`

Ouvrir le fichier `.env` créé et renseigner les variables :

```dotenv
# Jira
JIRA_URL=https://monorg.atlassian.net
JIRA_TOKEN=votre_token_personnel

# Confluence
CONFLUENCE_URL=https://monorg.atlassian.net/wiki
CONFLUENCE_TOKEN=votre_token_personnel

# Neo4j (valeur de votre choix, doit correspondre au compose.yml)
NEO4J_PASSWORD=motdepasse_fort

# Ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=mistral:7b          # ou qwen2.5:14b, llama3.2:3b, etc.

# Embeddings et reranking (valeurs par défaut recommandées)
EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

Pour récupérer le token Jira/Confluence :
→ Atlassian : *Account Settings → Security → API tokens*

### Étape 4 — Démarrer Neo4j

```bash
make up
# Équivalent Windows : .\make.ps1 up
```

Attendre ~60 secondes (le plugin APOC se télécharge au premier démarrage).
Vérifier : [http://localhost:7474](http://localhost:7474) → login `neo4j` /
valeur de `NEO4J_PASSWORD`.

### Étape 5 — Démarrer Ollama et télécharger un modèle

```bash
# Démarrer le serveur Ollama (s'il ne tourne pas en arrière-plan)
ollama serve &

# Télécharger le modèle choisi (une seule fois)
ollama pull mistral:7b
# ou pour de meilleures performances :
ollama pull qwen2.5:14b
```

### Étape 6 — Premier téléchargement des modèles d'embeddings

Les modèles HuggingFace sont téléchargés **automatiquement** au premier appel.
Pour les pré-télécharger explicitement (~5 Go au total) :

```bash
uv run python -c "
from sentence_transformers import SentenceTransformer, CrossEncoder
SentenceTransformer('BAAI/bge-m3')
CrossEncoder('BAAI/bge-reranker-v2-m3')
print('Modèles téléchargés.')
"
```

### Étape 7 — Vérifier l'installation

```bash
# Tests unitaires (hors intégration)
make test

# Vérifier le CLI
uv run kb version

# Vérifier l'API
uv run uvicorn kb_smart_metering.api.app:app --reload &
curl http://localhost:8000/health
```

---

## 3. Tâches régulières — maintenir la base à jour

### Ingestion Jira

À faire : après chaque sprint, ou quotidiennement si les tickets changent souvent.

```bash
# Ingérer tous les tickets d'un projet Jira
uv run kb ingest --source jira --project SMART

# Tester sans écrire dans Neo4j (dry-run)
uv run kb ingest --source jira --project SMART --dry-run

# Isoler dans une partition du graphe (utile pour multi-projet)
uv run kb ingest --source jira --project INFRA --group-id infra_project
```

> **Idempotence** : les tickets non modifiés depuis la dernière ingestion
> sont ignorés automatiquement. Seuls les tickets nouveaux ou modifiés
> sont traités.

### Ingestion Confluence

À faire : après chaque publication ou mise à jour de page importante.

```bash
# Ingérer toutes les pages d'un espace Confluence
uv run kb ingest --source confluence --space ARCH

# Autre espace
uv run kb ingest --source confluence --space TECH
```

### Ingestion Git

À faire : après chaque sprint ou livraison.

```bash
# Ingérer l'historique de commits d'un dépôt
uv run kb ingest --source git --path /chemin/vers/mon-repo

# Plusieurs dépôts : relancer la commande pour chacun
uv run kb ingest --source git --path /repos/backend
uv run kb ingest --source git --path /repos/frontend
```

### Ingestion de fichiers (Word, PDF, Excel)

À faire : après réception ou mise à jour d'un document.

```bash
# Un seul fichier
uv run kb ingest --source file --path /docs/spec_technique_v3.docx
uv run kb ingest --source file --path /docs/cahier_charges.pdf
uv run kb ingest --source file --path /docs/matrice_risques.xlsx

# Tout un répertoire (tous les formats supportés en une commande)
uv run kb ingest --source file --path /docs/livrables/
```

Formats supportés : `.docx`, `.pdf`, `.xlsx`, `.xls`

### Ingestion de réunions (transcriptions)

À faire : après chaque réunion dont la transcription est disponible.

```bash
# Un seul fichier de transcription
uv run kb ingest --source meeting --path /transcriptions/reunion_2024-01-15.txt
uv run kb ingest --source meeting --path /transcriptions/sprint_review_vtt/reunion_teams.vtt

# Tout un répertoire de transcriptions
uv run kb ingest --source meeting --path /transcriptions/2024/
```

Formats supportés : `.txt` (transcription brute), `.vtt` (Teams/Zoom)

### Fréquences recommandées

| Source       | Fréquence suggérée         | Déclencheur naturel               |
|--------------|----------------------------|-----------------------------------|
| Jira         | Quotidien ou hebdomadaire  | Fin de sprint / changement statut |
| Confluence   | Hebdomadaire               | Après mise à jour de page         |
| Git          | À chaque livraison         | Tag de version / fin de sprint    |
| Fichiers     | À la réception             | Nouveau document partagé          |
| Réunions     | Dans les 24h               | Après la réunion                  |

---

## 4. Interroger la base — recherche d'information

### Commande de base

```bash
uv run kb ask "votre question"
```

La réponse est structurée et affichée sous forme JSON + Markdown Obsidian :

```json
{
  "resume": "Résumé de la réponse",
  "facts": ["Fait 1 extrait du graphe", "Fait 2..."],
  "decisions": ["Décision prise lors de la réunion du 12/03"],
  "actions": ["Action assignée à X pour le sprint 3"],
  "risks": ["Risque identifié : dépendance externe Y"],
  "sources": ["SMART-142", "Confluence:ARCH/Integration", "reunion_2024-01-15.txt"]
}
```

### Filtres temporels — questions datées

Le système reconnaît automatiquement les phases projet dans la question :

```bash
# Filtrage automatique par phase (détection dans la question)
uv run kb ask "Quelle était l'architecture de communication en PR2 ?"
uv run kb ask "Quelles décisions ont été prises pendant le sprint 3 ?"

# Phases reconnues automatiquement : PR1, PR2, PR3, PR4, sprint1 à sprint4
```

Pour une date précise :

```bash
# Via l'API (voir section API) : passer as_of_date en ISO 8601
# Ex : {"question": "...", "as_of_date": "2023-12-01T00:00:00"}
```

### Filtres par type d'entité — questions ciblées

Via l'API, restreindre la recherche à certains types d'entités :

```json
{
  "question": "Quelles sont les décisions d'architecture prises ?",
  "entity_types": ["Decision"]
}
```

Types disponibles : `Person`, `Application`, `Component`, `Document`,
`Ticket`, `Meeting`, `Decision`, `Action`, `BusinessRule`

### Exemples de questions efficaces

#### Décisions et arbitrages

```bash
uv run kb ask "Quelles décisions d'architecture ont été prises sur le module Export ?"
uv run kb ask "Pourquoi a-t-on choisi Kafka plutôt que RabbitMQ ?"
uv run kb ask "Qui a validé la décision sur le protocole DLMS ?"
```

#### Suivi d'actions

```bash
uv run kb ask "Quelles actions sont assignées à l'équipe architecture ?"
uv run kb ask "Quelles actions du sprint 2 n'ont pas été clôturées ?"
uv run kb ask "Quels tickets Jira concernent la performance du concentrateur ?"
```

#### Risques et problèmes

```bash
uv run kb ask "Quels sont les risques identifiés sur l'intégration MDM ?"
uv run kb ask "Y a-t-il des dépendances critiques non résolues ?"
```

#### Architecture et technique

```bash
uv run kb ask "Comment fonctionne l'interface entre le compteur et le concentrateur ?"
uv run kb ask "Quelle version de l'API expose le service de relevé ?"
uv run kb ask "Quels composants consomment l'événement MeterReadingReceived ?"
```

#### Réunions et historique

```bash
uv run kb ask "Qu'a-t-on décidé lors de la réunion du 15 janvier 2024 ?"
uv run kb ask "Quels sujets ont été abordés dans les réunions de sprint review ?"
uv run kb ask "Quelle est la dernière mise à jour de la page d'architecture Confluence ?"
```

### Conseils pour des questions efficaces

| À faire                                         | À éviter                            |
|-------------------------------------------------|-------------------------------------|
| Questions précises avec contexte                | Questions vagues ("dis-moi tout")   |
| Mentionner la phase / sprint pour filtrer       | Questions hors périmètre du projet  |
| Utiliser les noms exacts (application, ticket)  | Questions hypothétiques générales   |
| Citer le type de réponse souhaité (décision…)   | Demander des documents complets     |

> **Principe clé** : le LLM ne répond que sur la base du contexte extrait
> du graphe. Si l'information n'a pas été ingérée, il le dit explicitement.
> En cas de réponse vide ou pauvre, vérifier que la source a bien été ingérée.

---

## 5. Module revengine — analyser du code source

> **Prérequis** : installer l'extra `revengine` si ce n'est pas déjà fait :
> ```bash
> uv sync --extra revengine
> ```

### Rétro-ingénierie d'un dépôt

Analyse statique AST (classes, méthodes, appels, événements publiés/consommés)
et ingestion dans le graphe de connaissances.

```bash
# Analyser et ingérer un dépôt Java
uv run kb reveng --repo /repos/compteur-service --lang java

# Python
uv run kb reveng --repo /repos/data-pipeline --lang python

# C#
uv run kb reveng --repo /repos/mdm-client --lang csharp

# Langages supportés : java | python | csharp
```

Après ingestion, les questions sur l'architecture du code sont disponibles :

```bash
uv run kb ask "Quels composants publient l'événement MeterReadingReceived ?"
uv run kb ask "Quelles méthodes de ExportService appellent le MDM ?"
```

### Génération de documentation Markdown

Génère des fiches de documentation par module au format Markdown/Obsidian.

```bash
# Générer la doc de tous les modules d'un dépôt
uv run kb docgen --repo /repos/compteur-service --lang java --out docs/generated/

# Cibler un module précis
uv run kb docgen --repo /repos/compteur-service --lang java --module ExportService --out docs/

# Python
uv run kb docgen --repo /repos/data-pipeline --lang python --out docs/generated/
```

Les fichiers Markdown générés sont compatibles avec un vault Obsidian :
frontmatter YAML + sections structurées (classes, méthodes, dépendances, événements).

---

## 6. API HTTP

Démarrer le serveur :

```bash
uv run uvicorn kb_smart_metering.api.app:app --reload
# Swagger UI : http://localhost:8000/docs
```

### `GET /health` — vérification de l'état

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

### `POST /search` — retrieval + contexte, SANS appel LLM (par défaut, recommandé)

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Quelles décisions ont été prises sur le module Export ?"
  }'
```

La réponse contient uniquement `contexte` (texte assemblé) — aucun LLM
n'est appelé côté serveur. C'est au client (agent, script) de rédiger la
réponse structurée à partir de ce contexte, comme le fait l'agent Copilot
via le skill `kb-ask`/`kb-chercheur`.

Mêmes filtres que `/ask` ci-dessous (`as_of_date`, `entity_types`).

### `POST /ask` — poser une question, réponse générée par LLM (nécessite Ollama)

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Quelles décisions ont été prises sur le module Export ?"
  }'
```

**Échoue avec une erreur 500 si aucun LLM réseau n'est joignable** — utiliser
`/search` ci-dessus dans ce cas.

Avec filtre temporel :

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Quelle était l'\''architecture en fin PR2 ?",
    "as_of_date": "2023-12-01T00:00:00"
  }'
```

Avec filtre par type d'entité :

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Quels sont les risques identifiés ?",
    "entity_types": ["BusinessRule", "Decision"]
  }'
```

La réponse inclut `reponse` (JSON structuré) **et** `markdown`
(rendu Obsidian prêt à coller dans un vault).

---

## Windows — LLM via le pont Copilot (option avancée, sans Ollama)

> **Option avancée, déconseillée par défaut.** Sur Windows sans Ollama, le
> flux recommandé est le **flux conversationnel** (skills `kb-ingest` /
> `kb-ask`, section 2 et section "Quick Start" ci-dessus) : aucun serveur,
> aucun port ouvert. Le pont décrit dans cette section ouvre un serveur HTTP
> local (port 4141) — à réserver aux cas où un pipeline automatique en une
> commande est explicitement requis, en acceptant ce compromis sécurité.

Le **pont Copilot** est une extension VS Code incluse dans ce dépôt
(`copilot-bridge/`) qui expose GitHub Copilot Chat comme un serveur HTTP
local compatible OpenAI, via l'API publique `vscode.lm` (pas de
rétro-ingénierie d'endpoint privé).

> **GitHub Models est retiré.** L'ancienne alternative basée sur un token
> `models:read` et l'endpoint `models.inference.ai.azure.com` /
> `models.github.ai` a été arrêtée par GitHub le 30/07/2026. Ne plus
> l'utiliser — l'endpoint ne répond plus, quel que soit le token.

### Différences avec Ollama

| Critère              | Ollama local              | Pont Copilot                       |
|----------------------|---------------------------|-------------------------------------|
| Installation         | `ollama serve`            | Extension VS Code (`copilot-bridge/`), Node.js 20+ |
| GPU / RAM            | ~4–16 Go selon le modèle  | Aucune (inférence via Copilot)     |
| Auth                 | Aucune                    | Aucune (session Copilot déjà ouverte dans VS Code) |
| Disponibilité        | Service headless permanent | **Uniquement si VS Code est ouvert et le pont démarré** |
| Confidentialité      | 100 % local               | Données envoyées à Copilot Chat (GitHub/Microsoft) |
| Qualité              | 3–14B selon modèle choisi | Modèle sélectionné dans Copilot (ex. gpt-4o) |
| Consommation         | Aucune limite              | Compte dans le quota de requêtes Copilot de l'utilisateur |

> **Important** : les questions posées et les extraits de contexte transitent
> par Copilot Chat (infrastructure GitHub/Microsoft). Ne pas utiliser avec
> des données confidentielles si votre politique de sécurité l'interdit.
> Pour l'ingestion en masse (Phase 2), préférer des lots réduits et
> incrémentaux (`--updated-since`) pour ménager le quota Copilot.

### Étape 1 — Installer et démarrer l'extension

Prérequis : [Node.js](https://nodejs.org/) 20+.

```powershell
cd copilot-bridge
npm install
npm run compile
```

Charger l'extension dans VS Code :
- **Développement** : ouvrir `copilot-bridge/` dans VS Code, appuyer sur **F5**
- **Usage durable** : `npx vsce package` puis
  `code --install-extension kb-copilot-bridge-0.1.0.vsix`

Puis : palette de commandes (`Ctrl+Shift+P`) →
**"KB Bridge: Démarrer le pont Copilot"**. La barre de statut affiche
`KB Bridge :4141` une fois démarré.

### Étape 2 — Configurer `.env`

```dotenv
# Option A — Ollama (commenter si pas disponible)
# OLLAMA_BASE_URL=http://localhost:11434/v1
# OLLAMA_MODEL=mistral:7b

# Option B — Pont Copilot (décommenter les 3 lignes)
OLLAMA_BASE_URL=http://127.0.0.1:4141/v1
OLLAMA_MODEL=gpt-4o
LLM_API_KEY=
```

Modèle disponible : dépend de l'abonnement Copilot de l'utilisateur —
vérifier avec `GET http://127.0.0.1:4141/v1/models` une fois le pont démarré.

### Étape 3 — Vérifier la connexion

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:4141/health"

Invoke-RestMethod `
  -Uri "http://127.0.0.1:4141/v1/chat/completions" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"model":"gpt-4o","messages":[{"role":"user","content":"ping"}]}'
```

### Embeddings : toujours en local

Les embeddings (BGE-M3) et le reranker (BGE-reranker-v2-m3) **restent locaux**
(via `sentence-transformers`). Seul le LLM est déporté vers Copilot Chat.
Le comportement du pipeline ne change pas.

Détails complets (diagnostics, configuration avancée) :
`.github/skills/kb-copilot-bridge/SKILL.md` et `copilot-bridge/README.md`.

---

## 8. Résumé des commandes

```bash
# --- Infrastructure ---
make setup              # Installation initiale (une seule fois) — .\make.ps1 setup sur
                         # Windows ; détecte l'absence de uv et bascule sur py+pip
make up                 # Démarrer Neo4j
make down                # Arrêter Neo4j
make test                # Lancer les tests
make lint                # Vérifier le style et les types

# --- Ingestion — SANS LLM réseau (par défaut, voir skill kb-ingest) ---
kb extract --source jira       --project KEY --out data/raw/
kb extract --source confluence --space   KEY --out data/raw/
kb extract --source git        --path    /repo --out data/raw/
kb extract --source file       --path    /doc_ou_repertoire --out data/raw/
kb extract --source meeting    --path    /transcription_ou_repertoire --out data/raw/
# → l'agent lit chaque fichier, extrait entités/relations, puis :
kb ingest-extraction data/raw/extraction_XXX.json [--dry-run]

# --- Ingestion — AVEC Ollama (pipeline automatique en une commande) ---
uv run kb ingest --source jira       --project KEY
uv run kb ingest --source confluence --space   KEY
uv run kb ingest --source git        --path    /repo
uv run kb ingest --source file       --path    /doc_ou_repertoire
uv run kb ingest --source meeting    --path    /transcription_ou_repertoire
# Options communes : --group-id NOM (défaut: smart_metering), --dry-run

# --- Interrogation — SANS LLM réseau (par défaut, voir skill kb-ask) ---
kb search "question en langage naturel"   # affiche le contexte ; l'agent rédige la réponse

# --- Interrogation — AVEC Ollama ---
uv run kb ask "question en langage naturel"   # réponse déjà générée

# --- Rétro-ingénierie (nécessite l'extra revengine, voir skill kb-reveng) ---
# Sans LLM :
kb reveng --repo /repo --lang java|python|csharp --out data/raw/
kb docgen --repo /repo --lang java|python|csharp --out data/raw-docgen/ --extract-only
kb docgen --repo /repo --lang java|python|csharp --from-extraction <fichier>.json --out docs/
# Avec Ollama :
uv run kb reveng --repo /repo --lang java|python|csharp
uv run kb docgen --repo /repo --lang java|python|csharp [--module NOM] [--out docs/]

# --- API ---
uv run uvicorn kb_smart_metering.api.app:app --reload
# GET  http://localhost:8000/health
# POST http://localhost:8000/search   — sans LLM réseau (défaut, recommandé)
# POST http://localhost:8000/ask      — avec LLM réseau (Ollama)
```
