"""Tests de fumée sur les modèles Pydantic (entités du domaine)."""

from datetime import datetime, timezone

from kb_smart_metering.models.entities import Decision, Person, SourceRef, Ticket
from kb_smart_metering.models.responses import LLMResponse


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _source() -> SourceRef:
    return SourceRef(type="jira", identifier="PROJ-42")


def test_person_creation() -> None:
    """Création d'une entité Person valide."""
    p = Person(
        name="Alice Dupont",
        email="alice@example.com",
        role="Architecte solution",
        valid_from=_now(),
        source_ref=_source(),
    )
    assert p.name == "Alice Dupont"
    assert p.valid_to is None


def test_ticket_creation() -> None:
    """Création d'un Ticket Jira valide."""
    t = Ticket(
        key="PROJ-42",
        summary="Implémenter l'extracteur Jira",
        status="In Progress",
        valid_from=_now(),
        source_ref=_source(),
    )
    assert t.key == "PROJ-42"


def test_decision_creation() -> None:
    """Création d'une Decision valide."""
    d = Decision(
        title="Utiliser BGE-M3 comme modèle d'embeddings",
        rationale="Meilleur score sur les benchmarks multilingues",
        stakeholders=["Alice", "Bob"],
        valid_from=_now(),
        source_ref=SourceRef(type="meeting", identifier="reunion-2024-01-15"),
    )
    assert len(d.stakeholders) == 2


def test_llm_response_defaults() -> None:
    """LLMResponse avec valeurs par défaut."""
    r = LLMResponse()
    assert r.facts == []
    assert r.risks == []
    assert r.answer is None


def test_llm_response_complete() -> None:
    """LLMResponse complète valide."""
    r = LLMResponse(
        facts=["Le compteur Linky est compatible DLMS"],
        decisions=["Utiliser MQTT pour le transport"],
        actions=["Documenter l'API de collecte"],
        risks=["Dépendance au fournisseur"],
        sources=["PROJ-10", "https://confluence/page/123"],
        answer="Le protocole retenu est MQTT.",
    )
    assert r.answer == "Le protocole retenu est MQTT."
