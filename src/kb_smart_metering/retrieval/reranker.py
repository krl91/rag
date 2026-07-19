"""
Reranker BGE-reranker-v2-m3 via sentence-transformers CrossEncoder.

Charge le modèle en lazy singleton pour éviter de le recharger à chaque appel.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Singleton du CrossEncoder — None tant que non chargé
_reranker_instance: Optional[object] = None


def _get_reranker():
    """
    Retourne l'instance CrossEncoder (lazy loading au premier appel).

    Utilise le modèle configuré dans settings.reranker_model.
    sentence-transformers n'est importé qu'au premier appel pour éviter
    un chargement inutile si le reranker n'est pas utilisé.
    """
    global _reranker_instance
    if _reranker_instance is None:
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers est requis pour le reranker. "
                "Installez-le avec : uv sync"
            ) from exc

        from kb_smart_metering.config import settings

        logger.info("Chargement du reranker : %s", settings.reranker_model)
        _reranker_instance = CrossEncoder(settings.reranker_model)
        logger.info("Reranker chargé.")
    return _reranker_instance


@dataclass
class RankedCandidate:
    """Candidat reranké avec son score de pertinence."""

    original_index: int
    text: str
    score: float
    metadata: dict = field(default_factory=dict)


def rerank(
    question: str,
    candidates: list[str],
    top_n: int = 10,
    metadata: Optional[list[dict]] = None,
) -> list[RankedCandidate]:
    """
    Reranke les candidats par rapport à la question avec BGE-reranker-v2-m3.

    Paramètres
    ----------
    question : str
        Question de référence pour le reranking.
    candidates : list[str]
        Textes des candidats à classer.
    top_n : int
        Nombre maximum de résultats à retourner (défaut 10).
    metadata : list[dict], optionnel
        Métadonnées associées à chaque candidat (même ordre que candidates).
        Propagées dans les RankedCandidate retournés.

    Retourne
    --------
    list[RankedCandidate]
        Candidats triés par score décroissant, limités à top_n.
    """
    if not candidates:
        return []

    if metadata is not None and len(metadata) != len(candidates):
        raise ValueError(
            f"metadata ({len(metadata)}) doit avoir la même longueur que candidates ({len(candidates)})"
        )

    reranker = _get_reranker()
    pairs = [(question, text) for text in candidates]
    scores = reranker.predict(pairs)

    meta = metadata if metadata is not None else [{} for _ in candidates]

    ranked = [
        RankedCandidate(
            original_index=i,
            text=candidates[i],
            score=float(scores[i]),
            metadata=meta[i],
        )
        for i in range(len(candidates))
    ]
    ranked.sort(key=lambda x: x.score, reverse=True)

    logger.debug(
        "Reranking : %d candidats → top %d, score max=%.4f",
        len(candidates),
        min(top_n, len(ranked)),
        ranked[0].score if ranked else 0.0,
    )
    return ranked[:top_n]
