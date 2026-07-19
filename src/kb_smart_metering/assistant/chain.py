"""
Chaîne complète : question → retrieval → reranker → contexte → LLM → réponse.

Conçue pour être appelée depuis la CLI et l'API FastAPI.
Le graphe Graphiti est instancié à la demande et fermé après usage.
"""

import logging
from datetime import datetime
from typing import Optional

from kb_smart_metering.assistant.llm import LLMAssistant, ReponseStructuree
from kb_smart_metering.assistant.render import to_markdown
from kb_smart_metering.retrieval.context import (
    ContextItem,
    ContextSource,
    ContextType,
    assemble_context,
)
from kb_smart_metering.retrieval.reranker import rerank
from kb_smart_metering.retrieval.search import SearchCandidate

logger = logging.getLogger(__name__)

# Candidats récupérés avant reranking
_TOP_K_SEARCH = 20
# Candidats conservés après reranking
_TOP_N_RERANK = 8

_ABSENT_CONTEXT = "Aucun contexte disponible dans le graphe de connaissances."


def _candidate_to_context_item(candidate: SearchCandidate) -> ContextItem:
    """Convertit un SearchCandidate en ContextItem pour l'assemblage du contexte."""
    edge_lower = candidate.edge_name.lower()
    if "decision" in edge_lower or "décision" in edge_lower:
        ctx_type = ContextType.DECISION
    elif "action" in edge_lower:
        ctx_type = ContextType.ACTION
    elif "risk" in edge_lower or "risque" in edge_lower:
        ctx_type = ContextType.RISK
    elif "meeting" in edge_lower or "reunion" in edge_lower or "réunion" in edge_lower:
        ctx_type = ContextType.MEETING
    else:
        ctx_type = ContextType.FACT

    source = ContextSource(type="graph", identifier=candidate.uuid)
    valid_at = candidate.valid_at.date().isoformat() if candidate.valid_at else None

    return ContextItem(
        type=ctx_type,
        content=candidate.fact,
        source=source,
        valid_at=valid_at,
    )


class AssistantChain:
    """
    Orchestre la chaîne complète de réponse à une question.

    Paramètres
    ----------
    llm : LLMAssistant, optionnel
        Instance du client LLM. Un nouveau client est créé si absent.
    """

    def __init__(self, llm: Optional[LLMAssistant] = None) -> None:
        self._llm = llm or LLMAssistant()

    async def build_context(
        self,
        question: str,
        as_of_date: Optional[datetime] = None,
        entity_types: Optional[list[str]] = None,
    ) -> str:
        """
        Retrieval + reranking + assemblage de contexte — AUCUN appel LLM.

        C'est le cœur réutilisable de la chaîne : utilisé par `run()` (pipeline
        complet, pour les environnements avec un LLM réseau joignable — Ollama)
        et directement par la commande `kb search` (pour le flux conversationnel
        VS Code, où c'est l'agent Copilot qui rédige la réponse finale à partir
        de ce contexte, pas un appel HTTP côté Python).

        Paramètres
        ----------
        question : str
            Question posée par l'utilisateur.
        as_of_date : datetime, optionnel
            Date de référence pour filtrer les faits temporels.
        entity_types : list[str], optionnel
            Labels de nœuds Graphiti à restreindre (ex: ["Decision"]).

        Retourne
        --------
        str
            Contexte assemblé (markdown compact), prêt à être lu par un LLM.
        """
        from kb_smart_metering.ingestion.graphiti import build_graphiti
        from kb_smart_metering.retrieval.search import hybrid_search

        graphiti = build_graphiti()
        try:
            logger.info("Retrieval — question : %r", question[:80])
            candidates: list[SearchCandidate] = await hybrid_search(
                graphiti=graphiti,
                question=question,
                as_of_date=as_of_date,
                entity_types=entity_types,
                top_k=_TOP_K_SEARCH,
            )
        finally:
            await graphiti.close()

        logger.info("%d candidats récupérés", len(candidates))

        if not candidates:
            logger.warning("Aucun candidat — contexte vide pour : %r", question[:80])
            return _ABSENT_CONTEXT

        texts = [c.fact for c in candidates]
        meta = [{"candidate": c} for c in candidates]
        ranked = rerank(question=question, candidates=texts, top_n=_TOP_N_RERANK, metadata=meta)

        items: list[ContextItem] = []
        for rc in ranked:
            original: SearchCandidate = rc.metadata["candidate"]
            items.append(_candidate_to_context_item(original))

        contexte = assemble_context(items=items, question=question)
        logger.debug("Contexte assemblé — %d chars", len(contexte))
        return contexte

    async def run(
        self,
        question: str,
        as_of_date: Optional[datetime] = None,
        entity_types: Optional[list[str]] = None,
    ) -> ReponseStructuree:
        """
        Exécute la chaîne complète et retourne une réponse structurée.

        Nécessite un LLM réseau joignable (OLLAMA_BASE_URL) — utiliser
        `build_context()` directement si aucun LLM n'est disponible en
        Python (flux conversationnel VS Code, voir skill kb-chercheur).

        Retourne
        --------
        ReponseStructuree
            Réponse validée par Pydantic.
        """
        contexte = await self.build_context(
            question=question, as_of_date=as_of_date, entity_types=entity_types
        )
        reponse = self._llm.ask(question=question, contexte=contexte)
        logger.info("Réponse structurée — %d faits, %d décisions", len(reponse.facts), len(reponse.decisions))
        return reponse

    def render_markdown(self, question: str, reponse: ReponseStructuree) -> str:
        """Rend la réponse en markdown Obsidian."""
        return to_markdown(question=question, reponse=reponse)
