"""
Configuration pytest globale.

Marqueurs personnalisés :
- integration : tests nécessitant Neo4j et Ollama actifs (désactivés par défaut).
  Activer avec : uv run pytest -m integration
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: test d'intégration nécessitant Neo4j et Ollama (skip par défaut)",
    )
