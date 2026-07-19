# Portage Windows — Problème 1 : Makefile et commandes shell POSIX

## Contexte du projet

`kb-smart-metering` est un système de gestion des connaissances projet pour
architectes solution dans l'industrie smart metering. Il est développé en
Python 3.11+ avec `uv` comme gestionnaire de dépendances, Podman pour les
conteneurs, FastAPI pour l'API REST et Typer pour la CLI.

Le dépôt cible actuellement macOS/Linux. L'objectif de cette série de prompts
est de le porter sur Windows (natif, sans WSL2 obligatoire).

---

## Principe directeur

**Privilégier systématiquement ce qui est déjà disponible** sur la machine
cible avant de recommander l'installation d'outils supplémentaires :
- Si un outil est présent dans l'environnement Windows standard (PowerShell,
  `winget`, fonctionnalités .NET), l'utiliser en priorité.
- N'introduire une dépendance externe (Chocolatey, Scoop, etc.) que si aucune
  alternative native ne permet de répondre au besoin.
- Vérifier d'abord si `uv` ou Python seul peuvent résoudre le problème sans
  outil tiers supplémentaire.
- Proposer les solutions du moins intrusif au plus intrusif.

---

## Description du problème

Le projet expose toutes ses commandes d'administration via un `Makefile` à la
racine du dépôt. Ce fichier est **totalement inutilisable sur Windows natif**
car :

1. `make` n'est pas installé par défaut sur Windows (ni dans `cmd.exe` ni dans
   PowerShell).
2. La recette `setup` utilise la commande shell POSIX `cp` avec l'option `-n`
   et un opérateur `|| true` :

```makefile
setup:
	uv sync --all-extras
	cp -n .env.example .env || true
```

Ces syntaxes n'existent pas dans `cmd.exe` ni PowerShell natif.

### Contenu complet du Makefile actuel

```makefile
CONTAINER_ENGINE ?= podman

.PHONY: setup up down test lint

## Installe l'environnement virtuel et les dépendances (via uv)
setup:
	uv sync --all-extras
	cp -n .env.example .env || true

## Démarre les conteneurs en arrière-plan (Neo4j, etc.)
up:
	$(CONTAINER_ENGINE) compose up -d

## Arrête et supprime les conteneurs
down:
	$(CONTAINER_ENGINE) compose down

## Lance la suite de tests pytest
test:
	uv run pytest

## Vérifie le style et les types (ruff + mypy)
lint:
	uv run ruff check src tests
	uv run mypy src
```

---

## Ce que tu dois analyser

1. **Évaluer les options pour remplacer ou compléter le Makefile** sous Windows :
   - Fichier `Makefile` compatible via [GNU Make pour Windows](https://gnuwin32.sourceforge.net/packages/make.htm) ou Chocolatey (`choco install make`) — quelles limitations subsistent ?
   - Script PowerShell `make.ps1` ou `tasks.ps1` équivalent — quelle est la syntaxe correcte ?
   - `Justfile` (outil [just](https://just.systems/)) compatible Windows, macOS et Linux — est-ce adapté ?
   - `Taskfile` (outil [Task](https://taskfile.dev/)) YAML cross-platform — est-ce adapté ?

2. **Résoudre l'équivalent de `cp -n .env.example .env || true`** en PowerShell :
   - La sémantique exacte est : "copier `.env.example` vers `.env` uniquement si `.env` n'existe pas encore, sans erreur si `.env` existe déjà".
   - Proposer l'équivalent PowerShell.
   - Proposer l'équivalent en Python pur (script `scripts/setup.py` appelable via `uv run python scripts/setup.py`) pour être vraiment cross-platform.

3. **Stratégie de compatibilité retenue** :
   - Doit fonctionner sans installation d'outils supplémentaires au-delà de Python et `uv`.
   - Doit rester compatible macOS/Linux pour ne pas casser l'existant.
   - Les commandes `make setup`, `make test`, `make lint` doivent avoir un équivalent documenté pour Windows.

---

## Contraintes du projet

- Python 3.11+, gestionnaire `uv`.
- Podman (jamais Docker) pour les conteneurs — voir Problème 2 pour les détails sur Podman sous Windows.
- `CONTAINER_ENGINE` est une variable surchargeable dans le Makefile.
- Ne pas supprimer le Makefile existant (les utilisateurs macOS/Linux l'utilisent) : **ajouter** une solution parallèle pour Windows.

---

## Livrable attendu

Propose une solution concrète et implémentable :
- Les fichiers à créer (avec leur contenu complet).
- Les modifications à apporter au `README.md` pour documenter la procédure Windows.
- Une ligne de commande unique à exécuter dans PowerShell pour bootstrapper le projet sur un Windows vierge (Python + uv déjà installés).
