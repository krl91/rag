"""
Configuration et construction du client Graphiti.

Fournit la fonction build_graphiti() qui instancie Graphiti avec :
- LLM local via endpoint OpenAI-compatible (Ollama)
- Embeddings BGE-M3 via sentence-transformers (BAAI/bge-m3)
- Base Neo4j issue des paramètres de configuration
"""

import logging

from graphiti_core.graphiti import Graphiti
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

from kb_smart_metering.config import settings
from kb_smart_metering.ingestion.embedder import BGEM3Embedder

logger = logging.getLogger(__name__)


def build_graphiti() -> Graphiti:
    """
    Construit une instance Graphiti configurée pour le projet smart metering.

    LLM
    ---
    Utilise l'endpoint OpenAI-compatible exposé par Ollama (OLLAMA_BASE_URL).
    Le mode structured_output_mode est forcé à ``json_object`` car la plupart
    des modèles Ollama ne supportent pas le mode ``json_schema``.

    Embeddings
    ----------
    BAAI/bge-m3 chargé localement via sentence-transformers (1024 dimensions).

    Reranker
    --------
    Non configuré (None) : Graphiti utilisera son comportement par défaut
    sans cross-encoder, ce qui convient aux LLM locaux de taille réduite.

    Retourne
    --------
    Graphiti
        Instance prête à l'emploi, à fermer avec await graphiti.close().
    """
    # api_key : valeur factice — ni Ollama ni le pont Copilot local n'exigent d'auth
    llm_config = LLMConfig(
        api_key=settings.llm_api_key or "ollama",
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
    )
    llm_client = OpenAIGenericClient(
        config=llm_config,
        # json_object : le schéma est injecté dans le prompt (compatible Ollama)
        structured_output_mode="json_object",
    )
    embedder = BGEM3Embedder(model_name=settings.embedding_model)

    logger.info(
        "Initialisation Graphiti — neo4j=%s, llm=%s, embedder=%s",
        settings.neo4j_uri,
        settings.ollama_model,
        settings.embedding_model,
    )

    return Graphiti(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        llm_client=llm_client,
        embedder=embedder,
        # cross_encoder non fourni → pas de reranker (compatible LLM locaux)
    )
