"""
Schéma d'extraction produit par l'agent Copilot pendant la conversation.

Remplace l'extraction automatique par LLM de graphiti-core (add_episode),
qui exige un endpoint réseau OpenAI-compatible joignable en permanence —
incompatible avec une utilisation "tout dans VS Code, aucun serveur, aucun
port ouvert". À la place : l'agent lit un RawDocument dans la conversation,
fait lui-même le travail d'extraction (c'est le rôle du LLM choisi dans
Copilot Chat), et produit ce JSON structuré. graph_writer.py l'écrit ensuite
dans Neo4j de façon déterministe, sans appel LLM côté Python.

Les 9 types valides (clé du champ ``type``) sont ceux définis dans
``kb_smart_metering.models.entities`` : Person, Application, Component,
Document, Ticket, Meeting, Decision, Action, BusinessRule. Les champs
spécifiques à chaque type (ex: ``ticket_key``/``status`` pour Ticket,
``email``/``role`` pour Person) vont dans ``attributes``.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

VALID_ENTITY_TYPES = {
    "Person",
    "Application",
    "Component",
    "Document",
    "Ticket",
    "Meeting",
    "Decision",
    "Action",
    "BusinessRule",
}


class ExtractedEntity(BaseModel):
    """Une entité extraite par l'agent à partir d'un document source."""

    key: str = Field(
        description="Clé locale au batch (ex: 'unity_water'), utilisée par "
        "ExtractedRelation.source_key/target_key pour relier les entités."
    )
    type: str = Field(description="Un des 9 types du domaine (voir VALID_ENTITY_TYPES).")
    name: str = Field(description="Nom lisible de l'entité.")
    summary: str = Field(default="", description="Résumé court de l'entité.")
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Champs spécifiques au type (ex: ticket_key, status, email…).",
    )

    @field_validator("type")
    @classmethod
    def _type_connu(cls, v: str) -> str:
        if v not in VALID_ENTITY_TYPES:
            raise ValueError(
                f"type d'entité inconnu : {v!r} — attendu un de {sorted(VALID_ENTITY_TYPES)}"
            )
        return v


class ExtractedRelation(BaseModel):
    """Une relation entre deux entités extraites (par leur clé locale au batch)."""

    source_key: str = Field(description="Clé locale (ExtractedEntity.key) du nœud source.")
    target_key: str = Field(description="Clé locale (ExtractedEntity.key) du nœud cible.")
    name: str = Field(description="Verbe/type de la relation (ex: 'concerne', 'décide').")
    fact: str = Field(description="Phrase complète en langage naturel décrivant le fait.")
    valid_at: datetime | None = Field(
        default=None, description="Date à partir de laquelle le fait est valide."
    )
    invalid_at: datetime | None = Field(
        default=None, description="Date à partir de laquelle le fait n'est plus valide."
    )


class ExtractionResult(BaseModel):
    """
    Résultat d'extraction pour UN document source, produit par l'agent.

    ``source_ref`` doit être stable et unique par document — c'est la clé
    d'idempotence utilisée par IngestionPipeline (même format que l'ancien
    episode_key : ``{source_type}:{id_source}:{version}``).
    """

    source_ref: str
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)
