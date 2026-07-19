CONTAINER_ENGINE ?= podman

.PHONY: setup up down test lint

## Installe l'environnement virtuel et les dépendances (via uv)
setup:
	uv sync --all-extras
	uv run python scripts/setup.py

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
