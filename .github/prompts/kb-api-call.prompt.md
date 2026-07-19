---
description: "Générer un appel curl ou Python vers l'API de kb-smart-metering (POST /search, sans LLM — par défaut ; ou POST /ask, si un LLM réseau est joignable). Utiliser pour : construire une requête API avec filtres temporels (as_of_date), filtres par type d'entité (Decision, Action, Risk…), intégrer l'API dans un script ou une automatisation."
argument-hint: "Question, filtres souhaités (date, type d'entité), endpoint (search|ask), langage (curl|python)"
---

Génère un appel à l'API kb-smart-metering pour la question suivante :

**Question :** $QUESTION

**Paramètres optionnels :**
- `as_of_date` : $DATE_ISO (laisser vide si non applicable)
- `entity_types` : $ENTITY_TYPES (ex: ["Decision", "Action"] — laisser vide pour tout)
- Endpoint : $ENDPOINT (search | ask — search par défaut si non précisé)
- Format de sortie : $FORMAT (curl | python | les deux)

---

Règles pour la génération :

1. L'API tourne sur `http://localhost:8000` par défaut.
2. Deux endpoints disponibles :
   - `POST /search` (défaut, recommandé) — retrieval + contexte assemblé,
     **aucun appel LLM côté serveur**. La réponse contient `contexte` (str) :
     à toi (l'agent, ou le code appelant) de rédiger la réponse structurée
     à partir de ce contexte, exactement comme le skill `kb-ask`.
   - `POST /ask` — pipeline complet avec réponse déjà générée. **Nécessite
     un LLM réseau joignable côté serveur (Ollama)** — échoue sinon avec une
     erreur 500. Réponse : `reponse` (JSON structuré) ET `markdown` (Obsidian).
3. Corps JSON (identique pour les deux) :
   `{"question": "...", "as_of_date": null, "entity_types": null}`
4. Types d'entités valides : `Person`, `Application`, `Component`, `Document`,
   `Ticket`, `Meeting`, `Decision`, `Action`, `BusinessRule`.
5. Format `as_of_date` : ISO 8601, ex: `"2023-12-01T00:00:00"`.

Générer :
- L'appel `curl` commenté
- L'équivalent Python avec `httpx`
- Pour `/search` : un exemple montrant comment lire `data["contexte"]` et
  rédiger la réponse à partir de ce texte (pas de parsing JSON de réponse
  déjà structurée, puisqu'il n'y en a pas)
- Pour `/ask` : un exemple de traitement de la réponse structurée (accéder
  à `.reponse.decisions`, etc.)
