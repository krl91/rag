"""
Modèles Pydantic v2 des entités du domaine smart metering.

Toutes les entités conservent :
- valid_from / valid_to : temporalité de la connaissance
- source_ref : référence à la source originale (URL, SHA, chemin)

Non implémentés dans cette phase. Squelettes documentés.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """Référence à la source d'un fait ingéré."""

    type: str = Field(description="Type de source : jira, confluence, git, file, meeting")
    identifier: str = Field(description="URL, SHA commit, chemin fichier ou ID ticket")
    page: Optional[int] = Field(default=None, description="Numéro de page (PDF/Word)")


class TemporalEntity(BaseModel):
    """Classe de base pour toutes les entités temporelles du domaine."""

    valid_from: datetime = Field(description="Date de début de validité du fait")
    valid_to: Optional[datetime] = Field(
        default=None, description="Date de fin de validité (None = toujours valide)"
    )
    source_ref: SourceRef = Field(description="Référence à la source originale")


class Person(TemporalEntity):
    """Personne impliquée dans le projet (architecte, développeur, PO, etc.)."""

    name: str
    email: Optional[str] = None
    role: Optional[str] = None


class Application(TemporalEntity):
    """Application ou système du périmètre smart metering."""

    name: str
    description: Optional[str] = None
    version: Optional[str] = None


class Component(TemporalEntity):
    """Composant technique d'une application."""

    name: str
    application_name: str
    technology: Optional[str] = None


class Document(TemporalEntity):
    """Document projet (Word, PDF, Excel, Confluence)."""

    title: str
    url: Optional[str] = None
    content_summary: Optional[str] = None


class Ticket(TemporalEntity):
    """Ticket Jira."""

    key: str
    summary: str
    status: Optional[str] = None
    assignee: Optional[str] = None


class Meeting(TemporalEntity):
    """Réunion projet avec participants et sujets abordés."""

    title: str
    participants: list[str] = Field(default_factory=list)
    summary: Optional[str] = None


class Decision(TemporalEntity):
    """Décision architecturale ou projet."""

    title: str
    rationale: Optional[str] = None
    stakeholders: list[str] = Field(default_factory=list)


class Action(TemporalEntity):
    """Action à réaliser, issue d'une réunion ou d'un ticket."""

    description: str
    owner: Optional[str] = None
    due_date: Optional[datetime] = None
    done: bool = False


class BusinessRule(TemporalEntity):
    """Règle métier ou contrainte réglementaire smart metering."""

    name: str
    description: str
    regulatory_reference: Optional[str] = None
