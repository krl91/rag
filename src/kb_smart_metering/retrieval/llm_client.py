"""
Client LLM — envoie le contexte minimal au LLM via l'endpoint OpenAI-compatible
(Ollama) et valide la réponse JSON avec Pydantic.

Non implémenté dans cette phase. Squelette documenté.
"""

import logging

logger = logging.getLogger(__name__)


class LLMClient:
    """Client pour l'endpoint OpenAI-compatible (Ollama).

    N'envoie jamais un document complet au LLM : uniquement un contexte
    minimal assemblé par le retrieval.
    Sera implémenté en Phase 1.
    """
