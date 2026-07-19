"""
Tests de la configuration Pydantic Settings.

Vérifie le chargement des variables d'environnement sans fichier .env réel.
"""

import pytest
from pydantic import ValidationError


def test_settings_chargement_depuis_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les variables obligatoires doivent être lues depuis l'environnement."""
    monkeypatch.setenv("JIRA_URL", "https://test.atlassian.net")
    monkeypatch.setenv("JIRA_TOKEN", "tok_jira")
    monkeypatch.setenv("CONFLUENCE_URL", "https://test.atlassian.net/wiki")
    monkeypatch.setenv("CONFLUENCE_TOKEN", "tok_confluence")
    monkeypatch.setenv("NEO4J_PASSWORD", "secret")

    # Réinitialisation du module pour forcer le rechargement de Settings
    import importlib

    import kb_smart_metering.config as cfg_module

    importlib.reload(cfg_module)
    s = cfg_module.Settings()

    assert s.jira_url == "https://test.atlassian.net"
    assert s.jira_token == "tok_jira"
    assert s.neo4j_uri == "bolt://localhost:7687"
    assert s.ollama_model == "mistral:7b"
    assert s.embedding_model == "BAAI/bge-m3"


def test_settings_valeurs_manquantes_leve_erreur(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une variable obligatoire manquante doit lever une ValidationError."""
    # Supprime toutes les variables potentiellement héritées
    for var in ("JIRA_URL", "JIRA_TOKEN", "CONFLUENCE_URL", "CONFLUENCE_TOKEN", "NEO4J_PASSWORD"):
        monkeypatch.delenv(var, raising=False)

    import importlib

    import kb_smart_metering.config as cfg_module

    importlib.reload(cfg_module)

    with pytest.raises(ValidationError):
        cfg_module.Settings(_env_file=None)  # type: ignore[call-arg]
