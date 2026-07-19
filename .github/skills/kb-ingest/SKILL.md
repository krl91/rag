---
name: kb-ingest
description: "Ingestion de sources dans la base de connaissances kb-smart-metering, entièrement pilotée depuis la conversation VS Code (aucun serveur, aucun LLM réseau requis). Utiliser pour : ingérer des tickets Jira, pages Confluence, commits Git, fichiers Word/PDF/Excel, transcriptions de réunions. C'est TOI (l'agent choisi dans Copilot Chat) qui fais l'extraction d'entités/relations — Python ne fait que l'extraction brute des sources et l'écriture finale dans Neo4j."
argument-hint: "Source (jira|confluence|git|file|meeting) + paramètres"
---

# Skill — Ingestion de sources (flux conversationnel, sans LLM réseau)

## Principe — pourquoi ce flux en 3 étapes

L'ancienne approche (`kb ingest --source ...` seul) faisait extraire les
entités par un LLM appelé automatiquement en HTTP par Python (Ollama ou un
service équivalent). Sur la machine cible, il n'y a ni Ollama, ni serveur
local, ni port ouvert — la seule IA disponible est **toi**, dans cette
conversation VS Code.

Le pipeline est donc scindé en 3 étapes, toutes déclenchées par des tool
calls que tu exécutes dans cette conversation :

```
[1. kb extract]         [2. TOI : extraction]        [3. kb ingest-extraction]
Python — I/O pure   →   entités/relations JSON   →   Python — écriture Neo4j
(aucun LLM)              (ton travail de lecture)      (aucun LLM)
```

Aucune commande de cette phase n'appelle jamais un LLM réseau — c'est TOI
qui fais le travail de compréhension du texte, directement dans cette
conversation.

---

## Étape 1 — Extraire les documents bruts (Python, aucun LLM)

```bash
py -m kb_smart_metering.cli extract --source jira --project SMART --out data/raw/
py -m kb_smart_metering.cli extract --source confluence --space ARCH --out data/raw/
py -m kb_smart_metering.cli extract --source git --path /repos/compteur-service --out data/raw/
py -m kb_smart_metering.cli extract --source file --path /docs/spec.docx --out data/raw/
py -m kb_smart_metering.cli extract --source meeting --path /transcriptions/reunion.vtt --out data/raw/
```

(Sur une machine avec `uv`, `uv run kb extract ...` fonctionne aussi de façon équivalente.)

Cette commande écrit un fichier JSON (`RawDocument`) par document dans
`data/raw/` — titre, contenu texte brut, métadonnées, source. Aucune
écriture dans Neo4j à cette étape.

---

## Étape 2 — Extraire entités et relations (TON travail, dans la conversation)

Pour **chaque** fichier `data/raw/*.json` :

1. Lis le fichier (tool call de lecture).
2. Identifie les entités mentionnées, chacune avec un des **9 types** du domaine :
   `Person`, `Application`, `Component`, `Document`, `Ticket`, `Meeting`,
   `Decision`, `Action`, `BusinessRule`.
3. Identifie les relations entre ces entités (qui concerne quoi, qui décide
   quoi, qui est assigné à quoi…).
4. Produis un JSON conforme au schéma `ExtractionResult`
   (`src/kb_smart_metering/ingestion/extraction_schema.py`) :

```json
{
  "source_ref": "jira:SMART-74743:2026-07-10T00:00:00+00:00",
  "entities": [
    {
      "key": "smart_74743",
      "type": "Ticket",
      "name": "SMART-74743",
      "summary": "Suppression de l'export des Missing Data",
      "attributes": { "ticket_key": "SMART-74743", "status": "En cours" }
    },
    {
      "key": "unity_water",
      "type": "Application",
      "name": "Unity Water",
      "summary": "Client final concerné par le ticket",
      "attributes": {}
    }
  ],
  "relations": [
    {
      "source_key": "smart_74743",
      "target_key": "unity_water",
      "name": "concerne",
      "fact": "Le ticket SMART-74743 concerne l'application Unity Water.",
      "valid_at": "2026-07-10T00:00:00+00:00"
    }
  ]
}
```

Règles importantes :
- **`source_ref`** : reprends exactement l'identifiant du RawDocument
  (`{source_type}:{id_source}`, plus la date de modification si connue) —
  c'est la clé d'idempotence, elle doit être stable d'une ingestion à l'autre.
- **`key`** (par entité) : une clé stable et **réutilisée** si tu reconnais
  la même entité dans plusieurs documents (ex: toujours `"unity_water"` pour
  l'application Unity Water, que tu la voies dans un ticket, une réunion ou
  une page Confluence). C'est CE rapprochement, fait par toi, qui remplace
  la résolution automatique par LLM de l'ancien pipeline — sois cohérent
  d'un document à l'autre dans la même session.
- **`attributes`** : les champs spécifiques au type. Voir
  `src/kb_smart_metering/models/entities.py` pour la liste indicative par
  type (ex: `Ticket` → `key`/`status`/`assignee` ; `Person` → `email`/`role` ;
  `Decision` → `rationale`/`stakeholders`).
- N'invente rien : n'extrais que ce qui est explicitement dans le texte.

Écris ce JSON dans un fichier, ex. `data/raw/extraction_smart_74743.json`.

---

## Étape 3 — Écrire dans Neo4j (Python, aucun LLM)

```bash
py -m kb_smart_metering.cli ingest-extraction data/raw/extraction_smart_74743.json
py -m kb_smart_metering.cli ingest-extraction data/raw/extraction_smart_74743.json --dry-run   # valider sans écrire
```

Répète pour chaque fichier d'extraction. Le résumé affiché indique le
nombre d'entités créées/réutilisées et de relations créées.

**Idempotence** : une entité déjà écrite (même `type` + même `key`) est
réutilisée, pas dupliquée — tu peux ré-ingérer un document déjà traité sans
risque, tant que tu réutilises les mêmes clés.

---

## Alternative — si Ollama (ou un endpoint LLM local) est disponible

Si la machine a Ollama configuré (`OLLAMA_BASE_URL` dans `.env` pointe vers
un vrai endpoint), le pipeline automatique d'origine reste utilisable et
fait tout en une commande (extraction + écriture, sans passer par toi) :

```bash
uv run kb ingest --source jira --project SMART --dry-run
uv run kb ingest --source jira --project SMART
```

N'utilise cette voie que si un LLM réseau est confirmé joignable — sinon
elle échoue avec une erreur de connexion. Dans le doute, utilise le flux
en 3 étapes ci-dessus, qui fonctionne toujours.

---

## Fréquences recommandées

| Source     | Fréquence          | Déclencheur                       |
|------------|--------------------|-----------------------------------|
| Jira       | Quotidien          | Fin de sprint / changement statut |
| Confluence | Hebdomadaire       | Après mise à jour de page         |
| Git        | À chaque livraison | Tag de version / merge main       |
| Fichiers   | À la réception     | Document partagé par email/Teams  |
| Réunions   | Dans les 24h       | Transcription disponible          |

---

## Workflows types

Voir [workflows-pipelines.md](./references/workflows-pipelines.md) pour les
exemples détaillés (pipeline fin de sprint, onboarding d'un nouveau projet,
ingestion batch de documents existants, pipeline post-livraison) — à
adapter au flux en 3 étapes ci-dessus si aucun LLM réseau n'est disponible.
