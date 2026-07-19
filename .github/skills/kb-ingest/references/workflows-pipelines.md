# Workflows et pipelines d'ingestion

> **Ces exemples supposent un LLM réseau joignable (Ollama) et `uv`
> disponible.** Sans LLM réseau (flux par défaut, voir skill `kb-ingest`) :
> remplacer chaque `uv run kb ingest --source X ...` par `kb extract
> --source X ... --out data/raw/`, puis l'extraction d'entités/relations
> par toi (l'agent, dans la conversation), puis `kb ingest-extraction
> <fichier>.json` pour chacun. Remplacer chaque `uv run kb ask "..."` par
> `kb search "..."` (contexte affiché) puis rédige la réponse toi-même.
> Sans `uv` (Windows, py+pip) : remplacer `uv run kb` par `kb` (si le
> paquet est installé, venv activé) ou `py -m kb_smart_metering.cli`.
> La logique des pipelines ci-dessous (quoi ingérer, dans quel ordre, à
> quelle fréquence) reste valable dans les deux cas — seule la commande
> d'ingestion/interrogation change.

## Pipeline fin de sprint

À exécuter après chaque sprint review/rétrospective.

```bash
# 1. Ingérer les tickets du sprint (nouveaux + modifiés uniquement)
uv run kb ingest --source jira --project SMART

# 2. Ingérer les pages Confluence mises à jour
uv run kb ingest --source confluence --space ARCH
uv run kb ingest --source confluence --space TECH

# 3. Ingérer la transcription de la sprint review
uv run kb ingest --source meeting --path /transcriptions/sprint_review_S42.vtt

# 4. Ingérer les commits du sprint (depuis le dépôt principal)
uv run kb ingest --source git --path /repos/compteur-service

# 5. Vérification rapide : poser une question sur le sprint
uv run kb ask "Quelles décisions ont été prises lors du sprint 42 ?"
```

**Durée estimée :** 5–15 min selon le volume (premiers appels plus longs
si des modèles BGE-M3 doivent traiter de nouveaux documents).

---

## Pipeline onboarding d'un nouveau projet

Pour intégrer un projet existant depuis zéro.

```bash
# 1. Dry-run d'abord : estimer le volume sans écrire
uv run kb ingest --source jira       --project NEWPROJ --dry-run
uv run kb ingest --source confluence --space   NEWPROJ --dry-run

# 2. Ingestion réelle dans une partition dédiée
uv run kb ingest --source jira       --project NEWPROJ --group-id newproj
uv run kb ingest --source confluence --space   NEWPROJ --group-id newproj

# 3. Ingérer tous les livrables documentaires existants
uv run kb ingest --source file --path /docs/projets/NEWPROJ/ --group-id newproj

# 4. Ingérer les dépôts de code
uv run kb ingest --source git --path /repos/newproj-backend  --group-id newproj
uv run kb ingest --source git --path /repos/newproj-frontend --group-id newproj

# 5. Vérification
uv run kb ask "Quel est le périmètre du projet NEWPROJ ?"
uv run kb ask "Quelles applications sont impliquées dans NEWPROJ ?"
```

---

## Pipeline ingestion batch de documents existants

Pour intégrer une bibliothèque documentaire historique (rapports, études, CdC).

```bash
# Estimation du volume (dry-run)
uv run kb ingest --source file --path /docs/archives/ --dry-run

# Ingestion par dossier thématique
uv run kb ingest --source file --path /docs/archives/specifications/
uv run kb ingest --source file --path /docs/archives/comptes-rendus/
uv run kb ingest --source file --path /docs/archives/livrables/

# Ingestion d'un dossier de transcriptions historiques
uv run kb ingest --source meeting --path /transcriptions/2023/
uv run kb ingest --source meeting --path /transcriptions/2024/

# Vérification : l'historique est accessible
uv run kb ask "Quelle était la décision d'architecture sur le protocole DLMS en PR2 ?"
```

---

## Pipeline post-livraison (tag de version)

```bash
# Après un git tag vX.Y.Z sur le dépôt principal
uv run kb ingest --source git --path /repos/compteur-service

# Ingérer le document de release notes si disponible
uv run kb ingest --source file --path /docs/releases/release-v2.3.0.pdf

# Ingérer les pages Confluence de documentation de version
uv run kb ingest --source confluence --space ARCH

# Poser des questions de validation
uv run kb ask "Quelles fonctionnalités ont été livrées en v2.3.0 ?"
uv run kb ask "Quels composants ont été modifiés dans cette version ?"
```

---

## Pipeline de synchronisation quotidienne (automatisable)

> **Nécessite un LLM réseau joignable (Ollama).** Sans lui, l'extraction
> d'entités/relations est faite par l'agent en conversation (voir skill
> `kb-ingest`) — un script cron/Task Scheduler headless ne peut pas
> remplacer ce travail. Sur une machine sans LLM réseau, ce pipeline
> automatisé n'est donc pas applicable tel quel ; `kb extract` (la partie
> mécanique, sans LLM) peut en revanche être planifiée seule, pour préparer
> les fichiers que l'agent traitera ensuite en session.

Ce pipeline peut être mis dans un script `scripts/daily_ingest.sh` et planifié
via cron ou Task Scheduler Windows (uniquement pertinent avec Ollama) :

```bash
#!/bin/bash
# daily_ingest.sh — Synchronisation quotidienne de la base de connaissances
set -e

cd "$(dirname "$0")/.."

echo "=== Ingestion quotidienne — $(date) ==="

# Sources qui changent fréquemment
uv run kb ingest --source jira       --project SMART
uv run kb ingest --source jira       --project INFRA
uv run kb ingest --source confluence --space ARCH
uv run kb ingest --source confluence --space TECH

# Git : dépôts actifs
uv run kb ingest --source git --path /repos/compteur-service
uv run kb ingest --source git --path /repos/mdm-client

echo "=== Synchronisation terminée ==="
```

---

## Résumé de sortie interprétation

```
Résumé : 47 épisodes (45 ingérés, 2 ignorés), 312 entités, 891 relations.
```

- **épisodes ingérés** : documents traités par Graphiti → nouveaux nœuds/edges créés
- **épisodes ignorés** : hash identique → document inchangé depuis la dernière ingestion
- **entités** : nœuds créés dans Neo4j (Person, Application, Decision, etc.)
- **relations** : edges entre entités (IS_PART_OF, DECIDED_BY, ACTION_FOR, etc.)
