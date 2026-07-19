"""
Types d'entités custom pour Graphiti (guide l'extraction LLM).

Chaque type est un modèle Pydantic v2 dont les champs décrivent
les attributs spécifiques au domaine smart metering à extraire.

Contrainte : les noms de champs ne doivent PAS entrer en conflit
avec ceux d'EntityNode (uuid, name, group_id, labels, created_at,
name_embedding, summary, attributes).
"""

from typing import Optional

from pydantic import BaseModel, Field


class PersonEntity(BaseModel):
    """Personne impliquée dans le projet (architecte, développeur, PO…)."""

    email: Optional[str] = Field(default=None, description="Adresse email de la personne")
    role: Optional[str] = Field(default=None, description="Rôle dans le projet")


class ApplicationEntity(BaseModel):
    """Application ou système du périmètre smart metering."""

    description: Optional[str] = Field(
        default=None, description="Description de l'application"
    )
    version: Optional[str] = Field(default=None, description="Version de l'application")


class ComponentEntity(BaseModel):
    """Composant technique d'une application."""

    application: Optional[str] = Field(
        default=None, description="Nom de l'application parente"
    )
    technology: Optional[str] = Field(default=None, description="Technologie utilisée")


class DocumentEntity(BaseModel):
    """Document projet (Word, PDF, Excel, Confluence…)."""

    url: Optional[str] = Field(default=None, description="URL du document")
    content_summary: Optional[str] = Field(
        default=None, description="Résumé du contenu du document"
    )


class TicketEntity(BaseModel):
    """Ticket Jira."""

    ticket_key: Optional[str] = Field(
        default=None, description="Clé du ticket Jira (ex: SMART-42)"
    )
    status: Optional[str] = Field(default=None, description="Statut du ticket")
    assignee: Optional[str] = Field(default=None, description="Responsable assigné")


class MeetingEntity(BaseModel):
    """Réunion projet avec participants et sujets abordés."""

    participants: Optional[str] = Field(
        default=None, description="Liste des participants (virgule-séparée)"
    )
    meeting_summary: Optional[str] = Field(
        default=None, description="Résumé de la réunion"
    )


class DecisionEntity(BaseModel):
    """Décision architecturale ou projet."""

    rationale: Optional[str] = Field(
        default=None, description="Justification de la décision"
    )
    stakeholders: Optional[str] = Field(
        default=None, description="Parties prenantes (virgule-séparée)"
    )


class ActionEntity(BaseModel):
    """Action à réaliser, issue d'une réunion ou d'un ticket."""

    owner: Optional[str] = Field(default=None, description="Responsable de l'action")
    due_date: Optional[str] = Field(
        default=None, description="Date limite au format ISO 8601"
    )
    done: bool = Field(default=False, description="Indicateur d'action réalisée")


class BusinessRuleEntity(BaseModel):
    """Règle métier ou contrainte réglementaire smart metering."""

    description: Optional[str] = Field(
        default=None, description="Description détaillée de la règle"
    )
    regulatory_reference: Optional[str] = Field(
        default=None, description="Référence réglementaire (décret, norme…)"
    )


# Dictionnaire prêt à passer à graphiti.add_episode(entity_types=...)
ENTITY_TYPES: dict[str, type[BaseModel]] = {
    "Person": PersonEntity,
    "Application": ApplicationEntity,
    "Component": ComponentEntity,
    "Document": DocumentEntity,
    "Ticket": TicketEntity,
    "Meeting": MeetingEntity,
    "Decision": DecisionEntity,
    "Action": ActionEntity,
    "BusinessRule": BusinessRuleEntity,
}
