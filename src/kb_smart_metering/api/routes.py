"""
Routeur API FastAPI — assistant et santé.

Endpoints :
  GET  /health       — vérification de l'état du service
  POST /ask          — pose une question au graphe de connaissances
                        (nécessite un LLM réseau joignable — Ollama)
  POST /search       — retrieval + contexte assemblé, SANS appel LLM ;
                        à un client (agent, script) de rédiger la réponse
                        à partir de ce contexte
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from kb_smart_metering.assistant.chain import AssistantChain
from kb_smart_metering.assistant.llm import ReponseStructuree

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assistant"])


# ---------------------------------------------------------------------------
# Schémas de requête / réponse
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    """Corps de la requête POST /ask."""

    question: str = Field(description="Question à poser au graphe de connaissances")
    as_of_date: Optional[datetime] = Field(
        default=None,
        description="Date de référence ISO pour les filtres temporels (ex: 2023-12-01T00:00:00)",
    )
    entity_types: Optional[list[str]] = Field(
        default=None,
        description="Types d'entités Graphiti à restreindre (ex: [\"Decision\", \"Action\"])",
    )


class AskResponse(BaseModel):
    """Corps de la réponse POST /ask."""

    question: str
    reponse: ReponseStructuree
    markdown: str = Field(description="Rendu Markdown compatible Obsidian")


class SearchRequest(BaseModel):
    """Corps de la requête POST /search."""

    question: str = Field(description="Question à poser au graphe de connaissances")
    as_of_date: Optional[datetime] = Field(
        default=None,
        description="Date de référence ISO pour les filtres temporels (ex: 2023-12-01T00:00:00)",
    )
    entity_types: Optional[list[str]] = Field(
        default=None,
        description="Types d'entités Graphiti à restreindre (ex: [\"Decision\", \"Action\"])",
    )


class SearchResponse(BaseModel):
    """Corps de la réponse POST /search."""

    question: str
    contexte: str = Field(
        description="Contexte assemblé (retrieval + reranking) — aucune réponse générée. "
        "À rédiger par le client (agent, script) à partir de ce contexte uniquement."
    )


class HealthResponse(BaseModel):
    """Corps de la réponse GET /health."""

    status: str = "ok"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse, summary="Vérification de l'état du service")
async def health() -> HealthResponse:
    """Retourne {\"status\": \"ok\"} si le service est opérationnel."""
    return HealthResponse()


@router.post("/ask", response_model=AskResponse, summary="Pose une question au graphe de connaissances")
async def ask(request: AskRequest) -> AskResponse:
    """
    Chaîne complète : question → retrieval → reranker → LLM → réponse structurée.

    La réponse inclut la version JSON structurée et le rendu Markdown Obsidian.
    """
    chain = AssistantChain()
    try:
        reponse = await chain.run(
            question=request.question,
            as_of_date=request.as_of_date,
            entity_types=request.entity_types,
        )
    except Exception as exc:
        logger.exception("Erreur lors du traitement de la question : %r", request.question[:80])
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    markdown = chain.render_markdown(question=request.question, reponse=reponse)

    return AskResponse(
        question=request.question,
        reponse=reponse,
        markdown=markdown,
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Retrieval + contexte assemblé — sans appel LLM",
)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Retrieval + reranking + contexte assemblé — AUCUN appel LLM côté serveur.

    Destiné à un client (agent Copilot, script) qui rédige lui-même la
    réponse structurée à partir de ce contexte, sans dépendre d'un LLM
    réseau côté serveur. Équivalent HTTP de `kb search`.
    """
    chain = AssistantChain()
    try:
        contexte = await chain.build_context(
            question=request.question,
            as_of_date=request.as_of_date,
            entity_types=request.entity_types,
        )
    except Exception as exc:
        logger.exception("Erreur lors de la recherche : %r", request.question[:80])
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return SearchResponse(question=request.question, contexte=contexte)
