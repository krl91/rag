---
name: kb-reveng
description: "Analyse statique et documentation de code source via kb-smart-metering revengine. Utiliser pour : rétro-ingénierie de dépôts Java, Python ou C#, extraction AST (classes, méthodes, appels sortants, événements publish/subscribe), cartographie des dépendances inter-composants, génération de documentation Markdown/Obsidian par module, ingestion de l'architecture code dans le graphe de connaissances. Fonctionne avec ou sans LLM réseau (Ollama) — flux conversationnel par défaut. Prérequis : uv sync --extra revengine (ou pip install -e '.[dev,revengine]' sans uv)."
argument-hint: "Chemin dépôt + langage (java|python|csharp) [+ module cible]"
---

# Skill — Analyse et documentation de code (revengine)

## Quand utiliser ce skill

- Comprendre l'architecture d'un dépôt non documenté
- Cartographier les flux d'événements (publish/subscribe) entre microservices
- Générer des fiches de documentation par module
- Enrichir le graphe de connaissances avec la structure du code
- Préparer une revue d'architecture ou une migration

---

## Prérequis

**Avec `uv` :**
```bash
uv sync --extra revengine
uv run python -c "import tree_sitter_language_pack; print('revengine OK')"
```

**Sans `uv` (Windows, py + pip) :**
```powershell
pip install -e ".[dev,revengine]"
python -c "import tree_sitter_language_pack; print('revengine OK')"
```

Langages supportés : **Java**, **Python**, **C#**

---

## Deux chemins possibles

Comme pour l'ingestion classique (skill `kb-ingest`), `kb reveng` (analyse +
écriture graphe) et `kb docgen` (documentation Markdown) exigent tous deux
un LLM réseau joignable dans leur mode "tout en une commande". **Sans
Ollama, utiliser le flux en 3 étapes ci-dessous — c'est le flux par défaut
et recommandé.**

```
[1. kb reveng --out          [2. TOI : extraction         [3. kb ingest-extraction
    / kb docgen               d'entités et rédaction]         / kb docgen --from-extraction]
    --extract-only]        →  (dans la conversation)      →   Python — écriture, aucun LLM
Python — AST seul, aucun LLM
```

---

## A — Cartographier l'architecture dans le graphe (sans LLM)

### Étape 1 — Extraire (Python, aucun LLM)

```bash
kb reveng --repo /repos/compteur-service --lang java --out data/raw/
```

Affiche aussi les relations candidates détectées par heuristique AST
(`Component --publie--> Event`, `--consomme-->`, `--appelle-->`) — un point
de départ fiable pour l'étape suivante, à transcrire dans le JSON
d'extraction plutôt qu'à réinventer.

### Étape 2 — Extraire entités/relations (TON travail, dans la conversation)

Même schéma `ExtractionResult` que pour les autres sources (voir skill
`kb-ingest`). Pour du code, les entités typiques sont `Component`
(classes/services) et éventuellement `Application` ; les relations
reprennent les relations candidates affichées à l'étape 1
(`publie`/`consomme`/`appelle`), enrichies si le contexte du fichier JSON
apporte plus de détails.

### Étape 3 — Écrire dans Neo4j (Python, aucun LLM)

```bash
kb ingest-extraction data/raw/extraction_ExportService.json
```

---

## B — Générer la documentation Markdown d'un module (sans LLM)

### Étape 1 — Extraire le contexte structurel (Python, aucun LLM)

```bash
kb docgen --repo /repos/compteur-service --lang java --out data/raw-docgen/ --extract-only
# Ou pour un seul module :
kb docgen --repo /repos/compteur-service --lang java --module ExportService \
           --out data/raw-docgen/ --extract-only
```

Écrit un fichier `<module>.extraction.json` par module, avec les champs AST
déjà remplis (`classes`, `events_published`, `events_subscribed`, `sources`)
et une clé `contexte` en lecture seule (les éléments structurels, le même
contenu que celui normalement envoyé au LLM) — plus 5 champs vides à
compléter : `description`, `composants`, `flux`, `regles_metier`, `risques`.

### Étape 2 — Rédiger la documentation (TON travail, dans la conversation)

Pour chaque fichier `data/raw-docgen/*.extraction.json` :

1. Lis-le, en particulier la clé `contexte`.
2. Complète, **à partir de `contexte` uniquement** (ne rien inventer) :
   - `description` : description fonctionnelle du module en 2-4 phrases
   - `composants` : composants identifiés
   - `flux` : flux de données ou événements détectés (ex: "A → B via EventX")
   - `regles_metier` : règles métier détectées par analyse statique
   - `risques` : risques ou dette technique détectés
3. Sauvegarde le fichier tel quel (la clé `contexte` est ignorée à la relecture).

### Étape 3 — Assembler le Markdown (Python, aucun LLM)

```bash
kb docgen --repo /repos/compteur-service --lang java \
          --from-extraction data/raw-docgen/ExportService.extraction.json --out docs/
```

---

## Alternative — si Ollama (ou un endpoint LLM local) est disponible

Pipeline automatique en une commande, sans passer par toi :

```bash
uv run kb reveng --repo /repos/compteur-service --lang java   # analyse + ingestion
uv run kb docgen --repo /repos/compteur-service --lang java --out docs/generated/
```

N'utilise cette voie que si un LLM réseau est confirmé joignable — sinon
elle échoue avec une erreur de connexion (`kb reveng` sans `--out` appelle
Graphiti/LLM ; `kb docgen` sans `--extract-only` appelle le LLM directement
pour rédiger la doc). Dans le doute, utiliser les flux A/B ci-dessus.

---

## Interroger le graphe enrichi

Une fois l'architecture ingérée (voie A), utiliser `kb search` (skill
`kb-ask`) — tu rédiges la réponse à partir du contexte retourné :

```bash
kb search "Quels composants publient l'événement MeterReadingReceived ?"
kb search "Quelles méthodes de ExportService appellent le MDM ?"
kb search "Quelles classes implémentent le protocole DLMS ?"
```

(Avec Ollama configuré, `uv run kb ask "..."` fonctionne aussi directement.)

---

## Format des fichiers de documentation générés

```markdown
---
module: ExportService
language: java
generated_at: 2024-01-15
repo: /repos/compteur-service
---

# ExportService

## Classes

### ExportService
- `exportMeterData(String meterId)` → appelle MDMClient.getReading()
- `publishExportEvent(ExportEvent event)` → publie ExportEvent

## Dépendances sortantes
- MDMClient
- KafkaProducer

## Événements publiés
- ExportEvent (via publishExportEvent)

## Événements consommés
- MeterReadingReceived (via onMeterReading)
```
