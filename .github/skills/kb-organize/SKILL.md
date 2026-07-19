---
name: kb-organize
description: "Méthodes d'organisation à appliquer SI BESOIN dans kb-smart-metering : PARA (structure du dossier docs/), Zettelkasten (atomicité des entités extraites), Getting Things Done (triage des actions), matrice d'Eisenhower (priorisation actions/risques/décisions). Utiliser uniquement quand l'utilisateur demande explicitement d'organiser, trier, prioriser ou classer — ne jamais appliquer par défaut."
argument-hint: "Méthode (para|zettelkasten|gtd|eisenhower) + ce qui doit être organisé"
---

# Skill — Méthodes d'organisation (usage conditionnel)

> **Ne charge ce skill que si l'utilisateur le demande explicitement**
> ("organise mes notes", "trie ces actions", "priorise ces risques",
> "classe ce dossier"). Ce n'est pas un comportement par défaut du projet —
> les 4 méthodes ci-dessous sont des outils de réflexion que tu appliques
> à la demande, pas une structure imposée aux données du graphe.

---

## Quelle méthode pour quel besoin

| Méthode | S'applique à | Déclencheur typique |
|---|---|---|
| **PARA** | Organisation de fichiers/dossiers (`docs/`, vault Obsidian) | "range ces documents", "structure mon dossier docs" |
| **Zettelkasten** | Qualité de l'extraction d'entités (skill `kb-ingest`) | Déjà appliqué implicitement — voir note ci-dessous |
| **GTD** | Entités `Action` retrouvées via `kb search` | "quelles actions dois-je traiter", "fais le point sur mes tâches" |
| **Eisenhower** | Entités `Action`/`Risk`/`Decision` retrouvées via `kb search` | "priorise ces risques", "qu'est-ce qui est urgent" |

Les quatre méthodes sont indépendantes — n'en combine pas plusieurs dans
la même réponse sauf demande explicite (ex: "GTD puis Eisenhower sur les
actions non urgentes").

---

## PARA — organiser des fichiers/dossiers

**Projects** (objectif précis, date de fin) / **Areas** (responsabilité
continue, pas de fin) / **Resources** (référence, pas d'action requise) /
**Archive** (inactif).

Application dans ce projet : la sortie de `kb docgen` (`docs/`) et les
exports (`kb export`) peuvent être rangés ainsi, par exemple :

```
docs/
├── projects/    # migrations, épics en cours (ex: docs/projects/migration-v3/)
├── areas/       # composants/applications sous responsabilité continue
├── resources/   # documentation d'architecture de référence (ARC, specs)
└── archive/     # versions dépréciées, projets clos
```

Quand on te demande de ranger un ensemble de fichiers déjà générés :
1. Demande (ou déduis du contexte) si chaque élément a une fin prévue
   (→ Project), une responsabilité continue (→ Area), sert de référence
   (→ Resource), ou est terminé/obsolète (→ Archive).
2. Propose le déplacement avant de l'exécuter — jamais de déplacement
   silencieux de fichiers existants.

---

## Zettelkasten — atomicité des entités (déjà en partie appliqué)

Principe : chaque note/entité porte **une seule idée**, autonome, reliée
aux autres par des liens explicites plutôt que par une hiérarchie de
dossiers.

Ce principe est **déjà le fondement du schéma d'extraction** du projet
(`ingestion/extraction_schema.py`, skill `kb-ingest`) : chaque
`ExtractedEntity` doit représenter un seul concept, et les
`ExtractedRelation` sont les liens explicites entre entités — c'est
littéralement un Zettelkasten appliqué au graphe de connaissances plutôt
qu'à des fichiers Markdown.

Si on te demande explicitement de renforcer cet aspect pendant une
extraction (skill `kb-ingest`, étape 2) :
- Vérifie qu'aucune entité ne mélange deux concepts distincts (ex: ne pas
  fusionner "Ticket SMART-142" et "Décision associée" dans une seule
  entité — ce sont deux entités reliées par une relation).
- Vérifie que chaque relation (`fact`) est une phrase autonome,
  compréhensible sans relire le document source.

---

## GTD (Getting Things Done) — triage des actions

Sur un ensemble d'entités `Action` retrouvées via `kb search`, applique la
clarification GTD :

1. **Actionnable ?** Non → Référence (ignorer) ou Un jour/Peut-être.
2. **Actionnable, < 2 minutes ?** → à faire immédiatement (le signaler).
3. **Actionnable, > 2 minutes, une seule étape ?** → **Action suivante**,
   assignée à un contexte/une personne (`owner` de l'entité `Action`).
4. **Plusieurs étapes ?** → **Projet** (regrouper les actions liées).
5. **Déléguée à quelqu'un d'autre ?** → **En attente de** (`waiting for`),
   avec le nom du responsable.

```bash
kb search "actions ouvertes non clôturées"
```
Puis présente le résultat sous forme de listes GTD (Actions suivantes /
En attente de / Projets / Un jour-peut-être), à partir des entités `Action`
du contexte retourné — jamais d'action inventée hors de ce contexte.

---

## Matrice d'Eisenhower — priorisation

Sur un ensemble d'entités `Action`/`Risk`/`Decision` retrouvées via
`kb search`, classe chaque élément selon urgence × importance :

|               | Urgent | Pas urgent |
|---------------|--------|------------|
| **Important**     | Faire maintenant | Planifier |
| **Pas important** | Déléguer | Éliminer/ignorer |

```bash
kb search "risques et actions ouvertes sur [périmètre]"
```
Pour chaque élément du contexte retourné, indique le quadrant et une
justification courte (échéance connue → urgent ; impact sur
livraison/client → important). Ne classe que ce qui est explicitement dans
le contexte — si l'urgence ou l'importance n'est pas déductible de la
source, le dire plutôt que de deviner.
