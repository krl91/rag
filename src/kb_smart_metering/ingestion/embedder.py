"""
Embedder BGE-M3 local via sentence-transformers.

Implémente EmbedderClient de graphiti-core pour permettre l'utilisation
des embeddings locaux (BAAI/bge-m3) sans appel cloud.
"""
from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import TYPE_CHECKING, Iterable

from graphiti_core.embedder import EmbedderClient

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Dimension des embeddings BGE-M3 (doit correspondre à EMBEDDING_DIM si défini)
BGE_M3_DIM = 1024


class BGEM3Embedder(EmbedderClient):
    """
    Embedder utilisant le modèle BAAI/bge-m3 en local.

    Le modèle est chargé en mémoire au premier appel (lazy loading)
    pour éviter un chargement inutile si l'embedder n'est pas utilisé.
    """

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self._model_name = model_name
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        """Charge le modèle si ce n'est pas encore fait (thread-safe via GIL)."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers est requis pour les embeddings. "
                    "Installez-le avec : uv sync"
                ) from exc
            logger.info("Chargement du modèle d'embedding : %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def _encode_sync(self, text: str) -> list[float]:
        """Encode un texte de façon synchrone (appelé dans un thread d'exécution)."""
        model = self._get_model()
        embedding = model.encode(text, normalize_embeddings=True)
        # SentenceTransformer retourne un np.ndarray ; les mocks peuvent retourner une liste
        if hasattr(embedding, "tolist"):
            return embedding.tolist()
        return list(embedding)

    async def create(
        self,
        input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]],
    ) -> list[float]:
        """
        Crée un embedding pour le texte ou la liste de tokens fournis.

        Graphiti passe généralement une liste contenant un seul élément str.
        L'encode est délégué à un thread d'exécution pour ne pas bloquer
        la boucle d'événements asyncio.
        """
        if isinstance(input_data, str):
            text = input_data
        elif isinstance(input_data, list) and input_data:
            first = input_data[0]
            text = first if isinstance(first, str) else str(first)
        else:
            text = str(input_data)

        loop = asyncio.get_running_loop()
        encode_fn = partial(self._encode_sync, text)
        return await loop.run_in_executor(None, encode_fn)
