"""
Schéma de réponse LLM structurée.

Le LLM retourne toujours un JSON conforme à ce modèle.
Validé par Pydantic avant utilisation.
"""

from typing import Optional

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """Réponse structurée attendue du LLM (validée par Pydantic)."""

    facts: list[str] = Field(
        default_factory=list,
        description="Faits extraits ou synthétisés par le LLM",
    )
    decisions: list[str] = Field(
        default_factory=list,
        description="Décisions identifiées dans le contexte",
    )
    actions: list[str] = Field(
        default_factory=list,
        description="Actions à réaliser identifiées dans le contexte",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Risques identifiés dans le contexte",
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Références aux sources utilisées pour construire la réponse",
    )
    answer: Optional[str] = Field(
        default=None,
        description="Réponse en langage naturel, si demandée",
    )
