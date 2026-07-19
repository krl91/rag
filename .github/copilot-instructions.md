# Instructions projet — kb-smart-metering

## Mission
Système de gestion des connaissances projet pour architectes solution
(industrie smart metering). Sources : Jira, Confluence, Git, transcriptions
de réunions, documents Word/Excel/PDF, notes Obsidian. Mémoire centrale :
Neo4j (graphe de connaissances temporel, via graphiti-core pour le modèle
d'entités/relations et le retrieval).

## LLM : optionnel, jamais un service réseau obligatoire
- Par défaut, **aucun LLM réseau n'est requis**. Le flux normal se déroule
  entièrement dans la conversation VS Code : c'est l'agent choisi dans
  Copilot Chat (mode Agent) qui fait le travail de compréhension du texte
  (extraction d'entités/relations à l'ingestion, rédaction de la réponse à
  la recherche) — jamais un appel HTTP Python vers un serveur externe.
- **Ne jamais proposer, créer ou faire tourner un serveur HTTP local ni
  ouvrir un port** pour servir de LLM à l'application. C'est un choix
  délibéré (surface de sécurité) — y compris en loopback (127.0.0.1).
  L'extension `copilot-bridge/` (serveur HTTP local optionnel) existe déjà
  dans le dépôt à titre d'option avancée explicitement déconseillée par
  défaut ; ne pas l'utiliser ni la recommander sauf demande explicite de
  l'utilisateur en connaissance de cause.
- Si Ollama (ou tout endpoint OpenAI-compatible réellement joignable) est
  disponible sur la machine, il reste utilisable en complément — configuré
  via `OLLAMA_BASE_URL`/`OLLAMA_MODEL`/`LLM_API_KEY` — pour un pipeline
  automatique en une commande (`kb ingest`, `kb ask`, `kb docgen`). Mais ce
  n'est jamais un prérequis : les commandes équivalentes sans LLM
  (`kb extract` + `kb ingest-extraction`, `kb search`, `kb reveng --out` +
  `kb docgen --extract-only`/`--from-extraction`) doivent toujours
  fonctionner et rester la référence par défaut.
- GitHub Models (service tiers basé sur un token `models:read`) a été
  retiré par GitHub le 30/07/2026 — ne jamais le proposer ni y faire
  référence comme option viable.

## Contraintes techniques
- Python 3.11+. Gestion de dépendances : `uv` si disponible, sinon `py`
  (Python launcher Windows) + `pip` dans un environnement virtuel
  (`py -m venv .venv`). Ne jamais supposer `uv` présent sur la machine
  cible — toujours vérifier, et fournir l'équivalent `py`/`pip` dans toute
  documentation ou script généré. Ne jamais supposer `Node.js` présent non
  plus (uniquement nécessaire pour l'extension `copilot-bridge/` optionnelle).
- Typage strict : Pydantic v2 pour tous les modèles de données.
- Bibliothèques imposées :
  - graphiti-core (modèles d'entités/relations EntityNode/EntityEdge,
    retrieval hybride graphe+vecteurs). L'extraction/résolution LLM
    automatique de graphiti-core (`add_episode`, `add_episode_bulk`,
    `add_triplet`) exige un `llm_client` réseau joignable — ne l'utiliser
    que dans le chemin "Ollama disponible". Le chemin par défaut écrit
    directement via `add_nodes_and_edges_bulk` (voir
    `ingestion/graph_writer.py`), sans passer par ces méthodes.
  - neo4j (driver officiel)
  - atlassian-python-api (Jira + Confluence)
  - GitPython (dépôts Git)
  - python-docx, openpyxl, pymupdf (Word, Excel, PDF)
  - sentence-transformers (embeddings BGE-M3 + reranker BGE-reranker-v2-m3)
    — toujours locaux, jamais réseau, quelle que soit la config LLM.
  - fastapi + typer (API et CLI)
  - tree-sitter + tree-sitter-language-pack (analyse statique)
- LLM (si utilisé) : appels via endpoint OpenAI-compatible configurable
  (OLLAMA_BASE_URL). Jamais d'appel direct à OpenAI/Anthropic cloud.
- Secrets uniquement via variables d'environnement (.env, python-dotenv).
  Ne jamais écrire de token en dur.
- Conteneurs : Podman exclusivement (rootless). Utiliser `podman compose`
  dans tous les scripts et Makefile, jamais la commande `docker`. Si Podman
  n'est pas disponible sur la machine (bloqué par l'IT), prévoir un repli
  Neo4j sans conteneur plutôt que de bloquer.
  Références d'images toujours qualifiées (docker.io/library/neo4j:5,
  pas neo4j:5).

## Principes d'architecture
1. Deux chemins d'ingestion, tous deux valides :
   - **Par défaut (sans LLM réseau)** : Extraction (`kb extract`) →
     Normalisation (RawDocument JSON) → **extraction d'entités/relations
     par l'agent, dans la conversation** → Écriture Neo4j déterministe
     (`kb ingest-extraction`, `ingestion/graph_writer.py`) → Retrieval
     (`kb search`) → Reranker → **rédaction de la réponse par l'agent**.
   - **Si Ollama disponible** : Extraction → Normalisation → Ingestion
     Graphiti automatique (`kb ingest`) → Retrieval → Reranker → LLM
     (`kb ask`) → Réponse.
2. Le LLM (qu'il s'agisse d'Ollama ou de l'agent en conversation) ne reçoit
   JAMAIS un document complet : uniquement un contexte minimal assemblé par
   le retrieval, ou les éléments structurels d'UN module pour revengine.
3. Toute connaissance est temporelle : conserver valid_at/invalid_at (edges)
   ou l'équivalent, ne jamais écraser une version antérieure.
4. Réponses en JSON structuré : {resume, facts, decisions, actions, risks,
   sources}. Toujours valider avec Pydantic (`ReponseStructuree`).
5. Entités du domaine (9 types, voir `models/entities.py` et
   `ingestion/extraction_schema.py`) : Person, Application, Component,
   Document, Ticket, Meeting, Decision, Action, BusinessRule.
6. Chaque fait ingéré garde une référence à sa source
   (URL Jira/Confluence, commit SHA, chemin fichier + page).
7. Idempotence par clé métier stable, pas par résolution floue : dans le
   flux sans LLM, c'est l'agent qui réutilise la même `key` locale pour une
   entité déjà rencontrée (dans la même conversation) — Python ne fait
   qu'un upsert déterministe sur cette clé.

## Style de code
- Fonctions courtes, docstrings en français, logs via logging (pas print).
- Tests pytest pour chaque extracteur avec fixtures (pas d'appel réseau
  dans les tests : mocker les API, y compris `add_nodes_and_edges_bulk`).
- Idempotence : réexécuter une ingestion ne doit pas dupliquer les nœuds.

## Ce que tu ne dois PAS faire
- Ne pas inventer d'API : vérifier les signatures de graphiti-core avant
  de coder (lire le code source dans .venv si nécessaire).
- Ne pas générer de code pour des sources non demandées dans la phase
  en cours.
- Ne pas refactorer du code existant hors du périmètre de la phase.
- Ne pas créer de serveur HTTP ni ouvrir de port pour servir de LLM local
  (voir section LLM ci-dessus).
- Ne pas supposer `uv` ou `Node.js` disponibles sans les avoir vérifiés.
