"""
Recherche hybride dans le graphe Graphiti.

Combine recherche sémantique (cosine similarity), BM25 et traversée de graphe
via l'API graphiti-core. Supporte des filtres temporels (as_of_date) et par
type d'entité.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from graphiti_core.graphiti import Graphiti
from graphiti_core.search.search_config import SearchResults
from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_RRF
from graphiti_core.search.search_filters import (
    ComparisonOperator,
    DateFilter,
    SearchFilters,
)

logger = logging.getLogger(__name__)

# Mapping version/phase → dates approximatives du projet smart metering.
# Permet d'inférer as_of_date depuis la question (ex : "en PR2").
VERSION_DATE_MAP: dict[str, datetime] = {
    "pr1": datetime(2023, 6, 1),
    "pr2": datetime(2023, 12, 1),
    "pr3": datetime(2024, 6, 1),
    "pr4": datetime(2024, 12, 1),
    "sprint1": datetime(2023, 3, 1),
    "sprint2": datetime(2023, 6, 1),
    "sprint3": datetime(2023, 9, 1),
    "sprint4": datetime(2023, 12, 1),
}

_VERSION_RE = re.compile(r"\b(pr\s*\d+|sprint\s*\d+)\b", re.IGNORECASE)


def detect_date_from_question(question: str) -> Optional[datetime]:
    """
    Tente d'inférer une date as_of_date depuis la question.

    Reconnait les patterns : "PR2", "PR 3", "sprint 1", etc.
    Retourne None si aucun pattern connu n'est trouvé.
    """
    match = _VERSION_RE.search(question)
    if match:
        key = match.group(1).lower().replace(" ", "")
        date = VERSION_DATE_MAP.get(key)
        if date is not None:
            logger.debug("Date inférée depuis la question : %r → %s", key, date.date())
            return date
    return None


@dataclass
class SearchCandidate:
    """Résultat brut d'une recherche hybride dans le graphe."""

    uuid: str
    fact: str
    edge_name: str
    valid_at: Optional[datetime]
    created_at: datetime
    group_id: str
    score: float = 0.0


async def hybrid_search(
    graphiti: Graphiti,
    question: str,
    as_of_date: Optional[datetime] = None,
    entity_types: Optional[list[str]] = None,
    top_k: int = 20,
) -> list[SearchCandidate]:
    """
    Effectue une recherche hybride (sémantique + BM25 + traversée de graphe).

    Paramètres
    ----------
    graphiti : Graphiti
        Instance Graphiti connectée à Neo4j.
    question : str
        Question ou requête de recherche.
    as_of_date : datetime, optionnel
        Si fourni, filtre les faits dont valid_at est antérieur ou égal à
        cette date et dont expired_at est postérieur (ou nul).
        Si absent, tente d'inférer la date depuis la question via
        detect_date_from_question().
    entity_types : list[str], optionnel
        Labels de nœuds pour filtrer les résultats
        (ex : ["Decision", "Action"]).
    top_k : int
        Nombre maximum de résultats retournés (défaut 20).

    Retourne
    --------
    list[SearchCandidate]
        Candidats triés par pertinence décroissante.
    """
    # Tentative d'inférence de date si non fournie explicitement
    effective_date = as_of_date if as_of_date is not None else detect_date_from_question(question)

    # Construction des filtres Graphiti
    filters = SearchFilters()

    if effective_date is not None:
        # Faits devenus valides avant ou à la date de référence
        filters.valid_at = [
            [
                DateFilter(
                    date=effective_date,
                    comparison_operator=ComparisonOperator.less_than_equal,
                )
            ]
        ]
        # Faits qui n'ont pas encore expiré à la date de référence
        filters.expired_at = [
            [
                DateFilter(
                    date=effective_date,
                    comparison_operator=ComparisonOperator.greater_than,
                )
            ]
        ]
        logger.info("Filtre temporel appliqué : as_of_date=%s", effective_date.date())

    if entity_types:
        filters.node_labels = entity_types
        logger.info("Filtre par type d'entité : %s", entity_types)

    # Configuration de recherche hybride avec Reciprocal Rank Fusion
    config = COMBINED_HYBRID_SEARCH_RRF.model_copy(deep=True)
    config.limit = top_k

    logger.info(
        "Recherche hybride : question=%r, top_k=%d",
        question[:80],
        top_k,
    )

    results: SearchResults = await graphiti.search_(
        query=question,
        config=config,
        search_filter=filters,
    )

    candidates: list[SearchCandidate] = []
    for edge in results.edges:
        candidates.append(
            SearchCandidate(
                uuid=edge.uuid,
                fact=edge.fact,
                edge_name=edge.name,
                valid_at=edge.valid_at,
                created_at=edge.created_at,
                group_id=edge.group_id,
            )
        )

    logger.info("Recherche hybride : %d résultats retournés", len(candidates))
    return candidates
