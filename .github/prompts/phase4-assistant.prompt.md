Implémente src/assistant/.

1. llm.py : client OpenAI-compatible pointant sur OLLAMA_BASE_URL.
   Fonction ask(question, contexte) -> ReponseStructuree (Pydantic) :
   {resume, facts[], decisions[], actions[], risks[], sources[]}.
   Prompt système imposant : "réponds UNIQUEMENT à partir du contexte
   fourni ; si l'information est absente, dis-le explicitement".
   Parsing JSON robuste (retry 1 fois en cas de JSON invalide).
2. Chaîne complète : question → retrieval → reranker → contexte →
   LLM → réponse structurée → rendu.
3. CLI typer : `kb ask "question"` avec options --as-of, --type,
   --json / --markdown.
4. API FastAPI : POST /ask (mêmes paramètres), GET /health.
5. Rendu markdown compatible Obsidian :
   # Sujet / ## Résumé / ## Décisions / ## Actions / ## Risques /
   ## Sources (liens cliquables).

Tests : mock du LLM (réponses canned), vérification du schéma.