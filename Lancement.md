Initialise le projet

Périmètre STRICT de cette session :
1. Arborescence complète du dépôt (voir copilot-instructions.md),
   avec des __init__.py et des modules vides documentés.
2. pyproject.toml (uv) avec toutes les dépendances listées dans les
   instructions, versions épinglées.
3. compose.yml compatible Podman : Neo4j 5.x (image
   docker.io/library/neo4j:5, plugin APOC, volumes nommés persistants,
   ports 7474/7687), healthcheck. Pas de directives spécifiques
   Docker Desktop.
4. .env.example documenté : JIRA_URL, JIRA_TOKEN, CONFLUENCE_URL,
   CONFLUENCE_TOKEN, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
   OLLAMA_BASE_URL, OLLAMA_MODEL, EMBEDDING_MODEL, RERANKER_MODEL.
5. src/config.py : chargement Pydantic Settings de la configuration.
6. Makefile : make setup, make up (podman compose up -d),
   make down, make test, make lint. Variable CONTAINER_ENGINE
   surchargeable (défaut : podman).
7. README.md minimal : prérequis (dont `podman machine init/start`
   sur macOS), installation, démarrage Neo4j.

Ne code AUCUN extracteur, AUCUNE logique métier. Termine en listant
ce qui sera fait en Phase 1.