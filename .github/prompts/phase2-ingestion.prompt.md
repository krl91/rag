Implémente src/ingestion/.

1. Lis d'abord le code de graphiti-core installé dans .venv pour
   vérifier l'API réelle (add_episode, entity_types, etc.).
   Ne suppose rien.
2. Définis les types d'entités custom (Pydantic) : Person, Application,
   Component, Document, Ticket, Meeting, Decision, Action, BusinessRule.
3. pipeline.py : consomme des RawDocument, les découpe en épisodes
   Graphiti (1 ticket = 1 épisode ; 1 page Confluence = 1 épisode par
   version ; 1 réunion = 1 épisode). Passe les entity_types custom.
4. Configure Graphiti pour utiliser le LLM local (endpoint OpenAI-
   compatible, OLLAMA_BASE_URL) et les embeddings BGE-M3 locaux.
5. Idempotence : clé stable par épisode (source_type + id_source +
   version) ; ne pas ré-ingérer un épisode inchangé (hash du contenu
   stocké dans une table de suivi SQLite locale).
6. CLI typer : `kb ingest --source jira --project XXX`,
   `kb ingest --source confluence --space YYY`, etc., avec --dry-run.
7. Journalise le nombre d'entités/relations créées par run.

Livre aussi un test d'intégration désactivable (marqueur pytest
@integration) qui ingère 2 fixtures dans un Neo4j de test.