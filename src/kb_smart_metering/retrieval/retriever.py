"""
Retrieval hybride — interroge le graphe Graphiti et les index vectoriels,
puis rerank les résultats avec BGE-reranker-v2-m3.

Non implémenté dans cette phase. Squelette documenté.
"""

import logging

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Combine recherche graphe et recherche vectorielle, puis rerank.

    Sera implémenté en Phase 1.
    """


class Reranker:
    """Reranker BGE-reranker-v2-m3 via sentence-transformers.

    Sera implémenté en Phase 1.
    """
