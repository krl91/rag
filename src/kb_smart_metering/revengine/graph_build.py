"""
Transformation des modules extraits (AST) en RawDocument et relations candidates.

Produit :
  - un RawDocument par ExtractedModule (source_type="code") pour ingestion
    dans le pipeline Phase 2
  - une liste de RelationCandidate :
      Component --publie-->  Event
      Component --consomme--> Event
      Component --appelle--> Component

Usage :
    from kb_smart_metering.revengine.graph_build import GraphBuilder

    builder = GraphBuilder()
    docs = builder.build_documents(modules)
    relations = builder.build_relations(modules)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from kb_smart_metering.normalize.models import RawDocument
from kb_smart_metering.revengine.ast_extract import ExtractedModule

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modèles de relation candidate
# ---------------------------------------------------------------------------

RelationKind = Literal["publie", "consomme", "appelle"]


class RelationCandidate(BaseModel):
    """Relation candidate extraite par heuristique depuis l'AST."""

    source_component: str = Field(description="Nom du composant source")
    target: str = Field(description="Nom du composant ou de l'événement cible")
    kind: RelationKind = Field(description="Type de relation")
    source_file: str = Field(description="Chemin du fichier source")
    line: int = Field(description="Ligne approximative (début de la classe)")
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Niveau de confiance de la relation (heuristique)",
    )


# ---------------------------------------------------------------------------
# Constructeur
# ---------------------------------------------------------------------------


class GraphBuilder:
    """
    Transforme des ExtractedModule en RawDocument et RelationCandidate.

    L'idempotence est assurée par le pipeline d'ingestion (SQLite tracking).
    """

    def build_documents(self, modules: list[ExtractedModule]) -> list[RawDocument]:
        """
        Construit un RawDocument par module extrait.

        Le contenu textuel est un résumé structuré JSON des classes, méthodes
        et événements — pas le code source complet.
        """
        docs: list[RawDocument] = []
        for module in modules:
            doc = self._module_to_raw_document(module)
            docs.append(doc)
            logger.debug("Document construit : %s", doc.id_source)
        return docs

    def build_relations(self, modules: list[ExtractedModule]) -> list[RelationCandidate]:
        """Extrait toutes les relations candidates depuis les modules."""
        relations: list[RelationCandidate] = []
        for module in modules:
            relations.extend(self._extract_module_relations(module))
        logger.info(
            "%d relation(s) candidate(s) extraite(s) depuis %d module(s)",
            len(relations),
            len(modules),
        )
        return relations

    # ------------------------------------------------------------------
    # Privé
    # ------------------------------------------------------------------

    @staticmethod
    def _module_to_raw_document(module: ExtractedModule) -> RawDocument:
        """Convertit un ExtractedModule en RawDocument ingérable."""
        # Résumé structuré : JSON compact des éléments AST
        summary_parts: list[dict] = []
        for cls in module.classes:
            entry: dict = {
                "name": cls.name,
                "kind": cls.kind,
                "lines": f"{cls.line_start}-{cls.line_end}",
                "methods": [m.name for m in cls.methods],
            }
            if cls.events_published:
                entry["events_published"] = cls.events_published
            if cls.events_subscribed:
                entry["events_subscribed"] = cls.events_subscribed
            if cls.data_models:
                entry["data_models"] = cls.data_models
            if cls.outgoing_components:
                entry["calls"] = cls.outgoing_components
            summary_parts.append(entry)

        contenu = (
            f"# Module : {module.module_name}\n"
            f"Langage : {module.language}\n"
            f"Package : {module.package or 'N/A'}\n\n"
            f"## Éléments extraits (AST)\n"
            f"```json\n{json.dumps(summary_parts, ensure_ascii=False, indent=2)}\n```\n\n"
            f"## Extrait source\n"
            f"```\n{module.raw_source_excerpt}\n```"
        )

        return RawDocument(
            id_source=f"code:{module.language}:{module.file_path}",
            source_type="obsidian",  # réutilise le type le plus proche pour l'ingestion
            titre=f"[Code] {module.module_name}",
            contenu_texte=contenu,
            url_ou_chemin=module.file_path,
            date_creation=datetime.now(tz=timezone.utc),
            metadonnees={
                "language": module.language,
                "package": module.package,
                "classes": [c.name for c in module.classes],
                "source_kind": "reverse_engineering",
            },
        )

    @staticmethod
    def _extract_module_relations(module: ExtractedModule) -> list[RelationCandidate]:
        """Extrait les relations depuis un seul module."""
        relations: list[RelationCandidate] = []

        for cls in module.classes:
            # Component --publie--> Event
            for evt in cls.events_published:
                relations.append(
                    RelationCandidate(
                        source_component=cls.name,
                        target=evt,
                        kind="publie",
                        source_file=module.file_path,
                        line=cls.line_start,
                    )
                )

            # Component --consomme--> Event
            for evt in cls.events_subscribed:
                relations.append(
                    RelationCandidate(
                        source_component=cls.name,
                        target=evt,
                        kind="consomme",
                        source_file=module.file_path,
                        line=cls.line_start,
                    )
                )

            # Component --appelle--> Component (heuristique sur les champs)
            for dep in cls.outgoing_components:
                relations.append(
                    RelationCandidate(
                        source_component=cls.name,
                        target=dep,
                        kind="appelle",
                        source_file=module.file_path,
                        line=cls.line_start,
                        confidence=0.5,  # confiance plus faible (heuristique champs)
                    )
                )

        return relations
